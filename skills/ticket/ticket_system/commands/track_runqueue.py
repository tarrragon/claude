"""
ticket track runqueue 命令（W17-011.1 / W17-009 scheduler 落地）

統一 scheduler CLI，合併原 next / schedule / resume-hint 三命令為單一 runqueue
+ --format 視圖切換。三視角審查（Evidence / Alternatives / linux）一致收斂結論。

視圖語意：
- list（預設）：blockedBy == [] 且 status == pending 的可執行清單，
  priority P0→P3 排序
- dag：拓撲層級分組，整個 DAG（含 blocked），呈現 blockedBy 鏈
- critical-path：僅返回關鍵路徑節點（slack = 0）

額外參數：
- --top N：list / critical-path 生效，dag 忽略
- --context=resume：與 .claude/handoff/pending/ 交集 ticket_id
- --wave N：wave 範圍過濾

設計約束（W17-011.1 ticket 關鍵約束）：
- 復用 ticket_system.lib.critical_path.CriticalPathAnalyzer
- 復用 ticket_system.lib.cycle_detector.CycleDetector（經由 analyzer 間接使用）
- 註冊於 track.py _create_command_handlers() 字典
  （不走 snapshot / dispatch-check 特殊分支雙軌）
- 不新增 scheduler nice-flag 類參數（linux 審查：ticket 無動態 CPU share 類比）
- 不自行實作拓撲 / CPM / 環檢測演算法（皆復用 lib）
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from ticket_system.lib.critical_path import (
    CriticalPathAnalyzer,
    CriticalPathResult,
)
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.paths import get_project_root


# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

FORMAT_LIST = "list"
FORMAT_DAG = "dag"
FORMAT_CRITICAL_PATH = "critical-path"

_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
_DEFAULT_PRIORITY_RANK = 99  # 未知 priority 排最後


# ---------------------------------------------------------------------------
# 內部工具：ticket 過濾 / 排序 / handoff 掃描
# ---------------------------------------------------------------------------

def _priority_rank(ticket: Dict) -> int:
    """取得 priority 的排序鍵，未知值排最後。"""
    raw = (ticket.get("priority") or "").strip().upper()
    return _PRIORITY_ORDER.get(raw, _DEFAULT_PRIORITY_RANK)


def _is_unblocked_pending(ticket: Dict) -> bool:
    """list 視圖規則：status=pending 且 blockedBy=[]。"""
    if ticket.get("status") != "pending":
        return False
    blocked_by = ticket.get("blockedBy") or []
    return len(blocked_by) == 0


def _filter_by_wave(tickets: Iterable[Dict], wave: Optional[int]) -> List[Dict]:
    if wave is None:
        return list(tickets)
    return [t for t in tickets if t.get("wave") == wave]


def _get_pending_handoff_ticket_ids() -> Set[str]:
    """掃描 .claude/handoff/pending/*.json 取得 ticket_id 集合。

    獨立函式便於測試 monkeypatch；不依賴 handoff_utils 完整解析流程
    （只需 ticket_id），降低耦合。
    """
    try:
        root = get_project_root()
    except Exception:
        return set()

    pending_dir = root / ".claude" / "handoff" / "pending"
    if not pending_dir.exists():
        return set()

    ticket_ids: Set[str] = set()
    for handoff_file in sorted(pending_dir.glob("*.json")):
        try:
            data = json.loads(handoff_file.read_text(encoding="utf-8"))
        except (IOError, json.JSONDecodeError):
            continue
        ticket_id = data.get("ticket_id")
        if ticket_id:
            ticket_ids.add(ticket_id)
    return ticket_ids


def _apply_context_resume(
    tickets: List[Dict], context: Optional[str]
) -> List[Dict]:
    """context=resume：與 handoff pending 交集。"""
    if context != "resume":
        return tickets
    pending_ids = _get_pending_handoff_ticket_ids()
    if not pending_ids:
        return []
    return [t for t in tickets if t.get("id") in pending_ids]


# ---------------------------------------------------------------------------
# 視圖渲染：list
# ---------------------------------------------------------------------------

def _render_list(
    tickets: List[Dict],
    top: Optional[int],
    wave: Optional[int],
    context: Optional[str] = None,
) -> str:
    runnable = [t for t in tickets if _is_unblocked_pending(t)]
    runnable.sort(
        key=lambda t: (_priority_rank(t), str(t.get("id", "")))
    )

    if top is not None and top > 0:
        runnable = runnable[:top]

    lines: List[str] = []
    header_parts = ["可執行清單"]
    if wave is not None:
        header_parts.append(f"wave {wave}")
    if top is not None:
        header_parts.append(f"top {top}")
    header_parts.append("priority 排序")
    lines.append("─" * 60)
    lines.append("（" + " / ".join(header_parts) + "）")
    lines.append("─" * 60)

    if not runnable:
        if context == "resume":
            lines.append("（無 resume 候選；當前無 handoff pending ticket）")
        else:
            lines.append(
                "（無可執行 Ticket；blockedBy 全非空或 status 非 pending）"
            )
        return "\n".join(lines)

    for idx, ticket in enumerate(runnable, start=1):
        tid = ticket.get("id", "<unknown>")
        priority = ticket.get("priority") or "P?"
        title = ticket.get("title") or ""
        lines.append(
            f"  {idx}. [{priority}] {tid}  {title}  blockedBy=[]"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 視圖渲染：dag
# ---------------------------------------------------------------------------

def _compute_topological_levels(
    tickets: List[Dict],
) -> Dict[int, List[Dict]]:
    """以每個 ticket 的 ES（最早開始時間，來自 CPM forward pass）作為層級。

    復用 CriticalPathAnalyzer 的計算結果，避免自行實作拓撲層級。
    若有環，analyzer 回傳 is_valid=False；此時 fallback 將所有 ticket 放層級 0。
    """
    ticket_map = {t.get("id"): t for t in tickets if t.get("id")}
    result = CriticalPathAnalyzer.analyze(list(ticket_map.values()))

    levels: Dict[int, List[Dict]] = defaultdict(list)
    if not result.is_valid:
        levels[0] = list(ticket_map.values())
        return levels

    for tid, schedule in result.ticket_schedule.items():
        level = schedule.get("es", 0)
        if tid in ticket_map:
            levels[level].append(ticket_map[tid])
    return levels


def _render_dag(tickets: List[Dict]) -> str:
    if not tickets:
        return "（無 Ticket）"

    levels = _compute_topological_levels(tickets)
    critical_path_ids = set()
    result = CriticalPathAnalyzer.analyze(tickets)
    if result.is_valid:
        critical_path_ids = set(result.critical_path)

    lines: List[str] = []
    lines.append("─" * 60)
    lines.append("DAG 視圖（拓撲層級分組）")
    lines.append("─" * 60)

    if not result.is_valid:
        cycle = result.cycle_info or []
        lines.append(
            f"[WARN] 偵測到循環依賴：{' → '.join(cycle) if cycle else '<unknown>'}"
        )
        lines.append("（以下為無環境下的平鋪列表）")

    for level in sorted(levels.keys()):
        bucket = sorted(
            levels[level],
            key=lambda t: (_priority_rank(t), str(t.get("id", ""))),
        )
        lines.append(f"層級 {level}:")
        for ticket in bucket:
            tid = ticket.get("id", "<unknown>")
            priority = ticket.get("priority") or "P?"
            status = ticket.get("status") or "?"
            marker = " <關鍵路徑>" if tid in critical_path_ids else ""
            blocked = ticket.get("blockedBy") or []
            blocked_repr = ",".join(blocked) if blocked else ""
            lines.append(
                f"  [{priority}] {tid} ({status})"
                + (f" blockedBy=[{blocked_repr}]" if blocked else "")
                + marker
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 視圖渲染：critical-path
# ---------------------------------------------------------------------------

def _render_critical_path(
    tickets: List[Dict], top: Optional[int]
) -> str:
    if not tickets:
        return "（無 Ticket）"

    result = CriticalPathAnalyzer.analyze(tickets)
    lines: List[str] = []
    lines.append("─" * 60)
    lines.append("關鍵路徑（slack = 0）")
    lines.append("─" * 60)

    if not result.is_valid:
        cycle = result.cycle_info or []
        lines.append(
            "[WARN] 偵測到循環依賴："
            f"{' → '.join(cycle) if cycle else '<unknown>'}"
        )
        return "\n".join(lines)

    path = result.critical_path
    if top is not None and top > 0:
        path = path[:top]

    if not path:
        lines.append("（無關鍵路徑）")
        return "\n".join(lines)

    ticket_map = {t.get("id"): t for t in tickets}
    for idx, tid in enumerate(path, start=1):
        ticket = ticket_map.get(tid, {})
        priority = ticket.get("priority") or "P?"
        title = ticket.get("title") or ""
        lines.append(f"  {idx}. [{priority}] {tid}  {title}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def execute_runqueue(args: argparse.Namespace, version: str) -> int:
    """執行 track runqueue 命令。

    Returns:
        0: 正常；非 0 僅用於內部錯誤
    """
    fmt = getattr(args, "format", FORMAT_LIST) or FORMAT_LIST
    top = getattr(args, "top", None)
    context = getattr(args, "context", None)
    wave = getattr(args, "wave", None)

    all_tickets = list_tickets(version) or []
    scoped = _filter_by_wave(all_tickets, wave)
    scoped = _apply_context_resume(scoped, context)

    if fmt == FORMAT_LIST:
        print(_render_list(scoped, top, wave, context))
    elif fmt == FORMAT_DAG:
        # dag 忽略 --top（呈現完整 DAG）
        print(_render_dag(scoped))
    elif fmt == FORMAT_CRITICAL_PATH:
        print(_render_critical_path(scoped, top))
    else:
        print(f"[ERROR] 不支援的 --format={fmt}")
        return 1
    return 0


def register_runqueue(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 runqueue 子命令 parser。

    註冊邏輯由 track.py 呼叫；execute dispatch 走
    _create_command_handlers() 字典（不走 snapshot / dispatch-check
    特殊處理雙軌）。
    """
    p = subparsers.add_parser(
        "runqueue",
        help=(
            "統一 scheduler CLI："
            "runqueue --format={list|dag|critical-path} [--top N] "
            "[--context=resume] [--wave N]"
        ),
    )
    p.add_argument(
        "--format",
        choices=[FORMAT_LIST, FORMAT_DAG, FORMAT_CRITICAL_PATH],
        default=FORMAT_LIST,
        help="輸出視圖（預設 list）",
    )
    p.add_argument(
        "--top",
        type=int,
        default=None,
        help="返回前 N 筆（僅 list / critical-path 有效，dag 忽略）",
    )
    p.add_argument(
        "--context",
        choices=["resume"],
        default=None,
        help="resume：與 .claude/handoff/pending/ 交集",
    )
    p.add_argument(
        "--wave",
        type=int,
        default=None,
        help="過濾 wave 範圍",
    )
    p.add_argument(
        "--status",
        default="pending",
        help="目前僅支援 pending（預設）",
    )
    p.add_argument("--version", help="指定版本號")
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
