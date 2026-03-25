"""
Protocol Version 常數單元測試

驗證所有 protocol_version 相關常數的定義正確性。
"""
import pytest

from ticket_system.lib.constants import (
    PROTOCOL_VERSION_CURRENT,
    PROTOCOL_VERSION_DEFAULT,
    PROTOCOL_VERSION_MIGRATIONS,
    PROTOCOL_VERSION_PATTERN,
    PROTOCOL_VERSION_RE,
    PROTOCOL_VERSIONS_SUPPORTED,
)


class TestProtocolVersionConstants:
    """Protocol Version 常數定義測試"""

    def test_protocol_version_current(self):
        """TC-001: PROTOCOL_VERSION_CURRENT 常數定義"""
        assert PROTOCOL_VERSION_CURRENT == "2.0"
        assert isinstance(PROTOCOL_VERSION_CURRENT, str)

    def test_protocol_version_default(self):
        """TC-002: PROTOCOL_VERSION_DEFAULT 常數定義"""
        assert PROTOCOL_VERSION_DEFAULT == "1.0"
        assert isinstance(PROTOCOL_VERSION_DEFAULT, str)

    def test_protocol_versions_supported(self):
        """TC-003: PROTOCOL_VERSIONS_SUPPORTED 清單定義"""
        assert PROTOCOL_VERSIONS_SUPPORTED == ["1.0", "2.0"]
        assert isinstance(PROTOCOL_VERSIONS_SUPPORTED, list)
        assert len(PROTOCOL_VERSIONS_SUPPORTED) == 2

    def test_protocol_version_pattern(self):
        """TC-004: 版本格式正則表達式 - 有效格式"""
        # 有效格式：Major.Minor
        assert PROTOCOL_VERSION_RE.match("2.0") is not None
        assert PROTOCOL_VERSION_RE.match("1.0") is not None
        assert PROTOCOL_VERSION_RE.match("0.0") is not None
        assert PROTOCOL_VERSION_RE.match("10.20") is not None

    def test_protocol_version_pattern_invalid_formats(self):
        """TC-005-009: 版本格式正則表達式 - 無效格式"""
        # 無效格式
        assert PROTOCOL_VERSION_RE.match("v2.0") is None  # v 前綴
        assert PROTOCOL_VERSION_RE.match("2") is None  # 缺少 Minor
        assert PROTOCOL_VERSION_RE.match("2.0.1") is None  # 三層版本
        assert PROTOCOL_VERSION_RE.match("") is None  # 空字串
        assert PROTOCOL_VERSION_RE.match("a.b") is None  # 非數字

    def test_protocol_version_pattern_type(self):
        """驗證正則表達式型別"""
        assert isinstance(PROTOCOL_VERSION_PATTERN, str)
        assert PROTOCOL_VERSION_PATTERN == r"^\d+\.\d+$"

    def test_protocol_version_re_compiled(self):
        """驗證正則表達式已預編譯"""
        import re
        assert isinstance(PROTOCOL_VERSION_RE, re.Pattern)

    def test_protocol_version_migrations_structure(self):
        """驗證遷移鏈結構"""
        assert isinstance(PROTOCOL_VERSION_MIGRATIONS, dict)
        assert "1.0" in PROTOCOL_VERSION_MIGRATIONS

        # 驗證 v1.0 遷移規則
        v1_rule = PROTOCOL_VERSION_MIGRATIONS["1.0"]
        assert v1_rule["target"] == "2.0"
        assert v1_rule["handler"] == "migrate_v1_to_v2"
        assert v1_rule["breaking_changes"] is False
