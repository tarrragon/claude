"""
track_fields 模組測試

測試 5W1H 相關欄位的 Ticket 操作：get/set who, what, when, where, why, how
"""

from typing import Dict, Any
from unittest.mock import Mock, patch

import pytest

# 注意：這些是預期的未來模組導入
# 目前在紅燈階段，這些模組尚未建立
from ticket_system.commands.fields import (
    execute_get_field,
    execute_set_field,
    execute_get_who,
    execute_set_who,
    execute_get_what,
    execute_set_what,
    execute_get_when,
    execute_set_when,
    execute_get_where,
    execute_set_where,
    execute_get_why,
    execute_set_why,
    execute_get_how,
    execute_set_how,
)


class TestGetField:
    """取得通用欄位測試"""

    def test_get_field_existing_field_success(self):
        """
        Given: Ticket 存在一個特定欄位
        When: 執行 get-field 操作
        Then: 應返回 0，並輸出欄位值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.field = "title"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Test Ticket",
                "status": "in_progress",
            }
            mock_load.return_value = mock_ticket

            result = execute_get_field(args, "0.31.0")

            assert result == 0

    def test_get_field_nonexistent_field_failure(self):
        """
        Given: Ticket 不存在指定的欄位
        When: 執行 get-field 操作
        Then: 應返回錯誤代碼 1，提示欄位不存在
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.field = "nonexistent_field"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Test Ticket",
            }
            mock_load.return_value = mock_ticket

            result = execute_get_field(args, "0.31.0")

            assert result == 1

    def test_get_field_ticket_not_found_failure(self):
        """
        Given: Ticket ID 不存在
        When: 執行 get-field 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.field = "title"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_load.return_value = None

            result = execute_get_field(args, "0.31.0")

            assert result == 1


class TestSetField:
    """設定通用欄位測試"""

    def test_set_field_success(self):
        """
        Given: Ticket 存在，且欄位值有效
        When: 執行 set-field 操作
        Then: 應返回 0，並更新欄位值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.field = "title"
        args.value = "New Title"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "title": "Old Title",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_set_field(args, "0.31.0")

                assert result == 0
                mock_save.assert_called_once()
                saved_ticket = mock_save.call_args[0][0]
                assert saved_ticket["title"] == "New Title"

    def test_set_field_nonexistent_ticket_failure(self):
        """
        Given: Ticket ID 不存在
        When: 執行 set-field 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.field = "title"
        args.value = "New Title"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_load.return_value = None

            result = execute_set_field(args, "0.31.0")

            assert result == 1

    def test_set_field_empty_value_success(self):
        """
        Given: 設定欄位值為空字串
        When: 執行 set-field 操作
        Then: 應返回 0，清空欄位值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.field = "description"
        args.value = ""
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "description": "Old Description",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_set_field(args, "0.31.0")

                assert result == 0


class TestWhoField:
    """Who 欄位 (5W1H) 測試"""

    def test_get_who_success(self):
        """
        Given: Ticket 存在 who 欄位
        When: 執行 get-who 操作
        Then: 應返回 0，輸出 who 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "who": "sage-test-architect",
            }
            mock_load.return_value = mock_ticket

            result = execute_get_who(args, "0.31.0")

            assert result == 0

    def test_set_who_success(self):
        """
        Given: 設定 Ticket 的 who 欄位
        When: 執行 set-who 操作
        Then: 應返回 0，更新 who 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.value = "parsley-flutter-developer"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            # who 為 dict 結構（W10-086 修復後的正確格式）
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "who": {"current": "sage-test-architect", "history": {}},
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_set_who(args, "0.31.0")

                assert result == 0
                saved_ticket = mock_save.call_args[0][0]
                # set-who 僅更新 who.current，保留 dict 結構（W10-088 修復：防止壓扁）
                assert isinstance(saved_ticket["who"], dict)
                assert saved_ticket["who"]["current"] == "parsley-flutter-developer"
                assert "history" in saved_ticket["who"]


class TestWhatField:
    """What 欄位 (5W1H) 測試"""

    def test_get_what_success(self):
        """
        Given: Ticket 存在 what 欄位
        When: 執行 get-what 操作
        Then: 應返回 0，輸出 what 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "what": "設計測試案例",
            }
            mock_load.return_value = mock_ticket

            result = execute_get_what(args, "0.31.0")

            assert result == 0

    def test_set_what_success(self):
        """
        Given: 設定 Ticket 的 what 欄位
        When: 執行 set-what 操作
        Then: 應返回 0，更新 what 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.value = "實作測試模組"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "what": "設計測試案例",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_set_what(args, "0.31.0")

                assert result == 0
                saved_ticket = mock_save.call_args[0][0]
                assert saved_ticket["what"] == "實作測試模組"


class TestWhenField:
    """When 欄位 (5W1H) 測試"""

    def test_get_when_success(self):
        """
        Given: Ticket 存在 when 欄位
        When: 執行 get-when 操作
        Then: 應返回 0，輸出 when 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "when": "2026-01-30",
            }
            mock_load.return_value = mock_ticket

            result = execute_get_when(args, "0.31.0")

            assert result == 0

    def test_set_when_success(self):
        """
        Given: 設定 Ticket 的 when 欄位
        When: 執行 set-when 操作
        Then: 應返回 0，更新 when 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.value = "2026-02-01"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "when": "2026-01-30",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_set_when(args, "0.31.0")

                assert result == 0
                saved_ticket = mock_save.call_args[0][0]
                assert saved_ticket["when"] == "2026-02-01"


