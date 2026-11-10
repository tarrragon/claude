"""dispatch_tracker 在 linked worktree 內讀寫主倉庫 dispatch-active.json 的對照測試。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib import dispatch_tracker as dt  # noqa: E402


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repos(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "f.txt").write_text("x")
    _git(main, "add", "f.txt")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wt-branch")
    for root in (main, wt):
        (root / ".claude").mkdir(exist_ok=True)
    dt.reset_cache()
    yield main.resolve(), wt.resolve()
    dt.reset_cache()


def _seed(root: Path, desc: str) -> None:
    state = {"dispatches": [{"agent_description": desc, "dispatched_at": "2099-01-01T00:00:00+00:00"}]}
    (root / ".claude" / "dispatch-active.json").write_text(json.dumps(state))


def test_read_in_worktree_returns_main_entries(repos):
    main, wt = repos
    _seed(main, "main-entry")
    _seed(wt, "worktree-entry")
    descs = [d["agent_description"] for d in dt.get_active_dispatches(wt)]
    assert descs == ["main-entry"]


def test_write_in_worktree_lands_in_main(repos):
    main, wt = repos
    _seed(wt, "stale-worktree")
    dt.record_dispatch(wt, "new-entry", tool_use_id="t1")
    main_state = json.loads((main / ".claude" / "dispatch-active.json").read_text())
    assert [d["agent_description"] for d in main_state["dispatches"]] == ["new-entry"]
    wt_state = json.loads((wt / ".claude" / "dispatch-active.json").read_text())
    assert [d["agent_description"] for d in wt_state["dispatches"]] == ["stale-worktree"]


def test_main_repo_unchanged(repos):
    main, _ = repos
    _seed(main, "m")
    assert [d["agent_description"] for d in dt.get_active_dispatches(main)] == ["m"]


def test_git_failure_falls_back_and_reports(repos, capsys, monkeypatch):
    _, wt = repos
    _seed(wt, "worktree-entry")

    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(dt.subprocess, "run", boom)
    dt.reset_cache()
    descs = [d["agent_description"] for d in dt.get_active_dispatches(wt)]
    assert descs == ["worktree-entry"]
    assert "降級" in capsys.readouterr().err
