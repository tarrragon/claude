"""Tests for _type_rank sorting in track_runqueue.py (W5-005.17).

驗證同 priority 下 type 權重排序（ANA < DOC < IMP）與 list 輸出 type 標籤。
"""

from __future__ import annotations

from typing import Dict, Optional

import pytest

from ticket_system.commands import track_runqueue


def _mk(tid: str, priority: str = "P2", ticket_type: Optional[str] = "IMP") -> Dict:
    return {
        "id": tid,
        "status": "pending",
        "blockedBy": [],
        "priority": priority,
        "type": ticket_type,
        "title": f"title-{tid}",
    }


# ---------------------------------------------------------------------------
# _type_rank
# ---------------------------------------------------------------------------

def test_type_rank_ana_lowest():
    assert track_runqueue._type_rank(_mk("t1", ticket_type="ANA")) == 0


def test_type_rank_doc_middle():
    assert track_runqueue._type_rank(_mk("t1", ticket_type="DOC")) == 1


def test_type_rank_imp_highest():
    assert track_runqueue._type_rank(_mk("t1", ticket_type="IMP")) == 2


def test_type_rank_unknown_fallback_doc_level():
    assert track_runqueue._type_rank(_mk("t1", ticket_type="UNKNOWN")) == 1
    assert track_runqueue._type_rank(_mk("t1", ticket_type=None)) == 1


# ---------------------------------------------------------------------------
# _render_list 排序：同 priority 下 ANA 排在 IMP 前
# ---------------------------------------------------------------------------

def test_render_list_same_priority_ana_before_imp():
    tickets = [
        _mk("imp-1", priority="P2", ticket_type="IMP"),
        _mk("ana-1", priority="P2", ticket_type="ANA"),
    ]
    out = track_runqueue._render_list(tickets, top=None, wave=None)
    assert out.index("ana-1") < out.index("imp-1")


def test_render_list_different_priority_priority_still_first():
    tickets = [
        _mk("imp-p0", priority="P0", ticket_type="IMP"),
        _mk("ana-p2", priority="P2", ticket_type="ANA"),
    ]
    out = track_runqueue._render_list(tickets, top=None, wave=None)
    assert out.index("imp-p0") < out.index("ana-p2")


def test_render_list_unknown_type_fallback_doc_level_order():
    tickets = [
        _mk("imp-1", priority="P2", ticket_type="IMP"),
        _mk("unknown-1", priority="P2", ticket_type="UNKNOWN"),
        _mk("ana-1", priority="P2", ticket_type="ANA"),
    ]
    out = track_runqueue._render_list(tickets, top=None, wave=None)
    assert out.index("ana-1") < out.index("unknown-1") < out.index("imp-1")


def test_render_list_includes_type_tag():
    tickets = [_mk("ana-1", priority="P1", ticket_type="ANA")]
    out = track_runqueue._render_list(tickets, top=None, wave=None)
    assert "[P1|ANA]" in out
