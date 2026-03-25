"""
Protocol Version Check Hook 集成測試

驗證 Hook 邏輯（版本遷移）在 ticket 載入場景中的正確性。
"""
import pytest

from ticket_system.lib.migrations import migrate_ticket


class TestProtocolVersionHookIntegration:
    """Protocol Version Check Hook 集成測試"""

    def test_hook_scenario_migrate_old_ticket(self):
        """TC-020: 模擬 Hook 場景 - 自動遷移無 protocol_version 的舊 ticket"""
        # 模擬從磁碟載入的舊 ticket
        ticket_from_disk = {
            "id": "0.1.0-W1-001",
            "title": "Old Ticket",
            "status": "pending",
            # 無 protocol_version 欄位
        }

        # Hook 會呼叫 migrate_ticket()
        migrated_ticket, history = migrate_ticket(ticket_from_disk)

        # 驗證 Hook 的預期結果
        assert migrated_ticket["protocol_version"] == "2.0"
        assert migrated_ticket["id"] == "0.1.0-W1-001"
        assert migrated_ticket["title"] == "Old Ticket"
        assert len(history) == 1
        assert history[0]["from"] == "1.0"
        assert history[0]["to"] == "2.0"

    def test_hook_scenario_preserve_v2_ticket(self):
        """TC-021: 模擬 Hook 場景 - 保留已是 v2.0 的 ticket"""
        # 模擬已是新版本的 ticket
        ticket_from_disk = {
            "id": "0.1.2-W1-001",
            "protocol_version": "2.0",
            "title": "V2 Ticket",
            "creation_accepted": False,
        }

        # Hook 會呼叫 migrate_ticket()
        migrated_ticket, history = migrate_ticket(ticket_from_disk)

        # 驗證無需遷移
        assert migrated_ticket["protocol_version"] == "2.0"
        assert len(history) == 0
        assert migrated_ticket["id"] == "0.1.2-W1-001"

    def test_hook_scenario_invalid_format_handled(self):
        """TC-022: 模擬 Hook 場景 - 處理無效的版本格式"""
        # 模擬格式異常的 ticket
        ticket_from_disk = {
            "id": "0.1.0-W1-001",
            "protocol_version": "v2.0",  # 無效格式
        }

        # Hook 應該捕捉異常並輸出警告（不拋出異常）
        from ticket_system.lib.migrations import ProtocolVersionError

        with pytest.raises(ProtocolVersionError):
            migrate_ticket(ticket_from_disk)

    def test_hook_scenario_adds_defaults_during_migration(self):
        """TC-023: 模擬 Hook 場景 - 遷移時添加新欄位的預設值"""
        # 模擬舊 ticket（無新欄位）
        old_ticket = {
            "id": "0.31.0-W3-001",
            "title": "Complete Ticket",
        }

        # Hook 呼叫 migrate_ticket() 進行遷移
        migrated_ticket, _ = migrate_ticket(old_ticket)

        # 驗證新欄位已添加默認值
        assert migrated_ticket["creation_accepted"] is False
        assert migrated_ticket["tdd_phase"] is None
        assert migrated_ticket["tdd_stage"] == []
        # 驗證原有欄位保留
        assert migrated_ticket["id"] == "0.31.0-W3-001"
        assert migrated_ticket["title"] == "Complete Ticket"
