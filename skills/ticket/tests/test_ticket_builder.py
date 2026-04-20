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
- update_source_spawned_tickets() - 6 個案例（A1-A6；PC-073）
- create_ticket_frontmatter(source_ticket) - 3 個案例（D1-D3；PC-073）

總共：既有 22 + 新增 9 = 31+ 測試案例
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
    update_source_spawned_tickets,
    get_default_acceptance_criteria,
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

    def test_get_next_child_seq_no_children(self, monkeypatch, tmp_path):
        """Given: 父任務 children 為空，檔案系統無子 Ticket
        When: 呼叫 get_next_child_seq
        Then: 返回 1
        """
        def mock_load_ticket(version, ticket_id):
            return {"children": []}

        def mock_get_tickets_dir(version):
            return tmp_path

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 1

    def test_get_next_child_seq_with_existing_children(self, monkeypatch, tmp_path):
        """Given: 父任務 children 有兩個子任務
        When: 呼叫 get_next_child_seq
        Then: 返回 3
        """
        def mock_load_ticket(version, ticket_id):
            return {"children": ["0.31.0-W5-001.1", "0.31.0-W5-001.2"]}

        def mock_get_tickets_dir(version):
            return tmp_path

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 3

    def test_get_next_child_seq_ignores_deep_nesting(self, monkeypatch, tmp_path):
        """Given: children 含孫任務 001.1.1
        When: 呼叫 get_next_child_seq
        Then: 返回 2（只計算直接子任務 001.1）
        """
        def mock_load_ticket(version, ticket_id):
            return {"children": ["0.31.0-W5-001.1", "0.31.0-W5-001.1.1"]}

        def mock_get_tickets_dir(version):
            return tmp_path

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 2

    def test_get_next_child_seq_files_override_empty_children(self, monkeypatch, tmp_path):
        """Given: 父任務 children 為空，但檔案系統有 001.1.md 和 001.2.md
        When: 呼叫 get_next_child_seq
        Then: 返回 3（從檔案系統偵測到最大序號 2）

        驗證修復：即使父 Ticket 的 children 欄位未同步，
        也能從檔案系統正確偵測已存在的子 Ticket。
        """
        # 建立子 Ticket 檔案（模擬 children 欄位未同步的情況）
        (tmp_path / "0.31.0-W5-001.1.md").touch()
        (tmp_path / "0.31.0-W5-001.2.md").touch()

        def mock_load_ticket(version, ticket_id):
            return {"children": []}

        def mock_get_tickets_dir(version):
            return tmp_path

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 3

    def test_get_next_child_seq_takes_max_of_both_sources(self, monkeypatch, tmp_path):
        """Given: children 有 001.1，檔案系統有 001.1.md 和 001.3.md
        When: 呼叫 get_next_child_seq
        Then: 返回 4（檔案系統的 3 > children 的 1）
        """
        (tmp_path / "0.31.0-W5-001.1.md").touch()
        (tmp_path / "0.31.0-W5-001.3.md").touch()

        def mock_load_ticket(version, ticket_id):
            return {"children": ["0.31.0-W5-001.1"]}

        def mock_get_tickets_dir(version):
            return tmp_path

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 4

    def test_get_next_child_seq_file_scan_ignores_deep_nesting(self, monkeypatch, tmp_path):
        """Given: 檔案系統有 001.1.md 和 001.1.1.md
        When: 呼叫 get_next_child_seq
        Then: 返回 2（忽略孫任務檔案 001.1.1.md）
        """
        (tmp_path / "0.31.0-W5-001.1.md").touch()
        (tmp_path / "0.31.0-W5-001.1.1.md").touch()

        def mock_load_ticket(version, ticket_id):
            return {"children": []}

        def mock_get_tickets_dir(version):
            return tmp_path

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_tickets_dir", mock_get_tickets_dir)
        result = get_next_child_seq("0.31.0-W5-001")
        assert result == 2


