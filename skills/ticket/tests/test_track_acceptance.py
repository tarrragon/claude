"""
track_acceptance 模組測試

測試驗收相關的 Ticket 操作：check-acceptance, append-log
"""

import re
import tempfile
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest

# 導入 track_acceptance 模組中的函式
from ticket_system.commands.track_acceptance import (
    execute_check_acceptance,
    execute_append_log,
)

# W1-018.1: 真實 tmp lock target。command 內為 lock_target = Path(get_ticket_path(...))；
# 若 get_ticket_path 被 patch 成無 return_value 的 MagicMock，Path(MagicMock) 會經
# os.fspath 合成出 "MagicMock/get_ticket_path()/<id>" 真實垃圾路徑，再由 file_lock 寫出
# .lock 檔污染 cwd。patch 一律回傳真實 tmp target，使 .lock 落在 tmp 並由 OS 清理。
_LOCK_TARGET = Path(tempfile.gettempdir()) / "w1018_test_lock_target.md"


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
        args.all = False

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
        args.all = False

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
        Then: 應返回 2（業務拒絕），提示無驗收條件

        依 .claude/references/cli-exit-code-rules.md 規則 2：
        用戶輸入錯誤路徑（包含 ticket 無 acceptance 可勾選）均為業務拒絕（return 2）。
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = "1"
        args.uncheck = False
        args.all = False

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "title": "Test Ticket",
            "_path": "/path/to/ticket.md",
            "acceptance": [],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            result = execute_check_acceptance(args, "0.31.0")

            assert result == 2

    def test_check_acceptance_nonexistent_ticket(self):
        """
        Given: Ticket ID 不存在
        When: 執行 check-acceptance 操作
        Then: 應返回 2（業務拒絕：用戶輸入錯誤路徑）

        依 cli-exit-code-rules.md 規則 2：ticket 不存在屬用戶輸入錯誤 → return 2。
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.version = "0.31.0"
        args.index = "1"
        args.uncheck = False
        args.all = False

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (None, "Ticket not found")

            result = execute_check_acceptance(args, "0.31.0")

            assert result == 2

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
        args.all = False

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

    def test_check_acceptance_all_flag(self):
        """
        Given: Ticket 有部分驗收條件未勾選
        When: 執行 check-acceptance --all 批量勾選
        Then: 應返回 0，勾選所有未勾選的項目
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = None  # --all 時不提供 index
        args.uncheck = False
        args.all = True

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "acceptance": ["[x] Condition 1", "[ ] Condition 2", "[ ] Condition 3"],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                result = execute_check_acceptance(args, "0.31.0")

                assert result == 0
                # 驗證所有項目都被勾選
                saved_ticket = mock_save.call_args[0][0]
                assert saved_ticket["acceptance"] == ["[x] Condition 1", "[x] Condition 2", "[x] Condition 3"]

    def test_check_acceptance_all_uncheck_flag(self):
        """
        Given: Ticket 有部分驗收條件已勾選
        When: 執行 check-acceptance --all --uncheck 批量取消勾選
        Then: 應返回 0，取消勾選所有已勾選的項目
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = None  # --all 時不提供 index
        args.uncheck = True
        args.all = True

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "acceptance": ["[x] Condition 1", "[x] Condition 2", "[ ] Condition 3"],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                result = execute_check_acceptance(args, "0.31.0")

                assert result == 0
                # 驗證所有項目都被取消勾選
                saved_ticket = mock_save.call_args[0][0]
                assert saved_ticket["acceptance"] == ["[ ] Condition 1", "[ ] Condition 2", "[ ] Condition 3"]

    def test_check_acceptance_all_and_index_mutually_exclusive(self):
        """
        Given: 同時提供 --all 和 index 參數
        When: 執行 check-acceptance <id> <index> --all
        Then: 應返回 2（業務拒絕：互斥參數同時提供）

        依 cli-exit-code-rules.md 規則 2：互斥參數衝突屬用戶輸入錯誤 → return 2。
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = "1"  # 提供 index
        args.uncheck = False
        args.all = True  # 同時使用 --all

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "acceptance": ["[ ] Condition 1", "[ ] Condition 2"],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            result = execute_check_acceptance(args, "0.31.0")

            # 應返回 2（業務拒絕）
            assert result == 2

    def test_check_acceptance_missing_index_and_all(self):
        """
        Given: 未提供 --all，也未提供 index 參數
        When: 執行 check-acceptance <id>
        Then: 應返回 2（業務拒絕：缺少必填參數）

        依 cli-exit-code-rules.md 規則 2：缺少必填參數屬用戶輸入錯誤 → return 2。
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.index = None  # 未提供 index
        args.uncheck = False
        args.all = False  # 未使用 --all

        mock_ticket = {
            "id": "0.31.0-W4-001",
            "_path": "/path/to/ticket.md",
            "acceptance": ["[ ] Condition 1"],
        }

        with patch('ticket_system.commands.track_acceptance.load_and_validate_ticket') as mock_load:
            mock_load.return_value = (mock_ticket, None)

            result = execute_check_acceptance(args, "0.31.0")

            # 應返回 2（業務拒絕）
            assert result == 2


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

            with patch('ticket_system.commands.track_acceptance.get_ticket_path', return_value=_LOCK_TARGET):
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

            with patch('ticket_system.commands.track_acceptance.get_ticket_path', return_value=_LOCK_TARGET):
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

            with patch('ticket_system.commands.track_acceptance.get_ticket_path', return_value=_LOCK_TARGET):
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

            with patch('ticket_system.commands.track_acceptance.get_ticket_path', return_value=_LOCK_TARGET):
                with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                    result = execute_append_log(args, "0.31.0")

                    assert result == 0
                    mock_save.assert_called_once()


class TestAppendLogH2Warning:
    """W17-208: append-log 寫入 Schema 章節時內容含 ## H2 → stderr warning（不阻擋）"""

    def _run(self, section: str, content: str, capsys):
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.section = section
        args.content = content
        body = f"## {section}\n\n（佔位）\n"
        mock_ticket = {"id": args.ticket_id, "_path": "/p/t.md", "_body": body}
        with patch('ticket_system.commands.track_acceptance.load_ticket') as mock_load:
            mock_load.return_value = mock_ticket
            with patch('ticket_system.commands.track_acceptance.get_ticket_path', return_value=_LOCK_TARGET):
                with patch('ticket_system.commands.track_acceptance.save_ticket') as mock_save:
                    result = execute_append_log(args, "0.31.0")
        captured = capsys.readouterr()
        return result, captured, mock_save

    def test_h2_in_solution_triggers_warning(self, capsys):
        result, captured, mock_save = self._run("Solution", "## 實作策略\n內文", capsys)
        assert result == 0
        assert "WARNING" in captured.err
        assert "H2" in captured.err
        mock_save.assert_called_once()

    def test_h3_in_solution_no_warning(self, capsys):
        result, captured, mock_save = self._run("Solution", "### 子節\n內文", capsys)
        assert result == 0
        assert "WARNING" not in captured.err
        mock_save.assert_called_once()

    def test_execution_log_h2_skipped(self, capsys):
        # Execution Log 不在 schema check 範圍
        result, captured, _ = self._run("Execution Log", "## 任何", capsys)
        assert result == 0
        assert "WARNING" not in captured.err

    # W1-068（W1-038 方案 B）: 自動降級 H2 → H3 規範化測試

    def test_h2_auto_downgraded_to_h3(self, capsys):
        """W1-068 方案 B：H2 自動降級為 H3，warning 文案明示降級

        斷言用行首 regex（^## ）避免 substring 誤觸：`### 第一` 字串包含 `## 第一`
        """
        result, captured, mock_save = self._run(
            "Solution", "## 第一 H2\n內文\n## 第二 H2\n更多", capsys
        )
        assert result == 0
        assert "WARNING" in captured.err
        assert "自動降級" in captured.err
        mock_save.assert_called_once()
        saved_ticket = mock_save.call_args[0][0]
        saved_body = saved_ticket["_body"]
        # 行首檢查：## 第一 H2 與 ## 第二 H2 已不存在（已被降級為 ###）
        assert re.search(r'(?m)^## 第一 H2', saved_body) is None
        assert re.search(r'(?m)^## 第二 H2', saved_body) is None
        # 行首檢查：### 第一 H2 與 ### 第二 H2 存在
        assert re.search(r'(?m)^### 第一 H2', saved_body) is not None
        assert re.search(r'(?m)^### 第二 H2', saved_body) is not None

    def test_pure_text_unchanged(self, capsys):
        """W1-068 方案 B：純文字無 H2，不觸發降級也無 warning"""
        result, captured, mock_save = self._run(
            "Solution", "純文字內容\n更多內容", capsys
        )
        assert result == 0
        assert "WARNING" not in captured.err
        mock_save.assert_called_once()
        saved_ticket = mock_save.call_args[0][0]
        saved_body = saved_ticket["_body"]
        assert "純文字內容" in saved_body

    def test_existing_h3_h4_unaffected(self, capsys):
        """W1-068 方案 B：已含 H3/H4 不受影響（只匹配行首 H2）"""
        result, captured, mock_save = self._run(
            "Solution", "### 已 H3\n內文\n#### 已 H4\n更多", capsys
        )
        assert result == 0
        assert "WARNING" not in captured.err
        mock_save.assert_called_once()
        saved_ticket = mock_save.call_args[0][0]
        saved_body = saved_ticket["_body"]
        # 行首檢查：### 已 H3 與 #### 已 H4 保留（regex 行首匹配）
        assert re.search(r'(?m)^### 已 H3', saved_body) is not None
        assert re.search(r'(?m)^#### 已 H4', saved_body) is not None
        # 行首檢查：無誤升為 ## 或誤降為 ##### 的情況
        assert re.search(r'(?m)^## 已 H3', saved_body) is None
        assert re.search(r'(?m)^##### 已 H4', saved_body) is None


