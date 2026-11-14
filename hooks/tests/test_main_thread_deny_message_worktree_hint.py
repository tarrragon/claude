"""
Test: 主線程拒絕訊息含持票者的 worktree 指引

驗證預設拒絕與程式碼拒絕兩則訊息，除「建立 Ticket 派發代理人」之外，
另給已持票者可執行的處置：worktree create <ticket-id> 後在 worktree 修改。
判定結果不在此驗證（由既有 main-thread 測試覆蓋）。
"""

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR.parent))


@pytest.mark.parametrize(
    "attr", ["EDIT_BLOCKED_DEFAULT_DENY", "EDIT_BLOCKED_PROGRAM_FILES"]
)
def test_deny_message_has_worktree_hint_for_ticket_holder(attr):
    from lib.hook_messages import GateMessages

    message = getattr(GateMessages, attr)
    assert "worktree create <ticket-id>" in message
    assert "已持有該 Ticket" in message
