"""A 組六支 hook 讀票面的根測試（3.3.0-W1-204.1.2.2）。

情境 B：cwd 與 CLAUDE_PROJECT_DIR 都在 linked worktree（WT）。
情境 C：CLAUDE_PROJECT_DIR=MAIN，cwd 在 WT。
兩者讀票面的根都必須是 MAIN；情境 A（cwd 在 MAIN）與 HOOK_TEST_ISOLATION=1 不變。

方法：以 spy 取代各 hook 下游讀票函式，記錄實際收到的根；
gate hook 另以僅存在於 MAIN 的真實票檔做正向對照。
fixture 全在 tmp_path，不碰真實主 repo。
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
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))
if str(HOOKS.parent) not in sys.path:
    sys.path.insert(0, str(HOOKS.parent))


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


@pytest.fixture
def repos(tmp_path: Path):
    """真實 repo（MAIN）與 linked worktree（WT），皆在 tmp_path。"""
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
        "a_group_" + filename.replace("-", "_").removesuffix(".py"), HOOKS / filename
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _env(monkeypatch, cwd: Path, project_dir: Path, isolation: bool = False):
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_dir))
    if isolation:
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    else:
        monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)


def _stdin(monkeypatch, payload: dict):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def _roots(repos, cwd_key, env_key):
    main, wt = repos
    pick = {"main": main, "wt": wt}
    return pick[cwd_key], pick[env_key]


def _expected(repos, key):
    return {"main": repos[0], "wt": repos[1]}[key]


def _case(repos, monkeypatch, cwd_key, env_key, isolation):
    cwd, env = _roots(repos, cwd_key, env_key)
    _env(monkeypatch, cwd, env, isolation)


PARAMS = "cwd_key,env_key,expect_key,isolation"


def _scenarios():
    # (cwd, env, 預期根, isolation)
    return [
        pytest.param("wt", "wt", "main", False, id="B"),
        pytest.param("wt", "main", "main", False, id="C"),
        pytest.param("main", "main", "main", False, id="A-main-cwd"),
    ]


@pytest.mark.parametrize(PARAMS, _scenarios())
def test_command_entrance_gate_reads_main(repos, monkeypatch, cwd_key, env_key, expect_key, isolation):
    hook = _load("command-entrance-gate-hook.py")
    seen = []
    monkeypatch.setattr(hook, "find_ticket_files", lambda root, **k: seen.append(root) or [])
    _case(repos, monkeypatch, cwd_key, env_key, isolation)
    hook.get_latest_pending_ticket(logger=_NullLogger())
    assert seen == [_expected(repos, expect_key)]


def test_command_entrance_gate_positive_main_only_ticket(repos, monkeypatch):
    """正向對照：票只存在 MAIN，從 WT 執行（B、C）都找得到。"""
    main, wt = repos
    tdir = main / ".claude" / "tickets"
    tdir.mkdir(parents=True)
    (tdir / "0.1.0-W1-001.md").write_text("---\nid: 0.1.0-W1-001\nstatus: in_progress\n---\nbody\n")
    hook = _load("command-entrance-gate-hook.py")
    for env_dir in (wt, main):
        _env(monkeypatch, wt, env_dir)
        found = hook.get_latest_pending_ticket(logger=_NullLogger())
        assert found is not None and found[0] == "0.1.0-W1-001"


@pytest.mark.parametrize(PARAMS, _scenarios())
def test_commit_handoff_reads_main(repos, monkeypatch, cwd_key, env_key, expect_key, isolation):
    hook = _load("commit-handoff-hook.py")
    seen = []
    monkeypatch.setattr(
        hook, "get_current_version_from_todolist", lambda root, logger: seen.append(root) or None
    )
    _case(repos, monkeypatch, cwd_key, env_key, isolation)
    hook.detect_wave_completion(_NullLogger())
    assert seen == [_expected(repos, expect_key)]


@pytest.mark.parametrize(PARAMS, _scenarios())
def test_file_ownership_guard_reads_main(repos, monkeypatch, cwd_key, env_key, expect_key, isolation):
    hook = _load("file-ownership-guard-hook.py")
    seen = []
    monkeypatch.setattr(hook, "_validate_input", lambda *a, **k: "0.1.0-W1-001")
    monkeypatch.setattr(
        hook, "find_file_ownership_conflicts", lambda tid, root, logger: seen.append(root) or []
    )
    monkeypatch.setattr(hook, "emit_hook_output", lambda *a, **k: None)
    _case(repos, monkeypatch, cwd_key, env_key, isolation)
    _stdin(monkeypatch, {"tool_name": "Agent"})
    hook.main()
    assert seen == [_expected(repos, expect_key)]


@pytest.mark.parametrize(PARAMS, _scenarios())
def test_parallel_claim_audit_reads_and_writes_main(repos, monkeypatch, cwd_key, env_key, expect_key, isolation):
    hook = _load("parallel-claim-audit-hook.py")
    snap, wrote = [], []
    monkeypatch.setattr(hook, "parse_claim_command", lambda c: "0.1.0-W1-001")
    monkeypatch.setattr(hook, "is_claim_successful", lambda *a, **k: True)
    monkeypatch.setattr(
        hook, "build_same_wave_snapshot", lambda tid, root, logger: snap.append(root) or ("W1", [])
    )
    monkeypatch.setattr(hook, "write_audit_entry", lambda e, logger: wrote.append(e))
    _case(repos, monkeypatch, cwd_key, env_key, isolation)
    _stdin(monkeypatch, {"tool_name": "Bash", "tool_input": {"command": "x"}})
    hook.main()
    expect = _expected(repos, expect_key)
    assert snap == [expect]
    assert len(wrote) == 1, "write_audit_entry 必須被呼叫恰好一次"


@pytest.mark.parametrize(PARAMS, _scenarios())
def test_parallel_suggestion_reads_main(repos, monkeypatch, cwd_key, env_key, expect_key, isolation):
    hook = _load("parallel-suggestion-hook.py")
    seen = []
    monkeypatch.setattr(hook, "is_continuation_request", lambda p, logger: True)
    monkeypatch.setattr(hook, "find_ticket_files", lambda root, **k: seen.append(root) or [])
    _case(repos, monkeypatch, cwd_key, env_key, isolation)
    _stdin(monkeypatch, {"prompt": "繼續"})
    hook.main()
    assert seen and seen[0] == _expected(repos, expect_key)


@pytest.mark.parametrize(PARAMS, _scenarios())
def test_session_experience_reminder_reads_main(repos, monkeypatch, cwd_key, env_key, expect_key, isolation):
    hook = _load("session-experience-persistence-reminder-hook.py")
    seen = []
    monkeypatch.setattr(hook, "scan_context_sensitive_tickets", lambda root, logger: seen.append(root) or [])
    _case(repos, monkeypatch, cwd_key, env_key, isolation)
    hook.scan_tickets(_NullLogger())
    assert seen == [_expected(repos, expect_key)]


def test_isolation_keeps_fallback_root(repos, monkeypatch):
    """HOOK_TEST_ISOLATION=1 時不回推主 repo，仍用呼叫端解析的根。"""
    hook = _load("session-experience-persistence-reminder-hook.py")
    seen = []
    monkeypatch.setattr(hook, "scan_context_sensitive_tickets", lambda root, logger: seen.append(root) or [])
    main, wt = repos
    _env(monkeypatch, wt, wt, isolation=True)
    hook.scan_tickets(_NullLogger())
    assert seen == [wt]


def test_session_state_dir_and_git_untouched(repos, monkeypatch):
    """session 狀態目錄改走 shared state root（3.3.0-W1-204.1.5.1 由 get_project_root 遷移）。"""
    hook = _load("session-experience-persistence-reminder-hook.py")
    main, wt = repos
    _env(monkeypatch, wt, main)
    assert hook.get_state_dir().parent.parent == main


class _NullLogger:
    def __getattr__(self, name):
        return lambda *a, **k: None
