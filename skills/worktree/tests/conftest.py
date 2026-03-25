"""
pytest fixtures for worktree SKILL tests

提供共用的 mock 和測試資料。
"""

import pytest
from pathlib import Path
import sys


# ===== 樣本資料 =====

@pytest.fixture
def sample_ticket_ids():
    """各類 Ticket ID 範例"""
    return {
        "valid_root": "0.1.1-W9-002",
        "valid_subtask": "0.1.1-W9-002.1",
        "valid_nested": "0.1.1-W9-002.1.2.3",
        "invalid_format": "my-feature",
        "invalid_no_w": "0.1.1-001",
    }


@pytest.fixture
def mock_worktree_list_output():
    """Mock git worktree list --porcelain 的輸出"""
    return """/Users/mac-eric/project/ccsession (branch refs/heads/main)
/Users/mac-eric/project/ccsession-0.1.1-W9-002.1 (branch refs/heads/feat/0.1.1-W9-002.1)
/Users/mac-eric/project/ccsession-0.1.1-W9-002.2 (branch refs/heads/feat/0.1.1-W9-002.2)"""


# ===== Mock 工具函式（#14 修復：修正未使用和格式錯誤的 fixture） =====

@pytest.fixture
def mock_run_git_command(monkeypatch):
    """
    Mock run_git_command，支援自訂返回值

    此 fixture 為主要測試提供模擬 git 命令執行功能。
    """
    def _mock_run_git_command(args, cwd=None, timeout=10):
        """模擬 git 命令執行"""
        # 預設行為：根據命令類型返回適當結果
        if len(args) >= 2 and args[0] == "worktree" and args[1] == "list":
            return (True, "/Users/mac-eric/project/ccsession (branch refs/heads/main)\n")
        elif len(args) >= 2 and args[0] == "rev-parse" and args[1] == "--verify":
            # 預設分支存在
            return (True, "")
        elif len(args) >= 1 and args[0] == "rev-list":
            # 預設返回 0 commit
            return (True, "0")
        else:
            return (True, "")

    # 在主程式中進行 mock（worktree_manager 模組內）
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(project_root / ".claude" / "lib"))

    # Mock worktree_manager 中的 run_git_command
    import worktree_manager
    monkeypatch.setattr("worktree_manager.run_git_command", _mock_run_git_command)

    return _mock_run_git_command


@pytest.fixture
def mock_get_project_root(monkeypatch, tmp_path):
    """
    Mock get_project_root，返回臨時路徑

    此 fixture 為測試 derive_worktree_path 時提供模擬專案根目錄。
    """
    def _mock_get_project_root():
        return str(tmp_path / "ccsession")

    # 在主程式中進行 mock
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(project_root / ".claude" / "lib"))

    import worktree_manager
    monkeypatch.setattr("worktree_manager.get_project_root", _mock_get_project_root)

    return _mock_get_project_root
