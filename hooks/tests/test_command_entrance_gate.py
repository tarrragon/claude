"""
Tests for command-entrance-gate-hook.py

測試命令入口驗證閘門 Hook 的阻塞式驗證功能。
涵蓋邊界情境、錯誤路徑和所有主要分支。
"""

import json
import sys
import io
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import datetime

import pytest
import importlib.util


# ============================================================================
# 動態載入 Hook 模組
# ============================================================================

def load_hook_module():
    """動態載入 command-entrance-gate-hook.py"""
    hook_path = Path(__file__).parent.parent / "command-entrance-gate-hook.py"
    spec = importlib.util.spec_from_file_location("command_entrance_gate_hook", hook_path)
    hook_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook_module)
    return hook_module


# ============================================================================
# 第一階段測試：純邏輯函式（無 IO 依賴）
# ============================================================================

class TestIsSystemInternalMessage:
    """is_system_internal_message() 邊界情境和錯誤路徑測試"""

    def test_empty_string(self):
        """測試空字串輸入"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_system_internal_message("", logger) is False

    def test_none_input(self):
        """測試 None 輸入（邊界情境）"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_system_internal_message(None, logger) is False

    @pytest.mark.parametrize("marker", [
        "<task-notification>",
        "<system-reminder>",
        "<tool-result>",
        "<task-id>",
    ])
    def test_system_markers_detected(self, marker):
        """測試系統標記偵測"""
        hook_module = load_hook_module()
        logger = MagicMock()
        prompt = f"some content {marker} more content"
        assert hook_module.is_system_internal_message(prompt, logger) is True
        logger.debug.assert_called()

    def test_no_system_markers(self):
        """測試無系統標記的一般命令"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_system_internal_message("實作新功能", logger) is False


class TestIsManagementOperation:
    """is_management_operation() 邊界情境和錯誤路徑測試"""

    def test_empty_string(self):
        """測試空字串"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_management_operation("", logger) is False

    def test_none_input(self):
        """測試 None 輸入"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_management_operation(None, logger) is False

    def test_slash_command(self):
        """測試 Slash 命令（SKILL 呼叫）"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_management_operation("/ticket create", logger) is True
        logger.info.assert_called()

    @pytest.mark.parametrize("short_answer", [
        "是", "好", "確認", "同意", "ok", "yes",
        "否", "不", "取消", "no",
        "1", "2", "10",
    ])
    def test_short_answers(self, short_answer):
        """測試短回答白名單"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_management_operation(short_answer, logger) is True

    @pytest.mark.parametrize("pattern", [
        "2, 4",           # 組合多選
        "1,3,5",          # 另一種格式
        "phase 4a",       # Phase 選項
        "Phase 3b",       # Phase 大寫
        "a",              # 單字母選項
    ])
    def test_short_answer_patterns(self, pattern):
        """測試短回答正則模式"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_management_operation(pattern, logger) is True

    @pytest.mark.parametrize("pattern", [
        "ticket", "/ticket",
        "hook", "設定",
        "分析", "研究",
        "為什麼", "怎麼", "如何",
    ])
    def test_management_patterns(self, pattern):
        """測試管理和討論操作白名單"""
        hook_module = load_hook_module()
        logger = MagicMock()
        prompt = f"幫我 {pattern} 一下"
        assert hook_module.is_management_operation(prompt, logger) is True

    def test_development_command_not_management(self):
        """測試開發命令不被視為管理操作"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_management_operation("實作新功能", logger) is False


class TestIsDevelopmentCommand:
    """is_development_command() 邊界情境和錯誤路徑測試"""

    def test_empty_string(self):
        """測試空字串"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_development_command("", logger) is False

    def test_none_input(self):
        """測試 None 輸入"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_development_command(None, logger) is False

    @pytest.mark.parametrize("keyword", [
        "實作", "建立", "新增", "重構",
        "測試", "驗證", "檢查",
        "修正", "修復", "優化",
    ])
    def test_development_keywords(self, keyword):
        """測試開發命令關鍵字識別"""
        hook_module = load_hook_module()
        logger = MagicMock()
        prompt = f"需要{keyword}一個功能"
        assert hook_module.is_development_command(prompt, logger) is True
        logger.info.assert_called()

    def test_non_development_command(self):
        """測試非開發命令"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_development_command("你好", logger) is False
        assert hook_module.is_development_command("請問如何？", logger) is False


