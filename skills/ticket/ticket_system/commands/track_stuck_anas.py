"""
ticket track stuck-anas 命令（W17-008.15 方案 D 第 1 項；children 落地路徑擴充）

掃描 ANA type + status=in_progress + 落地路徑（spawned_tickets 與/或
children）已全數 terminal 的 ticket，協助 PM 識別「衍生/子任務全完成但
source ANA 未 complete」的卡住情境。

落地路徑判定語意（用戶裁示）：
- ANA 的落地物可能寫入 spawned_tickets（create --source-ticket）或
  children（create --parent），兩者皆須納入偵測，否則走 children 落地
  的 ANA 永遠不會被列出（曾有子票皆 completed、分析已寫完，仍長時間
  滯留 in_progress 且未被本指令偵測到的實測案例）。
- 兩個來源各自可為空；空來源不參與判定。
- 兩個來源皆空 → 不視為卡住（避免把剛派發、尚無任何落地物的票誤報）。
- 至少一個來源非空時，所有非空來源都必須「全部存在且皆 terminal」才
  視為卡住；任一來源尚有非 terminal（或找不到）的票，即不列出——採
  聯集全 terminal，優先避免誤報而非避免漏報。

設計約束：
- version-agnostic（可選 --version / --wave 過濾；--all 為相容保留旗標，
  與預設行為無差異）
- 註冊於 track.py _create_version_agnostic_handlers() 字典
- 復用 ticket_loader.list_tickets / get_active_versions
"""

from __future__ import annotations

import argparse
from typing import Dict, List, Optional, Tuple

from ticket_system.constants import STATUS_IN_PROGRESS, TERMINAL_STATUSES
from ticket_system.lib.command_tracking_messages import TrackMessages
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.version import get_active_versions

# ticket 欄位名 -> 落地路徑，順序即輸出欄位標明順序。
_LANDING_PATH_FIELDS: Tuple[str, ...] = ("spawned_tickets", "children")


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------

def _is_ana_in_progress(ticket: Dict) -> bool:
    """ANA type 且 status=in_progress。"""
    return (
        ticket.get("type") == "ANA"
        and ticket.get("status") == STATUS_IN_PROGRESS
    )


def _is_source_all_terminal(
    ids: List[str], ticket_index: Dict[str, Dict]
) -> Optional[bool]:
    """單一落地來源（spawned_tickets 或 children）是否全數 terminal。

    來源為空回傳 None（表示此來源未使用，不參與判定）；
    來源非空但任一 id 查不到或非 terminal，回傳 False（保守，不視為完成）。
    """
    if not ids:
        return None
    for tid in ids:
        target = ticket_index.get(tid)
        if not target or target.get("status") not in TERMINAL_STATUSES:
            return False
    return True


def _stuck_sources(
    ticket: Dict, ticket_index: Dict[str, Dict]
) -> Tuple[bool, List[str]]:
    """判定 ticket 是否卡住，並回傳實際參與判定的落地來源清單。

    回傳 (is_stuck, active_sources)。active_sources 為非空來源的欄位名
    （"spawned_tickets" / "children"），用於輸出標明落地路徑。
    """
    active_sources: List[str] = []
    results: List[bool] = []
    for field in _LANDING_PATH_FIELDS:
        ids = ticket.get(field) or []
        result = _is_source_all_terminal(ids, ticket_index)
        if result is None:
            continue
        active_sources.append(field)
        results.append(result)

    if not active_sources:
        # 兩個來源皆空：無任何落地物，不視為卡住（避免誤報剛派發的票）
        return False, active_sources
    return all(results), active_sources


def _collect_stuck_anas(
    tickets: List[Dict], wave: Optional[int]
) -> List[Tuple[Dict, List[str]]]:
    """過濾卡住的 ANA，並附帶各票的落地來源清單。"""
    ticket_index = {t.get("id"): t for t in tickets if t.get("id")}
    stuck: List[Tuple[Dict, List[str]]] = []
    for ticket in tickets:
        if not _is_ana_in_progress(ticket):
            continue
        if wave is not None and ticket.get("wave") != wave:
            continue
        is_stuck, active_sources = _stuck_sources(ticket, ticket_index)
        if is_stuck:
            stuck.append((ticket, active_sources))
    return stuck


def _gather_tickets(
    explicit_version: Optional[str],
) -> List[Dict]:
    """依 --version / 自動偵測 active versions 收集 ticket 清單。"""
    versions: List[str]
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

def _render(stuck: List[Tuple[Dict, List[str]]], wave: Optional[int]) -> str:
    lines: List[str] = []
    lines.append("─" * 60)
    header = "卡住的 ANA（in_progress 且落地路徑全 completed）"
    if wave is not None:
        header += f"  wave={wave}"
    lines.append(header)
    lines.append("─" * 60)

    if not stuck:
        lines.append("（無卡住的 ANA）")
        return "\n".join(lines)

    for idx, (ticket, active_sources) in enumerate(stuck, start=1):
        tid = ticket.get("id", "<unknown>")
        title = ticket.get("title") or ""
        source_summary = "、".join(
            f"{field}={len(ticket.get(field) or [])}" for field in active_sources
        )
        lines.append(
            f"  {idx}. {tid}  {title}"
        )
        lines.append(
            f"      {source_summary} 全 completed → 可考慮 "
            f"ticket track complete {tid}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def execute_stuck_anas(args: argparse.Namespace) -> int:
    """執行 track stuck-anas 命令（version-agnostic）。"""
    wave = getattr(args, "wave", None)
    explicit_version = getattr(args, "version", None)

    tickets = _gather_tickets(explicit_version)
    stuck = _collect_stuck_anas(tickets, wave)
    print(_render(stuck, wave))
    return 0


def register_stuck_anas(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 stuck-anas 子命令 parser。"""
    p = subparsers.add_parser(
        "stuck-anas",
        help=(
            "列出卡住的 ANA："
            "type=ANA + status=in_progress 且落地路徑全 completed"
        ),
    )
    p.add_argument(
        "--wave",
        type=int,
        default=None,
        help="僅列出指定 wave 的 ANA",
    )
    p.add_argument(
        "--all",
        action="store_true",
        default=False,
        help=TrackMessages.ARG_ALL_COMPAT,
    )
    p.add_argument(
        "--version",
        default=None,
        help="指定版本（覆蓋自動偵測）",
    )
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
