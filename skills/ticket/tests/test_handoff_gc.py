"""
Handoff GC 命令測試（W6-001）

驗證 execute_gc() 的 --dry-run 和 --execute 行為：
- 識別並列出 stale handoff
- --dry-run 不移動檔案
- --execute 移動至 archive/
- 無 stale 時輸出清潔訊息
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands.handoff_gc import execute_gc, _collect_stale_handoffs


@pytest.fixture
def temp_gc_env():
    """建立臨時 GC 測試環境"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        handoff_pending = project_root / ".claude" / "handoff" / "pending"
        handoff_archive = project_root / ".claude" / "handoff" / "archive"
        handoff_pending.mkdir(parents=True, exist_ok=True)
        (project_root / "pubspec.yaml").touch()

        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)

        try:
            yield project_root, handoff_pending, handoff_archive
        finally:
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


def _write_handoff(pending_dir: Path, ticket_id: str, direction: str, from_status: str = "in_progress") -> Path:
    """建立測試用 handoff JSON"""
    data = {
        "ticket_id": ticket_id,
        "direction": direction,
        "timestamp": "2026-01-30T12:00:00",
        "from_status": from_status,
        "title": "Test",
    }
    path = pending_dir / f"{ticket_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def _write_handoff_markdown(pending_dir: Path, ticket_id: str, content: str = "Test handoff") -> Path:
    """建立測試用 handoff Markdown 檔案"""
    path = pending_dir / f"{ticket_id}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestCollectStaleHandoffs:
    """測試 _collect_stale_handoffs 函式"""

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_no_completed_ticket_returns_empty(self, mock_completed, temp_gc_env):
        """來源 ticket 未完成時，無 stale handoff"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = False
        _write_handoff(pending, "0.1.0-W6-001", "context-refresh")
        result = _collect_stale_handoffs()
        assert len(result) == 0

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_context_refresh_completed_is_stale(self, mock_completed, temp_gc_env):
        """context-refresh + 來源已完成（from_status != completed）= stale"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        _write_handoff(pending, "0.1.0-W6-001", "context-refresh", from_status="in_progress")
        result = _collect_stale_handoffs()
        assert len(result) == 1
        assert result[0][1] == "0.1.0-W6-001"

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_context_refresh_from_completed_not_stale(self, mock_completed, temp_gc_env):
        """context-refresh + from_status == completed = 不算 stale"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        _write_handoff(pending, "0.1.0-W6-001", "context-refresh", from_status="completed")
        result = _collect_stale_handoffs()
        assert len(result) == 0

    @patch("ticket_system.commands.handoff_gc.is_ticket_in_progress_or_completed")
    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_task_chain_target_started_is_stale(self, mock_completed, mock_target_started, temp_gc_env):
        """任務鏈 handoff + 目標已啟動 = stale"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        mock_target_started.return_value = True
        _write_handoff(pending, "0.1.0-W6-001", "to-sibling:0.1.0-W6-002")
        result = _collect_stale_handoffs()
        assert len(result) == 1

    @patch("ticket_system.lib.handoff_utils.is_ticket_in_progress_or_completed")
    @patch("ticket_system.lib.handoff_utils.is_ticket_completed")
    def test_task_chain_target_not_started_not_stale(self, mock_completed, mock_target_started, temp_gc_env):
        """任務鏈 handoff + 目標未啟動 = 不算 stale"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        mock_target_started.return_value = False
        _write_handoff(pending, "0.1.0-W6-001", "to-sibling:0.1.0-W6-002")
        result = _collect_stale_handoffs()
        assert len(result) == 0

    def test_empty_pending_dir_returns_empty(self, temp_gc_env):
        """空 pending 目錄應返回空列表"""
        project_root, pending, archive = temp_gc_env
        result = _collect_stale_handoffs()
        assert result == []

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_markdown_stale_handoff_collected(self, mock_completed, temp_gc_env):
        """Markdown 格式的 stale handoff 應被識別"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        _write_handoff_markdown(pending, "0.1.0-W7-001", "# Handoff for W7-001\n\nTest content")
        result = _collect_stale_handoffs()
        assert len(result) == 1
        assert result[0][1] == "0.1.0-W7-001"
        assert result[0][0].suffix == ".md"

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_markdown_not_completed_not_stale(self, mock_completed, temp_gc_env):
        """Markdown 格式的 handoff，若 ticket 未完成，不算 stale"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = False
        _write_handoff_markdown(pending, "0.1.0-W7-001", "# Test")
        result = _collect_stale_handoffs()
        assert len(result) == 0

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_mixed_json_and_markdown_stale(self, mock_completed, temp_gc_env):
        """同時掃描 .json 和 .md 檔案"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        _write_handoff(pending, "0.1.0-W7-001", "context-refresh", from_status="in_progress")
        _write_handoff_markdown(pending, "0.1.0-W7-002", "# Markdown handoff")
        result = _collect_stale_handoffs()
        assert len(result) == 2
        # 驗證兩種格式都被收集
        formats = {r[0].suffix for r in result}
        assert ".json" in formats
        assert ".md" in formats


