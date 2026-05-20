"""Test suite for hook_health lib (W13-016).

Coverage:
- scan_logs(since) — aggregate hook-logs/ directory stats
- classify_hook(name, settings) — 2-class coarse classification
- evaluate(stats, type, baseline) — verdict normal/warning/critical
- read_session_marker() — read .claude/state/last-session-start.marker
- Bootstrap path — no 7-day history fallback to absolute lower bound 100/day
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# Make lib importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import hook_health  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hook_logs_dir(tmp_path):
    """Create a fake .claude/hook-logs/ directory tree."""
    root = tmp_path / "hook-logs"
    root.mkdir()
    return root


def _make_log(dir_path: Path, hook_name: str, dt: datetime, idx: int = 0):
    """Create a fake hook log file mimicking real naming pattern."""
    hook_dir = dir_path / hook_name
    hook_dir.mkdir(exist_ok=True)
    name = f"{hook_name}-{dt.strftime('%Y%m%d-%H%M%S')}-{idx}.log"
    f = hook_dir / name
    f.write_text("dummy log content")
    # Set mtime to dt so scan_logs can filter by since
    ts = dt.timestamp()
    import os
    os.utime(f, (ts, ts))
    return f


# ---------------------------------------------------------------------------
# scan_logs
# ---------------------------------------------------------------------------

class TestScanLogs:
    def test_aggregates_per_hook_count(self, hook_logs_dir):
        now = datetime(2026, 5, 19, 12, 0, 0)
        for i in range(5):
            _make_log(hook_logs_dir, "acceptance-gate", now - timedelta(hours=i), idx=i)
        for i in range(2):
            _make_log(hook_logs_dir, "phase4-decision-enforcement", now - timedelta(hours=i), idx=i)

        since = now - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["acceptance-gate"]["total"] == 5
        assert stats["phase4-decision-enforcement"]["total"] == 2

    def test_filters_by_since(self, hook_logs_dir):
        now = datetime(2026, 5, 19, 12, 0, 0)
        _make_log(hook_logs_dir, "acceptance-gate", now, idx=0)
        # 10 days ago — must be excluded by since=7d
        _make_log(hook_logs_dir, "acceptance-gate", now - timedelta(days=10), idx=1)

        since = now - timedelta(days=7)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["acceptance-gate"]["total"] == 1

    def test_empty_dir_returns_empty_dict(self, hook_logs_dir):
        since = datetime(2026, 5, 19) - timedelta(days=7)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)
        assert stats == {}

    def test_per_day_breakdown_present(self, hook_logs_dir):
        now = datetime(2026, 5, 19, 12, 0, 0)
        _make_log(hook_logs_dir, "h1", now, idx=0)
        _make_log(hook_logs_dir, "h1", now - timedelta(days=1), idx=1)
        _make_log(hook_logs_dir, "h1", now - timedelta(days=1), idx=2)

        stats = hook_health.scan_logs(now - timedelta(days=7), logs_root=hook_logs_dir)

        assert "per_day" in stats["h1"]
        # per_day maps date_str -> count
        assert sum(stats["h1"]["per_day"].values()) == 3


# ---------------------------------------------------------------------------
# classify_hook
# ---------------------------------------------------------------------------

class TestClassifyHook:
    def _settings_with(self, event: str, hook_name: str):
        return {
            "hooks": {
                event: [
                    {
                        "matcher": "",
                        "hooks": [
                            {"type": "command",
                             "command": f"$CLAUDE_PROJECT_DIR/.claude/hooks/{hook_name}.py"}
                        ],
                    }
                ]
            }
        }

    def test_pretooluse_decision_hooks_high_freq_ok(self):
        settings = self._settings_with("PreToolUse", "phase4-decision-enforcement")
        cls = hook_health.classify_hook("phase4-decision-enforcement", settings)
        assert cls == "high_freq_ok"

    def test_wrap_decision_tripwire_high_freq_ok(self):
        settings = self._settings_with("PreToolUse", "wrap-decision-tripwire")
        cls = hook_health.classify_hook("wrap-decision-tripwire", settings)
        assert cls == "high_freq_ok"

    def test_posttooluse_default_low_freq(self):
        settings = self._settings_with("PostToolUse", "acceptance-gate")
        cls = hook_health.classify_hook("acceptance-gate", settings)
        assert cls == "low_freq_expected"

    def test_sessionstart_low_freq(self):
        settings = self._settings_with("SessionStart", "hook-health-monitor")
        cls = hook_health.classify_hook("hook-health-monitor", settings)
        assert cls == "low_freq_expected"

    def test_unknown_hook_defaults_low_freq(self):
        # Hook not in settings — conservative default
        cls = hook_health.classify_hook("never-registered", {"hooks": {}})
        assert cls == "low_freq_expected"


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_normal_when_under_baseline(self):
        stats = {"total": 30, "recent": 10, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=20.0)
        assert verdict.status == "normal"

    def test_warning_when_recent_exceeds_baseline_times_N(self):
        # low_freq N=2 → recent 50 > baseline 20 * 2 = 40 → warning
        stats = {"total": 200, "recent": 50, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=20.0)
        assert verdict.status == "warning"

    def test_high_freq_uses_N3(self):
        # high_freq N=3 → recent 50 vs baseline 20*3=60 → normal
        stats = {"total": 200, "recent": 50, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="high_freq_ok", baseline=20.0)
        assert verdict.status == "normal"

    def test_critical_when_3_consecutive_days_exceed(self):
        # Build per_day with 3 consecutive over-threshold days
        baseline = 10.0
        per_day = {
            "2026-05-17": 30,  # > 10*2
            "2026-05-18": 35,
            "2026-05-19": 40,
        }
        stats = {"total": 105, "recent": 40, "per_day": per_day}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=baseline)
        assert verdict.status == "critical"

    def test_verdict_contains_diagnostic_fields(self):
        stats = {"total": 200, "recent": 50, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=20.0)
        assert verdict.recent == 50
        assert verdict.baseline == 20.0
        assert verdict.multiplier in (2, 3)


# ---------------------------------------------------------------------------
# Bootstrap path
# ---------------------------------------------------------------------------

class TestBootstrap:
    def test_no_history_uses_absolute_lower_bound(self):
        # baseline=0 means no historical data; fallback threshold = 100/day
        stats = {"total": 50, "recent": 50, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=0.0)
        # 50 < 100 → normal (bootstrap absolute threshold)
        assert verdict.status == "normal"
        assert verdict.bootstrap is True

    def test_bootstrap_warning_when_over_absolute_threshold(self):
        stats = {"total": 150, "recent": 150, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=0.0)
        assert verdict.status == "warning"
        assert verdict.bootstrap is True


# ---------------------------------------------------------------------------
# read_session_marker
# ---------------------------------------------------------------------------

class TestSessionMarker:
    def test_reads_iso_timestamp(self, tmp_path):
        marker = tmp_path / "last-session-start.marker"
        ts = "2026-05-19T13:00:00"
        marker.write_text(ts)
        result = hook_health.read_session_marker(marker_path=marker)
        assert result == datetime.fromisoformat(ts)

    def test_returns_none_if_missing(self, tmp_path):
        marker = tmp_path / "nope.marker"
        result = hook_health.read_session_marker(marker_path=marker)
        assert result is None

    def test_returns_none_on_invalid_content(self, tmp_path):
        marker = tmp_path / "bad.marker"
        marker.write_text("not-a-timestamp")
        result = hook_health.read_session_marker(marker_path=marker)
        assert result is None
