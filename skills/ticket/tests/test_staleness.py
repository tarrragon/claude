"""
Ticket 有效期 stale 警告機制測試（0.18.0-W11-001.2）

驗證 staleness 模組：
- 閾值常數：7/14/30 天
- 建立年齡判斷
- claim/query/list 命令整合輸出

輸出限制：警告訊息最多 3 行（避免警告疲勞）。
"""

from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest


class TestStalenessThresholds:
    """staleness 模組閾值常數與 level 計算"""

    def test_thresholds_defined(self):
        from ticket_system.lib.staleness import (
            STALE_INFO_DAYS,
            STALE_WARNING_DAYS,
            STALE_CRITICAL_DAYS,
        )

        assert STALE_INFO_DAYS == 7
        assert STALE_WARNING_DAYS == 14
        assert STALE_CRITICAL_DAYS == 30

    def test_level_none_when_fresh(self):
        from ticket_system.lib.staleness import calculate_stale_level

        today = date(2026, 4, 16)
        # 3 天前建立，不觸發
        created = (today - timedelta(days=3)).isoformat()
        assert calculate_stale_level(created, today=today) is None

    def test_level_info_at_7_days(self):
        from ticket_system.lib.staleness import calculate_stale_level

        today = date(2026, 4, 16)
        created = (today - timedelta(days=7)).isoformat()
        assert calculate_stale_level(created, today=today) == "info"

    def test_level_info_between_7_and_13(self):
        from ticket_system.lib.staleness import calculate_stale_level

        today = date(2026, 4, 16)
        created = (today - timedelta(days=10)).isoformat()
        assert calculate_stale_level(created, today=today) == "info"

    def test_level_warning_at_14_days(self):
        from ticket_system.lib.staleness import calculate_stale_level

        today = date(2026, 4, 16)
        created = (today - timedelta(days=14)).isoformat()
        assert calculate_stale_level(created, today=today) == "warning"

    def test_level_warning_between_14_and_29(self):
        from ticket_system.lib.staleness import calculate_stale_level

        today = date(2026, 4, 16)
        created = (today - timedelta(days=20)).isoformat()
        assert calculate_stale_level(created, today=today) == "warning"

    def test_level_critical_at_30_days(self):
        from ticket_system.lib.staleness import calculate_stale_level

        today = date(2026, 4, 16)
        created = (today - timedelta(days=30)).isoformat()
        assert calculate_stale_level(created, today=today) == "critical"

    def test_level_critical_beyond_30(self):
        from ticket_system.lib.staleness import calculate_stale_level

        today = date(2026, 4, 16)
        created = (today - timedelta(days=90)).isoformat()
        assert calculate_stale_level(created, today=today) == "critical"

    def test_missing_created_returns_none(self):
        from ticket_system.lib.staleness import calculate_stale_level

        assert calculate_stale_level(None) is None
        assert calculate_stale_level("") is None

    def test_invalid_date_returns_none(self):
        from ticket_system.lib.staleness import calculate_stale_level

        assert calculate_stale_level("not-a-date") is None


class TestFormatStaleWarning:
    """format_stale_warning 輸出格式（單一 Ticket）"""

    def test_returns_none_when_fresh(self):
        from ticket_system.lib.staleness import format_stale_warning

        today = date(2026, 4, 16)
        ticket = {
            "id": "0.18.0-W1-001",
            "created": (today - timedelta(days=3)).isoformat(),
        }
        assert format_stale_warning(ticket, today=today) is None

    def test_info_message_at_7_days(self):
        from ticket_system.lib.staleness import format_stale_warning

        today = date(2026, 4, 16)
        ticket = {
            "id": "0.18.0-W1-001",
            "created": (today - timedelta(days=7)).isoformat(),
        }
        msg = format_stale_warning(ticket, today=today)
        assert msg is not None
        assert "INFO" in msg
        assert "7" in msg

    def test_warning_message_at_14_days(self):
        from ticket_system.lib.staleness import format_stale_warning

        today = date(2026, 4, 16)
        ticket = {
            "id": "0.18.0-W1-001",
            "created": (today - timedelta(days=14)).isoformat(),
        }
        msg = format_stale_warning(ticket, today=today)
        assert msg is not None
        assert "WARNING" in msg
        assert "14" in msg

    def test_critical_message_at_30_days(self):
        from ticket_system.lib.staleness import format_stale_warning

        today = date(2026, 4, 16)
        ticket = {
            "id": "0.18.0-W1-001",
            "created": (today - timedelta(days=45)).isoformat(),
        }
        msg = format_stale_warning(ticket, today=today)
        assert msg is not None
        # 強烈警告且建議 stale
        assert "WARNING" in msg or "強烈" in msg
        assert "stale" in msg.lower()

    def test_output_limited_to_three_lines(self):
        """AC: 輸出控制在 3 行內"""
        from ticket_system.lib.staleness import format_stale_warning

        today = date(2026, 4, 16)
        ticket = {
            "id": "0.18.0-W1-001",
            "created": (today - timedelta(days=45)).isoformat(),
        }
        msg = format_stale_warning(ticket, today=today)
        assert msg is not None
        assert msg.count("\n") <= 2  # 最多 3 行