class TestGetDefaultAcceptanceCriteria:
    """測試 get_default_acceptance_criteria() 函式"""

    def test_get_default_acceptance_criteria_imp(self):
        """Given: ticket_type = "IMP"
        When: 呼叫 get_default_acceptance_criteria("IMP")
        Then: 返回包含量化佔位符的實作驗收條件
        """
        result = get_default_acceptance_criteria("IMP")
        assert len(result) == 3
        assert "指定功能（{feature_name}）實作符合設計規格" in result
        assert any("相關測試 100% 通過" in item for item in result)
        assert any("0 issues" in item for item in result)

    def test_get_default_acceptance_criteria_ana(self):
        """Given: ticket_type = "ANA"（分析 Ticket）
        When: 呼叫 get_default_acceptance_criteria("ANA")
        Then: 返回包含結構化分析步驟和防護 Ticket 相關項目的驗收條件
        """
        result = get_default_acceptance_criteria("ANA")
        assert len(result) == 6
        # 檢查關鍵詞而不是完全匹配，因為條件包含結構化描述
        assert any("分析報告已撰寫" in item for item in result)
        assert any("根因已通過" in item for item in result)
        assert any("改善方案至少包含" in item for item in result)
        assert any("症狀修復" in item for item in result)
        assert any("機制防護" in item for item in result)
        assert any("spawned_tickets" in item for item in result)

    def test_get_default_acceptance_criteria_unknown_type(self):
        """Given: ticket_type = "UNKNOWN"（未知類型）
        When: 呼叫 get_default_acceptance_criteria("UNKNOWN")
        Then: 返回預設值（IMP 類型的驗收條件）
        """
        result = get_default_acceptance_criteria("UNKNOWN")
        assert result == get_default_acceptance_criteria("IMP")

    def test_get_default_acceptance_criteria_doc(self):
        """Given: ticket_type = "DOC"
        When: 呼叫 get_default_acceptance_criteria("DOC")
        Then: 返回文件類型的量化驗收條件
        """
        result = get_default_acceptance_criteria("DOC")
        assert len(result) == 3
        assert any("文件內容完整" in item for item in result)
        assert any("格式符合規範" in item for item in result)
        assert any("無 TODO" in item for item in result)


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
          - acceptance = 包含量化佔位符的 IMP 型預設條件（帶 [ ] 前綴）
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

        # 驗證是 IMP 預設條件的量化版本，均有 [ ] 前綴
        acceptance = frontmatter["acceptance"]
        assert len(acceptance) == 3
        assert all(item.startswith("[ ]") for item in acceptance)
        assert any("{feature_name}" in item for item in acceptance)
        assert any("100% 通過" in item for item in acceptance)
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

    def test_create_ticket_frontmatter_ana_type(self):
        """Given: TicketConfig ticket_type = "ANA"（分析 Ticket），無自訂驗收條件
        When: 呼叫 create_ticket_frontmatter(config)
        Then: frontmatter["acceptance"] 應包含 ANA 類型的量化驗收條件：
          - 分析報告已撰寫、根因已通過分析、改善方案至少包含兩個方向（基礎驗收）
          - [ ] 分析結論已建立修復 Ticket（症狀修復），Ticket ID 已記錄在 spawned_tickets
          - [ ] 根因已建立防護 Ticket（機制防護），Ticket ID 已記錄在 spawned_tickets
          - [ ] 若無後續 Ticket 需建立，需說明理由
          （所有項目都以 [ ] 前綴開頭）
        """
        config: TicketConfig = {
            "ticket_id": "0.31.0-W5-001",
            "version": "0.31.0",
            "wave": 5,
            "title": "分析效能問題",
            "ticket_type": "ANA",
            "priority": "P1",
            "who": "system-analyst",
            "what": "分析系統效能問題",
            "when": "立即",
            "where_layer": "Infrastructure",
            "where_files": ["server/main.go"],
            "why": "用戶回報系統緩慢",
            "how_task_type": "Analysis",
            "how_strategy": "Profiling"
        }

        frontmatter = create_ticket_frontmatter(config)

        # 驗證 ANA 預設驗收條件的關鍵元素
        acceptance = frontmatter["acceptance"]
        assert len(acceptance) == 6
        assert all(item.startswith("[ ]") for item in acceptance)

        # 驗證關鍵詞而不是完全匹配
        assert any("分析報告已撰寫" in ac for ac in acceptance)
        assert any("根因已通過" in ac for ac in acceptance)
        assert any("改善方案至少包含" in ac for ac in acceptance)
        assert any("症狀修復" in ac for ac in acceptance)
        assert any("機制防護" in ac for ac in acceptance)
        assert any("若無後續 Ticket" in ac for ac in acceptance)

    def test_create_ticket_frontmatter_doc_type(self):
        """Given: TicketConfig ticket_type = "DOC"（文件 Ticket）
        When: 呼叫 create_ticket_frontmatter(config)
        Then: frontmatter["acceptance"] 應為 DOC 類型的預設驗收條件
        """
        config: TicketConfig = {
            "ticket_id": "0.31.0-W5-001",
            "version": "0.31.0",
            "wave": 5,
            "title": "更新 README",
            "ticket_type": "DOC",
            "priority": "P2",
            "who": "pm",
            "what": "更新專案 README",
            "when": "本 Wave 結束",
            "where_layer": "Documentation",
            "where_files": ["README.md"],
            "why": "補充缺失的說明",
            "how_task_type": "Documentation",
            "how_strategy": "直接編寫"
        }

        frontmatter = create_ticket_frontmatter(config)

        # 驗證 DOC 類型的驗收條件
        acceptance = frontmatter["acceptance"]
        assert any("文件內容完整" in ac for ac in acceptance)
        assert any("格式符合規範" in ac for ac in acceptance)


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

    def test_create_ticket_body_ana_includes_reproduction_section(self):
        """Given: ticket_type = "ANA"
        When: 呼叫 create_ticket_body(what, who, "ANA")
        Then: 返回的 body 包含「重現實驗結果」章節及三個子節（PC-063 防護 1）
        """
        body = create_ticket_body("分析問題 Y", "sage-test-architect", "ANA")

        assert "## 重現實驗結果" in body
        assert "### 實驗方法" in body
        assert "### 實驗執行" in body
        assert "### 實驗發現" in body

    def test_create_ticket_body_non_ana_excludes_reproduction_section(self):
        """Given: ticket_type = "IMP"（非 ANA）
        When: 呼叫 create_ticket_body(what, who, "IMP")
        Then: 返回的 body 不含「重現實驗結果」章節
        """
        body = create_ticket_body("實作功能 Z", "parsley-flutter-developer", "IMP")

        assert "## 重現實驗結果" not in body
        assert "### 實驗方法" not in body


