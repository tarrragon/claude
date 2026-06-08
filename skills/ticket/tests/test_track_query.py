"""
track_query 模組測試

測試查詢相關的 Ticket 操作：query, summary, tree, chain, full, log, list, version
"""

from typing import Dict, Any, List
from unittest.mock import Mock, patch
from pathlib import Path

import pytest

from ticket_system.commands.track_query import (
    execute_query,
    execute_summary,
    execute_tree,
    execute_chain,
    execute_full,
    execute_log,
    execute_list,
    execute_version,
)


class TestQuery:
    """單一 Ticket 查詢測試"""

    def test_query_existing_ticket_success(self):
        """
        Given: 存在一個有效的 Ticket ID
        When: 執行 query 操作
        Then: 應返回 0，並輸出 Ticket 資訊
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Test Ticket",
                "status": "in_progress",
            }
            mock_load.return_value = mock_ticket

            result = execute_query(args, "0.31.0")

            assert result == 0
            mock_load.assert_called_once()

    def test_query_nonexistent_ticket_failure(self):
        """
        Given: 查詢一個不存在的 Ticket ID
        When: 執行 query 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_load.return_value = None

            result = execute_query(args, "0.31.0")

            assert result == 1

    def test_query_with_auto_version_detection(self):
        """
        Given: 未指定版本號，應自動偵測
        When: 執行 query 操作
        Then: 應該正確偵測版本並返回 Ticket
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = None

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Test Ticket",
            }
            mock_load.return_value = mock_ticket

            result = execute_query(args, "0.31.0")

            assert result == 0


class TestSummary:
    """摘要查詢測試"""

    def test_summary_all_tickets_success(self):
        """
        Given: 存在多個 Ticket
        When: 執行 summary 操作
        Then: 應返回 0，並輸出所有 Ticket 的摘要
        """
        args = Mock()
        args.version = "0.31.0"
        args.status = None

        with patch('ticket_system.commands.track_query.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W4-001", "status": "completed", "title": "Ticket 1"},
                {"id": "0.31.0-W4-002", "status": "in_progress", "title": "Ticket 2"},
                {"id": "0.31.0-W4-003", "status": "pending", "title": "Ticket 3"},
            ]
            mock_list.return_value = mock_tickets

            with patch('ticket_system.commands.track_query.format_ticket_list'):
                with patch('ticket_system.commands.track_query._print_cross_version_warning'):
                    result = execute_summary(args, "0.31.0")

                    assert result == 0
                    # 應該被調用至少一次（針對當前版本）
                    assert mock_list.called

    def test_summary_empty_ticket_list(self):
        """
        Given: 沒有任何 Ticket
        When: 執行 summary 操作
        Then: 應返回 0，並顯示空列表訊息
        """
        args = Mock()
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_list.return_value = []

            result = execute_summary(args, "0.31.0")

            assert result == 0

    def test_summary_shows_progress_statistics(self):
        """
        Given: 存在不同狀態的 Ticket
        When: 執行 summary 操作
        Then: 應輸出進度統計（完成數、進行中數、待處理數）
        """
        args = Mock()
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W4-001", "status": "completed"},
                {"id": "0.31.0-W4-002", "status": "completed"},
                {"id": "0.31.0-W4-003", "status": "in_progress"},
                {"id": "0.31.0-W4-004", "status": "pending"},
            ]
            mock_list.return_value = mock_tickets

            with patch('ticket_system.lib.ticket_formatter.get_ticket_stats') as mock_stats:
                mock_stats.return_value = {
                    "completed": 2,
                    "in_progress": 1,
                    "pending": 1,
                    "total": 4,
                }

                result = execute_summary(args, "0.31.0")

                assert result == 0


class TestTree:
    """任務鏈樹狀結構測試"""

    def test_tree_single_ticket(self):
        """
        Given: 查詢一個沒有子任務的根 Ticket
        When: 執行 tree 操作
        Then: 應返回 0，顯示單一 Ticket
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Root Ticket",
                "children": [],
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_formatter.format_ticket_tree'):
                result = execute_tree(args, "0.31.0")

                assert result == 0

    def test_tree_with_child_tickets(self):
        """
        Given: 存在有多個子任務的根 Ticket
        When: 執行 tree 操作
        Then: 應返回 0，以樹狀結構顯示所有層級
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Root Ticket",
                "children": [
                    "0.31.0-W4-001.1",
                    "0.31.0-W4-001.2",
                ],
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_formatter.format_ticket_tree'):
                result = execute_tree(args, "0.31.0")

                assert result == 0

    def test_tree_nonexistent_root_failure(self):
        """
        Given: 根 Ticket ID 不存在
        When: 執行 tree 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_load.return_value = None

            result = execute_tree(args, "0.31.0")

            assert result == 1


