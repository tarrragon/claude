"""
派發條目明示釋放與恢復測試（3.3.0-W1-120.2）

- dispatch_tracker.release_dispatch：只釋放本 session 的無票、非隔離條目
- dispatch_tracker.restore_released：SendMessage 送往已釋放代理人時放回條目
- active-dispatch-tracker-hook 的 PostToolUse(SendMessage) 路徑串起兩者

背景：SubagentStop 只代表回合結束，代理人之後仍可能被 SendMessage 恢復寫檔，
唯一可靠的移除訊號是 PM 明示放棄恢復（見 3.3.0-W1-120 實驗）。
"""

import importlib.util
import io
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_HOOKS_DIR.parent))
sys.path.insert(0, str(_HOOKS_DIR))

from lib import dispatch_tracker as dt  # noqa: E402
from lib.dispatch_tracker import (  # noqa: E402
    RELEASE_AMBIGUOUS,
    RELEASE_HAS_TICKET,
    RELEASE_IN_TURN,
    RELEASE_ISOLATED,
    RELEASE_NO_SESSION,
    RELEASE_NOT_FOUND,
    RELEASE_OK,
    RELEASE_OTHER_SESSION,
    cleanup_expired,
    get_active_dispatches,
    get_state_file_path,
    mark_turn_ended_by_handle,
    record_dispatch,
    release_dispatch,
    restore_released,
)

