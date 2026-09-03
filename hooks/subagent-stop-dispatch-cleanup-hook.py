#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
SubagentStop Dispatch Cleanup Hook

功能: 代理人回合結束時標記 dispatch-active.json 記錄的回合結束時刻
      （不刪除 entry）+ 回合狀態廣播。
觸發時機: SubagentStop
行為: 不阻擋（exit 0），以 top-level systemMessage（純顯示通道）輸出 [OK]/[WAIT] 狀態。
       自激迴圈防護（1.0.0-W1-055.1）：
       1. stop_hook_active=true（runtime 因 stop hook 而繼續）時靜默 exit 0，
          斷開「注入 → 繼續 → 再停止 → 再注入」迴圈（CC hook 規格的防迴圈欄位）。
       2. [WAIT] 廣播以 agent_id + still_running 內容 hash 為 key 做 TTL 去重，
          同 key 在 TTL 內已播報則跳過輸出。
       3. 輸出通道自 hookSpecificOutput.additionalContext 回退 systemMessage：
          W1-055 ANA 活體確證 additionalContext 的投遞對象是「停止中的 subagent」
          （注入其對話並令其繼續，H1 confidence 0.95），與本 hook「通知 PM 主線程」
          意圖不符，且為自激迴圈的觸發核心；systemMessage 為 2026-06-05 前的
          已知良好狀態（每 agent_id 恆 1 次事件）。

觸發前提修正（SubagentStop 刪除記錄前提失準修復票）：
  本 hook 原本記載的前提是「SubagentStop（CC runtime 保證代理人真正
  停止才觸發）」，據此在事件觸發時直接刪除 dispatch-active.json 記錄。
  實測前提不成立：代理人回合結束後轉入 idle 仍存活、仍列於代理人清單、
  仍可接受訊息並繼續工作，而其記錄已被清空——唯一追蹤存活狀態的資料源
  在代理人尚未終止時即消失，之後該代理人進入無資料源可見的狀態，同時
  使 bare-commit-guard-hook.py 等依 dispatch-active.json 判斷並行風險
  的防護在此期間降級（見 `.claude/lib/dispatch_tracker.py` 模組
  docstring「turn_ended_at 欄位」段的完整說明）。

  修法：`clear_dispatch_by_id` / `clear_oldest_null_agent_id_entry`（刪除
  式）改為 `mark_turn_ended_by_id` / `mark_oldest_active_null_agent_id_
  entry_turn_ended`（標記式，entry 保留、寫入 `turn_ended_at`）。連帶
  影響本 hook 自身的廣播語意：entry 不再消失，[WAIT]／[OK] 判斷改依
  `turn_ended_at` 是否為 None 篩出「當下真正在執行回合」的子集
  （`still_running`），不再用「entry 是否還在陣列中」判斷——後者在標記式
  設計下恆為真（entry 保留），若仍以此判斷會使 [WAIT] 對已結束回合的
  代理人永久誤報。[OK] 訊息措辭同步淡化為「目前無代理人在執行回合中」，
  不再宣稱「所有代理人已完成，可開始驗收」——標記式設計下無法確認代理人
  已真正終止，此宣稱與事實不符。

來源:
  - W10-066 — 從 PostToolUse(Agent) 遷移清理和廣播職責到 SubagentStop
  - 0.19.1-W1-046 — CC 2.1.163 解禁後曾改用 additionalContext（已由 W1-055.1 回退）
  - 1.0.0-W1-055.1 — 自激迴圈斷路器 + WAIT 廣播 dedup + 通道回退 systemMessage
  - SubagentStop 刪除記錄前提失準修復票 — 標記不刪除 + still_running 語意修正
  - 識別碼命名空間修復票 — 新增 mark_turn_ended_by_handle 精準比對路徑，
    先於既有 mark_turn_ended_by_id 呼叫（named 派發 tool_response.agentId
    不可靠，改用 dispatch 當下同步可得的 agent_handle 錨定比對）
