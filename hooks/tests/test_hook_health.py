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
    """Create a fake legacy-format (one-file-per-trigger) hook log file."""
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


def _make_liveness_entries(root: Path, session_id: str, entries):
    """Append liveness records to root/_liveness/<session_id>.jsonl.

    entries: iterable of (hook_name, datetime) — one JSON line per entry,
    mirroring hook_logging.mark_hook_entry()'s {"hook", "session_id",
    "pid", "ts"} schema.
    """
    liveness_dir = root / "_liveness"
    liveness_dir.mkdir(exist_ok=True)
    path = liveness_dir / "{}.jsonl".format(session_id)
    with path.open("a", encoding="utf-8") as f:
        for hook_name, dt in entries:
            f.write(
                json.dumps(
                    {
                        "hook": hook_name,
                        "session_id": session_id,
                        "pid": 1,
                        "ts": dt.isoformat(),
                    }
                )
                + "\n"
            )
    return path


def _make_daily_log(dir_path: Path, hook_name: str, day: datetime, record_times):
    """Create/append to a fake daily-rotated (append-mode) hook log file.

    record_times: iterable of datetime — one FILE_FORMAT-style record line
    is appended per entry, mimicking hook_logging.py's
    "[%Y-%m-%d %H:%M:%S] DEBUG - Hook execution time: 0.01s" output.
    """
    hook_dir = dir_path / hook_name
    hook_dir.mkdir(exist_ok=True)
    name = f"{hook_name}-{day.strftime('%Y%m%d')}.log"
    f = hook_dir / name
    with f.open("a", encoding="utf-8") as fh:
        for rt in record_times:
            fh.write(
                "[{}] DEBUG - Hook execution time: 0.01s\n".format(
                    rt.strftime("%Y-%m-%d %H:%M:%S")
                )
            )
    return f


# ---------------------------------------------------------------------------
# scan_logs
# ---------------------------------------------------------------------------

class TestScanLogs:
    """scan_logs() 觸發次數計數來源：_liveness/*.jsonl（不再是行數/檔案數）。"""

    def test_aggregates_per_hook_count_from_liveness(self, hook_logs_dir):
        now = datetime(2026, 5, 19, 12, 0, 0)
        entries = [
            ("acceptance-gate", now - timedelta(hours=i)) for i in range(5)
        ] + [("phase4-decision-enforcement", now - timedelta(hours=i)) for i in range(2)]
        _make_liveness_entries(hook_logs_dir, "sess-1", entries)
        # on-disk dirs must exist for the hook to surface via the top-level
        # walk when it has no daily/legacy content otherwise irrelevant.
        (hook_logs_dir / "acceptance-gate").mkdir()
        (hook_logs_dir / "phase4-decision-enforcement").mkdir()

        since = now - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["acceptance-gate"]["total"] == 5
        assert stats["phase4-decision-enforcement"]["total"] == 2
        assert "no_precise_count" not in stats["acceptance-gate"]

    def test_liveness_only_hook_surfaces_without_on_disk_dir(self, hook_logs_dir):
        """A hook with liveness records but no hook-logs/<name>/ directory
        (e.g. purged, or never wrote a legacy/daily file) is still
        authoritative via liveness."""
        now = datetime(2026, 5, 19, 12, 0, 0)
        _make_liveness_entries(hook_logs_dir, "sess-1", [("ghost-hook", now)])

        since = now - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["ghost-hook"]["total"] == 1

    def test_filters_by_since(self, hook_logs_dir):
        now = datetime(2026, 5, 19, 12, 0, 0)
        (hook_logs_dir / "acceptance-gate").mkdir()
        _make_liveness_entries(
            hook_logs_dir,
            "sess-1",
            [
                ("acceptance-gate", now),
                # 10 days ago — must be excluded by since=7d
                ("acceptance-gate", now - timedelta(days=10)),
            ],
        )

        since = now - timedelta(days=7)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["acceptance-gate"]["total"] == 1

    def test_empty_dir_returns_empty_dict(self, hook_logs_dir):
        since = datetime(2026, 5, 19) - timedelta(days=7)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)
        assert stats == {}

    def test_per_day_breakdown_present(self, hook_logs_dir):
        now = datetime(2026, 5, 19, 12, 0, 0)
        (hook_logs_dir / "h1").mkdir()
        _make_liveness_entries(
            hook_logs_dir,
            "sess-1",
            [
                ("h1", now),
                ("h1", now - timedelta(days=1)),
                ("h1", now - timedelta(days=1)),
            ],
        )

        stats = hook_health.scan_logs(now - timedelta(days=7), logs_root=hook_logs_dir)

        assert "per_day" in stats["h1"]
        assert sum(stats["h1"]["per_day"].values()) == 3

    def test_merges_across_multiple_session_files(self, hook_logs_dir):
        """Liveness is one file per session_id — counts across sessions must
        merge, not just the latest/first session."""
        now = datetime(2026, 5, 19, 12, 0, 0)
        (hook_logs_dir / "h1").mkdir()
        _make_liveness_entries(hook_logs_dir, "sess-a", [("h1", now)])
        _make_liveness_entries(hook_logs_dir, "sess-b", [("h1", now)])

        stats = hook_health.scan_logs(now - timedelta(days=1), logs_root=hook_logs_dir)

        assert stats["h1"]["total"] == 2

    def test_malformed_liveness_line_skipped_not_crashed(self, hook_logs_dir):
        now = datetime(2026, 5, 19, 12, 0, 0)
        (hook_logs_dir / "h1").mkdir()
        liveness_dir = hook_logs_dir / "_liveness"
        liveness_dir.mkdir()
        path = liveness_dir / "sess-1.jsonl"
        path.write_text(
            "not json\n"
            + json.dumps({"hook": "h1", "session_id": "sess-1", "pid": 1, "ts": now.isoformat()})
            + "\n"
            + json.dumps({"hook": "h1", "pid": 1, "ts": "not-a-timestamp"})
            + "\n",
            encoding="utf-8",
        )

        stats = hook_health.scan_logs(now - timedelta(days=1), logs_root=hook_logs_dir)

        assert stats["h1"]["total"] == 1

    def test_liveness_dir_absent_falls_through_to_no_precise_count(self, hook_logs_dir):
        """No _liveness/ directory at all — every on-disk hook with legacy
        activity must degrade to no_precise_count, not error."""
        now = datetime(2026, 5, 19, 12, 0, 0)
        _make_log(hook_logs_dir, "h1", now, idx=0)

        stats = hook_health.scan_logs(now - timedelta(days=1), logs_root=hook_logs_dir)

        assert stats["h1"] == {"total": 0, "per_day": {}, "no_precise_count": True}


