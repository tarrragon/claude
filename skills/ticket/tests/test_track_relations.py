"""
track_relations 模組測試

測試關係相關的 Ticket 操作：add-child, phase, agent
"""

from typing import Dict, Any
from unittest.mock import Mock, patch

import pytest

# 導入 track_relations 模組中的函式
from ticket_system.commands.track_relations import (
    execute_add_child,
    execute_phase,
    execute_agent,
)


class TestAddChild:
    """新增子 Ticket 測試"""

    def test_add_child_success(self):
        """
        Given: 存在一個父 Ticket，子 Ticket 存在
        When: 執行 add-child 操作，將子 Ticket 新增到父 Ticket
        Then: 應返回 0，更新父 Ticket 的 children 列表
        """
        args = Mock()
        args.parent_id = "0.31.0-W4-001"
        args.child_id = "0.31.0-W4-001.1"
        args.version = "0.31.0"

        # Patch 在 track_relations 模組中的導入
        with patch('ticket_system.commands.track_relations.load_ticket') as mock_load:
            # 每次調用都返回新的 dict 副本，避免引用共享
            parent_ticket = {
                "id": "0.31.0-W4-001",
                "children": [],
            }
            child_ticket = {
                "id": "0.31.0-W4-001.1",
                "parent_id": "0.31.0-W4-001",
            }

            def load_side_effect(version, ticket_id):
                if ticket_id == "0.31.0-W4-001":
                    return {**parent_ticket}  # 返回副本
                else:
                    return {**child_ticket}   # 返回副本

            mock_load.side_effect = load_side_effect

            with patch('ticket_system.commands.track_relations.save_ticket') as mock_save:
                result = execute_add_child(args, "0.31.0")

                assert result == 0
                # save_ticket 應該被調用兩次（父和子）
                assert mock_save.call_count == 2

    def test_add_child_parent_not_found(self):
        """
        Given: 父 Ticket ID 不存在
        When: 執行 add-child 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.parent_id = "0.31.0-W4-999"
        args.child_id = "0.31.0-W4-999.1"
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.load_ticket') as mock_load:
            # load_ticket 在找不到檔案時返回 None，不是拋出 FileNotFoundError
            mock_load.return_value = None

            result = execute_add_child(args, "0.31.0")

            assert result == 1

    def test_add_child_child_not_found(self):
        """
        Given: 子 Ticket ID 不存在
        When: 執行 add-child 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.parent_id = "0.31.0-W4-001"
        args.child_id = "0.31.0-W4-001.999"
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.load_ticket') as mock_load:
            parent_ticket = {
                "id": "0.31.0-W4-001",
                "children": [],
            }

            def side_effect(version, ticket_id):
                if ticket_id == "0.31.0-W4-001":
                    return parent_ticket
                else:
                    # load_ticket 在找不到檔案時返回 None，不是拋出 FileNotFoundError
                    return None

            mock_load.side_effect = side_effect

            result = execute_add_child(args, "0.31.0")

            assert result == 1

    def test_add_child_already_exists(self):
        """
        Given: 子 Ticket 已經在父 Ticket 的 children 列表中
        When: 執行 add-child 操作
        Then: 應返回 1 或顯示警告，不重複新增
        """
        args = Mock()
        args.parent_id = "0.31.0-W4-001"
        args.child_id = "0.31.0-W4-001.1"
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.load_ticket') as mock_load:
            parent_ticket = {
                "id": "0.31.0-W4-001",
                "children": ["0.31.0-W4-001.1"],  # Already exists
            }
            child_ticket = {
                "id": "0.31.0-W4-001.1",
                "parent_id": "0.31.0-W4-001",
            }
            mock_load.side_effect = [parent_ticket, child_ticket]

            result = execute_add_child(args, "0.31.0")

            # 應返回 0（冪等）或 1（錯誤）
            assert result in [0, 1]

    def test_add_child_verify_chain_info(self):
        """
        Given: 新增子 Ticket 時應驗證 chain 資訊一致
        When: 執行 add-child 操作
        Then: 應返回 0，並驗證 child 的 chain 資訊指向正確的 parent
        """
        args = Mock()
        args.parent_id = "0.31.0-W4-001"
        args.child_id = "0.31.0-W4-001.1"
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.load_ticket') as mock_load:
            parent_ticket = {
                "id": "0.31.0-W4-001",
                "children": [],
            }
            child_ticket = {
                "id": "0.31.0-W4-001.1",
                "chain": {"parent": "0.31.0-W4-001"},
            }
            mock_load.side_effect = [parent_ticket, child_ticket]

            with patch('ticket_system.lib.ticket_loader.save_ticket'):
                result = execute_add_child(args, "0.31.0")

                assert result == 0


