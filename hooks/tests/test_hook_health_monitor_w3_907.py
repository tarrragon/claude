"""Tests for hook-health-monitor.py staleness / log-dir resolution fixes.

覆蓋兩個既存誤判情境：
1. 單一持久檔（open mode "a" 逐次 append）的 log 目錄，目錄本身 mtime 停在
   建檔當下不變，但檔案內容持續更新 -> 應以目錄內最新檔案 mtime 判斷，
   不應誤判為 staleness (FAIL)。
2. hook 呼叫 setup_hook_logging(HOOK_NAME) 時使用與檔名 stem（含去 `-hook`
   後綴）皆不符的自訂短名 -> 應能從原始碼掃描 HOOK_NAME 常數值找到對應
   log 目錄，不應誤判為 "log dir not found"。
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOK_DIR))


def _load_monitor_module():
    path = HOOK_DIR / "hook-health-monitor.py"
    spec = importlib.util.spec_from_file_location("hook_health_monitor_w3_907", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


monitor = _load_monitor_module()


class TestNewestFileMtime:
    """_newest_file_mtime: 掃描目錄內最新檔案 mtime，而非目錄本身 mtime"""

    def test_single_persistent_file_append_not_stale(self, tmp_path):
        """單一持久檔案 mtime 更新，即使目錄本身 mtime 未變也應反映最新寫入"""
        log_dir = tmp_path / "some-hook"
        log_dir.mkdir()
        diag_log = log_dir / "diagnostic.log"
        diag_log.write_text("line 1\n", encoding="utf-8")

        # 模擬目錄 mtime 停在建檔當下（過去），但檔案持續 append 到現在
        old_time = time.time() - 100 * 3600  # 100 小時前
        import os

        os.utime(log_dir, (old_time, old_time))

        # 檔案本身維持「現在」的 mtime（剛剛寫入）
        newest = monitor._newest_file_mtime(log_dir)

        # 檔案 mtime（現在）應遠比目錄 mtime（100 小時前）新
        assert newest > old_time + 3600

    def test_large_file_count_stays_fast_and_non_recursive(self, tmp_path):
        """P0 回歸：大量檔案（5000 個）不遞迴子目錄仍應在合理時間內完成，
        且子目錄內的檔案不影響結果（第一層限定，非遞迴）
        """
        log_dir = tmp_path / "busy-hook"
        log_dir.mkdir()

        for i in range(5000):
            (log_dir / f"log-{i}.log").write_text("x", encoding="utf-8")

        # 子目錄放一個極新的檔案；不應被掃到（限定第一層，避免遞迴大量子目錄）
        nested_dir = log_dir / "nested"
        nested_dir.mkdir()
        nested_file = nested_dir / "nested.log"
        nested_file.write_text("nested\n", encoding="utf-8")
        future_time = time.time() + 10000
        import os

        os.utime(nested_file, (future_time, future_time))

        start = time.monotonic()
        newest = monitor._newest_file_mtime(log_dir)
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, f"應在合理時間內完成，實際耗時 {elapsed:.2f}s"
        # 巢狀檔案的未來時間戳不應影響結果（未遞迴掃描）
        assert newest < future_time

    def test_empty_dir_falls_back_to_dir_mtime(self, tmp_path):
        """空目錄無檔案時 fallback 回傳目錄本身 mtime，不拋錯"""
        log_dir = tmp_path / "empty-hook"
        log_dir.mkdir()

        newest = monitor._newest_file_mtime(log_dir)

        assert newest == pytest.approx(log_dir.stat().st_mtime, abs=1.0)

    def test_check_single_hook_log_uses_newest_file_not_dir_mtime(self, tmp_path, monkeypatch):
        """回歸案例：目錄 mtime 過期但檔案內容最近寫入 -> 不應判 FAIL"""
        project_root = tmp_path
        log_dir = project_root / ".claude" / "hook-logs" / "some-hook"
        log_dir.mkdir(parents=True)
        (log_dir / "some-hook.log").write_text("recent\n", encoding="utf-8")

        import os

        old_time = time.time() - 800 * 3600  # 遠超過 CRITICAL_THRESHOLD_HOURS
        os.utime(log_dir, (old_time, old_time))

        severity, msg, filename = monitor._check_single_hook_log(
            "some-hook.py", project_root
        )

        assert severity == 0, f"expected OK (0), got severity={severity}, msg={msg}"
        assert "[OK]" in msg


class TestResolveHookNameFromSource:
    """_resolve_hook_name_from_source: 從原始碼掃描 HOOK_NAME 常數"""

    def test_extracts_custom_hook_name_constant(self, tmp_path):
        project_root = tmp_path
        hooks_dir = project_root / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        hook_file = hooks_dir / "foo-availability-check-hook.py"
        hook_file.write_text(
            'HOOK_NAME = "foo-check"\n'
            "logger = setup_hook_logging(HOOK_NAME)\n",
            encoding="utf-8",
        )

        result = monitor._resolve_hook_name_from_source(
            "foo-availability-check-hook.py", project_root
        )

        assert result == "foo-check"

    def test_returns_none_when_no_hook_name_constant(self, tmp_path):
        project_root = tmp_path
        hooks_dir = project_root / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        hook_file = hooks_dir / "bar-hook.py"
        hook_file.write_text("logger = setup_hook_logging('bar')\n", encoding="utf-8")

        result = monitor._resolve_hook_name_from_source("bar-hook.py", project_root)

        assert result is None

    def test_returns_none_when_file_missing(self, tmp_path):
        result = monitor._resolve_hook_name_from_source("missing-hook.py", tmp_path)
        assert result is None


class TestResolveHookLogDirSourceFallback:
    """resolve_hook_log_dir: 第三層 fallback 讀取 HOOK_NAME 常數"""

    def test_falls_back_to_source_hook_name_when_stem_mismatches(self, tmp_path):
        project_root = tmp_path
        hooks_dir = project_root / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        hook_file = hooks_dir / "foo-availability-check-hook.py"
        hook_file.write_text('HOOK_NAME = "foo-check"\n', encoding="utf-8")

        # log 目錄名與檔名 stem（含去 -hook）皆不符，只符合 HOOK_NAME 常數
        log_dir = project_root / ".claude" / "hook-logs" / "foo-check"
        log_dir.mkdir(parents=True)

        name, resolved_dir, found = monitor.resolve_hook_log_dir(
            "foo-availability-check-hook.py", project_root
        )

        assert found is True
        assert name == "foo-check"
        assert resolved_dir == log_dir

    def test_still_returns_not_found_when_no_match_anywhere(self, tmp_path):
        project_root = tmp_path
        hooks_dir = project_root / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        hook_file = hooks_dir / "orphan-hook.py"
        hook_file.write_text("# no HOOK_NAME constant\n", encoding="utf-8")

        name, resolved_dir, found = monitor.resolve_hook_log_dir(
            "orphan-hook.py", project_root
        )

        assert found is False
