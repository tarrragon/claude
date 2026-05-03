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
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Set

from ticket_system.lib.critical_path import (
    CriticalPathAnalyzer,
    CriticalPathResult,
)
from ticket_system.lib.ticket_loader import list_tickets, load_ticket
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.section_locator import find_section
from ticket_system.lib.staleness import is_stale_in_progress


# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

FORMAT_LIST = "list"
FORMAT_DAG = "dag"
FORMAT_CRITICAL_PATH = "critical-path"

_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
_DEFAULT_PRIORITY_RANK = 99  # 未知 priority 排最後

# Exit Status tags 顯示於 runqueue --context=resume（W17-031.1 / W17-010 schema）
# 規格：成功 / 缺欄位 → 不標籤（fail-open）；以下四類顯示為 tag
ExitStatusTag = Literal[
    "needs_context", "blocked", "failed", "partial_success"
]
_TAGGED_EXIT_STATUSES: Set[str] = {
    "needs_context", "blocked", "failed", "partial_success"
}


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


def _is_listable(ticket: Dict) -> bool:
    """W17-031.4: list 視圖納入條件 = unblocked pending OR stale in_progress。

    stale in_progress 加入 list 是為了讓 PM 在 runqueue 看見遺留 ticket
    並人工介入（評估 agent 真停滯還是長任務）。W17-033 自律 + acceptance-gate-hook
    無法覆蓋 agent 中斷案例（agent 已不在）。
    """
    if _is_unblocked_pending(ticket):
        return True
    if is_stale_in_progress(ticket):
        return True
    return False


def _filter_by_wave(tickets: Iterable[Dict], wave: Optional[int]) -> List[Dict]:
    if wave is None:
        return list(tickets)
    return [t for t in tickets if t.get("wave") == wave]


def _get_pending_handoff_info() -> Dict[str, Dict]:
    """掃描 .claude/handoff/pending/*.json，回傳 ticket_id → handoff JSON 字典。

    W17-031.1：擴充自原 _get_pending_handoff_ticket_ids；保留完整 handoff
    資料以便讀取 exit_status（W17-010 schema）。獨立函式便於測試 monkeypatch；
    不依賴 handoff_utils 完整解析流程，降低耦合。

    Returns:
        ticket_id → handoff data dict；解析失敗或無 pending 目錄時回傳 {}。
    """
    try:
        root = get_project_root()
    except Exception:
        return {}

    pending_dir = root / ".claude" / "handoff" / "pending"
    if not pending_dir.exists():
        return {}

    info: Dict[str, Dict] = {}
    for handoff_file in sorted(pending_dir.glob("*.json")):
        try:
            data = json.loads(handoff_file.read_text(encoding="utf-8"))
        except (IOError, json.JSONDecodeError):
            continue
        ticket_id = data.get("ticket_id")
        if ticket_id:
            info[ticket_id] = data
    return info


def _get_pending_handoff_ticket_ids() -> Set[str]:
    """回傳 handoff pending ticket_id 集合（thin wrapper，向後相容）。"""
    return set(_get_pending_handoff_info().keys())


def _get_exit_status_tag(handoff_info: Optional[Dict]) -> Optional[str]:
    """從 handoff JSON 解析 exit_status tag（W17-031.1）。

    Fail-open 設計：handoff 不存在 / 缺 exit_status 欄位 / 非 dict / status=success
    皆回傳 None（不顯示 tag）；僅四類 needs_context/blocked/failed/partial_success
    回傳對應字串。

    Args:
        handoff_info: handoff JSON dict，或 None
    Returns:
        ExitStatusTag 字串之一，或 None（不標籤）
    """
    if not handoff_info or not isinstance(handoff_info, dict):
        return None
    exit_status = handoff_info.get("exit_status")
    if not isinstance(exit_status, dict):
        return None
    status = exit_status.get("status")
    if isinstance(status, str) and status in _TAGGED_EXIT_STATUSES:
        return status
    return None


# ---------------------------------------------------------------------------
# W17-031.3: Readiness 標註
# ---------------------------------------------------------------------------

# Readiness tags（W17-031.3 ticket md 判定規則表）
READINESS_READY = "READY"
READINESS_NEEDS_CTX = "NEEDS-CTX"
READINESS_BLOCKED = "BLOCKED"
READINESS_FAILED = "FAILED"
READINESS_NO_CB = "NO-CB"

# W17-031.4: stale in_progress 標註（與 readiness tag 並列顯示）
STALE_TAG = "STALE"

# exit_status → readiness tag 映射（非 success / 缺欄位）
_EXIT_STATUS_TO_READINESS: Dict[str, str] = {
    "needs_context": READINESS_NEEDS_CTX,
    "blocked": READINESS_BLOCKED,
    "failed": READINESS_FAILED,
}