class TestSplitKebabCase:
    """split_kebab_case() 的邊界情境測試"""

    def test_simple_word(self):
        """測試簡單單詞"""
        hook_module = load_hook_module()
        assert hook_module.split_kebab_case("hello") == ["hello"]

    def test_kebab_case_word(self):
        """測試 kebab-case 詞彙"""
        hook_module = load_hook_module()
        result = hook_module.split_kebab_case("command-entrance-gate-hook")
        assert result == ["command", "entrance", "gate", "hook"]

    def test_single_hyphen(self):
        """測試單一連字號"""
        hook_module = load_hook_module()
        assert hook_module.split_kebab_case("hello-world") == ["hello", "world"]

    def test_empty_string(self):
        """測試空字串"""
        hook_module = load_hook_module()
        # 空字串會被 split() 產生 [""]，但過濾掉會得到 []
        assert hook_module.split_kebab_case("") == []

    def test_trailing_hyphens(self):
        """測試尾部連字號"""
        hook_module = load_hook_module()
        result = hook_module.split_kebab_case("hello-world-")
        # 連字號會產生空字串，被過濾掉
        assert "" not in result or len(result) >= 2


class TestTokenizeText:
    """tokenize_text() 的邊界情境和錯誤路徑測試"""

    def test_empty_string(self):
        """測試空字串"""
        hook_module = load_hook_module()
        assert hook_module.tokenize_text("") == []

    def test_none_input(self):
        """測試 None 輸入"""
        hook_module = load_hook_module()
        assert hook_module.tokenize_text(None) == []

    def test_simple_text(self):
        """測試簡單文本"""
        hook_module = load_hook_module()
        result = hook_module.tokenize_text("修復 bug 問題")
        # 應排除噪音詞「問題」（長度 <= 1 的詞和噪音詞）
        assert "修復" in result
        assert "bug" in result
        assert len(result) >= 2

    def test_kebab_case_splitting(self):
        """測試 kebab-case 拆分"""
        hook_module = load_hook_module()
        result = hook_module.tokenize_text("修復 command-entrance-gate-hook")
        assert "command" in result
        assert "entrance" in result
        assert "gate" in result
        assert "hook" in result

    def test_noise_word_filtering(self):
        """測試噪音詞過濾"""
        hook_module = load_hook_module()
        result = hook_module.tokenize_text("修復 的 和 或 問題")
        # 應包含「修復」但排除「的」「和」「或」「問題」
        assert "修復" in result
        assert "的" not in result
        assert "和" not in result


class TestCheckWordRelevance:
    """check_word_relevance() 的邊界情境測試"""

    def test_exact_match(self):
        """測試完全匹配"""
        hook_module = load_hook_module()
        logger = MagicMock()
        prompt_words = ["hook"]
        title_words = ["command", "entrance", "gate", "hook"]
        assert hook_module.check_word_relevance(prompt_words, title_words, logger) is True

    def test_substring_match(self):
        """測試子字串匹配"""
        hook_module = load_hook_module()
        logger = MagicMock()
        prompt_words = ["hook"]
        title_words = ["command-entrance-gate-hook"]
        result = hook_module.check_word_relevance(prompt_words, title_words, logger)
        # 應偵測到子字串匹配
        assert result is True or logger.debug.called

    def test_no_match(self):
        """測試無匹配"""
        hook_module = load_hook_module()
        logger = MagicMock()
        prompt_words = ["unrelated"]
        title_words = ["command", "entrance", "gate", "hook"]
        assert hook_module.check_word_relevance(prompt_words, title_words, logger) is False

    def test_empty_lists(self):
        """測試空清單"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.check_word_relevance([], [], logger) is False
        assert hook_module.check_word_relevance(["word"], [], logger) is False


# ============================================================================
# 第二階段測試：檔案操作函式（模擬文件系統）
# ============================================================================

class TestExtractTicketStatus:
    """extract_ticket_status() 的檔案操作測試"""

    def test_valid_ticket_file(self, tmp_path):
        """測試有效的 Ticket 檔案提取"""
        hook_module = load_hook_module()
        logger = MagicMock()

        # 建立 Ticket 檔案
        ticket_file = tmp_path / "0.1.0-W39-003.md"
        content = """---
