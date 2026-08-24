#!/usr/bin/env python3
"""
共用 index 裸操作可觀測性 tripwire 測試

驗證 lib.git_utils.run_git_command 對未帶 GIT_INDEX_FILE 的
read-tree/reset/checkout <commit> -- 操作會記錄 WARNING（executor +
timestamp），對隔離操作（帶 GIT_INDEX_FILE）與非風險操作不觸發。
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.git_utils import (
    run_git_command,
    _is_bare_index_risk_op,
)


class TestIsBareIndexRiskOp(unittest.TestCase):
    """測試風險操作判定邏輯"""

    def test_read_tree_is_risk(self):
        self.assertTrue(_is_bare_index_risk_op(["read-tree", "HEAD"]))

    def test_reset_is_risk(self):
        self.assertTrue(_is_bare_index_risk_op(["reset", "--hard", "HEAD"]))

    def test_checkout_with_dashdash_is_risk(self):
        self.assertTrue(
            _is_bare_index_risk_op(["checkout", "abc123", "--", "file.txt"])
        )

    def test_checkout_branch_switch_is_not_risk(self):
        self.assertFalse(_is_bare_index_risk_op(["checkout", "main"]))

    def test_status_is_not_risk(self):
        self.assertFalse(_is_bare_index_risk_op(["status", "--porcelain"]))

    def test_empty_args_is_not_risk(self):
        self.assertFalse(_is_bare_index_risk_op([]))


class TestRunGitCommandTripwire(unittest.TestCase):
    """測試 run_git_command 對風險操作的日誌行為"""

    def setUp(self):
        # 確保測試不受呼叫環境殘留 GIT_INDEX_FILE 影響
        self._orig_env = os.environ.pop("GIT_INDEX_FILE", None)

    def tearDown(self):
        if self._orig_env is not None:
            os.environ["GIT_INDEX_FILE"] = self._orig_env

    @patch('lib.git_utils._log_bare_index_operation')
    @patch('subprocess.run')
    def test_bare_read_tree_triggers_log(self, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_git_command(["read-tree", "HEAD"])
        mock_log.assert_called_once()
        called_args = mock_log.call_args[0][0]
        self.assertEqual(called_args, ["read-tree", "HEAD"])

    @patch('lib.git_utils._log_bare_index_operation')
    @patch('subprocess.run')
    def test_bare_reset_triggers_log(self, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_git_command(["reset", "--hard", "HEAD"])
        mock_log.assert_called_once()

    @patch('lib.git_utils._log_bare_index_operation')
    @patch('subprocess.run')
    def test_bare_checkout_commit_triggers_log(self, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        run_git_command(["checkout", "abc123", "--", "file.txt"])
        mock_log.assert_called_once()

    @patch('lib.git_utils._log_bare_index_operation')
    @patch('subprocess.run')
    def test_non_risk_command_does_not_trigger_log(self, mock_run, mock_log):
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")
        run_git_command(["branch", "--show-current"])
        mock_log.assert_not_called()

    @patch('lib.git_utils._log_bare_index_operation')
    @patch('subprocess.run')
    def test_isolated_index_does_not_trigger_log(self, mock_run, mock_log):
        """帶 GIT_INDEX_FILE（隔離操作）不應觸發 tripwire"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        os.environ["GIT_INDEX_FILE"] = "/tmp/isolated-index"
        try:
            run_git_command(["read-tree", "HEAD"])
        finally:
            del os.environ["GIT_INDEX_FILE"]
        mock_log.assert_not_called()

    @patch('subprocess.run')
    def test_log_content_includes_executor_and_timestamp(self, mock_run):
        """驗證實際寫入的 log 訊息含 executor 與 timestamp 欄位"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        m = mock_open()
        with patch('lib.git_utils.get_project_root') as mock_root, \
             patch('builtins.open', m), \
             patch('pathlib.Path.mkdir'):
            import tempfile
            mock_root.return_value = Path(tempfile.gettempdir())
            run_git_command(["read-tree", "HEAD"])
            handle = m()
            written = "".join(call.args[0] for call in handle.write.call_args_list)
            self.assertIn("executor=", written)
            self.assertIn("timestamp=", written)
            self.assertIn("cmd=read-tree HEAD", written)


if __name__ == "__main__":
    unittest.main()
