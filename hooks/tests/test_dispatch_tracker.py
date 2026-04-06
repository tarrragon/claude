"""
Active Dispatch Tracker 單元測試

測試 .claude/hooks/lib/dispatch_tracker.py 的所有公開 API。

Ticket: 0.17.2-W7-004
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 設定 import 路徑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from dispatch_tracker import (
    get_state_file_path,
    record_dispatch,
    clear_dispatch,
    get_active_dispatches,
    is_file_under_dispatch,
    cleanup_expired,
    detect_orphan_branches,
)


@pytest.fixture
def project_root():
    """建立臨時 project_root 目錄"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / ".claude").mkdir()
        yield root


class TestRecordDispatch:
    def test_record_dispatch(self, project_root: Path):
        """記錄後 get_active_dispatches 回傳正確"""
        record_dispatch(
            project_root,
            agent_description="Fix dart_parser",
            ticket_id="W7-001",
            files=["lib/parsers/dart_parser.py"],
            branch_name="agent-abc12345",
        )
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1
        assert dispatches[0]["agent_description"] == "Fix dart_parser"
        assert dispatches[0]["ticket_id"] == "W7-001"
        assert dispatches[0]["files"] == ["lib/parsers/dart_parser.py"]
        assert dispatches[0]["branch_name"] == "agent-abc12345"
        assert "dispatched_at" in dispatches[0]

    def test_record_dispatch_default_branch_name(self, project_root: Path):
        """未提供 branch_name 時預設為空字串"""
        record_dispatch(project_root, "Task without branch")
        dispatches = get_active_dispatches(project_root)
        assert dispatches[0]["branch_name"] == ""

    def test_record_multiple_dispatches(self, project_root: Path):
        """多次記錄累加"""
        record_dispatch(project_root, "Task A")
        record_dispatch(project_root, "Task B")
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 2


class TestClearDispatch:
    def test_clear_dispatch(self, project_root: Path):
        """清理後記錄消失"""
        record_dispatch(project_root, "Task A")
        record_dispatch(project_root, "Task B")

        result = clear_dispatch(project_root, "Task A")

        assert result is True
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1
        assert dispatches[0]["agent_description"] == "Task B"

    def test_clear_dispatch_not_found(self, project_root: Path):
        """清理不存在的記錄回傳 False"""
        record_dispatch(project_root, "Task A")
        result = clear_dispatch(project_root, "Task X")
        assert result is False
        assert len(get_active_dispatches(project_root)) == 1


class TestIsFileUnderDispatch:
    def test_file_under_dispatch(self, project_root: Path):
        """檔案在派發中回傳 dispatch 記錄"""
        record_dispatch(
            project_root, "Fix parser", files=["src/parser.py", "src/utils.py"]
        )
        result = is_file_under_dispatch(project_root, "src/parser.py")
        assert result is not None
        assert result["agent_description"] == "Fix parser"

    def test_file_not_under_dispatch(self, project_root: Path):
        """不在派發中回傳 None"""
        record_dispatch(project_root, "Fix parser", files=["src/parser.py"])
        result = is_file_under_dispatch(project_root, "src/other.py")
        assert result is None


class TestCleanupExpired:
    def test_cleanup_expired(self, project_root: Path):
        """超時記錄被清理"""
        # 手動寫入一筆過期記錄
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        state = {
            "dispatches": [
                {
                    "agent_description": "Old task",
                    "ticket_id": "",
                    "files": [],
                    "dispatched_at": old_time,
                },
                {
                    "agent_description": "New task",
                    "ticket_id": "",
                    "files": [],
                    "dispatched_at": datetime.now(timezone.utc).isoformat(),
                },
            ]
        }
        state_file = get_state_file_path(project_root)
        state_file.write_text(json.dumps(state), encoding="utf-8")

        removed = cleanup_expired(project_root, max_age_hours=4)

        assert removed == 1
        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1
        assert dispatches[0]["agent_description"] == "New task"

    def test_cleanup_no_expired(self, project_root: Path):
        """無超時記錄時回傳 0"""
        record_dispatch(project_root, "Fresh task")
        removed = cleanup_expired(project_root)
        assert removed == 0


class TestDetectOrphanBranches:
    def test_detect_orphan_branches(self, project_root: Path):
        """mock git worktree list，偵測 orphan"""
        porcelain_output = (
            "worktree /main\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /tmp/agent-fix-parser\n"
            "HEAD def456\n"
            "branch refs/heads/agent-fix-parser\n"
            "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output

        with patch("dispatch_tracker.subprocess.run", return_value=mock_result):
            # 無 dispatch 記錄，agent- 分支應為 orphan
            orphans = detect_orphan_branches(project_root)

        assert "agent-fix-parser" in orphans

    def test_no_orphan_when_dispatch_exists(self, project_root: Path):
        """有對應 dispatch 記錄（含 branch_name）時不算 orphan"""
        record_dispatch(
            project_root, "fix-parser", branch_name="agent-fix-parser"
        )

        porcelain_output = (
            "worktree /tmp/agent-fix-parser\n"
            "HEAD def456\n"
            "branch refs/heads/agent-fix-parser\n"
            "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output

        with patch("dispatch_tracker.subprocess.run", return_value=mock_result):
            orphans = detect_orphan_branches(project_root)

        assert len(orphans) == 0

    def test_orphan_when_dispatch_has_no_branch_name(self, project_root: Path):
        """dispatch 記錄無 branch_name 時，worktree 分支視為 orphan"""
        record_dispatch(project_root, "fix-parser")

        porcelain_output = (
            "worktree /tmp/agent-fix-parser\n"
            "HEAD def456\n"
            "branch refs/heads/agent-fix-parser\n"
            "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output

        with patch("dispatch_tracker.subprocess.run", return_value=mock_result):
            orphans = detect_orphan_branches(project_root)

        # 無 branch_name 的 dispatch 不會匹配任何 worktree
        assert "agent-fix-parser" in orphans

    def test_exact_match_prevents_substring_false_negative(self, project_root: Path):
        """精確比對防止子字串誤判（如 agent-fix 不匹配 agent-fix-parser）"""
        record_dispatch(
            project_root, "fix", branch_name="agent-fix"
        )

        porcelain_output = (
            "worktree /tmp/agent-fix-parser\n"
            "HEAD def456\n"
            "branch refs/heads/agent-fix-parser\n"
            "\n"
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = porcelain_output

        with patch("dispatch_tracker.subprocess.run", return_value=mock_result):
            orphans = detect_orphan_branches(project_root)

        # agent-fix != agent-fix-parser，精確比對不會誤判
        assert "agent-fix-parser" in orphans


class TestEdgeCases:
    def test_state_file_not_exist(self, project_root: Path):
        """狀態檔不存在時各函式正常運作"""
        assert get_active_dispatches(project_root) == []
        assert is_file_under_dispatch(project_root, "any.py") is None
        assert clear_dispatch(project_root, "any") is False
        assert cleanup_expired(project_root) == 0

    def test_concurrent_access(self, project_root: Path):
        """多次寫入不會損壞 JSON"""
        for i in range(10):
            record_dispatch(project_root, f"Task {i}")

        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 10

        # 驗證 JSON 可正確解析
        state_file = get_state_file_path(project_root)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert len(data["dispatches"]) == 10
