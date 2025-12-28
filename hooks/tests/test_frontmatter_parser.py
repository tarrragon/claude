#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pytest>=7.0",
#     "pyyaml>=6.0",
# ]
# ///

"""
frontmatter_parser.py 單元測試

測試核心功能：
- parse_frontmatter(): 解析 YAML frontmatter
- read_ticket(): 讀取和解析 Ticket 檔案
- update_frontmatter(): 更新 frontmatter 欄位
- list_tickets(): 列出目錄中所有 tickets
- detect_format(): 偵測版本格式
"""

import sys
import pytest
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import tempfile
import shutil

# 導入要測試的模組
sys.path.insert(0, str(Path(__file__).parent.parent))
from frontmatter_parser import (
    parse_frontmatter,
    read_ticket,
    update_frontmatter,
    list_tickets,
    detect_format,
    extract_body,
    TicketData
)


# ============================================================================
# 測試用的 Fixtures
# ============================================================================

@pytest.fixture
def sample_ticket_content() -> str:
    """標準的 Ticket 檔案內容"""
    return """---
ticket_id: "0.16.0-W1-001"
version: "0.16.0"
wave: 1
action: "Implement"
target: "frontmatter_parser.py 解析模組"
agent: "basil-hook-architect"
who: "basil-hook-architect"
what: "Implement frontmatter_parser.py 解析模組"
when: "Wave 1 開始"
where: ".claude/hooks/frontmatter_parser.py"
why: "提供 YAML frontmatter 解析功能"
how: "使用 PyYAML 解析"
acceptance:
  - "parse_frontmatter() 可正確解析"
  - "read_ticket() 可讀取檔案"
files:
  - ".claude/hooks/frontmatter_parser.py"
dependencies: []
status: "pending"
assigned: false
started_at: null
completed_at: null
---

# 執行日誌

## 任務摘要

建立 YAML frontmatter 解析模組。

---

## 問題分析

<!-- 待執行代理人填寫 -->
"""


@pytest.fixture
def temp_tickets_dir():
    """暫時的 Tickets 目錄"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


# ============================================================================
# parse_frontmatter() 測試
# ============================================================================

class TestParseFrontmatter:
    """測試 parse_frontmatter() 函式"""

    def test_parse_valid_frontmatter(self, sample_ticket_content: str):
        """測試解析有效的 frontmatter"""
        frontmatter = parse_frontmatter(sample_ticket_content)

        assert frontmatter['ticket_id'] == "0.16.0-W1-001"
        assert frontmatter['version'] == "0.16.0"
        assert frontmatter['wave'] == 1
        assert frontmatter['action'] == "Implement"
        assert frontmatter['status'] == "pending"

    def test_parse_with_list_values(self, sample_ticket_content: str):
        """測試包含列表的 frontmatter"""
        frontmatter = parse_frontmatter(sample_ticket_content)

        assert isinstance(frontmatter['acceptance'], list)
        assert len(frontmatter['acceptance']) == 2
        assert "parse_frontmatter() 可正確解析" in frontmatter['acceptance']

        assert isinstance(frontmatter['files'], list)
        assert len(frontmatter['files']) == 1
        assert frontmatter['dependencies'] == []

    def test_parse_missing_separator(self):
        """測試缺少 --- 分隔符的情況"""
        content = "ticket_id: test\nno frontmatter"
        with pytest.raises(ValueError, match="找不到有效的 frontmatter 格式"):
            parse_frontmatter(content)

    def test_parse_invalid_yaml(self):
        """測試無效的 YAML 語法"""
        content = """---
invalid: yaml: syntax: here
---

body"""
        with pytest.raises(ValueError, match="YAML 解析失敗"):
            parse_frontmatter(content)

    def test_parse_empty_frontmatter(self):
        """測試空的 frontmatter"""
        content = """---
---

