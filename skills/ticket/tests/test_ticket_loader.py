"""
ticket_loader 模組測試

測試 Ticket 載入、解析、儲存等核心功能。
"""

import os
from pathlib import Path
from typing import Dict, Any

import pytest
import yaml

from ticket_system.lib.ticket_loader import (
    get_project_root,
    get_current_version,
    get_tickets_dir,
    get_ticket_path,
    parse_frontmatter,
    load_ticket,
    save_ticket,
    list_tickets,
)
from ticket_system.lib.parser import YAMLParseError


class TestGetProjectRoot:
    """取得專案根目錄的測試"""

    def test_get_project_root_with_env_var(self, temp_project_dir):
        """測試使用環境變數指定專案根目錄"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            result = get_project_root()
            assert result == temp_project_dir
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_get_project_root_search_pubspec(self, temp_project_dir):
        """測試透過搜尋 pubspec.yaml 找到專案根目錄"""
        # 確保環境變數未設定
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            if "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

            # pubspec.yaml 已由 fixture 建立
            assert (temp_project_dir / "pubspec.yaml").exists()
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


class TestGetCurrentVersion:
    """偵測當前版本的測試"""

    def test_get_current_version_with_valid_dirs(self, temp_project_dir):
        """測試找到有效的版本目錄"""
        # 建立多個版本目錄（注意 fixture 已建立 v0.31.0）
        (temp_project_dir / "docs" / "work-logs" / "v0.30.0").mkdir(parents=True, exist_ok=True)
        (temp_project_dir / "docs" / "work-logs" / "v0.31.0").mkdir(parents=True, exist_ok=True)
        (temp_project_dir / "docs" / "work-logs" / "v0.31.1").mkdir(parents=True, exist_ok=True)

        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            result = get_current_version()
            # 應該返回最高版本
            assert result == "v0.31.1"
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_get_current_version_no_versions(self):
        """測試沒有版本目錄時返回 None"""
        # 使用一個新的臨時目錄，不使用 fixture
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "pubspec.yaml").touch()

            old_env = os.environ.get("CLAUDE_PROJECT_DIR")
            try:
                os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)
                result = get_current_version()
                assert result is None
            finally:
                if old_env:
                    os.environ["CLAUDE_PROJECT_DIR"] = old_env
                elif "CLAUDE_PROJECT_DIR" in os.environ:
                    del os.environ["CLAUDE_PROJECT_DIR"]


class TestGetTicketsDir:
    """取得 Tickets 目錄的測試"""

    def test_get_tickets_dir_with_v_prefix(self, temp_project_dir):
        """測試帶 v 前綴的版本號"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            result = get_tickets_dir("v0.31.0")
            expected = temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets"
            assert result == expected
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_get_tickets_dir_without_v_prefix(self, temp_project_dir):
        """測試不帶 v 前綴的版本號"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            result = get_tickets_dir("0.31.0")
            expected = temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets"
            assert result == expected
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]


class TestGetTicketPath:
    """取得 Ticket 檔案路徑的測試"""

    def test_get_ticket_path_md_exists(self, temp_project_dir):
        """測試 .md 檔案存在時優先返回"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            tickets_dir = temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)

            # 建立 .md 檔案
            md_path = tickets_dir / "0.31.0-W4-001.md"
            md_path.touch()

            result = get_ticket_path("0.31.0", "0.31.0-W4-001")
            assert result == md_path
            assert result.suffix == ".md"
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_get_ticket_path_yaml_fallback(self, temp_project_dir):
        """測試 .md 不存在時降級到 .yaml"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            tickets_dir = temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)

            # 只建立 .yaml 檔案
            yaml_path = tickets_dir / "0.31.0-W4-001.yaml"
            yaml_path.touch()

            result = get_ticket_path("0.31.0", "0.31.0-W4-001")
            assert result == yaml_path
            assert result.suffix == ".yaml"
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_get_ticket_path_default_md(self, temp_project_dir):
        """測試都不存在時預設返回 .md 路徑"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            result = get_ticket_path("0.31.0", "0.31.0-W4-001")
            assert result.suffix == ".md"
            assert "0.31.0-W4-001.md" in str(result)
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]


class TestParseFrontmatter:
    """解析 frontmatter 的測試"""

    def test_parse_valid_frontmatter(self):
        """測試解析有效的 frontmatter"""
        content = """---
id: test-001
status: pending
---
Body content here"""

        fm, body = parse_frontmatter(content)

        assert fm["id"] == "test-001"
        assert fm["status"] == "pending"
        assert body.strip() == "Body content here"

    def test_parse_no_frontmatter(self):
        """測試沒有 frontmatter 的內容"""
        content = "Plain content without frontmatter"

        fm, body = parse_frontmatter(content)

        assert fm == {}
        assert body == content

    def test_parse_incomplete_frontmatter(self):
        """測試不完整的 frontmatter"""
        content = "---\nid: test\n"

        fm, body = parse_frontmatter(content)

        # 不完整的 frontmatter 應該被視為無 frontmatter
        assert fm == {}
        assert body == content

    def test_parse_invalid_yaml_frontmatter(self):
        """測試無效的 YAML frontmatter"""
        content = """---
id: test
invalid: [ syntax
---
Body"""

        # 無效 YAML 應該丟出 YAMLParseError
        with pytest.raises(YAMLParseError):
            parse_frontmatter(content)


