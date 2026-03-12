"""
測試 TICKET_ID_PATTERN 正則驗證

測試 Ticket ID 正則表達式的所有邊界條件，包括：
- 標準格式（向後相容）
- 子任務格式（向後相容）
- 帶後綴格式（新功能）
- 邊界和錯誤情況
"""

import re
import pytest
from ticket_system.lib.constants import TICKET_ID_PATTERN


class TestTicketIDPatternStandard:
    """測試標準格式（向後相容）"""

    def test_pattern_matches_standard_format(self):
        """標準 ID 應該匹配，group(4) 為 None"""
        cases = [
            ("0.31.0-W3-001", ("0.31.0", "3", "001", None)),
            ("0.1.0-W1-001", ("0.1.0", "1", "001", None)),
            ("1.0.0-W99-999", ("1.0.0", "99", "999", None)),
        ]
        for raw_id, expected_groups in cases:
            match = re.match(TICKET_ID_PATTERN, raw_id)
            assert match is not None, f"應該匹配: {raw_id}"
            assert (match.group(1), match.group(2), match.group(3), match.group(4)) == expected_groups

    def test_pattern_matches_subtask_format(self):
        """子任務 ID 應該匹配，group(3) 含多個序號，group(4) 為 None"""
        cases = [
            ("0.31.0-W3-001.1", ("0.31.0", "3", "001.1", None)),
            ("0.31.0-W3-001.1.2", ("0.31.0", "3", "001.1.2", None)),
            ("0.31.0-W3-001.1.2.3", ("0.31.0", "3", "001.1.2.3", None)),
        ]
        for raw_id, expected_groups in cases:
            match = re.match(TICKET_ID_PATTERN, raw_id)
            assert match is not None, f"應該匹配: {raw_id}"
            assert (match.group(1), match.group(2), match.group(3), match.group(4)) == expected_groups


class TestTicketIDPatternSuffix:
    """測試帶後綴格式（新功能）"""

    def test_pattern_matches_with_known_suffixes(self):
        """帶已知後綴的 ID 應該匹配，group(4) 含後綴字串"""
        cases = [
            ("0.1.0-W11-004-phase1-design", ("-phase1-design",)),
            ("0.1.0-W44-003-phase2-test-design", ("-phase2-test-design",)),
            ("0.1.0-W39-001-phase3a-strategy", ("-phase3a-strategy",)),
            ("0.1.0-W25-005-analysis", ("-analysis",)),
            ("0.1.0-W1-005-test-cases", ("-test-cases",)),
        ]
        for raw_id, (expected_suffix,) in cases:
            match = re.match(TICKET_ID_PATTERN, raw_id)
            assert match is not None, f"應該匹配: {raw_id}"
            assert match.group(4) == expected_suffix

    def test_pattern_matches_subtask_with_suffix(self):
        """子任務帶後綴應該匹配，group(3) 含子序號，group(4) 含後綴"""
        cases = [
            ("0.1.0-W11-004.1-phase1-design", ("0.1.0", "11", "004.1", "-phase1-design")),
            ("0.1.0-W11-004.1.2-analysis", ("0.1.0", "11", "004.1.2", "-analysis")),
        ]
        for raw_id, expected_groups in cases:
            match = re.match(TICKET_ID_PATTERN, raw_id)
            assert match is not None, f"應該匹配: {raw_id}"
            assert (match.group(1), match.group(2), match.group(3), match.group(4)) == expected_groups


class TestTicketIDPatternBoundary:
    """測試邊界條件"""

    def test_pattern_matches_suffix_starting_with_digit(self):
        """後綴以數字開頭（如 '3b'）應該匹配"""
        raw_id = "0.1.0-W3-001-3b"
        match = re.match(TICKET_ID_PATTERN, raw_id)
        assert match is not None
        assert match.group(4) == "-3b"

    def test_pattern_matches_suffix_with_hyphens(self):
        """後綴含多個連字號應該匹配"""
        raw_id = "0.1.0-W11-004-phase-1-design"
        match = re.match(TICKET_ID_PATTERN, raw_id)
        assert match is not None
        assert match.group(4) == "-phase-1-design"

    def test_pattern_matches_exactly_60_char_suffix(self):
        """後綴恰好 60 字元應該匹配"""
        suffix = "-" + "a" * 59  # "-" 加 59 字元 = 60 字元
        raw_id = f"0.1.0-W11-004{suffix}"
        match = re.match(TICKET_ID_PATTERN, raw_id)
        assert match is not None
        assert len(match.group(4)) == 60


class TestTicketIDPatternRejection:
    """測試應該不匹配的格式"""

    def test_pattern_rejects_suffix_only_hyphen(self):
        """後綴只有連字號應該不匹配"""
        raw_id = "0.1.0-W11-004-"
        match = re.match(TICKET_ID_PATTERN, raw_id)
        assert match is None, f"應該不匹配: {raw_id}"

    def test_pattern_rejects_uppercase_in_suffix(self):
        """後綴含大寫字母應該不匹配"""
        raw_id = "0.1.0-W11-004-Phase1"
        match = re.match(TICKET_ID_PATTERN, raw_id)
        assert match is None, f"應該不匹配: {raw_id}"

    def test_pattern_rejects_too_long_suffix(self):
        """後綴超過 60 字元應該不匹配"""
        long_suffix = "-" + "a" * 61
        raw_id = f"0.1.0-W11-004{long_suffix}"
        match = re.match(TICKET_ID_PATTERN, raw_id)
        assert match is None, f"應該不匹配: {raw_id}"

    def test_pattern_rejects_invalid_format(self):
        """無效格式應該不匹配"""
        cases = ["invalid", "0.1.0", "W11-004", "0.1.0-W11"]
        for raw_id in cases:
            match = re.match(TICKET_ID_PATTERN, raw_id)
            assert match is None, f"應該不匹配: {raw_id}"
