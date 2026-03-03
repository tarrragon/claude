"""
測試模組 C: set-blocked-by / set-related-to

驗證：
1. C-1: set-blocked-by 替換模式
2. C-2: set-blocked-by --add 追加模式
3. C-3: set-blocked-by --remove 移除模式
4. C-4: set-related-to 成功設定
5. C-5: 不存在的 Ticket ID 報錯（Fail Fast）
6. C-6: 追加重複 ID → idempotent
"""

import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def sample_ticket_for_relations() -> dict:
    """用於測試關係欄位的 Ticket 樣本"""
    return {
        "id": "0.1.0-W1-001",
        "title": "Task with relations",
        "status": "in_progress",
        "what": "Test description",
        "blockedBy": [],
        "relatedTo": [],
    }


@pytest.fixture
def sample_ticket_with_blockers() -> dict:
    """已有 blockedBy 的 Ticket 樣本"""
    return {
        "id": "0.1.0-W1-001",
        "title": "Task with blockers",
        "status": "in_progress",
        "what": "Test description",
        "blockedBy": ["0.1.0-W1-002"],
        "relatedTo": [],
    }


@pytest.fixture
def sample_blocking_tickets() -> dict:
    """被引用的 Ticket 樣本"""
    return {
        "0.1.0-W1-002": {"id": "0.1.0-W1-002", "status": "pending"},
        "0.1.0-W1-003": {"id": "0.1.0-W1-003", "status": "completed"},
    }


