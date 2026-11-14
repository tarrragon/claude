"""linked worktree 內 lib 的 hook-logs 寫入須落在主 repo（3.3.0-W1-204.1.6.2）。

子行程 + 清除 HOOK_TEST_ISOLATION，使 cwd 為 linked worktree 的解析走真實路徑。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[2]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repos(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("x\n", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "feat")
    return main.resolve(), wt.resolve()


def _run_in(wt: Path, code: str) -> None:
    env = {k: v for k, v in os.environ.items()
           if k not in ("HOOK_TEST_ISOLATION", "CLAUDE_PROJECT_DIR")}
    env["PYTHONPATH"] = str(CLAUDE_DIR)
    subprocess.run([sys.executable, "-c", code], cwd=wt, env=env, check=True)


def test_setup_project_environment_logs_dir_in_main_repo(repos):
    main, wt = repos
    _run_in(wt, "from lib.common_functions import setup_project_environment as s; s()")
    assert (main / ".claude" / "hook-logs").is_dir()
    assert not (wt / ".claude" / "hook-logs").exists()


def test_index_tripwire_log_in_main_repo(repos):
    main, wt = repos
    _run_in(wt, "from lib.git_utils import _log_bare_index_operation as f; f(['read-tree','HEAD'], None)")
    logs = list((main / ".claude" / "hook-logs").rglob("*.log"))
    assert logs, "tripwire 日誌應寫入主 repo"
    assert not (wt / ".claude" / "hook-logs").exists()
