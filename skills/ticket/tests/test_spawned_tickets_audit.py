"""0.18.0-W15-003: acceptance_auditor.validate_spawned_tickets_completed 測試

4 情境：
- 無 spawned_tickets → pass（skipped）
- 部分 spawned completed → fail
- 全部 spawned completed → pass
- 循環引用（A spawns B, B spawns A）→ detect + 不無限遞迴
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from ticket_system.lib.acceptance_auditor import (
    _check_spawned_recursive,
    validate_spawned_tickets_completed,
)


def _make_tickets(*pairs):
    """建立 ticket_id → dict 的 map。pair 形式 (id, status, spawned_list)"""
    store = {}
    for tid, status, spawned in pairs:
        store[tid] = {
            "id": tid,
            "status": status,
            "type": "IMP",
            "spawned_tickets": list(spawned or []),
        }
    return store


def _patch_loader(store):
    def fake_load(version, ticket_id):
        return store.get(ticket_id)

    return patch(
        "ticket_system.lib.acceptance_auditor.load_ticket",
        side_effect=fake_load,
    )


# 情境 1：無 spawned_tickets → skipped
def test_validate_no_spawned_tickets_skipped():
    ticket = {"id": "A", "type": "ANA", "spawned_tickets": []}
    passed, issues, skipped = validate_spawned_tickets_completed(ticket, "0.18.0")
    assert passed is True
    assert skipped is True
    assert issues == []


def test_validate_non_ana_type_skipped():
    ticket = {"id": "A", "type": "IMP", "spawned_tickets": ["B"]}
    passed, issues, skipped = validate_spawned_tickets_completed(ticket, "0.18.0")
    assert passed is True
    assert skipped is True


# 情境 2：部分 spawned completed → fail
def test_validate_partial_spawned_completed_fails():
    store = _make_tickets(
        ("B", "completed", []),
        ("C", "in_progress", []),
        ("D", "pending", []),
    )
    ticket = {"id": "A", "type": "ANA", "spawned_tickets": ["B", "C", "D"]}

    with _patch_loader(store):
        passed, issues, skipped = validate_spawned_tickets_completed(ticket, "0.18.0")

    assert passed is False
    assert skipped is False
    assert any("1/3 completed" in issue for issue in issues)
    joined = "\n".join(issues)
    assert "C" in joined
    assert "D" in joined


# 情境 3：全部 spawned completed → pass
def test_validate_all_spawned_completed_passes():
    store = _make_tickets(
        ("B", "completed", []),
        ("C", "completed", []),
    )
    ticket = {"id": "A", "type": "ANA", "spawned_tickets": ["B", "C"]}

    with _patch_loader(store):
        passed, issues, skipped = validate_spawned_tickets_completed(ticket, "0.18.0")

    assert passed is True
    assert skipped is False
    assert issues == []


# 情境 4：循環引用
def test_validate_circular_reference_detected():
    """A spawns B, B spawns A → visited 防護應讓遞迴終止"""
    store = _make_tickets(
        ("B", "in_progress", ["A"]),
    )
    ticket = {"id": "A", "type": "ANA", "spawned_tickets": ["B"]}

    with _patch_loader(store):
        passed, issues, skipped = validate_spawned_tickets_completed(ticket, "0.18.0")

    assert passed is False
    assert skipped is False
    assert any("B" in issue for issue in issues)


def test_check_spawned_recursive_visited_prevents_double_count():
    store = _make_tickets(
        ("B", "pending", ["C"]),
        ("C", "pending", []),
    )
    with _patch_loader(store):
        all_completed, incomplete = _check_spawned_recursive(["B", "C"], "0.18.0")

    assert all_completed is False
    b_count = sum(1 for item in incomplete if item.startswith("B:"))
    c_count = sum(1 for item in incomplete if item.startswith("C:"))
    assert b_count == 1
    assert c_count == 1


# 邊界：not_found
def test_validate_spawned_not_found_fails():
    store = {}
    ticket = {"id": "A", "type": "ANA", "spawned_tickets": ["B"]}

    with _patch_loader(store):
        passed, issues, skipped = validate_spawned_tickets_completed(ticket, "0.18.0")

    assert passed is False
    joined = "\n".join(issues)
    assert "not_found" in joined
