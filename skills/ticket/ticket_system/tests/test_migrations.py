"""
Protocol Version 遷移邏輯單元測試

測試從 v1.0 向 v2.0 的遷移邏輯，確保無資訊遺失和格式驗證正確。
"""
import pytest

from ticket_system.lib.migrations import (
    ProtocolVersionError,
    is_valid_version_format,
    migrate_ticket,
    migrate_v1_to_v2,
)


class TestVersionFormatValidation:
    """版本格式驗證測試"""

    def test_valid_format_v2_0(self):
        """TC-004.1: 有效格式 '2.0' 應匹配"""
        assert is_valid_version_format("2.0") is True

    def test_valid_format_v1_0(self):
        """TC-004.2: 有效格式 '1.0' 應匹配"""
        assert is_valid_version_format("1.0") is True

    def test_invalid_format_v_prefix(self):
        """TC-005: 無效格式 'v2.0' 應不匹配（v 前綴）"""
        assert is_valid_version_format("v2.0") is False

    def test_invalid_format_missing_minor(self):
        """TC-006: 無效格式 '2' 應不匹配（缺少 Minor）"""
        assert is_valid_version_format("2") is False

    def test_invalid_format_three_level(self):
        """TC-007: 無效格式 '2.0.1' 應不匹配（三層版本）"""
        assert is_valid_version_format("2.0.1") is False

    def test_invalid_format_empty_string(self):
        """TC-008: 空字串應不匹配"""
        assert is_valid_version_format("") is False

    def test_invalid_format_non_numeric(self):
        """TC-009: 非數字格式應不匹配"""
        assert is_valid_version_format("a.b") is False


class TestMigrateTicket:
    """ticket 遷移函式測試"""

    def test_migrate_old_ticket_without_protocol_version(self):
        """TC-010: 遷移無 protocol_version 的舊 ticket"""
        old_ticket = {
            "id": "0.1.0-W1-001",
            "title": "Old Ticket",
            "status": "pending",
        }

        migrated, history = migrate_ticket(old_ticket)

        # 驗證版本已升級
        assert migrated["protocol_version"] == "2.0"
        # 驗證原有欄位保留
        assert migrated["id"] == "0.1.0-W1-001"
        assert migrated["title"] == "Old Ticket"
        assert migrated["status"] == "pending"
        # 驗證遷移歷史
        assert len(history) == 1
        assert history[0]["from"] == "1.0"
        assert history[0]["to"] == "2.0"
        assert history[0]["status"] == "success"
        assert history[0]["handler"] == "migrate_v1_to_v2"

    def test_migrate_v2_ticket_no_migration_needed(self):
        """TC-011: 已是 v2.0 的 ticket 無需遷移"""
        v2_ticket = {
            "id": "0.1.2-W1-001",
            "protocol_version": "2.0",
            "title": "V2 Ticket",
        }

        migrated, history = migrate_ticket(v2_ticket)

        # 驗證版本不變
        assert migrated["protocol_version"] == "2.0"
        # 驗證無遷移步驟
        assert len(history) == 0

    def test_migrate_invalid_version_format_raises_error(self):
        """TC-012: 無效的版本格式應拋出 ProtocolVersionError"""
        invalid_ticket = {
            "id": "0.1.0-W1-001",
            "protocol_version": "v2.0",  # 無效格式
        }

        with pytest.raises(ProtocolVersionError) as exc_info:
            migrate_ticket(invalid_ticket)

        assert "無效版本格式" in str(exc_info.value)

    def test_migrate_preserves_all_fields(self):
        """TC-013: 遷移應保留所有現有欄位"""
        old_ticket = {
            "id": "0.31.0-W3-001",
            "title": "Complete Ticket",
            "status": "in_progress",
            "what": "實作功能 X",
            "where": {"files": ["lib/main.dart"]},
            "why": "滿足需求 Y",
            "acceptance": ["條件 1", "條件 2"],
            "custom_field": "custom_value",
        }

        migrated, history = migrate_ticket(old_ticket)

        # 驗證所有原有欄位都保留
        for key, value in old_ticket.items():
            assert migrated[key] == value
        # 驗證新欄位已添加
        assert "protocol_version" in migrated
        assert migrated["protocol_version"] == "2.0"


class TestMigrateV1ToV2:
    """v1 到 v2 遷移函式測試"""

    def test_migrate_v1_to_v2_basic(self):
        """TC-014: 基本 v1→v2 遷移"""
        v1_data = {
            "id": "0.1.0-W1-001",
            "title": "Test Ticket",
            "status": "pending",
        }

        v2_data = migrate_v1_to_v2(v1_data)

        # 驗證新欄位已添加
        assert v2_data["creation_accepted"] is False
        assert v2_data["tdd_phase"] is None
        assert v2_data["tdd_stage"] == []
        # 驗證原有欄位保留
        assert v2_data["id"] == "0.1.0-W1-001"
        assert v2_data["title"] == "Test Ticket"

    def test_migrate_v1_to_v2_preserves_existing_new_fields(self):
        """TC-015: 若新欄位已存在，遷移應保留現有值"""
        v1_data = {
            "id": "0.1.0-W1-001",
            "creation_accepted": True,
            "tdd_phase": "phase2",
            "tdd_stage": ["phase1"],
        }

        v2_data = migrate_v1_to_v2(v1_data)

        # 驗證現有值被保留
        assert v2_data["creation_accepted"] is True
        assert v2_data["tdd_phase"] == "phase2"
        assert v2_data["tdd_stage"] == ["phase1"]

    def test_migrate_v1_to_v2_no_data_loss(self):
        """TC-016: v1→v2 遷移無資訊遺失"""
        v1_data = {
            "id": "0.31.0-W3-001",
            "title": "Ticket",
            "status": "completed",
            "what": "做某事",
            "where": {"files": ["lib/a.dart", "lib/b.dart"]},
            "why": "因為需要",
            "acceptance": ["A", "B", "C"],
            "custom_field_1": "value1",
            "custom_field_2": {"nested": "value"},
        }

        v2_data = migrate_v1_to_v2(v1_data)

        # 驗證所有原有欄位都保留
        for key in v1_data:
            assert key in v2_data
            assert v2_data[key] == v1_data[key]

    def test_migrate_empty_ticket(self):
        """TC-017: 遷移空 ticket（僅 id）"""
        empty_ticket = {"id": "0.1.0-W1-001"}

        v2_data = migrate_v1_to_v2(empty_ticket)

        assert v2_data["id"] == "0.1.0-W1-001"
        assert v2_data["creation_accepted"] is False
        assert v2_data["tdd_phase"] is None
        assert v2_data["tdd_stage"] == []
