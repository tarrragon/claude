"""
Handoff 命令測試

測試 handoff --status 的自動偵測功能。
"""

import argparse
import os
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import pytest
import yaml

from ticket_system.commands.handoff import (
    _find_completed_tickets,
    _find_in_progress_tickets,
    _prompt_select_ticket,
    execute,
    _verify_handoff_status,
    _verify_handoff_dependencies,
)
from ticket_system.lib.constants import STATUS_IN_PROGRESS, STATUS_PENDING, STATUS_COMPLETED


@pytest.fixture
def temp_version_tickets() -> Path:
    """建立臨時版本的 Tickets 目錄"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        tickets_dir = project_root / "docs" / "work-logs" / "v0.31.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        # 建立 pubspec.yaml 標記為專案根目錄
        (project_root / "pubspec.yaml").touch()

        # 設置環境變數讓 get_project_root 使用這個目錄
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)

        try:
            yield project_root, tickets_dir
        finally:
            # 恢復環境變數
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


def _create_ticket_file(
    tickets_dir: Path,
    ticket_id: str,
    status: str,
    title: str = "Test Ticket",
    completed_at: str = None,
) -> None:
    """輔助函式：建立 Ticket 檔案"""
    ticket_data = {
        "id": ticket_id,
        "title": title,
        "status": status,
        "priority": "P1",
        "type": "IMP",
        "created": "2026-01-30",
    }
    if completed_at is not None:
        ticket_data["completed_at"] = completed_at

    frontmatter_yaml = yaml.dump(
        ticket_data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    body = f"# {title}\n\n## 目標\n測試內容"
    content = f"---\n{frontmatter_yaml}---\n{body}"

    ticket_path = tickets_dir / f"{ticket_id}.md"
    ticket_path.write_text(content, encoding="utf-8")


class TestFindInProgressTickets:
    """測試 _find_in_progress_tickets 函式"""

    def test_find_single_in_progress_ticket(self, temp_version_tickets):
        """測試單個 in_progress 任務的尋找"""
        project_root, tickets_dir = temp_version_tickets

        # 建立一個 in_progress 和一個 pending Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_IN_PROGRESS, "Task 1")
        _create_ticket_file(tickets_dir, "0.31.0-W4-002", STATUS_PENDING, "Task 2")

        result = _find_in_progress_tickets("0.31.0")

        assert len(result) == 1
        assert result[0]["id"] == "0.31.0-W4-001"
        assert result[0]["status"] == STATUS_IN_PROGRESS

    def test_find_multiple_in_progress_tickets(self, temp_version_tickets):
        """測試多個 in_progress 任務的尋找"""
        project_root, tickets_dir = temp_version_tickets

        # 建立多個 in_progress Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_IN_PROGRESS, "Task 1")
        _create_ticket_file(tickets_dir, "0.31.0-W4-002", STATUS_IN_PROGRESS, "Task 2")
        _create_ticket_file(tickets_dir, "0.31.0-W4-003", STATUS_COMPLETED, "Task 3")

        result = _find_in_progress_tickets("0.31.0")

        assert len(result) == 2
        assert all(t["status"] == STATUS_IN_PROGRESS for t in result)
        ticket_ids = {t["id"] for t in result}
        assert ticket_ids == {"0.31.0-W4-001", "0.31.0-W4-002"}

    def test_find_no_in_progress_tickets(self, temp_version_tickets):
        """測試沒有 in_progress 任務的情況"""
        project_root, tickets_dir = temp_version_tickets

        # 建立只有 pending 和 completed 的 Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_PENDING, "Task 1")
        _create_ticket_file(tickets_dir, "0.31.0-W4-002", STATUS_COMPLETED, "Task 2")

        result = _find_in_progress_tickets("0.31.0")

        assert len(result) == 0

    def test_find_empty_directory(self, temp_version_tickets):
        """測試空的 Tickets 目錄"""
        project_root, tickets_dir = temp_version_tickets

        result = _find_in_progress_tickets("0.31.0")

        assert len(result) == 0


class TestFindCompletedTickets:
    """測試 _find_completed_tickets 函式"""

    def test_returns_recent_completed_tickets_sorted(self, temp_version_tickets):
        """有多個 completed tickets 時，回傳依 completed_at 倒序的最近 N 個"""
        project_root, tickets_dir = temp_version_tickets

        _create_ticket_file(
            tickets_dir, "0.31.0-W4-001", STATUS_COMPLETED,
            "Task 1", completed_at="2026-03-01T10:00:00",
        )
        _create_ticket_file(
            tickets_dir, "0.31.0-W4-002", STATUS_COMPLETED,
            "Task 2", completed_at="2026-03-02T10:00:00",
        )
        _create_ticket_file(
            tickets_dir, "0.31.0-W4-003", STATUS_COMPLETED,
            "Task 3", completed_at="2026-03-03T10:00:00",
        )
        _create_ticket_file(
            tickets_dir, "0.31.0-W4-004", STATUS_PENDING, "Task 4",
        )

        result = _find_completed_tickets("0.31.0")

        assert len(result) == 3
        assert result[0]["id"] == "0.31.0-W4-003"
        assert result[1]["id"] == "0.31.0-W4-002"
        assert result[2]["id"] == "0.31.0-W4-001"

    def test_returns_single_completed_ticket(self, temp_version_tickets):
        """只有 1 個 completed ticket 時，回傳該 ticket"""
        project_root, tickets_dir = temp_version_tickets

        _create_ticket_file(
            tickets_dir, "0.31.0-W4-001", STATUS_COMPLETED,
            "Task 1", completed_at="2026-03-01T10:00:00",
        )
        _create_ticket_file(
            tickets_dir, "0.31.0-W4-002", STATUS_PENDING, "Task 2",
        )

        result = _find_completed_tickets("0.31.0")

        assert len(result) == 1
        assert result[0]["id"] == "0.31.0-W4-001"

    def test_returns_empty_list_when_no_completed(self, temp_version_tickets):
        """無 completed tickets 時，回傳空列表"""
        project_root, tickets_dir = temp_version_tickets

        _create_ticket_file(
            tickets_dir, "0.31.0-W4-001", STATUS_PENDING, "Task 1",
        )
        _create_ticket_file(
            tickets_dir, "0.31.0-W4-002", STATUS_IN_PROGRESS, "Task 2",
        )

        result = _find_completed_tickets("0.31.0")

        assert len(result) == 0

    def test_excludes_tickets_without_completed_at(self, temp_version_tickets):
        """completed tickets 缺少 completed_at 欄位時，被正確過濾"""
        project_root, tickets_dir = temp_version_tickets

        _create_ticket_file(
            tickets_dir, "0.31.0-W4-001", STATUS_COMPLETED,
            "Task 1", completed_at="2026-03-01T10:00:00",
        )
        _create_ticket_file(
            tickets_dir, "0.31.0-W4-002", STATUS_COMPLETED,
            "Task 2",
        )

        result = _find_completed_tickets("0.31.0")

        assert len(result) == 1
        assert result[0]["id"] == "0.31.0-W4-001"


class TestPromptSelectTicket:
    """測試 _prompt_select_ticket 函式"""

    def test_select_valid_option(self):
        """測試選擇有效選項"""
        tickets = [
            {"id": "0.31.0-W4-001", "title": "Task 1", "status": STATUS_IN_PROGRESS},
            {"id": "0.31.0-W4-002", "title": "Task 2", "status": STATUS_IN_PROGRESS},
        ]

        with patch("ticket_system.commands.handoff._is_interactive", return_value=True):
            with patch("builtins.input", return_value="1"):
                result = _prompt_select_ticket(tickets)
                assert result == tickets[0]

    def test_select_second_option(self):
        """測試選擇第二個選項"""
        tickets = [
            {"id": "0.31.0-W4-001", "title": "Task 1", "status": STATUS_IN_PROGRESS},
            {"id": "0.31.0-W4-002", "title": "Task 2", "status": STATUS_IN_PROGRESS},
        ]

        with patch("ticket_system.commands.handoff._is_interactive", return_value=True):
            with patch("builtins.input", return_value="2"):
                result = _prompt_select_ticket(tickets)
                assert result == tickets[1]

    def test_cancel_selection(self):
        """測試取消選擇（輸入 0）"""
        tickets = [
            {"id": "0.31.0-W4-001", "title": "Task 1", "status": STATUS_IN_PROGRESS},
            {"id": "0.31.0-W4-002", "title": "Task 2", "status": STATUS_IN_PROGRESS},
        ]

        with patch("builtins.input", return_value="0"):
            result = _prompt_select_ticket(tickets)
            assert result is None

    def test_invalid_then_valid_input(self):
        """測試無效輸入後重試的情況"""
        tickets = [
            {"id": "0.31.0-W4-001", "title": "Task 1", "status": STATUS_IN_PROGRESS},
        ]

        # 首次輸入無效，第二次輸入有效
        with patch("ticket_system.commands.handoff._is_interactive", return_value=True):
            with patch("builtins.input", side_effect=["99", "1"]):
                result = _prompt_select_ticket(tickets)
                assert result == tickets[0]


class TestHandoffStatusCommand:
    """測試 handoff --status 命令"""

    def test_status_without_ticket_id_single_in_progress(self, temp_version_tickets):
        """測試 --status 不帶 ticket_id，有單個 in_progress 任務"""
        project_root, tickets_dir = temp_version_tickets

        # 建立一個 in_progress Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_IN_PROGRESS, "Task 1")

        args = argparse.Namespace(
            status=True,
            ticket_id=None,
            version=None,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        # 模擬 _print_status 的行為（避免實際輸出）
        with patch("ticket_system.commands.handoff._print_status", return_value=0):
            result = execute(args)
            assert result == 0

    def test_status_without_ticket_id_no_in_progress(self, temp_version_tickets):
        """測試 --status 不帶 ticket_id，無 in_progress 任務"""
        project_root, tickets_dir = temp_version_tickets

        args = argparse.Namespace(
            status=True,
            ticket_id=None,
            version=None,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        with patch("builtins.print") as mock_print:
            result = execute(args)
            # 應該列印「沒有進行中的任務」訊息
            assert result == 0
            # 驗證輸出包含相關訊息
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("沒有進行中" in str(call) for call in print_calls)

    def test_status_with_ticket_id(self, temp_version_tickets):
        """測試 --status 帶 ticket_id"""
        project_root, tickets_dir = temp_version_tickets

        # 建立 Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_IN_PROGRESS, "Task 1")

        args = argparse.Namespace(
            status=True,
            ticket_id="0.31.0-W4-001",
            version=None,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        with patch("ticket_system.commands.handoff._print_status", return_value=0):
            result = execute(args)
            assert result == 0

    def test_status_without_ticket_id_multiple_in_progress(self, temp_version_tickets):
        """測試 --status 不帶 ticket_id，有多個 in_progress 任務"""
        project_root, tickets_dir = temp_version_tickets

        # 建立多個 in_progress Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_IN_PROGRESS, "Task 1")
        _create_ticket_file(tickets_dir, "0.31.0-W4-002", STATUS_IN_PROGRESS, "Task 2")

        args = argparse.Namespace(
            status=True,
            ticket_id=None,
            version=None,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        # 模擬用戶選擇第一個任務
        with patch("builtins.input", return_value="1"):
            with patch("ticket_system.commands.handoff._print_status", return_value=0):
                result = execute(args)
                assert result == 0


class TestVerifyHandoffStatus:
    """測試 _verify_handoff_status 狀態驗證函式"""

    def test_status_completed(self):
        """測試 completed 狀態通過驗證"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket"
        }
        result = _verify_handoff_status(ticket, "0.31.0-W4-001")
        assert result is True

    def test_status_in_progress_fails(self):
        """測試 in_progress 狀態不通過驗證（獨立任務）"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_IN_PROGRESS,
            "title": "Test Ticket"
        }
        with patch("builtins.print"):
            result = _verify_handoff_status(ticket, "0.31.0-W4-001")
            assert result is False

    def test_status_in_progress_with_children_passes(self):
        """測試 in_progress 狀態通過驗證（有 children 的父任務）"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_IN_PROGRESS,
            "title": "Test Ticket",
            "children": ["0.31.0-W4-001.1", "0.31.0-W4-001.2"]
        }
        result = _verify_handoff_status(ticket, "0.31.0-W4-001")
        assert result is True

    def test_status_completed_with_children_passes(self):
        """測試 completed 狀態通過驗證（有 children 的父任務）"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket",
            "children": ["0.31.0-W4-001.1"]
        }
        result = _verify_handoff_status(ticket, "0.31.0-W4-001")
        assert result is True

    def test_status_pending_fails(self):
        """測試 pending 狀態不通過驗證"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_PENDING,
            "title": "Test Ticket"
        }
        with patch("builtins.print"):
            result = _verify_handoff_status(ticket, "0.31.0-W4-001")
            assert result is False

    def test_status_blocked_fails(self):
        """測試 blocked 狀態不通過驗證"""
        ticket = {
            "id": "0.31.0-W4-001",
            "status": "blocked",
            "title": "Test Ticket"
        }
        with patch("builtins.print"):
            result = _verify_handoff_status(ticket, "0.31.0-W4-001")
            assert result is False


class TestVerifyHandoffDependencies:
    """測試 _verify_handoff_dependencies 依賴驗證函式"""

    def test_no_dependencies(self, temp_version_tickets):
        """測試沒有 blockedBy 依賴的 Ticket"""
        project_root, tickets_dir = temp_version_tickets

        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket",
            "blockedBy": []
        }
        result = _verify_handoff_dependencies(ticket, "0.31.0-W4-001", "0.31.0")
        assert result is True

    def test_single_completed_dependency(self, temp_version_tickets):
        """測試單個已完成的依賴"""
        project_root, tickets_dir = temp_version_tickets

        # 建立依賴 Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_COMPLETED, "Dependency Task")

        ticket = {
            "id": "0.31.0-W4-002",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket",
            "blockedBy": ["0.31.0-W4-001"]
        }
        result = _verify_handoff_dependencies(ticket, "0.31.0-W4-002", "0.31.0")
        assert result is True

    def test_single_incomplete_dependency(self, temp_version_tickets):
        """測試單個未完成的依賴"""
        project_root, tickets_dir = temp_version_tickets

        # 建立未完成的依賴 Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_IN_PROGRESS, "Dependency Task")

        ticket = {
            "id": "0.31.0-W4-002",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket",
            "blockedBy": ["0.31.0-W4-001"]
        }
        with patch("builtins.print"):
            result = _verify_handoff_dependencies(ticket, "0.31.0-W4-002", "0.31.0")
            assert result is False

    def test_multiple_dependencies_all_completed(self, temp_version_tickets):
        """測試多個依賴都已完成"""
        project_root, tickets_dir = temp_version_tickets

        # 建立多個已完成的依賴 Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_COMPLETED, "Dependency 1")
        _create_ticket_file(tickets_dir, "0.31.0-W4-002", STATUS_COMPLETED, "Dependency 2")

        ticket = {
            "id": "0.31.0-W4-003",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket",
            "blockedBy": ["0.31.0-W4-001", "0.31.0-W4-002"]
        }
        result = _verify_handoff_dependencies(ticket, "0.31.0-W4-003", "0.31.0")
        assert result is True

    def test_multiple_dependencies_some_incomplete(self, temp_version_tickets):
        """測試多個依賴中有未完成的"""
        project_root, tickets_dir = temp_version_tickets

        # 建立多個依賴 Ticket（狀態不同）
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_COMPLETED, "Dependency 1")
        _create_ticket_file(tickets_dir, "0.31.0-W4-002", STATUS_IN_PROGRESS, "Dependency 2")

        ticket = {
            "id": "0.31.0-W4-003",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket",
            "blockedBy": ["0.31.0-W4-001", "0.31.0-W4-002"]
        }
        with patch("builtins.print"):
            result = _verify_handoff_dependencies(ticket, "0.31.0-W4-003", "0.31.0")
            assert result is False

    def test_missing_dependency_ticket(self, temp_version_tickets):
        """測試依賴 Ticket 不存在"""
        project_root, tickets_dir = temp_version_tickets

        ticket = {
            "id": "0.31.0-W4-001",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket",
            "blockedBy": ["0.31.0-W4-999"]  # 不存在的 Ticket
        }
        with patch("builtins.print"):
            result = _verify_handoff_dependencies(ticket, "0.31.0-W4-001", "0.31.0")
            assert result is False

    def test_blocked_by_as_string(self, temp_version_tickets):
        """測試 blockedBy 為逗號分隔字符串格式"""
        project_root, tickets_dir = temp_version_tickets

        # 建立已完成的依賴 Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_COMPLETED, "Dependency 1")
        _create_ticket_file(tickets_dir, "0.31.0-W4-002", STATUS_COMPLETED, "Dependency 2")

        # blockedBy 為字符串格式
        ticket = {
            "id": "0.31.0-W4-003",
            "status": STATUS_COMPLETED,
            "title": "Test Ticket",
            "blockedBy": "0.31.0-W4-001, 0.31.0-W4-002"
        }
        result = _verify_handoff_dependencies(ticket, "0.31.0-W4-003", "0.31.0")
        assert result is True


class TestHandoffStatusVerification:
    """測試 handoff 命令完整的狀態驗證流程"""

    def test_handoff_rejected_when_status_not_completed(self, temp_version_tickets):
        """測試狀態不為 completed 時 handoff 被拒絕"""
        project_root, tickets_dir = temp_version_tickets

        # 建立 in_progress 的 Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_IN_PROGRESS, "Test Task")

        args = argparse.Namespace(
            ticket_id="0.31.0-W4-001",
            status=False,
            version=None,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        with patch("builtins.print") as mock_print:
            result = execute(args)
            assert result == 1
            # 驗證輸出包含狀態驗證錯誤訊息
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("無法執行 handoff" in str(call) for call in print_calls)

    def test_handoff_rejected_when_dependencies_incomplete(self, temp_version_tickets):
        """測試有未完成的依賴時 handoff 被拒絕"""
        project_root, tickets_dir = temp_version_tickets

        # 建立未完成的依賴 Ticket
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_IN_PROGRESS, "Dependency Task")

        # 建立 completed 但有未完成依賴的 Ticket
        ticket_data = {
            "id": "0.31.0-W4-002",
            "title": "Test Task",
            "status": STATUS_COMPLETED,
            "priority": "P1",
            "type": "IMP",
            "created": "2026-01-30",
            "blockedBy": ["0.31.0-W4-001"]
        }

        frontmatter_yaml = yaml.dump(
            ticket_data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        body = f"# Test Task\n\n## 目標\n測試內容"
        content = f"---\n{frontmatter_yaml}---\n{body}"

        ticket_path = tickets_dir / "0.31.0-W4-002.md"
        ticket_path.write_text(content, encoding="utf-8")

        args = argparse.Namespace(
            ticket_id="0.31.0-W4-002",
            status=False,
            version=None,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        with patch("builtins.print") as mock_print:
            result = execute(args)
            assert result == 1
            # 驗證輸出包含依賴驗證錯誤訊息
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("阻塞依賴" in str(call) for call in print_calls)

    def test_handoff_succeeded_when_all_conditions_met(self, temp_version_tickets):
        """測試所有驗證通過時 handoff 成功"""
        project_root, tickets_dir = temp_version_tickets

        # 建立 completed 的 Ticket（無依賴）
        _create_ticket_file(tickets_dir, "0.31.0-W4-001", STATUS_COMPLETED, "Test Task")

        args = argparse.Namespace(
            ticket_id="0.31.0-W4-001",
            status=False,
            version=None,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        # 模擬成功的 handoff 檔案建立
        with patch("ticket_system.commands.handoff._create_handoff_file", return_value=0):
            result = execute(args)
            assert result == 0