class TestSetBlockedBy:
    """set-blocked-by 測試組"""

    def test_set_blocked_by_replace_mode(
        self,
        sample_ticket_for_relations: dict,
        sample_blocking_tickets: dict,
    ) -> None:
        """C-1: set-blocked-by 替換模式"""
        from ticket_system.commands.track_relations import _execute_set_relation_field

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            value="0.1.0-W1-002 0.1.0-W1-003",
            add=False,
            remove=False,
        )

        def mock_load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.1.0-W1-001":
                return sample_ticket_for_relations
            return sample_blocking_tickets.get(ticket_id)

        with patch("ticket_system.commands.track_relations.load_ticket") as mock_load:
            with patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
                with patch("ticket_system.commands.track_relations.get_ticket_path"):
                    mock_load.side_effect = mock_load_ticket_side_effect

                    result = _execute_set_relation_field(args, "0.1.0", "blockedBy")

                    assert result == 0
                    # 驗證 save_ticket 被呼叫
                    mock_save.assert_called_once()
                    # 驗證更新的值
                    saved_ticket = mock_save.call_args[0][0]
                    assert saved_ticket["blockedBy"] == ["0.1.0-W1-002", "0.1.0-W1-003"]

    def test_set_blocked_by_add_mode(
        self,
        sample_ticket_with_blockers: dict,
        sample_blocking_tickets: dict,
    ) -> None:
        """C-2: set-blocked-by --add 追加模式"""
        from ticket_system.commands.track_relations import _execute_set_relation_field

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            value="0.1.0-W1-003",
            add=True,
            remove=False,
        )

        def mock_load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.1.0-W1-001":
                return sample_ticket_with_blockers
            return sample_blocking_tickets.get(ticket_id)

        with patch("ticket_system.commands.track_relations.load_ticket") as mock_load:
            with patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
                with patch("ticket_system.commands.track_relations.get_ticket_path"):
                    mock_load.side_effect = mock_load_ticket_side_effect

                    result = _execute_set_relation_field(args, "0.1.0", "blockedBy")

                    assert result == 0
                    mock_save.assert_called_once()
                    saved_ticket = mock_save.call_args[0][0]
                    # 應該保留 002 並新增 003
                    assert "0.1.0-W1-002" in saved_ticket["blockedBy"]
                    assert "0.1.0-W1-003" in saved_ticket["blockedBy"]
                    assert len(saved_ticket["blockedBy"]) == 2

    def test_set_blocked_by_remove_mode(
        self,
        sample_blocking_tickets: dict,
    ) -> None:
        """C-3: set-blocked-by --remove 移除模式"""
        from ticket_system.commands.track_relations import _execute_set_relation_field

        ticket_with_multiple_blockers = {
            "id": "0.1.0-W1-001",
            "blockedBy": ["0.1.0-W1-002", "0.1.0-W1-003"],
        }

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            value="0.1.0-W1-002",
            add=False,
            remove=True,
        )

        def mock_load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.1.0-W1-001":
                return ticket_with_multiple_blockers
            return sample_blocking_tickets.get(ticket_id)

        with patch("ticket_system.commands.track_relations.load_ticket") as mock_load:
            with patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
                with patch("ticket_system.commands.track_relations.get_ticket_path"):
                    mock_load.side_effect = mock_load_ticket_side_effect

                    result = _execute_set_relation_field(args, "0.1.0", "blockedBy")

                    assert result == 0
                    mock_save.assert_called_once()
                    saved_ticket = mock_save.call_args[0][0]
                    # 應該只剩 003
                    assert saved_ticket["blockedBy"] == ["0.1.0-W1-003"]

    def test_set_blocked_by_fail_fast_ticket_not_found(
        self,
        sample_ticket_for_relations: dict,
    ) -> None:
        """C-5: 不存在的 Ticket ID 報錯（Fail Fast）"""
        from ticket_system.commands.track_relations import _execute_set_relation_field

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            value="0.1.0-W1-999",  # 不存在的 Ticket
            add=False,
            remove=False,
        )

        def mock_load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.1.0-W1-001":
                return sample_ticket_for_relations
            return None  # 不存在的 Ticket

        with patch("ticket_system.commands.track_relations.load_ticket") as mock_load:
            with patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
                mock_load.side_effect = mock_load_ticket_side_effect

                result = _execute_set_relation_field(args, "0.1.0", "blockedBy")

                # 應該失敗
                assert result == 1
                # 不應該保存
                mock_save.assert_not_called()

    def test_set_blocked_by_add_duplicate_idempotent(
        self,
        sample_ticket_with_blockers: dict,
        sample_blocking_tickets: dict,
    ) -> None:
        """C-6: 追加重複 ID → idempotent"""
        from ticket_system.commands.track_relations import _execute_set_relation_field

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            value="0.1.0-W1-002",  # 已經存在的 ID
            add=True,
            remove=False,
        )

        def mock_load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.1.0-W1-001":
                return sample_ticket_with_blockers
            return sample_blocking_tickets.get(ticket_id)

        with patch("ticket_system.commands.track_relations.load_ticket") as mock_load:
            with patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
                with patch("ticket_system.commands.track_relations.get_ticket_path"):
                    mock_load.side_effect = mock_load_ticket_side_effect

                    result = _execute_set_relation_field(args, "0.1.0", "blockedBy")

                    assert result == 0
                    mock_save.assert_called_once()
                    saved_ticket = mock_save.call_args[0][0]
                    # 不應該重複
                    assert saved_ticket["blockedBy"] == ["0.1.0-W1-002"]


class TestSetRelatedTo:
    """set-related-to 測試組"""

    def test_set_related_to_success(
        self,
        sample_ticket_for_relations: dict,
        sample_blocking_tickets: dict,
    ) -> None:
        """C-4: set-related-to 成功設定"""
        from ticket_system.commands.track_relations import _execute_set_relation_field

        args = argparse.Namespace(
            ticket_id="0.1.0-W1-001",
            value="0.1.0-W1-002 0.1.0-W1-003",
            add=False,
            remove=False,
        )

        def mock_load_ticket_side_effect(version, ticket_id):
            if ticket_id == "0.1.0-W1-001":
                return sample_ticket_for_relations
            return sample_blocking_tickets.get(ticket_id)

        with patch("ticket_system.commands.track_relations.load_ticket") as mock_load:
            with patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
                with patch("ticket_system.commands.track_relations.get_ticket_path"):
                    mock_load.side_effect = mock_load_ticket_side_effect

                    result = _execute_set_relation_field(args, "0.1.0", "relatedTo")

                    assert result == 0
                    mock_save.assert_called_once()
                    saved_ticket = mock_save.call_args[0][0]
                    assert saved_ticket["relatedTo"] == ["0.1.0-W1-002", "0.1.0-W1-003"]
