"""1.0.0-W8-006 — auto-commit index.lock retry RED 測試（Phase 2）。

承接 1.0.0-W8-001 ANA 結論（方案 A）：index.lock 是唯一中頻 degrade 觸發源；
``_auto_commit_ticket_md`` 在 git commit 失敗（git_failed）且 stderr 含
``index.lock`` 時，sleep 1s 重試一次：

- 重試成功 → 回傳 ``"committed"``（degrade 被接住）。
- 重試仍失敗 → 回傳 ``"git_failed"``（沿用現有 degrade 路徑）。
- stderr 不含 ``index.lock`` 的 git_failed → 不重試，直接回 ``"git_failed"``。

驗證設計：透過 patch ``git_utils._run_git`` 控制 commit 步驟回傳值，
並 patch ``git_utils.time.sleep`` 避免測試實際 sleep（保持測試快速）。
rev-parse / add 成功、diff 回非 0（有變更）以觸發 commit 步驟。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ticket_system.lib import git_utils


def _make_run_git(commit_results):
    """產生 fake _run_git：rev-parse/add 成功、diff 回 1（有變更），commit 依序回傳。

    Args:
        commit_results: list[MagicMock]，每次 commit 呼叫依序回傳之 CompletedProcess。
    """
    commit_iter = iter(commit_results)

    def fake_run_git(cwd, *args, timeout=git_utils._FAST_GIT_TIMEOUT):
        if args[0] == "commit":
            return next(commit_iter)
        if args[:2] == ("diff", "--cached"):
            # returncode 1 表示有 staged 變更 → 觸發 commit
            return MagicMock(returncode=1)
        # rev-parse / add 成功
        return MagicMock(returncode=0)

    return fake_run_git


class TestIndexLockRetry:
    def test_retry_once_then_success_returns_committed(self):
        """commit 首次 git_failed 且 stderr 含 index.lock → sleep 1s 重試一次成功 → committed。"""
        first = MagicMock(returncode=1, stderr="fatal: Unable to create '.git/index.lock': File exists.")
        second = MagicMock(returncode=0, stderr="")

        fake_run_git = _make_run_git([first, second])

        with patch.object(git_utils, "_run_git", side_effect=fake_run_git), \
                patch.object(git_utils.time, "sleep") as mock_sleep:
            status = git_utils._auto_commit_ticket_md("/tmp/x.md", "1.0.0-W0-T", "Solution")

        assert status == "committed", "index.lock 重試成功應回 committed"
        mock_sleep.assert_called_once_with(1)

    def test_retry_once_then_still_fails_returns_git_failed(self):
        """commit 兩次皆 git_failed（含 index.lock）→ 仍回 git_failed。"""
        first = MagicMock(returncode=1, stderr="fatal: Unable to create '.git/index.lock': File exists.")
        second = MagicMock(returncode=1, stderr="fatal: Unable to create '.git/index.lock': File exists.")

        fake_run_git = _make_run_git([first, second])

        with patch.object(git_utils, "_run_git", side_effect=fake_run_git), \
                patch.object(git_utils.time, "sleep") as mock_sleep:
            status = git_utils._auto_commit_ticket_md("/tmp/x.md", "1.0.0-W0-T", "Solution")

        assert status == "git_failed", "重試仍失敗應回 git_failed"
        mock_sleep.assert_called_once_with(1)

    def test_no_retry_when_stderr_not_index_lock(self):
        """commit git_failed 但 stderr 不含 index.lock → 不重試，直接 git_failed。"""
        only = MagicMock(returncode=1, stderr="fatal: some other git error")

        fake_run_git = _make_run_git([only])

        with patch.object(git_utils, "_run_git", side_effect=fake_run_git), \
                patch.object(git_utils.time, "sleep") as mock_sleep:
            status = git_utils._auto_commit_ticket_md("/tmp/x.md", "1.0.0-W0-T", "Solution")

        assert status == "git_failed", "非 index.lock 失敗應直接回 git_failed"
        mock_sleep.assert_not_called()

    def test_no_retry_on_first_commit_success(self):
        """commit 首次成功 → 不 sleep、不重試，回 committed。"""
        only = MagicMock(returncode=0, stderr="")

        fake_run_git = _make_run_git([only])

        with patch.object(git_utils, "_run_git", side_effect=fake_run_git), \
                patch.object(git_utils.time, "sleep") as mock_sleep:
            status = git_utils._auto_commit_ticket_md("/tmp/x.md", "1.0.0-W0-T", "Solution")

        assert status == "committed"
        mock_sleep.assert_not_called()