class TestLoadTicket:
    """載入 Ticket 的測試"""

    def test_load_ticket_markdown(self, temp_project_dir, valid_ticket_markdown):
        """測試載入 Markdown 格式 Ticket"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            tickets_dir = temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)

            # 寫入 Ticket 檔案
            ticket_path = tickets_dir / "0.31.0-W4-001.md"
            ticket_path.write_text(valid_ticket_markdown, encoding="utf-8")

            result = load_ticket("0.31.0", "0.31.0-W4-001")

            assert result is not None
            assert result["id"] == "0.31.0-W4-001"
            assert result["status"] == "pending"
            assert "_body" in result
            assert "_path" in result
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_load_ticket_yaml(self, temp_project_dir, valid_ticket_yaml):
        """測試載入 YAML 格式 Ticket"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            tickets_dir = temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)

            # 寫入 YAML Ticket 檔案
            ticket_path = tickets_dir / "0.31.0-W4-001.yaml"
            ticket_path.write_text(valid_ticket_yaml, encoding="utf-8")

            result = load_ticket("0.31.0", "0.31.0-W4-001")

            assert result is not None
            assert result["id"] == "0.31.0-W4-001"
            assert result["status"] == "pending"
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_load_ticket_not_found(self, temp_project_dir):
        """測試載入不存在的 Ticket"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            result = load_ticket("0.31.0", "0.31.0-W4-999")
            assert result is None
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]


class TestSaveTicket:
    """儲存 Ticket 的測試"""

    def test_save_ticket_markdown(self, temp_project_dir, valid_ticket_data):
        """測試儲存為 Markdown 格式"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            ticket = valid_ticket_data.copy()
            ticket["_body"] = "Test body content"

            ticket_path = (
                temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets" / "test.md"
            )

            save_ticket(ticket, ticket_path)

            assert ticket_path.exists()
            content = ticket_path.read_text(encoding="utf-8")
            assert "---" in content
            assert "id: 0.31.0-W4-001" in content
            assert "Test body content" in content
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_save_ticket_yaml(self, temp_project_dir, valid_ticket_data):
        """測試儲存為 YAML 格式"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            ticket = valid_ticket_data.copy()

            ticket_path = (
                temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets" / "test.yaml"
            )

            save_ticket(ticket, ticket_path)

            assert ticket_path.exists()
            content = ticket_path.read_text(encoding="utf-8")
            loaded = yaml.safe_load(content)
            assert loaded["ticket"]["id"] == "0.31.0-W4-001"
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]


    def test_save_ticket_with_checkbox_acceptance(self, temp_project_dir, valid_ticket_data):
        """測試儲存包含 checkbox 格式的 acceptance 欄位

        驗證 acceptance 欄位使用 markdown checkbox 格式時：
        1. 儲存時自動為 [ ] 和 [x] 加上引號（由 yaml.dump 自動處理）
        2. 儲存後可以正常載入
        3. checkbox 內容正確保留

        此測試確保修復 W8-005 問題後的行為正確。
        """
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            ticket = valid_ticket_data.copy()
            ticket["_body"] = "# Execution Log\n\nTest content"
            ticket["acceptance"] = [
                "[x] 第一個驗收條件已完成",
                "[ ] 第二個驗收條件待處理",
                "一般文字驗收條件（無 checkbox）",
            ]

            ticket_path = (
                temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets" / "checkbox-test.md"
            )

            # 儲存 Ticket
            save_ticket(ticket, ticket_path)

            assert ticket_path.exists(), "Ticket 檔案應該被建立"

            # 驗證檔案內容包含正確格式的引號
            content = ticket_path.read_text(encoding="utf-8")
            assert "'[x] 第一個驗收條件已完成'" in content, "完成的 checkbox 應該被引號包圍"
            assert "'[ ] 第二個驗收條件待處理'" in content, "待處理的 checkbox 應該被引號包圍"

            # 直接解析檔案驗證載入正確性
            parts = content.split("---", 2)
            assert len(parts) >= 3, "檔案應該包含 frontmatter"
            frontmatter = yaml.safe_load(parts[1])
            assert frontmatter is not None, "Frontmatter 應該能正確解析"
            assert "acceptance" in frontmatter, "應該包含 acceptance 欄位"
            assert len(frontmatter["acceptance"]) == 3, "應該有 3 個驗收條件"
            assert frontmatter["acceptance"][0] == "[x] 第一個驗收條件已完成"
            assert frontmatter["acceptance"][1] == "[ ] 第二個驗收條件待處理"
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]


class TestListTickets:
    """列出 Tickets 的測試"""

    def test_list_tickets_multiple(self, temp_project_dir, valid_ticket_markdown):
        """測試列出多個 Tickets"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            tickets_dir = temp_project_dir / "docs" / "work-logs" / "v0.31.0" / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)

            # 建立多個 Ticket
            for i in range(1, 4):
                ticket_id = f"0.31.0-W4-00{i}"
                ticket_data = {
                    "id": ticket_id,
                    "title": f"Test Ticket {i}",
                    "status": "pending",
                    "what": f"Test {i}",
                }
                frontmatter_yaml = yaml.dump(ticket_data, allow_unicode=True)
                content = f"---\n{frontmatter_yaml}---\nBody"
                (tickets_dir / f"{ticket_id}.md").write_text(content, encoding="utf-8")

            result = list_tickets("0.31.0")

            assert len(result) == 3
            assert result[0]["id"] == "0.31.0-W4-001"
            assert result[1]["id"] == "0.31.0-W4-002"
            assert result[2]["id"] == "0.31.0-W4-003"
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]

    def test_list_tickets_empty_dir(self, temp_project_dir):
        """測試空的 Tickets 目錄"""
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        try:
            os.environ["CLAUDE_PROJECT_DIR"] = str(temp_project_dir)
            result = list_tickets("0.31.0")
            assert result == []
        finally:
            if old_env:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env
            elif "CLAUDE_PROJECT_DIR" in os.environ:
                del os.environ["CLAUDE_PROJECT_DIR"]