class TestCreateTicketBodySchemaMarkers:
    """測試 type-aware body schema 標註（W17-016.2）"""

    def test_ana_body_has_ana_schema_markers(self):
        """ANA body 四章節含 Schema[ANA/...] 標註"""
        body = create_ticket_body("分析 X", "sage-test-architect", "ANA")
        assert "Schema[ANA/Problem Analysis]: 必填" in body
        assert "Schema[ANA/Solution]: 必填" in body
        assert "Schema[ANA/Test Results]: 選填" in body
        assert "Schema[ANA/Completion Info]: 必填" in body

    def test_imp_body_has_imp_schema_markers(self):
        """IMP body Test Results 必填、Problem Analysis 選填"""
        body = create_ticket_body("實作 Y", "thyme-python-developer", "IMP")
        assert "Schema[IMP/Test Results]: 必填" in body
        assert "Schema[IMP/Problem Analysis]: 選填" in body
        assert "Schema[IMP/Completion Info]: 必填" in body

    def test_doc_body_has_doc_schema_markers(self):
        """DOC body Solution/Test Results 免填、Completion Info 必填"""
        body = create_ticket_body("更新文件 Z", "rosemary-project-manager", "DOC")
        assert "Schema[DOC/Solution]: 免填" in body
        assert "Schema[DOC/Test Results]: 免填" in body
        assert "Schema[DOC/Completion Info]: 必填" in body

    def test_unknown_type_has_no_schema_markers(self):
        """未知 type（含空字串）不產出 Schema 標註（向後相容）"""
        body = create_ticket_body("任務", "agent", "")
        assert "Schema[" not in body

    def test_schema_marker_references_pm_rules(self):
        """Schema 標註引用 pm-rules/ticket-body-schema.md 路徑"""
        body = create_ticket_body("分析", "sage-test-architect", "ANA")
        assert ".claude/pm-rules/ticket-body-schema.md" in body


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


