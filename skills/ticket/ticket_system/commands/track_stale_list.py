"""
ticket track stale-list 命令（W17-200）

列舉 stale ticket 明細（pending status），補 list 命令僅顯示彙總計數
而無法定位個別 stale ticket 的缺口。

設計約束：
- version-agnostic（可選 --version / --wave / --all 過濾）
- 註冊於 track.py _create_version_agnostic_handlers() 字典
- 復用 lib/staleness.py calculate_stale_level 與閾值常數
- 預設 --threshold warning（warning + critical）；info / all 顯示三級；
  critical 僅 critical
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Dict, List, Optional

from ticket_system.constants import STATUS_PENDING
from ticket_system.lib.staleness import (
    LEVEL_CRITICAL,
    LEVEL_INFO,
    LEVEL_WARNING,
    calculate_stale_level,
)
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.version import get_active_versions


# 等級權重（用於 critical-only / warning+critical / info+ 篩選）
_LEVEL_RANK = {
    LEVEL_INFO: 1,
    LEVEL_WARNING: 2,
    LEVEL_CRITICAL: 3,
}

# 顯示用 label
_LEVEL_LABEL = {
    LEVEL_INFO: "info",
    LEVEL_WARNING: "warning",
    LEVEL_CRITICAL: "critical",
}


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------

def _min_rank_for_threshold(threshold: str) -> int:
    """依 --threshold 回傳允許納入的最低 level rank。

    - critical → 僅 critical（rank >= 3）
    - warning → warning + critical（rank >= 2）
    - info / all → 三級全收（rank >= 1）
    """
    if threshold == "critical":
        return _LEVEL_RANK[LEVEL_CRITICAL]
    if threshold in ("info", "all"):
        return _LEVEL_RANK[LEVEL_INFO]
    # 預設 / "warning"
    return _LEVEL_RANK[LEVEL_WARNING]


def _days_since_created(ticket: Dict, today: date) -> Optional[int]:
    """以 created 計算天數差（與 staleness.py 一致）；解析失敗回 None。"""
    from ticket_system.lib.staleness import _parse_created

    created = _parse_created(ticket.get("created"))
    if created is None:
        return None
    return (today - created).days


def _collect_stale(
    tickets: List[Dict],
    *,
    threshold: str,
    wave: Optional[int],
    today: date,
) -> List[Dict]:
    """過濾 pending stale ticket，附加 _level / _days 暫存欄位後依 days 降序排序。"""
    min_rank = _min_rank_for_threshold(threshold)
    rows: List[Dict] = []
    for ticket in tickets:
        if ticket.get("status") != STATUS_PENDING:
            continue
        if wave is not None and ticket.get("wave") != wave:
            continue
        level = calculate_stale_level(ticket.get("created"), today=today)
        if level is None:
            continue
        if _LEVEL_RANK[level] < min_rank:
            continue
        days = _days_since_created(ticket, today)
        if days is None:
            continue
        rows.append({**ticket, "_level": level, "_days": days})
    rows.sort(key=lambda r: r["_days"], reverse=True)
    return rows


def _gather_tickets(
    explicit_version: Optional[str], all_versions: bool
) -> List[Dict]:
    """依 --version / --all / 自動 active 版本收集 ticket。"""
    if explicit_version:
        versions = [explicit_version]
    else:
        versions = get_active_versions() or []
    aggregated: List[Dict] = []
    for version in versions:
        aggregated.extend(list_tickets(version) or [])
    return aggregated


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _render_table(rows: List[Dict], threshold: str, wave: Optional[int]) -> str:
    lines: List[str] = []
    lines.append("─" * 60)
    header = f"Stale pending tickets (threshold={threshold})"
    if wave is not None:
        header += f"  wave={wave}"
    lines.append(header)
    lines.append("─" * 60)
    if not rows:
        lines.append("（無符合條件的 stale ticket）")
        return "\n".join(lines)
    for row in rows:
        tid = row.get("id", "<unknown>")
        title = row.get("title") or ""
        level = _LEVEL_LABEL.get(row["_level"], row["_level"])
        days = row["_days"]
        lines.append(f"{tid} | [{level}] | {days} 天 | {title}")
    return "\n".join(lines)


def _render_ids(rows: List[Dict]) -> str:
    return "\n".join(r.get("id", "") for r in rows if r.get("id"))


def _render_yaml(rows: List[Dict]) -> str:
    lines: List[str] = []
    for row in rows:
        lines.append(f"- id: {row.get('id', '')}")
        lines.append(f"  level: {_LEVEL_LABEL.get(row['_level'], row['_level'])}")
        lines.append(f"  days: {row['_days']}")
        title = (row.get("title") or "").replace('"', '\\"')
        lines.append(f'  title: "{title}"')
    if not lines:
        return "[]"
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def execute_stale_list(args: argparse.Namespace) -> int:
    """執行 track stale-list 命令。"""
    threshold = getattr(args, "threshold", "warning") or "warning"
    wave = getattr(args, "wave", None)
    all_versions = bool(getattr(args, "all", False))
    explicit_version = getattr(args, "version", None)
    fmt = getattr(args, "format", "table") or "table"
    today_override = getattr(args, "_today", None)  # 測試用 hook
    today = today_override or date.today()

    tickets = _gather_tickets(explicit_version, all_versions)
    rows = _collect_stale(
        tickets, threshold=threshold, wave=wave, today=today
    )

    if fmt == "ids":
        print(_render_ids(rows))
    elif fmt == "yaml":
        print(_render_yaml(rows))
    else:
        print(_render_table(rows, threshold, wave))
    return 0


def register_stale_list(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 stale-list 子命令 parser。"""
    p = subparsers.add_parser(
        "stale-list",
        help=(
            "列出 stale pending ticket 明細（ID + level + 天數 + 標題）"
        ),
    )
    p.add_argument(
        "--threshold",
        choices=["info", "warning", "critical", "all"],
        default="warning",
        help=(
            "篩選等級："
            "warning（預設，warning+critical）/ info / all（同 info）/ critical"
        ),
    )
    p.add_argument(
        "--wave",
        type=int,
        default=None,
        help="僅列出指定 wave 的 ticket",
    )
    p.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="跨所有 active 版本掃描（預設僅當前 active 版本）",
    )
    p.add_argument(
        "--version",
        default=None,
        help="指定版本（覆蓋自動偵測；與 --all 互斥）",
    )
    p.add_argument(
        "--format",
        choices=["table", "ids", "yaml"],
        default="table",
        help="輸出格式（預設 table）",
    )
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
