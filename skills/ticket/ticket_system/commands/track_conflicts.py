"""
ticket track conflicts 命令（multi-PM 協調層 Phase 2，issue tarrragon/claude#77）

Phase 2 盲測實證：宣告 where.files 吻合度僅 3/10，七成 completed 票的實際
commit 超出宣告範圍，主導缺漏是「宣告實作檔、漏宣告伴生測試檔與關聯模組」。
純宣告值交集判定的錯誤方向是 false negative（宣告互斥、實際相撞），因此
本命令內建 impl→test 擴張啟發式：對每個宣告的實作檔路徑，額外推導其可能
的伴生測試檔路徑一併納入交集判定，擴大偵測面。

判定規則：
  1. pending/in_progress 票兩兩比對 where.files（原始宣告 + 啟發式衍生）
  2. 路徑交集用 PurePosixPath 前綴比對（精確相符或互為上層目錄），禁用
     string startswith（避免 "lib/foo" 誤命中 "lib/foobar.dart"）
  3. 與 pm-registry 的 files 欄位交叉比對（僅採 FRESH session 宣告，STALE
     殘留 entry 排除），兩源不一致時 stderr 警告（issue #77 premortem 1：
     registry 與票面漂移需可觀測）
  4. exit code 表達判定：0 無衝突 / 1 有衝突（registry 警告不影響 exit code）

registry 讀取一律經 `.claude/lib/pm_registry` 的 `get_registry_paths` +
`read_registry`，不重寫第三份讀取路徑（lazy import 經
`ticket_system.lib.claude_lib_loader` 共用實作）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ticket_system.commands.track_sessions import _build_rows
from ticket_system.lib.claude_lib_loader import (
    current_project_root,
    empty_registry_skeleton,
    load_claude_lib,
)
from ticket_system.lib.command_tracking_messages import TrackMessages
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.version import get_active_versions

FORMAT_TABLE = "table"
FORMAT_JSON = "json"

_CONFLICT_STATUSES = {"pending", "in_progress"}


# ---------------------------------------------------------------------------
# Lib 載入：lazy import `.claude/lib/pm_registry`（收斂自五處近乎相同複本，
# 共用實作見 ticket_system.lib.claude_lib_loader）
# ---------------------------------------------------------------------------


def load_registry() -> Dict[str, Any]:
    """讀取 pm-registry.json；不可用（非 git 環境 / 模組載入失敗）時回傳空結構。"""
    pm_registry = load_claude_lib("pm_registry")
    if pm_registry is None:
        return empty_registry_skeleton()
    paths = pm_registry.get_registry_paths()
    if paths is None:
        return empty_registry_skeleton()
    registry_file, _lock_file = paths
    return pm_registry.read_registry(registry_file)


# ---------------------------------------------------------------------------
# 路徑判定（AC-3：與 `ticket track runqueue --groups` 共用同一實作，抽至
# `ticket_system/lib/file_conflict.py`，本檔僅直接使用其公開名稱）
# ---------------------------------------------------------------------------

from ticket_system.lib.file_conflict import (
    compute_pairwise_conflicts,
    compute_targeted_conflicts,
    expand_files,
    files_intersect,
    is_directory_declaration,
    write_files,
)


# ---------------------------------------------------------------------------
# 衝突判定
# ---------------------------------------------------------------------------

def find_conflicts(
    tickets: List[Dict[str, Any]], project_root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """篩選 pending/in_progress 票後，委派 `file_conflict.compute_pairwise_conflicts`
    做兩兩 where.files 交集判定（含擴張啟發式）。

    `project_root` 供 impl->test 啟發式驗證真實 `tests/` 目錄結構；為 None
    時該啟發式停用，僅比對原始宣告值。
    """
    filtered = [t for t in tickets if t.get("status") in _CONFLICT_STATUSES]
    return compute_pairwise_conflicts(filtered, project_root)


def find_targeted_conflicts(
    tickets: List[Dict[str, Any]],
    target_ids: Set[str],
    project_root: Optional[Path] = None,
    both_sides: bool = False,
) -> List[Dict[str, Any]]:
    """`--for`/`--among` 針對性模式版本：篩選 pending/in_progress 票後，
    委派 `file_conflict.compute_targeted_conflicts`，僅比對與 `target_ids`
    相關的配對（O(k·n) 而非全量 O(n^2)，見該函式 docstring）。
    """
    filtered = [t for t in tickets if t.get("status") in _CONFLICT_STATUSES]
    return compute_targeted_conflicts(
        filtered, target_ids, project_root, both_sides=both_sides
    )


# ---------------------------------------------------------------------------
# registry 交叉比對
# ---------------------------------------------------------------------------

def _fresh_session_ids(
    registry: Dict[str, Any], *, project_root: Optional[str], now: datetime
) -> Set[str]:
    """複用 `track_sessions._build_rows` 判定 FRESH session id 集合。

    FRESH/STALE 完全交由 `_build_rows` 內部既有邏輯計算（同 track_onboard.py
    的複用方式）：本檔不定義任何 stale 閾值常數，避免與其他命令各自
    hardcode 一份導致未來調整閾值時彼此漂移。
    """
    rows = _build_rows(registry, project_root=project_root, now=now)
    return {r["session_id"] for r in rows if r["status"] == "FRESH"}


def _ticket_registry_files(
    registry: Dict[str, Any], allowed_session_ids: Set[str]
) -> Dict[str, Set[str]]:
    """由 registry 建立 ticket_id -> FRESH session 宣告的 files 聯集。

    僅採 `allowed_session_ids`（FRESH session）：STALE session 為死亡/已
    離線的殘留 entry，其宣告不代表當下真實仍在進行的認領範圍，納入比對
    會產生誤報（把已死 session 的舊宣告誤判為與現行票衝突）。
    """
    sessions = registry.get("sessions") if isinstance(registry, dict) else None
    mapping: Dict[str, Set[str]] = {}
    if not isinstance(sessions, dict):
        return mapping
    for session_id, data in sessions.items():
        if session_id not in allowed_session_ids:
            continue
        if not isinstance(data, dict):
            continue
        for tid in data.get("tickets") or []:
            mapping.setdefault(tid, set()).update(data.get("files") or [])
    return mapping


def cross_check_registry(
    tickets: List[Dict[str, Any]],
    registry: Dict[str, Any],
    *,
    project_root: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[str]:
    """比對 in_progress 票的 where.files 與 registry 對應 FRESH session 的 files。

    兩源皆非空且無任何交集時視為不一致，回傳警告訊息清單（呼叫端負責輸出
    至 stderr，本函式維持純函式便於測試）。僅採 FRESH session 宣告
    （STALE session 排除，見 `_ticket_registry_files`）。
    """
    now = now or datetime.now(timezone.utc)
    fresh_ids = _fresh_session_ids(registry, project_root=project_root, now=now)
    ticket_registry_files = _ticket_registry_files(registry, fresh_ids)
    warnings: List[str] = []
    for t in tickets:
        if t.get("status") != "in_progress":
            continue
        tid = t.get("id") or ""
        registry_files = ticket_registry_files.get(tid)
        if not registry_files:
            continue
        declared = set(write_files(t))
        if not declared:
            continue
        if not any(files_intersect(rf, df) for rf in registry_files for df in declared):
            warnings.append(
                f"registry/ticket file 宣告不一致：{tid} "
                f"registry.files={sorted(registry_files)} vs write_files={sorted(declared)}"
                f"（衝突判定僅採 write 集合；請校正票面宣告或重跑 claim）"
            )
    return warnings


# ---------------------------------------------------------------------------
# 資料蒐集
# ---------------------------------------------------------------------------

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

def _render_table(conflicts: List[Dict[str, Any]]) -> str:
    lines: List[str] = ["=== File Conflicts ==="]
    if not conflicts:
        lines.append("（無衝突）")
        return "\n".join(lines)
    for c in conflicts:
        tag = " [heuristic]" if c["heuristic_only"] else ""
        files_repr = ", ".join(c["matched_files"])
        lines.append(f"  {c['ticket_a']} <-> {c['ticket_b']}{tag}: {files_repr}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 針對性查詢（--for / --among）
# ---------------------------------------------------------------------------


def _is_directory_level_hit(
    conflict: Dict[str, Any], project_root: Optional[Path]
) -> bool:
    """判定衝突對是否命中「目錄層級宣告」（宣告值為目錄而非單一檔案，
    如 `.claude/hooks/` 對任何位於該目錄下的檔案宣告皆會匹配，噪音來源）。

    與 `heuristic_only`（impl->test 擴張啟發式衍生候選命中）語意不同：
    目錄宣告即使是原始宣告值（非衍生候選）仍可能命中，`heuristic_only`
    對此類命中通常回傳 False（見 `compute_pairwise_conflicts`），故需另
    以 `is_directory_declaration` 逐一檢查 `matched_files` 涉及的路徑。
    """
    for entry in conflict["matched_files"]:
        for path in entry.split(" ~ "):
            if is_directory_declaration(path, project_root):
                return True
    return False


def _drop_directory_level_hits(
    conflicts: List[Dict[str, Any]], project_root: Optional[Path]
) -> List[Dict[str, Any]]:
    """濾除目錄層級宣告命中（--for/--among 預設隱藏，需 --include-heuristic 開啟）。"""
    return [c for c in conflicts if not _is_directory_level_hit(c, project_root)]


def _render_json(conflicts: List[Dict[str, Any]]) -> str:
    return json.dumps({"conflicts": conflicts}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def execute_conflicts(args: argparse.Namespace) -> int:
    """執行 track conflicts 命令（version-agnostic）。

    Returns:
        0: 無衝突
        1: 偵測到衝突（registry 警告不影響此判定）
    """
    fmt = getattr(args, "format", FORMAT_TABLE) or FORMAT_TABLE
    explicit_version = getattr(args, "version", None)
    for_ticket = getattr(args, "for_ticket", None)
    among_arg = getattr(args, "among_tickets", None)
    include_heuristic = getattr(args, "include_heuristic", False)

    tickets = _gather_tickets(explicit_version)
    project_root = get_project_root()

    # 針對性查詢：--for / --among 二擇一（互斥，argparse 層不強制，此處
    # 以 --among 優先——同時提供兩者屬呼叫端誤用，選較窄的語意較安全）。
    # 兩者皆命中純目錄層級 heuristic 的命中預設隱藏，需顯式 --include-heuristic
    # 開啟；未帶 --for/--among 時走既有全量兩兩比對（回歸不變）。
    # 針對性模式改走 find_targeted_conflicts（O(k·n) 而非全量 O(n^2)），
    # 不再對全量結果事後過濾（原 _filter_for/_filter_among 已隨此變更移除，
    # 過濾邊界改由 compute_targeted_conflicts 的 both_sides 參數直接決定）。
    if among_arg:
        among_ids = {i.strip() for i in among_arg.split(",") if i.strip()}
        conflicts = find_targeted_conflicts(
            tickets, among_ids, project_root, both_sides=True
        )
        if not include_heuristic:
            conflicts = _drop_directory_level_hits(conflicts, project_root)
    elif for_ticket:
        conflicts = find_targeted_conflicts(
            tickets, {for_ticket}, project_root, both_sides=False
        )
        if not include_heuristic:
            conflicts = _drop_directory_level_hits(conflicts, project_root)
    else:
        conflicts = find_conflicts(tickets, project_root)

    registry = load_registry()
    now = getattr(args, "_now", None) or datetime.now(timezone.utc)
    # registry `project` 欄位比對鍵須為純 git-toplevel 語意（同 Registry
    # Schema 契約 v1），與上方 find_conflicts 所需的 Path 物件用途不同——
    # 不可共用 get_project_root()（其 CLAUDE_PROJECT_DIR 優先序會使比對鍵
    # 與其他純 git-toplevel 解析的呼叫端分歧）。
    for warning in cross_check_registry(
        tickets, registry, project_root=current_project_root(), now=now
    ):
        sys.stderr.write(f"[track conflicts] {warning}\n")

    if fmt == FORMAT_JSON:
        print(_render_json(conflicts))
    else:
        print(_render_table(conflicts))

    return 1 if conflicts else 0


def register_conflicts(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 conflicts 子命令 parser。"""
    p = subparsers.add_parser(
        "conflicts",
        help=(
            "偵測 pending/in_progress 票 where.files 交集（含 impl->test "
            "擴張啟發式，exit code 表達判定，multi-PM 協調層 Phase 2）"
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
        "--format",
        choices=[FORMAT_TABLE, FORMAT_JSON],
        default=FORMAT_TABLE,
        help=f"輸出格式（預設 {FORMAT_TABLE}）",
    )
    p.add_argument(
        "--for",
        dest="for_ticket",
        default=None,
        metavar="TICKET_ID",
        help="僅列出指定票與其他 pending/in_progress 票的衝突對（與 --among 互斥，--among 優先）",
    )
    p.add_argument(
        "--among",
        dest="among_tickets",
        default=None,
        metavar="ID1,ID2,...",
        help="僅比對指定票組彼此之間（逗號分隔，不含票組外的票）",
    )
    p.add_argument(
        "--include-heuristic",
        action="store_true",
        default=False,
        help="--for/--among 模式下納入純目錄層級 heuristic 命中（預設隱藏）",
    )
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
