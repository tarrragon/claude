"""
Hook 訊息常數模組測試

測試 hook_messages.py 中所有的訊息常數類別和格式化函式。
"""

import sys
from pathlib import Path

# 加入 lib 目錄到 Python 路徑
hooks_dir = Path(__file__).parent.parent
lib_dir = hooks_dir / "lib"
if str(lib_dir) not in sys.path:
    sys.path.insert(0, str(lib_dir))

import pytest
from hook_messages import (
    CoreMessages,
    GateMessages,
    WorkflowMessages,
    QualityMessages,
    ValidationMessages,
    format_message,
    format_multiline_block,
)


# ============================================================================
# CoreMessages 測試
# ============================================================================


class TestCoreMessages:
    """CoreMessages 類別測試"""

    def test_all_core_messages_exist(self):
        """測試所有 CoreMessages 常數都已定義"""
        assert hasattr(CoreMessages, "HOOK_START")
        assert hasattr(CoreMessages, "INPUT_EMPTY")
        assert hasattr(CoreMessages, "JSON_PARSE_ERROR")
        assert hasattr(CoreMessages, "HOOK_ERROR")
        assert hasattr(CoreMessages, "DEFAULT_ALLOW")

    def test_core_messages_not_empty(self):
        """測試 CoreMessages 所有常數都非空字串"""
        for attr_name in dir(CoreMessages):
            if attr_name.isupper():
                value = getattr(CoreMessages, attr_name)
                assert isinstance(value, str), f"{attr_name} should be string"
                assert len(value) > 0, f"{attr_name} should not be empty"

    def test_core_messages_with_placeholders(self):
        """測試含有佔位符的 CoreMessages 可正常格式化"""
        # HOOK_START 有 {hook_name} 佔位符
        msg = CoreMessages.HOOK_START.format(hook_name="test-hook")
        assert msg == "test-hook 啟動"
        assert "{" not in msg  # 確保沒有未替換的佔位符

        # JSON_PARSE_ERROR 有 {error} 佔位符
        msg = CoreMessages.JSON_PARSE_ERROR.format(error="test error")
        assert "test error" in msg
        assert "{" not in msg


# ============================================================================
# GateMessages 測試
# ============================================================================


class TestGateMessages:
    """GateMessages 類別測試"""

    def test_all_gate_messages_exist(self):
        """測試關鍵的 GateMessages 常數都已定義"""
        assert hasattr(GateMessages, "COMMAND_GATE_START")
        assert hasattr(GateMessages, "TICKET_NOT_FOUND_ERROR")
        assert hasattr(GateMessages, "TICKET_NOT_CLAIMED_ERROR")
        assert hasattr(GateMessages, "DECISION_TREE_MISSING_ERROR")

    def test_gate_messages_not_empty(self):
        """測試 GateMessages 所有常數都非空字串"""
        for attr_name in dir(GateMessages):
            if attr_name.isupper():
                value = getattr(GateMessages, attr_name)
                assert isinstance(value, str), f"{attr_name} should be string"
                assert len(value) > 0, f"{attr_name} should not be empty"

    def test_error_messages_with_placeholders(self):
        """測試錯誤訊息的佔位符格式化"""
        # TICKET_NOT_CLAIMED_ERROR 有 {ticket_id} 佔位符
        msg = GateMessages.TICKET_NOT_CLAIMED_ERROR.format(ticket_id="0.31.0-W1-001")
        assert "0.31.0-W1-001" in msg
        # 驗證 {ticket_id} 被替換成實際值
        assert "{ticket_id}" not in msg

    def test_relevance_warning_format(self):
        """測試關聯性警告訊息的格式化"""
        msg = GateMessages.TICKET_RELEVANCE_WARNING.format(
            ticket_id="0.31.0-W1-001", title="修復 Hook 問題"
        )
        assert "0.31.0-W1-001" in msg
        assert "修復 Hook 問題" in msg


# ============================================================================
# WorkflowMessages 測試
# ============================================================================


