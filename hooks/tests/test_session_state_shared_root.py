"""5 處 session 範圍狀態檔改取 shared state root 的測試（3.3.0-W1-204.1.5.1）。

情境 C：CLAUDE_PROJECT_DIR=MAIN，cwd 在 linked worktree（WT）。
寫入端與讀取端必須落到 MAIN 下同一份檔。不設 HOOK_TEST_ISOLATION；
fixture 全在 tmp_path，不碰真實主 repo。
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

HOOKS = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS.parent
for p in (HOOKS, CLAUDE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


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


@pytest.fixture
def scenario_c(repos, monkeypatch):
    main, wt = repos
    monkeypatch.chdir(wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    return main, wt


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Log:
    def __getattr__(self, _):
        return lambda *a, **k: None


def _stdin(monkeypatch, payload: dict):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def test_monitor_file_pre_write_post_read_same_sr(scenario_c, monkeypatch):
    main, wt = scenario_c
    pre = _load(HOOKS / "test-timeout-pre.py", "s_pre")
    post = _load(HOOKS / "post-test-hook.py", "s_post")
    payload = {"tool_name": "Bash", "tool_use_id": "toolu_1",
               "tool_input": {"command": "pytest tests/"}}
    _stdin(monkeypatch, payload)
    pre.main()
    keyed = main / ".claude" / "hook-logs" / "test-monitor" / "toolu_1.json"
    assert keyed.exists()
    assert not (wt / ".claude" / "hook-logs" / "test-monitor").exists()
    # 讀取端找得到同一份並收尾（鍵檔即刪）
    post.check_test_timeout(payload, payload["tool_input"], _Log())
    assert not keyed.exists()


def test_prune_uses_sr(scenario_c, monkeypatch):
    main, _ = scenario_c
    d = main / ".claude" / "hook-logs" / "test-monitor"
    d.mkdir(parents=True)
    stale = d / "old.json"
    stale.write_text("{}")
    old = time.time() - 7200
    os.utime(stale, (old, old))
    pre = _load(HOOKS / "test-timeout-pre.py", "s_pre2")
    _stdin(monkeypatch, {"tool_name": "Bash", "tool_use_id": "toolu_2",
                         "tool_input": {"command": "pytest tests/"}})
    pre.main()
    assert not stale.exists()


def test_persistence_reminder_state_dir_is_sr(scenario_c):
    main, _ = scenario_c
    mod = _load(HOOKS / "session-experience-persistence-reminder-hook.py", "s_per")
    assert mod.get_state_dir() == main / ".claude" / "hook-state"


def test_suggest_compact_counter_is_sr(scenario_c):
    main, _ = scenario_c
    mod = _load(CLAUDE / "skills" / "strategic-compact" / "suggest-compact.py", "s_sc")
    assert mod._counter_path("sess-1").parent == main / ".claude" / "hook-state"


def test_suggest_compact_counter_is_sr_when_env_is_wt(repos, monkeypatch):
    main, wt = repos
    monkeypatch.chdir(wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    mod = _load(CLAUDE / "skills" / "strategic-compact" / "suggest-compact.py", "s_sc2")
    assert mod._counter_path("sess-1").parent == main / ".claude" / "hook-state"


def test_wrap_decision_base_state_path_is_sr(scenario_c, monkeypatch):
    main, _ = scenario_c
    mod = _load(CLAUDE / "skills" / "wrap-decision" / "hooks" / "wrap-decision-tripwire-hook.py", "s_wd")
    seen = []

    class _Stop(Exception):
        pass

    def _spy(base, event, logger):
        seen.append(base)
        raise _Stop

    monkeypatch.setattr(mod, "is_pytest_environment", lambda: False)
    monkeypatch.setattr(mod, "load_config", lambda *a, **k: SimpleNamespace(state_file="s/state.json"))
    monkeypatch.setattr(mod, "resolve_state_path", _spy)
    _stdin(monkeypatch, {"session_id": "s1"})
    try:
        mod.main()
    except _Stop:
        pass
    assert seen == [main / "s" / "state.json"]
