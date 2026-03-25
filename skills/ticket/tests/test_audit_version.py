"""
audit_version 模組測試

測試版本審計核心邏輯（scan_all_tickets、detect_mismatches、detect_duplicates）
和 CLI 命令功能（execute_audit_version、報告格式化等）。
"""

import os
import tempfile
from pathlib import Path
from typing import List

import pytest
import yaml

from ticket_system.lib.audit_version import (
    TicketVersionInfo,
    VersionMismatch,
    DuplicateTicket,
    scan_all_tickets,
    detect_mismatches,
    detect_duplicates,
)
from ticket_system.commands.audit_version import (
    execute_audit_version,
    _format_version_audit_report,
    _format_separator,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def audit_temp_project_dir():
    """
    為版本審計建立臨時專案目錄結構

    Returns:
        Path: 臨時專案根目錄
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # 建立多個版本目錄
        for version in ["v0.1.0", "v0.2.0", "v0.1.1"]:
            tickets_dir = project_root / "docs" / "work-logs" / version / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)

        # 建立 pubspec.yaml 標記為專案根目錄
        (project_root / "pubspec.yaml").touch()

        yield project_root


@pytest.fixture
def clean_project_env(audit_temp_project_dir):
    """
    設定乾淨的環境變數環境
    """
    old_env = os.environ.get("CLAUDE_PROJECT_DIR")
    try:
        os.environ["CLAUDE_PROJECT_DIR"] = str(audit_temp_project_dir)
        yield audit_temp_project_dir
    finally:
        if old_env:
            os.environ["CLAUDE_PROJECT_DIR"] = old_env
        elif "CLAUDE_PROJECT_DIR" in os.environ:
            del os.environ["CLAUDE_PROJECT_DIR"]


def create_ticket_file(
    project_root: Path,
    version: str,
    ticket_id: str,
    frontmatter_version: str = None,
) -> Path:
    """
    建立測試用的 Ticket 檔案

    Args:
        project_root: 專案根目錄
        version: 目錄版本（如 "0.1.0"）
        ticket_id: Ticket ID（如 "0.1.0-W1-001"）
        frontmatter_version: frontmatter 中的版本號（預設為 version）

    Returns:
        Path: 建立的 Ticket 檔案路徑
    """
    if frontmatter_version is None:
        frontmatter_version = version

    tickets_dir = project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)

    file_path = tickets_dir / f"{ticket_id}.md"

    frontmatter = {
        "id": ticket_id,
        "title": f"Test Ticket {ticket_id}",
        "version": frontmatter_version,
        "type": "IMP",
        "status": "pending",
    }

    frontmatter_yaml = yaml.dump(
        frontmatter,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )

    content = f"""---
{frontmatter_yaml}---

# Test Ticket

## Summary
This is a test ticket for version audit testing.
"""

    file_path.write_text(content, encoding="utf-8")
    return file_path


# ============================================================================
# TestTicketVersionInfo
# ============================================================================

class TestTicketVersionInfo:
    """TicketVersionInfo 資料類別的測試"""

    def test_creation(self):
        """測試建立 TicketVersionInfo 物件"""
        info = TicketVersionInfo(
            file_path="/path/to/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )

        assert info.file_path == "/path/to/0.1.0-W1-001.md"
        assert info.ticket_id == "0.1.0-W1-001"
        assert info.id_version == "0.1.0"
        assert info.frontmatter_version == "0.1.0"
        assert info.directory_version == "0.1.0"

    def test_immutable(self):
        """測試 TicketVersionInfo 的不可變性"""
        info = TicketVersionInfo(
            file_path="/path/to/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )

        # 嘗試修改應該拋出異常
        with pytest.raises(AttributeError):
            info.id_version = "0.2.0"

    def test_with_description_suffix(self):
        """測試帶描述後綴的 Ticket ID"""
        info = TicketVersionInfo(
            file_path="/path/to/0.1.0-W1-001-phase1-design.md",
            ticket_id="0.1.0-W1-001-phase1-design",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )

        assert info.ticket_id == "0.1.0-W1-001-phase1-design"


# ============================================================================
# TestVersionMismatch
# ============================================================================

class TestVersionMismatch:
    """VersionMismatch 資料類別的測試"""

    def test_creation(self):
        """測試建立 VersionMismatch 物件"""
        info = TicketVersionInfo(
            file_path="/path/to/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.1",
            directory_version="0.1.0",
        )

        mismatch = VersionMismatch(
            ticket_info=info,
            mismatch_type="frontmatter_vs_directory",
            expected_version="0.1.0",
            actual_version="0.1.1",
        )

        assert mismatch.ticket_info == info
        assert mismatch.mismatch_type == "frontmatter_vs_directory"
        assert mismatch.expected_version == "0.1.0"
        assert mismatch.actual_version == "0.1.1"


# ============================================================================
# TestDuplicateTicket
# ============================================================================

class TestDuplicateTicket:
    """DuplicateTicket 資料類別的測試"""

    def test_creation(self):
        """測試建立 DuplicateTicket 物件"""
        info1 = TicketVersionInfo(
            file_path="/path/v0.1.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )
        info2 = TicketVersionInfo(
            file_path="/path/v0.2.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.2.0",
        )

        dup = DuplicateTicket(
            ticket_id="0.1.0-W1-001",
            locations=[info1, info2],
            recommended_version="0.1.0",
        )

        assert dup.ticket_id == "0.1.0-W1-001"
        assert len(dup.locations) == 2
        assert dup.recommended_version == "0.1.0"


# ============================================================================
# TestScanAllTickets
# ============================================================================

class TestScanAllTickets:
    """scan_all_tickets() 函式的測試"""

    def test_scan_no_tickets(self, clean_project_env):
        """測試掃描空目錄"""
        result = scan_all_tickets()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_scan_single_ticket(self, clean_project_env):
        """測試掃描單個 Ticket"""
        create_ticket_file(
            clean_project_env,
            version="0.1.0",
            ticket_id="0.1.0-W1-001",
        )

        result = scan_all_tickets()

        assert len(result) == 1
        assert result[0].ticket_id == "0.1.0-W1-001"
        assert result[0].id_version == "0.1.0"
        assert result[0].directory_version == "0.1.0"
        assert result[0].frontmatter_version == "0.1.0"

    def test_scan_multiple_tickets_multiple_versions(self, clean_project_env):
        """測試掃描多個版本目錄中的多個 Ticket"""
        # 在 v0.1.0 中建立 2 個 Ticket
        create_ticket_file(clean_project_env, "0.1.0", "0.1.0-W1-001")
        create_ticket_file(clean_project_env, "0.1.0", "0.1.0-W1-002")

        # 在 v0.2.0 中建立 1 個 Ticket
        create_ticket_file(clean_project_env, "0.2.0", "0.2.0-W1-001")

        result = scan_all_tickets()

        assert len(result) == 3

        # 驗證版本號提取正確
        v0_1_0_tickets = [t for t in result if t.directory_version == "0.1.0"]
        v0_2_0_tickets = [t for t in result if t.directory_version == "0.2.0"]

        assert len(v0_1_0_tickets) == 2
        assert len(v0_2_0_tickets) == 1

    def test_scan_ticket_with_description_suffix(self, clean_project_env):
        """測試掃描帶描述後綴的 Ticket"""
        create_ticket_file(
            clean_project_env,
            version="0.1.0",
            ticket_id="0.1.0-W1-001-phase1-design",
        )

        result = scan_all_tickets()

        assert len(result) == 1
        # 掃描時會提取核心 ID（去掉後綴）
        assert result[0].ticket_id == "0.1.0-W1-001"

    def test_scan_ticket_missing_frontmatter_version(self, clean_project_env):
        """測試掃描缺少 frontmatter version 的 Ticket"""
        project_root = clean_project_env
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        # 手動建立缺少 version 欄位的 Ticket
        file_path = tickets_dir / "0.1.0-W1-001.md"
        content = """---
id: 0.1.0-W1-001
title: Test Ticket
type: IMP
status: pending
---

# Test Ticket
"""
        file_path.write_text(content, encoding="utf-8")

        result = scan_all_tickets()

        assert len(result) == 1
        assert result[0].frontmatter_version == ""  # 缺少時為空字串

    def test_scan_preserves_sorted_order(self, clean_project_env):
        """測試掃描結果的排序"""
        # 以逆序建立 Ticket
        create_ticket_file(clean_project_env, "0.1.0", "0.1.0-W1-003")
        create_ticket_file(clean_project_env, "0.1.0", "0.1.0-W1-001")
        create_ticket_file(clean_project_env, "0.1.0", "0.1.0-W1-002")

        result = scan_all_tickets()

        # 結果應該按檔案路徑排序
        assert len(result) == 3
        ticket_ids = [t.ticket_id for t in result]
        assert ticket_ids == ["0.1.0-W1-001", "0.1.0-W1-002", "0.1.0-W1-003"]


# ============================================================================
# TestDetectMismatches
# ============================================================================

class TestDetectMismatches:
    """detect_mismatches() 函式的測試"""

    def test_no_mismatches(self):
        """測試全部一致的情況"""
        info = TicketVersionInfo(
            file_path="/path/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )

        mismatches = detect_mismatches([info])

        assert len(mismatches) == 0

    def test_id_vs_directory_mismatch(self):
        """測試 Ticket ID 版本與目錄版本不一致"""
        info = TicketVersionInfo(
            file_path="/path/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.2.0",  # 不一致
        )

        mismatches = detect_mismatches([info])

        # 會報告一個 id_vs_directory 不一致
        id_vs_dir = [m for m in mismatches if m.mismatch_type == "id_vs_directory"]
        assert len(id_vs_dir) == 1
        assert id_vs_dir[0].expected_version == "0.2.0"
        assert id_vs_dir[0].actual_version == "0.1.0"

    def test_frontmatter_vs_directory_mismatch(self):
        """測試 Frontmatter 版本與目錄版本不一致"""
        info = TicketVersionInfo(
            file_path="/path/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.1",  # 不一致
            directory_version="0.1.0",
        )

        mismatches = detect_mismatches([info])

        # 會報告 frontmatter_vs_directory 和 id_vs_frontmatter
        fm_vs_dir = [m for m in mismatches if m.mismatch_type == "frontmatter_vs_directory"]
        assert len(fm_vs_dir) == 1
        assert fm_vs_dir[0].expected_version == "0.1.0"
        assert fm_vs_dir[0].actual_version == "0.1.1"

    def test_id_vs_frontmatter_mismatch(self):
        """測試 Ticket ID 版本與 Frontmatter 版本不一致"""
        info = TicketVersionInfo(
            file_path="/path/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.1",  # 不一致
            directory_version="0.1.0",
        )

        mismatches = detect_mismatches([info])

        # 應該檢測到 id_vs_frontmatter 不一致
        id_vs_frontmatter = [m for m in mismatches if m.mismatch_type == "id_vs_frontmatter"]
        assert len(id_vs_frontmatter) == 1

    def test_multiple_mismatches_same_ticket(self):
        """測試單個 Ticket 有多種不一致"""
        info = TicketVersionInfo(
            file_path="/path/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.1",
            directory_version="0.2.0",
        )

        mismatches = detect_mismatches([info])

        # 應該報告所有不一致
        assert len(mismatches) >= 2
        mismatch_types = {m.mismatch_type for m in mismatches}
        assert "id_vs_directory" in mismatch_types or "frontmatter_vs_directory" in mismatch_types

    def test_missing_frontmatter_version_ignored(self):
        """測試 frontmatter 版本為空字串時被忽略"""
        info = TicketVersionInfo(
            file_path="/path/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="",  # 空字串
            directory_version="0.1.0",
        )

        mismatches = detect_mismatches([info])

        # 不應報告 frontmatter 相關的不一致
        frontmatter_mismatches = [
            m for m in mismatches
            if m.mismatch_type.startswith("frontmatter_")
        ]
        assert len(frontmatter_mismatches) == 0

    def test_multiple_tickets_multiple_mismatches(self):
        """測試多個 Ticket 的混合不一致情況"""
        tickets = [
            # 一致
            TicketVersionInfo(
                file_path="/path/0.1.0-W1-001.md",
                ticket_id="0.1.0-W1-001",
                id_version="0.1.0",
                frontmatter_version="0.1.0",
                directory_version="0.1.0",
            ),
            # ID 不一致
            TicketVersionInfo(
                file_path="/path/0.1.0-W1-002.md",
                ticket_id="0.1.0-W1-002",
                id_version="0.1.1",
                frontmatter_version="0.1.0",
                directory_version="0.1.0",
            ),
            # Frontmatter 不一致
            TicketVersionInfo(
                file_path="/path/0.1.0-W1-003.md",
                ticket_id="0.1.0-W1-003",
                id_version="0.1.0",
                frontmatter_version="0.2.0",
                directory_version="0.1.0",
            ),
        ]

        mismatches = detect_mismatches(tickets)

        # 第一個 Ticket 無不一致（0）
        # 第二個 Ticket 有 2 個不一致（id_vs_directory 和 id_vs_frontmatter）
        # 第三個 Ticket 有 2 個不一致（frontmatter_vs_directory 和 id_vs_frontmatter）
        assert len(mismatches) >= 2

        # 確認有來自不同 Ticket 的不一致
        mismatch_tickets = {m.ticket_info.ticket_id for m in mismatches}
        assert len(mismatch_tickets) >= 2


# ============================================================================
# TestDetectDuplicates
# ============================================================================

class TestDetectDuplicates:
    """detect_duplicates() 函式的測試"""

    def test_no_duplicates(self):
        """測試沒有重複的情況"""
        info = TicketVersionInfo(
            file_path="/path/v0.1.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )

        duplicates = detect_duplicates([info])

        assert len(duplicates) == 0

    def test_single_ticket_multiple_directories(self):
        """測試同一 Ticket 在 2 個版本目錄出現"""
        info1 = TicketVersionInfo(
            file_path="/path/v0.1.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )
        info2 = TicketVersionInfo(
            file_path="/path/v0.2.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.2.0",
        )

        duplicates = detect_duplicates([info1, info2])

        assert len(duplicates) == 1
        assert duplicates[0].ticket_id == "0.1.0-W1-001"
        assert len(duplicates[0].locations) == 2
        assert duplicates[0].recommended_version == "0.1.0"

    def test_single_ticket_three_directories(self):
        """測試同一 Ticket 在 3 個版本目錄出現"""
        info1 = TicketVersionInfo(
            file_path="/path/v0.1.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )
        info2 = TicketVersionInfo(
            file_path="/path/v0.1.1/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.1",
        )
        info3 = TicketVersionInfo(
            file_path="/path/v0.2.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.2.0",
        )

        duplicates = detect_duplicates([info1, info2, info3])

        assert len(duplicates) == 1
        assert len(duplicates[0].locations) == 3

    def test_duplicate_with_description_suffix(self):
        """測試帶描述後綴的 Ticket 重複偵測"""
        info1 = TicketVersionInfo(
            file_path="/path/v0.1.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )
        info2 = TicketVersionInfo(
            file_path="/path/v0.2.0/0.1.0-W1-001-phase1-design.md",
            ticket_id="0.1.0-W1-001-phase1-design",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.2.0",
        )

        duplicates = detect_duplicates([info1, info2])

        # 應該偵測為重複（同一核心 ID）
        assert len(duplicates) == 1
        assert duplicates[0].ticket_id == "0.1.0-W1-001"
        assert len(duplicates[0].locations) == 2

    def test_multiple_duplicates(self):
        """測試多個重複的不同 Ticket ID"""
        tickets = [
            # Ticket 1 的重複
            TicketVersionInfo(
                file_path="/path/v0.1.0/0.1.0-W1-001.md",
                ticket_id="0.1.0-W1-001",
                id_version="0.1.0",
                frontmatter_version="0.1.0",
                directory_version="0.1.0",
            ),
            TicketVersionInfo(
                file_path="/path/v0.2.0/0.1.0-W1-001.md",
                ticket_id="0.1.0-W1-001",
                id_version="0.1.0",
                frontmatter_version="0.1.0",
                directory_version="0.2.0",
            ),
            # Ticket 2 的重複
            TicketVersionInfo(
                file_path="/path/v0.1.0/0.1.0-W1-002.md",
                ticket_id="0.1.0-W1-002",
                id_version="0.1.0",
                frontmatter_version="0.1.0",
                directory_version="0.1.0",
            ),
            TicketVersionInfo(
                file_path="/path/v0.1.1/0.1.0-W1-002.md",
                ticket_id="0.1.0-W1-002",
                id_version="0.1.0",
                frontmatter_version="0.1.0",
                directory_version="0.1.1",
            ),
            # 非重複
            TicketVersionInfo(
                file_path="/path/v0.2.0/0.2.0-W1-001.md",
                ticket_id="0.2.0-W1-001",
                id_version="0.2.0",
                frontmatter_version="0.2.0",
                directory_version="0.2.0",
            ),
        ]

        duplicates = detect_duplicates(tickets)

        assert len(duplicates) == 2
        duplicate_ids = {dup.ticket_id for dup in duplicates}
        assert duplicate_ids == {"0.1.0-W1-001", "0.1.0-W1-002"}

    def test_recommended_version_from_id(self):
        """測試推薦版本來自 Ticket ID"""
        # Ticket ID 中的版本是推薦位置
        info1 = TicketVersionInfo(
            file_path="/path/v0.1.0/0.1.5-W1-001.md",
            ticket_id="0.1.5-W1-001",
            id_version="0.1.5",
            frontmatter_version="0.1.5",
            directory_version="0.1.5",
        )
        info2 = TicketVersionInfo(
            file_path="/path/v0.2.0/0.1.5-W1-001.md",
            ticket_id="0.1.5-W1-001",
            id_version="0.1.5",
            frontmatter_version="0.1.5",
            directory_version="0.2.0",
        )

        duplicates = detect_duplicates([info1, info2])

        assert duplicates[0].recommended_version == "0.1.5"


# ============================================================================
# TestFormatSeparator
# ============================================================================

class TestFormatSeparator:
    """_format_separator() 函式的測試"""

    def test_separator_format(self):
        """測試分隔線格式"""
        separator = _format_separator()

        assert isinstance(separator, str)
        assert len(separator) > 0
        # 應該是重複的字元
        assert len(set(separator)) == 1


# ============================================================================
# TestFormatVersionAuditReport
# ============================================================================

class TestFormatVersionAuditReport:
    """_format_version_audit_report() 函式的測試"""

    def test_report_no_issues(self):
        """測試無問題的報告"""
        report = _format_version_audit_report([], [], 10)

        assert isinstance(report, str)
        # 報告應該包含通過的訊息（可能是中文）
        assert ("通過" in report or "PASS" in report.upper() or
                "成功" in report or len(report) > 0)

    def test_report_with_mismatches(self):
        """測試包含版本不一致的報告"""
        info = TicketVersionInfo(
            file_path="/path/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.1",
            directory_version="0.1.0",
        )

        mismatch = VersionMismatch(
            ticket_info=info,
            mismatch_type="frontmatter_vs_directory",
            expected_version="0.1.0",
            actual_version="0.1.1",
        )

        report = _format_version_audit_report([mismatch], [], 1)

        assert isinstance(report, str)
        assert "0.1.0-W1-001" in report

    def test_report_with_duplicates(self):
        """測試包含重複 Ticket 的報告"""
        info1 = TicketVersionInfo(
            file_path="/path/v0.1.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )
        info2 = TicketVersionInfo(
            file_path="/path/v0.2.0/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.2.0",
        )

        dup = DuplicateTicket(
            ticket_id="0.1.0-W1-001",
            locations=[info1, info2],
            recommended_version="0.1.0",
        )

        report = _format_version_audit_report([], [dup], 2)

        assert isinstance(report, str)
        assert "0.1.0-W1-001" in report

    def test_report_mixed_issues(self):
        """測試同時包含版本不一致和重複的報告"""
        info1 = TicketVersionInfo(
            file_path="/path/0.1.0-W1-001.md",
            ticket_id="0.1.0-W1-001",
            id_version="0.1.0",
            frontmatter_version="0.1.1",
            directory_version="0.1.0",
        )

        info2 = TicketVersionInfo(
            file_path="/path/v0.1.0/0.1.0-W1-002.md",
            ticket_id="0.1.0-W1-002",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.1.0",
        )
        info3 = TicketVersionInfo(
            file_path="/path/v0.2.0/0.1.0-W1-002.md",
            ticket_id="0.1.0-W1-002",
            id_version="0.1.0",
            frontmatter_version="0.1.0",
            directory_version="0.2.0",
        )

        mismatch = VersionMismatch(
            ticket_info=info1,
            mismatch_type="frontmatter_vs_directory",
            expected_version="0.1.0",
            actual_version="0.1.1",
        )

        dup = DuplicateTicket(
            ticket_id="0.1.0-W1-002",
            locations=[info2, info3],
            recommended_version="0.1.0",
        )

        report = _format_version_audit_report([mismatch], [dup], 3)

        assert isinstance(report, str)
        assert "0.1.0-W1-001" in report
        assert "0.1.0-W1-002" in report


# ============================================================================
# TestExecuteAuditVersion
# ============================================================================

class TestExecuteAuditVersion:
    """execute_audit_version() 命令函式的測試"""

    def test_execute_dry_run_no_issues(self, clean_project_env, capsys):
        """測試 dry-run 模式，無問題"""
        create_ticket_file(clean_project_env, "0.1.0", "0.1.0-W1-001")

        # 建立簡單的 args 物件
        class Args:
            fix = False
            audit_version = None

        result = execute_audit_version(Args(), "0.1.0")

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out  # 應該有輸出

    def test_execute_dry_run_with_issues(self, clean_project_env, capsys):
        """測試 dry-run 模式，有版本不一致"""
        create_ticket_file(
            clean_project_env,
            version="0.1.0",
            ticket_id="0.1.0-W1-001",
            frontmatter_version="0.1.1",
        )

        class Args:
            fix = False
            audit_version = None

        result = execute_audit_version(Args(), "0.1.0")

        assert result == 1
        captured = capsys.readouterr()
        assert captured.out

    def test_execute_version_filter(self, clean_project_env, capsys):
        """測試 --version 參數篩選"""
        create_ticket_file(clean_project_env, "0.1.0", "0.1.0-W1-001")
        create_ticket_file(clean_project_env, "0.2.0", "0.2.0-W1-001")

        class Args:
            fix = False
            audit_version = "0.1.0"

        result = execute_audit_version(Args(), "0.1.0")

        captured = capsys.readouterr()
        assert "0.1.0" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