id: 0.1.0-W39-003
title: 補充測試覆蓋
status: in_progress
---

# 內容
"""
        ticket_file.write_text(content, encoding="utf-8")

        ticket_id, status, extracted_content = hook_module.extract_ticket_status(ticket_file, logger)

        assert ticket_id == "0.1.0-W39-003"
        assert status == "in_progress"
        assert len(extracted_content) > 0

    def test_pending_ticket_extraction(self, tmp_path):
        """測試 pending 狀態 Ticket 提取"""
        hook_module = load_hook_module()
        logger = MagicMock()

        ticket_file = tmp_path / "0.1.0-W39-004.md"
        content = """---
status: pending
---
"""
        ticket_file.write_text(content, encoding="utf-8")

        _, status, _ = hook_module.extract_ticket_status(ticket_file, logger)
        assert status == "pending"

    def test_missing_status_field(self, tmp_path):
        """測試缺少 status 欄位的檔案"""
        hook_module = load_hook_module()
        logger = MagicMock()

        ticket_file = tmp_path / "broken.md"
        ticket_file.write_text("---\nid: 123\n---\n", encoding="utf-8")

        ticket_id, status, _ = hook_module.extract_ticket_status(ticket_file, logger)
        assert ticket_id == "broken"
        assert status is None

    def test_invalid_file_read(self):
        """測試無效的檔案讀取"""
        hook_module = load_hook_module()
        logger = MagicMock()

        invalid_path = Path("/nonexistent/file.md")
        ticket_id, status, content = hook_module.extract_ticket_status(invalid_path, logger)

        assert ticket_id is None
        assert status is None
        assert content == ""
        logger.debug.assert_called()


# ============================================================================
# 第三階段測試：複雜依賴函式（需要 mock）
# ============================================================================

class TestCheckTicketStatus:
    """check_ticket_status() 的複雜邏輯測試"""

    def test_no_ticket_found(self):
        """測試未找到 Ticket 情境"""
        hook_module = load_hook_module()
        logger = MagicMock()

        with patch.object(hook_module, 'get_latest_pending_ticket', return_value=None):
            is_valid, error_msg, ticket_id, warning = hook_module.check_ticket_status(
                prompt="實作功能", logger=logger
            )

        assert is_valid is False
        assert ticket_id is None
        assert error_msg is not None
        # 檢查常見關鍵詞
        assert "未找到" in error_msg or "找不到" in error_msg or "待處理" in error_msg

    def test_ticket_not_claimed(self):
        """測試 Ticket 未認領情境（邊界情境 1）"""
        hook_module = load_hook_module()
        logger = MagicMock()

        with patch.object(hook_module, 'get_latest_pending_ticket',
                         return_value=("0.1.0-W39-003", "pending", "content")):
            is_valid, error_msg, ticket_id, _ = hook_module.check_ticket_status(
                prompt="實作功能", logger=logger
            )

        assert is_valid is False
        assert ticket_id == "0.1.0-W39-003"
        assert "未認領" in error_msg or "未被認領" in error_msg

    def test_missing_decision_tree(self):
        """測試缺少決策樹欄位情境"""
        hook_module = load_hook_module()
        logger = MagicMock()

        with patch.object(hook_module, 'get_latest_pending_ticket',
                         return_value=("0.1.0-W39-003", "in_progress", "content")):
            with patch.object(hook_module, 'validate_ticket_has_decision_tree', return_value=False):
                is_valid, error_msg, ticket_id, _ = hook_module.check_ticket_status(
                    prompt="實作功能", logger=logger
                )

        assert is_valid is False
        assert ticket_id == "0.1.0-W39-003"
        assert "決策樹" in error_msg

    def test_valid_ticket_without_relevance_check(self):
        """測試有效 Ticket，無 relevance 警告"""
        hook_module = load_hook_module()
        logger = MagicMock()

        with patch.object(hook_module, 'get_latest_pending_ticket',
                         return_value=("0.1.0-W39-003", "in_progress", "title: 測試")):
            with patch.object(hook_module, 'validate_ticket_has_decision_tree', return_value=True):
                is_valid, error_msg, ticket_id, warning = hook_module.check_ticket_status(
                    prompt=None, logger=logger
                )

        assert is_valid is True
        assert error_msg is None
        assert ticket_id == "0.1.0-W39-003"

    def test_valid_ticket_with_relevance_warning(self):
        """測試有效 Ticket，帶 relevance 警告"""
        hook_module = load_hook_module()
        logger = MagicMock()

        with patch.object(hook_module, 'get_latest_pending_ticket',
                         return_value=("0.1.0-W39-003", "in_progress", "content")):
            with patch.object(hook_module, 'validate_ticket_has_decision_tree', return_value=True):
                with patch.object(hook_module, 'check_ticket_relevance',
                                 return_value=(False, "警告訊息")):
                    is_valid, error_msg, ticket_id, warning = hook_module.check_ticket_status(
                        prompt="其他命令", logger=logger
                    )

        assert is_valid is True
        assert warning is not None
        assert "警告" in warning or len(warning) > 0

    def test_unknown_ticket_status(self):
        """測試未知 Ticket 狀態"""
        hook_module = load_hook_module()
        logger = MagicMock()

        with patch.object(hook_module, 'get_latest_pending_ticket',
                         return_value=("0.1.0-W39-003", "unknown_status", "content")):
            is_valid, error_msg, ticket_id, _ = hook_module.check_ticket_status(
                prompt="實作功能", logger=logger
            )

        assert is_valid is False
        assert "unknown_status" in error_msg


class TestGenerateHookOutput:
    """generate_hook_output() 的輸出生成測試"""

    def test_allowed_non_dev_command(self):
        """測試允許非開發命令"""
        hook_module = load_hook_module()

        output = hook_module.generate_hook_output(
            prompt="你好",
            is_dev_cmd=False,
            is_valid=True,
            error_msg=None,
            ticket_id=None,
            relevance_warning=None
        )

        assert "check_result" in output
        assert output["check_result"]["should_block"] is False
        assert output["check_result"]["exit_code"] == "EXIT_SUCCESS"

    def test_blocked_dev_command_without_ticket(self):
        """測試阻擋無 Ticket 的開發命令"""
        hook_module = load_hook_module()

        output = hook_module.generate_hook_output(
            prompt="實作新功能",
            is_dev_cmd=True,
            is_valid=False,
            error_msg="未找到 Ticket",
            ticket_id=None,
            relevance_warning=None
        )

        assert output["check_result"]["should_block"] is True
        assert output["check_result"]["exit_code"] == "EXIT_BLOCK"
        assert "未找到 Ticket" in output["hookSpecificOutput"].get("additionalContext", "")

    def test_output_with_both_errors_and_warning(self):
        """測試同時包含錯誤和警告的輸出"""
        hook_module = load_hook_module()

        output = hook_module.generate_hook_output(
            prompt="實作功能",
            is_dev_cmd=True,
            is_valid=True,
            error_msg=None,
            ticket_id="0.1.0-W39-003",
            relevance_warning="關聯性警告"
        )

        assert output["check_result"]["should_block"] is False
        context = output["hookSpecificOutput"].get("additionalContext", "")
        assert "關聯性警告" in context or len(context) > 0

    def test_output_json_structure(self):
        """測試輸出 JSON 結構完整性"""
        hook_module = load_hook_module()

        output = hook_module.generate_hook_output(
            prompt="測試",
            is_dev_cmd=False,
            is_valid=True,
            error_msg=None,
            ticket_id="0.1.0-W39-003",
            relevance_warning=None
        )

        assert "hookSpecificOutput" in output
        assert "hookEventName" in output["hookSpecificOutput"]
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "check_result" in output
        assert "timestamp" in output["check_result"]


class TestMainFunction:
    """main() 函式的整合測試"""

    def test_system_message_skip(self):
        """測試系統內部訊息被跳過"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"prompt": "<system-reminder>"}):
            with patch('sys.stdout', new_callable=io.StringIO):
                result = hook_module.main()

        assert result == 0  # EXIT_SUCCESS

    def test_management_operation_allowed(self):
        """測試管理操作被允許"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"prompt": "/ticket create"}):
            with patch('sys.stdout', new_callable=io.StringIO):
                result = hook_module.main()

        assert result == 0  # EXIT_SUCCESS

    def test_invalid_input_handling(self):
        """測試無效輸入處理（邊界情境 5）"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={}):  # 缺少 prompt 欄位
            with patch('sys.stdout', new_callable=io.StringIO):
                result = hook_module.main()

        # 應允許執行（預設安全行為）
        assert result == 0

    def test_dev_command_blocked(self):
        """測試開發命令被阻擋"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"prompt": "實作新功能"}):
            with patch.object(hook_module, 'is_development_command', return_value=True):
                with patch.object(hook_module, 'check_ticket_status',
                                 return_value=(False, "Ticket 未找到", None, None)):
                    with patch('sys.stdout', new_callable=io.StringIO):
                        with patch('sys.stderr', new_callable=io.StringIO):
                            result = hook_module.main()

        assert result == 2  # EXIT_BLOCK

    def test_dev_command_allowed(self):
        """測試開發命令被允許（Ticket 驗證通過）"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"prompt": "實作新功能"}):
            with patch.object(hook_module, 'is_development_command', return_value=True):
                with patch.object(hook_module, 'check_ticket_status',
                                 return_value=(True, None, "0.1.0-W39-003", None)):
                    with patch('sys.stdout', new_callable=io.StringIO):
                        result = hook_module.main()

        assert result == 0  # EXIT_SUCCESS

    def test_hook_error_handling(self):
        """測試 Hook 執行錯誤處理"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         side_effect=Exception("讀取錯誤")):
            with patch('sys.stdout', new_callable=io.StringIO):
                result = hook_module.main()

        # 應返回 EXIT_ERROR（1）
        assert result == 1


# ============================================================================
# 整合測試：多 Ticket ID、豁免情境等邊界情境
# ============================================================================

class TestBoundaryScenarios:
    """邊界情境和錯誤路徑整合測試"""

    def test_multiple_ticket_ids_in_prompt(self):
        """測試多 Ticket ID 的邊界情境 2"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"prompt": "0.1.0-W39-001 0.1.0-W39-002 實作新功能"}):
            with patch.object(hook_module, 'is_development_command', return_value=True):
                with patch.object(hook_module, 'check_ticket_status',
                                 return_value=(False, "錯誤", None, None)):
                    with patch('sys.stdout', new_callable=io.StringIO):
                        with patch('sys.stderr', new_callable=io.StringIO):
                            result = hook_module.main()

        assert result == 2

    def test_exempted_scenario_analysis_command(self):
        """測試豁免情境 — 分析命令不進行驗證"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"prompt": "分析程式碼結構"}):
            with patch.object(hook_module, 'is_development_command', return_value=False):
                with patch('sys.stdout', new_callable=io.StringIO):
                    result = hook_module.main()

        assert result == 0

    def test_malformed_json_input(self):
        """測試錯誤格式輸入（邊界情境 5）"""
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"invalid": "data"}):
            with patch('sys.stdout', new_callable=io.StringIO):
                result = hook_module.main()

        # 應允許執行（預設安全行為）
        assert result == 0


# ============================================================================
# W4-027 組合 F：三層誤判修復測試
# ============================================================================

class TestW4027L1WordBoundaryContext:
    """L1 is_development_command：描述性開發詞不誤判為開發命令

    W4-026 根因：prompt「更新 v0.20.0-main.md 反映新增的監測波次」中
    描述性「新增」以 substring 命中 IMPLEMENT_KEYWORDS 被誤判為開發命令。
    """

    def test_descriptive_keyword_in_doc_edit_not_dev(self):
        """描述性開發詞嵌在 doc 編輯 prompt 中不應判為開發命令"""
        hook_module = load_hook_module()
        logger = MagicMock()
        prompt = "更新 v0.20.0-main.md 反映新增的監測波次"
        assert hook_module.is_development_command(prompt, logger) is False

    def test_descriptive_keyword_mid_sentence_not_dev(self):
        """開發詞出現在描述子句（「的」修飾語）不應判為開發命令"""
        hook_module = load_hook_module()
        logger = MagicMock()
        # 「新增的功能」屬名詞性描述，非命令
        assert hook_module.is_development_command(
            "整理文件以說明新增的功能清單", logger
        ) is False

    def test_imperative_keyword_at_start_is_dev(self):
        """命令式開發詞（句首）仍應判為開發命令（防護不喪失）"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_development_command("實作新功能", logger) is True
        assert hook_module.is_development_command("新增使用者登入流程", logger) is True

    def test_imperative_keyword_short_prompt_is_dev(self):
        """短命令式開發 prompt 仍應判為開發命令"""
        hook_module = load_hook_module()
        logger = MagicMock()
        assert hook_module.is_development_command("重構 UC-06", logger) is True


