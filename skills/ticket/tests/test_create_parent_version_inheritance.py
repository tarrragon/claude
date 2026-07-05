"""
--parent 版本繼承回歸測試（1.5.0-W5-005.13）

問題：--parent 未帶 --version 時，版本歸屬引導（suggest_version_for_ticket）會
推導根票邏輯下的建議版本（如 1.3.2），若該版本未在 todolist.yaml 註冊，
validate_version_registered 會 hard-fail（VERSION_NOT_REGISTERED），導致子票
建立失敗。修復後：子任務（--parent 存在）version 無條件繼承父票，完全跳過
版本歸屬引導與 VERSION_NOT_REGISTERED 檢查；根票行為不變。

Mock 策略（Sociable Unit Tests，比照 test_create_source_ticket.py）：
- Unit = Module：execute 與其使用的 validator/loader/builder 視為一個 module
- Mock 外部邊界：檔案 I/O（load_ticket / list_tickets / get_next_seq /
  get_next_child_seq / _build_and_save_ticket / get_ticket_path /
  update_parent_children）
- 不 mock extract_version_from_ticket_id（內層純函式，驗證真實解析行為）
"""

import argparse
from unittest.mock import MagicMock
import pytest

from ticket_system.commands.create import execute


def _make_args(**overrides) -> argparse.Namespace:
    """建立完整的 args Namespace（預設值涵蓋 execute 會讀的所有欄位）。"""
    defaults = {
        "version": None,
        "wave": None,
        "seq": None,
        "type": "IMP",
        "priority": "P2",
        "action": "實作",
        "target": "測試目標",
        "title": "子任務測試 Ticket",
        "who": "thyme-python-developer",
        "what": "測試用 what",
        "when": "測試用 when",
        "where_layer": "Infrastructure",
        "where_files": "src/test.py",
        "why": "測試用 why",
        "how_type": None,
        "how_strategy": "測試策略",
        "parent": None,
        "source_ticket": None,
        "blocked_by": None,
        "related_to": None,
        "acceptance": ["驗收條件 A"],
        "decision_tree_entry": "第三層",
        "decision_tree_decision": "建立 IMP",
        "decision_tree_rationale": "W5-005.13 測試",
        "force": False,
        "quiet": False,
        "verbose": False,
        "json_output": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _install_common_mocks(monkeypatch, *, parent_ticket=None):
    """安裝 execute() 需要的外部邊界 mock（不 mock resolve_version /
    validate_version_registered，讓子票路徑真實跳過這兩者的呼叫）。
    """
    monkeypatch.setattr(
        "ticket_system.commands.create.list_tickets",
        lambda v: [],
    )

    def _load_ticket(version, ticket_id):
        if parent_ticket is not None and ticket_id == parent_ticket.get("id"):
            return parent_ticket
        return None

    monkeypatch.setattr(
        "ticket_system.commands.create.load_ticket",
        _load_ticket,
    )

    stub_ticket = {
        "id": "stub",
        "title": "stub",
        "what": "stub",
        "type": "IMP",
        "where": {"files": ["src/test.py"]},
        "how": {"strategy": "測試策略"},
    }
    monkeypatch.setattr(
        "ticket_system.commands.create._build_and_save_ticket",
        lambda v, tid, cfg: stub_ticket,
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.get_ticket_path",
        lambda v, tid: f"/tmp/tickets/{tid}.md",
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.update_parent_children",
        lambda v, pid, tid: True,
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.get_next_seq",
        lambda v, w: 1,
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.get_next_child_seq",
        lambda pid: 1,
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.compute_depth",
        lambda pid, v: 1,
    )


class TestParentVersionInheritance:
    """--parent 存在時 version/wave 應無條件繼承父票，跳過版本歸屬引導與註冊檢查。"""

    def test_child_without_version_inherits_parent_version(self, monkeypatch):
        """--parent 不帶 --version 時，version 直接從 --parent ticket ID 解析，
        不呼叫 resolve_version / validate_version_registered（不應觸發
        VERSION_NOT_REGISTERED），建票成功（exit 0）。
        """
        _install_common_mocks(monkeypatch)

        resolve_version_mock = MagicMock()
        monkeypatch.setattr(
            "ticket_system.commands.create.resolve_version",
            resolve_version_mock,
        )
        validate_registered_mock = MagicMock()
        monkeypatch.setattr(
            "ticket_system.lib.version.validate_version_registered",
            validate_registered_mock,
        )

        args = _make_args(parent="1.5.0-W5-005")
        result = execute(args)

        assert result == 0
        # 子票路徑不應呼叫版本註冊檢查（避免未註冊版本 hard-fail）
        validate_registered_mock.assert_not_called()

    def test_child_ticket_id_uses_parent_version(self, monkeypatch, capsys):
        """--parent 1.5.0-W5-005 --> 子票 ID 應落在 1.5.0（父票版本），
        而非版本歸屬引導可能推導出的其他版本。
        """
        _install_common_mocks(monkeypatch)
        monkeypatch.setattr(
            "ticket_system.commands.create.resolve_version",
            lambda v: v,
        )

        captured_config = {}

        def _capture_build(version, ticket_id, cfg):
            captured_config["version"] = version
            captured_config["ticket_id"] = ticket_id
            return {
                "id": ticket_id,
                "title": "stub",
                "what": "stub",
                "type": "IMP",
                "where": {"files": ["src/test.py"]},
                "how": {"strategy": "測試策略"},
            }

        monkeypatch.setattr(
            "ticket_system.commands.create._build_and_save_ticket",
            _capture_build,
        )

        args = _make_args(parent="1.5.0-W5-005")
        result = execute(args)

        assert result == 0
        assert captured_config["version"] == "1.5.0"
        assert captured_config["ticket_id"].startswith("1.5.0-W5-")

    def test_root_ticket_version_guidance_unchanged(self, monkeypatch, capsys):
        """根票（無 --parent）：版本歸屬引導與註冊檢查行為不變——
        建議版本未註冊時仍應 hard-fail（VERSION_NOT_REGISTERED）。
        """
        _install_common_mocks(monkeypatch)
        monkeypatch.setattr(
            "ticket_system.commands.create.resolve_version",
            lambda v: v or "9.9.9",
        )
        monkeypatch.setattr(
            "ticket_system.commands.create.suggest_version_for_ticket",
            lambda ticket_type, action: ("9.9.9", "測試引導"),
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.validate_version_registered",
            lambda v: (False, f"版本 {v} 未在 todolist.yaml 註冊"),
        )

        args = _make_args(wave=5)
        result = execute(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "VERSION_NOT_REGISTERED" in captured.out

    def test_root_ticket_success_path_unchanged(self, monkeypatch):
        """根票（無 --parent）：版本已註冊時建票成功，行為與修復前一致。"""
        _install_common_mocks(monkeypatch)
        monkeypatch.setattr(
            "ticket_system.commands.create.resolve_version",
            lambda v: v or "1.5.0",
        )
        monkeypatch.setattr(
            "ticket_system.commands.create.suggest_version_for_ticket",
            lambda ticket_type, action: None,
        )
        monkeypatch.setattr(
            "ticket_system.lib.version.validate_version_registered",
            lambda v: (True, ""),
        )

        args = _make_args(wave=5, version="1.5.0")
        result = execute(args)

        assert result == 0
