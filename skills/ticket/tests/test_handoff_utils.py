"""
test_handoff_utils.is_handoff_stale 單元測試

覆蓋 W17-095.1 Context Bundle 4 個 stale 情境：
1. 任務鏈目標已啟動 (in_progress / completed)
2. 非任務鏈來源 ticket 已 completed
3. 非任務鏈 from_status 已標記 completed
4. 未完成（不 stale）
"""

from unittest.mock import patch

import pytest

from ticket_system.lib.handoff_utils import is_handoff_stale


class TestIsHandoffStaleTaskChainTargetStarted:
    """情境 1：任務鏈方向且目標已啟動"""

    @patch("ticket_system.lib.handoff_utils.load_and_validate_ticket")
    @patch("ticket_system.lib.handoff_utils.extract_version_from_ticket_id")
    @patch("ticket_system.lib.handoff_utils.is_ticket_in_progress_or_completed")
    def test_task_chain_target_in_progress_is_stale(
        self, mock_target_started, mock_extract_version, mock_load
    ):
        mock_target_started.return_value = True
        mock_extract_version.return_value = "0.18.0"
        mock_load.return_value = ({"status": "in_progress"}, None)

        record = {
            "from_ticket": "0.18.0-W17-001",
            "direction": "to-sibling:0.18.0-W17-002",
            "from_status": "completed",
        }
        is_stale, reason = is_handoff_stale(record)

        assert is_stale is True
        assert "任務鏈目標 0.18.0-W17-002" in reason
        assert "in_progress" in reason

    @patch("ticket_system.lib.handoff_utils.load_and_validate_ticket")
    @patch("ticket_system.lib.handoff_utils.extract_version_from_ticket_id")
    @patch("ticket_system.lib.handoff_utils.is_ticket_in_progress_or_completed")
    def test_task_chain_target_completed_is_stale(
        self, mock_target_started, mock_extract_version, mock_load
    ):
        mock_target_started.return_value = True
        mock_extract_version.return_value = "0.18.0"
        mock_load.return_value = ({"status": "completed"}, None)

        record = {
            "from_ticket": "0.18.0-W17-001",
            "direction": "to-child:0.18.0-W17-001.1",
            "from_status": "completed",
        }
        is_stale, reason = is_handoff_stale(record)

        assert is_stale is True
        assert "completed" in reason


class TestIsHandoffStaleNonChainSourceCompleted:
    """情境 2：非任務鏈方向且來源 ticket 已 completed"""

    @patch("ticket_system.lib.handoff_utils.is_ticket_completed")
    def test_context_refresh_source_completed_is_stale(self, mock_completed):
        mock_completed.return_value = True

        record = {
            "from_ticket": "0.18.0-W17-001",
            "direction": "context-refresh",
            "from_status": "in_progress",
        }
        is_stale, reason = is_handoff_stale(record)

        assert is_stale is True
        assert "來源 ticket 0.18.0-W17-001 已 completed" in reason

    @patch("ticket_system.lib.handoff_utils.is_ticket_completed")
    def test_uses_ticket_id_when_from_ticket_missing(self, mock_completed):
        """向後相容：record 只有 ticket_id 沒有 from_ticket"""
        mock_completed.return_value = True

        record = {
            "ticket_id": "0.18.0-W17-005",
            "direction": "context-refresh",
            "from_status": "",
        }
        is_stale, reason = is_handoff_stale(record)

        assert is_stale is True
        assert "0.18.0-W17-005" in reason


class TestIsHandoffStaleNonChainFromStatusCompleted:
    """情境 3：非任務鏈方向且 from_status 已標記 completed"""

    @patch("ticket_system.lib.handoff_utils.is_ticket_completed")
    def test_from_status_completed_is_stale(self, mock_completed):
        # 來源 ticket 未 completed（避免命中情境 2），但 from_status 已標 completed
        mock_completed.return_value = False

        record = {
            "from_ticket": "0.18.0-W17-001",
            "direction": "context-refresh",
            "from_status": "completed",
        }
        is_stale, reason = is_handoff_stale(record)

        assert is_stale is True
        assert "from_status" in reason
        assert "completed" in reason


class TestIsHandoffStaleNotStale:
    """情境 4：未完成（不 stale）"""

    @patch("ticket_system.lib.handoff_utils.is_ticket_completed")
    def test_non_chain_source_not_completed_not_stale(self, mock_completed):
        mock_completed.return_value = False

        record = {
            "from_ticket": "0.18.0-W17-001",
            "direction": "context-refresh",
            "from_status": "in_progress",
        }
        is_stale, reason = is_handoff_stale(record)

        assert is_stale is False
        assert reason == ""

    @patch("ticket_system.lib.handoff_utils.is_ticket_in_progress_or_completed")
    def test_task_chain_target_not_started_not_stale(self, mock_target_started):
        mock_target_started.return_value = False

        record = {
            "from_ticket": "0.18.0-W17-001",
            "direction": "to-sibling:0.18.0-W17-002",
            "from_status": "completed",
        }
        is_stale, reason = is_handoff_stale(record)

        assert is_stale is False
        assert reason == ""

    def test_task_chain_without_target_id_not_stale(self):
        """任務鏈方向但無 target_id（如 'to-parent' 無冒號）→ 不 stale"""
        record = {
            "from_ticket": "0.18.0-W17-001",
            "direction": "to-parent",
            "from_status": "completed",
        }
        is_stale, reason = is_handoff_stale(record)

        assert is_stale is False
        assert reason == ""