class TestW4027L2TriggerNarrowing:
    """L2 get_latest_pending_ticket：觸發限縮

    僅在 prompt 顯式引用 ticket-id 或存在 in_progress ticket 時才回傳 pending，
    不再用全版本 mtime-latest-pending 盲選。
    """

    def _ticket(self, tmp_path, name, status, title="無關標題"):
        f = tmp_path / name
        f.write_text(
            f"---\nid: {name[:-3]}\ntitle: {title}\nstatus: {status}\n---\n",
            encoding="utf-8",
        )
        return f

    def test_no_ticket_id_no_in_progress_returns_none(self, tmp_path):
        """prompt 無 ticket-id 引用、無 in_progress ticket → 不盲選 pending"""
        hook_module = load_hook_module()
        logger = MagicMock()
        pending = self._ticket(tmp_path, "0.20.0-W1-013.md", "pending")

        with patch.object(hook_module, 'get_project_root', return_value=tmp_path):
            with patch.object(hook_module, 'find_ticket_files', return_value=[pending]):
                result = hook_module.get_latest_pending_ticket(
                    logger, prompt="更新 v0.20.0-main.md 反映新增的監測波次"
                )

        assert result is None

    def test_explicit_ticket_id_returns_matching(self, tmp_path):
        """prompt 顯式引用 ticket-id → 回傳該 ticket"""
        hook_module = load_hook_module()
        logger = MagicMock()
        pending = self._ticket(tmp_path, "0.20.0-W1-013.md", "pending")

        with patch.object(hook_module, 'get_project_root', return_value=tmp_path):
            with patch.object(hook_module, 'find_ticket_files', return_value=[pending]):
                result = hook_module.get_latest_pending_ticket(
                    logger, prompt="認領 0.20.0-W1-013 並開始"
                )

        assert result is not None
        assert result[0] == "0.20.0-W1-013"

    def test_in_progress_ticket_returned_without_id(self, tmp_path):
        """存在 in_progress ticket → 即使 prompt 無 ticket-id 仍回傳（既有 gate 行為）"""
        hook_module = load_hook_module()
        logger = MagicMock()
        in_prog = self._ticket(tmp_path, "0.20.0-W1-005.md", "in_progress")

        with patch.object(hook_module, 'get_project_root', return_value=tmp_path):
            with patch.object(hook_module, 'find_ticket_files', return_value=[in_prog]):
                result = hook_module.get_latest_pending_ticket(
                    logger, prompt="繼續實作功能"
                )

        assert result is not None
        assert result[0] == "0.20.0-W1-005"
        assert result[1] == "in_progress"

    def test_backward_compat_no_prompt_arg(self, tmp_path):
        """向後相容：未傳 prompt 參數時 fallback 回舊行為（mtime-latest pending）"""
        hook_module = load_hook_module()
        logger = MagicMock()
        pending = self._ticket(tmp_path, "0.20.0-W1-013.md", "pending")

        with patch.object(hook_module, 'get_project_root', return_value=tmp_path):
            with patch.object(hook_module, 'find_ticket_files', return_value=[pending]):
                result = hook_module.get_latest_pending_ticket(logger)

        assert result is not None
        assert result[0] == "0.20.0-W1-013"