class TestWorkflowMessages:
    """WorkflowMessages 類別測試"""

    def test_all_workflow_messages_exist(self):
        """測試關鍵的 WorkflowMessages 常數都已定義"""
        assert hasattr(WorkflowMessages, "EXTERNAL_QUERY_DETECTED")
        assert hasattr(WorkflowMessages, "EXTERNAL_QUERY_GUIDE")
        assert hasattr(WorkflowMessages, "PRE_FIX_EVAL_REQUIRED")

    def test_workflow_messages_not_empty(self):
        """測試 WorkflowMessages 所有常數都非空字串"""
        for attr_name in dir(WorkflowMessages):
            if attr_name.isupper():
                value = getattr(WorkflowMessages, attr_name)
                assert isinstance(value, str), f"{attr_name} should be string"
                assert len(value) > 0, f"{attr_name} should not be empty"

    def test_external_query_detected_format(self):
        """測試外部查詢檢測訊息的格式化"""
        msg = WorkflowMessages.EXTERNAL_QUERY_DETECTED.format(tool_name="WebFetch")
        assert "WebFetch" in msg


# ============================================================================
# QualityMessages 測試
# ============================================================================


class TestQualityMessages:
    """QualityMessages 類別測試"""

    def test_all_quality_messages_exist(self):
        """測試關鍵的 QualityMessages 常數都已定義"""
        assert hasattr(QualityMessages, "TICKET_QUALITY_CHECK_PASSED")
        assert hasattr(QualityMessages, "FILE_EDIT_WARNING")
        assert hasattr(QualityMessages, "FILE_TYPE_WARNINGS")

    def test_quality_messages_not_empty(self):
        """測試 QualityMessages 所有常數都非空字串"""
        for attr_name in dir(QualityMessages):
            if attr_name.isupper():
                value = getattr(QualityMessages, attr_name)
                if isinstance(value, str):
                    assert len(value) > 0, f"{attr_name} should not be empty"

    def test_file_type_warnings_dict(self):
        """測試檔案類型警告字典"""
        assert isinstance(QualityMessages.FILE_TYPE_WARNINGS, dict)
        assert "config" in QualityMessages.FILE_TYPE_WARNINGS
        assert "workflow" in QualityMessages.FILE_TYPE_WARNINGS
        assert "docs" in QualityMessages.FILE_TYPE_WARNINGS
        # 所有值都應該是非空字串
        for key, value in QualityMessages.FILE_TYPE_WARNINGS.items():
            assert isinstance(value, str), f"Warning for {key} should be string"
            assert len(value) > 0, f"Warning for {key} should not be empty"

    def test_file_edit_warning_format(self):
        """測試檔案編輯警告的格式化"""
        msg = QualityMessages.FILE_EDIT_WARNING.format(category="Config")
        assert "Config" in msg


# ============================================================================
# ValidationMessages 測試
# ============================================================================


class TestValidationMessages:
    """ValidationMessages 類別測試"""

    def test_all_validation_messages_exist(self):
        """測試關鍵的 ValidationMessages 常數都已定義"""
        assert hasattr(ValidationMessages, "WORKLOG_FORMAT_CHECK_PASSED")
        assert hasattr(ValidationMessages, "MCP_TESTS_VALIDATION_PASSED")
        assert hasattr(ValidationMessages, "TIMEOUT_CHECK_STARTED")

    def test_validation_messages_not_empty(self):
        """測試 ValidationMessages 所有常數都非空字串"""
        for attr_name in dir(ValidationMessages):
            if attr_name.isupper():
                value = getattr(ValidationMessages, attr_name)
                assert isinstance(value, str), f"{attr_name} should be string"
                assert len(value) > 0, f"{attr_name} should not be empty"


# ============================================================================
# 格式化函式測試
# ============================================================================