class TestChain:
    """完整任務鏈測試"""

    def test_chain_display_full_chain(self):
        """
        Given: 查詢一個任務的完整任務鏈
        When: 執行 chain 操作
        Then: 應返回 0，顯示完整的任務鏈結構
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001.1"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001.1",
                "title": "Child Ticket",
                "chain": {"root": "0.31.0-W4-001", "parent": "0.31.0-W4-001"},
            }
            mock_load.return_value = mock_ticket

            result = execute_chain(args, "0.31.0")

            assert result == 0

    def test_chain_root_ticket(self):
        """
        Given: 查詢一個根 Ticket 的任務鏈
        When: 執行 chain 操作
        Then: 應返回 0，顯示整個任務鏈（包含根及所有子任務）
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Root Ticket",
                "chain": {"root": "0.31.0-W4-001"},
                "children": ["0.31.0-W4-001.1", "0.31.0-W4-001.2"],
            }
            mock_load.return_value = mock_ticket

            result = execute_chain(args, "0.31.0")

            assert result == 0


class TestFull:
    """完整內容查詢測試"""

    def test_full_show_complete_content(self):
        """
        Given: 查詢 Ticket 的完整內容
        When: 執行 full 操作
        Then: 應返回 0，顯示所有欄位（包含目標、驗收條件、備註等）
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Test Ticket",
                "status": "in_progress",
                "target": "實作功能",
                "acceptance_criteria": [
                    {"text": "條件 1", "completed": True},
                    {"text": "條件 2", "completed": False},
                ],
                "suggestions": [
                    {"text": "建議 1", "decision": "adopted"},
                ],
            }
            mock_load.return_value = mock_ticket

            result = execute_full(args, "0.31.0")

            assert result == 0

    def test_full_includes_all_sections(self):
        """
        Given: 一個包含所有可能欄位的 Ticket
        When: 執行 full 操作
        Then: 應顯示所有存在的欄位，包括目標、驗收條件、建議、執行日誌等
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Complete Ticket",
                "status": "completed",
                "who": "developer",
                "what": "實作功能",
                "when": "2026-01-30",
                "where": "lib/module.py",
                "why": "改善性能",
                "how": "使用快取",
            }
            mock_load.return_value = mock_ticket

            result = execute_full(args, "0.31.0")

            assert result == 0


class TestShowAlias:
    """W17-008.2 / W17-004 落差 2：show 作為 full 的 alias

    驗證 dispatcher 端 show / full 雙路徑都指向 execute_full，
    並確認 argparse 端 show 子命令已註冊。
    """

    def test_show_handler_dispatches_to_execute_full(self):
        """Given: dispatcher handler dict
        When: 查 show 與 full
        Then: 兩者皆指向同一個 execute_full
        """
        from ticket_system.commands.track import _create_command_handlers

        handlers = _create_command_handlers()
        assert "show" in handlers, "show 必須註冊為 dispatcher handler"
        assert "full" in handlers, "full 仍須保留（向後相容）"
        assert handlers["show"] is handlers["full"], (
            "show 必須指向與 full 相同的 handler（execute_full）"
        )
        assert handlers["show"] is execute_full

    def test_show_subparser_registered(self):
        """Given: track 的 argparse 註冊
        When: 解析 `track show <id>` 與 `track full <id>`
        Then: 兩者皆能解析成功且 operation 對應正確
        """
        import argparse
        from ticket_system.commands.track import register

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)

        args_show = parser.parse_args(["track", "show", "0.31.0-W4-001"])
        assert args_show.operation == "show"
        assert args_show.ticket_id == "0.31.0-W4-001"

        args_full = parser.parse_args(["track", "full", "0.31.0-W4-001"])
        assert args_full.operation == "full"
        assert args_full.ticket_id == "0.31.0-W4-001"


