"""G2 寫入端 hook-logs 路徑：linked worktree 內須落在主 repo（3.3.0-W1-204.1.6.3）。

不設 HOOK_TEST_ISOLATION；在 tmp 主 repo + linked worktree fixture 內，
以 worktree 內的 hook 副本執行，斷言日誌寫到主 repo 的 .claude/hook-logs。
"""
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_SRC = REPO_ROOT / ".claude"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def linked_worktree(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wtb")
    (wt / ".claude" / "hooks").mkdir(parents=True)
    shutil.copytree(CLAUDE_SRC / "lib", wt / ".claude" / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("malformed-tool-call-detector-hook.py", "session-source-diagnostic-hook.py"):
        shutil.copy(CLAUDE_SRC / "hooks" / name, wt / ".claude" / "hooks" / name)
    return main.resolve(), wt.resolve()


def _env():
    return {k: v for k, v in os.environ.items() if k not in ("HOOK_TEST_ISOLATION", "CLAUDE_PROJECT_DIR")}


def test_session_source_diagnostic_writes_to_main_repo(linked_worktree):
    main, wt = linked_worktree
    hook = wt / ".claude" / "hooks" / "session-source-diagnostic-hook.py"
    subprocess.run(["python3", str(hook)], input='{"source":"x","session_id":"abcdefgh12"}',
                   text=True, cwd=wt, env=_env(), check=True, capture_output=True)
    assert (main / ".claude" / "hook-logs" / "session-source-diagnostic" / "diagnostic.log").exists()
    assert not (wt / ".claude" / "hook-logs").exists()


def test_malformed_detector_log_dir_in_main_repo(linked_worktree, monkeypatch):
    main, wt = linked_worktree
    monkeypatch.chdir(wt)
    for k in ("HOOK_TEST_ISOLATION", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(k, raising=False)
    hook = wt / ".claude" / "hooks" / "malformed-tool-call-detector-hook.py"
    spec = importlib.util.spec_from_file_location("mtcd_wt", hook)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.log("probe")
    expected = main / ".claude" / "hook-logs" / "malformed-tool-call-detector"
    assert Path(mod.LOG_DIR).resolve() == expected
    assert (expected / "malformed-tool-call-detector.log").exists()
