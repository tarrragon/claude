#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml", "filelock>=3.12"]
# ///

"""
依賴說明（PC-135 復發模式）：handoff_utils 的 import 鏈為
handoff_utils -> ticket_system.lib.constants -> lib/__init__ -> ticket_loader
-> parser -> file_lock -> filelock，本 hook 以 `uv run --script`（PEP 723
script 環境）執行時僅按 dependencies 宣告安裝套件，缺 filelock 會使 import
落入 degraded fallback（resolve_target 恆回 None、is_handoff_stale 恆回非
stale），造成 target 顯示與 stale 過濾在真實 runtime 環境不生效，但 pytest
因專案 venv 已裝 filelock 而不會偵測到此缺口。
Action：異動本檔或 handoff_utils 的 import 範圍時，須同步比對 PEP 723
dependencies 是否涵蓋新 import 鏈的 transitive 依賴；驗收須以實際
`uv run --script` 執行方式複驗，pytest 綠燈不構成本檔行為的驗收依據。

Handoff 待恢復任務提醒 Hook

在 Session 啟動時檢查是否有待恢復的 handoff 任務。

功能:
1. 掃描 .claude/handoff/pending/ 目錄
2. 讀取所有 JSON handoff 檔案
3. 提取 ticket_id 和 title
4. 若有待恢復任務 → 顯示提醒訊息

使用方式:
    SessionStart Hook 自動觸發，或手動測試:
    python3 .claude/hooks/handoff-reminder-hook.py

輸入格式:
    SessionStart Hook 提供的 JSON (stdin，可選)

環境變數:
    CLAUDE_PROJECT_DIR: 專案根目錄
    HOOK_DEBUG: 啟用詳細日誌 (true/false)
"""

import sys
import json
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    parse_ticket_frontmatter,
    find_ticket_file,
)

# 加入 ticket_system lib 路徑以引用 handoff_utils.is_handoff_stale（W17-095.3）
# 同時加入 skills/ticket 父路徑以解析 handoff_utils 內部的 `from ticket_system.lib.*`
# import（缺此路徑會使 import 靜默降級為 ModuleNotFoundError fallback，
# resolve_target 永遠回 None，與 handoff-auto-resume-stop-hook.py 對齊補上）。
_TICKET_SKILL_PATH = Path(__file__).resolve().parents[1]
_TICKET_LIB_PATH = _TICKET_SKILL_PATH / "ticket_system" / "lib"
for _p in (_TICKET_SKILL_PATH, _TICKET_LIB_PATH):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from handoff_utils import is_handoff_stale, resolve_target  # type: ignore
except Exception as _import_err:  # pragma: no cover - fallback：lib 不可用時不過濾，行為退化為原狀
    # PC-135 防護：silent fallback 改 noisy。退化為「全不過濾」會讓 reminder 列出已 stale 的 handoff，
    # 雖偏保守側但會干擾用戶體驗，必須立即可見。
    sys.stderr.write(
        f"[handoff-reminder-hook][PC-135] handoff_utils import failed, "
        f"using degraded is_handoff_stale fallback (no stale filtering). "
        f"Cause: {type(_import_err).__name__}: {_import_err}\n"
    )
    def is_handoff_stale(record, project_root=None):  # type: ignore
        return False, ""

    def resolve_target(record):  # type: ignore
        # 退化 fallback：無 lib 時無法解析 target_ticket_id / direction 後綴，
        # 由呼叫端 `resolve_target(record) or record.get("ticket_id")` 自動 fallback 至來源票。
        return None

import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# 全域常數
EXIT_SUCCESS = 0
EXIT_ERROR = 1