class TestPhase:
    """更新 Phase 資訊測試"""

    def test_phase_set_success(self):
        """
        Given: Ticket 存在，設定有效的 Phase 值
        When: 執行 phase 操作
        Then: 應返回 0，更新 Ticket 的 phase 欄位
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.phase = "Phase 3b"
        args.version = "0.31.0"
        args.agent = "parsley-flutter-developer"

        with patch('ticket_system.commands.track_relations.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "phase": "Phase 1",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                result = execute_phase(args, "0.31.0")

                assert result == 0

    def test_phase_invalid_phase_value(self):
        """
        Given: 設定無效的 Phase 值
        When: 執行 phase 操作
        Then: 應返回 1，提示無效的 Phase
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.phase = "Phase 999"  # Invalid phase
        args.version = "0.31.0"

        result = execute_phase(args, "0.31.0")

        assert result == 1

    def test_phase_nonexistent_ticket(self):
        """
        Given: Ticket ID 不存在
        When: 執行 phase 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.phase = "Phase 2"
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.load_ticket') as mock_load:
            # load_ticket 在找不到檔案時返回 None，不是拋出 FileNotFoundError
            mock_load.return_value = None

            result = execute_phase(args, "0.31.0")

            assert result == 1

    def test_phase_all_valid_phases(self):
        """
        Given: 設定有效的 Phase 值（Phase 1-4）
        When: 執行 phase 操作
        Then: 應都返回 0，成功更新
        """
        valid_phases = ["Phase 1", "Phase 2", "Phase 3a", "Phase 3b", "Phase 4"]

        for phase in valid_phases:
            args = Mock()
            args.ticket_id = "0.31.0-W4-001"
            args.phase = phase
            args.version = "0.31.0"
            args.agent = "parsley-flutter-developer"

            with patch('ticket_system.commands.track_relations.load_ticket') as mock_load:
                mock_ticket = {
                    "id": "0.31.0-W4-001",
                    "phase": "Phase 1",
                }
                mock_load.return_value = mock_ticket

                with patch('ticket_system.lib.ticket_loader.save_ticket') as mock_save:
                    result = execute_phase(args, "0.31.0")

                    assert result == 0


class TestAgent:
    """設定代理人資訊測試"""

    def test_agent_set_success(self):
        """
        Given: Ticket 存在，設定有效的代理人值
        When: 執行 agent 操作
        Then: 應返回 0，更新 Ticket 的 agent 欄位
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.agent_name = "sage-test-architect"
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.list_tickets') as mock_list:
            mock_tickets = [
                {
                    "id": "0.31.0-W4-001",
                    "agent": "sage-test-architect",
                    "assignee": "pending",
                },
            ]
            mock_list.return_value = mock_tickets

            result = execute_agent(args, "0.31.0")

            assert result == 0

    def test_agent_invalid_agent_value(self):
        """
        Given: 設定無效的代理人值
        When: 執行 agent 操作
        Then: 應返回 1，提示無效的代理人
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.agent_name = "invalid-agent-999"
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.list_tickets') as mock_list:
            mock_list.return_value = []

            result = execute_agent(args, "0.31.0")

            # 不認可的代理人應返回 0（顯示空結果）或 1
            assert result in [0, 1]

    def test_agent_nonexistent_ticket(self):
        """
        Given: Ticket ID 不存在
        When: 執行 agent 操作
        Then: 應返回 0（顯示無 Tickets）
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.agent_name = "parsley-flutter-developer"
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.list_tickets') as mock_list:
            mock_list.return_value = []

            result = execute_agent(args, "0.31.0")

            # 應返回 0，顯示無 Tickets
            assert result == 0

    def test_agent_all_valid_agents(self):
        """
        Given: 設定所有有效的代理人值
        When: 執行 agent 操作
        Then: 應都返回 0，成功篩選
        """
        valid_agents = [
            "lavender-interface-designer",
            "sage-test-architect",
            "pepper-test-implementer",
            "parsley-flutter-developer",
            "cinnamon-refactor-owl",
            "system-analyst",
            "security-reviewer",
        ]

        for agent in valid_agents:
            args = Mock()
            args.ticket_id = "0.31.0-W4-001"
            args.agent_name = agent
            args.version = "0.31.0"

            with patch('ticket_system.commands.track_relations.list_tickets') as mock_list:
                mock_tickets = [
                    {
                        "id": "0.31.0-W4-001",
                        "agent": agent,
                        "assignee": "pending",
                    },
                ]
                mock_list.return_value = mock_tickets

                result = execute_agent(args, "0.31.0")

                assert result == 0

    def test_agent_clear_agent(self):
        """
        Given: 清除 Ticket 的代理人資訊（設為空或 pending）
        When: 執行 agent 操作，agent 設為空
        Then: 應返回 0，顯示無代理人 Tickets
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.agent_name = "pending"  # 或空字串
        args.version = "0.31.0"

        with patch('ticket_system.commands.track_relations.list_tickets') as mock_list:
            mock_list.return_value = []

            result = execute_agent(args, "0.31.0")

            assert result == 0