class TestUpdateSourceSpawnedTickets:
    """測試 update_source_spawned_tickets() 函式（PC-073）

    鏡像 TestUpdateParentChildren 的測試風格；只 mock 檔案 I/O 邊界
    （load_ticket/save_ticket/get_ticket_path），內層正規化/去重邏輯走真實實作。
    """

    def test_update_source_spawned_new_entry(self, monkeypatch):
        """A1 - Given: source `spawned_tickets: []`
        When: 呼叫 update_source_spawned_tickets(source_id, new_id)
        Then: 返回 True，且 source 的 spawned_tickets 包含 [new_id]
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "spawned_tickets": [],
            "_path": "/tmp/source.md"
        }

        def mock_load_ticket(version, ticket_id):
            return source_ticket

        def mock_save_ticket(ticket, path):
            pass

        def mock_get_ticket_path(version, ticket_id):
            return "/tmp/source.md"

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.save_ticket", mock_save_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_ticket_path", mock_get_ticket_path)

        result = update_source_spawned_tickets("0.18.0-W12-002", "0.18.0-W12-006")

        assert result is True
        assert source_ticket["spawned_tickets"] == ["0.18.0-W12-006"]

    def test_update_source_spawned_append_to_existing(self, monkeypatch):
        """A2 - Given: source 已有 1 個 spawned = ["0.18.0-W12-003"]
        When: append 第二個 spawned = "0.18.0-W12-006"
        Then: 返回 True，spawned_tickets 變為 ["0.18.0-W12-003", "0.18.0-W12-006"]
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "spawned_tickets": ["0.18.0-W12-003"],
            "_path": "/tmp/source.md"
        }

        def mock_load_ticket(version, ticket_id):
            return source_ticket

        def mock_save_ticket(ticket, path):
            pass

        def mock_get_ticket_path(version, ticket_id):
            return "/tmp/source.md"

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.save_ticket", mock_save_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_ticket_path", mock_get_ticket_path)

        result = update_source_spawned_tickets("0.18.0-W12-002", "0.18.0-W12-006")

        assert result is True
        assert source_ticket["spawned_tickets"] == [
            "0.18.0-W12-003",
            "0.18.0-W12-006",
        ]

    def test_update_source_spawned_duplicate_prevention(self, monkeypatch):
        """A3 - Given: source 已有 spawned = ["0.18.0-W12-006"]
        When: 以相同 ID 再呼叫一次 update_source_spawned_tickets
        Then: 返回 True，spawned_tickets 仍為單一項（去重）
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "spawned_tickets": ["0.18.0-W12-006"],
            "_path": "/tmp/source.md"
        }

        def mock_load_ticket(version, ticket_id):
            return source_ticket

        def mock_save_ticket(ticket, path):
            pass

        def mock_get_ticket_path(version, ticket_id):
            return "/tmp/source.md"

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.save_ticket", mock_save_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_ticket_path", mock_get_ticket_path)

        result = update_source_spawned_tickets("0.18.0-W12-002", "0.18.0-W12-006")

        assert result is True
        assert source_ticket["spawned_tickets"] == ["0.18.0-W12-006"]

    def test_update_source_spawned_source_not_found(self, monkeypatch):
        """A4 - Given: source Ticket 不存在（load_ticket 返回 None）
        When: 呼叫 update_source_spawned_tickets
        Then: 返回 False，不拋出異常
        """
        def mock_load_ticket(version, ticket_id):
            return None

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)

        result = update_source_spawned_tickets("0.18.0-W99-999", "0.18.0-W12-006")

        assert result is False

    def test_update_source_spawned_normalizes_string_to_list(self, monkeypatch, capsys):
        """A5 - Given: source 的 spawned_tickets 為字串（手動編輯異常）
        When: 呼叫 update_source_spawned_tickets
        Then: 函式自動正規化為 list 後 append，返回 True，stderr 有 WARNING
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            # 字串型別（模擬手動編輯損壞）
            "spawned_tickets": "0.18.0-W12-003",
            "_path": "/tmp/source.md"
        }

        def mock_load_ticket(version, ticket_id):
            return source_ticket

        def mock_save_ticket(ticket, path):
            pass

        def mock_get_ticket_path(version, ticket_id):
            return "/tmp/source.md"

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.save_ticket", mock_save_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_ticket_path", mock_get_ticket_path)

        result = update_source_spawned_tickets("0.18.0-W12-002", "0.18.0-W12-006")

        assert result is True
        # 字串已正規化為 list，並 append 新 ID
        assert source_ticket["spawned_tickets"] == [
            "0.18.0-W12-003",
            "0.18.0-W12-006",
        ]
        # stderr 有 WARNING 告知自動修正
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "spawned_tickets" in captured.err

    def test_update_source_spawned_save_failure_returns_false(self, monkeypatch):
        """A6 - Given: save_ticket 拋 IOError
        When: 呼叫 update_source_spawned_tickets
        Then: 函式捕獲並返回 False，不向外傳播異常
        """
        source_ticket = {
            "id": "0.18.0-W12-002",
            "spawned_tickets": [],
            "_path": "/tmp/source.md"
        }

        def mock_load_ticket(version, ticket_id):
            return source_ticket

        def mock_save_ticket(ticket, path):
            raise IOError("disk full")

        def mock_get_ticket_path(version, ticket_id):
            return "/tmp/source.md"

        monkeypatch.setattr("ticket_system.lib.ticket_builder.load_ticket", mock_load_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.save_ticket", mock_save_ticket)
        monkeypatch.setattr("ticket_system.lib.ticket_builder.get_ticket_path", mock_get_ticket_path)

        # 不應拋出 IOError
        result = update_source_spawned_tickets("0.18.0-W12-002", "0.18.0-W12-006")

        assert result is False


class TestCreateTicketFrontmatterSource:
    """測試 create_ticket_frontmatter() 對 source_ticket 欄位的處理（PC-073）"""

    def _build_base_config(self) -> TicketConfig:
        """測試用最小 TicketConfig（不含 source_ticket / parent_id）"""
        return {
            "ticket_id": "0.18.0-W12-006",
            "version": "0.18.0",
            "wave": 12,
            "title": "實作功能",
            "ticket_type": "IMP",
            "priority": "P2",
            "who": "thyme-python-developer",
            "what": "實作",
            "when": "Phase 3b",
            "where_layer": "Infrastructure",
            "where_files": [],
            "why": "PC-073 防護",
            "how_task_type": "Implementation",
            "how_strategy": "TDD Phase 3b"
        }

    def test_frontmatter_source_ticket_reads_from_config(self):
        """D1 - Given: TicketConfig 含 source_ticket = "0.18.0-W12-002"
        When: 呼叫 create_ticket_frontmatter(config)
        Then: frontmatter["source_ticket"] == "0.18.0-W12-002"
              （取代原本固定硬編碼 None）
        """
        config = self._build_base_config()
        config["source_ticket"] = "0.18.0-W12-002"

        frontmatter = create_ticket_frontmatter(config)

        assert frontmatter["source_ticket"] == "0.18.0-W12-002"

    def test_frontmatter_source_ticket_default_none_when_absent(self):
        """D2 - Given: TicketConfig 未提供 source_ticket
        When: 呼叫 create_ticket_frontmatter(config)
        Then: frontmatter["source_ticket"] is None（向後相容：既有流程不受影響）
        """
        config = self._build_base_config()
        # 不設 source_ticket

        frontmatter = create_ticket_frontmatter(config)

        assert frontmatter["source_ticket"] is None

    def test_frontmatter_source_ticket_and_parent_id_coexist_in_schema(self):
        """D3 - Given: frontmatter schema 同時包含 parent_id 與 source_ticket 欄位
        When: 呼叫 create_ticket_frontmatter(config)
        Then: 兩個欄位皆存在於輸出 dict；互斥由 CLI 層攔截，frontmatter 層不擋
              （schema-level coexistence 驗證）
        """
        config = self._build_base_config()

        frontmatter = create_ticket_frontmatter(config)

        # schema 兩個欄位都存在（即使值為 None 也代表欄位已定義）
        assert "parent_id" in frontmatter
        assert "source_ticket" in frontmatter
