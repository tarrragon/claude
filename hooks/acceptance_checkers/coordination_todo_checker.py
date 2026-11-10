"""
Coordination Todo Checker - 協調票 complete／close 前的未配對用戶待辦檢查

Why: 協調票帶未配對的用戶待辦（U1）結案，殘留事項被埋在已完成的舊票，看板讀不到。
Consequence: 不擋則用戶待辦靜默遺失。
Action: frontmatter 有 `coordination: true` 且未配對數大於 0 時阻擋，訊息列各鍵與兩條解法。

失敗語意：解析（匯入或配對函式）拋例外時 fail-open（放行），並寫 stderr 與 logger.error。
觸發條件：coordination_ticket 模組無法匯入，或 parse_user_todos 拋例外。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "skills" / "multi-session-orchestration" / "scripts"
)

TODO_DONE_FORMAT = "**用戶待辦完成**（<鍵>）：<結果>"
TODO_TRANSFER_FORMAT = "**用戶待辦完成**（<鍵>）：轉移至 <新協調票號>"


def _is_coordination(frontmatter: dict) -> bool:
    return str(frontmatter.get("coordination", "")).strip().lower() == "true"


def _format_block_message(ticket_id: str, todos: list, action: str = "complete") -> str:
    rows = "\n".join(
        "  - %s：%s" % (t["key"] if t["key"] is not None else "（無鍵）", t["item"])
        for t in todos
    )
    return (
        "協調票 %s 仍有 %d 項未配對的用戶待辦，%s 被阻擋：\n%s\n\n"
        "解法一：在 Solution 為每項寫完成行 `%s`。\n"
        "解法二（轉移）：寫完成行並註明轉移，`%s`，"
        "再到新協調票用新鍵重寫待辦行。\n"
        "格式見 .claude/skills/multi-session-orchestration/references/line-continuity.md §2〈用戶待辦〉"
        % (ticket_id, len(todos), action, rows, TODO_DONE_FORMAT, TODO_TRANSFER_FORMAT)
    )


def check_unpaired_user_todos(
    content: str, frontmatter: dict, ticket_id: str, logger, action: str = "complete"
) -> Tuple[bool, str]:
    """回傳 (should_block, message)。非協調票或無未配對項回 (False, "")。"""
    if not _is_coordination(frontmatter):
        return False, ""
    try:
        if str(_SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(_SCRIPTS_DIR))
        from coordination_ticket import parse_user_todos

        todos = parse_user_todos(content)
    except Exception as exc:  # fail-open：判定失敗不應封死所有協調票收尾
        sys.stderr.write(f"[coordination_todo_checker] 判定失敗，放行: {exc}\n")
        logger.error(f"協調票用戶待辦檢查失敗，fail-open 放行 {ticket_id}: {exc}")
        return False, ""
    if not todos:
        return False, ""
    return True, _format_block_message(ticket_id, todos, action)
