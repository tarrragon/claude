"""
ticket track onboard 命令（multi-PM 協調層 Phase 2，issue tarrragon/claude#77）

`/clear` = session 死亡 + 新生（新 session id，舊 registry entry 成孤兒）。
入場不是恢復記憶，是從世界平面重建三問：我是誰 / 同事是誰 / 我手上有
什麼。session 啟動已印 30+ hook 輸出牆，入場資訊必須收斂為單一固定值表，
不再疊加噪音（CLI-first、AI-last，AI 只讀結論不做判定）。

四節彙整，前三節資料源複用既有查詢，本命令不新增資料源：
  1. 活同事表    — 複用 `track_sessions._build_rows`（FRESH session）
  2. 孤兒 entry 表 — 同上（STALE session，heartbeat 已死但 registry entry 未回收）
  3. 髒檔歸屬     — 僅比對 in_progress 票，呈現方向為 file -> tickets
    （最長匹配前綴特異度歸屬，見 `attribute_dirty_files_by_file` docstring）
  4. 可認領建議   — 複用 `track_dashboard.load_top_ready`（同 dashboard Ready 章節）

registry 讀取一律經 `.claude/lib/pm_registry` 的 `get_registry_paths` +
`read_registry`，不重寫第三份讀取路徑（`sessions`/`conflicts` 兩命令已各
自獨立實作過一次 registry 讀取，第三次重寫會使三處讀取邏輯彼此漂移）；
stale 判定完全交由 `track_sessions._build_rows` 內部既有邏輯處理，本檔
不重複定義任何 stale 閾值常數（同一份 stale 閾值若各檔各自 hardcode
一份，未來調整閾值時容易漏改其中一處，造成三命令的 FRESH/STALE 判定
不一致）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

from ticket_system.commands.track_activity import list_dirty_files
from ticket_system.commands.track_dashboard import load_top_ready
from ticket_system.commands.track_runqueue import _get_pending_handoff_info
from ticket_system.commands.track_sessions import _build_rows
from ticket_system.lib.claude_lib_loader import (
    empty_registry_skeleton,
    load_claude_lib,
)
from ticket_system.lib.command_tracking_messages import TrackMessages
from ticket_system.lib.file_conflict import where_files as _lib_where_files
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.version import get_active_versions

FORMAT_TABLE = "table"
FORMAT_JSON = "json"

DEFAULT_READY_TOP = 5


# ---------------------------------------------------------------------------
# Lib 載入：lazy import `.claude/lib/pm_registry`（收斂自五處近乎相同複本，
# 共用實作見 ticket_system.lib.claude_lib_loader）
# ---------------------------------------------------------------------------


def load_registry() -> Dict[str, Any]:
    """讀取 pm-registry.json；不可用時回傳空結構（各節皆須優雅降級）。"""
    pm_registry = load_claude_lib("pm_registry")
    if pm_registry is None:
        return empty_registry_skeleton()
    paths = pm_registry.get_registry_paths()
    if paths is None:
        return empty_registry_skeleton()
    registry_file, _lock_file = paths
    return pm_registry.read_registry(registry_file)


# ---------------------------------------------------------------------------
# 四節資料蒐集（全複用既有查詢）
# ---------------------------------------------------------------------------

def _current_project_root_str() -> str:
    return str(get_project_root())


def collect_session_sections(
    registry: Dict[str, Any], *, project_root: str, now
) -> Dict[str, List[Dict[str, Any]]]:
    """複用 `track_sessions._build_rows`，依 status 拆為活同事表 / 孤兒 entry 表。"""
    rows = _build_rows(registry, project_root=project_root, now=now)
    colleagues = [r for r in rows if r["status"] == "FRESH"]
    orphans = [r for r in rows if r["status"] == "STALE"]
    return {"colleagues": colleagues, "orphans": orphans}


# 淺層目錄宣告（路徑段數 <= 此值，如 ".claude" 或 ".claude/skills"）視為
# 「泛目錄」——命中票數多時對「這個髒檔是誰的」缺乏鑑別力，收斂為單行摘要。
GENERIC_DIR_MAX_PARTS = 2


def _where_files(ticket: Dict[str, Any]) -> List[str]:
    """讀取 ticket 的 where.files 宣告清單。

    委派 `lib.file_conflict.where_files`（公開函式，非 `_` 前綴私有函式，
    跨模組引用不受 CQ-001 限制）：涵蓋本函式原本的舊逗號分隔字串格式
    容錯，並一併剝離逐檔讀寫意圖標記（`::read` / `::write`）。
    """
    return _lib_where_files(ticket)


def _match_specificity(dirty_path: str, declared: str) -> Optional[int]:
    """回傳宣告路徑對髒檔的匹配特異度；不匹配回傳 None。

    特異度定義（數值越大越具體，用於挑選「這個髒檔最可能是誰的」）：
      - 精確檔案相符：`sys.maxsize`（恆為最高特異度，優先於任何目錄宣告）
      - 上層目錄相符：宣告路徑的路徑段數（段數越多，目錄越深越具體）
    """
    try:
        dp = PurePosixPath(dirty_path)
        decl = PurePosixPath(declared.rstrip("/"))
    except ValueError:
        return None
    if dp == decl:
        return sys.maxsize
    if decl in dp.parents:
        return len(decl.parts)
    return None


def attribute_dirty_files_by_file(
    tickets: List[Dict[str, Any]], dirty_paths: List[str]
) -> List[Dict[str, Any]]:
    """file -> tickets 反轉呈現，採最長匹配前綴特異度歸屬。

    PM 入場真正想知道的是「這個髒檔是誰的」，非「這張票碰了哪些髒檔」
    （後者在票數多、宣告目錄淺時會被噪音放大）。對每個髒檔，找出所有
    命中的票並取「特異度」最高者（精確檔案 > 深層目錄 > 淺層目錄，見
    `_match_specificity`），僅保留在最高特異度上仍命中的票。

    若最高特異度落在「泛目錄」層級（路徑段數 <= GENERIC_DIR_MAX_PARTS，
    如僅宣告 ".claude/"）且命中票數 > 1，代表這些宣告本身無鑑別力，收斂
    為單行摘要（`summary` 欄位），不逐票展開（`tickets` 為 None）；否則
    回傳命中票 ID 清單（`tickets` 非 None，`summary` 為 None）。

    Returns:
        list[dict]：每筆為 `{"file": str, "tickets": list[str] | None,
        "summary": str | None}`，僅含至少有一票命中的髒檔。
    """
    result: List[Dict[str, Any]] = []
    for dirty in dirty_paths:
        best_per_ticket: Dict[str, int] = {}
        for t in tickets:
            tid = t.get("id")
            if not tid:
                continue
            best_spec: Optional[int] = None
            for declared in _where_files(t):
                spec = _match_specificity(dirty, declared)
                if spec is not None and (best_spec is None or spec > best_spec):
                    best_spec = spec
            if best_spec is not None:
                best_per_ticket[tid] = best_spec

        if not best_per_ticket:
            continue

        max_spec = max(best_per_ticket.values())
        winners = sorted(tid for tid, spec in best_per_ticket.items() if spec == max_spec)

        is_generic_dir = max_spec != sys.maxsize and max_spec <= GENERIC_DIR_MAX_PARTS
        if is_generic_dir and len(winners) > 1:
            result.append({
                "file": dirty,
                "tickets": None,
                "summary": f"泛目錄宣告命中 {len(winners)} 票（無鑑別力）",
            })
        else:
            result.append({"file": dirty, "tickets": winners, "summary": None})
    return result


def collect_dirty_attribution(
    tickets: List[Dict[str, Any]], project_root: Path
) -> List[Dict[str, Any]]:
    """僅比對 in_progress 票的髒檔歸屬（file -> tickets 方向）。

    先前版本比對全部 status（completed/pending 亦納入），與章節語意「進行
    式工作歸屬」相反，且審查實測噪音被放大（2 髒檔歸 20 票，抽查 5 張
    無一 in_progress）。
    """
    dirty_paths = list_dirty_files(cwd=str(project_root))
    if not dirty_paths:
        return []
    in_progress_tickets = [t for t in tickets if t.get("status") == "in_progress"]
    return attribute_dirty_files_by_file(in_progress_tickets, dirty_paths)


def collect_orphaned_dirty_files(
    tickets: List[Dict[str, Any]], project_root: Path
) -> List[str]:
    """dirty_paths 扣除已被 in_progress 票命中者的補集（無主髒檔）。

    僅列出路徑，不附任何票 ID 推測：擴大比對範圍（含 completed/pending 票
    where.files）曾實測對「檔案即票面自身」的情況給出錯誤歸屬（誤指某
    ticket md 指向兩張無關票），比零訊號更危險且重現既有已修過的噪音根因
    （見本票 why）。本函式與 `collect_dirty_attribution` 共用同一組
    in_progress 命中計算，僅呈現方向不同（未命中 vs 已命中）。
    """
    dirty_paths = list_dirty_files(cwd=str(project_root))
    if not dirty_paths:
        return []
    in_progress_tickets = [t for t in tickets if t.get("status") == "in_progress"]
    attribution = attribute_dirty_files_by_file(in_progress_tickets, dirty_paths)
    attributed_files = {item["file"] for item in attribution}
    return [path for path in dirty_paths if path not in attributed_files]


def collect_ready_suggestions(
    tickets: List[Dict[str, Any]], top: int
) -> List[Dict[str, Any]]:
    """複用 `track_dashboard.load_top_ready`（同 dashboard Ready 章節排序邏輯）。"""
    handoff_info = _get_pending_handoff_info()
    return load_top_ready(tickets, top=top, handoff_info=handoff_info)


def _gather_tickets(
    explicit_version: Optional[str],
) -> List[Dict[str, Any]]:
    if explicit_version:
        versions = [explicit_version]
    else:
        versions = get_active_versions() or []
    aggregated: List[Dict[str, Any]] = []
    for version in versions:
        aggregated.extend(list_tickets(version) or [])
    return aggregated


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _render_session_row(r: Dict[str, Any]) -> str:
    age = "?" if r["heartbeat_age_minutes"] is None else str(r["heartbeat_age_minutes"])
    return (
        f"  {r['session_id']}  {r['name']}  age={age}min  "
        f"tickets={r['tickets_count']}  files={r['files_count']}"
    )


def _render_table(
    colleagues: List[Dict[str, Any]],
    orphans: List[Dict[str, Any]],
    dirty_attribution: List[Dict[str, Any]],
    ready: List[Dict[str, Any]],
    orphaned_dirty_files: Optional[List[str]] = None,
) -> str:
    lines: List[str] = ["=== PM Onboard ===", ""]

    lines.append(f"[活同事] {len(colleagues)} session(s)")
    if not colleagues:
        lines.append("  （無活同事）")
    else:
        for r in colleagues:
            lines.append(_render_session_row(r))
    lines.append("")

    lines.append(f"[孤兒 entry] {len(orphans)} session(s)")
    if not orphans:
        lines.append("  （無孤兒 entry）")
    else:
        for r in orphans:
            lines.append(_render_session_row(r))
    lines.append("")

    lines.append(f"[髒檔歸屬] {len(dirty_attribution)} file(s)（僅 in_progress 票）")
    if not dirty_attribution:
        lines.append("  （無髒檔）")
    else:
        for item in dirty_attribution:
            if item.get("tickets") is not None:
                lines.append(f"  {item['file']}: {', '.join(item['tickets'])}")
            else:
                lines.append(f"  {item['file']}: {item['summary']}")
    lines.append("")

    if orphaned_dirty_files:
        lines.append(
            f"{TrackMessages.ONBOARD_ORPHAN_DIRTY_HEADER} "
            f"{len(orphaned_dirty_files)} file(s) "
            f"{TrackMessages.ONBOARD_ORPHAN_DIRTY_HINT}"
        )
        for path in orphaned_dirty_files:
            lines.append(f"  {path}")
        lines.append("")

    lines.append(f"[可認領建議 Top {len(ready)}]")
    if not ready:
        lines.append("  （無可認領建議）")
    else:
        for index, item in enumerate(ready, start=1):
            readiness_label = item.get("readiness", "ready").lower()
            lines.append(
                f"  [{index}] [{item['priority']}] [{readiness_label}] "
                f"{item['id']}  {item['title']}"
            )

    return "\n".join(lines)


def _render_json(
    colleagues: List[Dict[str, Any]],
    orphans: List[Dict[str, Any]],
    dirty_attribution: List[Dict[str, Any]],
    ready: List[Dict[str, Any]],
    orphaned_dirty_files: Optional[List[str]] = None,
) -> str:
    payload = {
        "colleagues": colleagues,
        "orphans": orphans,
        "dirty_attribution": dirty_attribution,
        "ready": ready,
    }
    if orphaned_dirty_files:
        payload["orphaned_dirty_files"] = orphaned_dirty_files
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def execute_onboard(args: argparse.Namespace) -> int:
    """執行 track onboard 命令（version-agnostic，read-only，四節彙整）。"""
    fmt = getattr(args, "format", FORMAT_TABLE) or FORMAT_TABLE
    explicit_version = getattr(args, "version", None)
    top = getattr(args, "top", DEFAULT_READY_TOP) or DEFAULT_READY_TOP
    now = getattr(args, "_now", None)

    tickets = _gather_tickets(explicit_version)
    project_root = get_project_root()

    registry = load_registry()
    now = now or datetime.now(timezone.utc)
    sessions = collect_session_sections(
        registry, project_root=_current_project_root_str(), now=now
    )
    dirty_attribution = collect_dirty_attribution(tickets, project_root)
    orphaned_dirty_files = collect_orphaned_dirty_files(tickets, project_root)
    ready = collect_ready_suggestions(tickets, top=top)

    if fmt == FORMAT_JSON:
        print(_render_json(
            sessions["colleagues"], sessions["orphans"], dirty_attribution, ready,
            orphaned_dirty_files=orphaned_dirty_files,
        ))
    else:
        print(_render_table(
            sessions["colleagues"], sessions["orphans"], dirty_attribution, ready,
            orphaned_dirty_files=orphaned_dirty_files,
        ))
    return 0


def register_onboard(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 onboard 子命令 parser。"""
    p = subparsers.add_parser(
        "onboard",
        help=(
            "PM 入場彙整：活同事 / 孤兒 entry / 髒檔歸屬 / 可認領建議四節，"
            "全複用既有查詢（multi-PM 協調層 Phase 2，入場五步 step 4）"
        ),
    )
    p.add_argument(
        "--version",
        default=None,
        help="指定版本（覆蓋自動偵測 active 版本）",
    )
    p.add_argument(
        "--all",
        action="store_true",
        default=False,
        help=TrackMessages.ARG_ALL_COMPAT,
    )
    p.add_argument(
        "--top",
        type=int,
        default=DEFAULT_READY_TOP,
        help=f"可認領建議章節列數上限（預設 {DEFAULT_READY_TOP}）",
    )
    p.add_argument(
        "--format",
        choices=[FORMAT_TABLE, FORMAT_JSON],
        default=FORMAT_TABLE,
        help=f"輸出格式（預設 {FORMAT_TABLE}）",
    )
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
