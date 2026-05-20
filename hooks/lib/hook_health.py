"""Hook health monitoring core engine (W13-016, derived from W13-008).

Pure-function library providing log aggregation, classification, and
relative-baseline evaluation for hook trigger frequencies.

Design principles:
- Pure stdlib (pathlib + datetime), Python 3.9 compatible
- 2-class coarse classification (high_freq_ok / low_freq_expected)
- Relative baseline (recent vs 7-day avg * N), N=2 default / N=3 for high_freq
- Bootstrap fallback: absolute lower bound 100/day when no history
- No side effects (file writes / subprocess / ticket creation) — caller
  decides observability surface (stderr / CLI / hook)

Consumed by:
- .claude/hooks/hook-health-monitor.py (SessionStart hook, W13-017)
- .claude/skills/ticket/ticket_system/cli.py hook-health subcommand (W13-018)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Bootstrap absolute lower bound when no 7-day baseline available (1 hit/day
# conservative threshold; documented in W13-008 Solution §Bootstrap).
BOOTSTRAP_ABSOLUTE_THRESHOLD = 100

# Multiplier N by hook class — see W13-008 量化標準 table.
MULTIPLIER_BY_TYPE = {
    "high_freq_ok": 3,
    "low_freq_expected": 2,
}

# Hook names classified as high_freq_ok by design intent. Conservative list;
# anything not in this set falls back to low_freq_expected (default).
# Extending the set requires WRAP-like review (W13-008 §觸發判定).
HIGH_FREQ_HOOK_PATTERNS = (
    "phase4-decision-enforcement",
    "wrap-decision-tripwire",
    "wrap-decision",
)

# Log file naming pattern: <hook-name>-YYYYMMDD-HHMMSS[-extra].log
# Used as a sanity guard when extracting the hook directory name.
_LOG_FILE_RE = re.compile(r".*-\d{8}-\d{6}.*\.log$")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Verdict:
    """Evaluation result for a single hook."""

    status: str  # "normal" | "warning" | "critical"
    recent: int
    baseline: float
    multiplier: int
    bootstrap: bool = False
    reasons: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# scan_logs
# ---------------------------------------------------------------------------

def scan_logs(since: datetime, logs_root: Optional[Path] = None) -> Dict[str, Dict]:
    """Aggregate hook-logs/ stats since the given timestamp.

    Args:
        since: Only files with mtime >= since are counted.
        logs_root: Override .claude/hook-logs/ root (testing).

    Returns:
        dict mapping hook_name -> {"total": int, "per_day": {date_str: count}}.
    """
    if logs_root is None:
        # Default: <repo>/.claude/hook-logs (lib lives at .claude/hooks/lib/)
        logs_root = Path(__file__).resolve().parents[2] / "hook-logs"

    stats: Dict[str, Dict] = {}
    if not logs_root.exists():
        return stats

    since_ts = since.timestamp()

    for hook_dir in sorted(logs_root.iterdir()):
        if not hook_dir.is_dir():
            continue
        hook_name = hook_dir.name
        # Skip aux dirs like "_sampling" (leading underscore convention).
        if hook_name.startswith("_"):
            continue

        per_day: Dict[str, int] = {}
        total = 0
        for f in hook_dir.iterdir():
            if not f.is_file() or not f.name.endswith(".log"):
                continue
            mtime = f.stat().st_mtime
            if mtime < since_ts:
                continue
            day_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            per_day[day_str] = per_day.get(day_str, 0) + 1
            total += 1

        if total > 0:
            stats[hook_name] = {"total": total, "per_day": per_day}

    return stats


# ---------------------------------------------------------------------------
# classify_hook
# ---------------------------------------------------------------------------

def classify_hook(name: str, settings: Dict) -> str:
    """Coarse 2-class classification for a hook by name.

    Returns "high_freq_ok" for PreToolUse decision/quality hooks (phase4-*,
    wrap-decision-*); otherwise "low_freq_expected".

    Args:
        name: Hook short name (matches hook-logs/ subdirectory name).
        settings: Parsed .claude/settings.json content (currently used as
            existence check — future extensions may inspect event types).
    """
    for pattern in HIGH_FREQ_HOOK_PATTERNS:
        if pattern in name:
            return "high_freq_ok"
    return "low_freq_expected"


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

def evaluate(stats: Dict, hook_type: str, baseline: float) -> Verdict:
    """Decide normal/warning/critical based on relative baseline (or bootstrap).

    Args:
        stats: {"total": int, "recent": int, "per_day": {date_str: count}}
        hook_type: "high_freq_ok" or "low_freq_expected"
        baseline: 7-day average per day. 0.0 triggers bootstrap path.

    Returns:
        Verdict with status, recent, baseline, multiplier, bootstrap flag.
    """
    recent = int(stats.get("recent", 0))
    per_day = stats.get("per_day") or {}
    multiplier = MULTIPLIER_BY_TYPE.get(hook_type, 2)

    # Bootstrap path: no 7-day history → absolute lower bound.
    if baseline <= 0.0:
        status = "warning" if recent > BOOTSTRAP_ABSOLUTE_THRESHOLD else "normal"
        reasons = []
        if status == "warning":
            reasons.append(
                "bootstrap: recent {r} > absolute {a}/day".format(
                    r=recent, a=BOOTSTRAP_ABSOLUTE_THRESHOLD
                )
            )
        return Verdict(
            status=status,
            recent=recent,
            baseline=baseline,
            multiplier=multiplier,
            bootstrap=True,
            reasons=reasons,
        )

    threshold = baseline * multiplier
    reasons: List[str] = []

    # Critical: 3 consecutive days above threshold (W13-008 §觸發判定 升級訊號)
    if _has_3_consecutive_over(per_day, threshold):
        reasons.append(
            "3+ consecutive days exceeded baseline*{n}={t:.1f}".format(
                n=multiplier, t=threshold
            )
        )
        return Verdict(
            status="critical",
            recent=recent,
            baseline=baseline,
            multiplier=multiplier,
            reasons=reasons,
        )

    if recent > threshold:
        reasons.append(
            "recent {r} > baseline*{n}={t:.1f}".format(
                r=recent, n=multiplier, t=threshold
            )
        )
        return Verdict(
            status="warning",
            recent=recent,
            baseline=baseline,
            multiplier=multiplier,
            reasons=reasons,
        )

    return Verdict(
        status="normal",
        recent=recent,
        baseline=baseline,
        multiplier=multiplier,
    )


def _has_3_consecutive_over(per_day: Dict[str, int], threshold: float) -> bool:
    """Return True if per_day contains 3+ consecutive calendar days over threshold."""
    if not per_day:
        return False
    # Parse dates and sort chronologically.
    dated: List[tuple] = []
    for day_str, count in per_day.items():
        try:
            d = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        dated.append((d, count))
    dated.sort()

    streak = 0
    prev_date = None
    for d, count in dated:
        over = count > threshold
        if not over:
            streak = 0
            prev_date = d
            continue
        if prev_date is not None and (d - prev_date) == timedelta(days=1):
            streak += 1
        else:
            streak = 1
        prev_date = d
        if streak >= 3:
            return True
    return False


# ---------------------------------------------------------------------------
# read_session_marker
# ---------------------------------------------------------------------------

def read_session_marker(marker_path: Optional[Path] = None) -> Optional[datetime]:
    """Read .claude/state/last-session-start.marker (ISO timestamp).

    Returns None if file missing or content not parseable. Caller decides how
    to handle absence (typical: fall back to since=7d for scan_logs).
    """
    if marker_path is None:
        marker_path = (
            Path(__file__).resolve().parents[2]
            / "state"
            / "last-session-start.marker"
        )
    if not marker_path.exists():
        return None
    try:
        content = marker_path.read_text(encoding="utf-8").strip()
        return datetime.fromisoformat(content)
    except (ValueError, OSError):
        return None
