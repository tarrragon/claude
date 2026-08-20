"""
worktree-branch-check-hook 測試套件（0.2.1-W3-267.1）

覆蓋範圍：is_main 由分支名推論（branch in ["main", "master"]）改為
worktree list 輸出順序判定（index==0，git 保證主倉庫恆為 --porcelain 首筆）。

回歸測試聚焦兩個已實測失準情境（0.2.1-W3-267 ANA 結論）：
  - 情境 A：主倉庫檢出非 main/master 分支。修正前 is_main=False 誤判非主倉庫，
    致主倉庫的未提交變更被多報為 worktree 變更（多報不漏報，影響低）。
  - 情境 B：linked worktree 檢出 main 分支。修正前 is_main=True 誤判為主倉庫，
    致該 worktree 的未提交變更被靜默忽略（漏報，違反 hook 設計目的，本票修正目標）。
"""

import importlib.util
from pathlib import Path

_HOOK_FILE = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "worktree-branch-check-hook.py"
)
_spec = importlib.util.spec_from_file_location(
    "worktree_branch_check_hook", _HOOK_FILE
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _porcelain(*entries):
    """組合 git worktree list --porcelain 輸出格式。

    Args:
        entries: (path, branch) tuple 列表，依序即為 worktree list 輸出順序。
    """
    blocks = [
        f"worktree {path}\nHEAD abc123\nbranch refs/heads/{branch}"
        for path, branch in entries
    ]
    return "\n\n".join(blocks)


class TestIsMainByOrder:
    """is_main 依 worktree list 輸出順序（index==0）判定，非依分支名推論。"""

    def test_first_entry_is_main_regardless_of_branch(self, monkeypatch):
        # 情境 A：主倉庫（首筆）檢出非 main/master 分支
        output = _porcelain(("/repo/main", "develop"), ("/repo/wt1", "feat/x"))
        monkeypatch.setattr(hook, "run_git_command", lambda args, cwd=None: (True, output))

        worktrees = hook.get_worktree_list()

        assert worktrees[0].path == "/repo/main"
        assert worktrees[0].branch == "develop"
        assert worktrees[0].is_main is True

    def test_linked_worktree_on_main_branch_is_not_main(self, monkeypatch):
        # 情境 B：linked worktree（非首筆）檢出 main 分支
        output = _porcelain(("/repo/main", "develop"), ("/repo/wt-on-main", "main"))
        monkeypatch.setattr(hook, "run_git_command", lambda args, cwd=None: (True, output))

        worktrees = hook.get_worktree_list()

        assert worktrees[1].path == "/repo/wt-on-main"
        assert worktrees[1].branch == "main"
        assert worktrees[1].is_main is False

    def test_typical_case_main_repo_on_main_branch(self, monkeypatch):
        # 基線：典型情況（主倉庫在 main 分支）順序法與分支名判準結果一致
        output = _porcelain(("/repo/main", "main"), ("/repo/wt1", "feat/x"))
        monkeypatch.setattr(hook, "run_git_command", lambda args, cwd=None: (True, output))

        worktrees = hook.get_worktree_list()

        assert worktrees[0].is_main is True
        assert worktrees[1].is_main is False

    def test_third_entry_is_never_main(self, monkeypatch):
        output = _porcelain(
            ("/repo/main", "main"),
            ("/repo/wt1", "feat/x"),
            ("/repo/wt2", "master"),
        )
        monkeypatch.setattr(hook, "run_git_command", lambda args, cwd=None: (True, output))

        worktrees = hook.get_worktree_list()

        assert worktrees[2].branch == "master"
        assert worktrees[2].is_main is False


class TestCheckGitStateScenarioB:
    """情境 B 回歸測試：linked worktree 在 main 分支的未提交變更不再被靜默排除。"""

    def _fake_run_git_command(self, worktree_output, dirty_paths):
        def _run(args, cwd=None):
            if args[:2] == ["worktree", "list"]:
                return (True, worktree_output)
            if args[:2] == ["status", "--short"]:
                if cwd in dirty_paths:
                    return (True, "M some_file.py")
                return (True, "")
            if args[:2] == ["branch", "--no-merged"]:
                return (True, "")
            return (True, "")

        return _run

    def test_worktree_on_main_branch_with_changes_is_reported(self, monkeypatch):
        output = _porcelain(("/repo/main", "develop"), ("/repo/wt-on-main", "main"))
        monkeypatch.setattr(
            hook, "run_git_command",
            self._fake_run_git_command(output, dirty_paths={"/repo/wt-on-main"}),
        )

        result = hook.check_git_state()

        assert result.has_uncommitted_worktrees is True
        reported_paths = [wt.path for wt in result.uncommitted_worktrees]
        assert "/repo/wt-on-main" in reported_paths

    def test_main_repo_uncommitted_changes_excluded_regardless_of_branch(self, monkeypatch):
        # 主倉庫（首筆）即使有未提交變更，也應排除於 worktree 清單外——
        # 主倉庫的髒污由其他 hook 負責檢查，非本 hook 職責。
        output = _porcelain(("/repo/main", "develop"), ("/repo/wt1", "feat/x"))
        monkeypatch.setattr(
            hook, "run_git_command",
            self._fake_run_git_command(output, dirty_paths={"/repo/main"}),
        )

        result = hook.check_git_state()

        reported_paths = [wt.path for wt in result.uncommitted_worktrees]
        assert "/repo/main" not in reported_paths
        assert result.has_uncommitted_worktrees is False

    def test_typical_case_still_reports_linked_worktree_changes(self, monkeypatch):
        # 基線：典型情況（主倉庫在 main 分支）修正後行為不變
        output = _porcelain(("/repo/main", "main"), ("/repo/wt1", "feat/x"))
        monkeypatch.setattr(
            hook, "run_git_command",
            self._fake_run_git_command(output, dirty_paths={"/repo/wt1"}),
        )

        result = hook.check_git_state()

        reported_paths = [wt.path for wt in result.uncommitted_worktrees]
        assert reported_paths == ["/repo/wt1"]
