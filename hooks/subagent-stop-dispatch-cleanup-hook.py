#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
SubagentStop Dispatch Cleanup Hook

功能: 代理人真正完成時精準清理 dispatch-active.json 記錄 + 完成廣播。
觸發時機: SubagentStop（CC runtime 保證代理人真正停止才觸發）
行為: 不阻擋（exit 0），以 top-level systemMessage（純顯示通道）輸出 [OK]/[WAIT] 狀態。
       自激迴圈防護（1.0.0-W1-055.1）：
       1. stop_hook_active=true（runtime 因 stop hook 而繼續）時靜默 exit 0，
          斷開「注入 → 繼續 → 再停止 → 再注入」迴圈（CC hook 規格的防迴圈欄位）。
       2. [WAIT] 廣播以 agent_id + remaining 內容 hash 為 key 做 TTL 去重，
          同 key 在 TTL 內已播報則跳過輸出。
       3. 輸出通道自 hookSpecificOutput.additionalContext 回退 systemMessage：
          W1-055 ANA 活體確證 additionalContext 的投遞對象是「停止中的 subagent」
          （注入其對話並令其繼續，H1 confidence 0.95），與本 hook「通知 PM 主線程」
          意圖不符，且為自激迴圈的觸發核心；systemMessage 為 2026-06-05 前的
          已知良好狀態（每 agent_id 恆 1 次事件）。

來源:
  - W10-066 — 從 PostToolUse(Agent) 遷移清理和廣播職責到 SubagentStop
  - 0.19.1-W1-046 — CC 2.1.163 解禁後曾改用 additionalContext（已由 W1-055.1 回退）
  - 1.0.0-W1-055.1 — 自激迴圈斷路器 + WAIT 廣播 dedup + 通道回退 systemMessage
"""

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
)

from lib.dispatch_tracker import (
    clear_dispatch_by_id,
    clear_oldest_null_agent_id_entry,
    get_active_dispatches,
    get_state_file_path,
)

HOOK_NAME = "subagent-stop-dispatch-cleanup"

# [WAIT] 廣播去重 TTL：自激迴圈與多 agent 收尾叢集的觀測間隔為 5-15 秒/次、
# 鏈長 5-20 次（W1-055 重現實驗），10 分鐘足以覆蓋整段叢集；TTL 過後同 key
# 重新播報，避免長時間執行的真實 [WAIT] 狀態永久靜默。
WAIT_BROADCAST_DEDUP_TTL_SECONDS = 600


def _get_wait_dedup_state_file(project_root: Path) -> Path:
    """[WAIT] 廣播去重 state 檔路徑（hook-logs 已被 .gitignore 排除）。"""
    return (
        project_root / ".claude" / "hook-logs" / HOOK_NAME / "wait-broadcast-dedup.json"
    )


def check_and_record_broadcast(
    state_file: Path,
    key: str,
    ttl_seconds: int,
    logger,
    now: "float | None" = None,
) -> bool:
    """檢查同 key 是否在 TTL 內已播報過；未播報過則記錄本次播報。

    Returns:
        bool: True 表示 TTL 內已播報過（呼叫端應跳過輸出）；False 表示
              首次播報（已記錄 timestamp）。

    state 檔損毀或 IO 失敗時 fail-open（回 False 照常播報）：dedup 層異常
    寧可重複通知，不可吞掉真實通知（quality-baseline 規則 4 可觀測性）。
    """
    if now is None:
        now = time.time()

    state: dict = {}
    try:
        if state_file.exists():
            raw = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # 載入時順手剪除過期 entry，state 檔不無限成長
                state = {
                    k: v
                    for k, v in raw.items()
                    if isinstance(v, (int, float)) and now - v < ttl_seconds
                }
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.debug("dedup state 讀取失敗（fail-open 照常播報）: %s", e)
        state = {}

    if key in state:
        return True

    state[key] = now
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state), encoding="utf-8")
    except OSError as e:
        logger.debug("dedup state 寫入失敗（fail-open 照常播報）: %s", e)
    return False


def main() -> int:
    """SubagentStop 主邏輯：精準清理 + fallback + 三態廣播。"""
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0

    if not input_data:
        logger.debug("stdin 無資料，跳過")
        return 0

    agent_id = input_data.get("agent_id", "")

    if not agent_id:
        logger.error("SubagentStop 無 agent_id（schema violation）")
        return 0

    # 自激迴圈斷路器（1.0.0-W1-055.1 修復 1）：stop_hook_active=true 表示本次
    # 停止是「上一輪 stop hook 輸出令 agent 繼續」的結果，記錄已於首次事件
    # 清理完畢，任何輸出都會再度延續迴圈 —— 靜默退出。
    if input_data.get("stop_hook_active"):
        logger.debug(
            "stop_hook_active=true（stop hook 引發的繼續），靜默退出避免自激迴圈"
        )
        return 0

    # 定位專案根目錄
    project_root = Path(__file__).resolve().parent.parent.parent
    state_file = get_state_file_path(project_root)

    if not state_file.exists():
        logger.debug("dispatch-active.json 不存在，跳過")
        return 0

    messages = []
    cleared = False

    # 主路徑：agent_id 精準清理
    cleared = clear_dispatch_by_id(project_root, agent_id)

    if not cleared:
        # Fallback：清理 agent_id=null 且 dispatched_at 最早的一筆（FIFO）
        # SubagentStop input 無 description 欄位，無法做 description 匹配
        fallback_cleared = clear_oldest_null_agent_id_entry(project_root)
        if fallback_cleared:
            logger.info(
                "SubagentStop fallback 清理（agent_id=%s 無精準匹配，FIFO 清理最早 null entry）",
                agent_id,
            )
            cleared = True
        else:
            logger.warning(
                "SubagentStop agent_id=%s 無匹配記錄（精準和 FIFO 兩路徑皆失敗）",
                agent_id,
            )

    if cleared:
        messages.append(f"已清理派發記錄 agent_id={agent_id}")

    # 三態廣播（從 active-dispatch-tracker-hook 遷移）
    remaining = get_active_dispatches(project_root)
    if remaining:
        agents_list = ", ".join(
            d.get("agent_description", "?") for d in remaining
        )
        wait_message = (
            "[WAIT] 仍有 {} 個代理人在執行: {}".format(len(remaining), agents_list)
        )
        # WAIT 廣播 dedup（1.0.0-W1-055.1 修復 2）：同一 agent_id 對相同 remaining
        # 內容在 TTL 內只播報一次；remaining 變化（agent 增減）視為新狀態重新播報
        dedup_key = hashlib.sha256(
            "{}|{}".format(agent_id, wait_message).encode("utf-8")
        ).hexdigest()
        if check_and_record_broadcast(
            _get_wait_dedup_state_file(project_root),
            dedup_key,
            WAIT_BROADCAST_DEDUP_TTL_SECONDS,
            logger,
        ):
            logger.info("[WAIT] 廣播 dedup 命中（TTL 內已播報），跳過: %s", wait_message)
        else:
            messages.append(wait_message)
    elif cleared:
        messages.append("[OK] 所有代理人已完成，可開始驗收")

    if not messages:
        return 0

    context = " | ".join(messages)
    # 1.0.0-W1-055.1 修復 4：通道回退 top-level systemMessage（純顯示）。
    # additionalContext 經 W1-055 活體確證會注入「停止中的 subagent」並令其
    # 繼續（自激迴圈核心），與「通知 PM 主線程」意圖不符。
    print(json.dumps({"systemMessage": context}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
