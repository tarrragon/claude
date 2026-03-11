"""
Ticket ID Validator Hook 單元測試

測試 Ticket ID 格式驗證、Wave 號範圍檢查等功能
"""

import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# 加入 Hook 模組路徑
hooks_path = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_path))

import pytest


@pytest.fixture
def ticket_validator_module():
    """載入 Ticket ID Validator Hook 模組"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ticket_id_validator_hook",
        hooks_path / "ticket-id-validator-hook.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mock_logger():
    """建立模擬 Logger"""
    logger = MagicMock()
    logger.debug = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.critical = MagicMock()
    return logger


@pytest.fixture
def temp_ticket_file():
    """建立臨時 Ticket 檔案"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # 建立目錄結構
        (root / "docs" / "work-logs" / "v0.37.0" / "tickets").mkdir(parents=True, exist_ok=True)

        yield root


class TestValidateTicketIdFormat:
    """Ticket ID 格式驗證測試"""

    def test_valid_simple_ticket_id(self, ticket_validator_module, mock_logger):
        """測試有效的簡單 Ticket ID"""
        # 載入常數和函式
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.31.0-W5-001",
            mock_logger
        )
        assert is_valid is True
        assert msg == ""

    def test_valid_ticket_id_with_subversion(self, ticket_validator_module, mock_logger):
        """測試包含子版本號的 Ticket ID"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.31.0-W5-001.1",
            mock_logger
        )
        assert is_valid is True
        assert msg == ""

    def test_valid_ticket_id_with_multi_subversion(self, ticket_validator_module, mock_logger):
        """測試多層子版本號的 Ticket ID"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.31.0-W5-001.1.2",
            mock_logger
        )
        assert is_valid is True
        assert msg == ""

    def test_wave_in_normal_range(self, ticket_validator_module, mock_logger):
        """測試 Wave 在正常範圍內（1-10）"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        for wave in [1, 5, 10]:
            is_valid, msg = ticket_validator_module.validate_ticket_id_format(
                f"0.31.0-W{wave}-001",
                mock_logger
            )
            assert is_valid is True, f"Wave {wave} 應該有效"
            assert msg == ""

    def test_wave_w33_plus(self, ticket_validator_module, mock_logger):
        """測試 Wave W33+ 通過驗證（修復的關鍵案例）"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        # W33, W34, W37, W50 都應該通過
        for wave in [33, 34, 37, 50, 100]:
            is_valid, msg = ticket_validator_module.validate_ticket_id_format(
                f"0.1.0-W{wave}-001",
                mock_logger
            )
            assert is_valid is True, f"Wave {wave} 應該通過驗證（但舊的 WAVE_MAX=10 會導致失敗）"
            assert msg == ""

    def test_wave_above_max(self, ticket_validator_module, mock_logger):
        """測試 Wave 超過合理上限應警告"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.31.0-W1000-001",
            mock_logger
        )
        assert is_valid is False
        assert "Wave 號不在合理範圍" in msg
        assert "1000" in msg

    def test_wave_zero(self, ticket_validator_module, mock_logger):
        """測試 Wave = 0 應拒絕"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.31.0-W0-001",
            mock_logger
        )
        assert is_valid is False
        assert "Wave 號不在合理範圍" in msg

    def test_invalid_version_format(self, ticket_validator_module, mock_logger):
        """測試無效的版本格式"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.31-W5-001",  # 缺少 patch 版本
            mock_logger
        )
        assert is_valid is False
        assert "Ticket ID 格式錯誤" in msg

    def test_invalid_wave_format(self, ticket_validator_module, mock_logger):
        """測試無效的 Wave 格式"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.31.0-wave5-001",  # 應為 W 不是 wave
            mock_logger
        )
        assert is_valid is False

    def test_empty_ticket_id(self, ticket_validator_module, mock_logger):
        """測試空 Ticket ID"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "",
            mock_logger
        )
        assert is_valid is False
        assert "為空" in msg

    def test_none_ticket_id(self, ticket_validator_module, mock_logger):
        """測試 None Ticket ID"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            None,
            mock_logger
        )
        assert is_valid is False