_spec = importlib.util.spec_from_file_location(
    "active_dispatch_tracker_hook_release",
    _HOOKS_DIR / "active-dispatch-tracker-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

SID = "sess-me"
OTHER = "sess-other"


@pytest.fixture
def root():
    dt.reset_cache()
    with tempfile.TemporaryDirectory() as tmpdir:
        r = Path(tmpdir)
        (r / ".claude").mkdir()
        yield r
    dt.reset_cache()


def _record(
    root, *, handle="", agent_id=None, session_id=SID, ticket_id="", branch_name="",
    turn_ended=True,
):
    """寫入一筆條目；turn_ended=True 時把 turn_ended_at 設為現在（回合已結束）。"""
    record_dispatch(
        root,
        agent_description=f"desc-{handle or agent_id}",
        agent_id=agent_id,
        agent_handle=handle,
        session_id=session_id,
        ticket_id=ticket_id,
        branch_name=branch_name,
        work_checkout=str(root),
    )
    if turn_ended:
        state = json.loads(get_state_file_path(root).read_text(encoding="utf-8"))
        state["dispatches"][-1]["turn_ended_at"] = datetime.now(timezone.utc).isoformat()
        get_state_file_path(root).write_text(json.dumps(state), encoding="utf-8")
        dt.reset_cache()


def _state(root):
    return json.loads(get_state_file_path(root).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# release_dispatch
# ---------------------------------------------------------------------------


class TestReleaseDispatch:
    def test_releases_own_untracked_entry_by_handle(self, root):
        _record(root, handle="probe")
        status, entries = release_dispatch(root, "probe", SID)
        assert status == RELEASE_OK
        assert entries[0]["agent_handle"] == "probe"
        assert get_active_dispatches(root) == []
        released = _state(root)["released"]
        assert released[0]["agent_handle"] == "probe"
        assert "released_at" in released[0]

    def test_releases_by_agent_id(self, root):
        _record(root, agent_id="ac6c923bb6253aa3a")
        status, _ = release_dispatch(root, "ac6c923bb6253aa3a", SID)
        assert status == RELEASE_OK
        assert get_active_dispatches(root) == []

    def test_other_session_entry_is_refused_and_kept(self, root):
        _record(root, handle="probe", session_id=OTHER)
        status, entries = release_dispatch(root, "probe", SID)
        assert status == RELEASE_OTHER_SESSION
        assert entries[0]["session_id"] == OTHER
        assert len(get_active_dispatches(root)) == 1
        assert "released" not in _state(root)

    def test_ticket_bound_entry_is_refused(self, root):
        _record(root, handle="probe", ticket_id="3.3.0-W1-001")
        status, entries = release_dispatch(root, "probe", SID)
        assert status == RELEASE_HAS_TICKET
        assert entries[0]["ticket_id"] == "3.3.0-W1-001"
        assert len(get_active_dispatches(root)) == 1

    def test_isolated_entry_is_refused(self, root):
        """isolation=worktree 條目供 isolated-subagent-main-write-guard 判定身分，不可釋放。"""
        _record(root, handle="iso", branch_name="worktree")
        status, _ = release_dispatch(root, "iso", SID)
        assert status == RELEASE_ISOLATED
        assert get_active_dispatches(root)[0]["branch_name"] == "worktree"

    def test_entry_in_turn_is_refused(self, root):
        """回合進行中（turn_ended_at 為空）拒絕，條目保留。"""
        _record(root, handle="busy", turn_ended=False)
        status, entries = release_dispatch(root, "busy", SID)
        assert status == RELEASE_IN_TURN
        assert entries[0]["turn_ended_at"] is None
        assert len(get_active_dispatches(root)) == 1
        assert "released" not in _state(root)

    def test_entry_after_turn_end_is_released(self, root):
        """對照：同一條目回合結束後可釋放。"""
        _record(root, handle="busy", turn_ended=False)
        assert release_dispatch(root, "busy", SID)[0] == RELEASE_IN_TURN
        mark_turn_ended_by_handle(root, "abusy-73070ca5c1d3f849")
        assert release_dispatch(root, "busy", SID)[0] == RELEASE_OK

    def test_release_key_with_ref_suffix(self, root):
        _record(root, handle="probe")
        status, _ = release_dispatch(root, "probe [abc123]", SID)
        assert status == RELEASE_OK

    def test_multiple_own_matches_are_ambiguous(self, root):
        _record(root, handle="probe")
        _record(root, handle="probe")
        status, entries = release_dispatch(root, "probe", SID)
        assert status == RELEASE_AMBIGUOUS
        assert len(entries) == 2
        assert len(get_active_dispatches(root)) == 2

    def test_not_found(self, root):
        _record(root, handle="probe")
        status, entries = release_dispatch(root, "nobody", SID)
        assert status == RELEASE_NOT_FOUND
        assert entries == []
        assert len(get_active_dispatches(root)) == 1

    def test_empty_session_id_is_refused(self, root):
        _record(root, handle="probe", session_id="")
        status, _ = release_dispatch(root, "probe", "")
        assert status == RELEASE_NO_SESSION
        assert len(get_active_dispatches(root)) == 1

    def test_empty_key_matches_nothing(self, root):
        """空 key 不得比對到 agent_handle 為空的條目。"""
        _record(root, agent_id="abc")
        status, _ = release_dispatch(root, "", SID)
        assert status == RELEASE_NOT_FOUND
        assert len(get_active_dispatches(root)) == 1

    def test_only_target_entry_is_removed(self, root):
        _record(root, handle="probe")
        _record(root, handle="other")
        release_dispatch(root, "probe", SID)
        assert [d["agent_handle"] for d in get_active_dispatches(root)] == ["other"]

    def test_corrupt_state_file_is_not_overwritten(self, root):
        path = get_state_file_path(root)
        path.write_text("{broken", encoding="utf-8")
        status, _ = release_dispatch(root, "probe", SID)
        assert status == RELEASE_NOT_FOUND
        assert path.read_text(encoding="utf-8") == "{broken"


# ---------------------------------------------------------------------------
# restore_released
# ---------------------------------------------------------------------------


class TestRestoreReleased:
    def test_restore_puts_entry_back(self, root):
        _record(root, handle="probe")
        release_dispatch(root, "probe", SID)
        entry = restore_released(root, "probe", SID)
        assert entry is not None
        active = get_active_dispatches(root)
        assert len(active) == 1
        assert active[0]["agent_handle"] == "probe"
        assert active[0]["turn_ended_at"] is None
        assert "resumed_at" in active[0]
        assert "released_at" not in active[0]
        assert "released" not in _state(root)

    def test_restore_with_ref_suffix(self, root):
        """SendMessage 以 `name [ref]` 指定對象時仍放回（正向對照）。"""
        _record(root, handle="probe")
        release_dispatch(root, "probe", SID)
        assert restore_released(root, "probe [abc123]", SID) is not None
        assert [d["agent_handle"] for d in get_active_dispatches(root)] == ["probe"]

    def test_ref_suffix_does_not_widen_match(self, root):
        """剝除後綴後仍須完全相等：`probe2 [x]` 不放回 probe。"""
        _record(root, handle="probe")
        release_dispatch(root, "probe", SID)
        assert restore_released(root, "probe2 [abc123]", SID) is None
        assert get_active_dispatches(root) == []

    def test_restore_without_release_writes_nothing(self, root):
        """對照：沒有釋放紀錄時 SendMessage 不改動狀態檔（E1 對照）。"""
        _record(root, handle="probe")
        before = get_state_file_path(root).read_text(encoding="utf-8")
        assert restore_released(root, "probe", SID) is None
        assert get_state_file_path(root).read_text(encoding="utf-8") == before

    def test_other_session_cannot_restore(self, root):
        _record(root, handle="probe")
        release_dispatch(root, "probe", SID)
        assert restore_released(root, "probe", OTHER) is None
        assert get_active_dispatches(root) == []

    def test_restored_entry_survives_in_progress_ttl(self, root):
        """恢復後 dispatched_at 重設，原值 3 小時前的條目不會被 1 小時 TTL 立刻清掉。"""
        _record(root, handle="probe")
        state = _state(root)
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        state["dispatches"][0]["dispatched_at"] = old
        state["dispatches"][0]["turn_ended_at"] = old
        get_state_file_path(root).write_text(json.dumps(state), encoding="utf-8")
        dt.reset_cache()

        release_dispatch(root, "probe", SID)
        restore_released(root, "probe", SID)
        assert cleanup_expired(root) == 0
        active = get_active_dispatches(root)
        assert active[0]["first_dispatched_at"] == old

    def test_expired_release_record_is_pruned(self, root):
        _record(root, handle="old")
        release_dispatch(root, "old", SID)
        state = _state(root)
        state["released"][0]["released_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=25)
        ).isoformat()
        get_state_file_path(root).write_text(json.dumps(state), encoding="utf-8")
        dt.reset_cache()

        _record(root, handle="new")
        release_dispatch(root, "new", SID)
        assert [r["agent_handle"] for r in _state(root)["released"]] == ["new"]


# ---------------------------------------------------------------------------
# hook：PostToolUse(SendMessage)
# ---------------------------------------------------------------------------


def _send_message_payload(to, session_id=SID):
    return {
        "tool_name": "SendMessage",
        "session_id": session_id,
        "tool_use_id": "tu_sm",
        "tool_input": {"to": to, "message": "continue", "summary": "s"},
        "tool_response": {},
    }


def _run_hook(monkeypatch, root, payload):
    monkeypatch.setattr(_hook, "is_subagent_environment", lambda _d: False)
    monkeypatch.setattr(_hook, "get_project_root", lambda: root)
    called = []
    monkeypatch.setattr(_hook, "detect_orphan_branches", lambda _r: called.append("orphan") or [])
    monkeypatch.setattr(_hook, "record_dispatch", lambda **k: called.append("record"))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = _hook.main()
    return rc, called


class TestHookSendMessage:
    def test_send_message_restores_released_agent(self, root, monkeypatch, capsys):
        _record(root, handle="probe")
        release_dispatch(root, "probe", SID)
        rc, called = _run_hook(monkeypatch, root, _send_message_payload("probe"))
        assert rc == 0
        assert [d["agent_handle"] for d in get_active_dispatches(root)] == ["probe"]
        assert called == []  # 不走 Agent 記錄與 housekeeping
        assert "重新登記" in capsys.readouterr().out

    def test_send_message_with_ref_suffix_restores(self, root, monkeypatch, capsys):
        _record(root, handle="probe")
        release_dispatch(root, "probe", SID)
        rc, _ = _run_hook(monkeypatch, root, _send_message_payload("probe [abc123]"))
        assert rc == 0
        assert [d["agent_handle"] for d in get_active_dispatches(root)] == ["probe"]

    def test_send_message_without_release_changes_nothing(self, root, monkeypatch, capsys):
        _record(root, handle="probe")
        before = get_state_file_path(root).read_text(encoding="utf-8")
        rc, called = _run_hook(monkeypatch, root, _send_message_payload("probe"))
        assert rc == 0
        assert called == []
        assert get_state_file_path(root).read_text(encoding="utf-8") == before
        assert capsys.readouterr().out.strip() == ""

    def test_send_message_to_peer_session_is_noop(self, root, monkeypatch):
        _record(root, handle="probe")
        release_dispatch(root, "probe", SID)
        rc, _ = _run_hook(
            monkeypatch, root, _send_message_payload("uds:/tmp/cc-socks/1.sock")
        )
        assert rc == 0
        assert get_active_dispatches(root) == []

    def test_send_message_restore_failure_is_visible(self, root, monkeypatch, capsys):
        def _boom(*a, **k):
            raise OSError("disk")

        monkeypatch.setattr(_hook, "restore_released", _boom)
        rc, _ = _run_hook(monkeypatch, root, _send_message_payload("probe"))
        assert rc == 0
        assert "恢復失敗" in capsys.readouterr().err

    def test_agent_payload_still_records(self, root, monkeypatch):
        """對照：非 SendMessage 的 payload 仍走派發記錄路徑。"""
        payload = {
            "tool_name": "Agent",
            "session_id": SID,
            "tool_use_id": "tu_1",
            "tool_input": {"description": "d", "prompt": "", "name": "probe"},
            "tool_response": {"agentId": "ag_1"},
        }
        monkeypatch.setattr(_hook, "cleanup_expired", lambda _r: 0)
        monkeypatch.setattr(_hook, "extract_where_files", lambda *a, **k: [])
        rc, called = _run_hook(monkeypatch, root, payload)
        assert rc == 0
        assert "record" in called