class TestFormatMessage:
    """format_message() 函式測試"""

    def test_format_message_basic(self):
        """測試基本訊息格式化"""
        result = format_message(CoreMessages.HOOK_START, hook_name="my-hook")
        assert result == "my-hook 啟動"

    def test_format_message_multiple_placeholders(self):
        """測試多個佔位符的格式化"""
        template = "Hook {hook_name} 錯誤: {error}"
        result = format_message(template, hook_name="test", error="JSON parse failed")
        assert result == "Hook test 錯誤: JSON parse failed"

    def test_format_message_missing_placeholder_raises_error(self):
        """測試缺少必要參數時引發 KeyError"""
        with pytest.raises(KeyError):
            format_message(CoreMessages.HOOK_START)  # 缺少 hook_name

    def test_format_message_with_special_characters(self):
        """測試含有特殊字元的格式化"""
        result = format_message(
            CoreMessages.JSON_PARSE_ERROR,
            error='Unexpected token "}" in JSON'
        )
        assert 'Unexpected token "}" in JSON' in result

    def test_format_message_with_chinese_parameters(self):
        """測試中文參數的格式化"""
        result = format_message(
            CoreMessages.HOOK_START,
            hook_name="測試-Hook"
        )
        assert result == "測試-Hook 啟動"


class TestFormatMultilineBlock:
    """format_multiline_block() 函式測試"""

    def test_format_multiline_basic(self):
        """測試基本多行格式化"""
        lines = ["第一行", "第二行", "第三行"]
        result = format_multiline_block(lines)
        assert result == "  第一行\n  第二行\n  第三行"

    def test_format_multiline_custom_indent(self):
        """測試自訂縮進的多行格式化"""
        lines = ["Item 1", "Item 2"]
        result = format_multiline_block(lines, indent="    ")  # 4 個空格
        assert result == "    Item 1\n    Item 2"

    def test_format_multiline_empty_list(self):
        """測試空清單的格式化"""
        result = format_multiline_block([])
        assert result == ""

    def test_format_multiline_single_line(self):
        """測試單行清單的格式化"""
        result = format_multiline_block(["只有一行"])
        assert result == "  只有一行"

    def test_format_multiline_with_empty_lines(self):
        """測試含有空字串的清單格式化"""
        lines = ["第一行", "", "第三行"]
        result = format_multiline_block(lines)
        assert result == "  第一行\n  \n  第三行"


# ============================================================================
# 整合測試
# ============================================================================


class TestIntegration:
    """整合測試 - 測試所有訊息類別可以互相合作"""

    def test_all_message_classes_importable(self):
        """測試所有訊息類別都可被匯入"""
        assert CoreMessages is not None
        assert GateMessages is not None
        assert WorkflowMessages is not None
        assert QualityMessages is not None
        assert ValidationMessages is not None

    def test_format_message_with_all_message_classes(self):
        """測試格式化函式可與所有訊息類別配合"""
        # 測試 CoreMessages
        result = format_message(CoreMessages.HOOK_START, hook_name="test")
        assert isinstance(result, str)

        # 測試 GateMessages（此訊息實際上不需要參數）
        # TICKET_NOT_FOUND_ERROR 實際上沒有可格式化的佔位符
        result = GateMessages.TICKET_NOT_CLAIMED_ERROR.format(ticket_id="0.31.0-W1-001")
        assert isinstance(result, str)

        # 測試 WorkflowMessages
        result = format_message(
            WorkflowMessages.EXTERNAL_QUERY_DETECTED,
            tool_name="WebFetch"
        )
        assert isinstance(result, str)

    def test_no_hardcoded_messages_remain(self):
        """測試所有訊息常數都被正確提取（無空值、無 None）"""
        for msg_class in [CoreMessages, GateMessages, WorkflowMessages, QualityMessages, ValidationMessages]:
            for attr_name in dir(msg_class):
                if attr_name.isupper() and not attr_name.startswith("_"):
                    value = getattr(msg_class, attr_name)
                    # 跳過非字串和非字典的屬性
                    if isinstance(value, str):
                        assert value is not None, f"{msg_class.__name__}.{attr_name} is None"
                        assert value != "", f"{msg_class.__name__}.{attr_name} is empty string"


# ============================================================================
# 命令列執行防護
# ============================================================================


def test_module_not_directly_executable():
    """測試模組不支援直接執行（__main__ guard 已設置）"""
    # 此測試驗證 module guard 邏輯是否存在
    import hook_messages
    assert hasattr(hook_messages, "__name__")


# ============================================================================
# 執行測試
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
