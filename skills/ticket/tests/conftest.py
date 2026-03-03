"""
Pytest 配置和共用 fixtures

提供測試中使用的固定資料和環境配置。
"""

import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest
import yaml


@pytest.fixture
def temp_project_dir() -> Path:
    """
    建立臨時專案目錄結構

    Returns:
        Path: 臨時專案根目錄
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # 建立目錄結構
        work_logs_dir = project_root / "docs" / "work-logs" / "v0.31.0" / "tickets"
        work_logs_dir.mkdir(parents=True, exist_ok=True)

        claude_tickets_dir = project_root / ".claude" / "tickets"
        claude_tickets_dir.mkdir(parents=True, exist_ok=True)

        # 建立 pubspec.yaml 標記為專案根目錄
        (project_root / "pubspec.yaml").touch()

        yield project_root


@pytest.fixture
def valid_ticket_data() -> Dict[str, Any]:
    """
    有效的 Ticket 資料範例

    Returns:
        Dict: Ticket 資料字典
    """
    return {
        "id": "0.31.0-W4-001",
        "title": "實作 Ticket 載入功能",
        "status": "pending",
        "what": "實作 Ticket 載入模組",
        "priority": "P0",
        "type": "IMP",
        "created": "2026-01-30",
    }


@pytest.fixture
def invalid_ticket_data() -> Dict[str, Any]:
    """
    無效的 Ticket 資料範例（缺少必填欄位）

    Returns:
        Dict: 不完整的 Ticket 資料字典
    """
    return {
        "id": "invalid-id",
        # 缺少 status 和 title
        "priority": "P0",
    }


@pytest.fixture
def valid_ticket_markdown(valid_ticket_data) -> str:
    """
    有效的 Markdown 格式 Ticket

    Returns:
        str: Markdown 內容
    """
    frontmatter_yaml = yaml.dump(
        valid_ticket_data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    body = """# 實作 Ticket 載入功能

## 目標
建立 Ticket 載入和解析模組，支援 Markdown 和 YAML 格式。

## 驗收條件
- [x] 支援 Markdown frontmatter 解析
- [x] 支援 YAML 格式載入
- [ ] 支援 Ticket 儲存
"""
    return f"---\n{frontmatter_yaml}---\n{body}"


@pytest.fixture
def valid_ticket_yaml(valid_ticket_data) -> str:
    """
    有效的 YAML 格式 Ticket

    Returns:
        str: YAML 內容
    """
    data = {"ticket": valid_ticket_data}
    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)


@pytest.fixture
def fixture_dir(temp_project_dir) -> Path:
    """
    建立 fixtures 測試資料目錄

    Returns:
        Path: fixtures 目錄路徑
    """
    fixtures_path = Path(__file__).parent / "fixtures"
    fixtures_path.mkdir(exist_ok=True)
    return fixtures_path


@pytest.fixture
def valid_ticket_fixture_file(fixture_dir, valid_ticket_markdown) -> Path:
    """
    建立有效 Ticket 的測試檔案

    Returns:
        Path: Ticket 檔案路徑
    """
    ticket_path = fixture_dir / "valid_ticket.md"
    ticket_path.write_text(valid_ticket_markdown, encoding="utf-8")
    return ticket_path


@pytest.fixture
def invalid_ticket_fixture_file(fixture_dir) -> Path:
    """
    建立無效 Ticket 的測試檔案

    Returns:
        Path: 無效 Ticket 檔案路徑
    """
    # 無效的 frontmatter（缺少必填欄位）
    invalid_content = """---
id: invalid-format
priority: P0
---

無效的 Ticket 內容
缺少必填欄位 status 和 title
"""
    ticket_path = fixture_dir / "invalid_ticket.md"
    ticket_path.write_text(invalid_content, encoding="utf-8")
    return ticket_path
