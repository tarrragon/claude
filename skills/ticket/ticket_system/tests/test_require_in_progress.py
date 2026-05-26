"""W3-044 S1 — require_in_progress helper 純函式測試（A 組 11 case）。

依 Phase 2 sage 測試矩陣 §A：helper 為純函式，輸入 ticket dict + 參數組合，
輸出 (ok, error_msg)。force=True 路徑透過 monkeypatch HOOK_LOGS_DIR 隔離驗證。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ticket_system.lib.precondition import (
    FORCE_BYPASS_WARNING,
    require_in_progress,
)


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def isolated_hook_logs(tmp_path: Path, monkeypatch):
    """隔離 hook-logs 目錄到 tmp_path，避免污染專案 hook-logs。"""
    logs_dir = tmp_path / "hook-logs"
    monkeypatch.setenv("HOOK_LOGS_DIR", str(logs_dir))
    return logs_dir


def _ticket(status: str | None) -> dict:
    """構造最小 ticket dict。status=None 表示故意省略 status 欄位（A10）。"""
    if status is None:
        return {"id": "TEST-1"}
    return {"id": "TEST-1", "status": status}


# --- A 組測試 -----------------------------------------------------------------


class TestRequireInProgressPureFunction:
    """A1-A11：require_in_progress helper 純函式行為。"""

    def test_A1_pending_default_rejects_suggest_claim(self, isolated_hook_logs):
        ok, msg = require_in_progress(_ticket("pending"), "TID-1", "append-log")
        assert ok is False
        assert msg is not None
        assert "claim" in msg
        assert "TID-1" in msg

    def test_A2_pending_allow_completed_still_rejects(self, isolated_hook_logs):
        ok, msg = require_in_progress(
            _ticket("pending"), "TID-2", "append-log", allow_completed=True
        )
        assert ok is False
        assert "claim" in msg

    def test_A3_in_progress_passes(self, isolated_hook_logs):
        ok, msg = require_in_progress(_ticket("in_progress"), "TID-3", "complete")
        assert ok is True
        assert msg is None

    def test_A4_in_progress_with_allow_completed_passes(self, isolated_hook_logs):
        ok, msg = require_in_progress(
            _ticket("in_progress"), "TID-4", "append-log", allow_completed=True
        )
        assert ok is True
        assert msg is None

    def test_A5_completed_default_rejects_suggest_reopen(self, isolated_hook_logs):
        ok, msg = require_in_progress(_ticket("completed"), "TID-5", "set-acceptance")
        assert ok is False
        assert "reopen" in msg

    def test_A6_completed_allow_completed_passes(self, isolated_hook_logs):
        """append-log 補 review 路徑：completed 通過。"""
        ok, msg = require_in_progress(
            _ticket("completed"), "TID-6", "append-log", allow_completed=True
        )
        assert ok is True
        assert msg is None

    def test_A7_blocked_rejects_suggest_release(self, isolated_hook_logs):
        ok, msg = require_in_progress(_ticket("blocked"), "TID-7", "append-log")
        assert ok is False
        assert "release" in msg

    def test_A8_closed_rejects_suggest_closed(self, isolated_hook_logs):
        ok, msg = require_in_progress(_ticket("closed"), "TID-8", "append-log")
        assert ok is False
        assert "closed" in msg

    def test_A9_force_bypass_pending_logs_and_passes(self, isolated_hook_logs, capsys):
        ok, msg = require_in_progress(
            _ticket("pending"), "TID-9", "append-log", force=True
        )
        assert ok is True
        assert msg is None

        # 驗證 hook-logs JSONL 寫入
        log_file = isolated_hook_logs / "cli-force-usage.jsonl"
        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["ticket_id"] == "TID-9"
        assert record["operation"] == "append-log"
        assert record["status_at_time"] == "pending"
        assert record["reason"] == "force-flag"
        assert "timestamp" in record

        # stderr 含 warning
        captured = capsys.readouterr()
        assert FORCE_BYPASS_WARNING in captured.err

    def test_A10_missing_status_defaults_to_pending(self, isolated_hook_logs):
        """缺 status 欄位 → 視為 pending（最嚴格防禦）。"""
        ok, msg = require_in_progress(_ticket(None), "TID-10", "append-log")
        assert ok is False
        # 訊息應提示 claim（因為視為 pending）
        assert "claim" in msg

    def test_A11_empty_ticket_id_rejects(self, isolated_hook_logs):
        """ticket_id 為空字串 → 拒絕並回傳明確錯誤訊息。"""
        ok, msg = require_in_progress(_ticket("in_progress"), "", "append-log")
        assert ok is False
        assert msg is not None
        # 訊息含 empty-ticket-id 暗示語
        assert "空" in msg or "empty" in msg.lower() or "ticket_id" in msg.lower()


class TestForceLogging:
    """A9 延伸：hook-logs 寫入細節驗證。"""

    def test_force_log_creates_dir_if_missing(self, tmp_path, monkeypatch, capsys):
        """C2: hook-logs 目錄不存在時自動建立。"""
        logs_dir = tmp_path / "nested" / "hook-logs"
        monkeypatch.setenv("HOOK_LOGS_DIR", str(logs_dir))
        assert not logs_dir.exists()

        ok, _ = require_in_progress(
            _ticket("pending"), "TID-DIR", "append-log", force=True
        )
        assert ok is True
        assert logs_dir.exists()
        assert (logs_dir / "cli-force-usage.jsonl").exists()

    def test_force_log_appends_multiple_records(
        self, isolated_hook_logs, capsys
    ):
        """C3: 連續 force 呼叫累積記錄（append-only）。"""
        for i, op in enumerate(["append-log", "set-acceptance", "complete"]):
            ok, _ = require_in_progress(
                _ticket("pending"), f"TID-MULTI-{i}", op, force=True
            )
            assert ok is True

        log_file = isolated_hook_logs / "cli-force-usage.jsonl"
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        ops = [json.loads(line)["operation"] for line in lines]
        assert ops == ["append-log", "set-acceptance", "complete"]