body"""
        frontmatter = parse_frontmatter(content)
        assert frontmatter == {} or frontmatter is None


# ============================================================================
# extract_body() 測試
# ============================================================================

class TestExtractBody:
    """測試 extract_body() 函式"""

    def test_extract_body(self, sample_ticket_content: str):
        """測試提取 body 內容"""
        body = extract_body(sample_ticket_content)
        assert "# 執行日誌" in body
        assert "建立 YAML frontmatter 解析模組" in body
        assert "ticket_id" not in body

    def test_extract_body_no_frontmatter(self):
        """測試沒有 frontmatter 的內容"""
        content = "just body content\nno frontmatter"
        body = extract_body(content)
        assert body == content


# ============================================================================
# read_ticket() 測試
# ============================================================================

class TestReadTicket:
    """測試 read_ticket() 函式"""

    def test_read_valid_ticket(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試讀取有效的 Ticket 檔案"""
        ticket_file = temp_tickets_dir / "0.16.0-W1-001.md"
        ticket_file.write_text(sample_ticket_content, encoding='utf-8')

        ticket = read_ticket(ticket_file)

        assert isinstance(ticket, TicketData)
        assert ticket.ticket_id == "0.16.0-W1-001"
        assert ticket.version == "0.16.0"
        assert ticket.wave == 1
        assert ticket.action == "Implement"
        assert ticket.agent == "basil-hook-architect"
        assert ticket.status == "pending"
        assert ticket.assigned is False
        assert len(ticket.acceptance) == 2

    def test_read_ticket_missing_file(self):
        """測試讀取不存在的檔案"""
        with pytest.raises(FileNotFoundError):
            read_ticket(Path("/nonexistent/ticket.md"))

    def test_read_ticket_missing_required_field(self, temp_tickets_dir: Path):
        """測試缺少必需欄位的 Ticket"""
        content = """---
ticket_id: "0.16.0-W1-001"
version: "0.16.0"
wave: 1
---

body"""
        ticket_file = temp_tickets_dir / "invalid.md"
        ticket_file.write_text(content, encoding='utf-8')

        with pytest.raises(ValueError, match="缺少必需欄位"):
            read_ticket(ticket_file)

    def test_read_ticket_preserves_body(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試讀取時保留 body 內容"""
        ticket_file = temp_tickets_dir / "0.16.0-W1-001.md"
        ticket_file.write_text(sample_ticket_content, encoding='utf-8')

        ticket = read_ticket(ticket_file)

        assert "# 執行日誌" in ticket.body
        assert "建立 YAML frontmatter 解析模組" in ticket.body


# ============================================================================
# update_frontmatter() 測試
# ============================================================================

class TestUpdateFrontmatter:
    """測試 update_frontmatter() 函式"""

    def test_update_simple_field(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試更新簡單欄位"""
        ticket_file = temp_tickets_dir / "0.16.0-W1-001.md"
        ticket_file.write_text(sample_ticket_content, encoding='utf-8')

        # 更新狀態
        success = update_frontmatter(ticket_file, {"status": "in_progress"})

        assert success is True

        # 驗證更新
        updated_ticket = read_ticket(ticket_file)
        assert updated_ticket.status == "in_progress"

    def test_update_preserves_body(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試更新時保留 body 內容"""
        ticket_file = temp_tickets_dir / "0.16.0-W1-001.md"
        ticket_file.write_text(sample_ticket_content, encoding='utf-8')

        original_body = extract_body(sample_ticket_content)

        # 更新多個欄位
        update_frontmatter(ticket_file, {
            "status": "in_progress",
            "assigned": True,
            "started_at": datetime.now().isoformat()
        })

        # 驗證 body 保留
        updated_content = ticket_file.read_text(encoding='utf-8')
        updated_body = extract_body(updated_content)
        assert original_body == updated_body

    def test_update_multiple_fields(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試更新多個欄位"""
        ticket_file = temp_tickets_dir / "0.16.0-W1-001.md"
        ticket_file.write_text(sample_ticket_content, encoding='utf-8')

        now = datetime.now()
        updates = {
            "status": "completed",
            "assigned": True,
            "started_at": now,
            "completed_at": now
        }

        update_frontmatter(ticket_file, updates)

        # 驗證所有欄位都被更新
        updated_ticket = read_ticket(ticket_file)
        assert updated_ticket.status == "completed"
        assert updated_ticket.assigned is True
        assert updated_ticket.started_at is not None
        assert updated_ticket.completed_at is not None

    def test_update_nonexistent_file(self, temp_tickets_dir: Path):
        """測試更新不存在的檔案"""
        nonexistent = temp_tickets_dir / "nonexistent.md"
        with pytest.raises(FileNotFoundError):
            update_frontmatter(nonexistent, {"status": "completed"})


# ============================================================================
# list_tickets() 測試
# ============================================================================

class TestListTickets:
    """測試 list_tickets() 函式"""

    def test_list_empty_directory(self, temp_tickets_dir: Path):
        """測試列出空目錄"""
        tickets = list_tickets(temp_tickets_dir)
        assert tickets == []

    def test_list_multiple_tickets(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試列出多個 Tickets"""
        # 建立 3 個 Ticket
        for i in range(1, 4):
            content = sample_ticket_content.replace("0.16.0-W1-001", f"0.16.0-W1-{i:03d}")
            ticket_file = temp_tickets_dir / f"0.16.0-W1-{i:03d}.md"
            ticket_file.write_text(content, encoding='utf-8')

        tickets = list_tickets(temp_tickets_dir)

        assert len(tickets) == 3
        assert tickets[0].ticket_id == "0.16.0-W1-001"
        assert tickets[1].ticket_id == "0.16.0-W1-002"
        assert tickets[2].ticket_id == "0.16.0-W1-003"

    def test_list_sorted_by_name(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試列表按名稱排序"""
        # 以亂序建立檔案
        for i in [3, 1, 2]:
            content = sample_ticket_content.replace("0.16.0-W1-001", f"0.16.0-W1-{i:03d}")
            ticket_file = temp_tickets_dir / f"0.16.0-W1-{i:03d}.md"
            ticket_file.write_text(content, encoding='utf-8')

        tickets = list_tickets(temp_tickets_dir)

        # 驗證順序
        ticket_ids = [t.ticket_id for t in tickets]
        assert ticket_ids == sorted(ticket_ids)

    def test_list_skips_invalid_tickets(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試列出時跳過無效的 Tickets"""
        # 建立有效的 Ticket
        valid_file = temp_tickets_dir / "0.16.0-W1-001.md"
        valid_file.write_text(sample_ticket_content, encoding='utf-8')

        # 建立無效的 Ticket（缺少必需欄位）
        invalid_file = temp_tickets_dir / "0.16.0-W1-002.md"
        invalid_file.write_text("---\nticket_id: invalid\n---\nbody", encoding='utf-8')

        # 應該只列出有效的 Ticket
        tickets = list_tickets(temp_tickets_dir)
        assert len(tickets) == 1
        assert tickets[0].ticket_id == "0.16.0-W1-001"

    def test_list_nonexistent_directory(self):
        """測試列出不存在的目錄"""
        with pytest.raises(FileNotFoundError):
            list_tickets(Path("/nonexistent/directory"))


# ============================================================================
# detect_format() 測試
# ============================================================================

class TestDetectFormat:
    """測試 detect_format() 函式"""

    def test_detect_markdown_format(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試偵測 Markdown 格式"""
        # 建立 tickets 子目錄
        tickets_dir = temp_tickets_dir / "tickets"
        tickets_dir.mkdir()

        # 建立 Markdown Ticket
        ticket_file = tickets_dir / "0.16.0-W1-001.md"
        ticket_file.write_text(sample_ticket_content, encoding='utf-8')

        fmt = detect_format(temp_tickets_dir)
        assert fmt == "markdown"

    def test_detect_csv_format(self, temp_tickets_dir: Path):
        """測試偵測 CSV 格式"""
        # 建立 CSV 檔案
        csv_file = temp_tickets_dir / "tickets.csv"
        csv_file.write_text("id,status\n0.16.0-W1-001,pending", encoding='utf-8')

        fmt = detect_format(temp_tickets_dir)
        assert fmt == "csv"

    def test_detect_unknown_format(self, temp_tickets_dir: Path):
        """測試偵測未知格式"""
        fmt = detect_format(temp_tickets_dir)
        assert fmt == "unknown"

    def test_detect_markdown_takes_priority(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試 Markdown 格式優先於 CSV"""
        # 同時建立 Markdown 和 CSV
        tickets_dir = temp_tickets_dir / "tickets"
        tickets_dir.mkdir()

        ticket_file = tickets_dir / "0.16.0-W1-001.md"
        ticket_file.write_text(sample_ticket_content, encoding='utf-8')

        csv_file = temp_tickets_dir / "tickets.csv"
        csv_file.write_text("id,status", encoding='utf-8')

        fmt = detect_format(temp_tickets_dir)
        assert fmt == "markdown"


# ============================================================================
# 整合測試
# ============================================================================

class TestIntegration:
    """整合測試"""

    def test_full_ticket_lifecycle(self, sample_ticket_content: str, temp_tickets_dir: Path):
        """測試完整的 Ticket 生命週期"""
        ticket_file = temp_tickets_dir / "0.16.0-W1-001.md"
        ticket_file.write_text(sample_ticket_content, encoding='utf-8')

        # Step 1: 列出 Tickets
        tickets = list_tickets(temp_tickets_dir)
        assert len(tickets) == 1

        # Step 2: 讀取 Ticket
        ticket = read_ticket(ticket_file)
        assert ticket.status == "pending"

        # Step 3: 更新狀態
        now = datetime.now()
        update_frontmatter(ticket_file, {
            "status": "in_progress",
            "assigned": True,
            "started_at": now
        })

        # Step 4: 驗證更新
        updated_ticket = read_ticket(ticket_file)
        assert updated_ticket.status == "in_progress"
        assert updated_ticket.assigned is True

        # Step 5: 完成 Ticket
        update_frontmatter(ticket_file, {
            "status": "completed",
            "completed_at": now
        })

        # Step 6: 最終驗證
        final_ticket = read_ticket(ticket_file)
        assert final_ticket.status == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