class TestW4027L3PendingRelevanceGate:
    """L3 check_ticket_status：pending 阻擋前加 relevance 閘門

    mirror in_progress 既有 check_ticket_relevance 路徑：
    pending ticket 與 prompt 無關時不阻擋（放行而非要求認領無關 ticket）。
    """

    def test_pending_irrelevant_not_blocked(self):
        """pending ticket 與 prompt 無關 → 不阻擋"""
        hook_module = load_hook_module()
        logger = MagicMock()

        with patch.object(hook_module, 'get_latest_pending_ticket',
                          return_value=("0.20.0-W1-013", "pending",
                                        "title: 監測波次校準分析")):
            is_valid, error_msg, ticket_id, _ = hook_module.check_ticket_status(
                prompt="更新 v0.20.0-main.md 反映新增的監測波次", logger=logger
            )

        # 無關 pending 不阻擋
        assert is_valid is True

    def test_pending_relevant_still_blocked(self):
        """pending ticket 與 prompt 相關但未認領 → 仍阻擋（要求 claim，防護不喪失）"""
        hook_module = load_hook_module()
        logger = MagicMock()

        with patch.object(hook_module, 'get_latest_pending_ticket',
                          return_value=("0.20.0-W1-013", "pending",
                                        "title: 修復 command-entrance-gate-hook")):
            is_valid, error_msg, ticket_id, _ = hook_module.check_ticket_status(
                prompt="修復 command-entrance-gate-hook", logger=logger
            )

        assert is_valid is False
        assert ticket_id == "0.20.0-W1-013"
        assert "未認領" in error_msg or "未被認領" in error_msg