# ---------------------------------------------------------------------------
# scan_logs — hooks without _liveness records ("no_precise_count")
# ---------------------------------------------------------------------------

class TestNoPreciseCountFallback:
    def test_on_disk_legacy_activity_without_liveness_is_flagged_not_counted(
        self, hook_logs_dir
    ):
        """Regression guard for the bug this fixes: a hook with real legacy
        log activity but zero _liveness records (not yet migrated to
        run_hook_safely) must NOT fall back to the line/file count — it
        must be explicitly labelled no_precise_count with total=0."""
        now = datetime(2026, 8, 21, 9, 0, 0)
        for i in range(5):
            _make_log(hook_logs_dir, "legacy-only-hook", now - timedelta(hours=i), idx=i)

        since = now - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["legacy-only-hook"]["no_precise_count"] is True
        assert stats["legacy-only-hook"]["total"] == 0

    def test_on_disk_daily_activity_without_liveness_is_flagged_not_counted(
        self, hook_logs_dir
    ):
        today = datetime(2026, 8, 21, 9, 0, 0)
        record_times = [today + timedelta(minutes=i) for i in range(5)]
        _make_daily_log(hook_logs_dir, "daily-only-hook", today, record_times)

        since = today - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["daily-only-hook"]["no_precise_count"] is True
        assert stats["daily-only-hook"]["total"] == 0

    def test_no_activity_from_either_source_is_omitted(self, hook_logs_dir):
        (hook_logs_dir / "quiet-hook").mkdir()

        since = datetime(2026, 8, 21) - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert "quiet-hook" not in stats

    def test_liveness_hook_takes_priority_over_stale_on_disk_activity(self, hook_logs_dir):
        """A hook migrated to run_hook_safely has both liveness records and
        (from before migration) leftover legacy files in window — liveness
        must win, not be shadowed by the on-disk diagnostic scan."""
        now = datetime(2026, 8, 21, 9, 0, 0)
        _make_log(hook_logs_dir, "migrated-hook", now, idx=0)
        _make_liveness_entries(hook_logs_dir, "sess-1", [("migrated-hook", now)])

        since = now - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["migrated-hook"] == {"total": 1, "per_day": {"2026-08-21": 1}}


# ---------------------------------------------------------------------------
# scan_logs — on-disk log dir scan retained for diagnostics only
# ---------------------------------------------------------------------------

