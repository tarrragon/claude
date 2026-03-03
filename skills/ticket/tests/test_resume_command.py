"""
Resume 命令測試

測試 resume 命令的 handoff 檔案恢復功能。
"""

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch

import pytest
import yaml

from ticket_system.commands.resume import (
    list_pending_handoffs,
    load_handoff_file,
    archive_handoff_file,
    execute,
    _get_handoff_dir,
    _find_handoff_file,
    _print_handoff_info,
    _print_basic_info,
    _print_5w1h_info,
    _print_chain_info,
    _print_markdown_content,
    _print_ticket_info,
)


@pytest.fixture
def temp_handoff_env() -> tuple[Path, Path]:
    """建立臨時 handoff 環境"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # 建立目錄結構
        handoff_pending = project_root / ".claude" / "handoff" / "pending"
        handoff_archive = project_root / ".claude" / "handoff" / "archive"
        handoff_pending.mkdir(parents=True, exist_ok=True)
        handoff_archive.mkdir(parents=True, exist_ok=True)

        # 建立 pubspec.yaml 標記為專案根目錄
        (project_root / "pubspec.yaml").touch()

        # 設置環境變數
        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)

        try:
            yield project_root, handoff_pending
        finally:
            # 恢復環境變數
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


def _create_handoff_json(
    handoff_dir: Path,
    ticket_id: str,
    direction: str = "auto",
    title: str = "Test Task",
    what: str = "Test description"
) -> None:
    """輔助函式：建立 JSON 格式的 handoff 檔案"""
    handoff_data = {
        "ticket_id": ticket_id,
        "direction": direction,
        "timestamp": "2026-01-30T12:00:00",
        "from_status": "in_progress",
        "title": title,
        "what": what,
        "chain": {
            "root": "0.31.0-W4-001",
            "parent": "0.31.0-W4-001",
            "depth": 1,
            "sequence": [2]
        }
    }

    handoff_file = handoff_dir / f"{ticket_id}.json"
    with open(handoff_file, "w", encoding="utf-8") as f:
        json.dump(handoff_data, f, ensure_ascii=False, indent=2)


def _create_handoff_md(
    handoff_dir: Path,
    ticket_id: str,
    content: str = "# Handoff\n\nTest content"
) -> None:
    """輔助函式：建立 Markdown 格式的 handoff 檔案"""
    handoff_file = handoff_dir / f"{ticket_id}.md"
    handoff_file.write_text(content, encoding="utf-8")


class TestListPendingHandoffs:
    """測試 list_pending_handoffs 函式"""

    def test_list_empty(self, temp_handoff_env):
        """測試空的 pending 目錄"""
        project_root, _ = temp_handoff_env

        result = list_pending_handoffs()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_json_handoffs(self, temp_handoff_env):
        """測試列出 JSON 格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001", title="Task 1")
        _create_handoff_json(handoff_dir, "0.31.0-W4-002", title="Task 2")

        result = list_pending_handoffs()

        assert len(result) == 2
        assert result[0]["ticket_id"] == "0.31.0-W4-001"
        assert result[1]["ticket_id"] == "0.31.0-W4-002"

    def test_list_mixed_formats(self, temp_handoff_env):
        """測試混合格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001")
        _create_handoff_md(handoff_dir, "0.31.0-W4-002")

        result = list_pending_handoffs()

        assert len(result) == 2


class TestLoadHandoffFile:
    """測試 load_handoff_file 函式"""

    def test_load_json_handoff(self, temp_handoff_env):
        """測試載入 JSON 格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001", title="Test Task")

        result = load_handoff_file("0.31.0-W4-001")

        assert result is not None
        assert result["ticket_id"] == "0.31.0-W4-001"
        assert result["title"] == "Test Task"

    def test_load_md_handoff(self, temp_handoff_env):
        """測試載入 Markdown 格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_md(handoff_dir, "0.31.0-W4-002", content="# Test\n\nContent")

        result = load_handoff_file("0.31.0-W4-002")

        assert result is not None
        assert result["ticket_id"] == "0.31.0-W4-002"
        assert result["format"] == "markdown"
        assert "# Test" in result["content"]

    def test_load_nonexistent_handoff(self, temp_handoff_env):
        """測試載入不存在的 handoff 檔案"""
        project_root, _ = temp_handoff_env

        result = load_handoff_file("0.31.0-W4-999")

        assert result is None


class TestArchiveHandoffFile:
    """測試 archive_handoff_file 函式"""

    def test_archive_json_handoff(self, temp_handoff_env):
        """測試歸檔 JSON 格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001")

        result = archive_handoff_file("0.31.0-W4-001")

        assert result is True

        # 確認檔案已移動
        pending_file = handoff_dir / "0.31.0-W4-001.json"
        archive_file = project_root / ".claude" / "handoff" / "archive" / "0.31.0-W4-001.json"

        assert not pending_file.exists()
        assert archive_file.exists()

    def test_archive_md_handoff(self, temp_handoff_env):
        """測試歸檔 Markdown 格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_md(handoff_dir, "0.31.0-W4-002")

        result = archive_handoff_file("0.31.0-W4-002")

        assert result is True

        # 確認檔案已移動
        pending_file = handoff_dir / "0.31.0-W4-002.md"
        archive_file = project_root / ".claude" / "handoff" / "archive" / "0.31.0-W4-002.md"

        assert not pending_file.exists()
        assert archive_file.exists()

    def test_archive_nonexistent_handoff(self, temp_handoff_env):
        """測試歸檔不存在的 handoff 檔案"""
        project_root, _ = temp_handoff_env

        result = archive_handoff_file("0.31.0-W4-999")

        assert result is False


class TestFindHandoffFile:
    """測試 _find_handoff_file 函式"""

    def test_find_json_file(self, temp_handoff_env):
        """測試尋找 JSON 格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001")

        result = _find_handoff_file("0.31.0-W4-001", "pending")

        assert result is not None
        file_path, file_format = result
        assert file_path.exists()
        assert file_format == "json"

    def test_find_markdown_file(self, temp_handoff_env):
        """測試尋找 Markdown 格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_md(handoff_dir, "0.31.0-W4-002")

        result = _find_handoff_file("0.31.0-W4-002", "pending")

        assert result is not None
        file_path, file_format = result
        assert file_path.exists()
        assert file_format == "markdown"

    def test_find_nonexistent_file(self, temp_handoff_env):
        """測試尋找不存在的檔案"""
        project_root, _ = temp_handoff_env

        result = _find_handoff_file("0.31.0-W4-999", "pending")

        assert result is None

    def test_json_preferred_over_markdown(self, temp_handoff_env):
        """測試 JSON 檔案優先於 Markdown 檔案"""
        project_root, handoff_dir = temp_handoff_env

        # 同時建立 JSON 和 Markdown 檔案
        _create_handoff_json(handoff_dir, "0.31.0-W4-001")
        _create_handoff_md(handoff_dir, "0.31.0-W4-001")

        result = _find_handoff_file("0.31.0-W4-001", "pending")

        assert result is not None
        _, file_format = result
        assert file_format == "json"


class TestPrintFunctions:
    """測試列印輔助函式"""

    def test_print_basic_info(self, capsys):
        """測試 _print_basic_info 函式"""
        handoff = {
            "ticket_id": "0.31.0-W4-001",
            "title": "Test Task",
            "from_status": "in_progress",
            "direction": "auto",
            "timestamp": "2026-01-30T12:00:00"
        }

        _print_basic_info(handoff)

        captured = capsys.readouterr()
        assert "基本資訊" in captured.out
        assert "0.31.0-W4-001" in captured.out
        assert "Test Task" in captured.out

    def test_print_chain_info(self, capsys):
        """測試 _print_chain_info 函式"""
        handoff = {
            "chain": {
                "root": "0.31.0-W4-001",
                "parent": "0.31.0-W4-001",
                "depth": 1,
                "sequence": [2]
            }
        }

        _print_chain_info(handoff)

        captured = capsys.readouterr()
        assert "任務鏈資訊" in captured.out
        assert "0.31.0-W4-001" in captured.out

    def test_print_markdown_content(self, capsys):
        """測試 _print_markdown_content 函式"""
        handoff = {
            "format": "markdown",
            "content": "# Test\n\nMarkdown content"
        }

        _print_markdown_content(handoff)

        captured = capsys.readouterr()
        assert "完整內容" in captured.out
        assert "# Test" in captured.out


class TestExecute:
    """測試 execute 函式（主命令邏輯）"""

    def test_execute_list(self, temp_handoff_env, capsys):
        """測試 --list 選項"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001", title="Task 1")
        _create_handoff_json(handoff_dir, "0.31.0-W4-002", title="Task 2")

        args = argparse.Namespace(
            list=True,
            ticket_id=None,
            version=None
        )

        result = execute(args)

        assert result == 0

        captured = capsys.readouterr()
        assert "待恢復任務清單" in captured.out or "[待恢復任務清單]" in captured.out
        assert "0.31.0-W4-001" in captured.out
        assert "0.31.0-W4-002" in captured.out

    def test_execute_resume_handoff(self, temp_handoff_env, capsys):
        """測試恢復 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001", title="Test Task")

        args = argparse.Namespace(
            list=False,
            ticket_id="0.31.0-W4-001",
            version=None
        )

        result = execute(args)

        assert result == 0

        captured = capsys.readouterr()
        assert "0.31.0-W4-001" in captured.out
        assert "Test Task" in captured.out

        # 確認檔案已標記為已接手（resumed_at 已更新）
        pending_file = handoff_dir / "0.31.0-W4-001.json"
        assert pending_file.exists()
        import json
        with open(pending_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("resumed_at") is not None

    def test_execute_resume_nonexistent(self, temp_handoff_env, capsys):
        """測試恢復不存在的 handoff 檔案"""
        project_root, _ = temp_handoff_env

        args = argparse.Namespace(
            list=False,
            ticket_id="0.31.0-W4-999",
            version=None
        )

        result = execute(args)

        assert result == 1

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "找不到" in captured.out

    def test_execute_missing_ticket_id(self, temp_handoff_env, capsys):
        """測試缺少 ticket_id 參數"""
        project_root, _ = temp_handoff_env

        args = argparse.Namespace(
            list=False,
            ticket_id=None,
            version=None
        )

        result = execute(args)

        assert result == 1

        captured = capsys.readouterr()
        assert "用法" in captured.out or "usage" in captured.out.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