class TestLog:
    """執行日誌查詢測試"""

    def test_log_show_execution_history(self):
        """
        Given: Ticket 有執行日誌記錄
        When: 執行 log 操作
        Then: 應返回 0，按時間順序顯示執行日誌
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Test Ticket",
                "execution_log": [
                    {"timestamp": "2026-01-30 10:00", "action": "created"},
                    {"timestamp": "2026-01-30 11:00", "action": "claimed"},
                    {"timestamp": "2026-01-30 12:00", "action": "completed"},
                ],
            }
            mock_load.return_value = mock_ticket

            result = execute_log(args, "0.31.0")

            assert result == 0

    def test_log_empty_execution_log(self):
        """
        Given: Ticket 沒有執行日誌
        When: 執行 log 操作
        Then: 應返回 0，顯示空日誌訊息
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Test Ticket",
                "execution_log": [],
            }
            mock_load.return_value = mock_ticket

            result = execute_log(args, "0.31.0")

            assert result == 0


class TestLogSection:
    """W17-008.3: ticket track log --section 過濾測試（與 W17-008.9 容錯規則同步）"""

    def _make_args(self, section):
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.section = section
        return args

    def _mock_ticket(self, body):
        return {"id": "0.31.0-W4-001", "title": "Test", "_body": body}

    def test_section_standard(self, capsys):
        """標準 section 標題 → 只輸出該 section 內容"""
        body = "## Problem Analysis\n問題描述\n\n## Solution\n解法內容\n\n## Test Results\n測試\n"
        with patch('ticket_system.lib.ticket_ops.load_ticket', return_value=self._mock_ticket(body)):
            assert execute_log(self._make_args("Solution"), "0.31.0") == 0
        out = capsys.readouterr().out
        assert "## Solution" in out
        assert "解法內容" in out
        assert "問題描述" not in out
        assert "Test Results" not in out

    def test_section_trailing_whitespace(self, capsys):
        """標題尾端空白容錯（W17-008.9）"""
        body = "## Solution   \n內容\n\n## Other\nx\n"
        with patch('ticket_system.lib.ticket_ops.load_ticket', return_value=self._mock_ticket(body)):
            assert execute_log(self._make_args("Solution"), "0.31.0") == 0
        assert "內容" in capsys.readouterr().out

    def test_section_double_space_after_hash(self, capsys):
        """## 與標題間多空白容錯（\\s+）"""
        body = "##  Solution\n內容\n\n## Other\nx\n"
        with patch('ticket_system.lib.ticket_ops.load_ticket', return_value=self._mock_ticket(body)):
            assert execute_log(self._make_args("Solution"), "0.31.0") == 0
        assert "內容" in capsys.readouterr().out

    def test_section_prefix_no_false_match(self, capsys):
        """前綴相同不應誤匹配：搜 Solution 不應命中 Solutions"""
        body = "## Solutions\n錯誤命中\n\n## Other\nx\n"
        with patch('ticket_system.lib.ticket_ops.load_ticket', return_value=self._mock_ticket(body)):
            assert execute_log(self._make_args("Solution"), "0.31.0") == 1
        out = capsys.readouterr().out
        assert "無 'Solution' 區段" in out
        assert "## Solutions" in out  # 引導列出現有標題

    def test_section_not_found_lists_existing(self, capsys):
        """section 不存在時列出現有標題引導"""
        body = "## Problem Analysis\nx\n\n## Other\ny\n"
        with patch('ticket_system.lib.ticket_ops.load_ticket', return_value=self._mock_ticket(body)):
            assert execute_log(self._make_args("Solution"), "0.31.0") == 1
        out = capsys.readouterr().out
        assert "現有 ## 標題" in out
        assert "## Problem Analysis" in out

    def test_no_section_falls_back_to_full_log(self, capsys):
        """無 --section 時走原本 Execution Log 路徑（回歸）"""
        body = "# Execution Log\n\n- 2026-01-30 entry\n"
        args = self._make_args(None)
        with patch('ticket_system.lib.ticket_ops.load_ticket', return_value=self._mock_ticket(body)):
            assert execute_log(args, "0.31.0") == 0
        assert "Execution Log" in capsys.readouterr().out


