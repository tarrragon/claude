"""dispatch-stall-reminder-hook 測試：E1 對照（停滯會提醒、任一條件不成立不輸出）與去重。"""

import importlib.util
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "dispatch_stall_reminder_hook", _HOOKS_DIR / "dispatch-stall-reminder-hook.py"
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

TID = "9.9.9-W1-001"
SESSION = "sess-A"
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
ENDED = NOW - timedelta(minutes=45)


def _git(root, *args, env_date=None):
    env = dict(os.environ)
    if env_date:
        env["GIT_COMMITTER_DATE"] = env_date
        env["GIT_AUTHOR_DATE"] = env_date
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, env=env)


@pytest.fixture
def root(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    tdir = tmp_path / "docs" / "work-logs" / "v9" / "tickets"
    tdir.mkdir(parents=True)
    ticket = tdir / f"{TID}.md"
    ticket.write_text("---\nstatus: in_progress\n---\nbody\n", encoding="utf-8")
    old = (ENDED - timedelta(minutes=10)).timestamp()
    os.utime(ticket, (old, old))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init",
         env_date="2025-01-01T00:00:00+00:00")
    return tmp_path


def _entry(**over):
    entry = {"session_id": SESSION, "ticket_id": TID,
             "turn_ended_at": ENDED.isoformat(), "agent_id": "ag1",
             "agent_description": "impl"}
    entry.update(over)
    return entry


def _run(monkeypatch, root, entries):
    monkeypatch.setattr(hook, "get_active_dispatches", lambda _r: entries)
    return hook.build_reminders(root, SESSION, NOW)


def test_stalled_entry_reminds(root, monkeypatch):
    result = _run(monkeypatch, root, [_entry()])
    assert len(result) == 1
    assert TID in result[0][1] and "45 分鐘" in result[0][1]


def test_not_overdue_silent(root, monkeypatch):
    recent = (NOW - timedelta(minutes=5)).isoformat()
    assert _run(monkeypatch, root, [_entry(turn_ended_at=recent)]) == []


def test_status_not_in_progress_silent(root, monkeypatch):
    f = hook.find_ticket_file(root, TID)
    f.write_text("---\nstatus: completed\n---\n", encoding="utf-8")
    old = (ENDED - timedelta(minutes=10)).timestamp()
    os.utime(f, (old, old))
    assert _run(monkeypatch, root, [_entry()]) == []


def test_commit_after_turn_end_silent(root, monkeypatch):
    (root / "x.txt").write_text("x")
    _git(root, "add", "x.txt")
    after = (ENDED + timedelta(minutes=5)).isoformat()
    _git(root, "commit", "-q", "-m", f"chore({TID}): work", env_date=after)
    assert _run(monkeypatch, root, [_entry()]) == []


def test_ticket_md_modified_after_turn_end_silent(root, monkeypatch):
    f = hook.find_ticket_file(root, TID)
    new = (ENDED + timedelta(minutes=5)).timestamp()
    os.utime(f, (new, new))
    assert _run(monkeypatch, root, [_entry()]) == []


def test_other_session_silent(root, monkeypatch):
    assert _run(monkeypatch, root, [_entry(session_id="other")]) == []


def test_turn_not_ended_or_no_ticket_silent(root, monkeypatch):
    entries = [_entry(turn_ended_at=None), _entry(ticket_id="")]
    assert _run(monkeypatch, root, entries) == []


def test_dedup_state_roundtrip(root, monkeypatch):
    monkeypatch.setattr(
        hook, "get_hook_log_dir",
        lambda name: root / ".claude" / "hook-logs" / name,
    )
    state = hook._state_file()
    assert hook.load_reminded(state) == []
    key = hook.dedup_key(_entry())
    hook.save_reminded(state, [key])
    assert key in hook.load_reminded(state)
    assert hook.dedup_key(_entry(agent_id="", agent_handle="h")).startswith("h|")


def test_main_emits_once_then_dedups(root, monkeypatch, capsys):
    monkeypatch.setattr(hook, "get_active_dispatches", lambda _r: [_entry()])
    monkeypatch.setattr(hook, "get_project_root", lambda: root)
    monkeypatch.setattr(hook, "read_json_from_stdin", lambda _l: {"session_id": SESSION})
    monkeypatch.setattr(hook, "resolve_session_id", lambda _d: SESSION)

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(hook, "datetime", _Clock)
    assert hook.main() == 0
    assert TID in capsys.readouterr().out
    assert hook.main() == 0
    assert capsys.readouterr().out.strip() == ""


def test_fail_open_on_git_error(root, monkeypatch, capsys):
    monkeypatch.setattr(hook, "get_active_dispatches", lambda _r: [_entry()])
    monkeypatch.setattr(hook, "get_project_root", lambda: root)
    monkeypatch.setattr(hook, "read_json_from_stdin", lambda _l: {})
    monkeypatch.setattr(hook, "resolve_session_id", lambda _d: SESSION)

    def boom(*_a, **_k):
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(hook, "has_commit_since", boom)

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(hook, "datetime", _Clock)
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "" and "偵測失敗" in captured.err
