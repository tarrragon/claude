"""W3-044 S4 — force-usage JSONL logging 副作用測試（C1-C4）。

C1-C3 已由 test_require_in_progress.py 涵蓋（force_log_creates_dir_if_missing /
appends_multiple_records / A9 主路徑）；本檔補 C4（OSError recovery）與
跨 entry point 的 hook-logs 整合驗證。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ticket_system.lib import precondition as precondition_mod
from ticket_system.lib.precondition import require_in_progress


class TestForceLogFailureRecovery:
    """C4: hook-logs 寫入失敗（OSError）→ 主操作仍成功 + stderr warning。"""

    def test_C4_oserror_does_not_block_main_flow(self, monkeypatch, capsys):
        """模擬 write_force_usage_log 拋 OSError，require_in_progress 仍應放行。"""

        def _raise_oserror(*args, **kwargs):
            raise OSError("simulated disk full")

        monkeypatch.setattr(
            precondition_mod, "write_force_usage_log", _raise_oserror
        )

        ok, msg = require_in_progress(
            {"status": "pending"}, "TID-C4", "append-log", force=True
        )
        # 主流程仍通過（force 是逃生閥，log 失敗不阻斷）
        assert ok is True
        assert msg is None

        # stderr 含失敗 warning + force bypass warning（雙重訊息）
        captured = capsys.readouterr()
        assert "force-log" in captured.err
        assert "失敗" in captured.err


class TestForceLogJSONLContract:
    """JSONL 格式契約：每行為合法 JSON，含必要欄位。"""

    def test_record_fields_complete(self, tmp_path, monkeypatch):
        logs_dir = tmp_path / "hook-logs"
        monkeypatch.setenv("HOOK_LOGS_DIR", str(logs_dir))

        require_in_progress(
            {"status": "blocked"}, "TID-CONTRACT", "set-acceptance", force=True
        )

        log_file = logs_dir / "cli-force-usage.jsonl"
        record = json.loads(log_file.read_text(encoding="utf-8").strip())

        required_keys = {"timestamp", "ticket_id", "operation", "status_at_time", "reason"}
        assert required_keys.issubset(record.keys())
        assert record["status_at_time"] == "blocked"
        assert record["operation"] == "set-acceptance"
