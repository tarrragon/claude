"""
paths.py 的 get_ticket_state_root() 單元測試

背景：ticket 狀態操作（claim/append-log/set-acceptance 等）原沿用
get_project_root() 的 worktree 感知——worktree 場景優先回傳呼叫端自己所在
worktree 的根目錄，導致並行派發的多個 worktree agent 各自把票面寫入自己的
worktree 分支，PM 在主倉庫看不到最新狀態，且 body 內容不會隨 worktree 分支
合併帶回主倉庫。get_ticket_state_root() 改為 worktree 場景一律回推主倉庫根
目錄，統一 ticket 狀態的寫入位置。

測試覆蓋：
- worktree 場景：回推主倉庫根目錄（非呼叫端自己的 worktree 根目錄）
- 非 worktree 場景：與 get_project_root() 行為一致
- git-common-dir 無法解析時的降級：委派 get_project_root()
- 測試隔離逃生艙優先序：凌駕 worktree 偵測（避免 pytest 自身在 worktree
  內執行時汙染真實 repo，同 get_project_root() 既有修復模式）
"""

from pathlib import Path
from unittest.mock import patch

from ticket_system.lib.paths import get_ticket_state_root, get_project_root


class TestGetTicketStateRootWorktree:
    """worktree 場景：回推主倉庫根目錄，而非呼叫端自己的 worktree 根目錄"""

    def test_worktree_returns_main_repo_root_not_worktree_root(self):
        """偵測到 linked worktree 時，回傳 git-common-dir 的父目錄（主倉庫根），
        且該值必須不同於呼叫端自己的 worktree 根目錄。"""
        worktree_root = Path("/main/repo/.claude/worktrees/agent-abc")
        main_repo_root = Path("/main/repo")
        common_dir = main_repo_root / ".git"

        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=worktree_root,
            ):
                with patch(
                    "ticket_system.lib.paths.get_git_common_dir",
                    return_value=common_dir,
                ):
                    result = get_ticket_state_root()

        assert result == main_repo_root
        assert result != worktree_root

    def test_worktree_git_common_dir_unresolvable_falls_back_to_project_root(self):
        """worktree 已偵測但 get_git_common_dir() 回傳 None（降級情境）：
        委派 get_project_root() 既有解析鏈，不拋例外。"""
        worktree_root = Path("/main/repo/.claude/worktrees/agent-abc")

        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": "/main/repo"}, clear=True):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=worktree_root,
            ):
                with patch(
                    "ticket_system.lib.paths.get_git_common_dir",
                    return_value=None,
                ):
                    result = get_ticket_state_root()

        # get_project_root() 在此 mock 情境下仍會偵測到 worktree_root
        # （沿用同一個 _linked_worktree_root patch），驗證降級路徑不拋例外
        # 且回傳一個有效 Path。
        assert isinstance(result, Path)


class TestGetTicketStateRootNonWorktree:
    """非 worktree 場景：與 get_project_root() 行為一致"""

    def test_non_worktree_matches_get_project_root(self):
        """_linked_worktree_root 回 None 時，直接委派 get_project_root()。"""
        main_repo = "/main/repo"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": main_repo}, clear=True):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None,
            ):
                state_root = get_ticket_state_root()
                project_root = get_project_root()

        assert state_root == project_root == Path(main_repo)

    def test_non_worktree_git_revparse_fallback(self):
        """非 worktree 且無 CLAUDE_PROJECT_DIR：委派 get_project_root() 走
        git rev-parse --show-toplevel 解析鏈。"""
        git_root = "/path/to/git/repo"
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None,
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = type(
                        "R", (), {"returncode": 0, "stdout": git_root + "\n"}
                    )()
                    result = get_ticket_state_root()

        assert result == Path(git_root)


class TestGetTicketStateRootIsolationEscapeHatch:
    """測試隔離逃生艙必須優先於 worktree 偵測（同 get_project_root() 修復模式）"""

    def test_isolation_flag_wins_over_worktree_detection(self, tmp_path):
        """即使偵測到（模擬的）linked worktree，TICKET_SYSTEM_TEST_ISOLATION=1
        時仍應直接採用 CLAUDE_PROJECT_DIR，不繼續往下解析 git-common-dir。"""
        isolated_dir = tmp_path / "isolated-project"
        isolated_dir.mkdir()
        worktree_root = Path("/main/repo/.claude/worktrees/agent-abc")

        with patch.dict(
            "os.environ",
            {
                "TICKET_SYSTEM_TEST_ISOLATION": "1",
                "CLAUDE_PROJECT_DIR": str(isolated_dir),
            },
            clear=True,
        ):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=worktree_root,
            ):
                with patch(
                    "ticket_system.lib.paths.get_git_common_dir",
                ) as mock_common_dir:
                    result = get_ticket_state_root()

        assert result == isolated_dir
        # 逃生艙短路：worktree 已偵測到，但不應繼續解析 git-common-dir
        mock_common_dir.assert_not_called()

    def test_isolation_flag_without_project_dir_falls_through(self):
        """TICKET_SYSTEM_TEST_ISOLATION=1 但未設 CLAUDE_PROJECT_DIR：逃生艙條件
        不成立（缺 isolated_dir），續走下方 worktree 偵測分支。"""
        main_repo = "/main/repo"
        with patch.dict(
            "os.environ",
            {"TICKET_SYSTEM_TEST_ISOLATION": "1"},
            clear=True,
        ):
            with patch(
                "ticket_system.lib.paths._linked_worktree_root",
                return_value=None,
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = type(
                        "R", (), {"returncode": 0, "stdout": main_repo + "\n"}
                    )()
                    result = get_ticket_state_root()

        assert result == Path(main_repo)
