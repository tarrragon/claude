"""
測試 extract_core_ticket_id() 函式

測試從可能帶後綴的 ID 中提取核心 ID 的邏輯。
"""

import pytest
from ticket_system.lib.id_parser import extract_core_ticket_id


class TestExtractCoreTicketIDRemovesSuffix:
    """測試移除後綴功能"""

    def test_removes_suffix(self):
        """帶後綴的 ID 應該去掉後綴"""
        cases = [
            ("0.1.0-W11-004-phase1-design", "0.1.0-W11-004"),
            ("0.1.0-W44-003-phase2-test-design", "0.1.0-W44-003"),
            ("0.1.0-W25-005-analysis", "0.1.0-W25-005"),
            ("0.1.0-W39-001-phase3a-strategy", "0.1.0-W39-001"),
        ]
        for raw_id, expected in cases:
            result = extract_core_ticket_id(raw_id)
            assert result == expected, f"{raw_id} 應該返回 {expected}"


class TestExtractCoreTicketIDPreservesStandard:
    """測試標準格式保持不變"""

    def test_preserves_standard_format(self):
        """標準格式的 ID（無後綴）應該原樣返回"""
        cases = [
            "0.31.0-W3-001",
            "0.1.0-W1-001",
            "1.0.0-W99-999",
        ]
        for raw_id in cases:
            result = extract_core_ticket_id(raw_id)
            assert result == raw_id, f"{raw_id} 應該保持不變"

    def test_preserves_subtask_format(self):
        """子任務格式應該原樣返回"""
        cases = [
            "0.31.0-W3-001.1",
            "0.31.0-W3-001.1.2",
        ]
        for raw_id in cases:
            result = extract_core_ticket_id(raw_id)
            assert result == raw_id, f"{raw_id} 應該保持不變"


class TestExtractCoreTicketIDSubtaskWithSuffix:
    """測試子任務帶後綴的情況"""

    def test_removes_suffix_from_subtask(self):
        """子任務帶後綴應該去掉後綴"""
        cases = [
            ("0.1.0-W11-004.1-phase1-design", "0.1.0-W11-004.1"),
            ("0.1.0-W11-004.1.2-analysis", "0.1.0-W11-004.1.2"),
            ("0.1.0-W11-004.1.2.3-feature-spec", "0.1.0-W11-004.1.2.3"),
        ]
        for raw_id, expected in cases:
            result = extract_core_ticket_id(raw_id)
            assert result == expected, f"{raw_id} 應該返回 {expected}"


class TestExtractCoreTicketIDNoneHandling:
    """測試 None 輸入處理"""

    def test_handles_none(self):
        """None 輸入應該返回 None"""
        result = extract_core_ticket_id(None)
        assert result is None

    def test_handles_empty_string(self):
        """空字串應該返回 None"""
        result = extract_core_ticket_id("")
        assert result is None


class TestExtractCoreTicketIDInvalidFormat:
    """測試無效格式"""

    def test_returns_none_for_invalid_format(self):
        """無效格式應該返回 None"""
        cases = [
            "invalid",
            "0.1.0",
            "W11-004",
            "0.1.0-W11-004-Phase1",  # 大寫
            "0.1.0-W11-004-",  # 只有連字號
        ]
        for raw_id in cases:
            result = extract_core_ticket_id(raw_id)
            assert result is None, f"{raw_id} 應該返回 None"


class TestExtractCoreTicketIDLowercaseW:
    """測試後綴含 w 小寫字母"""

    def test_handles_lowercase_w_in_suffix(self):
        """後綴含 'w' 小寫應該解析成功（w5 是後綴，不是 Wave）"""
        result = extract_core_ticket_id("0.1.0-W3-001-w5")
        assert result == "0.1.0-W3-001"
