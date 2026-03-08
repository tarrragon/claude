"""
Resume 命令：Schema 驗證（W4-001）和 Stale 過濾可見性（W4-002）測試

W4-001: 驗證 list_pending_handoffs() 正確跳過格式錯誤的 handoff JSON
W4-002: 驗證 stale 過濾後的計數提示功能
"""

import argparse
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands.exceptions import HandoffSchemaError
from ticket_system.commands.resume import (
    list_pending_handoffs,
    _execute_list,
)
from ticket_system.lib.handoff_utils import scan_pending_handoffs


@pytest.fixture
def temp_handoff_env():
    """建立臨時 handoff 環境"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        handoff_pending = project_root / ".claude" / "handoff" / "pending"
        handoff_pending.mkdir(parents=True, exist_ok=True)
        (project_root / "pubspec.yaml").touch()

        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)

        try:
            yield project_root, handoff_pending
        finally:
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


def _write_json(handoff_dir: Path, ticket_id: str, data: dict) -> None:
    """寫入 handoff JSON 檔案"""
    path = handoff_dir / f"{ticket_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _valid_handoff(ticket_id: str, direction: str = "context-refresh") -> dict:
    """產生一個完整有效的 handoff 資料"""
    return {
        "ticket_id": ticket_id,
        "direction": direction,
        "timestamp": "2026-01-30T12:00:00",
        "from_status": "in_progress",
        "title": "Test Task",
        "what": "Test description",
        "chain": {},
        "resumed_at": None,
    }


# ==============================================================================
# W4-001: Schema 驗證測試
# ==============================================================================


class TestScanPendingHandoffsSchemaValidation:
    """測試 scan_pending_handoffs() 的 schema 驗證行為"""

    def test_valid_schema_no_error(self, temp_handoff_env):
        """完整資料不應有 schema_error"""
        project_root, handoff_dir = temp_handoff_env
        data = _valid_handoff("0.1.0-W4-001")
        _write_json(handoff_dir, "0.1.0-W4-001", data)

        records = scan_pending_handoffs()
        assert len(records) == 1
        assert records[0].schema_error is None

    def test_missing_ticket_id_sets_schema_error(self, temp_handoff_env):
        """缺少 ticket_id 應設置 schema_error"""
        project_root, handoff_dir = temp_handoff_env
        data = _valid_handoff("0.1.0-W4-001")
        del data["ticket_id"]
        _write_json(handoff_dir, "0.1.0-W4-001", data)

        records = scan_pending_handoffs()
        assert len(records) == 1
        assert records[0].schema_error is not None
        assert "ticket_id" in records[0].schema_error

    def test_missing_direction_sets_schema_error(self, temp_handoff_env):
        """缺少 direction 應設置 schema_error"""
        project_root, handoff_dir = temp_handoff_env
        data = _valid_handoff("0.1.0-W4-001")
        del data["direction"]
        _write_json(handoff_dir, "0.1.0-W4-001", data)

        records = scan_pending_handoffs()
        assert len(records) == 1
        assert records[0].schema_error is not None
        assert "direction" in records[0].schema_error

    def test_missing_timestamp_sets_schema_error(self, temp_handoff_env):
        """缺少 timestamp 應設置 schema_error"""
        project_root, handoff_dir = temp_handoff_env
        data = _valid_handoff("0.1.0-W4-001")
        del data["timestamp"]
        _write_json(handoff_dir, "0.1.0-W4-001", data)

        records = scan_pending_handoffs()
        assert len(records) == 1
        assert records[0].schema_error is not None
        assert "timestamp" in records[0].schema_error

    def test_missing_multiple_fields_lists_all(self, temp_handoff_env):
        """缺少多個欄位時，schema_error 包含所有缺失欄位"""
        project_root, handoff_dir = temp_handoff_env
        data = {"from_status": "in_progress"}
        _write_json(handoff_dir, "0.1.0-W4-001", data)

        records = scan_pending_handoffs()
        assert len(records) == 1
        assert records[0].schema_error is not None
        # 應包含缺失的三個欄位
        assert "ticket_id" in records[0].schema_error
        assert "direction" in records[0].schema_error
        assert "timestamp" in records[0].schema_error

    def test_optional_fields_not_required(self, temp_handoff_env):
        """可選欄位缺少時不應有 schema_error"""
        project_root, handoff_dir = temp_handoff_env
        data = {
            "ticket_id": "0.1.0-W4-001",
            "direction": "context-refresh",
            "timestamp": "2026-01-30T12:00:00",
        }
        _write_json(handoff_dir, "0.1.0-W4-001", data)

        records = scan_pending_handoffs()
        assert len(records) == 1
        assert records[0].schema_error is None


class TestListPendingHandoffsSchemaValidation:
    """測試 list_pending_handoffs 的 Schema 驗證行為（W4-001）"""

    def test_malformed_json_skipped(self, temp_handoff_env, capsys):
        """格式錯誤的 handoff（缺少必填欄位）應被跳過"""
        project_root, handoff_dir = temp_handoff_env

        # 建立缺少 direction 的 handoff
        bad_data = {"ticket_id": "0.1.0-W4-001", "timestamp": "2026-01-30T12:00:00"}
        _write_json(handoff_dir, "0.1.0-W4-001", bad_data)

        result = list_pending_handoffs()

        assert len(result.handoffs) == 0, "格式錯誤的 handoff 應被跳過"

    def test_malformed_json_warning_on_stderr(self, temp_handoff_env, capsys):
        """格式錯誤的 handoff 應在 stderr 輸出 WARNING"""
        project_root, handoff_dir = temp_handoff_env

        bad_data = {"ticket_id": "0.1.0-W4-001", "timestamp": "2026-01-30T12:00:00"}
        _write_json(handoff_dir, "0.1.0-W4-001", bad_data)

        list_pending_handoffs()

        captured = capsys.readouterr()
        assert "[WARNING]" in captured.err

    def test_valid_handoffs_unaffected_by_malformed_one(self, temp_handoff_env):
        """格式錯誤的 handoff 不應影響其他有效的 handoff"""
        project_root, handoff_dir = temp_handoff_env

        # 建立一個有效和一個無效的 handoff
        good_data = _valid_handoff("0.1.0-W4-002")
        bad_data = {"ticket_id": "0.1.0-W4-001", "timestamp": "2026-01-30T12:00:00"}
        _write_json(handoff_dir, "0.1.0-W4-002", good_data)
        _write_json(handoff_dir, "0.1.0-W4-001", bad_data)

        result = list_pending_handoffs()

        assert len(result.handoffs) == 1, "有效的 handoff 應被保留"
        assert result.handoffs[0]["ticket_id"] == "0.1.0-W4-002"

    def test_schema_error_count_tracked(self, temp_handoff_env):
        """格式錯誤的 handoff 數量應被追蹤"""
        project_root, handoff_dir = temp_handoff_env

        bad_data = {"ticket_id": "0.1.0-W4-001", "timestamp": "2026-01-30T12:00:00"}
        _write_json(handoff_dir, "0.1.0-W4-001", bad_data)

        result = list_pending_handoffs()

        assert result.schema_error_count == 1


# ==============================================================================
# W4-002: Stale 過濾可見性測試
# ==============================================================================


class TestStaleFilterVisibility:
    """測試 stale 過濾的可見性計數（W4-002）"""

    def test_stale_count_zero_when_no_stale(self, temp_handoff_env):
        """無 stale handoff 時，計數應為 0"""
        project_root, handoff_dir = temp_handoff_env

        _write_json(handoff_dir, "0.1.0-W4-001", _valid_handoff("0.1.0-W4-001"))

        result = list_pending_handoffs()

        assert result.stale_count == 0

    @patch("ticket_system.commands.resume.is_ticket_completed")
    def test_stale_count_increments_for_filtered_handoffs(
        self, mock_completed, temp_handoff_env
    ):
        """stale handoff 被過濾時，計數應累加"""
        project_root, handoff_dir = temp_handoff_env
        mock_completed.return_value = True  # 所有 ticket 都已 completed

        # 建立 context-refresh handoff（非任務鏈，completed 應過濾）
        data = _valid_handoff("0.1.0-W4-001", direction="context-refresh")
        data["from_status"] = "in_progress"  # 不是 completed，所以會被過濾
        _write_json(handoff_dir, "0.1.0-W4-001", data)

        result = list_pending_handoffs()

        assert result.stale_count == 1

    @patch("ticket_system.commands.resume.is_ticket_completed")
    def test_execute_list_shows_stale_hint_when_empty_and_stale_filtered(
        self, mock_completed, temp_handoff_env, capsys
    ):
        """無有效 handoff 但有 stale 被過濾時，應顯示提示"""
        project_root, handoff_dir = temp_handoff_env
        mock_completed.return_value = True

        data = _valid_handoff("0.1.0-W4-001", direction="context-refresh")
        data["from_status"] = "in_progress"
        _write_json(handoff_dir, "0.1.0-W4-001", data)

        result = _execute_list()

        assert result == 0
        captured = capsys.readouterr()
        assert "stale" in captured.out.lower() or "已過濾" in captured.out

    @patch("ticket_system.commands.resume.is_ticket_completed")
    def test_execute_list_shows_stale_hint_in_result_list(
        self, mock_completed, temp_handoff_env, capsys
    ):
        """有有效 handoff 且有 stale 時，也應顯示過濾提示"""
        project_root, handoff_dir = temp_handoff_env

        def completed_side_effect(ticket_id):
            # W4-001 已完成，W4-002 未完成
            return ticket_id == "0.1.0-W4-001"

        mock_completed.side_effect = completed_side_effect

        # W4-001: stale（completed + from_status != completed）
        stale_data = _valid_handoff("0.1.0-W4-001", direction="context-refresh")
        stale_data["from_status"] = "in_progress"
        _write_json(handoff_dir, "0.1.0-W4-001", stale_data)

        # W4-002: 有效
        _write_json(handoff_dir, "0.1.0-W4-002", _valid_handoff("0.1.0-W4-002"))

        result = _execute_list()

        assert result == 0
        captured = capsys.readouterr()
        assert "0.1.0-W4-002" in captured.out
        assert "1" in captured.out  # stale count 出現在提示中