def scan_handoff_pending_directory(project_root: Path, logger) -> Tuple[List[Dict[str, Any]], int]:
    """
    掃描 .claude/handoff/pending/ 目錄中的所有待恢復任務

    目錄結構:
    .claude/handoff/
      └── pending/
          ├── 0.31.0-W4-001.1.json
          ├── 0.31.0-W4-002.json
          └── ...

    JSON 檔案格式:
    {
        "ticket_id": "0.31.0-W4-001.1",
        "title": "任務標題",
        "what": "工作內容描述",
        "direction": "to-parent|to-child",
        "timestamp": "ISO8601 時間戳",
        "resumed_at": null,
        "chain": {...},
        ...
    }

    Args:
        project_root: 專案根目錄

    Returns:
        tuple - (待恢復任務列表（按 timestamp 排序）, 已過濾 stale 數量)
    """
    pending_tasks = []
    stale_count = 0

    handoff_dir = project_root / ".claude" / "handoff" / "pending"

    if not handoff_dir.exists():
        logger.info(f"handoff/pending 目錄不存在: {handoff_dir}")
        return pending_tasks, stale_count

    if not handoff_dir.is_dir():
        logger.warning(f"handoff/pending 不是目錄: {handoff_dir}")
        return pending_tasks, stale_count

    # 掃描所有 .json 檔案
    try:
        for file_path in sorted(handoff_dir.glob("*.json")):
            logger.debug(f"掃描檔案: {file_path.name}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 檢查是否已被接手（有 resumed_at 時間戳表示已接手）
                resumed_at = data.get("resumed_at")
                if resumed_at is not None:
                    logger.debug(f"跳過已接手的任務: {file_path.stem} (resumed_at: {resumed_at})")
                    continue

                # W17-095.3：過濾 stale handoff（與 CLI resume --list 對齊）
                try:
                    is_stale, stale_reason = is_handoff_stale(data, project_root)
                except Exception as stale_err:
                    logger.warning(f"is_handoff_stale 判斷失敗 ({file_path.name}): {stale_err}")
                    is_stale, stale_reason = False, ""
                if is_stale:
                    stale_count += 1
                    logger.debug(f"跳過 stale handoff: {file_path.stem} ({stale_reason})")
                    continue

                # 提取必要欄位
                ticket_id = data.get("ticket_id", file_path.stem)
                title = data.get("title", "無標題")
                direction = data.get("direction", "unknown")

                # 不變式：顯示/排序/判定路徑一律以
                # `resolve_target(record) or record.get("ticket_id")` 解析出的
                # target 為對象；不可改成「有 target 才顯示」，因為 direction=auto
                # 記錄的 ticket_id 欄位本身就是 target（lifecycle.py 產生）。
                # 本檔為 SessionStart reminder，target_id 只用於待恢復清單顯示，
                # 不涉及阻塞/GC 判斷（GC 由 is_handoff_stale 於上方獨立處理）。
                target_id = resolve_target(data) or ticket_id
                display_title = title
                if target_id != ticket_id:
                    target_path = find_ticket_file(target_id, project_root, logger)
                    if target_path:
                        target_frontmatter = parse_ticket_frontmatter(target_path, logger)
                        if target_frontmatter and target_frontmatter.get("title"):
                            display_title = target_frontmatter["title"]

                pending_tasks.append({
                    "ticket_id": target_id,
                    "title": display_title,
                    "direction": direction,
                    "file_path": str(file_path),
                    "timestamp": data.get("timestamp", "unknown"),
                    "what": data.get("what", ""),
                    "chain": data.get("chain", {}),
                    "from_status": data.get("from_status", "unknown"),
                })

                logger.debug(f"找到待恢復任務: {target_id} - {display_title}")

            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失敗 ({file_path.name}): {e}")
            except Exception as e:
                logger.warning(f"讀取檔案失敗 ({file_path.name}): {e}")

    except Exception as e:
        logger.error(f"掃描 handoff/pending 目錄失敗: {e}")

    logger.info(
        f"掃描完成，找到 {len(pending_tasks)} 個待恢復任務"
        + (f"（已過濾 {stale_count} 個 stale）" if stale_count else "")
    )

    # 按 timestamp 排序（最新優先）
    pending_tasks.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
    return pending_tasks, stale_count

def mark_handoff_as_resumed(ticket_id: str, project_root: Path, logger) -> None:
    """
    標記 handoff 檔案為已接手（更新 resumed_at 欄位）

    Args:
        ticket_id: Ticket ID
        project_root: 專案根目錄
        logger: 日誌物件
    """
    handoff_dir = project_root / ".claude" / "handoff" / "pending"
    handoff_file = handoff_dir / f"{ticket_id}.json"

    if not handoff_file.exists():
        logger.warning(f"Handoff 檔案不存在: {handoff_file}")
        return

    try:
        with open(handoff_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 更新 resumed_at 欄位
        data["resumed_at"] = datetime.now().isoformat()

        with open(handoff_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"已標記 Handoff 為已接手: {ticket_id}")
    except Exception as e:
        logger.warning(f"標記 Handoff 失敗 ({ticket_id}): {e}")

def generate_reminder_message(
    pending_tasks: List[Dict[str, Any]],
    logger,
    stale_count: int = 0,
) -> str:
    """
    生成 Handoff 待恢復任務提醒訊息

    Args:
        pending_tasks: 待恢復任務列表
        logger: 日誌物件
        stale_count: 已過濾掉的 stale handoff 數量（W17-095.3，與 CLI resume --list 對齊）

    Returns:
        str - 格式化的提醒訊息
    """
    if not pending_tasks and not stale_count:
        return ""

    message = "============================================================\n"
    message += f"[Handoff 提醒] 有 {len(pending_tasks)} 個待恢復的任務\n"
    if stale_count:
        message += f"            （已過濾 {stale_count} 個 stale handoff，與 ticket resume --list 一致）\n"
    message += "============================================================\n\n"

    message += "待恢復任務：\n"
    for i, task in enumerate(pending_tasks, 1):
        ticket_id = task["ticket_id"]
        title = task["title"]
        direction = task["direction"]

        message += f"  {i}. {ticket_id}: {title}\n"
        message += f"     方向: {direction}\n"

    message += "\n執行提醒：\n"
    message += "  /ticket resume <id>        恢復指定任務 context\n"
    message += "  /ticket resume --list      查看完整清單\n\n"

    message += "============================================================\n"

    return message

def generate_hook_output(
    pending_tasks: List[Dict[str, Any]],
    project_root: Path,
    logger,
    stale_count: int = 0,
) -> Dict[str, Any]:
    """
    生成 Hook 輸出格式

    若有待恢復任務，顯示提醒訊息（純提醒模式，不自動標記）

    Args:
        pending_tasks: 待恢復任務列表
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        dict - Hook 輸出 JSON
    """
    # 若無待恢復任務，靜默跳過（不輸出任何訊息）
    if not pending_tasks:
        logger.info("無待恢復任務，不產生輸出")
        return {
            "suppressOutput": True
        }

    # 生成提醒訊息
    reminder_message = generate_reminder_message(pending_tasks, logger, stale_count=stale_count)

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": reminder_message
        },
        "suppressOutput": False
    }

