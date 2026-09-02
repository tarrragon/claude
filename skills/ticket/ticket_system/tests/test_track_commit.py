"""ticket track commit 子命令測試套件。

驗證：
1. 命令可在 where.files 子集內提交並印出 SHA。
2. 超出宣告範圍的檔案被拒絕（不部分提交）。
3. where.files 未宣告任何寫入路徑時拒絕提交。
4. ticket 不存在時回傳錯誤。
5. 空 tree 短路視為成功（無需提交）。
6. 提交失敗時印出錯誤並回傳非零。
7. 目錄型 where.files 宣告：傳個別檔名可成功提交（0.2.1-W3-1090）。
8. 目錄型 where.files 宣告：傳目錄本身會展開為實際變更檔案後提交，
   commit_files_isolated 恆收到具體檔案清單而非目錄字面值（0.2.1-W3-1090）。
9. --worktree 未指定時沿用 resolve_project_cwd()（既有行為不變）。
10. --worktree 指定且為合法 git 目錄時，repo root 改以該目錄為準
    （0.2.1-W4-017）。
11. --worktree 指定但非合法 git 目錄時拒絕提交並印出錯誤（0.2.1-W4-017）。
12. linked worktree 端到端場景：新檔可 add、已修改檔不再誤判空 tree，
    commit 落在 worktree 分支，主 repo 共用 index 未被觸碰
    （0.2.1-W4-017）。
"""
import argparse
import subprocess
from unittest.mock import patch

import pytest

from ticket_system.commands import track_commit


_TICKET_ID = "0.2.1-W3-999"
_VERSION = "0.2.1"


def _ticket(files):
    return {"id": _TICKET_ID, "type": "IMP", "where": {"files": files}}


def _args(files, message="test commit", worktree=None):
    return argparse.Namespace(
        ticket_id=_TICKET_ID, message=message, files=files, worktree=worktree
    )


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


class TestDirectoryDeclarationScope:
    """0.2.1-W3-1090：目錄型 where.files 宣告下，個別檔名與目錄本身兩種
    呼叫形式皆可成功提交；commit_files_isolated 恆收到具體檔案清單。"""

    def test_individual_file_under_declared_directory_accepted(self, capsys):
        """宣告 `a/dir`（目錄），傳入其下個別檔名應通過範圍檢查並提交。"""
        declared = ["a/dir"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch("os.path.isdir", return_value=False), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "committed", "commit_sha": "aaa111", "error": None},
             ) as mock_commit:
            rc = track_commit.execute_commit(_args(["a/dir/file.py"]), _VERSION)

        assert rc == 0
        mock_commit.assert_called_once()
        called_paths, _ = mock_commit.call_args[0]
        assert called_paths == ["a/dir/file.py"]

    def test_directory_itself_expands_to_concrete_changed_files(self, capsys):
        """宣告 `a/dir`（目錄），傳入目錄本身應展開為 git 回報的實際變更
        檔案後才交給 commit_files_isolated——後者恆收到具體檔案清單，不
        收到目錄字面值，故自我驗證不因目錄展開而誤判。"""
        declared = ["a/dir"]
        status_output = " M a/dir/file1.py\n?? a/dir/file2.py\n"
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch("os.path.isdir", return_value=True), \
             patch.object(track_commit, "_git_status_porcelain", return_value=status_output), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "committed", "commit_sha": "bbb222", "error": None},
             ) as mock_commit:
            rc = track_commit.execute_commit(_args(["a/dir"]), _VERSION)

        assert rc == 0
        mock_commit.assert_called_once()
        called_paths, _ = mock_commit.call_args[0]
        assert set(called_paths) == {"a/dir/file1.py", "a/dir/file2.py"}
        for p in called_paths:
            assert "a/dir" != p  # 恆為具體檔案，非目錄字面值

    def test_directory_with_no_changed_files_rejected(self, capsys):
        """宣告的目錄下 git status 無任何變更檔案時，無可提交內容，拒絕
        （不將目錄字面值傳給 commit_files_isolated）。"""
        declared = ["a/dir"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "resolve_project_cwd", return_value="/repo"), \
             patch("os.getcwd", return_value="/repo"), \
             patch("os.path.isdir", return_value=True), \
             patch.object(track_commit, "_git_status_porcelain", return_value=""), \
             patch.object(track_commit, "commit_files_isolated") as mock_commit:
            rc = track_commit.execute_commit(_args(["a/dir"]), _VERSION)

        assert rc == 1
        mock_commit.assert_not_called()


class TestResolveRepoRoot:
    """_resolve_repo_root：--worktree 未指定沿用既有行為；指定時改綁定
    該路徑對應的 git repo root（0.2.1-W4-017）。"""

    def test_no_worktree_falls_back_to_resolve_project_cwd(self):
        with patch.object(track_commit, "resolve_project_cwd", return_value="/repo"):
            result = track_commit._resolve_repo_root(None)

        assert result == "/repo"

    def test_worktree_given_uses_its_own_toplevel(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="/worktrees/wt1\n", stderr=""
        )
        with patch.object(track_commit.subprocess, "run", return_value=completed) as mock_run:
            result = track_commit._resolve_repo_root("/worktrees/wt1")

        assert result == "/worktrees/wt1"
        called_kwargs = mock_run.call_args.kwargs
        assert called_kwargs["cwd"] == "/worktrees/wt1"

    def test_worktree_not_a_git_dir_returns_none(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="not a git repository"
        )
        with patch.object(track_commit.subprocess, "run", return_value=completed):
            result = track_commit._resolve_repo_root("/not/a/repo")

        assert result is None


