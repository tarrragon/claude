"""scan_logs() 效能與取樣估計行為測試（W3-921）。

覆蓋範圍：
- 檔名時間戳解析取代 stat()（結果與 mtime-based 舊行為等價）
- 單目錄超過 MAX_FILES_PER_DIR 時的取樣估計與 WARNING 記錄
- 5000 檔規模下 < 2s 完成（效能斷言放獨立檔案，非計時 pass/fail 門檻混入
  主套件——依 test-assertion-design-rules D1，此為「上界寬鬆檢查」用途，
  斷言值遠高於預期以避免環境抖動造成 flaky）

觸發次數計數來源改為 _liveness/*.jsonl 後（見 hook_health.scan_logs
docstring），本檔原先透過 scan_logs() 斷言 total 的測試改為直接呼叫
_scan_hook_dir()——該函式現僅作 staleness/內容診斷用途，不再驅動
scan_logs() 回傳的 total；檔名解析與取樣估計邏輯本身未變，仍值得獨立驗證。
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import hook_health  # noqa: E402


@pytest.fixture
def hook_logs_dir(tmp_path):
    root = tmp_path / "hook-logs"
    root.mkdir()
    return root


def _touch_log(dir_path: Path, hook_name: str, dt: datetime, idx: int = 0) -> Path:
    """建立檔名含時間戳的空檔（不設定 mtime——驗證解析不依賴 stat）。"""
    hook_dir = dir_path / hook_name
    hook_dir.mkdir(exist_ok=True)
    name = "{}-{}-{}.log".format(hook_name, dt.strftime("%Y%m%d-%H%M%S"), idx)
    f = hook_dir / name
    f.write_text("x")
    return f


class TestFilenameTimestampParsing:
    def test_counts_by_filename_not_mtime(self, hook_logs_dir):
        """mtime 刻意設為與檔名時間戳不同（未來值），驗證計數以檔名為準。

        直接呼叫 _scan_hook_dir()（診斷路徑）——scan_logs() 的 total 現由
        _liveness 驅動，legacy 檔名解析邏輯本身仍需獨立驗證正確性。
        """
        now = datetime(2026, 8, 21, 12, 0, 0)
        f = _touch_log(hook_logs_dir, "acceptance-gate", now, idx=0)
        # mtime 撥到很久以前，若實作誤用 stat() 會被 since 過濾掉
        old_ts = (now - timedelta(days=365)).timestamp()
        os.utime(f, (old_ts, old_ts))

        since = now - timedelta(days=1)
        result = hook_health._scan_hook_dir(
            str(hook_logs_dir / "acceptance-gate"), since, None
        )

        assert result["total"] == 1

    def test_malformed_filename_skipped(self, hook_logs_dir):
        hook_dir = hook_logs_dir / "some-hook"
        hook_dir.mkdir()
        (hook_dir / "not-a-timestamped-name.log").write_text("x")

        since = datetime(2020, 1, 1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats == {}


class TestSamplingEstimate:
    def test_exceeds_cap_triggers_estimate_and_warning(self, hook_logs_dir, caplog):
        """診斷路徑（_scan_hook_dir 直呼）：取樣估計與 WARNING 邏輯未變。"""
        now = datetime(2026, 8, 21, 12, 0, 0)
        n = hook_health.MAX_FILES_PER_DIR + 500
        for i in range(n):
            _touch_log(hook_logs_dir, "high-volume-hook", now, idx=i)

        logger = logging.getLogger("test-hook-health-scan")
        since = now - timedelta(days=1)

        with caplog.at_level(logging.WARNING, logger="test-hook-health-scan"):
            result = hook_health._scan_hook_dir(
                str(hook_logs_dir / "high-volume-hook"), since, logger
            )

        # 取樣估計後 total 應接近真實檔案數（容許取樣誤差，非精確相等）
        assert result["total"] >= hook_health.MAX_FILES_PER_DIR
        assert any(
            "high-volume-hook" in rec.message and "estimated" in rec.message
            for rec in caplog.records
        )

        # scan_logs() 對外仍為 no_precise_count（無 _liveness 記錄）
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)
        assert stats["high-volume-hook"]["no_precise_count"] is True

    def test_under_cap_no_estimate_no_warning(self, hook_logs_dir, caplog):
        now = datetime(2026, 8, 21, 12, 0, 0)
        for i in range(10):
            _touch_log(hook_logs_dir, "low-volume-hook", now, idx=i)

        logger = logging.getLogger("test-hook-health-scan-2")
        since = now - timedelta(days=1)

        with caplog.at_level(logging.WARNING, logger="test-hook-health-scan-2"):
            result = hook_health._scan_hook_dir(
                str(hook_logs_dir / "low-volume-hook"), since, logger
            )

        assert result["total"] == 10
        assert not caplog.records


class TestPerformance:
    def test_5000_files_completes_quickly(self, hook_logs_dir):
        """上界寬鬆檢查（非效能 SLA）：5000 檔應遠低於秒級，斷言值刻意寬鬆。

        scan_logs() 對此 hook 因無 _liveness 記錄而落入 no_precise_count
        診斷路徑——效能斷言的對象正是這條路徑（含 _scan_hook_dir 的完整
        目錄掃描），不表示效能測試已失去意義。
        """
        now = datetime(2026, 8, 21, 12, 0, 0)
        for i in range(5000):
            _touch_log(hook_logs_dir, "perf-hook", now - timedelta(seconds=i), idx=i)

        since = now - timedelta(days=1)
        start = perf_counter()
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)
        elapsed = perf_counter() - start

        assert stats["perf-hook"]["no_precise_count"] is True
        assert elapsed < 5.0
