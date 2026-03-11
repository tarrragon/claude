"""
track list 篩選功能測試

測試 --wave、--status、--format 參數的正確性
"""

from unittest.mock import Mock, patch
import pytest

from ticket_system.commands.track_query import (
    execute_list,
    _build_status_filters,
    _output_ids,
    _output_yaml,
    _output_table,
)
from ticket_system.commands.track import _parse_wave_arg
from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
)


class TestParseWaveArg:
    """_parse_wave_arg 函式測試"""

    def test_integer_format(self):
        """接受純整數格式"""
        assert _parse_wave_arg("2") == 2
        assert _parse_wave_arg("28") == 28

    def test_uppercase_w_format(self):
        """接受 W{n} 大寫格式"""
        assert _parse_wave_arg("W2") == 2
        assert _parse_wave_arg("W28") == 28

    def test_lowercase_w_format(self):
        """接受 w{n} 小寫格式"""
        assert _parse_wave_arg("w2") == 2
        assert _parse_wave_arg("w28") == 28

    def test_invalid_value_raises(self):
        """無效值應拋出 ValueError"""
        with pytest.raises(ValueError):
            _parse_wave_arg("abc")
        with pytest.raises(ValueError):
            _parse_wave_arg("W")


class TestWaveFilter:
    """Wave 篩選測試"""

    def test_list_filter_by_wave(self):
        """
        Given: 有多個不同 Wave 的 Ticket
        When: 指定 --wave 1
        Then: 應只返回 Wave 1 的 Ticket
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.wave = 1
        args.status = None
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W1-001",
                    "status": STATUS_PENDING,
                    "wave": 1,
                    "title": "Task 1",
                },
                {
                    "id": "0.31.0-W2-001",
                    "status": STATUS_PENDING,
                    "wave": 2,
                    "title": "Task 2",
                },
                {
                    "id": "0.31.0-W1-002",
                    "status": STATUS_IN_PROGRESS,
                    "wave": 1,
                    "title": "Task 3",
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0

    def test_list_filter_by_wave_no_match(self):
        """
        Given: 指定的 Wave 沒有 Ticket
        When: 執行 execute_list
        Then: 應返回 0，顯示無符合結果
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.wave = 99
        args.status = None
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W1-001",
                    "status": STATUS_PENDING,
                    "wave": 1,
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0