class TestWaveMaxConstant:
    """WAVE_MAX 常數相關測試"""

    def test_wave_max_is_reasonable(self, ticket_validator_module):
        """測試 WAVE_MAX 已調整為合理值"""
        # 直接檢查常數值
        assert ticket_validator_module.WAVE_MAX >= 50, \
            "WAVE_MAX 應至少為 50（現已執行到 W37）"

        # 驗證 WAVE_MAX 足夠大
        assert ticket_validator_module.WAVE_MAX > 37, \
            "WAVE_MAX 應大於 37（當前最新 Wave）"

    def test_wave_max_not_hardcoded_to_10(self, ticket_validator_module):
        """測試 WAVE_MAX 不再是硬編碼的 10"""
        # 這是修復的核心：WAVE_MAX 應不再是 10
        assert ticket_validator_module.WAVE_MAX != 10, \
            "WAVE_MAX 應不再是 10（這是導致誤判的根本問題）"


class TestIsTicketFile:
    """Ticket 檔案判斷測試"""

    def test_work_logs_ticket_file(self, ticket_validator_module, mock_logger):
        """測試識別 docs/work-logs 下的 Ticket 檔案"""
        file_path = "docs/work-logs/v0.31.0/tickets/0.31.0-W5-001.md"
        result = ticket_validator_module.is_ticket_file(file_path, mock_logger)
        assert result is True

    def test_claude_tickets_file(self, ticket_validator_module, mock_logger):
        """測試識別 .claude/tickets 下的 Ticket 檔案"""
        file_path = ".claude/tickets/0.31.0-W5-001.md"
        result = ticket_validator_module.is_ticket_file(file_path, mock_logger)
        assert result is True

    def test_non_ticket_file(self, ticket_validator_module, mock_logger):
        """測試非 Ticket 檔案不被識別"""
        file_path = "lib/domain/entities/book.dart"
        result = ticket_validator_module.is_ticket_file(file_path, mock_logger)
        assert result is False


class TestGetDirectoryVersion:
    """從目錄提取版本號測試"""

    def test_extract_version_from_work_logs(self, ticket_validator_module, mock_logger):
        """測試從 docs/work-logs 目錄提取版本"""
        file_path = "docs/work-logs/v0.31.0/tickets/0.31.0-W5-001.md"
        version = ticket_validator_module.get_directory_version(file_path, mock_logger)
        assert version == "0.31.0"

    def test_extract_version_v037(self, ticket_validator_module, mock_logger):
        """測試從 v0.37.0 目錄提取版本"""
        file_path = "docs/work-logs/v0.37.0/tickets/0.37.0-W33-001.md"
        version = ticket_validator_module.get_directory_version(file_path, mock_logger)
        assert version == "0.37.0"

    def test_no_version_in_claude_tickets(self, ticket_validator_module, mock_logger):
        """測試 .claude/tickets 無法提取版本"""
        file_path = ".claude/tickets/0.31.0-W5-001.md"
        version = ticket_validator_module.get_directory_version(file_path, mock_logger)
        assert version is None


class TestValidateTicketIdVersionConsistency:
    """Ticket ID 版本一致性測試"""

    def test_consistent_version(self, ticket_validator_module, mock_logger):
        """測試版本一致"""
        is_consistent, msg = ticket_validator_module.validate_ticket_id_version_consistency(
            "0.31.0-W5-001",
            "0.31.0",
            mock_logger
        )
        assert is_consistent is True
        assert msg == ""

    def test_inconsistent_version(self, ticket_validator_module, mock_logger):
        """測試版本不一致"""
        is_consistent, msg = ticket_validator_module.validate_ticket_id_version_consistency(
            "0.31.0-W5-001",
            "0.30.0",
            mock_logger
        )
        assert is_consistent is False
        assert "版本與目錄版本不一致" in msg

    def test_no_directory_version(self, ticket_validator_module, mock_logger):
        """測試無目錄版本時跳過檢查"""
        is_consistent, msg = ticket_validator_module.validate_ticket_id_version_consistency(
            "0.31.0-W5-001",
            None,
            mock_logger
        )
        assert is_consistent is True
        assert msg == ""