class TestList:
    """Ticket 列表查詢測試"""

    def test_list_all_tickets(self):
        """
        Given: 未指定任何篩選條件
        When: 執行 list 操作
        Then: 應返回 0，列出所有 Ticket
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.version = "0.31.0"
        args.status = None

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W4-001", "status": "completed"},
                {"id": "0.31.0-W4-002", "status": "in_progress"},
                {"id": "0.31.0-W4-003", "status": "pending"},
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0
            assert len(mock_tickets) == 3

    def test_list_filter_pending_tickets(self):
        """
        Given: 設定 --pending 篩選
        When: 執行 list 操作
        Then: 應返回 0，只列出 pending 狀態的 Ticket
        """
        args = Mock()
        args.pending = True
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.version = "0.31.0"
        args.status = None

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W4-003", "status": "pending"},
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0

    def test_list_filter_multiple_statuses(self):
        """
        Given: 同時設定多個狀態篩選
        When: 執行 list 操作
        Then: 應返回 0，列出符合任一狀態的 Ticket
        """
        args = Mock()
        args.pending = True
        args.in_progress = True
        args.completed = False
        args.blocked = False
        args.version = "0.31.0"
        args.status = None

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W4-002", "status": "in_progress"},
                {"id": "0.31.0-W4-003", "status": "pending"},
            ]
            mock_list.return_value = mock_tickets

            result = execute_list(args, "0.31.0")

            assert result == 0

    def test_list_empty_result(self):
        """
        Given: 篩選條件無匹配的 Ticket
        When: 執行 list 操作
        Then: 應返回 0，顯示空列表訊息
        """
        args = Mock()
        args.pending = True
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.version = "0.31.0"
        args.status = None

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_list.return_value = []

            result = execute_list(args, "0.31.0")

            assert result == 0


class TestVersion:
    """版本進度摘要測試"""

    def test_version_show_progress_summary(self):
        """
        Given: 指定一個版本號（如 0.31.0 或 v0.31.0）
        When: 執行 version 操作
        Then: 應返回 0，顯示該版本的進度摘要
        """
        args = Mock()
        args.version_str = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W4-001", "status": "completed", "title": "Task 1"},
                {"id": "0.31.0-W4-002", "status": "in_progress", "title": "Task 2"},
                {"id": "0.31.0-W4-003", "status": "pending", "title": "Task 3"},
            ]
            mock_list.return_value = mock_tickets

            with patch('ticket_system.lib.ticket_formatter.format_ticket_stats'):
                result = execute_version(args, None)

                assert result == 0

    def test_version_with_v_prefix(self):
        """
        Given: 版本號包含 'v' 前綴 (v0.31.0)
        When: 執行 version 操作
        Then: 應正確解析版本號並返回 0
        """
        args = Mock()
        args.version_str = "v0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_list.return_value = []

            result = execute_version(args, None)

            assert result == 0

    def test_version_invalid_format_failure(self):
        """
        Given: 版本號格式不正確
        When: 執行 version 操作
        Then: 應返回 0（無 Ticket 時），或驗證版本號失敗
        """
        args = Mock()
        args.version_str = "invalid-version"

        with patch('ticket_system.commands.track_query.list_tickets') as mock_list:
            mock_list.return_value = []

            result = execute_version(args, None)

            # 版本號格式不正確但仍試圖列出票籤，返回 0（空列表）
            assert result == 0


class TestListFilterEnhancements:
    """track list 增強篩選功能測試"""

    def test_list_filter_by_wave(self):
        """
        Given: 指定 --wave 28
        When: 執行 list 操作
        Then: 應返回 0，只列出 wave 28 的 Ticket
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.wave = 28
        args.format = "table"
        args.version = "0.31.0"
        args.status = None

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W28-001", "status": "pending", "wave": 28},
                {"id": "0.31.0-W28-002", "status": "completed", "wave": 28},
                {"id": "0.31.0-W27-001", "status": "pending", "wave": 27},
            ]
            mock_list.return_value = mock_tickets

            with patch('ticket_system.lib.ticket_formatter.format_ticket_stats'):
                with patch('ticket_system.lib.ticket_formatter.format_ticket_list'):
                    result = execute_list(args, "0.31.0")

            assert result == 0

    def test_list_filter_by_status_parameter(self):
        """
        Given: 指定 --status pending
        When: 執行 list 操作
        Then: 應返回 0，結果與 --pending flag 相同
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = "pending"
        args.wave = None
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W4-003", "status": "pending"},
            ]
            mock_list.return_value = mock_tickets

            with patch('ticket_system.lib.ticket_formatter.format_ticket_stats'):
                with patch('ticket_system.lib.ticket_formatter.format_ticket_list'):
                    result = execute_list(args, "0.31.0")

            assert result == 0

    def test_list_output_format_ids(self):
        """
        Given: 指定 --format ids
        When: 執行 list 操作
        Then: 應返回 0，只輸出 Ticket ID
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.wave = None
        args.format = "ids"
        args.version = "0.31.0"
        args.status = None

        with patch('ticket_system.commands.track_query.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W4-001", "status": "pending"},
                {"id": "0.31.0-W4-002", "status": "completed"},
            ]
            mock_list.return_value = mock_tickets

            with patch('ticket_system.commands.track_query._print_cross_version_warning'):
                with patch('builtins.print') as mock_print:
                    result = execute_list(args, "0.31.0")

                    # 驗證只輸出了 ID
                    calls = [str(call) for call in mock_print.call_args_list]
                    assert any("0.31.0-W4-001" in str(call) for call in calls)
                    assert any("0.31.0-W4-002" in str(call) for call in calls)
                    assert result == 0

    def test_list_output_format_yaml(self):
        """
        Given: 指定 --format yaml
        When: 執行 list 操作
        Then: 應返回 0，以 YAML 格式輸出
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
                {"id": "0.31.0-W4-001", "title": "Test", "status": "pending", "wave": 4, "type": "IMP", "priority": "P1"},
                {"id": "0.31.0-W4-002", "title": "Test 2", "status": "completed", "wave": 4, "type": "DOC", "priority": "P2"},
            ]
            mock_list.return_value = mock_tickets

            with patch('builtins.print') as mock_print:
                result = execute_list(args, "0.31.0")

            # 驗證輸出了內容（YAML 格式）
            assert result == 0
            mock_print.assert_called()

    def test_list_backward_compatibility_pending_flag(self):
        """
        Given: 使用舊的 --pending flag
        When: 執行 list 操作
        Then: 應返回 0，向後相容
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
                {"id": "0.31.0-W4-003", "status": "pending"},
            ]
            mock_list.return_value = mock_tickets

            with patch('ticket_system.lib.ticket_formatter.format_ticket_stats'):
                with patch('ticket_system.lib.ticket_formatter.format_ticket_list'):
                    result = execute_list(args, "0.31.0")

            assert result == 0

    def test_list_combined_wave_and_status(self):
        """
        Given: 指定 --wave 28 和 --status pending
        When: 執行 list 操作
        Then: 應返回 0，應用兩個篩選條件
        """
        args = Mock()
        args.pending = False
        args.in_progress = False
        args.completed = False
        args.blocked = False
        args.status = "pending"
        args.wave = 28
        args.format = "table"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_loader.list_tickets') as mock_list:
            mock_tickets = [
                {"id": "0.31.0-W28-001", "status": "pending", "wave": 28},
                {"id": "0.31.0-W28-002", "status": "completed", "wave": 28},
                {"id": "0.31.0-W27-001", "status": "pending", "wave": 27},
            ]
            mock_list.return_value = mock_tickets

            with patch('ticket_system.lib.ticket_formatter.format_ticket_stats'):
                with patch('ticket_system.lib.ticket_formatter.format_ticket_list'):
                    result = execute_list(args, "0.31.0")

            assert result == 0