class TestFormatStaleListSummary:
    """list 命令的 stale 數量標示"""

    def test_returns_none_when_no_stale(self):
        from ticket_system.lib.staleness import format_stale_list_summary

        today = date(2026, 4, 16)
        tickets = [
            {"id": "A", "created": (today - timedelta(days=1)).isoformat()},
            {"id": "B", "created": (today - timedelta(days=3)).isoformat()},
        ]
        assert format_stale_list_summary(tickets, today=today) is None

    def test_counts_stale_tickets(self):
        from ticket_system.lib.staleness import format_stale_list_summary

        today = date(2026, 4, 16)
        tickets = [
            {"id": "A", "created": (today - timedelta(days=1)).isoformat()},
            {"id": "B", "created": (today - timedelta(days=8)).isoformat()},   # info
            {"id": "C", "created": (today - timedelta(days=15)).isoformat()},  # warning
            {"id": "D", "created": (today - timedelta(days=35)).isoformat()},  # critical
        ]
        msg = format_stale_list_summary(tickets, today=today)
        assert msg is not None
        # 應包含 stale 總數
        assert "3" in msg
        assert "stale" in msg.lower() or "陳舊" in msg

    def test_summary_three_lines_cap(self):
        from ticket_system.lib.staleness import format_stale_list_summary

        today = date(2026, 4, 16)
        tickets = [
            {"id": f"T{i}", "created": (today - timedelta(days=40)).isoformat()}
            for i in range(20)
        ]
        msg = format_stale_list_summary(tickets, today=today)
        assert msg is not None
        assert msg.count("\n") <= 2


class TestCommandIntegration:
    """整合測試：claim/query/list 命令輸出 stale 提示"""

    def _make_args(self, **kwargs):
        args = Mock()
        for k, v in kwargs.items():
            setattr(args, k, v)
        return args

    def test_query_prints_warning_for_old_ticket(self, capsys):
        from datetime import date, timedelta
        from ticket_system.commands.track_query import execute_query

        today = date.today()
        old_created = (today - timedelta(days=20)).isoformat()
        old_ticket = {
            "id": "0.18.0-W1-001",
            "title": "Old ticket",
            "status": "pending",
            "created": old_created,
            "who": {"current": "pm"},
            "what": "x",
            "when": "x",
            "where": {"layer": "x", "files": []},
            "why": "x",
        }

        args = self._make_args(ticket_id="0.18.0-W1-001", version=None)

        with patch(
            "ticket_system.commands.track_query.load_and_validate_ticket",
            return_value=(old_ticket, None),
        ), patch(
            "ticket_system.commands.track_query._check_yaml_error",
            return_value=False,
        ):
            execute_query(args, "0.18.0")

        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "20" in captured.out

    def test_query_no_warning_for_fresh_ticket(self, capsys):
        from datetime import date, timedelta
        from ticket_system.commands.track_query import execute_query

        today = date.today()
        fresh_ticket = {
            "id": "0.18.0-W1-002",
            "title": "Fresh ticket",
            "status": "pending",
            "created": (today - timedelta(days=2)).isoformat(),
            "who": {"current": "pm"},
            "what": "x",
            "when": "x",
            "where": {"layer": "x", "files": []},
            "why": "x",
        }

        args = self._make_args(ticket_id="0.18.0-W1-002", version=None)

        with patch(
            "ticket_system.commands.track_query.load_and_validate_ticket",
            return_value=(fresh_ticket, None),
        ), patch(
            "ticket_system.commands.track_query._check_yaml_error",
            return_value=False,
        ):
            execute_query(args, "0.18.0")

        captured = capsys.readouterr()
        assert "WARNING" not in captured.out
        assert "[INFO]" not in captured.out

    def test_list_table_prints_stale_summary(self, capsys):
        from datetime import date, timedelta
        from ticket_system.commands.track_query import _output_table

        today = date.today()
        tickets = [
            {
                "id": "A",
                "title": "A",
                "status": "pending",
                "wave": 1,
                "type": "IMP",
                "created": (today - timedelta(days=1)).isoformat(),
                "who": {"current": "pm"},
            },
            {
                "id": "B",
                "title": "B",
                "status": "pending",
                "wave": 1,
                "type": "IMP",
                "created": (today - timedelta(days=35)).isoformat(),
                "who": {"current": "pm"},
            },
        ]

        _output_table(tickets, "0.18.0")
        captured = capsys.readouterr()
        assert "Stale" in captured.out or "stale" in captured.out.lower()
        assert "1" in captured.out  # 1 個 critical
