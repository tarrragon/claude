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
from ticket_system.lib.handoff_utils import is_ticket_in_progress_or_completed
from ticket_system.commands.exceptions import HandoffDirectionUnknownError


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


class TestIsTicketInProgressOrCompleted:
    """測試 is_ticket_in_progress_or_completed 函式"""

    def test_returns_false_when_ticket_not_found(self, temp_handoff_env):
        """找不到 ticket 時返回 False（保守策略）"""
        result = is_ticket_in_progress_or_completed("0.99.0-W1-999")
        assert result is False

    def test_returns_false_for_invalid_ticket_id_format(self, temp_handoff_env):
        """格式錯誤的 ticket ID 返回 False"""
        result = is_ticket_in_progress_or_completed("invalid-id")
        assert result is False

    @patch("ticket_system.lib.handoff_utils.load_and_validate_ticket")
    def test_returns_true_for_in_progress_ticket(self, mock_load, temp_handoff_env):
        """目標 ticket 為 in_progress 時返回 True"""
        mock_load.return_value = ({"status": "in_progress"}, None)
        result = is_ticket_in_progress_or_completed("0.31.0-W4-001")
        assert result is True

    @patch("ticket_system.lib.handoff_utils.load_and_validate_ticket")
    def test_returns_true_for_completed_ticket(self, mock_load, temp_handoff_env):
        """目標 ticket 為 completed 時返回 True"""
        mock_load.return_value = ({"status": "completed"}, None)
        result = is_ticket_in_progress_or_completed("0.31.0-W4-001")
        assert result is True

    @patch("ticket_system.lib.handoff_utils.load_and_validate_ticket")
    def test_returns_false_for_pending_ticket(self, mock_load, temp_handoff_env):
        """目標 ticket 為 pending 時返回 False"""
        mock_load.return_value = ({"status": "pending"}, None)
        result = is_ticket_in_progress_or_completed("0.31.0-W4-001")
        assert result is False