def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化日誌
    2. 讀取 JSON 輸入（可選，SessionStart 可能無 stdin）
    3. 取得專案根目錄
    4. 掃描 .claude/handoff/pending/ 目錄
    5. 產生 Hook 輸出（自動載入或提醒）
    6. 輸出 JSON 結果

    Returns:
        int - Exit code (0 = 成功)
    """
    logger = setup_hook_logging("handoff-reminder-hook")

    try:
        # 步驟 1: 初始化日誌
        logger.info("Handoff 提醒 Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入（可選）
        input_data = read_json_from_stdin(logger)
        if not input_data:
            return 0

        # 步驟 3: 取得專案根目錄
        project_root = get_project_root()
        logger.info(f"專案根目錄: {project_root}")

        # 步驟 4: 掃描待恢復任務（W17-095.3：含 stale 過濾計數）
        pending_tasks, stale_count = scan_handoff_pending_directory(project_root, logger)

        # 步驟 5: 產生 Hook 輸出（自動載入最新任務或靜默跳過）
        hook_output = generate_hook_output(pending_tasks, project_root, logger, stale_count=stale_count)

        # 步驟 6: 輸出 JSON 結果
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        logger.info("Hook 執行完成")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        # 錯誤時也靜默跳過（非阻塊）
        print(json.dumps({
            "suppressOutput": True
        }, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS  # 不中斷 Session 啟動

if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "handoff-reminder"))
