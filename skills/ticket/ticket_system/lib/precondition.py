"""Body-op precondition checks (W3-044 / W3-043).

提供 CLI body 操作（append-log / set-acceptance / complete 等）的 status
precondition 檢查，從根本阻斷「status=pending 期間執行 body 操作」的協議違反路徑。

設計重點：
- helper 為純函式，輸入 ticket dict + 參數，輸出 (ok, error_msg) tuple
- 不直接 print / exit，由 caller 決定如何輸出（測試友善）
- ``force=True`` 路徑記錄到 hook-logs，但失敗不阻斷主流程（觀測 vs 可用權衡）
- ``allow_completed=True`` 允許 completed 狀態通過（append-log 補 review 場景）
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ticket_system.constants import (
    STATUS_BLOCKED,
    STATUS_CLOSED,
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
)


# --- Constants ---------------------------------------------------------------

# hook-logs 路徑由 env var 控制，便於測試隔離
_HOOK_LOGS_DIR_ENV = "HOOK_LOGS_DIR"
_DEFAULT_HOOK_LOGS_DIR = ".claude/hook-logs"
_FORCE_LOG_FILENAME = "cli-force-usage.jsonl"

FORCE_BYPASS_WARNING = (
    "[Warning] --force 旁路 status precondition 檢查；使用已記入 hook-logs"
)


# --- Helpers -----------------------------------------------------------------


def _build_error_msg(
    ticket_id: str,
    operation: str,
    status: str,
    suggest: str,
) -> str:
    """組合統一格式的錯誤訊息。

    suggest 對應 status 的建議後續指令（見 _SUGGEST_MAP）。
    """
    suggestion = _SUGGEST_MAP.get(suggest, suggest)
    return (
        f"[Error] {ticket_id} 無法執行 {operation}："
        f"當前 status={status}，需要 status=in_progress\n"
        f"        建議：{suggestion}\n"
        f"        逃生閥：--force（記入 hook-logs，需於後續 review 中說明理由）"
    )


_SUGGEST_MAP = {
    "claim": "ticket track claim <ticket_id>",
    "reopen": "ticket track reopen <ticket_id>（若需修改）或檢視是否誤呼叫",
    "release": "ticket track release <ticket_id> 或解除 blockedBy 依賴後 claim",
    "closed-immutable": "該 ticket 已 closed；如需修改請建立新 ticket 處理",
    "unknown-status": "未知 status，請確認 ticket frontmatter 是否合規",
    "empty-ticket-id": "ticket_id 為空，無法執行操作；請提供合法 ticket ID",
}


def _resolve_hook_logs_dir() -> Path:
    """解析 hook-logs 目錄；env var 優先，否則用預設相對路徑。"""
    return Path(os.environ.get(_HOOK_LOGS_DIR_ENV, _DEFAULT_HOOK_LOGS_DIR))


def write_force_usage_log(
    ticket_id: str,
    operation: str,
    status_at_time: str,
    reason: str = "force-flag",
) -> None:
    """寫入 --force 使用記錄到 hook-logs JSONL。

    Append-only 語義；目錄不存在時自動建立；IOError 由 caller 處理。

    Why: --force 是元事件（meta-event），不屬 ticket 內容；若寫入 ticket md，
    與「force 旁路 status 檢查」語義自我矛盾。
    """
    logs_dir = _resolve_hook_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ticket_id": ticket_id,
        "operation": operation,
        "status_at_time": status_at_time,
        "reason": reason,
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"

    # POSIX O_APPEND 對 ≤ PIPE_BUF (4096 bytes) 為原子，單行 JSON 遠低於此閾值
    log_file = logs_dir / _FORCE_LOG_FILENAME
    with open(log_file, mode="a", encoding="utf-8") as f:
        f.write(line)
        f.flush()


def require_in_progress(
    ticket: Dict[str, Any],
    ticket_id: str,
    operation: str,
    *,
    allow_completed: bool = False,
    force: bool = False,
) -> Tuple[bool, Optional[str]]:
    """檢查 body 操作的 status precondition。

    Args:
        ticket: 已 load 的 ticket dict（含 status 欄位）
        ticket_id: ticket ID，用於錯誤訊息與 hook-logs 記錄
        operation: 呼叫端操作名稱（"append-log" / "set-acceptance" / "complete"）
        allow_completed: 是否允許 status=completed（True 用於 append-log 補 review）
        force: 是否旁路檢查（記錄到 hook-logs，returns (True, None)）

    Returns:
        (ok, error_msg)
        - ok=True, error_msg=None：通過檢查（或 --force 旁路）
        - ok=False, error_msg=str：阻擋，error_msg 含建議的後續指令
    """
    # 邊界檢查：空 ticket_id（A11）
    if not ticket_id or not isinstance(ticket_id, str):
        return (
            False,
            _build_error_msg(
                ticket_id=str(ticket_id) if ticket_id is not None else "",
                operation=operation,
                status="<unknown>",
                suggest="empty-ticket-id",
            ),
        )

    # 缺欄位防禦（A10）：預設視為 pending（最嚴格）
    status = ticket.get("status", STATUS_PENDING) if ticket else STATUS_PENDING

    # Force 旁路：先 log 再放行（log 失敗不阻斷主流程，C4）
    if force:
        try:
            write_force_usage_log(ticket_id, operation, status, reason="force-flag")
        except (OSError, IOError) as exc:
            sys.stderr.write(
                f"[Warning] force-log 寫入失敗（不阻斷主流程）：{exc}\n"
            )
        sys.stderr.write(FORCE_BYPASS_WARNING + "\n")
        return (True, None)

    # 主決策表
    if status == STATUS_IN_PROGRESS:
        return (True, None)
    if status == STATUS_COMPLETED:
        if allow_completed:
            return (True, None)
        return (False, _build_error_msg(ticket_id, operation, status, "reopen"))
    if status == STATUS_PENDING:
        return (False, _build_error_msg(ticket_id, operation, status, "claim"))
    if status == STATUS_BLOCKED:
        return (False, _build_error_msg(ticket_id, operation, status, "release"))
    if status == STATUS_CLOSED:
        return (False, _build_error_msg(ticket_id, operation, status, "closed-immutable"))
    # 未知 status
    return (False, _build_error_msg(ticket_id, operation, status, "unknown-status"))
