"""C1 組三支非守衛 hook 的共用狀態根測試（3.3.0-W1-204.1.2.7）。

SR（票面、todolist、dispatch-active）讀取必須落主 repo（MAIN），
git 呼叫維持 get_project_root()（在 linked worktree 內為 WT）。
情境 B：cwd 與 CLAUDE_PROJECT_DIR 都在 WT；情境 C：CLAUDE_PROJECT_DIR=MAIN、cwd 在 WT。
E1 對照：把 get_shared_state_root 換成恆等函式，SR 斷言必須翻紅。
fixture 全在 tmp_path 的真實 linked worktree，關閉 HOOK_TEST_ISOLATION。
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent
for _p in (HOOKS, HOOKS.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SCENARIOS = ["B", "C"]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


@pytest.fixture
def repos(tmp_path: Path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "README.md").write_text("x")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    return main.resolve(), wt.resolve()


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(
        "c1_group_" + filename.replace("-", "_").removesuffix(".py"), HOOKS / filename
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _env(monkeypatch, repos, scenario: str) -> None:
    main, wt = repos
    monkeypatch.chdir(wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt if scenario == "B" else main))
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)


def _stdin(monkeypatch, payload: dict) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


class _Null:
    def __getattr__(self, name):
        return lambda *a, **k: None


def _identity(root=None):
    return root


# ---------- parallel-dispatch-verification ----------

def _run_pdv(monkeypatch, repos, scenario, identity=False):
    hook = _load("parallel-dispatch-verification-hook.py")
    if identity:
        monkeypatch.setattr(hook, "get_shared_state_root", _identity)
    seen = {}
    monkeypatch.setattr(hook, "is_ticket_complete_success", lambda d: True)
    monkeypatch.setattr(hook, "extract_ticket_id", lambda d: "0.1.0-W1-001")
    monkeypatch.setattr(hook, "is_subagent_environment", lambda d: False)

    def where(tid, root, logger):
        seen["where"] = root
        return ["a.py"]

    def kind(tid, root, logger):
        seen["kind"] = root
        return ("IMP", False)

    def changes(root, *a, **k):
        seen["git"] = root
        raise RuntimeError("stop-after-git-spy")

    monkeypatch.setattr(hook, "read_ticket_where_files", where)
    monkeypatch.setattr(hook, "read_ticket_type_and_children", kind)
    monkeypatch.setattr(hook, "get_ticket_change_sets", changes)
    _env(monkeypatch, repos, scenario)
    _stdin(monkeypatch, {"tool_name": "Bash"})
    hook.main()
    return seen


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_pdv_reads_ticket_from_main_git_stays(repos, monkeypatch, scenario):
    main, wt = repos
    seen = _run_pdv(monkeypatch, repos, scenario)
    assert seen["where"] == main
    assert seen["kind"] == main
    assert seen["git"] == (wt if scenario == "B" else seen["git"])
    if scenario == "B":
        assert seen["git"] != main


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_pdv_e1_identity_state_root_goes_red(repos, monkeypatch, scenario):
    """E1：恆等函式下 SR 不再是 MAIN（B 情境落 WT），證明斷言有鑑別力。"""
    main, wt = repos
    seen = _run_pdv(monkeypatch, repos, scenario, identity=True)
    if scenario == "B":
        assert seen["where"] != main


# ---------- post-git-commit ----------

def _run_wave(monkeypatch, repos, scenario, identity=False):
    hook = _load("post-git-commit-hook.py")
    if identity:
        monkeypatch.setattr(hook, "get_shared_state_root", _identity)
    seen = []
    monkeypatch.setattr(
        hook, "get_current_version_from_todolist",
        lambda root, logger: seen.append(root) or None)
    _env(monkeypatch, repos, scenario)
    hook._detect_wave_completion(_Null())
    return seen


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_post_git_commit_wave_reads_main(repos, monkeypatch, scenario):
    main, _ = repos
    assert _run_wave(monkeypatch, repos, scenario) == [main]


def test_post_git_commit_e1_identity_goes_red(repos, monkeypatch):
    main, _ = repos
    assert _run_wave(monkeypatch, repos, "B", identity=True) != [main]


# ---------- dispatch-stall-reminder ----------

def _run_stall(monkeypatch, repos, scenario, identity=False):
    hook = _load("dispatch-stall-reminder-hook.py")
    if identity:
        monkeypatch.setattr(hook, "get_shared_state_root", _identity)
    seen = {}

    def build(root, session, now, git_root=None):
        seen["state"], seen["git"] = root, git_root
        return []

    monkeypatch.setattr(hook, "build_reminders", build)
    monkeypatch.setattr(hook, "is_subagent_environment", lambda d: False)
    _env(monkeypatch, repos, scenario)
    _stdin(monkeypatch, {"session_id": "s"})
    hook.main()
    return seen, hook


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_stall_main_state_root_main_git_root_original(repos, monkeypatch, scenario):
    main, wt = repos
    seen, hook = _run_stall(monkeypatch, repos, scenario)
    assert seen["state"] == main
    assert seen["git"] == hook.get_project_root()
    if scenario == "B":
        assert seen["git"] == wt


def test_stall_e1_identity_goes_red(repos, monkeypatch):
    main, _ = repos
    seen, _hook = _run_stall(monkeypatch, repos, "B", identity=True)
    assert seen["state"] != main


def test_stall_build_reminders_splits_roots(repos, monkeypatch):
    """dispatch-active 與票面用 state 根；has_commit_since 用 git 根。"""
    main, wt = repos
    hook = _load("dispatch-stall-reminder-hook.py")
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ended = (now - timedelta(minutes=45)).isoformat()
    entry = {"session_id": "s", "ticket_id": "T", "turn_ended_at": ended}
    seen = {}
    monkeypatch.setattr(
        hook, "get_active_dispatches", lambda r: seen.__setitem__("dispatch", r) or [entry])
    tf = main / "t.md"
    tf.write_text("x")
    monkeypatch.setattr(hook, "find_ticket_file", lambda r, t: seen.__setitem__("ticket", r) or tf)
    monkeypatch.setattr(hook, "read_ticket_status", lambda f: "in_progress")
    os.utime(tf, (0, 0))
    monkeypatch.setattr(
        hook, "has_commit_since", lambda r, t, s: seen.__setitem__("git", r) or False)
    out = hook.build_reminders(main, "s", now, git_root=wt)
    assert len(out) == 1
    assert seen == {"dispatch": main, "ticket": main, "git": wt}
    seen.clear()
    hook.build_reminders(main, "s", now)
    assert seen["git"] == main
