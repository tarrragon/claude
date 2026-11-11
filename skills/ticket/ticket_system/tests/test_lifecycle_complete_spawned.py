"""ANA complete 的 spawned 確認：依落地版本分流（後續版本只印資訊）。

E1 對照：同一批 fixture 僅改 spawned 的版本，結果由 None 變 2。
"""
from __future__ import annotations

from unittest.mock import patch

from ticket_system.commands.lifecycle import _handle_ana_spawned_confirmation

ANA_VERSION = "3.2.0"


def _ana(spawned_ids, version=ANA_VERSION):
    return {
        "id": f"{version}-W1-001",
        "type": "ANA",
        "version": version,
        "spawned_tickets": list(spawned_ids),
    }


def _run(ticket, store, yes_spawned=False):
    """store: {ticket_id: status}；不在 store 內者視為 not_found。"""

    def fake_load(_version, tid):
        return {"id": tid, "status": store[tid]} if tid in store else None

    with patch("ticket_system.commands.lifecycle.load_ticket", side_effect=fake_load), \
         patch("ticket_system.commands.lifecycle.sys.stdin.isatty", return_value=False):
        return _handle_ana_spawned_confirmation(ticket, ticket["version"], yes_spawned)


def test_all_later_version_passes_with_info(capsys):
    ids = ["3.3.0-W1-001", "3.10.0-W2-004"]
    store = {i: "pending" for i in ids}
    assert _run(_ana(ids), store) is None
    err = capsys.readouterr().err
    for i in ids:
        assert i in err
    assert "版本 3.3.0" in err and "版本 3.10.0" in err


def test_same_version_pending_requires_confirmation():
    ids = ["3.2.0-W1-050"]
    assert _run(_ana(ids), {ids[0]: "pending"}) == 2


def test_contrast_only_spawned_version_differs():
    later, same = "3.3.0-W1-001", "3.2.0-W1-001"
    assert _run(_ana([later]), {later: "pending"}) is None
    assert _run(_ana([same]), {same: "pending"}) == 2


def test_mixed_requires_confirmation_and_lists_only_same_version(capsys):
    later, same = "3.3.0-W1-001", "3.2.0-W1-050"
    store = {later: "pending", same: "in_progress"}
    assert _run(_ana([later, same]), store) == 2
    err = capsys.readouterr().err
    assert f"  - {same}: in_progress\n" in err
    assert f"  - {later}: pending\n" not in err
    assert f"{later}: pending（版本 3.3.0）" in err


def test_not_found_still_requires_confirmation():
    assert _run(_ana(["3.3.0-W1-099"]), {}) == 2


def test_same_version_with_yes_spawned_bypasses():
    ids = ["3.2.0-W1-050"]
    assert _run(_ana(ids), {ids[0]: "pending"}, yes_spawned=True) is None


def test_multi_digit_version_compared_numerically():
    # 字串比較下 "3.10.0" < "3.9.0"；整數元組下 3.10.0 > 3.9.0
    later = "3.10.0-W1-001"
    assert _run(_ana([later], version="3.9.0"), {later: "pending"}) is None
    earlier = "3.9.0-W1-001"
    assert _run(_ana([earlier], version="3.10.0"), {earlier: "pending"}) == 2