"""

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
)

from lib.dispatch_tracker import (
    mark_turn_ended_by_handle,
    mark_turn_ended_by_id,
    mark_oldest_active_null_agent_id_entry_turn_ended,
    get_active_dispatches,
    get_state_file_path,
)

HOOK_NAME = "subagent-stop-dispatch-cleanup"


def _get_project_root() -> Path:
    """回傳本 hook 的 __file__ 導向專案根目錄（非 worktree-aware 的
    get_project_root()）。

    刻意設計為呼叫時求值（非 module 層級常數）：`__file__` 於函式呼叫當下
    才從 module 全域查找，測試以 importlib 動態載入後改寫 module.__file__
    時才能生效；若改成 import 當下即求值的常數，測試改寫 __file__ 的時機
    已晚於常數綁定，隔離機制會失效。供 run_hook_safely（liveness 索引）
    與 main()（state 解析、業務日誌）共用同一個值，避免各自呼叫無參數
    get_project_root() 時在 worktree 內執行分裂成不同 root。
    """
    return Path(__file__).resolve().parent.parent.parent


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
    """SubagentStop 主邏輯：標記回合結束 + fallback + 三態廣播。"""
    # __file__ 導向 root，使日誌解析與狀態解析採同一 root。hook 若在
    # worktree 內執行，各自呼叫無參數 get_project_root() 會分裂成不同
    # root，日誌落在 worktree 副本而非主 repo，FIFO 誤刪等訊號因此無人
    # 可查閱。
    project_root = _get_project_root()
    logger = setup_hook_logging(HOOK_NAME, project_root=project_root)

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

    state_file = get_state_file_path(project_root)

    if not state_file.exists():
        logger.debug("dispatch-active.json 不存在，跳過")
        return 0

    messages = []
    marked = False

    # 主路徑一：agent_handle 錨定比對（named 派發，dispatch 當下同步可得，
    # 不依賴 tool_response.agentId——該欄位對 named 派發已證實不可靠，
    # 見 dispatch_tracker.py 模組 docstring「agent_handle 欄位」段）
    marked = mark_turn_ended_by_handle(project_root, agent_id)

    # 主路徑二：agent_id 精準標記回合結束（entry 保留，不刪除；未命名
    # 派發的既有路徑，agent_handle 比對失敗或無 handle 可比對時才嘗試）
    if not marked:
        marked = mark_turn_ended_by_id(project_root, agent_id)

    if not marked:
        # Fallback：標記 agent_id=null 且尚未標記過回合結束的最早一筆（FIFO）
        # SubagentStop input 無 description 欄位，無法做 description 匹配。
        #
        # 候選數 > 1 時停用 FIFO：isolation=none 派發的 agent_id 全記為
        # null，此時「最早」不代表「本次真正結束的那一筆」，標記任一筆
        # 都可能誤將仍在執行中的代理人記錄判為已結束回合。候選數 > 1 時
        # 不標記任何記錄，只寫 WARNING，留待 cleanup_expired 依超時回收。
        null_candidates = [
            d for d in get_active_dispatches(project_root)
            if d.get("agent_id") is None and d.get("turn_ended_at") is None
        ]
        if len(null_candidates) > 1:
            logger.warning(
                "SubagentStop agent_id=%s 無精準匹配，null 候選 %d 筆（>1）"
                "已停用 FIFO 後援避免誤標，待 cleanup_expired 超時回收",
                agent_id,
                len(null_candidates),
            )
        else:
            fallback_marked = mark_oldest_active_null_agent_id_entry_turn_ended(
                project_root
            )
            if fallback_marked:
                logger.info(
                    "SubagentStop fallback 標記回合結束（agent_id=%s 無精準匹配，"
                    "FIFO 標記最早 null entry）",
                    agent_id,
                )
                marked = True
            else:
                logger.warning(
                    "SubagentStop agent_id=%s 無法標記回合結束（精準和 FIFO 兩路徑皆失敗）",
                    agent_id,
                )

    if marked:
        messages.append(f"已標記回合結束 agent_id={agent_id}")

    # 三態廣播（從 active-dispatch-tracker-hook 遷移）。entry 標記後仍保留
    # 在陣列中（見模組頂部「觸發前提修正」段），[WAIT]／[OK] 改依
    # turn_ended_at 是否為 None 篩出「當下真正在執行回合」的子集，不再用
    # 「entry 是否還在陣列中」判斷（後者恆為真，會對已結束回合者永久誤報）。
    still_running = [
        d for d in get_active_dispatches(project_root)
        if d.get("turn_ended_at") is None
    ]
    if still_running:
        agents_list = ", ".join(
            d.get("agent_description", "?") for d in still_running
        )
        wait_message = (
            "[WAIT] 仍有 {} 個代理人在執行: {}".format(len(still_running), agents_list)
        )
        # WAIT 廣播 dedup（1.0.0-W1-055.1 修復 2）：同一 agent_id 對相同
        # still_running 內容在 TTL 內只播報一次；內容變化（agent 增減）
        # 視為新狀態重新播報
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
    elif marked:
        # 不宣稱「已完成，可開始驗收」：標記式設計下無法確認代理人已真正
        # 終止，僅能確認「當下無代理人在執行回合中」。
        messages.append("[OK] 目前無代理人在執行回合中")

    if not messages:
        return 0

    context = " | ".join(messages)
    # 1.0.0-W1-055.1 修復 4：通道回退 top-level systemMessage（純顯示）。
    # additionalContext 經 W1-055 活體確證會注入「停止中的 subagent」並令其
    # 繼續（自激迴圈核心），與「通知 PM 主線程」意圖不符。
    print(json.dumps({"systemMessage": context}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    # project_root 顯式傳入：使 run_hook_safely 內部的 liveness 索引寫入
    # （main() 執行前，mark_hook_entry）也採 __file__ 導向 root，與 main()
    # 內業務日誌/狀態解析對齊，避免 worktree 內執行時分裂成不同 root。
    sys.exit(run_hook_safely(main, HOOK_NAME, project_root=_get_project_root()))
