"""lib 層未傳根時改用共用狀態根（3.3.0-W1-204.1.2.1）。

三處：hook_ticket.validate_ticket_unified／find_active_in_progress_ticket、
hook_io._scan_handoff_pending、todo_pending_registry.registry_path。

情境 B：cwd 與 CLAUDE_PROJECT_DIR 都在 linked worktree。
情境 C：CLAUDE_PROJECT_DIR=主倉庫、cwd=linked worktree。
兩者都必須落在主倉庫；主倉庫內執行時行為不變；傳根時語意不變。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib import hook_base, hook_io
from lib.hook_ticket import find_active_in_progress_ticket, validate_ticket_unified

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "framework-issue" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import todo_pending_registry as registry  # noqa: E402

TICKET_ID = "3.3.0-W1-900"
HANDOFF_SRC = "demo-src"
HANDOFF_TGT = "demo-tgt"


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _ticket(root):
    d = root / "docs" / "work-logs" / "v3.3.0" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    (d / (TICKET_ID + ".md")).write_text(
        "---\nid: %s\nstatus: in_progress\ndecision_tree_path:\n  entry_point: x\n---\n# t\n"
        % TICKET_ID,
        encoding="utf-8",
    )


def _handoff(root):
    pending = root / ".claude" / "handoff" / "pending"
    pending.mkdir(parents=True)
    (pending / "x.json").write_text(
        json.dumps({"ticket_id": HANDOFF_SRC, "target_ticket_id": HANDOFF_TGT}),
        encoding="utf-8",
    )
    tickets = root / ".claude" / "tickets"
    tickets.mkdir(parents=True, exist_ok=True)
    for tid in (HANDOFF_SRC, HANDOFF_TGT):
        (tickets / (tid + ".md")).write_text(
            "---\nid: %s\nstatus: pending\n---\n" % tid, encoding="utf-8"
        )


@pytest.fixture
def repos(tmp_path, monkeypatch):
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("x", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    hook_base.clear_project_root_cache()
    yield main, wt
    hook_base.clear_project_root_cache()


def _enter(monkeypatch, cwd, env_root):
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(env_root))
    hook_base.clear_project_root_cache()


@pytest.fixture(params=["B", "C"])
def in_worktree(request, repos, monkeypatch):
    main, wt = repos
    _enter(monkeypatch, wt, wt if request.param == "B" else main)
    return main, wt


def test_validate_ticket_unified_reads_main(in_worktree):
    main, wt = in_worktree
    _ticket(main)
    ok, msg = validate_ticket_unified(TICKET_ID)
    assert ok, msg


def test_find_active_in_progress_ticket_reads_main(in_worktree):
    main, wt = in_worktree
    _ticket(main)
    fm = find_active_in_progress_ticket()
    assert fm is not None and fm.get("id") == TICKET_ID


def test_scan_handoff_pending_reads_main(in_worktree):
    main, wt = in_worktree
    _handoff(main)
    hits = hook_io._scan_handoff_pending(None, None)
    assert [name for name, _ in hits] == ["x.json"]


def test_is_handoff_recovery_mode_reads_main(in_worktree, monkeypatch):
    main, wt = in_worktree
    _handoff(main)
    monkeypatch.setattr(hook_io, "_handoff_recovery_cache", None)
    assert hook_io.is_handoff_recovery_mode() is True


def test_registry_path_lands_in_main(in_worktree):
    main, wt = in_worktree
    assert registry.registry_path() == (
        main / ".claude" / "state" / "framework-issue-todo-pending.json"
    )


# --- 反向對照：不在 linked worktree 時行為不變 ---


def test_main_checkout_behaviour_unchanged(repos, monkeypatch):
    main, wt = repos
    _enter(monkeypatch, main, main)
    _ticket(main)
    assert validate_ticket_unified(TICKET_ID)[0] is True
    assert find_active_in_progress_ticket()["id"] == TICKET_ID
    assert registry.registry_path().parent.parent.parent == main


# --- 傳根時語意不變：明確傳入的根不被覆蓋為主倉庫（測試隔離下） ---


def test_explicit_root_is_used_when_passed(repos, monkeypatch, tmp_path):
    main, wt = repos
    _enter(monkeypatch, main, main)
    other = tmp_path / "other"
    _ticket(other)
    assert validate_ticket_unified(TICKET_ID, project_root=other)[0] is True
    assert find_active_in_progress_ticket(project_root=other)["id"] == TICKET_ID
    assert registry.registry_path(other).parent.parent.parent == other
    assert hook_io._scan_handoff_pending(None, other) == []


def test_isolation_env_returns_fallback_root(repos, monkeypatch):
    main, wt = repos
    _enter(monkeypatch, wt, wt)
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    hook_base.clear_project_root_cache()
    assert registry.registry_path().parent.parent.parent == wt
