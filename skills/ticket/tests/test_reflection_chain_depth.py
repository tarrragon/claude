"""
Tests for reflection chain depth detection in `ticket track deps` (W15-021).

覆蓋 W15-010 Layer 2 需求：
- ANA 沿 source_ticket 祖鏈深度計算
- 連續 ANA 才計入（非 ANA 中斷即停）
- 深度 ≥ 3 觸發 WARNING
- 循環引用防護
"""
from unittest.mock import patch

from ticket_system.commands.track_query import (
    REFLECTION_CHAIN_WARN_THRESHOLD,
    _compute_reflection_chain_depth,
)


def _make_ticket(tid: str, ttype: str = "ANA", source: str = None) -> dict:
    return {"id": tid, "type": ttype, "source_ticket": source}


def _patch_loader(store):
    def fake_load(_version, tid):
        return store.get(tid)
    return patch(
        "ticket_system.commands.track_query.load_ticket",
        side_effect=fake_load,
    )


def test_depth_single_ana_no_source():
    ticket = _make_ticket("A", "ANA", None)
    with _patch_loader({"A": ticket}):
        depth, chain = _compute_reflection_chain_depth(ticket, "0.18.0")
    assert depth == 1
    assert chain == ["A"]


def test_depth_non_ana_root_returns_zero():
    ticket = _make_ticket("A", "IMP", None)
    with _patch_loader({"A": ticket}):
        depth, chain = _compute_reflection_chain_depth(ticket, "0.18.0")
    assert depth == 0
    assert chain == []


def test_depth_three_consecutive_ana_triggers_warn():
    store = {
        "A": _make_ticket("A", "ANA", None),
        "B": _make_ticket("B", "ANA", "A"),
        "C": _make_ticket("C", "ANA", "B"),
    }
    with _patch_loader(store):
        depth, chain = _compute_reflection_chain_depth(store["C"], "0.18.0")
    assert depth == 3
    assert chain == ["A", "B", "C"]
    assert depth >= REFLECTION_CHAIN_WARN_THRESHOLD


def test_depth_stops_at_non_ana_ancestor():
    # A(IMP) -> B(ANA) -> C(ANA)；從 C 回溯 A(IMP) 應停在 B（depth=2）
    store = {
        "A": _make_ticket("A", "IMP", None),
        "B": _make_ticket("B", "ANA", "A"),
        "C": _make_ticket("C", "ANA", "B"),
    }
    with _patch_loader(store):
        depth, chain = _compute_reflection_chain_depth(store["C"], "0.18.0")
    assert depth == 2
    assert chain == ["B", "C"]


def test_depth_handles_cycle():
    # A -> B -> A（病態資料循環）
    store = {
        "A": _make_ticket("A", "ANA", "B"),
        "B": _make_ticket("B", "ANA", "A"),
    }
    with _patch_loader(store):
        depth, chain = _compute_reflection_chain_depth(store["A"], "0.18.0")
    # 應在遇到已造訪節點時停止，不無限迴圈
    assert depth == 2
    assert set(chain) == {"A", "B"}


def test_depth_missing_source_ticket_stops():
    # B 的 source_ticket 指向不存在的 Ticket
    store = {
        "B": _make_ticket("B", "ANA", "GHOST"),
    }
    with _patch_loader(store):
        depth, chain = _compute_reflection_chain_depth(store["B"], "0.18.0")
    assert depth == 1
    assert chain == ["B"]


def test_execute_deps_prints_warning_when_threshold_reached(capsys):
    """execute_deps 在反思鏈 >=3 時輸出 [WARNING]"""
    from ticket_system.commands.track_query import execute_deps
    import argparse

    store = {
        "A": {"id": "A", "type": "ANA", "source_ticket": None,
              "title": "root", "status": "completed", "spawned_tickets": []},
        "B": {"id": "B", "type": "ANA", "source_ticket": "A",
              "title": "mid", "status": "completed", "spawned_tickets": []},
        "C": {"id": "C", "type": "ANA", "source_ticket": "B",
              "title": "leaf", "status": "in_progress", "spawned_tickets": []},
    }

    def fake_load(_v, tid):
        return store.get(tid)

    args = argparse.Namespace(ticket_id="C", version="0.18.0")
    with patch("ticket_system.commands.track_query.load_ticket", side_effect=fake_load), \
         patch("ticket_system.commands.track_query.load_and_validate_ticket",
               return_value=(store["C"], None)), \
         patch("ticket_system.commands.track_query._check_yaml_error", return_value=False):
        rc = execute_deps(args, "0.18.0")

    assert rc == 0
    out = capsys.readouterr().out
    assert "Reflection Chain Depth: 3" in out
    assert "[WARNING] 反思鏈深度" in out
    assert "A -> B -> C" in out


def test_execute_deps_no_warning_when_below_threshold(capsys):
    """非 ANA 或深度 <3 不輸出 WARNING"""
    from ticket_system.commands.track_query import execute_deps
    import argparse

    ticket = {"id": "X", "type": "IMP", "source_ticket": None,
              "title": "imp", "status": "pending", "spawned_tickets": []}
    args = argparse.Namespace(ticket_id="X", version="0.18.0")
    with patch("ticket_system.commands.track_query.load_ticket", return_value=None), \
         patch("ticket_system.commands.track_query.load_and_validate_ticket",
               return_value=(ticket, None)), \
         patch("ticket_system.commands.track_query._check_yaml_error", return_value=False):
        rc = execute_deps(args, "0.18.0")

    assert rc == 0
    out = capsys.readouterr().out
    assert "Reflection Chain Depth: 0" in out
    assert "[WARNING]" not in out