class TestScanLogsDailyFormatDiagnosticOnly:
    def test_daily_format_content_no_longer_drives_total(self, hook_logs_dir):
        """Historical regression guard (now superseded): daily-rotated file
        content lines are read for diagnostics only — they must not appear
        as the returned total once no_precise_count applies."""
        today = datetime(2026, 8, 21, 9, 0, 0)
        record_times = [today + timedelta(minutes=i) for i in range(5)]
        _make_daily_log(hook_logs_dir, "acceptance-gate", today, record_times)

        since = today - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert stats["acceptance-gate"]["no_precise_count"] is True
        assert stats["acceptance-gate"]["total"] != 5

    def test_hook_dir_vanishing_mid_scan_does_not_crash(self, hook_logs_dir, monkeypatch):
        """Concurrent cleanup (e.g. another process rm -rf-ing a hook's log
        dir) between the top-level listing and the diagnostic per-dir scan
        must not crash scan_logs — observed live via manual dogfooding."""
        now = datetime(2026, 8, 21, 12, 0, 0)
        _make_daily_log(hook_logs_dir, "vanishing-hook", now, [now])
        _make_daily_log(hook_logs_dir, "stable-hook", now, [now, now])
        _make_liveness_entries(hook_logs_dir, "sess-1", [("stable-hook", now), ("stable-hook", now)])

        real_scan_hook_dir = hook_health._scan_hook_dir

        def _flaky_scan(hook_dir_path, since, logger):
            if "vanishing-hook" in hook_dir_path:
                raise FileNotFoundError(2, "No such file or directory", hook_dir_path)
            return real_scan_hook_dir(hook_dir_path, since, logger)

        monkeypatch.setattr(hook_health, "_scan_hook_dir", _flaky_scan)

        since = now - timedelta(days=1)
        stats = hook_health.scan_logs(since, logs_root=hook_logs_dir)

        assert "vanishing-hook" not in stats
        assert stats["stable-hook"]["total"] == 2


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

    def test_posttooluse_registration_is_high_freq(self):
        # 0.2.1-W3-936: any non-SessionStart registered event scales with
        # conversation-turn activity, not "meaningful state changes" — this
        # replaced the previous PostToolUse-defaults-low assumption after
        # dogfooding showed PostToolUse/PreToolUse Bash hooks alike can hit
        # thousands/day on an active dev day.
        settings = self._settings_with("PostToolUse", "acceptance-gate")
        cls = hook_health.classify_hook("acceptance-gate", settings)
        assert cls == "high_freq_ok"

    def test_pretooluse_bash_registration_is_high_freq(self):
        settings = self._settings_with("PreToolUse", "acceptance-gate")
        cls = hook_health.classify_hook("acceptance-gate", settings)
        assert cls == "high_freq_ok"

    def test_subagentstop_registration_is_high_freq(self):
        settings = self._settings_with("SubagentStop", "agent-commit-verification-hook")
        cls = hook_health.classify_hook("agent-commit-verification-hook", settings)
        assert cls == "high_freq_ok"

    def test_hook_name_without_trailing_hook_suffix_still_matches(self):
        # settings.json command stem is "agent-commit-verification-hook";
        # hook-logs/ subdirectory name is inconsistent about the "-hook"
        # suffix (e.g. "acceptance-gate" has none, this one does) — both
        # forms must resolve to the same registration.
        settings = self._settings_with("SubagentStop", "agent-commit-verification-hook")
        cls = hook_health.classify_hook("agent-commit-verification", settings)
        assert cls == "high_freq_ok"

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

def _full_week_per_day(start_day=10, count=3):
    """7 distinct days of low, non-triggering activity (0.2.1-W3-933:
    evaluate() now derives coverage_days from len(per_day), so relative-
    baseline tests must supply >= BASELINE_MIN_COVERAGE_DAYS distinct days
    or they get redirected into the bootstrap path)."""
    return {"2026-05-{:02d}".format(start_day + i): count for i in range(7)}


