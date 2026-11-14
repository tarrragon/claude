"""identity_guard 寫 usage.log、identity_guard_adoption 讀回，在 linked worktree 內的落點測試
（3.3.0-W1-204.1.6.8）。不設 HOOK_TEST_ISOLATION：讀寫兩端都要落在主 repo 的
.claude/hook-logs/identity-guard/usage.log。
"""

import importlib.util
import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from ticket_system.lib import identity_guard
from ticket_system.lib.paths import reset_project_root_cache

_ADOPTION_PATH = Path(__file__).parent.parent / "tools" / "identity_guard_adoption.py"


def _load_adoption():
    spec = importlib.util.spec_from_file_location("identity_guard_adoption_wt", _ADOPTION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def checkouts(tmp_path, monkeypatch):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("# t\n", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wt-branch")
    main, wt = main.resolve(), wt.resolve()
    monkeypatch.delenv("HOOK_LOGS_DIR", raising=False)
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    monkeypatch.chdir(wt)
    reset_project_root_cache()
    return main, wt


def _log(root: Path) -> Path:
    return root / ".claude" / "hook-logs" / "identity-guard" / "usage.log"


def _write_one(command="complete", result="pass"):
    identity_guard._write_telemetry(
        command=command, ticket_id="0.0.0-W0-001", as_value="a", result=result, caller_type="agent"
    )


def test_write_from_worktree_lands_in_main(checkouts):
    main, wt = checkouts
    _write_one()
    assert _log(main).exists()
    assert not _log(wt).exists()


def test_adoption_default_path_is_main_log_in_worktree(checkouts):
    main, wt = checkouts
    assert _load_adoption()._resolve_log_path(None) == _log(main)


def test_write_then_read_roundtrip_from_worktree(checkouts):
    main, wt = checkouts
    adoption = _load_adoption()
    _write_one(command="complete", result="warn")
    _write_one(command="complete", result="pass")

    stats = adoption.compute_rolling_stats(adoption._resolve_log_path(None), now=datetime.now())

    assert stats["complete"].total == 2


def test_two_checkouts_write_same_log_and_reader_sees_both(checkouts, monkeypatch):
    main, wt = checkouts
    adoption = _load_adoption()
    _write_one()  # worktree 啟動
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main))
    monkeypatch.chdir(main)
    reset_project_root_cache()
    _write_one()  # 主 checkout 啟動

    lines = [json.loads(x) for x in _log(main).read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert adoption._resolve_log_path(None) == _log(main)


def test_hook_logs_dir_env_still_overrides_both_ends(checkouts, monkeypatch, tmp_path):
    override = tmp_path / "override"
    monkeypatch.setenv("HOOK_LOGS_DIR", str(override))
    _write_one()
    assert (override / "identity-guard" / "usage.log").exists()
    assert _load_adoption()._resolve_log_path(None) == override / "identity-guard" / "usage.log"