class TestExecuteGcDryRun:
    """測試 execute_gc(dry_run=True) 行為"""

    def test_no_stale_prints_clean_message(self, temp_gc_env, capsys):
        """無 stale handoff 時輸出清潔訊息"""
        project_root, pending, archive = temp_gc_env
        result = execute_gc(dry_run=True)
        assert result == 0
        captured = capsys.readouterr()
        assert "清潔" in captured.out or "無 stale" in captured.out

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_dry_run_does_not_move_files(self, mock_completed, temp_gc_env, capsys):
        """--dry-run 不應移動檔案"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        stale_file = _write_handoff(pending, "0.1.0-W6-001", "context-refresh", from_status="in_progress")

        result = execute_gc(dry_run=True)

        assert result == 0
        assert stale_file.exists(), "dry-run 不應移動檔案"
        assert not archive.exists() or not (archive / "0.1.0-W6-001.json").exists()

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_dry_run_lists_stale_files(self, mock_completed, temp_gc_env, capsys):
        """--dry-run 應列出 stale handoff"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        _write_handoff(pending, "0.1.0-W6-001", "context-refresh", from_status="in_progress")

        execute_gc(dry_run=True)

        captured = capsys.readouterr()
        assert "0.1.0-W6-001.json" in captured.out

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_dry_run_shows_execute_hint(self, mock_completed, temp_gc_env, capsys):
        """--dry-run 應提示如何執行實際清理"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        _write_handoff(pending, "0.1.0-W6-001", "context-refresh", from_status="in_progress")

        execute_gc(dry_run=True)

        captured = capsys.readouterr()
        assert "--execute" in captured.out


class TestExecuteGcExecute:
    """測試 execute_gc(dry_run=False) 行為"""

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_execute_moves_stale_to_archive(self, mock_completed, temp_gc_env):
        """--execute 應將 stale handoff 移至 archive/"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        stale_file = _write_handoff(pending, "0.1.0-W6-001", "context-refresh", from_status="in_progress")

        result = execute_gc(dry_run=False)

        assert result == 0
        assert not stale_file.exists(), "stale 檔案應被移走"
        assert (archive / "0.1.0-W6-001.json").exists(), "檔案應移至 archive/"

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_execute_preserves_non_stale(self, mock_completed, temp_gc_env):
        """--execute 不應移動非 stale 的 handoff"""
        project_root, pending, archive = temp_gc_env
        mock_completed.side_effect = lambda tid: tid == "0.1.0-W6-001"

        stale_file = _write_handoff(pending, "0.1.0-W6-001", "context-refresh", from_status="in_progress")
        valid_file = _write_handoff(pending, "0.1.0-W6-002", "context-refresh", from_status="in_progress")

        execute_gc(dry_run=False)

        assert not stale_file.exists(), "stale 檔案應被移走"
        assert valid_file.exists(), "非 stale 檔案應保留"

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_execute_reports_count(self, mock_completed, temp_gc_env, capsys):
        """--execute 應回報清理數量"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        _write_handoff(pending, "0.1.0-W6-001", "context-refresh", from_status="in_progress")

        execute_gc(dry_run=False)

        captured = capsys.readouterr()
        assert "1" in captured.out

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_execute_moves_markdown_stale_to_archive(self, mock_completed, temp_gc_env):
        """--execute 應將 stale Markdown handoff 移至 archive/"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        stale_file = _write_handoff_markdown(pending, "0.1.0-W7-001", "# Stale handoff")

        result = execute_gc(dry_run=False)

        assert result == 0
        assert not stale_file.exists(), "stale Markdown 檔案應被移走"
        assert (archive / "0.1.0-W7-001.md").exists(), "Markdown 檔案應移至 archive/"

    @patch("ticket_system.commands.handoff_gc.is_ticket_completed")
    def test_execute_moves_mixed_formats_to_archive(self, mock_completed, temp_gc_env):
        """--execute 應同時移動 .json 和 .md 格式的 stale handoff"""
        project_root, pending, archive = temp_gc_env
        mock_completed.return_value = True
        json_file = _write_handoff(pending, "0.1.0-W7-001", "context-refresh", from_status="in_progress")
        md_file = _write_handoff_markdown(pending, "0.1.0-W7-002", "# Markdown")

        result = execute_gc(dry_run=False)

        assert result == 0
        assert not json_file.exists()
        assert not md_file.exists()
        assert (archive / "0.1.0-W7-001.json").exists()
        assert (archive / "0.1.0-W7-002.md").exists()