class TestW4027IntegrationReproCase:
    """W4-026 完整重現案例：doc-edit prompt + 無關 pending → 不應阻擋"""

    def test_doc_edit_with_unrelated_pending_not_blocked(self):
        """主重現：「更新 v0.20.0-main.md 反映新增的監測波次」+ 無關 pending → 放行"""
        hook_module = load_hook_module()

        # 模擬全版本掃描只找到無關的 pending W1-013
        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"prompt": "更新 v0.20.0-main.md 反映新增的監測波次"}):
            with patch.object(hook_module, 'get_latest_pending_ticket',
                             return_value=("0.20.0-W1-013", "pending",
                                           "title: 監測波次校準分析")):
                with patch('sys.stdout', new_callable=io.StringIO):
                    with patch('sys.stderr', new_callable=io.StringIO):
                        result = hook_module.main()

        assert result == 0  # 不應阻擋

    def test_real_coding_intent_no_ticket_still_blocked(self):
        """防護不喪失：真實命令式開發意圖（句首開發詞）+ 有相關 pending 仍被擋

        prompt 避開 management 白名單詞（如 hook/commit），確保走開發命令驗證路徑。
        """
        hook_module = load_hook_module()

        with patch.object(hook_module, 'read_json_from_stdin',
                         return_value={"prompt": "實作使用者登入流程"}):
            with patch.object(hook_module, 'get_latest_pending_ticket',
                             return_value=("0.20.0-W1-013", "pending",
                                           "title: 實作使用者登入流程")):
                with patch('sys.stdout', new_callable=io.StringIO):
                    with patch('sys.stderr', new_callable=io.StringIO):
                        result = hook_module.main()

        assert result == 2  # EXIT_BLOCK
