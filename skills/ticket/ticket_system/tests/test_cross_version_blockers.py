"""跨版本 blocker 的解除判定與 complete 反向解鎖（0.3.2-W1-006.2）。

替身以 (version, id) 為鍵：blocker 只存在於其自身版本，同版本內全集查無。
"""

from unittest.mock import patch

from ticket_system.commands import lifecycle, track_runqueue
from ticket_system.lib import blocker_resolution
from ticket_system.lib.blocker_resolution import is_fully_unblocked

BLOCKER_ID = "0.3.1-W1-010"
BLOCKED_ID = "0.3.2-W1-020"
GHOST_ID = "0.3.1-W1-999"


def _t(tid, status="pending", blocked_by=None):
    return {"id": tid, "title": f"t-{tid}", "status": status, "blockedBy": blocked_by or []}


def _fake_load(store):
    def load(version, tid):
        return store.get((version, tid))

    return load


def _blocked(blocker_id):
    return _t(BLOCKED_ID, "blocked", [blocker_id])


def test_cross_version_completed_blocker_is_unblocked():
    store = {("0.3.1", BLOCKER_ID): _t(BLOCKER_ID, "completed")}
    target = _blocked(BLOCKER_ID)
    with patch.object(blocker_resolution, "load_ticket", _fake_load(store)):
        assert is_fully_unblocked(
            target, {BLOCKED_ID: target}, include_closed_as_resolved=True
        )
        assert track_runqueue._unresolved_blockers(target, {BLOCKED_ID: target}) == []


def test_cross_version_pending_blocker_stays_unresolved():
    store = {("0.3.1", BLOCKER_ID): _t(BLOCKER_ID, "pending")}
    target = _blocked(BLOCKER_ID)
    with patch.object(blocker_resolution, "load_ticket", _fake_load(store)):
        assert not is_fully_unblocked(
            target, {BLOCKED_ID: target}, include_closed_as_resolved=True
        )
        assert track_runqueue._unresolved_blockers(target, {BLOCKED_ID: target}) == [
            BLOCKER_ID
        ]


def test_truly_missing_blocker_stays_blocked():
    """正向對照：同一 fixture（別的票存在），blocker 在其版本也不存在。"""
    store = {("0.3.1", BLOCKER_ID): _t(BLOCKER_ID, "completed")}
    target = _blocked(GHOST_ID)
    with patch.object(blocker_resolution, "load_ticket", _fake_load(store)):
        assert not is_fully_unblocked(
            target, {BLOCKED_ID: target}, include_closed_as_resolved=True
        )
        assert track_runqueue._unresolved_blockers(target, {BLOCKED_ID: target}) == [
            GHOST_ID
        ]


def test_complete_cross_version_blocker_reverse_unblocks_other_version(capsys):
    completed = _t(BLOCKER_ID, "completed")
    blocked = _blocked(BLOCKER_ID)
    by_version = {"0.3.1": [completed], "0.3.2": [blocked]}
    saved = []
    with patch.object(
        lifecycle, "list_tickets", side_effect=lambda v: list(by_version.get(v, []))
    ), patch.object(
        lifecycle, "list_open_versions", return_value=["0.3.1", "0.3.2"]
    ), patch.object(
        lifecycle, "save_ticket", side_effect=lambda t, p: saved.append(dict(t))
    ), patch.object(lifecycle, "resolve_ticket_path", return_value="p"):
        result = lifecycle._reverse_unblock_blockedby(
            BLOCKER_ID, "0.3.1", {BLOCKER_ID: completed}
        )
    assert [r["id"] for r in result] == [BLOCKED_ID]
    assert saved and saved[0]["status"] == "pending"
    assert BLOCKED_ID in capsys.readouterr().out


def test_todolist_parse_failure_warns_on_stderr(tmp_path, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "todolist.yaml").write_text("versions: [unclosed", encoding="utf-8")
    with patch.object(blocker_resolution, "get_project_root", return_value=tmp_path):
        assert blocker_resolution.list_open_versions() == []
    assert "[blocker_resolution] WARNING" in capsys.readouterr().err


def test_blocker_load_failure_warns_on_stderr(capsys):
    def boom(version, tid):
        raise OSError("disk")

    target = _blocked(BLOCKER_ID)
    with patch.object(blocker_resolution, "load_ticket", boom):
        assert track_runqueue._unresolved_blockers(target, {BLOCKED_ID: target}) == [
            BLOCKER_ID
        ]
    assert "disk" in capsys.readouterr().err


def test_reverse_unblock_ignores_other_version_blocked_by_unrelated_ticket():
    """對照：被擋票的 blockedBy 不含剛完成的票時，不被解鎖。"""
    completed = _t(BLOCKER_ID, "completed")
    other = _blocked("0.3.1-W1-011")
    by_version = {"0.3.2": [other]}
    with patch.object(
        lifecycle, "list_tickets", side_effect=lambda v: list(by_version.get(v, []))
    ), patch.object(
        lifecycle, "list_open_versions", return_value=["0.3.1", "0.3.2"]
    ), patch.object(lifecycle, "save_ticket") as save:
        result = lifecycle._reverse_unblock_blockedby(
            BLOCKER_ID, "0.3.1", {BLOCKER_ID: completed}
        )
    assert result == []
    save.assert_not_called()
