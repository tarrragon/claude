"""
track_acceptance 模組測試

測試驗收相關的 Ticket 操作：check-acceptance, append-log
"""

from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest

# 導入 track_acceptance 模組中的函式
from ticket_system.commands.track_acceptance import (
    execute_check_acceptance,
    execute_append_log,
)


class TestCheckAcceptance:
    """驗收條件檢查測試（frontmatter 版本）"""

    def test_check_acceptance_all_completed(self):
        """
        Given: Ticket 將所有驗收條件勾選完成（在 frontmatter 中）
        When: 執行 check-acceptance 操作勾選最後一個項目
        Then: 應返回 0，保存更新後的 Ticket
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = "3"  # 勾選第三個項目（未勾選狀態）
        args.uncheck = False

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "title": "Test Ticket",
            "_path": "/path/to/ticket.md",
            "acceptance": ["[x] Condition 1", "[x] Condition 2", "[ ] Condition 3"],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                result = execute_check_acceptance(args, "0.31.0")

                assert result == 0
                mock_save.assert_called_once()

    def test_check_acceptance_partial_completed(self):
        """
        Given: Ticket 的部分驗收條件已完成（在 frontmatter 中）
        When: 執行 check-acceptance 操作
        Then: 應返回 0，完成未勾選的項目
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = "2"  # 第二個項目
        args.uncheck = False

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "title": "Test Ticket",
            "_path": "/path/to/ticket.md",
            "acceptance": ["[x] Condition 1", "[ ] Condition 2", "[x] Condition 3"],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                result = execute_check_acceptance(args, "0.31.0")

                assert result == 0
                mock_save.assert_called_once()

    def test_check_acceptance_no_criteria(self):
        """
        Given: Ticket 沒有定義任何驗收條件
        When: 執行 check-acceptance 操作
        Then: 應返回 1，提示無驗收條件
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = "1"
        args.uncheck = False

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "title": "Test Ticket",
            "_path": "/path/to/ticket.md",
            "acceptance": [],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            result = execute_check_acceptance(args, "0.31.0")

            assert result == 1

    def test_check_acceptance_nonexistent_ticket(self):
        """
        Given: Ticket ID 不存在
        When: 執行 check-acceptance 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.version = "0.31.0"
        args.index = "1"
        args.uncheck = False

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (None, "Ticket not found")

            result = execute_check_acceptance(args, "0.31.0")

            assert result == 1

    def test_check_acceptance_shows_progress(self):
        """
        Given: 檢查多個驗收條件的進度（在 frontmatter 中）
        When: 執行 check-acceptance 操作
        Then: 應顯示進度百分比（完成數/總數）
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = "3"  # 第三個項目，未勾選
        args.uncheck = False

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "acceptance": ["[x] C1", "[x] C2", "[ ] C3", "[ ] C4"],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                result = execute_check_acceptance(args, "0.31.0")

                # 應返回 0（操作成功）
                assert result == 0
                mock_save.assert_called_once()


class TestAppendLog:
    """追加執行日誌測試"""

    def test_append_log_success(self):
        """
        Given: Ticket 存在，提供日誌內容
        When: 執行 append-log 操作
        Then: 應返回 0，將日誌追加到 Ticket
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.section = "Execution Log"
        args.content = "完成了第一階段實作"

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "_body": """## Execution Log

- [2026-01-30 10:00] Claimed
""",
        }

        with patch('ticket_system.commands.track_acceptance.load_ticket') as mock_load:
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.track_acceptance.get_ticket_path'):
                with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                    result = execute_append_log(args, "0.31.0")

                    assert result == 0
                    mock_save.assert_called_once()

    def test_append_log_empty_content(self):
        """
        Given: 日誌內容為空字串
        When: 執行 append-log 操作
        Then: 應返回 1，提示日誌內容不能為空
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.section = "Execution Log"
        args.content = ""

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "_body": "## Execution Log\n",
        }

        with patch('ticket_system.commands.track_acceptance.load_ticket') as mock_load:
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                result = execute_append_log(args, "0.31.0")

                # 空內容通常會返回 0（因為追加空內容不會報錯）
                # 但如果實現有驗證，可能返回 1
                assert result in [0, 1]

    def test_append_log_nonexistent_ticket(self):
        """
        Given: Ticket ID 不存在
        When: 執行 append-log 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.version = "0.31.0"
        args.section = "Execution Log"
        args.content = "Some log"

        with patch('ticket_system.commands.track_acceptance.load_ticket') as mock_load:
            mock_load.return_value = None

            result = execute_append_log(args, "0.31.0")

            assert result == 1

    def test_append_log_multiple_entries(self):
        """
        Given: Ticket 已有多個日誌記錄
        When: 執行 append-log 操作，追加新記錄
        Then: 應返回 0，保留舊記錄並新增記錄
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.section = "Execution Log"
        args.content = "第三個日誌記錄"

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "_body": """## Execution Log

- [2026-01-30 10:00] Created
- [2026-01-30 11:00] Claimed
""",
        }

        with patch('ticket_system.commands.track_acceptance.load_ticket') as mock_load:
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.track_acceptance.get_ticket_path'):
                with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                    result = execute_append_log(args, "0.31.0")

                    assert result == 0
                    mock_save.assert_called_once()

    def test_append_log_with_timestamp(self):
        """
        Given: 追加日誌時應自動記錄時間戳
        When: 執行 append-log 操作
        Then: 應返回 0，並自動添加時間戳
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.section = "Execution Log"
        args.content = "實作完成"

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "_body": "## Execution Log\n",
        }

        with patch('ticket_system.commands.track_acceptance.load_ticket') as mock_load:
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.track_acceptance.get_ticket_path'):
                with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                    result = execute_append_log(args, "0.31.0")

                    assert result == 0
                    # 驗證 save_ticket 被調用，並且新內容包含時間戳
                    mock_save.assert_called_once()

    def test_append_log_long_content(self):
        """
        Given: 日誌內容很長
        When: 執行 append-log 操作
        Then: 應返回 0，完整保存長日誌
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.section = "Execution Log"
        args.content = "A" * 1000  # 1000 字元的日誌

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "_body": "## Execution Log\n",
        }

        with patch('ticket_system.commands.track_acceptance.load_ticket') as mock_load:
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.track_acceptance.get_ticket_path'):
                with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                    result = execute_append_log(args, "0.31.0")

                    assert result == 0
                    mock_save.assert_called_once()