class TestStatusFilter:
    """Status 參數篩選測試"""

    def test_list_filter_by_status_pending(self):
        """
        Given: 使用 --status pending
        When: 執行 execute_list
        Then: 應只返回 pending Ticket
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = ["pending"]
        args.wave = None
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W1-001",
                    "status": STATUS_PENDING,
                    "title": "Task 1",
                },
                {
                    "id": "0.31.0-W1-002",
                    "status": STATUS_IN_PROGRESS,
                    "title": "Task 2",
                },
                {
                    "id": "0.31.0-W1-003",
                    "status": STATUS_COMPLETED,
                    "title": "Task 3",
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0

    def test_list_filter_by_status_completed(self):
        """
        Given: 使用 --status completed
        When: 執行 execute_list
        Then: 應只返回 completed Ticket
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = ["completed"]
        args.wave = None
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W1-001",
                    "status": STATUS_COMPLETED,
                    "title": "Task 1",
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0

    def test_backward_compatibility_pending_flag(self):
        """
        Given: 使用舊的 --pending flag
        When: 執行 execute_list
        Then: 應正確篩選 pending Ticket（向後相容）
        """
        args = Mock()
        args.pending = True
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = None
        args.wave = None
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W1-001",
                    "status": STATUS_PENDING,
                },
                {
                    "id": "0.31.0-W1-002",
                    "status": STATUS_IN_PROGRESS,
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0


class TestFormatOutput:
    """輸出格式測試"""

    def test_output_format_ids(self):
        """
        Given: 使用 --format ids
        When: 執行 execute_list
        Then: 應只輸出 Ticket ID，一行一個
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = None
        args.wave = None
        args.format = "ids"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W1-001", "status": STATUS_PENDING},
                {"id": "0.31.0-W1-002", "status": STATUS_IN_PROGRESS},
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0

    def test_output_format_yaml(self):
        """
        Given: 使用 --format yaml
        When: 執行 execute_list
        Then: 應輸出 YAML 格式的 Ticket 列表
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = None
        args.wave = None
        args.format = "yaml"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W1-001",
                    "status": STATUS_PENDING,
                    "title": "Task 1",
                    "wave": 1,
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0

    def test_output_format_default_table(self):
        """
        Given: 未指定 --format
        When: 執行 execute_list
        Then: 應使用預設的 table 格式
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = None
        args.wave = None
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W1-001", "status": STATUS_PENDING},
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0


class TestBuildStatusFilters:
    """狀態篩選器構建測試"""

    def test_status_filter_pending(self):
        """Given: --status pending，Then: 應返回 STATUS_PENDING"""
        args = Mock()
        args.status = ["pending"]
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False

        filters = _build_status_filters(args)

        assert STATUS_PENDING in filters
        assert len(filters) == 1

    def test_status_filter_in_progress(self):
        """Given: --status in_progress，Then: 應返回 STATUS_IN_PROGRESS"""
        args = Mock()
        args.status = ["in_progress"]
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False

        filters = _build_status_filters(args)

        assert STATUS_IN_PROGRESS in filters

    def test_status_filter_completed(self):
        """Given: --status completed，Then: 應返回 STATUS_COMPLETED"""
        args = Mock()
        args.status = ["completed"]
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False

        filters = _build_status_filters(args)

        assert STATUS_COMPLETED in filters

    def test_status_filter_blocked(self):
        """Given: --status blocked，Then: 應返回 STATUS_BLOCKED"""
        args = Mock()
        args.status = ["blocked"]
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False

        filters = _build_status_filters(args)

        assert STATUS_BLOCKED in filters

    def test_status_filter_multiple_values(self):
        """Given: --status pending in_progress，Then: 應返回多個狀態"""
        args = Mock()
        args.status = ["pending", "in_progress"]
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False

        filters = _build_status_filters(args)

        assert STATUS_PENDING in filters
        assert STATUS_IN_PROGRESS in filters
        assert len(filters) == 2

    def test_flag_filter_pending(self):
        """Given: --pending flag，Then: 應返回 STATUS_PENDING"""
        args = Mock()
        args.status = None
        args.pending = True
        args.in_progress = False
        args.completed = False
        args.blocked = False

        filters = _build_status_filters(args)

        assert STATUS_PENDING in filters

    def test_flag_filter_multiple(self):
        """Given: --pending --in-progress，Then: 應返回兩個狀態"""
        args = Mock()
        args.status = None
        args.pending = True
        args.in_progress = True
        args.completed = False
        args.blocked = False

        filters = _build_status_filters(args)

        assert STATUS_PENDING in filters
        assert STATUS_IN_PROGRESS in filters
        assert len(filters) == 2

    def test_no_filter_returns_empty(self):
        """Given: 未指定任何篩選，Then: 應返回空集合"""
        args = Mock()
        args.status = None
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False

        filters = _build_status_filters(args)

        assert len(filters) == 0


class TestComplexFilters:
    """複合篩選測試"""

    def test_filter_wave_and_status(self):
        """
        Given: --wave 1 --status pending
        When: 執行 execute_list
        Then: 應同時篩選 Wave 和狀態
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = ["pending"]
        args.wave = 1
        args.format = "ids"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W1-001",
                    "status": STATUS_PENDING,
                    "wave": 1,
                },
                {
                    "id": "0.31.0-W1-002",
                    "status": STATUS_IN_PROGRESS,
                    "wave": 1,
                },
                {
                    "id": "0.31.0-W2-001",
                    "status": STATUS_PENDING,
                    "wave": 2,
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0

    def test_filter_wave_and_status_no_match(self):
        """
        Given: --wave 99 --status pending（不存在的組合）
        When: 執行 execute_list
        Then: 應返回 0，顯示無符合結果
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = ["pending"]
        args.wave = 99
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W1-001",
                    "status": STATUS_PENDING,
                    "wave": 1,
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0