class TestExecuteCommitWorktreeOption:
    """execute_commit 對 --worktree 引數的處理（0.2.1-W4-017）。"""

    def test_worktree_option_forwarded_to_commit_files_isolated_cwd(self, capsys):
        declared = ["a/b.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(
                 track_commit, "_resolve_repo_root", return_value="/worktrees/wt1"
             ) as mock_resolve, \
             patch("os.getcwd", return_value="/repo"), \
             patch.object(
                 track_commit,
                 "commit_files_isolated",
                 return_value={"status": "committed", "commit_sha": "wt123", "error": None},
             ) as mock_commit:
            rc = track_commit.execute_commit(
                _args(["a/b.py"], worktree="/worktrees/wt1"), _VERSION
            )

        assert rc == 0
        mock_resolve.assert_called_once_with("/worktrees/wt1")
        assert mock_commit.call_args.kwargs["cwd"] == "/worktrees/wt1"

    def test_invalid_worktree_rejected_before_commit(self, capsys):
        declared = ["a/b.py"]
        with patch.object(track_commit, "load_ticket", return_value=_ticket(declared)), \
             patch.object(track_commit, "_resolve_repo_root", return_value=None), \
             patch.object(track_commit, "commit_files_isolated") as mock_commit:
            rc = track_commit.execute_commit(
                _args(["a/b.py"], worktree="/not/a/repo"), _VERSION
            )

        assert rc == 1
        mock_commit.assert_not_called()
        out = capsys.readouterr().out
        assert "/not/a/repo" in out


class TestLinkedWorktreeEndToEnd:
    """真實 tmp repo + git worktree add 場景：新檔可 add、已修改檔不再
    誤判空 tree，commit 落在 worktree 分支，主 repo 共用 index 未被觸碰
    （0.2.1-W4-017 acceptance 1）。"""

    @pytest.fixture
    def repo_and_worktree(self, tmp_path):
        main_repo = tmp_path / "main"
        main_repo.mkdir()
        _git(main_repo, "init", "-q", "-b", "main")
        _git(main_repo, "config", "user.email", "test@example.com")
        _git(main_repo, "config", "user.name", "Test")

        tracked = main_repo / "tracked.py"
        tracked.write_text("original content\n")
        _git(main_repo, "add", "tracked.py")
        _git(main_repo, "commit", "-q", "-m", "init")

        worktree_dir = tmp_path / "wt1"
        _git(main_repo, "worktree", "add", "-q", "-b", "feat/wt1", str(worktree_dir))

        return main_repo, worktree_dir

    def _ticket_declaring(self, files):
        return {"id": _TICKET_ID, "type": "IMP", "where": {"files": files}}

    def test_new_file_in_worktree_committed_to_worktree_branch(self, repo_and_worktree):
        main_repo, worktree_dir = repo_and_worktree
        new_file = worktree_dir / "new_file.py"
        new_file.write_text("new content\n")

        declared = ["tracked.py", "new_file.py"]
        with patch.object(
            track_commit, "load_ticket", return_value=self._ticket_declaring(declared)
        ):
            args = _args(
                ["new_file.py"], message="add new file", worktree=str(worktree_dir)
            )
            rc = track_commit.execute_commit(args, _VERSION)

        assert rc == 0
        # commit 落在 worktree 分支，非主 repo 分支
        wt_log = _git(worktree_dir, "log", "--oneline", "-1").stdout
        assert "add new file" in wt_log
        # 主 repo working tree / index 未被觸碰：檔案不存在於主 repo
        assert not (main_repo / "new_file.py").exists()
        main_status = _git(main_repo, "status", "--porcelain").stdout
        assert main_status.strip() == ""

    def test_modified_file_in_worktree_not_falsely_empty(self, repo_and_worktree):
        main_repo, worktree_dir = repo_and_worktree
        tracked_in_wt = worktree_dir / "tracked.py"
        tracked_in_wt.write_text("original content\nmodified line\n")

        declared = ["tracked.py"]
        with patch.object(
            track_commit, "load_ticket", return_value=self._ticket_declaring(declared)
        ):
            args = _args(
                ["tracked.py"], message="modify tracked file", worktree=str(worktree_dir)
            )
            rc = track_commit.execute_commit(args, _VERSION)

        assert rc == 0
        wt_log = _git(worktree_dir, "log", "--oneline", "-1").stdout
        assert "modify tracked file" in wt_log
        # 主 repo working tree 內容維持原樣，未被誤判為已提交或被覆寫
        assert (main_repo / "tracked.py").read_text() == "original content\n"
        main_status = _git(main_repo, "status", "--porcelain").stdout
        assert main_status.strip() == ""


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )
