"""
測試模組 A: Context Refresh Handoff

驗證：
1. A-1: in_progress 獨立任務 + --context-refresh → 成功
2. A-2: in_progress 獨立任務（無旗標）→ 拒絕
3. A-3: completed 狀態原有行為不變
4. A-4: --context-refresh 跳過依賴驗證
5. A-5: resume --list 顯示 context-refresh 方向
6. A-6: pending/blocked 狀態 + --context-refresh → 拒絕
7. A-7: --context-refresh 與方向旗標互斥
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import argparse
import pytest


@pytest.fixture
def sample_in_progress_ticket() -> dict:
    """in_progress 獨立 Ticket 樣本"""
    return {
        "id": "0.1.0-W1-001",
        "title": "Context Refresh Test Task",
        "status": "in_progress",
        "what": "Test description",
        "children": [],
        "chain": {},
    }


@pytest.fixture
def sample_completed_ticket() -> dict:
    """completed Ticket 樣本"""
    return {
        "id": "0.1.0-W1-001",
        "title": "Completed Test Task",
        "status": "completed",
        "what": "Test description",
        "children": [],
        "chain": {},
    }


@pytest.fixture
def sample_ticket_with_blockedBy() -> dict:
    """有 blockedBy 的 in_progress Ticket 樣本"""
    return {
        "id": "0.1.0-W1-001",
        "title": "Task with blockers",
        "status": "in_progress",
        "what": "Test description",
        "children": [],
        "chain": {},
        "blockedBy": ["0.1.0-W1-002"],
    }


class TestContextRefreshHandoff:
    """Context Refresh Handoff 測試組"""

    def test_context_refresh_in_progress_independent_success(
        self,
        sample_in_progress_ticket: dict,
    ) -> None:
        """A-1: in_progress 獨立任務 + --context-refresh → 成功"""
        from ticket_system.commands.handoff import _execute_handoff
        from ticket_system.lib.ticket_validator import validate_ticket_id
        from ticket_system.lib.constants import HANDOFF_DIR, HANDOFF_PENDING_SUBDIR

        # 準備 args
        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            version="0.1.0",
            context_refresh=True,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        # Mock 必要的依賴
        with patch("ticket_system.commands.handoff.validate_ticket_id") as mock_validate:
            with patch("ticket_system.commands.handoff.resolve_version") as mock_resolve:
                with patch("ticket_system.commands.handoff.load_ticket") as mock_load:
                    with patch("ticket_system.commands.handoff._create_handoff_file") as mock_create:
                        # 設定 mock
                        mock_validate.return_value = True
                        mock_resolve.return_value = "0.1.0"
                        mock_load.return_value = sample_in_progress_ticket
                        mock_create.return_value = 0

                        # 執行
                        result = _execute_handoff(args)

                        # 驗證
                        assert result == 0
                        mock_create.assert_called_once()
                        call_args = mock_create.call_args[0]
                        assert call_args[1] == "context-refresh"

    def test_in_progress_independent_rejected_without_flag(
        self,
        sample_in_progress_ticket: dict,
    ) -> None:
        """A-2: in_progress 獨立任務（無旗標）→ 拒絕"""
        from ticket_system.commands.handoff import _execute_handoff

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            version="0.1.0",
            context_refresh=False,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        with patch("ticket_system.commands.handoff.validate_ticket_id") as mock_validate:
            with patch("ticket_system.commands.handoff.resolve_version") as mock_resolve:
                with patch("ticket_system.commands.handoff.load_ticket") as mock_load:
                    with patch("ticket_system.commands.handoff._create_handoff_file") as mock_create:
                        mock_validate.return_value = True
                        mock_resolve.return_value = "0.1.0"
                        mock_load.return_value = sample_in_progress_ticket

                        result = _execute_handoff(args)

                        assert result == 1
                        mock_create.assert_not_called()

    def test_completed_status_backward_compatible(
        self,
        sample_completed_ticket: dict,
    ) -> None:
        """A-3: completed 狀態原有行為不變"""
        from ticket_system.commands.handoff import _execute_handoff

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            version="0.1.0",
            context_refresh=False,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        with patch("ticket_system.commands.handoff.validate_ticket_id") as mock_validate:
            with patch("ticket_system.commands.handoff.resolve_version") as mock_resolve:
                with patch("ticket_system.commands.handoff.load_ticket") as mock_load:
                    with patch("ticket_system.commands.handoff._verify_handoff_dependencies") as mock_deps:
                        with patch("ticket_system.commands.handoff._create_handoff_file") as mock_create:
                            with patch("ticket_system.commands.handoff.ChainAnalyzer") as mock_analyzer:
                                mock_validate.return_value = True
                                mock_resolve.return_value = "0.1.0"
                                mock_load.return_value = sample_completed_ticket
                                mock_deps.return_value = True
                                mock_create.return_value = 0
                                mock_analyzer.determine_direction.return_value = "to-parent"

                                result = _execute_handoff(args)

                                assert result == 0
                                mock_create.assert_called_once()

    def test_context_refresh_skips_dependency_verification(
        self,
        sample_ticket_with_blockedBy: dict,
    ) -> None:
        """A-4: --context-refresh 跳過依賴驗證"""
        from ticket_system.commands.handoff import _execute_handoff

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            version="0.1.0",
            context_refresh=True,
            to_parent=False,
            to_child=None,
            to_sibling=None,
        )

        with patch("ticket_system.commands.handoff.validate_ticket_id") as mock_validate:
            with patch("ticket_system.commands.handoff.resolve_version") as mock_resolve:
                with patch("ticket_system.commands.handoff.load_ticket") as mock_load:
                    with patch("ticket_system.commands.handoff._verify_handoff_dependencies") as mock_deps:
                        with patch("ticket_system.commands.handoff._create_handoff_file") as mock_create:
                            mock_validate.return_value = True
                            mock_resolve.return_value = "0.1.0"
                            mock_load.return_value = sample_ticket_with_blockedBy
                            mock_create.return_value = 0

                            result = _execute_handoff(args)

                            assert result == 0
                            # 驗證 _verify_handoff_dependencies 未被呼叫
                            mock_deps.assert_not_called()
                            mock_create.assert_called_once()

    def test_context_refresh_rejected_for_pending_or_blocked_status(self) -> None:
        """A-6: pending/blocked 狀態 + --context-refresh → 拒絕"""
        from ticket_system.commands.handoff import _execute_handoff

        for status in ["pending", "blocked"]:
            ticket = {
                "id": "0.1.0-W1-001",
                "status": status,
                "children": [],
                "chain": {},
            }

            args = argparse.Namespace(
                ticket_id="0.1.0-W1-001",
                version="0.1.0",
                context_refresh=True,
                to_parent=False,
                to_child=None,
                to_sibling=None,
            )

            with patch("ticket_system.commands.handoff.validate_ticket_id") as mock_validate:
                with patch("ticket_system.commands.handoff.resolve_version") as mock_resolve:
                    with patch("ticket_system.commands.handoff.load_ticket") as mock_load:
                        with patch("ticket_system.commands.handoff._create_handoff_file") as mock_create:
                            mock_validate.return_value = True
                            mock_resolve.return_value = "0.1.0"
                            mock_load.return_value = ticket

                            result = _execute_handoff(args)

                            assert result == 1
                            mock_create.assert_not_called()

    def test_context_refresh_mutually_exclusive_with_direction_flags(
        self,
        sample_in_progress_ticket: dict,
    ) -> None:
        """A-7: --context-refresh 與方向旗標互斥"""
        from ticket_system.commands.handoff import _execute_handoff

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            version="0.1.0",
            context_refresh=True,
            to_parent=True,  # 互斥
            to_child=None,
            to_sibling=None,
        )

        with patch("ticket_system.commands.handoff.validate_ticket_id") as mock_validate:
            with patch("ticket_system.commands.handoff.resolve_version") as mock_resolve:
                with patch("ticket_system.commands.handoff.load_ticket") as mock_load:
                    with patch("ticket_system.commands.handoff._create_handoff_file") as mock_create:
                        mock_validate.return_value = True
                        mock_resolve.return_value = "0.1.0"
                        mock_load.return_value = sample_in_progress_ticket

                        result = _execute_handoff(args)

                        assert result == 1
                        mock_create.assert_not_called()


class TestResumeContextRefresh:
    """Resume context-refresh 顯示測試"""

    def test_resume_list_displays_context_refresh_direction(self) -> None:
        """A-5: resume --list 顯示 context-refresh 方向"""
        from ticket_system.commands.resume import list_pending_handoffs

        # 建立臨時 handoff 環境
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # 建立 handoff 目錄結構
            handoff_dir = tmpdir_path / ".claude" / "handoff" / "pending"
            handoff_dir.mkdir(parents=True, exist_ok=True)

            # 建立 context-refresh handoff 檔案
            handoff_file = handoff_dir / "0.1.0-W1-001.json"
            handoff_data = {
                "ticket_id": "0.1.0-W1-001",
                "direction": "context-refresh",
                "timestamp": "2026-03-04T10:00:00",
                "from_status": "in_progress",
                "title": "Test Task",
            }
            handoff_file.write_text(json.dumps(handoff_data, ensure_ascii=False, indent=2))

            # Mock get_project_root 回傳臨時目錄
            with patch("ticket_system.commands.resume.get_project_root") as mock_root:
                mock_root.return_value = tmpdir_path

                # 執行 list_pending_handoffs
                handoffs = list_pending_handoffs()

                # 驗證
                assert len(handoffs) == 1
                assert handoffs[0]["ticket_id"] == "0.1.0-W1-001"
                assert handoffs[0]["direction"] == "context-refresh"
