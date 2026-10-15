"""complete／改派時後設欄位同步（tdd_phase、who.history、Executing Agent、Review Status）。

E1 對照：每個修正都配「不該變的情形」（manual 來源、current 未變、非 IMP 以外類型）。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from ticket_system.lib.identity_guard import PM_AGENT_NAME

BODY = """# Execution Log

## Solution

{solution}

## Completion Info

**Completion Time**: (pending)
**Executing Agent**: thyme-python-developer
**Review Status**: pending
"""

STAGES = ["phase1", "phase2", "phase3a", "phase3b", "phase4"]


def _ticket(**over):
    t = {
        "id": "0.18.0-W17-999",
        "type": "IMP",
        "status": "in_progress",
        "title": "Test",
        "who": {"current": "thyme-python-developer", "history": {}},
        "acceptance": [{"text": "x", "completed": True}],
        "tdd_phase": "phase1",
        "tdd_stage": list(STAGES),
        "_body": BODY.format(solution="無審查"),
        "_path": "/tmp/fake.md",
    }
    t.update(over)
    return t


def _complete(ticket):
    """執行 complete，回傳存檔時的 ticket。"""
    from ticket_system.commands.lifecycle import TicketLifecycle

    saved = {}

    def fake_save(t, p):
        saved["t"] = {k: (dict(v) if isinstance(v, dict) else v) for k, v in t.items()}

    with patch("ticket_system.commands.lifecycle.load_and_validate_ticket",
               return_value=(ticket, None)), \
         patch("ticket_system.commands.lifecycle.validate_completable_status",
               return_value=(True, "", False)), \
         patch("ticket_system.commands.lifecycle.validate_acceptance_criteria",
               return_value=(True, [])), \
         patch("ticket_system.commands.lifecycle.validate_execution_log",
               return_value=(True, [])), \
         patch("ticket_system.commands.lifecycle.validate_execution_log_by_type",
               return_value=(True, [])), \
         patch("ticket_system.commands.lifecycle.validate_self_check_subsection",
               return_value=(True, "")), \
         patch("ticket_system.commands.lifecycle.save_ticket", side_effect=fake_save), \
         patch("ticket_system.commands.lifecycle.resolve_ticket_path", return_value="/tmp/fake.md"), \
         patch("ticket_system.commands.lifecycle.append_worklog_progress"), \
         patch("ticket_system.commands.lifecycle.list_tickets", return_value=[]), \
         patch("ticket_system.commands.lifecycle._analyze_next_steps", return_value={}), \
         patch("ticket_system.commands.lifecycle._print_next_steps"), \
         patch("ticket_system.commands.lifecycle._auto_handoff_if_needed"), \
         patch("ticket_system.commands.lifecycle._auto_commit_completion_files", return_value=False), \
         patch("ticket_system.commands.lifecycle._handle_ana_spawned_confirmation", return_value=None):
        assert TicketLifecycle("0.18.0").complete("0.18.0-W17-999") == 0
    return saved["t"]


# ---- 214.1.2 tdd_phase ----

def test_complete_advances_tdd_phase_to_last_stage():
    assert _complete(_ticket(tdd_phase_source="auto"))["tdd_phase"] == "phase4"


def test_complete_advances_when_source_missing():
    assert _complete(_ticket())["tdd_phase"] == "phase4"


def test_complete_keeps_manual_tdd_phase():
    saved = _complete(_ticket(tdd_phase_source="manual", tdd_phase="phase2"))
    assert saved["tdd_phase"] == "phase2"


def test_complete_keeps_tdd_phase_when_stage_empty():
    assert _complete(_ticket(tdd_stage=[]))["tdd_phase"] == "phase1"


# ---- 214.1.3 who.history / Executing Agent ----

def test_claim_identity_appends_history():
    from ticket_system.commands.lifecycle import _apply_claim_identity

    t = {"who": {"current": PM_AGENT_NAME, "history": {}}}
    _apply_claim_identity(t, "thyme-python-developer")
    assert list(t["who"]["history"].values()) == [PM_AGENT_NAME]


def test_claim_identity_same_current_no_history():
    from ticket_system.commands.lifecycle import _apply_claim_identity

    t = {"who": {"current": "thyme-python-developer", "history": {}}}
    _apply_claim_identity(t, "thyme-python-developer")
    assert t["who"]["history"] == {}


def test_claim_identity_placeholder_current_no_history():
    from ticket_system.commands.lifecycle import _apply_claim_identity

    t = {"who": {"current": "pending", "history": {}}}
    _apply_claim_identity(t, "thyme-python-developer")
    assert t["who"]["history"] == {}


def test_set_who_appends_history():
    from ticket_system.commands import fields

    ticket = {"id": "x", "who": {"current": "agent-a", "history": {}}}
    args = SimpleNamespace(ticket_id="x", value="agent-b", current=None)
    with patch.object(fields, "load_and_validate_ticket", return_value=(ticket, None)), \
         patch.object(fields, "get_ticket_path", return_value="/tmp/x.md"), \
         patch.object(fields, "file_lock"), \
         patch.object(fields, "resolve_ticket_path", return_value="/tmp/x.md"), \
         patch.object(fields.ticket_loader, "save_ticket"), \
         patch.object(fields.git_utils, "commit_ticket_md_reporting", return_value=False):
        assert fields.execute_set_who(args, "0.18.0") == 0
    assert ticket["who"]["current"] == "agent-b"
    assert list(ticket["who"]["history"].values()) == ["agent-a"]


def test_set_who_subfield_appends_history_and_unchanged_does_not():
    from ticket_system.commands import fields

    for new, expected in (("agent-b", ["agent-a"]), ("agent-a", [])):
        ticket = {"id": "x", "who": {"current": "agent-a", "history": {}}}
        args = SimpleNamespace(ticket_id="x", value=None, current=new)
        with patch.object(fields, "load_and_validate_ticket", return_value=(ticket, None)), \
             patch.object(fields, "get_ticket_path", return_value="/tmp/x.md"), \
             patch.object(fields, "file_lock"), \
             patch.object(fields, "resolve_ticket_path", return_value="/tmp/x.md"), \
             patch.object(fields.ticket_loader, "save_ticket"), \
             patch.object(fields.git_utils, "commit_ticket_md_reporting", return_value=False):
            fields.execute_set_who(args, "0.18.0")
        assert list(ticket["who"]["history"].values()) == expected


def test_reassign_from_pm_appends_history():
    from ticket_system.commands import lifecycle

    ticket = {"id": "x", "who": {"current": PM_AGENT_NAME, "history": {}}}
    with patch.object(lifecycle, "load_and_validate_ticket", return_value=(ticket, None)), \
         patch.object(lifecycle, "get_ticket_path", return_value="/tmp/x.md"), \
         patch.object(lifecycle, "file_lock"), \
         patch.object(lifecycle, "resolve_ticket_path", return_value="/tmp/x.md"), \
         patch.object(lifecycle, "save_ticket"):
        assert lifecycle.reassign_who_from_pm_if_takeover("0.18.0", "x", "thyme-python-developer")
    assert list(ticket["who"]["history"].values()) == [PM_AGENT_NAME]


def test_complete_executing_agent_survives_pm_takeover():
    who = {"current": PM_AGENT_NAME, "history": {"2026-10-14T10:00:00": "thyme-python-developer"}}
    saved = _complete(_ticket(who=who, _body=BODY.format(solution="x").replace(
        "thyme-python-developer", "basil-hook-architect")))
    assert "**Executing Agent**: thyme-python-developer" in saved["_body"]


def test_complete_executing_agent_unchanged_without_history():
    saved = _complete(_ticket(who={"current": PM_AGENT_NAME, "history": {}}))
    assert "**Executing Agent**: thyme-python-developer" in saved["_body"]


def test_track_validate_hint_no_longer_claims_history_auto_set():
    from ticket_system.commands import track_validate

    text = open(track_validate.__file__, encoding="utf-8").read()
    assert "自動設定 current/history" not in text


# ---- 214.1.4 Review Status ----

def test_review_status_reviewed_when_phase4_evidence():
    saved = _complete(_ticket(_body=BODY.format(solution="Phase 4 結論：無需重構")))
    assert "**Review Status**: reviewed" in saved["_body"]


def test_review_status_stays_pending_without_evidence():
    saved = _complete(_ticket())
    assert "**Review Status**: pending" in saved["_body"]


def test_review_status_na_for_ana_and_doc():
    for typ in ("ANA", "DOC"):
        saved = _complete(_ticket(type=typ))
        assert "**Review Status**: n/a" in saved["_body"], typ


def test_review_status_filled_value_not_overwritten():
    body = BODY.format(solution="Phase 4 結論").replace("Review Status**: pending", "Review Status**: rejected")
    assert "Review Status**: rejected" in _complete(_ticket(_body=body))["_body"]
