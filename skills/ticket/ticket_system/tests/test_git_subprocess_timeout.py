"""W7-003.1 — git subprocess timeout 補強測試。

承接 1.0.0-W7-003 ANA 結論（TD-2 採納）：``git_utils._run_git`` 與
``lifecycle._auto_stage_git_add`` 原無 timeout，git hang（等認證 / index.lock）
會無限等待。本檔驗證兩處皆已帶 timeout，並對齊另兩處（track_snapshot=5s）。

驗證面向：
1. ``git_utils._run_git`` 簽名含 timeout 參數，預設 5s（快命令）。
2. ``git_utils._run_git`` 實際傳 timeout 給 subprocess.run。
3. ``git_utils._auto_commit_ticket_md`` 的 commit 步驟用較長 timeout（含 husky）。
4. ``lifecycle._auto_stage_git_add`` 實際傳 timeout 給 subprocess.run。
"""

from __future__ import annotations

import inspect
from unittest.mock import patch, MagicMock

from ticket_system.lib import git_utils
from ticket_system.commands import lifecycle


# ============================================================
# git_utils._run_git timeout
# ============================================================


class TestRunGitTimeout:
    def test_run_git_signature_has_timeout(self):
        """_run_git 簽名含 timeout 參數，預設為快命令 5s。"""
        sig = inspect.signature(git_utils._run_git)
        assert "timeout" in sig.parameters
        assert sig.parameters["timeout"].default == git_utils._FAST_GIT_TIMEOUT
        assert git_utils._FAST_GIT_TIMEOUT == 5

    def test_run_git_passes_timeout_to_subprocess(self):
        """_run_git 預設將 5s timeout 傳給 subprocess.run。"""
        with patch.object(git_utils.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            git_utils._run_git("/tmp", "rev-parse", "--show-toplevel")
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 5

    def test_run_git_accepts_custom_timeout(self):
        """_run_git 可由呼叫端傳入較長 timeout（commit 含 husky）。"""
        with patch.object(git_utils.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            git_utils._run_git("/tmp", "commit", "-m", "x", timeout=30)
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 30

    def test_commit_timeout_constant_longer_than_fast(self):
        """commit timeout 較快命令長（容納 pre-commit husky）。"""
        assert git_utils._COMMIT_GIT_TIMEOUT == 30
        assert git_utils._COMMIT_GIT_TIMEOUT > git_utils._FAST_GIT_TIMEOUT


class TestAutoCommitUsesCommitTimeout:
    def test_commit_step_uses_long_timeout(self):
        """_auto_commit_ticket_md 的 commit 步驟用 _COMMIT_GIT_TIMEOUT。

        透過 patch _run_git，讓 rev-parse / add 成功、diff 回非 0（有變更），
        斷言最後 commit 呼叫帶較長 timeout。
        """
        calls = []

        def fake_run_git(cwd, *args, timeout=git_utils._FAST_GIT_TIMEOUT):
            calls.append((args, timeout))
            # diff --cached --quiet：回 1 表示有變更（觸發 commit）
            rc = 1 if args[:2] == ("diff", "--cached") else 0
            return MagicMock(returncode=rc)

        with patch.object(git_utils, "_run_git", side_effect=fake_run_git):
            status = git_utils._auto_commit_ticket_md(
                "/tmp/x.md", "1.0.0-W0-T", "Solution"
            )

        assert status == "committed"
        commit_calls = [t for a, t in calls if a[0] == "commit"]
        assert commit_calls, "commit step not invoked"
        assert all(t == git_utils._COMMIT_GIT_TIMEOUT for t in commit_calls)


# ============================================================
# lifecycle._auto_stage_git_add timeout
# ============================================================


class TestAutoStageGitAddTimeout:
    def test_auto_stage_passes_timeout_to_subprocess(self):
        """_auto_stage_git_add 將 5s timeout 傳給 subprocess.run。"""
        with patch.object(lifecycle.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            lifecycle._auto_stage_git_add(["foo.md"])
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 5
