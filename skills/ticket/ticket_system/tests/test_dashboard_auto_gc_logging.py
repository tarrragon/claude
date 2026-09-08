"""track_dashboard._auto_gc_stale_handoffs 持久化日誌測試（0.2.1-W3-1337）。

來源 0.2.1-W3-1336 定位：該函式歸檔 stale handoff 時僅寫 sys.stderr，
`except Exception: pass` 完全靜默，違反可觀測性規則 4（catch 區塊必須
有日誌）。本測試驗證修復後的雙通道行為：
- 成功歸檔 → hook-logs 有 INFO 記錄，含來源路徑／目標路徑／stale 原因／
  ticket id（時間由 logging FileHandler 的 asctime 自動附加）。
- 歸檔失敗（如檔案已不存在）→ hook-logs 有 WARNING 記錄，含函式名與
  錯誤訊息；且不拋出例外（graceful degrade，不影響 dashboard 主流程）。

隔離依賴 `.claude/skills/ticket/conftest.py` 的 autouse fixture
`_isolate_project_root`（CLAUDE_PROJECT_DIR 導向獨立 tmp 目錄）——
`.claude/lib/hook_logging.py` 的 setup_hook_logging 與
`ticket_system.lib.paths.get_ticket_state_root` 皆讀此環境變數，故本檔
無需自行處理 root 隔離。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _hook_log_dir() -> Path:
    project_root = Path(os.environ["CLAUDE_PROJECT_DIR"])
    return project_root / ".claude" / "hook-logs" / "handoff-gc"


def _read_log_content() -> str:
    log_files = sorted(_hook_log_dir().glob("handoff-gc-*.log"))
    assert log_files, "應產生 .claude/hook-logs/handoff-gc/handoff-gc-*.log"
    return log_files[0].read_text(encoding="utf-8")


class TestAutoGcSuccessLogging:
    """成功歸檔路徑：hook-logs 須有 INFO 記錄含完整上下文。"""

    def test_archive_writes_info_log_with_source_dest_reason_ticket(
        self, tmp_path, monkeypatch
    ):
        from ticket_system.commands import handoff_gc as handoff_gc_module
        from ticket_system.commands import track_dashboard

        src_file = tmp_path / "0.1.0-W1-999.json"
        src_file.write_text("{}", encoding="utf-8")

        def _fake_collect(force=False):
            return [(src_file, "0.1.0-W1-999", "來源 ticket 已完成")]

        monkeypatch.setattr(
            handoff_gc_module, "_collect_stale_handoffs", _fake_collect
        )

        track_dashboard._auto_gc_stale_handoffs()

        content = _read_log_content()
        assert "INFO" in content
        assert "0.1.0-W1-999" in content
        assert "來源 ticket 已完成" in content
        assert str(src_file) in content
        assert "0.1.0-W1-999.json" in content


class TestAutoGcFailureLogging:
    """失敗路徑：hook-logs 須有 WARNING 記錄含函式名，且不可拋出例外。"""

    def test_rename_failure_writes_warning_log_with_function_name(
        self, tmp_path, monkeypatch
    ):
        from ticket_system.commands import handoff_gc as handoff_gc_module
        from ticket_system.commands import track_dashboard

        missing_file = tmp_path / "does-not-exist.json"

        def _fake_collect(force=False):
            return [(missing_file, "0.1.0-W1-998", "測試用不存在檔案")]

        monkeypatch.setattr(
            handoff_gc_module, "_collect_stale_handoffs", _fake_collect
        )

        # graceful degrade：不可拋出，不可影響 dashboard 主流程
        track_dashboard._auto_gc_stale_handoffs()

        content = _read_log_content()
        assert "WARNING" in content
        assert "_auto_gc_stale_handoffs" in content
