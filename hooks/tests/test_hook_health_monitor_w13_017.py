"""Tests for hook-health-monitor.py W13-017 extension.

Coverage (W13-008 IMP-2 acceptance):
- write_session_marker: SessionStart 寫 marker (ISO timestamp)
- run_frequency_scan: scope 擴大至全部 hooks
- run_frequency_scan: critical/warning 輸出 stderr 摘要
- run_frequency_scan: normal hook 不輸出 stderr
- main(): 既有 SessionStart 健康檢查邏輯回歸 (marker 寫入 + frequency scan 失敗不阻擋)
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Module loader — hook-health-monitor.py uses hyphen, cannot regular-import
# ---------------------------------------------------------------------------

HOOK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOK_DIR))


def _load_monitor_module():
    path = HOOK_DIR / "hook-health-monitor.py"
    spec = importlib.util.spec_from_file_location("hook_health_monitor_w13_017", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


monitor = _load_monitor_module()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_project(tmp_path):
    """Build a minimal .claude/ tree mimicking real layout."""
    (tmp_path / ".claude" / "state").mkdir(parents=True)
    (tmp_path / ".claude" / "hook-logs").mkdir(parents=True)
    # Minimal settings.json so _load_settings does not return {}
    (tmp_path / ".claude" / "settings.json").write_text(
        '{"hooks": {"SessionStart": []}}', encoding="utf-8"
    )
    return tmp_path


def _make_log(logs_root: Path, hook_name: str, dt: datetime, idx: int = 0):
    hook_dir = logs_root / hook_name
    hook_dir.mkdir(exist_ok=True)
    f = hook_dir / "{}-{}-{}.log".format(hook_name, dt.strftime("%Y%m%d-%H%M%S"), idx)
    f.write_text("dummy")
    ts = dt.timestamp()
    os.utime(f, (ts, ts))
    return f


# ---------------------------------------------------------------------------
# write_session_marker
# ---------------------------------------------------------------------------

class TestWriteSessionMarker:
    def test_writes_iso_timestamp_to_default_path(self, fake_project):
        now = datetime(2026, 5, 19, 14, 30, 0)
        marker = monitor.write_session_marker(fake_project, now=now)

        assert marker == fake_project / ".claude" / "state" / "last-session-start.marker"
        assert marker.exists()
        content = marker.read_text(encoding="utf-8").strip()
        assert content == "2026-05-19T14:30:00"
        # Round-trip with datetime.fromisoformat (used by hook_health.read_session_marker)
        assert datetime.fromisoformat(content) == now

    def test_creates_parent_dir_if_missing(self, tmp_path):
        # state/ does not pre-exist
        (tmp_path / ".claude").mkdir()
        marker = monitor.write_session_marker(tmp_path, now=datetime(2026, 5, 19))
        assert marker.exists()
        assert marker.parent == tmp_path / ".claude" / "state"

    def test_overwrites_existing_marker(self, fake_project):
        old = datetime(2026, 1, 1, 0, 0, 0)
        new = datetime(2026, 5, 19, 14, 30, 0)
        monitor.write_session_marker(fake_project, now=old)
        marker = monitor.write_session_marker(fake_project, now=new)
        assert marker.read_text(encoding="utf-8").strip() == "2026-05-19T14:30:00"


# ---------------------------------------------------------------------------
# run_frequency_scan — scope (全部 hooks) + stderr 摘要格式
# ---------------------------------------------------------------------------

class TestRunFrequencyScan:
    def test_returns_empty_when_no_logs(self, fake_project, caplog):
        logger = logging.getLogger("test")
        flagged = monitor.run_frequency_scan(
            fake_project,
            logger,
            now=datetime(2026, 5, 19, 12, 0, 0),
            logs_root=fake_project / ".claude" / "hook-logs",
        )
        assert flagged == []

    def test_scope_includes_non_sessionstart_hooks(self, fake_project, capsys):
        """Scope 擴大至全部 hooks（非僅 SessionStart）— W13-008 IMP-2 acceptance"""
        now = datetime(2026, 5, 19, 12, 0, 0)
        logs_root = fake_project / ".claude" / "hook-logs"

        # 一個 PostToolUse hook（非 SessionStart），今日大量觸發
        # baseline = 200/7 ≈ 28.6, recent=200, low_freq N=2 → 200 > 57.1 → warning
        for i in range(200):
            _make_log(logs_root, "acceptance-gate", now - timedelta(minutes=i), idx=i)

        logger = logging.getLogger("test_scope")
        flagged = monitor.run_frequency_scan(
            fake_project, logger, now=now, logs_root=logs_root
        )

        assert len(flagged) == 1
        assert flagged[0][0] == "acceptance-gate"
        # PostToolUse hook → low_freq_expected → multiplier 2
        assert flagged[0][1].multiplier == 2
        # stderr 包含命中 hook 名稱
        err = capsys.readouterr().err
        assert "acceptance-gate" in err
        assert "建議：手動建 ANA" in err

    def test_stderr_format_matches_w13_008_example(self, fake_project, capsys):
        """stderr 摘要格式：[hook-health] LVL: <name> 今日觸發 N 次 > 基線 B × n"""
        now = datetime(2026, 5, 19, 12, 0, 0)
        logs_root = fake_project / ".claude" / "hook-logs"

        # 製造 7 天分散 baseline + 今日尖峰
        for d in range(1, 7):
            for i in range(10):
                _make_log(
                    logs_root,
                    "phase4-decision-enforcement",
                    now - timedelta(days=d, hours=i),
                    idx=d * 100 + i,
                )
        # 今日觸發 200 次 → high_freq_ok N=3, baseline = 60/7 ≈ 8.57, 200 > 25.7 → warning
        for i in range(200):
            _make_log(
                logs_root,
                "phase4-decision-enforcement",
                now - timedelta(minutes=i),
                idx=i,
            )

        logger = logging.getLogger("test_format")
        monitor.run_frequency_scan(fake_project, logger, now=now, logs_root=logs_root)

        err = capsys.readouterr().err
        # 格式關鍵字
        assert "[hook-health]" in err
        assert "phase4-decision-enforcement" in err
        assert "今日觸發" in err
        assert "基線" in err
        # high_freq_ok classification → N=3
        assert "× 3" in err

    def test_normal_hooks_produce_no_stderr(self, fake_project, capsys):
        now = datetime(2026, 5, 19, 12, 0, 0)
        logs_root = fake_project / ".claude" / "hook-logs"
        # 平均分散，無尖峰 — 應為 normal
        for d in range(7):
            for i in range(5):
                _make_log(
                    logs_root,
                    "acceptance-gate",
                    now - timedelta(days=d, hours=i),
                    idx=d * 10 + i,
                )

        logger = logging.getLogger("test_normal")
        flagged = monitor.run_frequency_scan(
            fake_project, logger, now=now, logs_root=logs_root
        )
        assert flagged == []
        err = capsys.readouterr().err
        # 完全無 stderr 輸出（normal hook 不報）
        assert err == ""

    def test_classification_for_pretooluse_decision(self, fake_project):
        """phase4-decision-enforcement → high_freq_ok (N=3)"""
        from lib import hook_health
        assert hook_health.classify_hook("phase4-decision-enforcement", {}) == "high_freq_ok"

    def test_baseline_uses_window_7d(self):
        """baseline = sum(per_day) / 7（W13-008 量化標準）"""
        per_day = {"2026-05-13": 7, "2026-05-14": 14, "2026-05-15": 21}
        assert monitor._compute_baseline(per_day) == pytest.approx(42.0 / 7)


# ---------------------------------------------------------------------------
# main() 回歸：既有 SessionStart hook 健康檢查邏輯保留
# ---------------------------------------------------------------------------

class TestMainRegression:
    def test_main_writes_marker_and_runs_existing_check(self, fake_project):
        """main() 寫入 marker + 既有 SessionStart 健康檢查邏輯不被擾動"""
        with patch.object(monitor, "get_project_root", return_value=fake_project):
            with patch.object(monitor, "setup_hook_logging", return_value=logging.getLogger("test_main")):
                code = monitor.main()
        assert code == 0
        marker = fake_project / ".claude" / "state" / "last-session-start.marker"
        assert marker.exists()
        # marker 可被 hook_health.read_session_marker round-trip 解析
        from lib import hook_health
        assert hook_health.read_session_marker(marker_path=marker) is not None

    def test_main_continues_when_frequency_scan_raises(self, fake_project, capsys):
        """frequency scan 拋出時不阻擋既有邏輯（marker 已寫 + main 回 0）"""
        with patch.object(monitor, "get_project_root", return_value=fake_project):
            with patch.object(monitor, "setup_hook_logging", return_value=logging.getLogger("test_resilient")):
                with patch.object(monitor, "run_frequency_scan", side_effect=RuntimeError("boom")):
                    code = monitor.main()
        assert code == 0
        # 既有健康報告仍輸出（標誌：分隔線）
        out = capsys.readouterr()
        assert "Hook system health check" in out.out
        err = out.err
        assert "frequency scan failed" in err

    def test_main_continues_when_marker_write_fails(self, fake_project, capsys):
        """marker 寫入失敗不應阻擋既有 SessionStart 健康檢查"""
        with patch.object(monitor, "get_project_root", return_value=fake_project):
            with patch.object(monitor, "setup_hook_logging", return_value=logging.getLogger("test_marker_fail")):
                with patch.object(monitor, "write_session_marker", side_effect=OSError("disk full")):
                    code = monitor.main()
        assert code == 0
        out = capsys.readouterr()
        assert "Hook system health check" in out.out
        assert "failed to write session marker" in out.err
