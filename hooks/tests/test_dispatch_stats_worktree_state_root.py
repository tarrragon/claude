"""
204.1.6.5：events.jsonl / annotations.json 讀寫兩端改經 get_hook_log_dir

不設 HOOK_TEST_ISOLATION：以真實 git linked worktree fixture 驗證
讀（dispatch_stats）與寫（agent-dispatch-validation-hook）都落在主 checkout 的 .claude/hook-logs。
每個情境以子程序執行，cwd 為被測 checkout，輸出為 stdout 的 JSON 行。

執行：pytest .claude/hooks/tests/test_dispatch_stats_worktree_state_root.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
DISPATCH_STATS = HOOKS_DIR / "dispatch_stats.py"
HOOK = HOOKS_DIR.parent / "skills" / "ticket" / "hooks" / "agent-dispatch-validation-hook.py"
REL_EVENTS = Path(".claude/hook-logs/agent-dispatch-validation/events/events.jsonl")
REL_ANN = Path(".claude/hook-logs/agent-dispatch-validation/events/annotations.json")

EVENT = {
    "event_id": "20260101T000000Z-aaaaaaaa",
    "timestamp": "2026-01-01T00:00:00Z",
    "subagent_type": "x",
    "conflicts": [{"keyword": "k"}],
    "prompt_hash": "a" * 16,
    "prompt_length": 3,
}

_WRITE_SNIPPET = """
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("hook_under_test", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._write_event_jsonl("sub", "prompt-" + sys.argv[2], [{"keyword": "k"}], None)
print(json.dumps({"path": str(m._EVENTS_JSONL_PATH)}))
"""


def _env() -> dict:
    env = os.environ.copy()
    for k in ("HOOK_TEST_ISOLATION", "CLAUDE_PROJECT_DIR",
              "DISPATCH_STATS_EVENTS_PATH", "DISPATCH_STATS_ANNOTATIONS_PATH"):
        env.pop(k, None)
    return env


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repos(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
         "--allow-empty", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    return main.resolve(), wt.resolve()


def _write_via_hook(cwd: Path, tag: str) -> Path:
    out = subprocess.run(
        [sys.executable, "-c", _WRITE_SNIPPET, str(HOOK), tag],
        cwd=cwd, env=_env(), capture_output=True, text=True, check=True,
    )
    return Path(json.loads(out.stdout.strip().splitlines()[-1])["path"])


def _stats_list(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DISPATCH_STATS), "list", "--format", "json"],
        cwd=cwd, env=_env(), capture_output=True, text=True,
    )


def _seed(root: Path) -> None:
    p = root / REL_EVENTS
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(EVENT) + "\n", encoding="utf-8")


class TestWriteEndLandsInMainCheckout:
    def test_write_from_linked_worktree_lands_in_main(self, repos):
        main, wt = repos
        path = _write_via_hook(wt, "wt")
        assert path == main / REL_EVENTS
        assert (main / REL_EVENTS).exists()
        assert not (wt / REL_EVENTS).exists()

    def test_write_from_main_lands_in_main(self, repos):
        main, _ = repos
        assert _write_via_hook(main, "main") == main / REL_EVENTS

    def test_parallel_writers_merge_into_one_file(self, repos):
        main, wt = repos
        _write_via_hook(main, "main")
        _write_via_hook(wt, "wt")
        lines = (main / REL_EVENTS).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert not (wt / REL_EVENTS).exists()


class TestReadEndReadsMainCheckout:
    def test_read_from_linked_worktree_sees_main_events(self, repos):
        main, wt = repos
        _seed(main)
        res = _stats_list(wt)
        assert res.returncode == 0, res.stderr
        assert EVENT["event_id"] in res.stdout

    def test_read_from_main_sees_main_events(self, repos):
        main, _ = repos
        _seed(main)
        res = _stats_list(main)
        assert res.returncode == 0, res.stderr
        assert EVENT["event_id"] in res.stdout

    def test_write_then_read_roundtrip_across_checkouts(self, repos):
        main, wt = repos
        _write_via_hook(wt, "wt")
        res = _stats_list(main)
        assert res.returncode == 0, res.stderr
        assert "sub" in res.stdout

    def test_annotation_written_from_worktree_lands_in_main(self, repos):
        main, wt = repos
        _seed(main)
        res = subprocess.run(
            [sys.executable, str(DISPATCH_STATS), "annotate", EVENT["event_id"],
             "--label", "true_positive"],
            cwd=wt, env=_env(), capture_output=True, text=True,
        )
        assert res.returncode == 0, res.stderr
        assert (main / REL_ANN).exists()
        assert not (wt / REL_ANN).exists()