class TestEvaluate:
    def test_normal_when_under_baseline(self):
        stats = {"total": 30, "recent": 10, "per_day": _full_week_per_day()}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=20.0)
        assert verdict.status == "normal"
        assert verdict.bootstrap is False

    def test_warning_when_recent_exceeds_baseline_times_N(self):
        # low_freq N=2 → recent 50 > baseline 20 * 2 = 40 → warning
        stats = {"total": 200, "recent": 50, "per_day": _full_week_per_day()}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=20.0)
        assert verdict.status == "warning"
        assert verdict.bootstrap is False

    def test_high_freq_uses_N3(self):
        # high_freq N=3 → recent 50 vs baseline 20*3=60 → normal
        stats = {"total": 200, "recent": 50, "per_day": _full_week_per_day()}
        verdict = hook_health.evaluate(stats, hook_type="high_freq_ok", baseline=20.0)
        assert verdict.status == "normal"
        assert verdict.bootstrap is False

    def test_critical_when_3_consecutive_days_exceed(self):
        # 7 distinct days (coverage sufficient) with the last 3 consecutive
        # exceeding threshold = baseline(10) * multiplier(2) = 20.
        baseline = 10.0
        per_day = {
            "2026-05-13": 5,
            "2026-05-14": 5,
            "2026-05-15": 5,
            "2026-05-16": 5,
            "2026-05-17": 30,  # > 10*2
            "2026-05-18": 35,
            "2026-05-19": 40,
        }
        stats = {"total": sum(per_day.values()), "recent": 40, "per_day": per_day}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=baseline)
        assert verdict.status == "critical"
        assert verdict.bootstrap is False

    def test_verdict_contains_diagnostic_fields(self):
        stats = {"total": 200, "recent": 50, "per_day": _full_week_per_day()}
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

    def test_high_freq_bootstrap_uses_higher_threshold(self):
        # 0.2.1-W3-936: high_freq_ok hooks (e.g. PreToolUse:Bash) can hit
        # thousands/day; 150 must stay "normal" under the high_freq_ok
        # bootstrap ceiling even though it would warn under low_freq_expected
        # (see test_bootstrap_warning_when_over_absolute_threshold above).
        stats = {"total": 150, "recent": 150, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="high_freq_ok", baseline=0.0)
        assert verdict.status == "normal"
        assert verdict.bootstrap is True

    def test_high_freq_bootstrap_still_warns_above_its_own_ceiling(self):
        stats = {"total": 9000, "recent": 9000, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="high_freq_ok", baseline=0.0)
        assert verdict.status == "warning"
        assert verdict.bootstrap is True

    def test_unknown_hook_type_falls_back_to_absolute_threshold(self):
        stats = {"total": 150, "recent": 150, "per_day": {}}
        verdict = hook_health.evaluate(stats, hook_type="not_a_real_type", baseline=0.0)
        assert verdict.status == "warning"
        assert verdict.bootstrap is True


# ---------------------------------------------------------------------------
# Insufficient coverage → forced bootstrap (0.2.1-W3-933)
#
# baseline = sum(per_day) / 7 (fixed 7-day denominator) deflates whenever
# actual log coverage is under 7 days: the numerator grows with real data
# while the denominator stays fixed, making `recent > baseline*N` vacuously
# true for any recent > 0. Trigger conditions are not limited to a one-time
# post-cleanup event — new projects, hooks in their first few days, and
# genuinely low-frequency hooks with sparse (non-consecutive) activity
# inside the 7-day retention window all hit the same deflation.
# ---------------------------------------------------------------------------

class TestInsufficientCoverage:
    def test_single_day_data_forces_bootstrap_no_false_warning(self):
        # 清理後單日資料重現：per_day 僅 1 天，naive baseline = 81/7 ≈ 11.6
        # 會使 recent(81) > baseline*2 恆真；修正後改走 bootstrap（81 < 100
        # 絕對閾值 → normal）。
        per_day = {"2026-08-21": 81}
        stats = {"total": 81, "recent": 81, "per_day": per_day}
        naive_baseline = sum(per_day.values()) / 7.0
        verdict = hook_health.evaluate(
            stats, hook_type="low_freq_expected", baseline=naive_baseline
        )
        assert verdict.status == "normal"
        assert verdict.bootstrap is True
        assert any("資料不足" in r for r in verdict.reasons)

    def test_low_freq_hook_two_sparse_days_within_seven_day_window(self):
        # 低頻 hook 在 7 天保留期內僅 2 天有資料（非連續）：新專案或新 hook
        # 頭幾天常見的形態，非清理後的一次性現象。
        per_day = {"2026-08-15": 5, "2026-08-21": 6}
        stats = {"total": 11, "recent": 6, "per_day": per_day}
        naive_baseline = sum(per_day.values()) / 7.0
        verdict = hook_health.evaluate(
            stats, hook_type="low_freq_expected", baseline=naive_baseline
        )
        assert verdict.status == "normal"
        assert verdict.bootstrap is True
        assert any("資料不足 2 天" in r for r in verdict.reasons)

    def test_six_day_coverage_still_forces_bootstrap(self):
        # 邊界：6 天（< BASELINE_MIN_COVERAGE_DAYS=7）仍走 bootstrap。
        per_day = {"2026-08-{:02d}".format(d): 5 for d in range(15, 21)}
        stats = {"total": 30, "recent": 30, "per_day": per_day}
        verdict = hook_health.evaluate(
            stats, hook_type="low_freq_expected", baseline=30 / 7.0
        )
        assert verdict.bootstrap is True

    def test_seven_day_coverage_uses_relative_baseline_unchanged(self):
        # 邊界：滿 7 天恢復既有相對基線判定，行為不變。
        per_day = {"2026-08-{:02d}".format(d): 5 for d in range(15, 22)}
        stats = {"total": 35, "recent": 50, "per_day": per_day}
        verdict = hook_health.evaluate(stats, hook_type="low_freq_expected", baseline=5.0)
        assert verdict.status == "warning"  # recent 50 > baseline*2=10
        assert verdict.bootstrap is False


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
