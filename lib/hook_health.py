"""Hook health monitoring core engine (W13-016, derived from W13-008).

Pure-function library providing log aggregation, classification, and
relative-baseline evaluation for hook trigger frequencies.

Design principles:
- Pure stdlib (pathlib + datetime), Python 3.9 compatible
- 2-class coarse classification (high_freq_ok / low_freq_expected)
- Relative baseline (recent vs 7-day avg * N), N=2 default / N=3 for high_freq
- Bootstrap fallback: absolute lower bound 100/day when no history, OR when
  log coverage is under BASELINE_MIN_COVERAGE_DAYS (see evaluate() below —
  fixes a false-WARNING regression: baseline = sum(per_day)/7 with < 7 days
  of data deflates the denominator while recent stays at the numerator's
  full value, making `recent > baseline*N` vacuously true whenever recent>0)
- No side effects (file writes / subprocess / ticket creation) — caller
  decides observability surface (stderr / CLI / hook)

Consumed by:
- .claude/hooks/hook-health-monitor.py (SessionStart hook, W13-017)
- .claude/skills/ticket/ticket_system/cli.py hook-health subcommand (W13-018)

scan_logs() 對 .claude/hook-logs（667k 檔累積，最大單目錄 32k 檔）逐檔 os.stat()
曾造成 86.4s 端到端耗時（SessionStart hook 逐 session 卡住）。改為純檔名時間戳
解析（"<hook>-YYYYMMDD-HHMMSS[-extra].log"），完全不呼叫 stat()。

setup_hook_logging 的寫入策略（2026-08-21 起）已改為每日輪替 append
（"<hook>-YYYYMMDD.log"，同日多次觸發 append 至同檔）。這使「檔案數」與
「觸發次數」脫鉤——保留期內檔案數恆為 7（每日一檔），若沿用舊版「一檔=一次
觸發」的計數方式會全面失真且不報錯。

曾一度改為以「日檔內符合行首時間戳前綴的行數」作觸發次數代理，但同儕實測
發現行數 != 次數（一次觸發常產生多行日誌，如 DEBUG 執行時間行、WARNING
診斷行各自獨立成行），倍率因 hook 而異且不可預測（hook-health-monitor
90.2 行/次、acceptance-gate 24.7 行/次、bare-commit-guard 2.1 行/次）；
monitor 甚至把自己的 80 筆 WARNING 算成 504 次觸發並回報自己異常（自指
失真）。現改為：觸發次數的唯一權威來源是
`.claude/hook-logs/_liveness/<session_id>.jsonl`——
`hook_logging.run_hook_safely` 在呼叫 `main_func` 前無條件透過
`mark_hook_entry` 寫入一筆 `{"hook", "session_id", "pid", "ts"}` 記錄，語意
上「一次觸發 = 一筆記錄」精確成立，不受日誌行數倍率影響。`scan_logs()` 改
由 `_scan_liveness()` 讀取全部 `_liveness/*.jsonl`（跨 session 合併）作為
`total`/`per_day` 的計數來源；舊格式與新格式日檔（`_scan_hook_dir()` /
`_count_daily_file_lines()`）保留供 staleness 判定與內容診斷用途，不再
是計數依據。尚未遷移至 `run_hook_safely`（即無 `_liveness` 記錄）的 hook，
一律標註 `no_precise_count: True`（`total=0`），不回退成行數估計——寧可
明確「無精確計數」，也不用已知失真的代理值。

單目錄檔案數超過 MAX_FILES_PER_DIR 時（僅適用舊格式，新格式保留期內固定
7 檔不會觸發）改採樣估計並記錄 WARNING（經 logger 參數，caller 決定輸出面）
——此路徑僅影響診斷輸出，不再影響 scan_logs() 回傳的計數。

「最近一次觸發時點」的判定來源：hook-health-monitor.py::_newest_file_mtime
沿用檔案系統 mtime（非檔名解析），append 模式下每次寫入都會更新該檔 mtime，
故「目錄內最新檔案 mtime」在新格式下語意仍等價於「最近一次觸發時間」（原
docstring 描述的「退化為當日最後一次寫入」風險未發生——新格式本就是 append
至同一天檔案，mtime 本身即反映最後一次寫入即最後一次觸發，不需修改；該函式
不在本票 where.files 範圍，僅在此記錄決策依據）。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from logging import Logger
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Bootstrap absolute lower bound when no 7-day baseline available (1 hit/day
# conservative threshold; documented in W13-008 Solution §Bootstrap).
# Kept as the low_freq_expected member of BOOTSTRAP_THRESHOLD_BY_TYPE below
# and as the fallback for any hook_type not present in that dict.
BOOTSTRAP_ABSOLUTE_THRESHOLD = 100

# Per-hook-type bootstrap absolute threshold. A single flat 100/day constant
# conflated two different magnitude populations: hooks that fire once per
# session (SessionStart-only, genuinely ~1/day) and hooks that fire once per
# tool-call/prompt/subagent-turn (everything else), which scale with session
# activity and were observed at 100-5250/day on an active multi-agent dev
# day (same root cause as the sum(per_day)/window_days bootstrap-coverage
# bug fixed earlier: one constant applied to populations of different
# magnitude). Assumed ranges, revisit if observed traffic approaches either
# ceiling:
#   - low_freq_expected: SessionStart-only hooks. Expected ~1/day per
#     session; values persistently above 100/day likely indicate rapid
#     session churn or a restart loop, still worth flagging.
#   - high_freq_ok: every other registered event (PreToolUse/PostToolUse of
#     any matcher, UserPromptSubmit, Stop, SubagentStop) — these scale with
#     conversation-turn volume, not with "meaningful state changes", so the
#     ceiling must clear a busy day's tool-call count. Set with ~50%
#     headroom above the highest single-hook count observed in this repo
#     during dogfooding (~5250/day). Values persistently above 8000/day
#     still merit investigation (e.g. an infinite retry loop).
BOOTSTRAP_THRESHOLD_BY_TYPE = {
    "high_freq_ok": 8000,
    "low_freq_expected": BOOTSTRAP_ABSOLUTE_THRESHOLD,
}

# Minimum days of per_day coverage required for the relative baseline
# (sum(per_day)/window_days) to be meaningful. Caller's window is currently
# 7 days (hook-health-monitor.py FREQUENCY_SCAN_WINDOW_DAYS); this module
# mirrors that value as its own bootstrap-policy constant since evaluate()
# must decide bootstrap-vs-relative purely from the per_day dict it
# receives, without depending on the caller's window constant: with < 7
# days of data, baseline = total/7 undercounts and `recent > baseline*N`
# is vacuously true whenever recent>0 — observed as a full-set false-WARNING
# regression right after a log-directory cleanup emptied all history.
BASELINE_MIN_COVERAGE_DAYS = 7

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

# Log file naming pattern (both formats): <hook-name>-YYYYMMDD[-HHMMSS[-extra]].log
# Used as a sanity guard when extracting the hook directory name.
_LOG_FILE_RE = re.compile(r".*-\d{8}(-\d{6})?.*\.log$")

# Legacy format: one file per trigger. Captures (YYYYMMDD, HHMMSS) from the
# filename without any stat() call — counting is "one matched file = one
# trigger", unchanged from the pre-daily-rotation design.
_LOG_TIMESTAMP_RE = re.compile(r"-(\d{8})-(\d{6})[^/]*\.log$")

# Current format: one file per day, append-mode (setup_hook_logging since
# 2026-08-21). Captures YYYYMMDD only — file-count no longer proxies
# trigger-count under this format; see _count_daily_file_lines().
_DAILY_LOG_FILE_RE = re.compile(r"-(\d{8})\.log$")

# Matches the leading timestamp of one log record line, per FILE_FORMAT /
# DATE_FORMAT in hook_logging.py ("[%(asctime)s] %(levelname)s - ...",
# "%Y-%m-%d %H:%M:%S"). Only lines with this prefix are counted as records —
# multi-line traceback continuations (logger.critical(tb_str)) lack the
# prefix and are intentionally skipped (undercounts exception paths, which
# are rare; this remains a frequency proxy, not an exact trigger count).
_LOG_LINE_TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
_LOG_LINE_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Per-directory sampling cap. Directories with more file entries than this
# are estimated (parse first N files, extrapolate) instead of fully parsed,
# to keep worst-case per-directory cost bounded (largest observed dir has
# 32k+ files). A WARNING is logged (via optional logger param) when this
# path triggers so operators know counts are estimates.
MAX_FILES_PER_DIR = 5000

# Liveness index subdirectory name — mirrors hook_logging.LIVENESS_SUBDIR.
# Not imported directly (hook_logging.py is read-only for this module per
# ticket where.files scope); kept as a local literal to avoid a runtime
# import dependency between two independently-testable lib modules.
LIVENESS_SUBDIR = "_liveness"


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

def _count_daily_file_lines(
    file_path: str, day_date, since: datetime, logger: Optional[Logger]
) -> int:
    """Count log-record lines in one daily-rotated (append-mode) log file.

    Streams the file line-by-line (`for line in f`) — never loads the whole
    file into a single in-memory string, keeping cost bounded for the
    16-30 MB/day worst case observed. Only lines matching _LOG_LINE_TS_RE
    (the FILE_FORMAT leading "[YYYY-MM-DD HH:MM:SS]" prefix) are counted;
    this is a deliberate proxy for "one trigger" — see module docstring for
    the undercounting caveat on exception/traceback lines.

    For the boundary day (day_date == since.date()), each line's own
    timestamp is parsed and compared against `since` so that partial-day
    filtering matches the same semantics as the legacy since_key filter.
    For any other day already known >= since.date() (caller-filtered before
    invocation), every matched record line counts — no per-line parsing.

    Malformed lines (fails timestamp parse) and unreadable files (OSError —
    e.g. permission denied, mid-write encoding glitch) are skipped/return 0
    rather than raising; this degrades to an undercount, never a fabricated
    value (quality-baseline 規則 4：異常不靜默消失，故仍走 logger.warning
    可觀察路徑而非純粹吞掉).

    Args:
        file_path: str path to the daily log file.
        day_date: date parsed from the filename (YYYYMMDD).
        since: caller's since datetime — only used for boundary-day filtering.
        logger: optional logger for read-failure WARNING.

    Returns:
        Count of matched record lines (0 on read failure).
    """
    only_from = since if day_date == since.date() else None
    count = 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                match = _LOG_LINE_TS_RE.match(line)
                if not match:
                    continue
                if only_from is not None:
                    try:
                        ts = datetime.strptime(match.group(1), _LOG_LINE_TIMESTAMP_FORMAT)
                    except ValueError:
                        continue
                    if ts < only_from:
                        continue
                count += 1
    except OSError as e:
        if logger is not None:
            logger.warning(
                "[hook_health] failed to read daily log {}: {}".format(file_path, e)
            )
        return 0
    return count


def _scan_hook_dir(hook_dir_path: str, since: datetime, logger: Optional[Logger]) -> Dict:
    """Aggregate one hook's log dir, handling legacy and daily-rotated formats.

    Legacy format (`<hook>-YYYYMMDD-HHMMSS[-extra].log`, one file per
    trigger): filename-timestamp only, no stat() call — unchanged from the
    pre-daily-rotation design. Filename timestamp is compared lexically
    against since_key ("YYYYMMDD-HHMMSS" strings sort correctly since the
    format is zero-padded and fixed-width).

    Daily format (`<hook>-YYYYMMDD.log`, append-mode): content is streamed
    and counted via _count_daily_file_lines(). Bounded to ~7 files/dir under
    the 7-day retention policy, so MAX_FILES_PER_DIR sampling does not apply
    to this format (transition-period legacy files can still be numerous
    and are the ones sampling protects against).

    Both formats' per-day counts are accumulated into the same result;
    legacy counts are extrapolated (sampling estimate) independently before
    merging, so mixing formats in one directory during the migration window
    does not skew the daily-format counts.

    Args:
        hook_dir_path: str path (avoids Path object overhead per call).
        since: lower bound (inclusive) — full datetime for daily-file
            boundary-day filtering; also used to derive since_key for
            legacy filename comparison.
        logger: optional logger for the sampling-estimate / read-failure
            WARNINGs.

    Returns:
        {"total": int, "per_day": {date_str: count}} (total=0 → caller drops).
    """
    daily_per_day: Dict[str, int] = {}
    legacy_per_day: Dict[str, int] = {}
    legacy_total_entries = 0
    legacy_parsed = 0

    since_key = since.strftime("%Y%m%d-%H%M%S")
    since_date = since.date()

    with os.scandir(hook_dir_path) as it:
        for entry in it:
            name = entry.name
            if not name.endswith(".log"):
                continue

            daily_match = _DAILY_LOG_FILE_RE.search(name)
            if daily_match:
                date_part = daily_match.group(1)
                try:
                    day_date = datetime.strptime(date_part, "%Y%m%d").date()
                except ValueError:
                    continue
                if day_date < since_date:
                    continue
                count = _count_daily_file_lines(entry.path, day_date, since, logger)
                if count > 0:
                    day_str = "{}-{}-{}".format(date_part[0:4], date_part[4:6], date_part[6:8])
                    daily_per_day[day_str] = daily_per_day.get(day_str, 0) + count
                continue

            legacy_match = _LOG_TIMESTAMP_RE.search(name)
            if not legacy_match:
                continue
            legacy_total_entries += 1
            if legacy_parsed >= MAX_FILES_PER_DIR:
                continue  # keep counting legacy_total_entries for the estimate ratio
            legacy_parsed += 1
            date_part, time_part = legacy_match.group(1), legacy_match.group(2)
            file_key = "{}-{}".format(date_part, time_part)
            if file_key < since_key:
                continue
            day_str = "{}-{}-{}".format(date_part[0:4], date_part[4:6], date_part[6:8])
            legacy_per_day[day_str] = legacy_per_day.get(day_str, 0) + 1

    if legacy_total_entries > MAX_FILES_PER_DIR and legacy_parsed > 0:
        ratio = legacy_total_entries / float(legacy_parsed)
        legacy_per_day = {d: int(round(c * ratio)) for d, c in legacy_per_day.items()}
        if logger is not None:
            logger.warning(
                "[hook_health] {} has {} legacy-format files (> {} cap); counts "
                "estimated from first {} sampled (ratio {:.2f}x)".format(
                    hook_dir_path, legacy_total_entries, MAX_FILES_PER_DIR,
                    legacy_parsed, ratio
                )
            )

    per_day: Dict[str, int] = dict(daily_per_day)
    for d, c in legacy_per_day.items():
        per_day[d] = per_day.get(d, 0) + c

    return {"total": sum(per_day.values()), "per_day": per_day}


def _scan_liveness(
    logs_root: Path, since: datetime, logger: Optional[Logger]
) -> Dict[str, Dict]:
    """Aggregate .claude/hook-logs/_liveness/*.jsonl into per-hook counts.

    Each line is one unconditional "entered main_func" record written by
    hook_logging.mark_hook_entry() — "one line = one trigger" holds exactly
    (unlike the daily-log-line proxy this replaces, which conflated
    incidental DEBUG/WARNING lines with trigger count). Multiple session
    files (one per session_id) are merged by summing per-hook per-day
    counts across all files — liveness is session-scoped at the file level,
    not at the aggregation level.

    Args:
        logs_root: .claude/hook-logs/ root (liveness lives at
            logs_root/_liveness/).
        since: lower bound (inclusive) — records with ts < since are
            excluded.
        logger: optional logger for read-failure WARNING.

    Returns:
        dict mapping hook_name -> {"total": int, "per_day": {date_str: count}}.
        Empty dict if the _liveness directory does not exist or has no
        session files.
    """
    liveness_dir = logs_root / LIVENESS_SUBDIR
    stats: Dict[str, Dict] = {}
    if not liveness_dir.exists():
        return stats

    try:
        with os.scandir(str(liveness_dir)) as it:
            session_files = [e.path for e in it if e.name.endswith(".jsonl")]
    except OSError as e:
        if logger is not None:
            logger.warning(
                "[hook_health] failed to list liveness dir {}: {}".format(
                    liveness_dir, e
                )
            )
        return stats

    for path in session_files:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    hook_name = entry.get("hook")
                    ts_str = entry.get("ts")
                    if not hook_name or not ts_str:
                        continue
                    try:
                        ts = datetime.fromisoformat(ts_str)
                    except ValueError:
                        continue
                    if ts < since:
                        continue
                    day_str = ts.strftime("%Y-%m-%d")
                    hook_stats = stats.setdefault(
                        hook_name, {"total": 0, "per_day": {}}
                    )
                    hook_stats["per_day"][day_str] = (
                        hook_stats["per_day"].get(day_str, 0) + 1
                    )
                    hook_stats["total"] += 1
        except OSError as e:
            if logger is not None:
                logger.warning(
                    "[hook_health] failed to read liveness file {}: {}".format(
                        path, e
                    )
                )
            continue

    return stats


def scan_logs(
    since: datetime,
    logs_root: Optional[Path] = None,
    logger: Optional[Logger] = None,
) -> Dict[str, Dict]:
    """Aggregate hook-logs/ trigger stats since the given timestamp.

    Trigger count source is `_liveness/*.jsonl` (one unconditional record
    per hook entry, written by hook_logging.mark_hook_entry — see module
    docstring). Per-hook log directories (legacy one-file-per-trigger and
    daily-rotated append formats) are scanned only as a diagnostic
    cross-check (staleness / content inspection via logger.debug) — they no
    longer feed `total`/`per_day`. A hook with on-disk log activity but no
    matching `_liveness` record (not yet migrated to run_hook_safely, or
    crashed before mark_hook_entry ran) is reported with
    `no_precise_count: True` and `total=0` rather than falling back to the
    known-inaccurate line-count proxy.

    Only the first level of logs_root/<hook_name>/ is scanned (no
    recursion); directories starting with "_" (e.g. _liveness) are excluded
    from the per-hook-dir walk since they are not per-hook log directories.

    Args:
        since: Lower bound (inclusive) for both liveness records and the
            diagnostic per-hook-dir scan.
        logs_root: Override .claude/hook-logs/ root (testing).
        logger: optional logger, used for the diagnostic cross-check note
            and read-failure WARNINGs (legacy sampling estimate, unreadable
            daily file, unreadable liveness file/dir).

    Returns:
        dict mapping hook_name -> {"total": int, "per_day": {date_str: count}}
        (liveness-backed hooks), or
        {"total": 0, "per_day": {}, "no_precise_count": True} (hooks with
        on-disk log activity but no liveness record in window). Hooks with
        neither liveness nor on-disk activity are omitted.
    """
    if logs_root is None:
        # Default: <repo>/.claude/hook-logs (lib lives at .claude/lib/)
        logs_root = Path(__file__).resolve().parents[1] / "hook-logs"

    stats: Dict[str, Dict] = {}
    if not logs_root.exists():
        return stats

    liveness_stats = _scan_liveness(logs_root, since, logger)

    with os.scandir(str(logs_root)) as it:
        hook_dirs = sorted(
            e.name for e in it if e.is_dir() and not e.name.startswith("_")
        )

    for hook_name in hook_dirs:
        live = liveness_stats.get(hook_name)
        if live is not None and live["total"] > 0:
            stats[hook_name] = {"total": live["total"], "per_day": live["per_day"]}
            continue

        hook_dir_path = os.path.join(str(logs_root), hook_name)
        try:
            diag = _scan_hook_dir(hook_dir_path, since, logger)
        except (FileNotFoundError, NotADirectoryError) as e:
            # A concurrent cleanup process (e.g. a full hook-logs/ purge)
            # may remove this directory between the sorted() listing above
            # and this scan — observed live during dogfooding. Degrade by
            # skipping the hook (dir vanished mid-run == 0 recent triggers
            # observable), not crashing the whole scan.
            if logger is not None:
                logger.warning(
                    "[hook_health] {} vanished during scan (concurrent "
                    "cleanup?): {}".format(hook_dir_path, e)
                )
            continue

        if diag["total"] > 0:
            stats[hook_name] = {"total": 0, "per_day": {}, "no_precise_count": True}
            if logger is not None:
                logger.debug(
                    "[hook_health] {} has {} on-disk log-line(s) in window "
                    "but no _liveness record; reporting no_precise_count "
                    "instead of the line-count proxy".format(
                        hook_name, diag["total"]
                    )
                )
        # else: no activity in window from either source — omit (mirrors
        # the pre-existing drop-if-zero behaviour).

    # Hooks with liveness records but no on-disk hook-logs/<name>/ directory
    # at all (e.g. directory purged, or never wrote a legacy/daily file) are
    # still authoritative via liveness — include them too.
    for hook_name, live in liveness_stats.items():
        if hook_name not in stats and live["total"] > 0:
            stats[hook_name] = {"total": live["total"], "per_day": live["per_day"]}

    return stats


# ---------------------------------------------------------------------------
# classify_hook
# ---------------------------------------------------------------------------

def _hook_registered_events(name: str, settings: Dict) -> List[str]:
    """Return every settings.json event type this hook is registered under.

    Matches by exact command-filename stem (with and without a trailing
    "-hook" suffix, since hook-logs/ subdirectory names are inconsistent
    about including it — e.g. "acceptance-gate" vs
    "agent-commit-verification-hook"). Exact match only (no substring), to
    avoid one hook's name accidentally matching another's.

    Args:
        name: Hook short name (matches hook-logs/ subdirectory name).
        settings: Parsed .claude/settings.json content.

    Returns:
        List of event-type strings (e.g. ["PreToolUse", "SessionStart"]) for
        every settings.json registration matching this hook. Empty if the
        hook is not found (e.g. removed from settings.json but log dir
        still exists from before, or unit-test fixtures).
    """
    events: List[str] = []
    hooks_cfg = (settings or {}).get("hooks", {})
    for event, groups in hooks_cfg.items():
        for group in groups:
            for h in group.get("hooks", []):
                match = re.search(r"([\w-]+)\.py$", h.get("command", ""))
                if not match:
                    continue
                stem = match.group(1)
                stem_key = stem[:-5] if stem.endswith("-hook") else stem
                if stem == name or stem_key == name:
                    events.append(event)
    return events


def classify_hook(name: str, settings: Dict) -> str:
    """Coarse 2-class classification for a hook by name / registered event.

    Returns "high_freq_ok" for:
    - PreToolUse decision/quality hooks matched by name (phase4-*,
      wrap-decision-*) — legacy override, kept for hooks not resolvable via
      settings.json (e.g. removed from settings but log dir remains).
    - Any hook registered under a settings.json event other than
      SessionStart — PreToolUse/PostToolUse (any matcher), UserPromptSubmit,
      Stop, and SubagentStop hooks all fire proportional to
      conversation-turn activity (tool calls, prompts, subagent
      completions), not to "meaningful state changes"; SessionStart hooks
      fire once per session and are the only population where "~1/day" is a
      valid low-frequency assumption.

    Otherwise "low_freq_expected" (SessionStart-only hooks, and hooks not
    found in settings.json — conservative default).

    Args:
        name: Hook short name (matches hook-logs/ subdirectory name).
        settings: Parsed .claude/settings.json content.
    """
    for pattern in HIGH_FREQ_HOOK_PATTERNS:
        if pattern in name:
            return "high_freq_ok"
    events = _hook_registered_events(name, settings)
    if any(event != "SessionStart" for event in events):
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
        When log coverage (distinct days in per_day) is below
        BASELINE_MIN_COVERAGE_DAYS, this also forces the bootstrap path
        (regardless of baseline > 0) and prefixes reasons with a
        "資料不足 N 天，採 bootstrap 閾值" note — sum(per_day)/window_days
        deflates when the window has fewer than window_days of actual data,
        making the relative check vacuously true for any recent>0.
    """
    recent = int(stats.get("recent", 0))
    per_day = stats.get("per_day") or {}
    multiplier = MULTIPLIER_BY_TYPE.get(hook_type, 2)
    coverage_days = len(per_day)
    insufficient_coverage = coverage_days < BASELINE_MIN_COVERAGE_DAYS

    # Bootstrap path: no 7-day history, OR insufficient day-coverage to
    # trust the relative baseline → absolute lower bound, selected by
    # hook_type (see BOOTSTRAP_THRESHOLD_BY_TYPE docstring).
    if baseline <= 0.0 or insufficient_coverage:
        bootstrap_threshold = BOOTSTRAP_THRESHOLD_BY_TYPE.get(
            hook_type, BOOTSTRAP_ABSOLUTE_THRESHOLD
        )
        status = "warning" if recent > bootstrap_threshold else "normal"
        reasons = []
        if insufficient_coverage:
            reasons.append(
                "資料不足 {d} 天（< {m}），採 bootstrap 閾值".format(
                    d=coverage_days, m=BASELINE_MIN_COVERAGE_DAYS
                )
            )
        if status == "warning":
            reasons.append(
                "bootstrap: recent {r} > absolute {a}/day ({t})".format(
                    r=recent, a=bootstrap_threshold, t=hook_type
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
            Path(__file__).resolve().parents[1]
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
