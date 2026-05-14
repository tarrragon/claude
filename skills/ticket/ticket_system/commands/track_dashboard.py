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
  / _compute_readiness / _get_pending_handoff_info
- lib.staleness.compute_stale_minutes（W10-114 新增分鐘粒度純函式）
- lib.ticket_loader.list_tickets

不複用：
- track_runqueue._render_list / _render_dag / _render_critical_path（格式不同）
- track_stale_list._days_since_created（粒度為日，不符）
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from ticket_system.commands.track_runqueue import (
    _compute_readiness,
    _filter_by_wave,
    _get_pending_handoff_info,
    _is_unblocked_pending,
    _priority_rank,
)
from ticket_system.lib.staleness import compute_stale_minutes
from ticket_system.lib.ticket_loader import list_tickets


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


def load_top_ready(
    tickets: List[Dict],
    top: int,
    handoff_info: Optional[Dict[str, Dict]] = None,
) -> List[Dict[str, Any]]:
    """收集 top N ready，按 priority + id 排序。

    僅 readiness == 'READY' 列入；handoff_info 用於 _compute_readiness。
    top <= 0 回傳 []。
    """
    handoff_info = handoff_info or {}
    candidates = []
    for t in tickets:
        if not _is_unblocked_pending(t):
            continue
        readiness = _compute_readiness(t, handoff_info)
        if readiness != "READY":
            continue
        candidates.append((t, readiness))
    candidates.sort(key=lambda pair: (_priority_rank(pair[0]), str(pair[0].get("id") or "")))
    if top <= 0:
        return []
    limited = candidates[:top]
    return [
        {
            "id": t.get("id"),
            "title": t.get("title") or "",
            "priority": t.get("priority") or "P?",
            "readiness": readiness,
        }
        for (t, readiness) in limited
    ]


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

    # --- Ready Top N 區塊（唯一注入 [N] 編號處）---
    lines.append(f"[Ready Top {top}]  priority 排序，可直接 claim")
    if not ready:
        lines.append("  (none)")
    else:
        for index, item in enumerate(ready, start=1):
            readiness_label = "ready"
            lines.append(
                f"  [{index}] [{item['priority']}] [{readiness_label}] "
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
) -> str:
    """渲染 JSON 格式（hook / 自動化消費）。

    stale_disabled=True → stale 欄位為 JSON null（None），非 []（D5）。
    ready 欄位加 index（從 1 起算），與 text Ready 章節編號一致。
    """
    payload = {
        "version": version,
        "wave": wave,
        "in_progress": in_progress,
        "ready": [
            {
                "index": i + 1,
                "id": item["id"],
                "priority": item["priority"],
                "readiness": "ready",
                "title": item["title"],
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

def dashboard_main(args: argparse.Namespace, version: Optional[str]) -> int:
    """執行 track dashboard 命令。

    Returns:
        0: 正常輸出
        1: 無 active version / ticket index 載入失敗
    """
    if version is None:
        sys.stderr.write("No active version detected\n")
        return 1

    try:
        all_tickets = list_tickets(version) or []
    except Exception as exc:
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

    if fmt == FORMAT_JSON:
        print(render_json(
            version=version,
            wave=wave,
            in_progress=in_progress,
            ready=ready,
            stale=stale,
            stale_threshold=stale_threshold,
            stale_disabled=no_stale,
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
        ))
    return 0


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