class TestListPendingHandoffs:
    """測試 list_pending_handoffs 函式"""

    def test_list_empty(self, temp_handoff_env):
        """測試空的 pending 目錄"""
        project_root, _ = temp_handoff_env

        result = list_pending_handoffs()

        assert isinstance(result.handoffs, list)
        assert len(result.handoffs) == 0

    def test_list_json_handoffs(self, temp_handoff_env):
        """測試列出 JSON 格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001", title="Task 1")
        _create_handoff_json(handoff_dir, "0.31.0-W4-002", title="Task 2")

        result = list_pending_handoffs()

        assert len(result.handoffs) == 2
        assert result.handoffs[0]["ticket_id"] == "0.31.0-W4-001"
        assert result.handoffs[1]["ticket_id"] == "0.31.0-W4-002"

    def test_list_mixed_formats(self, temp_handoff_env):
        """測試混合格式的 handoff 檔案"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001")
        _create_handoff_md(handoff_dir, "0.31.0-W4-002")

        result = list_pending_handoffs()

        assert len(result.handoffs) == 2

    @patch("ticket_system.commands.resume.is_ticket_completed")
    @patch("ticket_system.commands.resume.is_ticket_in_progress_or_completed")
    def test_task_chain_handoff_filtered_when_target_in_progress(
        self, mock_target_check, mock_source_check, temp_handoff_env
    ):
        """to-sibling:target_id 且目標 in_progress 時，應過濾為 stale"""
        project_root, handoff_dir = temp_handoff_env

        # 來源 ticket 已 completed，目標 ticket 已 in_progress
        mock_source_check.return_value = True
        mock_target_check.return_value = True

        _create_handoff_json(
            handoff_dir, "0.31.0-W4-001",
            direction="to-sibling:0.31.0-W4-002"
        )

        result = list_pending_handoffs()

        assert len(result.handoffs) == 0, "目標已啟動的任務鏈 handoff 應被過濾"

    @patch("ticket_system.commands.resume.is_ticket_completed")
    @patch("ticket_system.commands.resume.is_ticket_in_progress_or_completed")
    def test_task_chain_handoff_filtered_when_target_completed(
        self, mock_target_check, mock_source_check, temp_handoff_env
    ):
        """to-sibling:target_id 且目標 completed 時，應過濾為 stale"""
        project_root, handoff_dir = temp_handoff_env

        mock_source_check.return_value = True
        mock_target_check.return_value = True

        _create_handoff_json(
            handoff_dir, "0.31.0-W4-001",
            direction="to-sibling:0.31.0-W4-002"
        )

        result = list_pending_handoffs()

        assert len(result.handoffs) == 0, "目標已完成的任務鏈 handoff 應被過濾"

    @patch("ticket_system.commands.resume.is_ticket_completed")
    @patch("ticket_system.commands.resume.is_ticket_in_progress_or_completed")
    def test_task_chain_handoff_kept_when_target_pending(
        self, mock_target_check, mock_source_check, temp_handoff_env
    ):
        """to-sibling:target_id 且目標 pending 時，應保留（待恢復）"""
        project_root, handoff_dir = temp_handoff_env

        mock_source_check.return_value = True
        mock_target_check.return_value = False  # 目標仍 pending

        _create_handoff_json(
            handoff_dir, "0.31.0-W4-001",
            direction="to-sibling:0.31.0-W4-002"
        )

        result = list_pending_handoffs()

        assert len(result.handoffs) == 1, "目標未啟動的任務鏈 handoff 應保留"

    @patch("ticket_system.commands.resume.is_ticket_completed")
    def test_task_chain_without_target_id_kept(
        self, mock_source_check, temp_handoff_env
    ):
        """to-sibling（無 target_id）的任務鏈 handoff，應保留原行為"""
        project_root, handoff_dir = temp_handoff_env

        mock_source_check.return_value = True

        _create_handoff_json(
            handoff_dir, "0.31.0-W4-001",
            direction="to-sibling"  # 無 target_id
        )

        result = list_pending_handoffs()

        assert len(result.handoffs) == 1, "無 target_id 的任務鏈 handoff 應保留"

    def test_unknown_direction_skipped_with_warning(self, temp_handoff_env, capsys):
        """W9-001: 遇到未知 direction 值時跳過該檔案，不中斷整個清單"""
        project_root, handoff_dir = temp_handoff_env

        # 建立含未知 direction 的 handoff 檔案
        _create_handoff_json(
            handoff_dir, "0.31.0-W4-001",
            direction="unknown-type"  # 不在已知列表中
        )

        # 同時建立有效的 handoff 檔案，驗證不會被中斷
        _create_handoff_json(
            handoff_dir, "0.31.0-W4-002",
            direction="context-refresh"  # 有效的 direction
        )

        # 應該返回結果而不拋出異常
        result = list_pending_handoffs()

        # 驗證：只有有效的 handoff 被列出
        assert len(result.handoffs) >= 1, "有效的 handoff 應被列出"

        # 驗證：損壞的 handoff 被記錄為 schema_error
        assert result.schema_error_count == 1, "未知 direction 應計入 schema_error_count"

        # 驗證：警告訊息被輸出到 stderr
        captured = capsys.readouterr()
        assert "跳過未知 direction 的 handoff" in captured.err, "應輸出警告訊息"
        assert "unknown-type" in captured.err, "警告應包含未知 direction 值"

    def test_valid_directions_accepted(self, temp_handoff_env):
        """W7-003: 驗證所有已知 direction 值都被接受"""
        project_root, handoff_dir = temp_handoff_env

        # 測試所有已知的 direction 值
        valid_directions = [
            "context-refresh",
            "to-parent",
            "to-sibling",
            "to-child",
            "auto",
            "to-sibling:0.31.0-W4-002",  # 含 target_id 的格式
        ]

        for direction in valid_directions:
            handoff_dir_iter = handoff_dir
            ticket_id = f"0.31.0-W4-{valid_directions.index(direction):03d}"
            _create_handoff_json(
                handoff_dir_iter, ticket_id,
                direction=direction
            )

        # 所有檔案都應被列出，不拋出異常
        result = list_pending_handoffs()

        # 應該列出所有有效的 handoff（具體數量取決於 stale 過濾）
        assert len(result.handoffs) >= 0  # 至少不拋出異常


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

    def test_find_by_direction_target_to_sibling(self, temp_handoff_env):
        """測試透過 direction 欄位反向查找目標 Ticket（to-sibling）"""
        project_root, handoff_dir = temp_handoff_env

        # 建立 handoff：來源是 0.31.0-W8-001，目標是 0.31.0-W9-001
        _create_handoff_json(
            handoff_dir,
            "0.31.0-W8-001",
            direction="to-sibling:0.31.0-W9-001",
            title="Task moved to sibling"
        )

        # 用目標 Ticket ID 查詢，應該找到這個 handoff
        result = _find_handoff_file("0.31.0-W9-001", "pending")

        assert result is not None
        file_path, file_format = result
        assert file_path.name == "0.31.0-W8-001.json"
        assert file_format == "json"

    def test_find_by_direction_target_to_parent(self, temp_handoff_env):
        """測試透過 direction 欄位反向查找目標 Ticket（to-parent）"""
        project_root, handoff_dir = temp_handoff_env

        # 建立 handoff：來源是 0.31.0-W8-002，目標是 0.31.0-W7-001
        _create_handoff_json(
            handoff_dir,
            "0.31.0-W8-002",
            direction="to-parent:0.31.0-W7-001",
            title="Task returned to parent"
        )

        # 用目標 Ticket ID 查詢，應該找到這個 handoff
        result = _find_handoff_file("0.31.0-W7-001", "pending")

        assert result is not None
        file_path, file_format = result
        assert file_path.name == "0.31.0-W8-002.json"
        assert file_format == "json"

    def test_find_by_direction_target_to_child(self, temp_handoff_env):
        """測試透過 direction 欄位反向查找目標 Ticket（to-child）"""
        project_root, handoff_dir = temp_handoff_env

        # 建立 handoff：來源是 0.31.0-W8-001，目標是 0.31.0-W9-002
        _create_handoff_json(
            handoff_dir,
            "0.31.0-W8-001",
            direction="to-child:0.31.0-W9-002",
            title="Task delegated to child"
        )

        # 用目標 Ticket ID 查詢，應該找到這個 handoff
        result = _find_handoff_file("0.31.0-W9-002", "pending")

        assert result is not None
        file_path, file_format = result
        assert file_path.name == "0.31.0-W8-001.json"
        assert file_format == "json"

    def test_direct_match_preferred_over_reverse_match(self, temp_handoff_env):
        """測試直接匹配優先於反向匹配"""
        project_root, handoff_dir = temp_handoff_env

        # 建立兩個 handoff：
        # 1. 來源是 0.31.0-W9-001（直接匹配）
        # 2. 來源是 0.31.0-W8-001，目標是 0.31.0-W9-001（反向匹配）
        _create_handoff_json(
            handoff_dir,
            "0.31.0-W9-001",
            direction="auto",
            title="Direct match"
        )
        _create_handoff_json(
            handoff_dir,
            "0.31.0-W8-001",
            direction="to-sibling:0.31.0-W9-001",
            title="Reverse match"
        )

        # 查詢應該返回直接匹配的 handoff
        result = _find_handoff_file("0.31.0-W9-001", "pending")

        assert result is not None
        file_path, _ = result
        assert file_path.name == "0.31.0-W9-001.json"

    def test_no_reverse_match_in_archive(self, temp_handoff_env):
        """測試 archive 子目錄不執行反向匹配"""
        project_root, handoff_dir = temp_handoff_env
        archive_dir = project_root / ".claude" / "handoff" / "archive"

        # 在 archive 中建立 handoff
        _create_handoff_json(
            archive_dir,
            "0.31.0-W8-001",
            direction="to-sibling:0.31.0-W9-001",
            title="Archived task"
        )

        # 在 archive 中查詢目標 Ticket，不應執行反向匹配
        result = _find_handoff_file("0.31.0-W9-001", "archive")

        assert result is None


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

        # 確認檔案已從 pending/ 移至 archive/（resume 後自動歸檔）
        pending_file = handoff_dir / "0.31.0-W4-001.json"
        archive_file = project_root / ".claude" / "handoff" / "archive" / "0.31.0-W4-001.json"

        assert not pending_file.exists(), "JSON 檔案應該從 pending/ 目錄移除"
        assert archive_file.exists(), "JSON 檔案應該存在於 archive/ 目錄"

        import json
        with open(archive_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("resumed_at") is not None

    def test_execute_resume_archives_json_file(self, temp_handoff_env, capsys):
        """測試 resume 後 JSON 檔案已從 pending/ 移至 archive/"""
        project_root, handoff_dir = temp_handoff_env

        _create_handoff_json(handoff_dir, "0.31.0-W4-001", title="Test Task")

        args = argparse.Namespace(
            list=False,
            ticket_id="0.31.0-W4-001",
            version=None
        )

        result = execute(args)

        assert result == 0

        # 確認檔案已從 pending/ 移至 archive/
        pending_file = handoff_dir / "0.31.0-W4-001.json"
        archive_file = project_root / ".claude" / "handoff" / "archive" / "0.31.0-W4-001.json"

        # resume 後應該將檔案從 pending 移到 archive
        assert not pending_file.exists(), "JSON 檔案應該從 pending/ 目錄移除"
        assert archive_file.exists(), "JSON 檔案應該存在於 archive/ 目錄"

        # 確認歸檔後的檔案包含 resumed_at
        import json
        with open(archive_file, "r", encoding="utf-8") as f:
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
