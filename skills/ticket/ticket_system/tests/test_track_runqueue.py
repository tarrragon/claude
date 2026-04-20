"""Tests for ticket_system/commands/track_runqueue.py (W17-020).

聚焦 _render_list 在 context=resume 過濾為空時的訊息分支。
"""

from __future__ import annotations

from typing import Dict, List

import pytest

from ticket_system.commands import track_runqueue


def _mk(tid: str, status: str = "pending", blocked=None, priority: str = "P2",
        wave: int = 17) -> Dict:
    return {
        "id": tid,
        "status": status,
        "blockedBy": blocked or [],
        "priority": priority,
        "wave": wave,
        "title": f"title-{tid}",
    }


# ---------------------------------------------------------------------------
# _render_list context 分支
# ---------------------------------------------------------------------------

def test_render_list_empty_default_context_shows_blocked_message():
    out = track_runqueue._render_list([], top=None, wave=None, context=None)
    assert "blockedBy 全非空或 status 非 pending" in out
    assert "無 resume 候選" not in out


def test_render_list_empty_resume_context_shows_handoff_message():
    out = track_runqueue._render_list(
        [], top=None, wave=None, context="resume"
    )
    assert "無 resume 候選" in out
    assert "handoff pending" in out
    assert "blockedBy 全非空" not in out


def test_render_list_empty_resume_with_filtered_tickets_shows_resume_message():
    """有 ticket 但全被 resume 過濾掉（實務上 _apply_context_resume 已回傳 []）。"""
    out = track_runqueue._render_list(
        [], top=None, wave=None, context="resume"
    )
    assert "無 resume 候選" in out


def test_render_list_non_empty_ignores_context():
    tickets = [_mk("0.18.0-W17-001", priority="P1")]
    out = track_runqueue._render_list(
        tickets, top=None, wave=None, context="resume"
    )
    assert "0.18.0-W17-001" in out
    assert "無 resume 候選" not in out


# ---------------------------------------------------------------------------
# execute_runqueue 端對端：context=resume 無 handoff pending
# ---------------------------------------------------------------------------

def test_execute_runqueue_resume_no_handoff_pending(monkeypatch, capsys):
    import argparse

    tickets = [_mk("0.18.0-W17-001"), _mk("0.18.0-W17-002")]
    monkeypatch.setattr(
        track_runqueue, "list_tickets", lambda version: tickets
    )
    monkeypatch.setattr(
        track_runqueue, "_get_pending_handoff_ticket_ids", lambda: set()
    )

    ns = argparse.Namespace(
        format="list", top=None, context="resume", wave=None,
    )
    rc = track_runqueue.execute_runqueue(ns, "0.18.0")
    assert rc == 0
    out = capsys.readouterr().out
    assert "無 resume 候選" in out
    assert "handoff pending" in out


def test_execute_runqueue_no_context_empty_uses_default_message(
    monkeypatch, capsys
):
    import argparse

    # 所有 ticket 都 blocked
    tickets = [_mk("0.18.0-W17-001", blocked=["x"])]
    monkeypatch.setattr(
        track_runqueue, "list_tickets", lambda version: tickets
    )

    ns = argparse.Namespace(
        format="list", top=None, context=None, wave=None,
    )
    rc = track_runqueue.execute_runqueue(ns, "0.18.0")
    assert rc == 0
    out = capsys.readouterr().out
    assert "blockedBy 全非空或 status 非 pending" in out
    assert "無 resume 候選" not in out
