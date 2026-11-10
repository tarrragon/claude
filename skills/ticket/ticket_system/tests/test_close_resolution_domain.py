"""close 的 resolved_by 值域驗證測試（3.1.0-W1-057）。

close 改為呼叫與 set-closed-by、version-tracking-consistency-guard-hook 相同的
值域函式（.claude/lib/close_resolution.py）。本檔驗證 close 端：
- transferred_to_issue 為合法 reason，resolved_by 只收 issue 參照
- 其餘 reason 不再「不驗」：值域外的值被拒（正向對照，E2）
- Ticket ID 指向不存在的票被拒
- requirement_vanished／cancelled_by_user 的 reason_note 必填照舊
"""

from __future__ import annotations

import pytest

from ticket_system.commands.lifecycle import TicketLifecycle
from ticket_system.constants import CLOSE_REASONS

EXISTING_ID = "0.0.0-W0-201"


@pytest.fixture
def lifecycle(monkeypatch) -> TicketLifecycle:
    from ticket_system.commands import lifecycle as lifecycle_mod

    def _fake_load_ticket(version: str, ticket_id: str):
        return {"id": ticket_id} if ticket_id == EXISTING_ID else None

    monkeypatch.setattr(lifecycle_mod, "load_ticket", _fake_load_ticket)
    return TicketLifecycle("0.0.0")


def _validate(lc: TicketLifecycle, reason: str, resolved_by: str, note: str = "說明"):
    return lc._validate_close_resolution(
        resolved_by=resolved_by, reason_code=reason, reason_note=note,
    )


def test_transferred_to_issue_is_close_reason():
    assert "transferred_to_issue" in CLOSE_REASONS


@pytest.mark.parametrize(
    "reason,value",
    [
        ("transferred_to_issue", "tarrragon/claude#60"),
        ("superseded_by", EXISTING_ID),
        ("duplicate", EXISTING_ID),
        ("goal_achieved", "none"),
        ("goal_achieved", EXISTING_ID),
        ("not_executable_knowledge_captured", "none"),
        ("requirement_vanished", "none"),
        ("cancelled_by_user", "none"),
    ],
)
def test_accepts_in_domain(lifecycle, reason, value):
    assert _validate(lifecycle, reason, value) is None


@pytest.mark.parametrize(
    "reason,value",
    [
        ("transferred_to_issue", "none"),
        ("transferred_to_issue", EXISTING_ID),
        ("superseded_by", "none"),
        ("duplicate", "tarrragon/claude#60"),
        ("goal_achieved", "tarrragon/claude#60"),
        ("goal_achieved", "thyme-python-developer"),
        ("not_executable_knowledge_captured", ""),
        ("not_executable_knowledge_captured", "tarrragon/claude#60"),
    ],
)
def test_rejects_out_of_domain(lifecycle, reason, value):
    error = _validate(lifecycle, reason, value)
    assert error is not None
    assert "closed_by 須為" in error


@pytest.mark.parametrize("reason", ["superseded_by", "goal_achieved"])
def test_rejects_nonexistent_ticket_id(lifecycle, reason):
    error = _validate(lifecycle, reason, "0.0.0-W0-999")
    assert error is not None
    assert "不存在" in error


@pytest.mark.parametrize("reason", ["requirement_vanished", "cancelled_by_user"])
def test_note_still_required(lifecycle, reason):
    error = _validate(lifecycle, reason, "none", note="")
    assert error is not None
    assert "--reason-note 必填" in error


def test_defer_semantics_still_rejected(lifecycle):
    error = _validate(lifecycle, "transferred_to_issue", "tarrragon/claude#60", note="後續處理")
    assert error is not None
    assert "延後語意" in error


def test_fails_closed_when_shared_module_missing(lifecycle, monkeypatch):
    from ticket_system.lib import close_resolution_check

    monkeypatch.setattr(close_resolution_check, "load_claude_lib", lambda name: None)
    error = _validate(lifecycle, "goal_achieved", "none")
    assert error is not None
    assert "無法載入" in error
