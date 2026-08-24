"""git_ops.commit_files_isolated 測試套件。

驗證隔離提交完整性要件：GIT_INDEX_FILE 隔離、範圍自我驗證、空 tree 短路、
CAS update-ref 失敗不覆蓋、index.lock 重試。
"""

import os
from unittest.mock import MagicMock, patch

from ticket_system.lib import git_ops

_TARGET = "docs/work-logs/v1/tickets/a.md"
_REPO_ROOT = os.getcwd()


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