class TestWhereField:
    """Where 欄位 (5W1H) 測試"""

    def test_get_where_success(self):
        """
        Given: Ticket 存在 where 欄位
        When: 執行 get-where 操作
        Then: 應返回 0，輸出 where 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "where": "tests/",
            }
            mock_load.return_value = mock_ticket

            result = execute_get_where(args, "0.31.0")

            assert result == 0

    def test_set_where_success(self):
        """
        Given: 設定 Ticket 的 where 欄位
        When: 執行 set-where 操作
        Then: 應返回 0，更新 where 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.value = "lib/commands/"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            # where 為 dict 結構（W10-086 修復後的正確格式）
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "where": {"layer": "tests/", "files": ["tests/test_a.py"]},
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_set_where(args, "0.31.0")

                assert result == 0
                saved_ticket = mock_save.call_args[0][0]
                # set-where 僅更新 where.layer，保留 files（W10-088 修復：防止壓扁）
                assert isinstance(saved_ticket["where"], dict)
                assert saved_ticket["where"]["layer"] == "lib/commands/"
                assert saved_ticket["where"]["files"] == ["tests/test_a.py"]


class TestWhyField:
    """Why 欄位 (5W1H) 測試"""

    def test_get_why_success(self):
        """
        Given: Ticket 存在 why 欄位
        When: 執行 get-why 操作
        Then: 應返回 0，輸出 why 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "why": "改善程式碼品質",
            }
            mock_load.return_value = mock_ticket

            result = execute_get_why(args, "0.31.0")

            assert result == 0

    def test_set_why_success(self):
        """
        Given: 設定 Ticket 的 why 欄位
        When: 執行 set-why 操作
        Then: 應返回 0，更新 why 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.value = "支援完整 TDD 流程"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "why": "改善程式碼品質",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_set_why(args, "0.31.0")

                assert result == 0
                saved_ticket = mock_save.call_args[0][0]
                assert saved_ticket["why"] == "支援完整 TDD 流程"


class TestHowField:
    """How 欄位 (5W1H) 測試"""

    def test_get_how_success(self):
        """
        Given: Ticket 存在 how 欄位
        When: 執行 get-how 操作
        Then: 應返回 0，輸出 how 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "how": "使用模組拆分",
            }
            mock_load.return_value = mock_ticket

            result = execute_get_how(args, "0.31.0")

            assert result == 0

    def test_set_how_success(self):
        """
        Given: 設定 Ticket 的 how 欄位
        When: 執行 set-how 操作
        Then: 應返回 0，更新 how 值
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.value = "按層級和功能拆分"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            # how 為 dict 結構（W10-086 修復後的正確格式）
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "how": {"task_type": "Implementation", "strategy": "使用模組拆分"},
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_set_how(args, "0.31.0")

                assert result == 0
                saved_ticket = mock_save.call_args[0][0]
                # set-how 僅更新 how.strategy，保留 task_type（W10-088 修復：防止壓扁）
                assert isinstance(saved_ticket["how"], dict)
                assert saved_ticket["how"]["strategy"] == "按層級和功能拆分"
                assert saved_ticket["how"]["task_type"] == "Implementation"


class TestDictFieldFlattenRegression:
    """W10-088 regression：set-who/set-where/set-how 對 dict 結構欄位的三種場景。

    覆蓋 dict（正常）/ 已壓扁為 string（降級復原）/ 缺失欄位（初始化）三種情境。
    """

    def _run_set(self, executor, field_name: str, subkey: str, new_value: str,
                 initial_ticket: Dict[str, Any]) -> Dict[str, Any]:
        """共用 helper：執行 set-* 並回傳被 save 的 ticket。"""
        args = Mock()
        args.ticket_id = "0.31.0-W4-099"
        args.value = new_value
        args.version = "0.31.0"
        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_load.return_value = dict(initial_ticket)
            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = executor(args, "0.31.0")
                assert result == 0
                return mock_save.call_args[0][0]

    def test_set_who_preserves_history_when_dict(self):
        """Given who={current,history}, when set-who, then only current updated."""
        saved = self._run_set(
            execute_set_who, "who", "current", "new-agent",
            {"id": "x", "who": {"current": "old-agent", "history": {"t0": "old-agent"}}},
        )
        assert saved["who"]["current"] == "new-agent"
        assert saved["who"]["history"] == {"t0": "old-agent"}

    def test_set_who_recovers_dict_when_flattened_string(self):
        """Given who 已壓扁為 string（legacy 資料），when set-who, then 重建為 dict。"""
        saved = self._run_set(
            execute_set_who, "who", "current", "recovered",
            {"id": "x", "who": "legacy-flattened"},
        )
        assert isinstance(saved["who"], dict)
        assert saved["who"]["current"] == "recovered"
        assert "history" in saved["who"]

    def test_set_where_preserves_files(self):
        """Given where={layer,files}, when set-where, then only layer updated, files 保留。"""
        saved = self._run_set(
            execute_set_where, "where", "layer", "新層級",
            {"id": "x", "where": {"layer": "舊層級", "files": ["a.py", "b.py"]}},
        )
        assert saved["where"]["layer"] == "新層級"
        assert saved["where"]["files"] == ["a.py", "b.py"]

    def test_set_how_preserves_task_type(self):
        """Given how={task_type,strategy}, when set-how, then only strategy updated。"""
        saved = self._run_set(
            execute_set_how, "how", "strategy", "新策略",
            {"id": "x", "how": {"task_type": "Analysis", "strategy": "舊策略"}},
        )
        assert saved["how"]["strategy"] == "新策略"
        assert saved["how"]["task_type"] == "Analysis"

    def test_set_what_scalar_field_unchanged(self):
        """Given what（非 dict 欄位）, when set-what, then 直接覆寫 string。"""
        saved = self._run_set(
            execute_set_what, "what", "", "新描述",
            {"id": "x", "what": "舊描述"},
        )
        assert saved["what"] == "新描述"