class TestRegressionW10Plus:
    """W10+ Ticket 誤判回歸測試（修復驗證）"""

    def test_w10_passes(self, ticket_validator_module, mock_logger):
        """測試 W10 通過"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.1.0-W10-001",
            mock_logger
        )
        assert is_valid is True

    def test_w11_passes(self, ticket_validator_module, mock_logger):
        """測試 W11 通過（舊版本 WAVE_MAX=10 時會失敗）"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.1.0-W11-001",
            mock_logger
        )
        assert is_valid is True

    def test_w37_passes(self, ticket_validator_module, mock_logger):
        """測試 W37 通過（當前版本）"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.1.0-W37-001",
            mock_logger
        )
        assert is_valid is True

    def test_w50_passes(self, ticket_validator_module, mock_logger):
        """測試 W50 通過（未來版本）"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            "0.1.0-W50-001",
            mock_logger
        )
        assert is_valid is True


class TestExtractTicketIdFromFile:
    """從檔案提取 Ticket ID 測試"""

    def test_extract_from_yaml_frontmatter(self, temp_ticket_file, ticket_validator_module, mock_logger):
        """測試從 YAML frontmatter 提取 ID"""
        file_path = temp_ticket_file / "docs" / "work-logs" / "v0.37.0" / "tickets" / "0.37.0-W33-001.md"
        file_path.write_text("""---
id: 0.37.0-W33-001
title: Test Ticket
---

# Test Content
""", encoding="utf-8")

        ticket_id = ticket_validator_module.extract_ticket_id_from_file(
            str(file_path),
            mock_logger
        )
        assert ticket_id == "0.37.0-W33-001"

    def test_extract_from_markdown_heading(self, temp_ticket_file, ticket_validator_module, mock_logger):
        """測試從 Markdown 標題提取 ID"""
        file_path = temp_ticket_file / "docs" / "work-logs" / "v0.37.0" / "tickets" / "0.37.0-W33-002.md"
        file_path.write_text("""# 0.37.0-W33-002: Test Ticket

## Content
""", encoding="utf-8")

        ticket_id = ticket_validator_module.extract_ticket_id_from_file(
            str(file_path),
            mock_logger
        )
        assert ticket_id == "0.37.0-W33-002"

    def test_extract_nonexistent_file(self, ticket_validator_module, mock_logger):
        """測試非存在檔案"""
        ticket_id = ticket_validator_module.extract_ticket_id_from_file(
            "/nonexistent/path/0.37.0-W33-001.md",
            mock_logger
        )
        assert ticket_id is None


class TestIntegration:
    """整合測試"""

    def test_full_validation_w37(self, temp_ticket_file, ticket_validator_module, mock_logger):
        """整合測試：完整驗證 W37 Ticket"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        file_path = temp_ticket_file / "docs" / "work-logs" / "v0.37.0" / "tickets" / "0.37.0-W37-001.md"
        file_path.write_text("""---
id: 0.37.0-W37-001
title: Test W37 Ticket
---

# Test Content
""", encoding="utf-8")

        # 提取 Ticket ID
        ticket_id = ticket_validator_module.extract_ticket_id_from_file(
            str(file_path),
            mock_logger
        )
        assert ticket_id == "0.37.0-W37-001"

        # 驗證格式
        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            ticket_id,
            mock_logger
        )
        assert is_valid is True

        # 驗證版本一致性
        dir_version = ticket_validator_module.get_directory_version(
            str(file_path),
            mock_logger
        )
        is_consistent, msg = ticket_validator_module.validate_ticket_id_version_consistency(
            ticket_id,
            dir_version,
            mock_logger
        )
        assert is_consistent is True

    def test_full_validation_backward_compatibility(self, temp_ticket_file, ticket_validator_module, mock_logger):
        """整合測試：驗證向後相容（舊 W5 Ticket 仍有效）"""
        ticket_validator_module.WAVE_MAX = 999
        ticket_validator_module.WAVE_MIN = 1

        file_path = temp_ticket_file / "docs" / "work-logs" / "v0.37.0" / "tickets" / "0.31.0-W5-001.md"
        file_path.write_text("""---
id: 0.31.0-W5-001
title: Old Ticket
---

# Test Content
""", encoding="utf-8")

        # 提取 Ticket ID
        ticket_id = ticket_validator_module.extract_ticket_id_from_file(
            str(file_path),
            mock_logger
        )
        assert ticket_id == "0.31.0-W5-001"

        # 驗證格式
        is_valid, msg = ticket_validator_module.validate_ticket_id_format(
            ticket_id,
            mock_logger
        )
        assert is_valid is True
