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
        track_runqueue, "_get_pending_handoff_info", lambda: {}
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


# ---------------------------------------------------------------------------
# W17-146: _apply_context_resume 解析 direction 取出 target
# ---------------------------------------------------------------------------

def _apply_with_handoff(monkeypatch, tickets, handoff_info):
    monkeypatch.setattr(
        track_runqueue, "_get_pending_handoff_info", lambda: handoff_info
    )
    return track_runqueue._apply_context_resume(tickets, "resume")


def test_apply_context_resume_to_sibling_with_target(monkeypatch):
    """T1: to-sibling:T → 候選含 T（target），不含 source。"""
    tickets = [
        _mk("0.18.0-W17-110.1", status="completed"),
        _mk("0.18.0-W17-110.3", status="pending"),
    ]
    handoff = {
        "0.18.0-W17-110.1": {
            "ticket_id": "0.18.0-W17-110.1",
            "direction": "to-sibling:0.18.0-W17-110.3",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    ids = {t["id"] for t in out}
    assert "0.18.0-W17-110.3" in ids


def test_apply_context_resume_to_parent_with_target(monkeypatch):
    """T2: to-parent:T → 候選含 T。"""
    tickets = [
        _mk("0.18.0-W17-200", status="pending"),
    ]
    handoff = {
        "0.18.0-W17-200.1": {
            "ticket_id": "0.18.0-W17-200.1",
            "direction": "to-parent:0.18.0-W17-200",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-200"}


def test_apply_context_resume_to_child_with_target(monkeypatch):
    """T3: to-child:T → 候選含 T。"""
    tickets = [
        _mk("0.18.0-W17-300.1", status="pending"),
    ]
    handoff = {
        "0.18.0-W17-300": {
            "ticket_id": "0.18.0-W17-300",
            "direction": "to-child:0.18.0-W17-300.1",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-300.1"}


def test_apply_context_resume_context_refresh_uses_source(monkeypatch):
    """T4: context-refresh → 候選為 source ticket_id。"""
    tickets = [
        _mk("0.18.0-W17-400", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-400": {
            "ticket_id": "0.18.0-W17-400",
            "direction": "context-refresh",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-400"}


def test_apply_context_resume_next_wave_uses_source(monkeypatch):
    """T5: next-wave → 候選為 source ticket_id。"""
    tickets = [
        _mk("0.18.0-W17-500", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-500": {
            "ticket_id": "0.18.0-W17-500",
            "direction": "next-wave",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-500"}


def test_apply_context_resume_empty_direction_falls_back_to_source(monkeypatch):
    """T6 邊界: direction 空字串 → fallback 到 source ticket_id，不 crash。"""
    tickets = [
        _mk("0.18.0-W17-600", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-600": {
            "ticket_id": "0.18.0-W17-600",
            "direction": "",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-600"}


def test_apply_context_resume_unknown_direction_falls_back_to_source(monkeypatch):
    """T7 邊界: direction 格式錯誤 → fallback 到 source ticket_id。"""
    tickets = [
        _mk("0.18.0-W17-700", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-700": {
            "ticket_id": "0.18.0-W17-700",
            "direction": "foobar",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-700"}


def test_apply_context_resume_task_chain_no_target_falls_back(monkeypatch):
    """to-sibling 無 :target → fallback source ticket_id。"""
    tickets = [
        _mk("0.18.0-W17-800", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-800": {
            "ticket_id": "0.18.0-W17-800",
            "direction": "to-sibling",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-800"}


# ---------------------------------------------------------------------------
# W6-022: _apply_context_resume 優先讀 target_ticket_id（W17-164 絕對指向）
# ---------------------------------------------------------------------------

def test_apply_context_resume_context_refresh_with_target_ticket_id(monkeypatch):
    """W6-022 regression: direction=context-refresh + target_ticket_id 存在
    → 候選為 target，而非 source（避免 completed source 被 _is_listable 濾掉）。
    """
    tickets = [
        _mk("0.18.0-W6-012", status="completed"),
        _mk("0.18.0-W13-001", status="pending"),
    ]
    handoff = {
        "0.18.0-W6-012": {
            "ticket_id": "0.18.0-W6-012",
            "direction": "context-refresh",
            "target_ticket_id": "0.18.0-W13-001",
            "from_status": "completed",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W13-001"}


def test_apply_context_resume_target_ticket_id_overrides_direction(monkeypatch):
    """W6-022: target_ticket_id 優先於 direction 解析（即使 direction 為任務鏈格式）。"""
    tickets = [
        _mk("0.18.0-W17-901", status="pending"),
        _mk("0.18.0-W17-902", status="pending"),
    ]
    handoff = {
        "0.18.0-W17-900": {
            "ticket_id": "0.18.0-W17-900",
            "direction": "to-sibling:0.18.0-W17-901",
            "target_ticket_id": "0.18.0-W17-902",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-902"}


def test_apply_context_resume_empty_target_ticket_id_falls_back(monkeypatch):
    """W6-022 邊界: target_ticket_id 為空字串 → fallback 既有 direction 邏輯。"""
    tickets = [
        _mk("0.18.0-W17-910", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-910": {
            "ticket_id": "0.18.0-W17-910",
            "direction": "context-refresh",
            "target_ticket_id": "",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-910"}


def test_apply_context_resume_non_string_target_ticket_id_falls_back(monkeypatch):
    """W6-022 邊界: target_ticket_id 非字串 → fallback 既有 direction 邏輯。"""
    tickets = [
        _mk("0.18.0-W17-920", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-920": {
            "ticket_id": "0.18.0-W17-920",
            "direction": "context-refresh",
            "target_ticket_id": None,
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-920"}


# ---------------------------------------------------------------------------
# W6-022: cross-command 一致性（runqueue --context=resume vs resume --list）
# ---------------------------------------------------------------------------

def test_cross_command_consistency_context_refresh_target_ticket_id(monkeypatch):
    """W6-022: runqueue --context=resume 應呈現 resume --list 同樣的 target ticket。

    建構 fixture：source=completed + target=pending + direction=context-refresh
    + target_ticket_id 存在。
    - resume --list 直接列舉 handoff JSON，回傳 target_ticket_id 集合。
    - runqueue --context=resume 過 _apply_context_resume → 應回傳同樣的 target。
    兩者結果集必須相等（修復前不相等：runqueue 落 source 被 _is_listable 濾掉）。
    """
    tickets = [
        _mk("0.18.0-W6-012", status="completed"),
        _mk("0.18.0-W13-001", status="pending"),
    ]
    handoff = {
        "0.18.0-W6-012": {
            "ticket_id": "0.18.0-W6-012",
            "direction": "context-refresh",
            "target_ticket_id": "0.18.0-W13-001",
        }
    }

    # runqueue --context=resume 結果集
    runqueue_out = _apply_with_handoff(monkeypatch, tickets, handoff)
    runqueue_ids = {t["id"] for t in runqueue_out}

    # resume --list 等價結果集：handoff JSON 之 target_ticket_id（W17-164 語意）
    resume_list_ids = {
        info["target_ticket_id"]
        for info in handoff.values()
        if info.get("target_ticket_id")
    }

    assert runqueue_ids == resume_list_ids
    assert "0.18.0-W13-001" in runqueue_ids
