"""closed_by 值域共用驗證函式與 session 啟動稽核的測試（3.1.0-W1-057）。

驗證：
- lib.close_resolution.validate_closed_by 依 close_reason 限定值域
- 各 reason 配不合法值時被拒（正向對照，E2）
- version-tracking-consistency-guard-hook 的 closed 票稽核呼叫同一個函式：
  以 none 合法關閉的存量票不報警告、transferred_to_issue + issue 參照不報警告、
  值域外的值照報
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).resolve().parent.parent  # .claude/hooks
sys.path.insert(0, str(_hooks_dir.parent))
sys.path.insert(0, str(_hooks_dir))

from lib.close_resolution import (  # noqa: E402
    KIND_INVALID,
    KIND_ISSUE_REF,
    KIND_NONE,
    KIND_TICKET_ID,
    classify_closed_by,
    validate_closed_by,
)

_spec = importlib.util.spec_from_file_location(
    "version_tracking_consistency_guard_hook_close",
    _hooks_dir / "version-tracking-consistency-guard-hook.py",
)
guard_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard_hook)

TICKET_ID = "3.1.0-W1-041"
ISSUE_REF = "tarrragon/claude#60"


class TestClassify:
    @pytest.mark.parametrize(
        "value,kind",
        [
            ("none", KIND_NONE),
            ("NONE", KIND_NONE),
            (TICKET_ID, KIND_TICKET_ID),
            ("3.1.0-W1-041.2", KIND_TICKET_ID),
            (ISSUE_REF, KIND_ISSUE_REF),
            ("some-org/repo.name#123", KIND_ISSUE_REF),
            ("", KIND_INVALID),
            (None, KIND_INVALID),
            ("thyme-python-developer", KIND_INVALID),
            ("claude#60", KIND_INVALID),
            ("tarrragon/claude#0", KIND_INVALID),
            ("tarrragon/claude", KIND_INVALID),
        ],
    )
    def test_kind(self, value, kind):
        assert classify_closed_by(value) == kind


class TestDomainAccepts:
    @pytest.mark.parametrize(
        "reason,value",
        [
            ("superseded_by", TICKET_ID),
            ("duplicate", TICKET_ID),
            ("transferred_to_issue", ISSUE_REF),
            ("goal_achieved", "none"),
            ("goal_achieved", TICKET_ID),
            ("not_executable_knowledge_captured", "none"),
            ("requirement_vanished", "none"),
            ("cancelled_by_user", TICKET_ID),
            ("unknown", "none"),
            (None, "none"),
        ],
    )
    def test_accepts(self, reason, value):
        assert validate_closed_by(reason, value) is None


class TestDomainRejects:
    """正向對照：各 reason 配值域外的值必須被拒。"""

    @pytest.mark.parametrize(
        "reason,value",
        [
            ("superseded_by", "none"),
            ("superseded_by", ISSUE_REF),
            ("duplicate", "none"),
            ("duplicate", ISSUE_REF),
            ("transferred_to_issue", "none"),
            ("transferred_to_issue", TICKET_ID),
            ("transferred_to_issue", "claude#60"),
            ("goal_achieved", ISSUE_REF),
            ("not_executable_knowledge_captured", ISSUE_REF),
            ("requirement_vanished", "thyme-python-developer"),
            ("cancelled_by_user", ""),
            (None, ISSUE_REF),
        ],
    )
    def test_rejects(self, reason, value):
        error = validate_closed_by(reason, value)
        assert error is not None
        assert repr(value) in error


def _closed(ticket_id, closed_by, close_reason=None, note=""):
    fm = {"id": ticket_id, "status": "closed", "closed_by": closed_by}
    if close_reason is not None:
        fm["close_reason"] = close_reason
    if note:
        fm["close_reason_note"] = note
    return fm


class TestHookClosedTicketAudit:
    def test_none_with_default_reason_not_reported(self):
        tickets = [_closed("9.9.9-W1-001", "none", "not_executable_knowledge_captured")]
        assert guard_hook.detect_closed_ticket_anomalies(tickets) == []

    def test_issue_ref_with_transferred_reason_not_reported(self):
        tickets = [_closed("9.9.9-W1-002", ISSUE_REF, "transferred_to_issue")]
        assert guard_hook.detect_closed_ticket_anomalies(tickets) == []

    def test_legacy_ticket_without_reason_accepts_none(self):
        tickets = [_closed("9.9.9-W1-003", "none")]
        assert guard_hook.detect_closed_ticket_anomalies(tickets) == []

    def test_none_with_superseded_reported(self):
        tickets = [_closed("9.9.9-W1-004", "none", "superseded_by")]
        anomalies = guard_hook.detect_closed_ticket_anomalies(tickets)
        assert len(anomalies) == 1
        assert "9.9.9-W1-004" in anomalies[0]

    def test_issue_ref_with_default_reason_reported(self):
        tickets = [_closed("9.9.9-W1-005", ISSUE_REF, "goal_achieved")]
        anomalies = guard_hook.detect_closed_ticket_anomalies(tickets)
        assert len(anomalies) == 1

    def test_agent_name_reported(self):
        tickets = [_closed("9.9.9-W1-006", "thyme-python-developer", "goal_achieved")]
        assert len(guard_hook.detect_closed_ticket_anomalies(tickets)) == 1

    def test_hook_uses_shared_validator(self):
        assert guard_hook.validate_closed_by is validate_closed_by
