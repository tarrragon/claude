"""
ticket track dashboard 命令（W10-114 落地，W10-113 ANA Solution M1+M4'）

聚合 in_progress + top N ready + stale warning 三章節為單一視圖，
讓 PM 接手新 session 時的 /ticket 流程從 7 tool call 降至 3 個
（dashboard + claim by number + 後續動作）。

設計約束：
- 禁用 subprocess（含 shell escape 函式），全部以 import 複用既有函式
- text / json 從同一份蒐集後資料渲染（A4 一致性）
- [N] 編號僅在 Ready 章節 enumerate，不跨章節（B3/B4）
- 三章節資料蒐集獨立函式，便於 monkeypatch 測試
- 任一階段失敗 → stderr + return 非 0，stdout 為空（D7）

複用既有：
- track_runqueue._priority_rank / _is_unblocked_pending / _filter_by_wave
  / _compute_readiness / _get_pending_handoff_info（0.2.1-W3-220 起同時以
  target_ticket_id 建索引，新增 [Handoff Target] 章節見 load_handoff_targets）
- lib.staleness.compute_stale_minutes（W10-114 新增分鐘粒度純函式）
- lib.ticket_loader.list_tickets

不複用：
- track_runqueue._render_list / _render_dag / _render_critical_path（格式不同）
- track_stale_list._days_since_created（粒度為日，不符）

0.2.1-W3-261（issue 42 修復）：
- Ready 判定的 blockedBy 維度自初版起即同源 is_fully_unblocked（經
  `_is_unblocked_pending` 間接複用，見 load_top_ready），與 runqueue
  共用同一 predicate，非本次新增。
- 本次新增 children 維度過濾：含未完成（非 completed/closed）子任務的
  父票不列入 Ready（見 `_has_incomplete_children`）。取捨依據：父票即使
  被 claim 也會在 complete 時被 acceptance_auditor.validate_children_completed
  阻擋（children 未完成），列為「可直接 claim」具誤導性，故選擇排除而非
  加標記。此過濾僅套用於 dashboard 的 Ready 章節，不回寫 runqueue——
  runqueue 的 dag/critical-path 視圖需完整呈現 DAG（含受 children 阻塞的
  父票）供排程判斷，兩者職責不同（各自的「同一 wave 一致性」僅指
  blockedBy 判定同源，不含 children 過濾範圍）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from ticket_system.commands.track_runqueue import (
    READINESS_NO_CB,
    READINESS_READY,
    _compute_readiness,
    _filter_by_wave,
    _get_pending_handoff_info,
    _is_unblocked_pending,
    _priority_rank,
)
from ticket_system.lib.constants import TERMINAL_STATUSES
from ticket_system.lib.staleness import compute_stale_minutes
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.ticket_ops import resolve_id_from_ref
from ticket_system.lib.version import check_version_all_completed
from ticket_system.lib.command_tracking_messages import (
    TrackQueryMessages,
    format_msg,
)


# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

FORMAT_TEXT = "text"
FORMAT_JSON = "json"

DEFAULT_TOP = 5
DEFAULT_STALE_THRESHOLD_MIN = 60

HINT_LINE = "Hint: ticket track claim <id>"


# ---------------------------------------------------------------------------
# 資料蒐集
# ---------------------------------------------------------------------------

def load_in_progress(tickets: List[Dict]) -> List[Dict[str, Any]]:
    """收集 in_progress ticket，按 started_at 升冪排序。"""
    result: List[Dict[str, Any]] = []
    for t in tickets:
        if t.get("status") != "in_progress":
            continue
        who = t.get("who") or {}
        agent = who.get("current") if isinstance(who, dict) else None
        result.append({
            "id": t.get("id"),
            "title": t.get("title") or "",
            "started_at": t.get("started_at"),
            "agent": agent,
        })
    result.sort(key=lambda x: str(x.get("started_at") or ""))
    return result


def _has_incomplete_children(ticket: Dict, ticket_map: Dict[str, Dict]) -> bool:
    """判斷 ticket 是否有未完成（非 completed/closed）的子任務（0.2.1-W3-261）。

    children 項目可能是字串 ID 或已嵌入 status 的字典。優先信任 ticket_map
    （同一 wave 全集、狀態即時）；找不到對應 ticket 時 fallback 讀字典內嵌
    status，兩者皆無則保守視為未完成——呼應 `is_fully_unblocked` 對缺失
    blocker 的保守設計（資料不一致時不建議把父票列為可直接 claim）。
    """
    children = ticket.get("children") or []
    if not children:
        return False
    for child_ref in children:
        child_id = resolve_id_from_ref(child_ref)
        child = ticket_map.get(child_id) if child_id else None
        if child is not None:
            status = child.get("status")
        elif isinstance(child_ref, dict):
            status = child_ref.get("status")
        else:
            status = None
        if status not in TERMINAL_STATUSES:
            return True
    return False


def load_top_ready(
    tickets: List[Dict],
    top: int,
    handoff_info: Optional[Dict[str, Dict]] = None,
) -> List[Dict[str, Any]]:
    """收集 top N actionable ticket，按 (readiness_rank, priority, trigger_bound, id) 排序。

    READY 排前、NO-CB 排後；其他 readiness（NEEDS-CTX/BLOCKED/FAILED）不列入。
    有未完成 children 的父票不列入（0.2.1-W3-261，見 `_has_incomplete_children`）。
    top <= 0 回傳 []。

    排序鍵語意（W3-096 + dashboard NO-CB 修復）：
    - readiness_rank 為最高鍵（READY=0, NO-CB=1）；READY 優先於 NO-CB
    - priority 為次要鍵（_priority_rank）
    - trigger_bound 為第三鍵（false=0 / true=1）
    - id 為穩定排序鍵
    """
    _ACTIONABLE = {READINESS_READY, READINESS_NO_CB}
    _READINESS_RANK = {READINESS_READY: 0, READINESS_NO_CB: 1}

    handoff_info = handoff_info or {}
    ticket_map = {t.get("id"): t for t in tickets if t.get("id")}
    candidates = []
    for t in tickets:
        if not _is_unblocked_pending(t, ticket_map):
            continue
        if _has_incomplete_children(t, ticket_map):
            continue
        readiness = _compute_readiness(t, handoff_info)
        if readiness not in _ACTIONABLE:
            continue
        candidates.append((t, readiness))
    candidates.sort(key=lambda pair: (
        _READINESS_RANK.get(pair[1], 99),
        _priority_rank(pair[0]),
        1 if pair[0].get("trigger_bound") else 0,
        str(pair[0].get("id") or ""),
    ))
    if top <= 0:
        return []
    limited = candidates[:top]
    return [
        {
            "id": t.get("id"),
            "title": t.get("title") or "",
            "priority": t.get("priority") or "P?",
            "readiness": readiness,
            "trigger_bound": bool(t.get("trigger_bound")),
        }
        for (t, readiness) in limited
    ]


def load_handoff_targets(
    tickets: List[Dict],
    handoff_info: Optional[Dict[str, Dict]] = None,
) -> List[Dict[str, Any]]:
    """收集 handoff target_ticket_id 指向的票，獨立於 Ready 的 unblocked-pending 過濾。

    0.2.1-W3-220：來源票 0.2.1-W3-178 實測，target 票若為 in_progress 或
    completed 會完全不出現在 Ready 章節（Ready 只收 unblocked pending）。
    本函式不套用該過濾，故 target 票任何 status 皆顯示，交接目標不再被埋。

    讀 `_get_pending_handoff_info()` 修復後（同時以 target_ticket_id 建索引）
    的結果：key 等於 data 的 target_ticket_id 才是「target 專屬項」，
    避免誤取以 source ticket_id 為 key 的項目（該項 target_ticket_id 多半
    指向另一張票，非自身）。

    按 id 排序，回傳穩定順序。
    """
    handoff_info = handoff_info or {}
    ticket_map = {t.get("id"): t for t in tickets if t.get("id")}
    seen: set = set()
    result: List[Dict[str, Any]] = []
    for key, data in handoff_info.items():
        if not isinstance(data, dict):
            continue
        target_id = data.get("target_ticket_id")
        if not target_id or target_id != key or target_id in seen:
            continue
        seen.add(target_id)
        ticket = ticket_map.get(target_id)
        readiness = _compute_readiness(ticket, handoff_info) if ticket else None
        result.append({
            "id": target_id,
            "title": (ticket or {}).get("title") or "",
            "status": (ticket or {}).get("status") or "unknown",
            "readiness": readiness,
        })
    result.sort(key=lambda x: str(x.get("id") or ""))
    return result


def load_stale_warning(
    tickets: List[Dict],
    threshold_min: int,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """收集 stale in_progress ticket，按 stale_minutes 降冪排序。"""
    result: List[Dict[str, Any]] = []
    for t in tickets:
        if t.get("status") != "in_progress":
            continue
        mins = compute_stale_minutes(t, now)
        if mins is None or mins < threshold_min:
            continue
        who = t.get("who") or {}
        agent = who.get("current") if isinstance(who, dict) else None
        result.append({
            "id": t.get("id"),
            "stale_minutes": mins,
            "status": t.get("status"),
            "agent": agent,
        })
    result.sort(key=lambda x: x.get("stale_minutes", 0), reverse=True)
    return result


# ---------------------------------------------------------------------------
# 渲染：text
# ---------------------------------------------------------------------------

def render_text(
    version: str,
    wave: Optional[int],
    in_progress: List[Dict[str, Any]],
    ready: List[Dict[str, Any]],
    stale: Optional[List[Dict[str, Any]]],
    top: int,
    stale_threshold: int,
    stale_disabled: bool,
    handoff_targets: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """渲染 text 格式（PM 預設視圖）。"""
    wave_repr = wave if wave is not None else "all"
    lines: List[str] = []
    lines.append(f"=== Dashboard (wave={wave_repr}, version={version}) ===")
    lines.append("")

    # --- In Progress 區塊（不編號）---
    lines.append(f"[In Progress] {len(in_progress)} ticket(s)")
    if not in_progress:
        lines.append("  (none)")
    else:
        for item in in_progress:
            lines.append(
                f"  - {item['id']}  {item['title']}  "
                f"(started_at: {item.get('started_at')}, agent: {item.get('agent')})"
            )
    lines.append("")

    # --- Handoff Target 區塊（獨立於 Ready 的 unblocked-pending 過濾；
    #     target 票 in_progress/completed 仍顯示，不編號，見 0.2.1-W3-220）---
    targets = handoff_targets or []
    lines.append(f"[Handoff Target] {len(targets)} ticket(s)")
    if not targets:
        lines.append("  (none)")
    else:
        for item in targets:
            readiness_label = (item.get("readiness") or "unknown").lower()
            lines.append(
                f"  - {item['id']}  {item['title']}  "
                f"(status: {item.get('status')}, readiness: {readiness_label})"
            )
    lines.append("")

    # --- Ready Top N 區塊（唯一注入 [N] 編號處）---
    lines.append(f"[Ready Top {top}]  priority 排序，可直接 claim")
    if not ready:
        lines.append("  (none)")
    else:
        for index, item in enumerate(ready, start=1):
            readiness_label = item.get("readiness", "ready").lower()
            trigger_tag = " [T]" if item.get("trigger_bound") else ""
            lines.append(
                f"  [{index}] [{item['priority']}] [{readiness_label}]{trigger_tag} "
                f"{item['id']}  {item['title']}"
            )
    lines.append("")

    # --- Stale 區塊（--no-stale 則完全省略，連 header 不印）---
    if not stale_disabled:
        stale_list = stale or []
        lines.append(
            f"[Stale Warning] {len(stale_list)} ticket(s) over {stale_threshold}min"
        )
        if not stale_list:
            lines.append("  (none)")
        else:
            for item in stale_list:
                lines.append(
                    f"  - {item['id']}  stale={item['stale_minutes']}m  "
                    f"status={item.get('status')}  agent={item.get('agent')}"
                )
        lines.append("")

    lines.append(HINT_LINE)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 渲染：json
# ---------------------------------------------------------------------------

def render_json(
    version: str,
    wave: Optional[int],
    in_progress: List[Dict[str, Any]],
    ready: List[Dict[str, Any]],
    stale: Optional[List[Dict[str, Any]]],
    stale_threshold: int,
    stale_disabled: bool,
    handoff_targets: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """渲染 JSON 格式（hook / 自動化消費）。

    stale_disabled=True → stale 欄位為 JSON null（None），非 []（D5）。
    ready 欄位加 index（從 1 起算），與 text Ready 章節編號一致。
    handoff_targets 不編號（獨立於 Ready，見 0.2.1-W3-220），與 text 一致。
    """
    payload = {
        "version": version,
        "wave": wave,
        "in_progress": in_progress,
        "handoff_targets": handoff_targets or [],
        "ready": [
            {
                "index": i + 1,
                "id": item["id"],
                "priority": item["priority"],
                "readiness": item.get("readiness", "READY").lower(),
                "title": item["title"],
                "trigger_bound": bool(item.get("trigger_bound")),
            }
            for i, item in enumerate(ready)
        ],
        "stale": None if stale_disabled else (stale or []),
        "stale_threshold_minutes": stale_threshold,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def _print_all_completed_warning(version: str, tickets: list) -> None:
    """若版本所有 ticket 皆為終結狀態，印出 warning。

    重用 dashboard_main 已載入的 tickets，避免冗餘 list_tickets 重載
    （該重載會觸發 get_project_root → subprocess）。
    """
    all_completed, next_version = check_version_all_completed(version, tickets=tickets)
    if not all_completed:
        return

    print()
    print(format_msg(
        TrackQueryMessages.VERSION_ALL_COMPLETED_WARNING,
        version=version,
    ))
    if next_version:
        print(format_msg(
            TrackQueryMessages.VERSION_ALL_COMPLETED_NEXT,
            next_version=next_version,
        ))
    print(TrackQueryMessages.VERSION_ALL_COMPLETED_HINT)


def dashboard_main(args: argparse.Namespace, version: Optional[str]) -> int:
    """執行 track dashboard 命令。

    Returns:
        0: 正常輸出
        1: 內部錯誤（ticket index 載入時拋出 exception）
        2: 業務拒絕（無 active version，查無資料可供呈現）

    詳見 .claude/references/cli-exit-code-rules.md
    """
    if version is None:
        # 業務拒絕：查無 active version（資料源無資料），呼叫方應依拒絕原因處理
        sys.stderr.write("No active version detected\n")
        return 2

    # W5-005.14: 自動清理已完成 ticket 的 stale handoff（非靜默，stderr 提示）
    _auto_gc_stale_handoffs()

    try:
        all_tickets = list_tickets(version) or []
    except Exception as exc:
        # 內部錯誤：ticket index 載入拋出 exception
        sys.stderr.write(f"Failed to load ticket index: {exc}\n")
        return 1

    wave = getattr(args, "wave", None)
    top = getattr(args, "top", DEFAULT_TOP)
    if top is None:
        top = DEFAULT_TOP
    stale_threshold = getattr(args, "stale_threshold", DEFAULT_STALE_THRESHOLD_MIN)
    if stale_threshold is None:
        stale_threshold = DEFAULT_STALE_THRESHOLD_MIN
    no_stale = bool(getattr(args, "no_stale", False))
    fmt = getattr(args, "format", FORMAT_TEXT) or FORMAT_TEXT

    scoped = _filter_by_wave(all_tickets, wave)
    handoff_info = _get_pending_handoff_info()

    in_progress = load_in_progress(scoped)
    ready = load_top_ready(scoped, top=top, handoff_info=handoff_info)
    stale = None if no_stale else load_stale_warning(scoped, threshold_min=stale_threshold)
    handoff_targets = load_handoff_targets(scoped, handoff_info=handoff_info)

    if fmt == FORMAT_JSON:
        print(render_json(
            version=version,
            wave=wave,
            in_progress=in_progress,
            ready=ready,
            stale=stale,
            stale_threshold=stale_threshold,
            stale_disabled=no_stale,
            handoff_targets=handoff_targets,
        ))
    else:
        print(render_text(
            version=version,
            wave=wave,
            in_progress=in_progress,
            ready=ready,
            stale=stale,
            top=top,
            stale_threshold=stale_threshold,
            stale_disabled=no_stale,
            handoff_targets=handoff_targets,
        ))

    _print_all_completed_warning(version, all_tickets)
    return 0


def _auto_gc_stale_handoffs() -> None:
    """自動清理已完成 ticket 的 stale handoff（W5-005.14）。

    在 dashboard 載入前執行；清理結果寫 stderr（非靜默）。
    失敗時 graceful degrade（不影響 dashboard 正常輸出）。
    """
    try:
        from ticket_system.commands.handoff_gc import _collect_stale_handoffs
        from ticket_system.lib.constants import HANDOFF_DIR, HANDOFF_ARCHIVE_SUBDIR
        from ticket_system.lib.paths import get_project_root

        stale = _collect_stale_handoffs(force=False)
        if not stale:
            return

        root = get_project_root()
        archive_dir = root / HANDOFF_DIR / HANDOFF_ARCHIVE_SUBDIR
        archive_dir.mkdir(parents=True, exist_ok=True)

        for file_path, ticket_id, reason in stale:
            dest = archive_dir / file_path.name
            file_path.rename(dest)
            sys.stderr.write(
                f"[handoff-gc] 已歸檔 stale handoff: {file_path.name} ({reason})\n"
            )
    except Exception:
        pass


# execute alias 對齊 track.py _create_command_handlers 命名慣例
execute_dashboard = dashboard_main


def register_dashboard(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 dashboard 子命令 parser。"""
    p = subparsers.add_parser(
        "dashboard",
        help=(
            "聚合視圖：in_progress + top N ready + stale warning，"
            "讓 PM 接手新 session 一次看完"
        ),
    )
    p.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help=f"Ready 章節列數上限（預設 {DEFAULT_TOP}）",
    )
    p.add_argument(
        "--wave",
        type=int,
        default=None,
        help="過濾 wave 範圍（預設全部）",
    )
    p.add_argument(
        "--no-stale",
        action="store_true",
        help="隱藏 stale warning 章節",
    )
    p.add_argument(
        "--stale-threshold",
        type=int,
        default=DEFAULT_STALE_THRESHOLD_MIN,
        help=f"stale 判定門檻分鐘數（預設 {DEFAULT_STALE_THRESHOLD_MIN}）",
    )
    p.add_argument(
        "--format",
        choices=[FORMAT_TEXT, FORMAT_JSON],
        default=FORMAT_TEXT,
        help="輸出格式（預設 text）",
    )
    p.add_argument("--version", help="指定版本號")
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
