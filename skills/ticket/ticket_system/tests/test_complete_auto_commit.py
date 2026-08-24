"""lifecycle._auto_commit_completion_files 測試套件。

驗證 complete() 收尾流程改用隔離索引提交（commit_files_isolated）後：
1. 不再留任何 staged 殘留於共用 index（全程不呼叫 `git add` 於共用環境）。
2. 清單來源獨立於共用 index（呼叫端自帶路徑，不讀 --cached）。
3. 失敗時 graceful degrade（stderr 警告 + 不中斷），不留 staged 殘留。
4. 空 tree（工作區與 HEAD 相同）不產生輸出、不視為錯誤。
"""

from unittest.mock import patch

import pytest

from ticket_system.commands import lifecycle

_TICKET_ID = "0.2.1-W3-916"
_PATHS = ["docs/work-logs/v0.2.1/tickets/a.md", "docs/work-logs/v0.2.1/worklog.md"]


class TestAutoCommitCompletionFiles:
    def test_committed_prints_commit_sha(self, capsys):
        with patch.object(
            lifecycle,
            "commit_files_isolated",
            return_value={
                "status": "committed",
                "commit_sha": "abc123def456",
                "error": None,
            },
        ) as mock_commit:
            lifecycle._auto_commit_completion_files(_TICKET_ID, _PATHS)

        mock_commit.assert_called_once()
        called_paths, called_message = mock_commit.call_args[0]
        assert called_paths == _PATHS
        assert _TICKET_ID in called_message

        out = capsys.readouterr().out
        assert "abc123de" in out
        for p in _PATHS:
            assert p in out

    def test_empty_status_produces_no_output(self, capsys):
        with patch.object(
            lifecycle,
            "commit_files_isolated",
            return_value={"status": "empty", "commit_sha": None, "error": None},
        ):
            lifecycle._auto_commit_completion_files(_TICKET_ID, _PATHS)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_failed_status_warns_to_stderr_not_stdout(self, capsys):
        with patch.object(
            lifecycle,
            "commit_files_isolated",
            return_value={
                "status": "failed",
                "commit_sha": None,
                "error": "提交範圍自我驗證失敗",
            },
        ):
            lifecycle._auto_commit_completion_files(_TICKET_ID, _PATHS)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "提交範圍自我驗證失敗" in captured.err

    def test_empty_paths_skips_commit_call(self):
        with patch.object(lifecycle, "commit_files_isolated") as mock_commit:
            lifecycle._auto_commit_completion_files(_TICKET_ID, [])
        mock_commit.assert_not_called()

    def test_exception_degrades_gracefully(self, capsys):
        """commit_files_isolated 拋例外時 graceful degrade，不中斷呼叫端。"""
        with patch.object(
            lifecycle, "commit_files_isolated", side_effect=RuntimeError("boom")
        ):
            lifecycle._auto_commit_completion_files(_TICKET_ID, _PATHS)
        captured = capsys.readouterr()
        assert "boom" in captured.err

    def test_never_calls_git_add_directly(self):
        """不應繞過 commit_files_isolated 直接對共用 index 呼叫 git add
        （即不留 staged 殘留）。"""
        with patch.object(
            lifecycle.subprocess, "run"
        ) as mock_subprocess_run, patch.object(
            lifecycle,
            "commit_files_isolated",
            return_value={"status": "committed", "commit_sha": "sha", "error": None},
        ):
            lifecycle._auto_commit_completion_files(_TICKET_ID, _PATHS)
        mock_subprocess_run.assert_not_called()

    def test_dedupes_paths_before_delegating(self):
        with patch.object(
            lifecycle,
            "commit_files_isolated",
            return_value={"status": "empty", "commit_sha": None, "error": None},
        ) as mock_commit:
            lifecycle._auto_commit_completion_files(
                _TICKET_ID, [_PATHS[0], _PATHS[0], _PATHS[1]]
            )
        called_paths = mock_commit.call_args[0][0]
        assert called_paths == _PATHS


def test_auto_stage_git_add_removed():
    """舊版 `_auto_stage_git_add`（直接對共用 index git add）已移除，
    避免有呼叫端誤用而重新留下 staged 殘留。"""
    assert not hasattr(lifecycle, "_auto_stage_git_add")
    assert not hasattr(lifecycle, "_auto_stage_completion_files")
