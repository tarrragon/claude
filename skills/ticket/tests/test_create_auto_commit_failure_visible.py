"""0.4.0-W1-064 — create 的 auto-commit 失敗不可靜默。

三個實例的共同特徵：建票回報 OK，票檔停在 untracked，無可見警告。成因兩類：
(1) update-ref 持 ref 鎖期間被 timeout 殺掉（reference-transaction hook 在高負載下
    執行超過 _GIT_TIMEOUT），留下 HEAD.lock／main.lock 殘骸；
(2) 殘骸或暫時性鎖競爭使後續每次提交撞鎖失敗，失敗原因未傳到使用者端。

E1 對照：修正前 rc=0 且無 [WARNING]；修正後 rc=EXIT_AUTO_COMMIT_FAILED 並輸出原因。
E2 對照：新鮮的鎖不得被判為過期殘骸。
"""

from __future__ import annotations

import os
import stat
import threading
import time
from pathlib import Path

from tests.test_create_auto_commit import (  # noqa: F401 (fixture 需在本檔可見)
    _commit_count,
    _make_args,
    _run_git,
    _single_created_ticket_id,
    git_repo,
    patch_paths_to_repo,
)


def _main_lock(repo: Path) -> Path:
    branch = _run_git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip()
    return repo / ".git" / "refs" / "heads" / f"{branch}.lock"


def _age(path: Path, seconds: int) -> None:
    old = time.time() - seconds
    os.utime(path, (old, old))


class TestStaleLockVisible:
    def test_stale_ref_lock_warns_and_exit_code(self, patch_paths_to_repo, capsys):
        """E1：過期鎖 -> [WARNING] + 專用 exit code；票檔仍在；鎖不被刪除。"""
        from ticket_system.commands.create import EXIT_AUTO_COMMIT_FAILED, execute

        repo = patch_paths_to_repo
        lock = _main_lock(repo)
        lock.write_text("deadbeef\n", encoding="utf-8")
        _age(lock, 600)

        rc = execute(_make_args())

        err = capsys.readouterr().err
        assert rc == EXIT_AUTO_COMMIT_FAILED
        assert "[WARNING]" in err
        assert str(lock) in err, "警告須含鎖檔路徑"
        assert "[殘骸診斷]" in err, "警告須含失敗原因（過期鎖診斷）"
        assert "git commit" in err or "git add" in err, "警告須含補救指令"
        assert lock.exists(), "工具絕不自動刪除鎖檔"
        ticket_id = _single_created_ticket_id(repo / "tickets")
        assert (repo / "tickets" / f"{ticket_id}.md").exists()

    def test_exit_code_distinct_from_create_failure(self):
        from ticket_system.commands.create import EXIT_AUTO_COMMIT_FAILED

        assert EXIT_AUTO_COMMIT_FAILED not in (0, 1, 2)

    def test_fresh_lock_not_judged_stale(self, patch_paths_to_repo, capsys):
        """E2：新鮮的鎖（模擬進行中的 git）不可被判為過期殘骸。"""
        from ticket_system.commands.create import EXIT_AUTO_COMMIT_FAILED, execute

        repo = patch_paths_to_repo
        lock = _main_lock(repo)
        lock.write_text("deadbeef\n", encoding="utf-8")  # mtime = now

        rc = execute(_make_args())

        err = capsys.readouterr().err
        assert rc == EXIT_AUTO_COMMIT_FAILED  # 重試耗盡後仍須可見
        assert "[WARNING]" in err
        assert "[殘骸診斷]" not in err
        assert lock.exists()


class TestTransientContention:
    def test_lock_released_during_retry_commits_silently(
        self, patch_paths_to_repo, capsys
    ):
        from ticket_system.commands.create import execute

        repo = patch_paths_to_repo
        lock = _main_lock(repo)
        lock.write_text("deadbeef\n", encoding="utf-8")
        before = _commit_count(repo)
        timer = threading.Timer(2.5, lambda: lock.unlink())
        timer.start()
        try:
            rc = execute(_make_args())
        finally:
            timer.join()

        err = capsys.readouterr().err
        assert rc == 0
        assert "[WARNING]" not in err
        assert _commit_count(repo) == before + 1


class TestUpdateRefNotKilled:
    def test_slow_reference_transaction_hook_leaves_no_lock(
        self, patch_paths_to_repo, monkeypatch, capsys
    ):
        """根因：update-ref 持鎖時被 timeout 殺掉會留下殘骸鎖。

        hook 睡 3 秒、timeout 設 1 秒：修正前 git 被殺、HEAD.lock／main.lock 殘留；
        修正後 update-ref 不受短 timeout 約束，ref 正確推進、無殘鎖。
        """
        from ticket_system.commands.create import execute
        from ticket_system.lib import git_ops

        repo = patch_paths_to_repo
        hook = repo / ".git" / "hooks" / "reference-transaction"
        hook.write_text(
            '#!/bin/sh\ncat >/dev/null\n[ "$1" = prepared ] && sleep 3\nexit 0\n',
            encoding="utf-8",
        )
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
        monkeypatch.setattr(git_ops, "_GIT_TIMEOUT", 1)
        before = _commit_count(repo)

        rc = execute(_make_args())

        err = capsys.readouterr().err
        assert _commit_count(repo) == before + 1, "ref 應正確推進"
        assert not (repo / ".git" / "HEAD.lock").exists()
        assert not _main_lock(repo).exists()
        assert rc == 0
        assert "[WARNING]" not in err


class TestRetryWrapper:
    def test_retries_lock_contention_then_succeeds(self, monkeypatch):
        from ticket_system.lib import git_utils

        monkeypatch.setattr(git_utils.time, "sleep", lambda s: None)
        calls = []

        def fake(*a, result_out=None, **kw):
            calls.append(1)
            if len(calls) < 3:
                result_out["error"] = "fatal: Unable to create '/r/.git/refs/heads/main.lock': File exists."
                return "git_failed"
            return "committed"

        monkeypatch.setattr(git_utils, "_auto_commit_ticket_md", fake)
        out = git_utils.auto_commit_ticket_md_with_retry("p", "id", "s")
        assert out["status"] == "committed" and out["attempts"] == 3

    def test_stale_or_non_lock_failure_not_retried(self, monkeypatch):
        from ticket_system.lib import git_utils

        monkeypatch.setattr(git_utils.time, "sleep", lambda s: None)
        errors = iter([
            "Unable to create '/r/.git/HEAD.lock'\n[殘骸診斷] stale",
            "fatal: something else",
        ])
        calls = []

        def fake(*a, result_out=None, **kw):
            calls.append(1)
            result_out["error"] = next(errors)
            return "git_failed"

        monkeypatch.setattr(git_utils, "_auto_commit_ticket_md", fake)
        assert git_utils.auto_commit_ticket_md_with_retry("p", "id", "s")["attempts"] == 1
        assert git_utils.auto_commit_ticket_md_with_retry("p", "id", "s")["attempts"] == 1
