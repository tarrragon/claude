"""G3 hook-logs 路徑在 linked worktree 內須落在主 repo（3.3.0-W1-204.1.6.4）。

相對路徑 `.claude/hook-logs/...` 與 repo toplevel 拼接都依 cwd，worktree 內會與主 repo
分處兩地。本檔不設 HOOK_TEST_ISOLATION（skill conftest 預設設了，這裡移除），
直接驗證寫入落在主 repo 的 `.claude/hook-logs`，且 worktree 自己的 `.claude/hook-logs` 不被建立。
"""

import subprocess
from pathlib import Path

import pytest

from ticket_system.lib import git_ops, git_utils, precondition, protocol_version_checker


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def linked_worktree(tmp_path, monkeypatch):
    """回傳 (主 repo 根, linked worktree 根)；cwd 切到 worktree，隔離旗標全數移除。"""
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    _git(main, "commit", "-q", "--allow-empty", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wt-branch")
    for name in ("HOOK_TEST_ISOLATION", "HOOK_LOGS_DIR", "CLAUDE_PROJECT_DIR", "TICKET_SYSTEM_TEST_ISOLATION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(wt)
    return main, wt


def _only_log(root: Path, subdir: str) -> str:
    logs = list((root / ".claude" / "hook-logs" / subdir).glob("*"))
    assert logs, f"{root}/.claude/hook-logs/{subdir} 沒有日誌檔"
    return logs[0].read_text(encoding="utf-8")


def test_prevalidate_failure_log_lands_in_main_repo(linked_worktree):
    main, wt = linked_worktree
    git_ops._report_prevalidate_failure(str(wt), "worktree-probe")
    assert "worktree-probe" in _only_log(main, "git-ops-prevalidate")
    assert not (wt / ".claude" / "hook-logs").exists()


def test_commit_retry_log_lands_in_main_repo(linked_worktree, monkeypatch):
    main, wt = linked_worktree
    monkeypatch.setattr(git_utils, "_RETRY_LOG_DIR", None)  # conftest 把 seam 導向 tmp，這裡走預設路徑
    ticket = wt / "T-1.md"
    ticket.write_text("x\n", encoding="utf-8")
    git_utils._log_commit_event(str(ticket), "retry", "T-1", 1, 0.1, "index.lock exists")
    assert "ticket=T-1" in _only_log(main, "ticket-commit-retry")
    assert not (wt / ".claude" / "hook-logs").exists()


def test_force_usage_log_lands_in_main_repo(linked_worktree):
    main, wt = linked_worktree
    precondition.write_force_usage_log("T-1", "complete", "pending")
    text = (main / ".claude" / "hook-logs" / "cli-force-usage.jsonl").read_text(encoding="utf-8")
    assert '"ticket_id": "T-1"' in text
    assert not (wt / ".claude" / "hook-logs").exists()


def test_protocol_version_log_lands_in_main_repo(linked_worktree):
    main, wt = linked_worktree
    protocol_version_checker.log_exception("worktree-probe")
    text = (main / ".claude" / "hook-logs" / "protocol-version-check.log").read_text(encoding="utf-8")
    assert "worktree-probe" in text
    assert not (wt / ".claude" / "hook-logs").exists()