def _has_context_bundle(ticket: Dict) -> bool:
    """檢查 ticket body 是否含非空 Context Bundle 段落。

    讀取順序：先用既有 _body 欄位（list_tickets 載入時附加）；若無則
    fallback 用 load_ticket 重新載入。判定「非空」：去除 placeholder /
    HTML 註解 / 空白後仍有實質內容。
    """
    body: Optional[str] = ticket.get("_body")
    if body is None:
        ticket_id = ticket.get("id")
        version = ticket.get("version")
        if not ticket_id or not version:
            return False
        loaded = load_ticket(str(version), str(ticket_id))
        if not loaded:
            return False
        body = loaded.get("_body") or ""

    if not body:
        return False

    match = find_section(body, "Context Bundle")
    if not match.found:
        return False

    content = match.content or ""
    # 移除 HTML 註解
    cleaned = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    # 去空白後判斷是否有實質內容
    return bool(cleaned.strip())


def _compute_readiness(
    ticket: Dict, handoff_info: Optional[Dict[str, Dict]] = None
) -> str:
    """計算 ticket 的 readiness tag（W17-031.3 判定規則表）。

    規則順序：
    1. exit_status in {needs_context, blocked, failed} → 對應 tag
    2. exit_status == success → READY
    3. Context Bundle 段落非空 → READY
    4. 其他 → NO-CB
    """
    handoff_info = handoff_info or {}
    info = handoff_info.get(ticket.get("id"))
    exit_status_obj = (info or {}).get("exit_status") if isinstance(info, dict) else None
    if isinstance(exit_status_obj, dict):
        status = exit_status_obj.get("status")
        if isinstance(status, str):
            mapped = _EXIT_STATUS_TO_READINESS.get(status)
            if mapped:
                return mapped
            if status == "success":
                return READINESS_READY
            # partial_success / 未知值 → fallthrough 改用 Context Bundle 判定

    if _has_context_bundle(ticket):
        return READINESS_READY
    return READINESS_NO_CB


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
    handoff_info: Optional[Dict[str, Dict]] = None,
) -> str:
    runnable = [t for t in tickets if _is_listable(t)]
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

    handoff_info = handoff_info or {}
    for idx, ticket in enumerate(runnable, start=1):
        tid = ticket.get("id", "<unknown>")
        priority = ticket.get("priority") or "P?"
        title = ticket.get("title") or ""
        # W17-031.1: resume 模式且有 exit_status tag → 顯示 [<status>] 取代
        # blockedBy=[] runnable 標記，避免 scheduler 誤把待補料 ticket 當可接手
        tag = _get_exit_status_tag(handoff_info.get(tid)) if context == "resume" else None
        suffix = f"[{tag}]" if tag else "blockedBy=[]"
        # W17-031.3: readiness tag（READY / NEEDS-CTX / BLOCKED / FAILED / NO-CB）
        # 不影響排序；資訊是 PM 派發前判斷可接手與否的可視訊號
        readiness = _compute_readiness(ticket, handoff_info)
        # W17-031.4: stale in_progress tag（與 readiness 並列；可疊加）
        # PM 看到 [STALE] → 人工介入評估（agent 真停滯 vs 長任務）
        stale_suffix = f" [{STALE_TAG}]" if is_stale_in_progress(ticket) else ""
        lines.append(
            f"  {idx}. [{priority}] [{readiness}]{stale_suffix} {tid}  {title}  {suffix}"
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

def render_runqueue(args: argparse.Namespace, version: str) -> str:
    """渲染 track runqueue 輸出文字。"""
    fmt = getattr(args, "format", FORMAT_LIST) or FORMAT_LIST
    top = getattr(args, "top", None)
    context = getattr(args, "context", None)
    wave = getattr(args, "wave", None)

    all_tickets = list_tickets(version) or []
    scoped = _filter_by_wave(all_tickets, wave)
    scoped = _apply_context_resume(scoped, context)

    # W17-031.1: resume 模式下載入 handoff info 供 _render_list 標 exit_status tag
    # W17-031.3: list 視圖一律載入 handoff info 供 readiness 計算（READY/NEEDS-CTX 等）
    handoff_info: Dict[str, Dict] = (
        _get_pending_handoff_info() if (context == "resume" or fmt == FORMAT_LIST) else {}
    )

    if fmt == FORMAT_LIST:
        return _render_list(scoped, top, wave, context, handoff_info)
    elif fmt == FORMAT_DAG:
        # dag 忽略 --top（呈現完整 DAG）
        return _render_dag(scoped)
    elif fmt == FORMAT_CRITICAL_PATH:
        return _render_critical_path(scoped, top)

    raise ValueError(f"不支援的 --format={fmt}")


def execute_runqueue(args: argparse.Namespace, version: str) -> int:
    """執行 track runqueue 命令。

    Returns:
        0: 正常；非 0 僅用於內部錯誤
    """
    try:
        print(render_runqueue(args, version))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
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
