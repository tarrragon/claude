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
import threading
import time
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


class TestRefLockRetryAndStaleDiagnosis:
    """0.1.0-W3-271：ref 鎖重試條件與鎖齡判讀。

    原缺陷兩段：(1) ``_run_git_with_lock_retry`` 只比對 ``index.lock`` 子字串，
    對 update-ref 撞鎖的錯誤文字（``cannot lock ref 'HEAD'`` +
    ``refs/heads/main.lock`` / ``HEAD.lock``）恆為 False，撞鎖瞬間即失敗且
    commit-tree SHA 遺失；(2) 修好重試後工具仍無鎖齡判讀，會對不會自行消失的
    崩潰殘骸無限重試。殘骸與活鎖的錯誤輸出完全同形，唯一可程式化的區別是鎖齡，
    故本類別的關鍵測項以持久殘骸鎖為輸入（``test_persistent_stale_lock_*``）
    ——只斷言「正常情況重試會成功」的測項在鎖齡判讀完全失效時照樣全綠。
    """

    _MAIN_LOCK_ERR = (
        "error: cannot lock ref 'HEAD': Unable to create "
        "'/repo/.git/refs/heads/main.lock': File exists."
    )
    _HEAD_LOCK_ERR = "fatal: Unable to create '/repo/.git/HEAD.lock': File exists."

    @pytest.mark.parametrize(
        "lock_err",
        [_MAIN_LOCK_ERR, _HEAD_LOCK_ERR],
        ids=["refs-heads-lock", "head-lock"],
    )
    def test_ref_lock_error_triggers_retry(self, lock_err):
        """AC1：refs/heads/*.lock 與 HEAD.lock 兩種錯誤文字皆觸發重試。"""
        attempts = {"update_ref": 0}

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "update-ref"]:
                attempts["update_ref"] += 1
                if attempts["update_ref"] == 1:
                    return MagicMock(returncode=1, stdout="", stderr=lock_err)
                return MagicMock(returncode=0, stdout="", stderr="")
            return _fake_run_factory([])(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run), patch.object(
            git_ops.time, "sleep", return_value=None
        ):
            result = git_ops.commit_files_isolated([_TARGET], "msg")

        assert attempts["update_ref"] == 2, "ref 鎖錯誤未觸發重試（重試條件恆為 False）"
        assert result["status"] == "committed"

    def test_update_ref_failure_error_contains_commit_sha_and_residue_verdict(self):
        """AC2 + AC5：update-ref 最終失敗時錯誤含 commit-tree SHA 與鎖殘骸歸屬。"""

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "update-ref"]:
                return MagicMock(returncode=1, stdout="", stderr="fatal: HEAD 已改變")
            return _fake_run_factory([])(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            result = git_ops.commit_files_isolated([_TARGET], "msg")

        assert result["status"] == "failed"
        assert "new_commit_sha" in result["error"], "錯誤未帶已建立的 commit-tree SHA"
        assert "鎖殘骸" in result["error"], "錯誤未指出本次是否留下鎖殘骸"

    def test_update_ref_reports_residue_lock_created_by_this_call(self, tmp_path):
        """AC5：呼叫前不存在、失敗後存在的鎖判為本次留下，責任歸屬本執行者。"""
        git_dir = tmp_path / ".git"
        (git_dir / "refs" / "heads").mkdir(parents=True)
        residue = git_dir / "refs" / "heads" / "main.lock"

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "rev-parse"] and args[2] == "--show-toplevel":
                return MagicMock(returncode=0, stdout=f"{tmp_path}\n", stderr="")
            if args[:2] == ["git", "update-ref"]:
                residue.write_bytes(b"a" * 41)  # 模擬 CAS 中途崩潰留下的半成品
                return MagicMock(returncode=1, stdout="", stderr="fatal: 中斷")
            return _fake_run_factory([], repo_root=str(tmp_path))(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run):
            result = git_ops.commit_files_isolated([str(tmp_path / _TARGET)], "msg")

        assert result["status"] == "failed"
        assert "留下鎖殘骸" in result["error"]
        assert str(residue) in result["error"]
        assert "41 bytes" in result["error"], "殘骸診斷未含大小，無從溯源"

    def test_persistent_stale_lock_stops_retrying_with_diagnosis(self, tmp_path):
        """AC4 + AC6（已知該紅的輸入）：以持久殘骸鎖為輸入，工具須在有限次重試後
        放棄並輸出殘骸診斷（mtime／大小／內容），而非持續重試。

        鎖檔 mtime 推回遠早於閾值且全程不移除，模擬不會自行消失的崩潰殘骸。
        鎖齡判讀失效時本測項紅在 update_ref 次數上（工具持續重試），診斷失效時
        紅在 mtime／大小／內容三項斷言上。
        """
        git_dir = tmp_path / ".git"
        (git_dir / "refs" / "heads").mkdir(parents=True)
        stale_lock = git_dir / "refs" / "heads" / "main.lock"
        stale_lock.write_text("ref: crashed-cas-payload\n", encoding="utf-8")
        stale_mtime = time.time() - 3600
        os.utime(stale_lock, (stale_mtime, stale_mtime))

        lock_err = (
            f"error: cannot lock ref 'HEAD': Unable to create '{stale_lock}': File exists."
        )
        attempts = {"update_ref": 0}

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "rev-parse"] and args[2] == "--show-toplevel":
                return MagicMock(returncode=0, stdout=f"{tmp_path}\n", stderr="")
            if args[:2] == ["git", "update-ref"]:
                attempts["update_ref"] += 1
                return MagicMock(returncode=1, stdout="", stderr=lock_err)
            return _fake_run_factory([], repo_root=str(tmp_path))(args, **kwargs)

        with patch.object(git_ops.subprocess, "run", side_effect=fake_run), patch.object(
            git_ops.time, "sleep", return_value=None
        ):
            result = git_ops.commit_files_isolated([str(tmp_path / _TARGET)], "msg")

        assert attempts["update_ref"] == 1, (
            f"殘骸鎖不會自行消失，工具須立即放棄而非重試（實得 {attempts['update_ref']} 次）"
        )
        assert result["status"] == "failed"
        error = result["error"]
        assert "殘骸診斷" in error
        assert str(stale_lock) in error
        assert "mtime" in error and "bytes" in error
        assert "crashed-cas-payload" in error, "診斷未含鎖內容，無法溯源為哪次崩潰的產物"
        assert stale_lock.exists(), "工具不得移除任何鎖，只該停止重試並診斷"

    def test_live_ref_lock_released_by_background_thread_then_succeeds(self, tmp_path):
        """AC3：真實 repo + 背景執行緒持有 refs/heads/<branch>.lock，鎖釋放後
        提交成功（活鎖與殘骸處置相反，本測項釘住活鎖側）。"""
        repo = tmp_path / "repo"
        repo.mkdir()
        _run_git(repo, "init")
        _run_git(repo, "config", "user.email", "test@test.com")
        _run_git(repo, "config", "user.name", "test")
        target = repo / "a.txt"
        target.write_text("v1\n", encoding="utf-8")
        _run_git(repo, "add", "a.txt")
        _run_git(repo, "commit", "-m", "init")

        branch = _run_git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip()
        lock_path = repo / ".git" / "refs" / "heads" / f"{branch}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("held by background thread\n", encoding="utf-8")

        released = threading.Event()

        def release_lock():
            time.sleep(0.3)
            lock_path.unlink()
            released.set()

        holder = threading.Thread(target=release_lock)
        holder.start()
        try:
            target.write_text("v2\n", encoding="utf-8")
            result = git_ops.commit_files_isolated(["a.txt"], "msg", cwd=str(repo))
        finally:
            holder.join()

        assert released.is_set()
        assert result["status"] == "committed", f"活鎖釋放後應重試成功：{result['error']}"
        assert _run_git(repo, "log", "-1", "--pretty=%s").stdout.strip() == "msg"
