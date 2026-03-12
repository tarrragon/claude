"""
測試 has_description_suffix() 函式

測試判斷 ID 是否帶有描述後綴的邏輯。
"""

import pytest
from ticket_system.lib.id_parser import has_description_suffix


class TestHasDescriptionSuffixDetects:
    """測試檢測後綴"""

    def test_detects_suffix(self):
        """帶後綴的 ID 應該返回 True"""
        cases = [
            "0.1.0-W11-004-phase1-design",
            "0.1.0-W25-005-analysis",
            "0.1.0-W39-001-phase3a-strategy",
        ]
        for raw_id in cases:
            result = has_description_suffix(raw_id)
            assert result is True, f"{raw_id} 應該返回 True"


class TestHasDescriptionSuffixReturnsfalse:
    """測試無後綴返回 False"""

    def test_returns_false_for_standard_format(self):
        """標準格式 ID（無後綴）應該返回 False"""
        cases = [
            "0.31.0-W3-001",
            "0.31.0-W3-001.1",
            "0.31.0-W3-001.1.2",
        ]
        for raw_id in cases:
            result = has_description_suffix(raw_id)
            assert result is False, f"{raw_id} 應該返回 False"

    def test_returns_false_for_invalid_format(self):
        """無效格式應該返回 False"""
        cases = [
            "invalid",
            "",
            None,
        ]
        for raw_id in cases:
            result = has_description_suffix(raw_id)
            assert result is False, f"{raw_id} 應該返回 False"
