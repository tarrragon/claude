"""git_ops.commit_files_isolated 測試套件。

驗證隔離提交完整性要件：GIT_INDEX_FILE 隔離、範圍自我驗證、空 tree 短路、
CAS update-ref 失敗不覆蓋、index.lock 重試。

TestRunGitTimeout：迴歸釘子搬遷。承接 1.0.0-W7-003 ANA 結論（TD-2 採納，
原測項位於 test_git_subprocess_timeout.py，對象為已移除的
git_utils._run_git）——git 命令原無 timeout 時，git hang（等認證 /
index.lock）會無限等待。git_utils._auto_commit_ticket_md 改委派
git_ops.commit_files_isolated 後，git 呼叫的 timeout 保證改由本模組的
_run_git 負責，原測項隨之搬遷至此，測試對象改為 git_ops._run_git。

TestAutoCommitCompletionFilesWorktreeCwd：0.2.1-W4-026 迴歸。lifecycle.
_auto_commit_completion_files 呼叫 commit_files_isolated 未傳 cwd 時，git
以呼叫端 process cwd（而非票面 md 實際所在的 repo）解析 --show-toplevel；
代理人在 linked worktree 內執行 `ticket track complete` 時，票面 md 已由
get_ticket_state_root() 統一落在主倉庫，git 卻以 worktree 為 repo，對主
倉庫路徑執行 `git add` 得到 `fatal: ... is outside repository`。本類別以
真實 tmp 主倉庫 + `git worktree add` 建立的 linked worktree 重現：process
cwd 切至 worktree 後呼叫 `_auto_commit_completion_files`（傳入路徑為主
倉庫內的票面 md），驗證修復後提交確實落在主倉庫 HEAD。
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ticket_system.lib import git_ops

_TARGET = "docs/work-logs/v1/tickets/a.md"
_REPO_ROOT = os.getcwd()


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False,
    )


def _fake_run_factory(calls, extra_changed=None, same_tree=False, repo_root=None):
    """建立模擬 git plumbing 各步驟輸出的 fake subprocess.run。"""
    extra_changed = extra_changed or []
    repo_root = repo_root or _REPO_ROOT

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[:2] == ["git", "rev-parse"] and len(args) > 2 and args[2] == "--show-toplevel":
            return MagicMock(returncode=0, stdout=f"{repo_root}\n", stderr="")
        if args[:2] == ["git", "rev-parse"] and args[2] == "HEAD":
            return MagicMock(returncode=0, stdout="old_head_sha\n", stderr="")
        if args[:2] == ["git", "rev-parse"] and args[2].endswith("^{tree}"):
            tree = "tree_sha\n" if same_tree else "old_tree_sha\n"
            return MagicMock(returncode=0, stdout=tree, stderr="")
        if args[:2] == ["git", "read-tree"]:
            return MagicMock(returncode=0, stdout="", stderr="")
        if args[:2] == ["git", "add"]:
            return MagicMock(returncode=0, stdout="", stderr="")
        if args[:2] == ["git", "write-tree"]:
            return MagicMock(returncode=0, stdout="tree_sha\n", stderr="")
        if args[:2] == ["git", "commit-tree"]:
            return MagicMock(returncode=0, stdout="new_commit_sha\n", stderr="")
        if args[:2] == ["git", "diff"]:
            changed = [_TARGET] + extra_changed
            return MagicMock(returncode=0, stdout="\n".join(changed) + "\n", stderr="")
        if args[:2] == ["git", "update-ref"]:
            return MagicMock(returncode=0, stdout="", stderr="")
        if args[:2] == ["git", "ls-tree"]:
            idx = args.index("--")
            requested = args[idx + 1 :]
            lines = [f"100644 blob fakeblobsha\t{p}" for p in requested]
            return MagicMock(
                returncode=0, stdout=("\n".join(lines) + "\n" if lines else ""), stderr=""
            )
        if args[:2] == ["git", "update-index"]:
            return MagicMock(returncode=0, stdout="", stderr="")
        raise AssertionError(f"未預期的 git 呼叫: {args}")

    return fake_run


class TestCommitFilesIsolated:
    def test_empty_paths_short_circuits(self):
        result = git_ops.commit_files_isolated([], "msg")
        assert result == {"status": "empty", "commit_sha": None, "error": None}

    def test_committed_returns_sha(self):
        calls = []
        with patch.object(
            git_ops.subprocess, "run", side_effect=_fake_run_factory(calls)
        ):
            result = git_ops.commit_files_isolated([_TARGET], "msg")
        assert result["status"] == "committed"
        assert result["commit_sha"] == "new_commit_sha"
        assert result["error"] is None

    def test_add_scope_limited_to_given_paths(self):
        """git add 呼叫的參數僅含指定路徑，無 -A。"""
        calls = []
        with patch.object(
            git_ops.subprocess, "run", side_effect=_fake_run_factory(calls)
        ):
            git_ops.commit_files_isolated([_TARGET], "msg")
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 1
        assert add_calls[0] == ["git", "add", "--", _TARGET]
        assert "-A" not in add_calls[0]

    def test_never_invokes_bare_commit(self):
        """提交路徑不經過 `git commit`（改用 plumbing）。"""
        calls = []
        with patch.object(
            git_ops.subprocess, "run", side_effect=_fake_run_factory(calls)
        ):
            git_ops.commit_files_isolated([_TARGET], "msg")
        assert all(c[:2] != ["git", "commit"] for c in calls)
        assert any(c[:2] == ["git", "commit-tree"] for c in calls)
        assert any(c[:2] == ["git", "update-ref"] for c in calls)

    def test_uses_isolated_index_env(self):
        """read-tree/add/write-tree 呼叫時 env 帶 GIT_INDEX_FILE，且與
        呼叫端行程環境不同（隔離臨時檔）。"""
        seen_envs = []

        def fake_run(args, **kwargs):
            if args[:2] in (["git", "read-tree"], ["git", "add"], ["git", "write-tree"]):
                seen_envs.append(kwargs.get("env"))
            return _fake_run_factory([])(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            git_ops.commit_files_isolated([_TARGET], "msg")
        assert seen_envs, "isolated-index 步驟未被呼叫"
        assert all(env is not None and "GIT_INDEX_FILE" in env for env in seen_envs)

    def test_empty_tree_short_circuits_no_commit(self):
        """write-tree 產出的 tree 與 HEAD 現有 tree 相同時，短路不提交。"""
        calls = []
        with patch.object(
            git_ops.subprocess,
            "run",
            side_effect=_fake_run_factory(calls, same_tree=True),
        ):
            result = git_ops.commit_files_isolated([_TARGET], "msg")
        assert result == {"status": "empty", "commit_sha": None, "error": None}
        assert all(c[:2] != ["git", "commit-tree"] for c in calls)

    def test_scope_self_check_rejects_unexpected_extra_file(self):
        """提交後 diff 範圍含指定範圍以外的檔案時放棄，不 update-ref。"""
        calls = []
        with patch.object(
            git_ops.subprocess,
            "run",
            side_effect=_fake_run_factory(calls, extra_changed=["lib/main.dart"]),
        ):
            result = git_ops.commit_files_isolated([_TARGET], "msg")
        assert result["status"] == "failed"
        assert "提交範圍自我驗證失敗" in result["error"]
        assert all(c[:2] != ["git", "update-ref"] for c in calls)

    def test_update_ref_cas_failure_returns_failed(self):
        """update-ref 帶舊值失敗（HEAD 於期間被並行移動）時回傳 failed，不覆蓋。"""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["git", "update-ref"]:
                return MagicMock(returncode=1, stdout="", stderr="fatal: HEAD 已改變")
            return _fake_run_factory([])(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            result = git_ops.commit_files_isolated([_TARGET], "msg")
        assert result["status"] == "failed"

    def test_add_failure_aborts(self):
        def fake_run(args, **kwargs):
            if args[:2] == ["git", "rev-parse"] and args[2] == "--show-toplevel":
                return MagicMock(returncode=0, stdout=f"{_REPO_ROOT}\n", stderr="")
            if args[:2] == ["git", "rev-parse"] and args[2] == "HEAD":
                return MagicMock(returncode=0, stdout="old_head_sha\n", stderr="")
            if args[:2] == ["git", "read-tree"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "add"]:
                return MagicMock(returncode=1, stdout="", stderr="add failed")
            raise AssertionError(f"未預期的 git 呼叫: {args}")

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            result = git_ops.commit_files_isolated([_TARGET], "msg")
        assert result["status"] == "failed"
        assert result["error"] == "add failed"

    def test_index_lock_retries_once(self):
        """rev-parse HEAD 遇 index.lock 時重試一次後成功。"""
        attempts = {"rev_parse_head": 0}

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "rev-parse"] and args[2] == "HEAD":
                attempts["rev_parse_head"] += 1
                if attempts["rev_parse_head"] == 1:
                    return MagicMock(returncode=1, stdout="", stderr="fatal: index.lock")
                return MagicMock(returncode=0, stdout="old_head_sha\n", stderr="")
            return _fake_run_factory([])(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run), patch.object(
            git_ops.time, "sleep", return_value=None
        ):
            result = git_ops.commit_files_isolated([_TARGET], "msg")
        assert result["status"] == "committed"
        assert attempts["rev_parse_head"] == 2

    def test_dedupes_paths_preserving_order(self):
        calls = []
        with patch.object(
            git_ops.subprocess, "run", side_effect=_fake_run_factory(calls)
        ):
            git_ops.commit_files_isolated([_TARGET, _TARGET], "msg")
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert add_calls[0] == ["git", "add", "--", _TARGET]

    def test_syncs_shared_index_after_successful_commit(self):
        """update-ref 成功後，以新 HEAD tree 同步共用 index（無 GIT_INDEX_FILE env）。"""
        calls = []
        envs = {}

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["git", "ls-tree"] or args[:2] == ["git", "update-index"]:
                envs[tuple(args)] = kwargs.get("env")
            return _fake_run_factory([])(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            result = git_ops.commit_files_isolated([_TARGET], "msg")

        assert result["status"] == "committed"
        ls_tree_calls = [c for c in calls if c[:2] == ["git", "ls-tree"]]
        assert ls_tree_calls == [["git", "ls-tree", "tree_sha", "--", _TARGET]]
        index_info_calls = [
            c for c in calls if c[:2] == ["git", "update-index"] and "--index-info" in c
        ]
        assert index_info_calls == [["git", "update-index", "--index-info"]]
        # 共用 index 同步呼叫不帶 GIT_INDEX_FILE（env=None，行程預設環境）
        assert all(env is None for env in envs.values())

    def test_sync_failure_does_not_change_commit_result(self):
        """共用 index 同步失敗只 WARNING，commit 結果仍回報 committed。"""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["git", "ls-tree"]:
                return MagicMock(returncode=1, stdout="", stderr="ls-tree failed")
            return _fake_run_factory([])(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            result = git_ops.commit_files_isolated([_TARGET], "msg")

        assert result["status"] == "committed"
        assert result["commit_sha"] == "new_commit_sha"
        assert all(c[:2] != ["git", "update-index"] for c in calls)

    def test_error_branches_never_touch_shared_index(self):
        """例外分支（add 失敗）於同步呼叫之前即回傳，共用 index 完全不被觸碰。"""

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "rev-parse"] and args[2] == "--show-toplevel":
                return MagicMock(returncode=0, stdout=f"{_REPO_ROOT}\n", stderr="")
            if args[:2] == ["git", "rev-parse"] and args[2] == "HEAD":
                return MagicMock(returncode=0, stdout="old_head_sha\n", stderr="")
            if args[:2] == ["git", "read-tree"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "add"]:
                return MagicMock(returncode=1, stdout="", stderr="add failed")
            raise AssertionError(f"未預期的 git 呼叫: {args}")

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            result = git_ops.commit_files_isolated([_TARGET], "msg")
        assert result["status"] == "failed"
        # fake_run 對 ls-tree/update-index 會 raise AssertionError，
        # 測試通過即代表這些呼叫從未發生（共用 index 未被觸碰）。

    def test_sync_force_removes_paths_missing_from_new_tree(self):
        """新 HEAD tree 中不存在的 path（如已刪除）以 --force-remove 同步。"""
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["git", "ls-tree"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return _fake_run_factory([])(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            result = git_ops.commit_files_isolated([_TARGET], "msg")

        assert result["status"] == "committed"
        force_remove_calls = [
            c for c in calls if c[:2] == ["git", "update-index"] and "--force-remove" in c
        ]
        assert force_remove_calls == [
            ["git", "update-index", "--force-remove", "--", _TARGET]
        ]

    def test_absolute_path_input_commits_successfully(self):
        """絕對路徑輸入須正規化為 repo-relative 後成功提交（0.2.1-W3-920 回歸）。

        修正前：呼叫端（lifecycle.complete()）傳入絕對路徑，但 git diff
        --name-only 回傳 repo-relative 路徑，範圍自我驗證恆判定不符，
        commit 恆為 failed。
        """
        abs_target = os.path.join(_REPO_ROOT, _TARGET)
        calls = []
        with patch.object(
            git_ops.subprocess, "run", side_effect=_fake_run_factory(calls)
        ):
            result = git_ops.commit_files_isolated([abs_target], "msg")
        assert result["status"] == "committed"
        assert result["error"] is None
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert add_calls[0] == ["git", "add", "--", _TARGET]


class TestRunGitTimeout:
    """迴歸釘子：git 命令原無 timeout 時，git hang（等認證 / index.lock）
    會無限等待（見本檔頭 module docstring 搬遷說明）。"""

    def test_run_git_passes_default_timeout_to_subprocess(self):
        with patch.object(git_ops.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            git_ops._run_git(["git", "rev-parse", "HEAD"])
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == git_ops._GIT_TIMEOUT

    def test_run_git_accepts_custom_timeout(self):
        with patch.object(git_ops.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            git_ops._run_git(["git", "commit-tree", "abc"], timeout=30)
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 30


class TestAutoCommitCompletionFilesWorktreeCwd:
    """0.2.1-W4-026：linked worktree cwd 下 complete 自動提交的真實 git 整合測試
    （見本檔頭 module docstring）。"""

    @pytest.fixture
    def main_repo_with_worktree(self, tmp_path: Path):
        """建立主倉庫（含已 commit 的票面 md）+ linked worktree，回傳
        (main_repo, worktree_dir, md_path)。md_path 恆位於主倉庫內，模擬
        get_ticket_state_root() 統一落地行為。"""
        main_repo = tmp_path / "main"
        main_repo.mkdir()
        _run_git(main_repo, "init")
        _run_git(main_repo, "config", "user.email", "test@test.com")
        _run_git(main_repo, "config", "user.name", "test")

        tickets_dir = main_repo / "tickets"
        tickets_dir.mkdir()
        md_path = tickets_dir / "0.0.0-W0-WT026.md"
        md_path.write_text("placeholder\n", encoding="utf-8")
        _run_git(main_repo, "add", "tickets/0.0.0-W0-WT026.md")
        _run_git(main_repo, "commit", "-m", "create ticket (placeholder)")

        worktree_dir = tmp_path / "worktree"
        result = _run_git(
            main_repo, "worktree", "add", "-b", "feat/w4-026-test", str(worktree_dir)
        )
        assert result.returncode == 0, f"worktree add 失敗: {result.stderr}"

        return main_repo, worktree_dir, md_path

    def test_committed_in_worktree_cwd_lands_on_main_repo_head(
        self, main_repo_with_worktree, monkeypatch
    ):
        """process cwd 為 linked worktree、傳入路徑為主倉庫票面 md 時，
        commit 仍須成功並落在主倉庫 HEAD（修復前：outside repository 失敗）。"""
        main_repo, worktree_dir, md_path = main_repo_with_worktree
        md_path.write_text("updated body\n", encoding="utf-8")

        main_head_before = _run_git(main_repo, "rev-parse", "HEAD").stdout.strip()
        worktree_head_before = _run_git(worktree_dir, "rev-parse", "HEAD").stdout.strip()
        assert main_head_before == worktree_head_before  # 建立當下同一 commit

        from ticket_system.commands import lifecycle

        monkeypatch.chdir(worktree_dir)
        lifecycle._auto_commit_completion_files(
            "0.0.0-W0-WT026", [str(md_path)]
        )

        main_head_after = _run_git(main_repo, "rev-parse", "HEAD").stdout.strip()
        assert main_head_after != main_head_before, (
            "隔離提交應在主倉庫（票面 md 實際所在的 repo）產生新 commit；"
            "未傳 cwd 時 git 以 process cwd（worktree）解析 repo 導致提交失敗"
        )

        worktree_head_after = _run_git(worktree_dir, "rev-parse", "HEAD").stdout.strip()
        assert worktree_head_after == worktree_head_before, (
            "worktree 自身分支的 HEAD 不應被此次提交推進——提交對象是主倉庫"
        )

        msg = _run_git(main_repo, "log", "-1", "--pretty=%s").stdout.strip()
        assert "0.0.0-W0-WT026" in msg

    def test_main_repo_cwd_scenario_unchanged(
        self, main_repo_with_worktree, monkeypatch
    ):
        """主倉庫 cwd 場景行為不變：process cwd 即主倉庫時提交仍成功
        （AC2 迴歸釘子，防止本票修復破壞既有非 worktree 路徑）。"""
        main_repo, _worktree_dir, md_path = main_repo_with_worktree
        md_path.write_text("updated body from main repo cwd\n", encoding="utf-8")

        main_head_before = _run_git(main_repo, "rev-parse", "HEAD").stdout.strip()

        from ticket_system.commands import lifecycle

        monkeypatch.chdir(main_repo)
        lifecycle._auto_commit_completion_files(
            "0.0.0-W0-WT026", [str(md_path)]
        )

        main_head_after = _run_git(main_repo, "rev-parse", "HEAD").stdout.strip()
        assert main_head_after != main_head_before
