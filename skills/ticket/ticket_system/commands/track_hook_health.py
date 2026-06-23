"""
ticket track hook-health 命令（W13-018 落地，源自 W13-008 IMP-3）

提供 PM 手動觸發 Hook 觸發頻率掃描與評估的 CLI，補強 W13-017 SessionStart
被動掃描的主動性（W13-008 方案 F：被動 + 主動雙軌）。

設計約束：
- version-agnostic（不需 active version；操作對象為 .claude/hook-logs/）
- 復用 W13-016 lib.hook_health 純函式（scan_logs / classify_hook / evaluate）
- 與 W13-017 hook-health-monitor.py 共用 baseline 邏輯（per_day sum / window_days）
- 預設 --since 7 天；--format table（PM 預設視圖）/ json（自動化消費）
- --dry-run 為契約點：本命令本即不寫入 ticket / 檔案；旗標明示「禁止副作用」

複用既有：
- .claude/lib/hook_health.py（scan_logs / classify_hook / evaluate / Verdict）
  經 lifecycle.py 同款 lazy sys.path.insert 模式引入

不複用：
- hook-health-monitor.run_frequency_scan：該函式 hook 內部用，混合 stderr 輸出 +
  ticket 建議；本命令需 stdout 結構化輸出（table/json），故另寫薄渲染層。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Lib 載入：lazy import + 多策略 project root 偵測
#
# 設計考量：全局 uv tool install 後，本檔位於 site-packages，
# Path(__file__).parents[4] 不再指向 .claude/。需用以下優先序：
#   1. $CLAUDE_PROJECT_DIR 環境變數（Claude Code runtime 提供）
#   2. cwd 向上找含 .claude/lib/hook_health.py 的目錄
#   3. Path(__file__).parents[4]（dev 模式 / 局部執行 fallback）
# 任一策略命中即將 hooks 目錄加入 sys.path 後 import。
# 測試使用 patch("ticket_system.commands.track_hook_health.scan_logs") 覆寫，
# 故 lazy resolve 不影響 unit test。
# ---------------------------------------------------------------------------

_HOOK_HEALTH_MODULE = None  # 快取避免重複載入


def _find_claude_dir() -> Optional[Path]:
    """依優先序定位 .claude/ 目錄。"""
    # 1. 環境變數
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        candidate = Path(env_root) / ".claude"
        if (candidate / "lib" / "hook_health.py").is_file():
            return candidate

    # 2. cwd 向上搜
    for d in [Path.cwd(), *Path.cwd().parents]:
        candidate = d / ".claude"
        if (candidate / "lib" / "hook_health.py").is_file():
            return candidate

    # 3. 開發環境 fallback：本檔在 .claude/skills/ticket/ticket_system/commands/
    try:
        dev_candidate = Path(__file__).resolve().parents[4]
        if (dev_candidate / "lib" / "hook_health.py").is_file():
            return dev_candidate
    except (IndexError, OSError):
        pass

    return None


def _load_hook_health():
    """Lazy 載入 .claude/lib/hook_health（首次呼叫時 import + 快取）。"""
    global _HOOK_HEALTH_MODULE
    if _HOOK_HEALTH_MODULE is not None:
        return _HOOK_HEALTH_MODULE

    claude_dir = _find_claude_dir()
    if claude_dir is None:
        raise RuntimeError(
            "Cannot locate .claude/lib/hook_health.py; "
            "set CLAUDE_PROJECT_DIR or run from within the project tree."
        )

    if str(claude_dir) not in sys.path:
        sys.path.insert(0, str(claude_dir))
    from lib import hook_health  # noqa: WPS433

    _HOOK_HEALTH_MODULE = hook_health
    return hook_health


def scan_logs(since: datetime, logs_root: Optional[Path] = None) -> Dict[str, Dict]:
    """Thin wrapper：對外暴露 scan_logs 名稱以便測試 patch。"""
    return _load_hook_health().scan_logs(since=since, logs_root=logs_root)


def classify_hook(name: str, settings: Dict) -> str:
    return _load_hook_health().classify_hook(name, settings)


def evaluate(stats: Dict, hook_type: str, baseline: float):
    return _load_hook_health().evaluate(stats, hook_type, baseline)


# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

FORMAT_TABLE = "table"
FORMAT_JSON = "json"

DEFAULT_SINCE_DAYS = 7


# ---------------------------------------------------------------------------
# 評估邏輯（與 hook-health-monitor._compute_baseline 對齊）
# ---------------------------------------------------------------------------

def _compute_baseline(per_day: Dict[str, int], window_days: int = DEFAULT_SINCE_DAYS) -> float:
    """baseline = sum(per_day) / window_days。

    與 hook-health-monitor._compute_baseline 邏輯一致（W13-008 量化標準）。
    """
    if window_days <= 0:
        return 0.0
    total = sum(per_day.values())
    return total / float(window_days)


def _today_str(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")


def _evaluate_all(
    stats_by_hook: Dict[str, Dict],
    *,
    window_days: int,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """對每個 hook 跑 classify + evaluate，回傳結構化結果清單。"""
    today = _today_str(now)
    results: List[Dict[str, Any]] = []
    for hook_name, stats in sorted(stats_by_hook.items()):
        per_day = stats.get("per_day") or {}
        recent = per_day.get(today, 0)
        baseline = _compute_baseline(per_day, window_days=window_days)
        hook_type = classify_hook(hook_name, {})
        verdict = evaluate(
            stats={"total": stats.get("total", 0), "recent": recent, "per_day": per_day},
            hook_type=hook_type,
            baseline=baseline,
        )
        results.append({
            "hook": hook_name,
            "type": hook_type,
            "status": verdict.status,
            "recent": verdict.recent,
            "baseline": round(verdict.baseline, 2),
            "multiplier": verdict.multiplier,
            "bootstrap": verdict.bootstrap,
            "reasons": list(verdict.reasons or []),
            "total_in_window": stats.get("total", 0),
        })
    return results


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _render_table(
    results: List[Dict[str, Any]],
    *,
    since_days: int,
    dry_run: bool,
) -> str:
    lines: List[str] = []
    header = f"=== Hook Health (since {since_days}d) ==="
    if dry_run:
        header += " [dry-run]"
    lines.append(header)
    lines.append("")

    if not results:
        lines.append("(無 hook-logs 資料；可能尚未產生任何 hook log)")
        return "\n".join(lines)

    # 簡易固定寬度表格（純文字，避免引入外部依賴）
    col_hook = max(len("hook"), max(len(r["hook"]) for r in results))
    col_status = max(len("status"), max(len(r["status"]) for r in results))
    col_type = max(len("type"), max(len(r["type"]) for r in results))

    fmt = "  {hook:<{w_hook}}  {status:<{w_status}}  {type:<{w_type}}  {recent:>6}  {baseline:>8.2f}  x{mult}"
    head = "  {hook:<{w_hook}}  {status:<{w_status}}  {type:<{w_type}}  {rcol:>6}  {bcol:>8}  {mcol}".format(
        hook="hook",
        status="status",
        type="type",
        rcol="recent",
        bcol="baseline",
        mcol="mult",
        w_hook=col_hook,
        w_status=col_status,
        w_type=col_type,
    )
    lines.append(head)
    lines.append("  " + "-" * (col_hook + col_status + col_type + 32))
    for r in results:
        lines.append(fmt.format(
            hook=r["hook"],
            status=r["status"],
            type=r["type"],
            recent=r["recent"],
            baseline=r["baseline"],
            mult=r["multiplier"],
            w_hook=col_hook,
            w_status=col_status,
            w_type=col_type,
        ))
        if r["reasons"]:
            lines.append("      reasons: " + "; ".join(r["reasons"]))

    flagged = [r for r in results if r["status"] in ("warning", "critical")]
    lines.append("")
    if flagged:
        lines.append(
            f"  {len(flagged)} hook(s) flagged。建議：ticket track create --type ANA "
            "--who basil-hook-architect ..."
        )
    else:
        lines.append("  all hooks normal")
    return "\n".join(lines)


def _render_json(
    results: List[Dict[str, Any]],
    *,
    since_days: int,
    dry_run: bool,
) -> str:
    payload = {
        "since_days": since_days,
        "dry_run": dry_run,
        "results": results,
        "flagged_count": sum(
            1 for r in results if r["status"] in ("warning", "critical")
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def execute_hook_health(args: argparse.Namespace) -> int:
    """執行 track hook-health 命令（version-agnostic）。

    Returns:
        0: 正常輸出（含 flagged）
        2: 參數錯誤（--since 非正整數）
    """
    since_days = getattr(args, "since", DEFAULT_SINCE_DAYS) or DEFAULT_SINCE_DAYS
    fmt = getattr(args, "format", FORMAT_TABLE) or FORMAT_TABLE
    dry_run = bool(getattr(args, "dry_run", False))

    if since_days <= 0:
        sys.stderr.write("--since must be positive integer\n")
        return 2

    since_dt = datetime.now() - timedelta(days=since_days)
    stats_by_hook = scan_logs(since=since_dt)
    results = _evaluate_all(stats_by_hook, window_days=since_days)

    if fmt == FORMAT_JSON:
        print(_render_json(results, since_days=since_days, dry_run=dry_run))
    else:
        print(_render_table(results, since_days=since_days, dry_run=dry_run))
    return 0


# execute alias 對齊 track.py 命名慣例
execute = execute_hook_health


def register_hook_health(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 hook-health 子命令 parser。"""
    p = subparsers.add_parser(
        "hook-health",
        help=(
            "掃描 .claude/hook-logs/ 評估 Hook 觸發頻率，"
            "復用 W13-016 lib.hook_health（PM 手動觸發補強 W13-017 被動掃描）"
        ),
    )
    p.add_argument(
        "--since",
        type=int,
        default=DEFAULT_SINCE_DAYS,
        help=f"掃描窗口天數（預設 {DEFAULT_SINCE_DAYS}）",
    )
    p.add_argument(
        "--format",
        choices=[FORMAT_TABLE, FORMAT_JSON],
        default=FORMAT_TABLE,
        help=f"輸出格式（預設 {FORMAT_TABLE}）",
    )
    p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="明示禁止任何副作用（本命令本即無副作用，此旗標為契約點）",
    )
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
