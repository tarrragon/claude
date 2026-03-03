"""
ticket_builder 模組的回歸測試

確保從 create.py 提取的 7 個函式行為保持一致。

測試覆蓋：
- format_ticket_id() - 3 個案例（有/無 v 前綴、大序號）
- format_child_ticket_id() - 3 個案例（單層、多層、深層）
- get_next_seq() - 4 個案例（空目錄、現有 Ticket、忽略子任務、多 Wave）
- get_next_child_seq() - 3 個案例（無子任務、現有子任務、忽略深層）
- create_ticket_frontmatter() - 3 個案例（完整配置、最小配置、自訂驗收條件）
- create_ticket_body() - 2 個案例（正常結構、特殊字元）
- update_parent_children() - 3 個案例（新增子任務、追加、重複防止、父任務不存在）

總共：22 個測試案例
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import tempfile
import pytest

from ticket_system.lib.ticket_builder import (
    TicketConfig,
    format_ticket_id,
    format_child_ticket_id,
    get_next_seq,
    get_next_child_seq,
    create_ticket_frontmatter,
    create_ticket_body,
    update_parent_children,
)
from ticket_system.lib.ticket_loader import (
    get_tickets_dir,
    save_ticket,
    get_ticket_path,
)
from ticket_system.lib.constants import STATUS_PENDING


class TestFormatTicketId:
    """測試 format_ticket_id() 函式"""

    def test_format_ticket_id_with_v_prefix(self):
        """Given: 版本號帶 "v" 前綴（如 "v0.31.0"）、Wave 號 5、序號 1
        When: 呼叫 format_ticket_id("v0.31.0", 5, 1)
        Then: 返回 "0.31.0-W5-001"（移除 v 前綴，序號補零至 3 位）
        """
        result = format_ticket_id("v0.31.0", 5, 1)
        assert result == "0.31.0-W5-001"

    def test_format_ticket_id_without_v_prefix(self):
        """Given: 版本號無 "v" 前綴（如 "0.31.0"）、Wave 號 5、序號 15
        When: 呼叫 format_ticket_id("0.31.0", 5, 15)
        Then: 返回 "0.31.0-W5-015"
        """
        result = format_ticket_id("0.31.0", 5, 15)
        assert result == "0.31.0-W5-015"

    def test_format_ticket_id_large_sequence(self):
        """Given: 序號 999（大於 3 位）、Wave 號 10、版本 "0.32.0"
        When: 呼叫 format_ticket_id("0.32.0", 10, 999)
        Then: 返回 "0.32.0-W10-999"（保持原序號，不截斷）
        """
        result = format_ticket_id("0.32.0", 10, 999)
        assert result == "0.32.0-W10-999"


class TestFormatChildTicketId:
    """測試 format_child_ticket_id() 函式"""

    def test_format_child_ticket_id_single_level(self):
        """Given: 父任務 ID "0.31.0-W5-001"、子序號 1
        When: 呼叫 format_child_ticket_id("0.31.0-W5-001", 1)
        Then: 返回 "0.31.0-W5-001.1"
        """
        result = format_child_ticket_id("0.31.0-W5-001", 1)
        assert result == "0.31.0-W5-001.1"

    def test_format_child_ticket_id_multi_level(self):
        """Given: 父任務 ID "0.31.0-W5-001.1"（已有子任務）、子序號 2
        When: 呼叫 format_child_ticket_id("0.31.0-W5-001.1", 2)
        Then: 返回 "0.31.0-W5-001.1.2"（支援無限深度）
        """
        result = format_child_ticket_id("0.31.0-W5-001.1", 2)
        assert result == "0.31.0-W5-001.1.2"

    def test_format_child_ticket_id_deep_nesting(self):
        """Given: 深層子任務 ID "0.31.0-W5-001.1.1.1"、子序號 1
        When: 呼叫 format_child_ticket_id("0.31.0-W5-001.1.1.1", 1)
        Then: 返回 "0.31.0-W5-001.1.1.1.1"
        """
        result = format_child_ticket_id("0.31.0-W5-001.1.1.1", 1)
        assert result == "0.31.0-W5-001.1.1.1.1"


class TestGetNextSeq:
    """測試 get_next_seq() 函式"""

    def test_get_next_seq_empty_directory(self, monkeypatch, tmp_path):
        """Given: 臨時目錄中無任何 Ticket 檔案、版本 "0.31.0"、Wave 5
        When: 呼叫 get_next_seq("0.31.0", 5)
        Then: 返回 1
        """
        # 模擬 get_tickets_dir() 返回不存在的臨時目錄
        def mock_get_tickets_dir(version):
            return tmp_path / f"tickets_{version}"

        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_seq("0.31.0", 5)
        assert result == 1

    def test_get_next_seq_with_existing_tickets(self, monkeypatch, tmp_path):
        """Given: 臨時目錄中有 0.31.0-W5-001.md、0.31.0-W5-002.md、0.31.0-W5-003.md
        When: 呼叫 get_next_seq("0.31.0", 5)
        Then: 返回 4
        """
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        # 建立測試檔案
        (tickets_dir / "0.31.0-W5-001.md").touch()
        (tickets_dir / "0.31.0-W5-002.md").touch()
        (tickets_dir / "0.31.0-W5-003.md").touch()

        def mock_get_tickets_dir(version):
            return tickets_dir

        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_seq("0.31.0", 5)
        assert result == 4

    def test_get_next_seq_ignores_child_tickets(self, monkeypatch, tmp_path):
        """Given: 目錄中有 0.31.0-W5-001.md、0.31.0-W5-001.1.md、0.31.0-W5-001.1.1.md（有子任務）
        When: 呼叫 get_next_seq("0.31.0", 5)
        Then: 返回 2（只計算根任務 001，忽略 001.1 和 001.1.1 的點號部分）
        """
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        # 建立測試檔案
        (tickets_dir / "0.31.0-W5-001.md").touch()
        (tickets_dir / "0.31.0-W5-001.1.md").touch()
        (tickets_dir / "0.31.0-W5-001.1.1.md").touch()

        def mock_get_tickets_dir(version):
            return tickets_dir

        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_seq("0.31.0", 5)
        assert result == 2

    def test_get_next_seq_different_waves(self, monkeypatch, tmp_path):
        """Given: 目錄中有 0.31.0-W4-001.md、0.31.0-W5-001.md、0.31.0-W6-001.md
        When: 呼叫 get_next_seq("0.31.0", 5)
        Then: 返回 2（只計算 Wave 5 的 Ticket）
        """
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        # 建立不同 Wave 的檔案
        (tickets_dir / "0.31.0-W4-001.md").touch()
        (tickets_dir / "0.31.0-W5-001.md").touch()
        (tickets_dir / "0.31.0-W6-001.md").touch()

        def mock_get_tickets_dir(version):
            return tickets_dir

        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_seq("0.31.0", 5)
        assert result == 2


class TestGetNextChildSeq:
    """測試 get_next_child_seq() 函式"""

    def test_get_next_child_seq_no_children(self, monkeypatch):
        """Given: 父任務 "0.31.0-W5-001" 的 children 清單為空
        When: 呼叫 get_next_child_seq("0.31.0-W5-001")
        Then: 返回 1
        """
        def mock_load_ticket(version, ticket_id):
            return {"children": []}

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 1

    def test_get_next_child_seq_with_existing_children(self, monkeypatch):
        """Given: 父任務 "0.31.0-W5-001" 的 children 為 ["0.31.0-W5-001.1", "0.31.0-W5-001.2"]
        When: 呼叫 get_next_child_seq("0.31.0-W5-001")
        Then: 返回 3
        """
        def mock_load_ticket(version, ticket_id):
            return {"children": ["0.31.0-W5-001.1", "0.31.0-W5-001.2"]}

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 3

    def test_get_next_child_seq_ignores_deep_nesting(self, monkeypatch):
        """Given: 父任務 "0.31.0-W5-001" 的 children 為 ["0.31.0-W5-001.1", "0.31.0-W5-001.1.1"]（有孫任務）
        When: 呼叫 get_next_child_seq("0.31.0-W5-001")
        Then: 返回 2（只計算直接子任務 001.1，忽略 001.1.1）
        """
        def mock_load_ticket(version, ticket_id):
            return {"children": ["0.31.0-W5-001.1", "0.31.0-W5-001.1.1"]}

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 2


class TestCreateTicketFrontmatter:
    """測試 create_ticket_frontmatter() 函式"""

    def test_create_ticket_frontmatter_complete_config(self):
        """Given: 完整的 TicketConfig，包含所有 18 個欄位
        When: 呼叫 create_ticket_frontmatter(config)
        Then: 返回字典包含：
          - status = "pending"（固定）
          - created = 當前日期（YYYY-MM-DD 格式）
          - children = []（空清單）
          - who = {"current": config["who"], "history": {}}（結構化）
          - where = {"layer": config["where_layer"], "files": config["where_files"]}（結構化）
        """
        config: TicketConfig = {
            "ticket_id": "0.31.0-W5-001",
            "version": "0.31.0",
            "wave": 5,
            "title": "實作功能 X",
            "ticket_type": "IMP",
            "priority": "P1",
            "who": "parsley-flutter-developer",
            "what": "實作功能 X",
            "when": "Phase 3b",
            "where_layer": "Application",
            "where_files": ["lib/application/use_case.dart"],
            "why": "需求規格要求",
            "how_task_type": "Implementation",
            "how_strategy": "TDD Phase 3b"
        }

        frontmatter = create_ticket_frontmatter(config)

        assert frontmatter["id"] == "0.31.0-W5-001"
        assert frontmatter["status"] == STATUS_PENDING
        assert frontmatter["children"] == []
        assert frontmatter["who"]["current"] == "parsley-flutter-developer"
        assert frontmatter["who"]["history"] == {}
        assert frontmatter["where"]["layer"] == "Application"
        assert frontmatter["where"]["files"] == ["lib/application/use_case.dart"]

    def test_create_ticket_frontmatter_minimal_config(self):
        """Given: 最小化的 TicketConfig（只有必填欄位）
        When: 呼叫 create_ticket_frontmatter(config)
        Then: 返回字典中所有可選欄位都有預設值：
          - acceptance = ["[ ] 任務實作完成", "[ ] 相關測試通過", "[ ] 無程式碼品質警告"]（預設，帶 [ ] 前綴）
          - parent_id = None
          - tdd_stage = []
        """
        config: TicketConfig = {
            "ticket_id": "0.31.0-W5-001",
            "version": "0.31.0",
            "wave": 5,
            "title": "實作功能",
            "ticket_type": "IMP",
            "priority": "P1",
            "who": "parsley",
            "what": "實作",
            "when": "Phase 3b",
            "where_layer": "Application",
            "where_files": [],
            "why": "需求",
            "how_task_type": "Implementation",
            "how_strategy": "TDD"
        }

        frontmatter = create_ticket_frontmatter(config)

        assert frontmatter["acceptance"] == ["[ ] 任務實作完成", "[ ] 相關測試通過", "[ ] 無程式碼品質警告"]
        assert frontmatter["parent_id"] is None
        assert frontmatter["tdd_stage"] == []

    def test_create_ticket_frontmatter_with_acceptance(self):
        """Given: TicketConfig 包含自訂 acceptance 清單 ["AC1", "AC2"]（無前綴）
        When: 呼叫 create_ticket_frontmatter(config)
        Then: frontmatter["acceptance"] = ["[ ] AC1", "[ ] AC2"]（自動加上 [ ] 前綴）
        """
        config: TicketConfig = {
            "ticket_id": "0.31.0-W5-001",
            "version": "0.31.0",
            "wave": 5,
            "title": "實作功能",
            "ticket_type": "IMP",
            "priority": "P1",
            "who": "parsley",
            "what": "實作",
            "when": "Phase 3b",
            "where_layer": "Application",
            "where_files": [],
            "why": "需求",
            "how_task_type": "Implementation",
            "how_strategy": "TDD",
            "acceptance": ["AC1", "AC2"]
        }

        frontmatter = create_ticket_frontmatter(config)
        # 無前綴的項會自動加上 [ ] 前綴
        assert frontmatter["acceptance"] == ["[ ] AC1", "[ ] AC2"]

    def test_create_ticket_frontmatter_with_related_to(self):
        """Given: TicketConfig 包含 related_to = ["0.31.0-W5-002", "0.31.0-W5-003"]
        When: 呼叫 create_ticket_frontmatter(config)
        Then: frontmatter["relatedTo"] = ["0.31.0-W5-002", "0.31.0-W5-003"]
        """
        config: TicketConfig = {
            "ticket_id": "0.31.0-W5-001",
            "version": "0.31.0",
            "wave": 5,
            "title": "實作功能",
            "ticket_type": "IMP",
            "priority": "P1",
            "who": "parsley",
            "what": "實作",
            "when": "Phase 3b",
            "where_layer": "Application",
            "where_files": [],
            "why": "需求",
            "how_task_type": "Implementation",
            "how_strategy": "TDD",
            "related_to": ["0.31.0-W5-002", "0.31.0-W5-003"]
        }

        frontmatter = create_ticket_frontmatter(config)
        assert frontmatter["relatedTo"] == ["0.31.0-W5-002", "0.31.0-W5-003"]

    def test_create_ticket_frontmatter_empty_related_to(self):
        """Given: TicketConfig 未指定 related_to
        When: 呼叫 create_ticket_frontmatter(config)
        Then: frontmatter["relatedTo"] = []（預設空清單）
        """
        config: TicketConfig = {
            "ticket_id": "0.31.0-W5-001",
            "version": "0.31.0",
            "wave": 5,
            "title": "實作功能",
            "ticket_type": "IMP",
            "priority": "P1",
            "who": "parsley",
            "what": "實作",
            "when": "Phase 3b",
            "where_layer": "Application",
            "where_files": [],
            "why": "需求",
            "how_task_type": "Implementation",
            "how_strategy": "TDD"
        }

        frontmatter = create_ticket_frontmatter(config)
        assert frontmatter["relatedTo"] == []


class TestCreateTicketBody:
    """測試 create_ticket_body() 函式"""

    def test_create_ticket_body_structure(self):
        """Given: what = "實作功能 X"、who = "parsley-flutter-developer"
        When: 呼叫 create_ticket_body(what, who)
        Then: 返回的 Markdown 包含所有必要的部分
        """
        body = create_ticket_body("實作功能 X", "parsley-flutter-developer")

        assert "# Execution Log" in body
        assert "## Task Summary" in body
        assert "實作功能 X" in body
        assert "## Problem Analysis" in body
        assert "## Solution" in body
        assert "## Test Results" in body
        assert "## Completion Info" in body
        assert "**Executing Agent**: parsley-flutter-developer" in body

    def test_create_ticket_body_with_special_characters(self):
        """Given: what = "實作 [特殊] {字元} & 符號"、who = "sage-test-architect"
        When: 呼叫 create_ticket_body(what, who)
        Then: 返回的 Markdown 正確處理特殊字元（無異常、符號保留）
        """
        what = "實作 [特殊] {字元} & 符號"
        body = create_ticket_body(what, "sage-test-architect")

        assert what in body
        assert "sage-test-architect" in body


class TestUpdateParentChildren:
    """測試 update_parent_children() 函式"""

    def test_update_parent_children_new_child(self, monkeypatch, tmp_path):
        """Given: 父任務 0.31.0-W5-001 存在但 children 清單為空、新子任務 0.31.0-W5-001.1
        When: 呼叫 update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.1")
        Then: 返回 True，且父任務的 children 現在包含 ["0.31.0-W5-001.1"]
        """
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        # 建立父任務檔案
        parent_ticket = {
            "id": "0.31.0-W5-001",
            "children": [],
            "_path": str(tickets_dir / "0.31.0-W5-001.md")
        }
        parent_path = tickets_dir / "0.31.0-W5-001.md"
        save_ticket(parent_ticket, parent_path)

        def mock_load_ticket(version, ticket_id):
            return parent_ticket

        def mock_get_ticket_path(version, ticket_id):
            return str(parent_path)

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_ticket_path", mock_get_ticket_path)

        result = update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.1")

        assert result is True
        assert "0.31.0-W5-001.1" in parent_ticket["children"]

    def test_update_parent_children_append_to_existing(self, monkeypatch):
        """Given: 父任務已有 children = ["0.31.0-W5-001.1"]、新增子任務 0.31.0-W5-001.2
        When: 呼叫 update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.2")
        Then: 返回 True，children 變為 ["0.31.0-W5-001.1", "0.31.0-W5-001.2"]
        """
        parent_ticket = {
            "id": "0.31.0-W5-001",
            "children": ["0.31.0-W5-001.1"],
            "_path": "/tmp/test.md"
        }

        def mock_load_ticket(version, ticket_id):
            return parent_ticket

        def mock_save_ticket(ticket, path):
            pass

        def mock_get_ticket_path(version, ticket_id):
            return "/tmp/test.md"

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.save_ticket", mock_save_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_ticket_path", mock_get_ticket_path)

        result = update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.2")

        assert result is True
        assert parent_ticket["children"] == ["0.31.0-W5-001.1", "0.31.0-W5-001.2"]

    def test_update_parent_children_duplicate_prevention(self, monkeypatch):
        """Given: 父任務已有 children = ["0.31.0-W5-001.1"]、嘗試新增同一子任務
        When: 呼叫 update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.1")
        Then: 返回 True，children 仍為 ["0.31.0-W5-001.1"]（不重複新增）
        """
        parent_ticket = {
            "id": "0.31.0-W5-001",
            "children": ["0.31.0-W5-001.1"],
            "_path": "/tmp/test.md"
        }

        def mock_load_ticket(version, ticket_id):
            return parent_ticket

        def mock_get_ticket_path(version, ticket_id):
            return "/tmp/test.md"

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_ticket_path", mock_get_ticket_path)

        result = update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.1")

        assert result is True
        assert parent_ticket["children"] == ["0.31.0-W5-001.1"]

    def test_update_parent_children_parent_not_found(self, monkeypatch):
        """Given: 父任務 "0.31.0-W5-999" 不存在
        When: 呼叫 update_parent_children("0.31.0", "0.31.0-W5-999", "0.31.0-W5-999.1")
        Then: 返回 False，不拋出異常
        """
        def mock_load_ticket(version, ticket_id):
            return None

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)

        result = update_parent_children("0.31.0", "0.31.0-W5-999", "0.31.0-W5-999.1")

        assert result is False