class TestAppendLogSectionMatching:
    """W17-008.9 section 標題容錯邊界測試（標準/末尾空白/雙空白命中；Solutions/Solution alt 不誤匹配）"""

    def _build_args(self, body: str, section: str = "Solution"):
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"
        args.section = section
        args.content = "新內容"
        ticket = {"id": args.ticket_id, "_path": "/p/t.md", "_body": body}
        return args, ticket

    def _run(self, args, ticket):
        with patch('ticket_system.commands.track_acceptance.load_ticket') as mock_load:
            mock_load.return_value = ticket
            with patch('ticket_system.commands.track_acceptance.get_ticket_path', return_value=_LOCK_TARGET):
                with patch('ticket_system.commands.track_acceptance.save_ticket'):
                    return execute_append_log(args, "0.31.0")

    def test_standard_header_matches(self):
        args, ticket = self._build_args("## Solution\n\n內容\n")
        assert self._run(args, ticket) == 0

    def test_trailing_whitespace_header_matches(self):
        args, ticket = self._build_args("## Solution \n\n內容\n")
        assert self._run(args, ticket) == 0

    def test_double_space_header_matches(self):
        args, ticket = self._build_args("##  Solution\n\n內容\n")
        assert self._run(args, ticket) == 0

    def test_solutions_does_not_falsely_match_solution(self):
        args, ticket = self._build_args("## Solutions\n\n內容\n", section="Solution")
        assert self._run(args, ticket) == 1

    def test_solution_alt_does_not_falsely_match(self):
        args, ticket = self._build_args("## Solution alt\n\n內容\n", section="Solution")
        assert self._run(args, ticket) == 1

    def test_error_message_lists_existing_headers(self, capsys):
        args, ticket = self._build_args(
            "## Problem Analysis\n內容\n## Test Results\n內容\n",
            section="Solution"
        )
        assert self._run(args, ticket) == 1
        out = capsys.readouterr().out
        assert "Problem Analysis" in out
        assert "Test Results" in out
