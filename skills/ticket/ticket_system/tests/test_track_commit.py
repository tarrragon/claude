"""ticket track commit 子命令測試套件。

驗證：
1. 命令可在 where.files 子集內提交並印出 SHA。
2. 超出宣告範圍的檔案被拒絕（不部分提交）。
3. where.files 未宣告任何寫入路徑時拒絕提交。
4. ticket 不存在時回傳錯誤。
5. 空 tree 短路視為成功（無需提交）。
6. 提交失敗時印出錯誤並回傳非零。
"""
import argparse
from unittest.mock import patch

from ticket_system.commands import track_commit


_TICKET_ID = "0.2.1-W3-999"
_VERSION = "0.2.1"


def _ticket(files):
    return {"id": _TICKET_ID, "type": "IMP", "where": {"files": files}}


def _args(files, message="test commit"):
    return argparse.Namespace(ticket_id=_TICKET_ID, message=message, files=files)


class TestExecuteCommit:
    def test_commits_files_within_declared_scope(self, capsys):
        declared = ["a/b.py", "a/c.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "committed", "commit_sha": "abc123", "error": None},
             ) as mock_commit:
            rc = track_commit.execute_commit(_args(["a/b.py"]), _VERSION)

        assert rc == 0
        mock_commit.assert_called_once()
        called_paths, called_message = mock_commit.call_args[0]
        assert called_paths == ["a/b.py"]
        assert called_message == "test commit"
        out = capsys.readouterr().out
        assert "abc123" in out

    def test_rejects_files_outside_declared_scope(self, capsys):
        declared = ["a/b.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch.object(track_commit, "commit_files_isolated") as mock_commit:
            rc = track_commit.execute_commit(_args(["a/other.py"]), _VERSION)

        assert rc == 1
        mock_commit.assert_not_called()
        err_or_out = capsys.readouterr().out
        assert "a/other.py" in err_or_out

    def test_rejects_partial_subset_when_any_file_out_of_scope(self, capsys):
        """混合宣告內/宣告外檔案時整批拒絕，不部分提交。"""
        declared = ["a/b.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch.object(track_commit, "commit_files_isolated") as mock_commit:
            rc = track_commit.execute_commit(_args(["a/b.py", "a/other.py"]), _VERSION)

        assert rc == 1
        mock_commit.assert_not_called()

    def test_rejects_when_where_files_declares_no_write_paths(self, capsys):
        with patch.object(track_commit, "load_ticket", return_value=_ticket([])), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch.object(track_commit, "commit_files_isolated") as mock_commit:
            rc = track_commit.execute_commit(_args(["a/b.py"]), _VERSION)

        assert rc == 1
        mock_commit.assert_not_called()

    def test_missing_ticket_returns_error(self, capsys):
        with patch.object(track_commit, "load_ticket", return_value=None):
            rc = track_commit.execute_commit(_args(["a/b.py"]), _VERSION)

        assert rc == 1

    def test_empty_status_treated_as_success(self, capsys):
        declared = ["a/b.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "empty", "commit_sha": None, "error": None},
             ):
            rc = track_commit.execute_commit(_args(["a/b.py"]), _VERSION)

        assert rc == 0

    def test_failed_status_prints_error_and_returns_nonzero(self, capsys):
        declared = ["a/b.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "failed", "commit_sha": None, "error": "提交範圍自我驗證失敗"},
             ):
            rc = track_commit.execute_commit(_args(["a/b.py"]), _VERSION)

        assert rc == 1
        out = capsys.readouterr().out
        assert "提交範圍自我驗證失敗" in out


class TestBaseDirIndependentFromCwd:
    """0.2.1-W3-932：base_dir 固定用 repo_root，不受 os.getcwd() 影響
    （ticket shim 以 `uv run --directory <skill_dir>` 呼叫，process 實際
    cwd 會被切到 skill_dir，與呼叫者鍵入指令時所在目錄不同）。
    覆蓋三種輸入形式：repo-root 相對路徑、絕對路徑、shim 式 cwd（不在
    repo 根，模擬 os.getcwd() 被切到 skill_dir 的情況）。
    """

    def test_relative_input_resolved_against_repo_root_not_cwd(self, capsys):
        """輸入為 repo-root 相對路徑，即使 os.getcwd() 被切到別處（模擬
        shim 的 --directory 行為）仍應正確比對到宣告範圍內。"""
        declared = ["a/b.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo/.claude/skills/ticket"), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "committed", "commit_sha": "def456", "error": None},
             ) as mock_commit:
            rc = track_commit.execute_commit(_args(["a/b.py"]), _VERSION)

        assert rc == 0
        mock_commit.assert_called_once()
        called_paths, _ = mock_commit.call_args[0]
        assert called_paths == ["a/b.py"]

    def test_absolute_input_resolved_correctly_regardless_of_cwd(self, capsys):
        """輸入為絕對路徑時，不受 base_dir 選擇影響，仍應正確比對。"""
        declared = ["a/b.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo/.claude/skills/ticket"), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "committed", "commit_sha": "ghi789", "error": None},
             ) as mock_commit:
            rc = track_commit.execute_commit(_args(["/repo/a/b.py"]), _VERSION)

        assert rc == 0
        mock_commit.assert_called_once()
        called_paths, _ = mock_commit.call_args[0]
        assert called_paths == ["a/b.py"]

    def test_shim_style_cwd_outside_repo_root_still_matches_declared_scope(self, capsys):
        """重現 PM 的實際回報場景：shim 的 os.getcwd() 落在 skill_dir
        （repo 根下的子目錄，但非 repo 根本身），輸入為 repo-root 相對
        路徑時應成功比對，不再誤判越界。"""
        declared = [
            ".claude/skills/ticket/ticket_system/tools/dispatch_prompt_baseline.py"
        ]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo/.claude/skills/ticket"), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "committed", "commit_sha": "jkl012", "error": None},
             ) as mock_commit:
            rc = track_commit.execute_commit(
                _args(
                    [
                        ".claude/skills/ticket/ticket_system/tools/"
                        "dispatch_prompt_baseline.py"
                    ]
                ),
                _VERSION,
            )

        assert rc == 0
        mock_commit.assert_called_once()
