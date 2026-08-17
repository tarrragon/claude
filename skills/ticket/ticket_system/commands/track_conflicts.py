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
`read_registry`，不重寫第三份讀取路徑（比照 track_hook_health.py 的
`_find_claude_dir()` + sys.path 模式）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Set, Tuple

from ticket_system.commands.track_sessions import _build_rows
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.version import get_active_versions

FORMAT_TABLE = "table"
FORMAT_JSON = "json"

_CONFLICT_STATUSES = {"pending", "in_progress"}


# ---------------------------------------------------------------------------
# Lib 載入：lazy import `.claude/lib/pm_registry`（比照 track_hook_health.py）
# ---------------------------------------------------------------------------

_PM_REGISTRY_MODULE = None


def _find_claude_dir() -> Optional[Path]:
    """依優先序定位 .claude/ 目錄（同 track_hook_health.py 的搜尋策略）。"""
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        candidate = Path(env_root) / ".claude"
        if (candidate / "lib" / "pm_registry.py").is_file():
            return candidate

    for d in [Path.cwd(), *Path.cwd().parents]:
        candidate = d / ".claude"
        if (candidate / "lib" / "pm_registry.py").is_file():
            return candidate

    try:
        dev_candidate = Path(__file__).resolve().parents[4]
        if (dev_candidate / "lib" / "pm_registry.py").is_file():
            return dev_candidate
    except (IndexError, OSError):
        pass

    return None


def _load_pm_registry():
    """Lazy 載入 .claude/lib/pm_registry（首次呼叫時 import + 快取）。"""
    global _PM_REGISTRY_MODULE
    if _PM_REGISTRY_MODULE is not None:
        return _PM_REGISTRY_MODULE

    claude_dir = _find_claude_dir()
    if claude_dir is None:
        return None

    if str(claude_dir) not in sys.path:
        sys.path.insert(0, str(claude_dir))
    from lib import pm_registry  # noqa: WPS433

    _PM_REGISTRY_MODULE = pm_registry
    return pm_registry


def load_registry() -> Dict[str, Any]:
    """讀取 pm-registry.json；不可用（非 git 環境 / 模組載入失敗）時回傳空結構。"""
    pm_registry = _load_pm_registry()
    if pm_registry is None:
        return {"schema_version": 0, "sessions": {}}
    paths = pm_registry.get_registry_paths()
    if paths is None:
        return {"schema_version": 0, "sessions": {}}
    registry_file, _lock_file = paths
    return pm_registry.read_registry(registry_file)


# ---------------------------------------------------------------------------
# 路徑判定
# ---------------------------------------------------------------------------

def _where_files(ticket: Dict[str, Any]) -> List[str]:
    where = ticket.get("where") or {}
    files = where.get("files") if isinstance(where, dict) else None
    if isinstance(files, str):
        return [f.strip() for f in files.split(",") if f.strip()]
    if isinstance(files, list):
        return [str(f) for f in files]
    return []


def _files_intersect(path_a: str, path_b: str) -> bool:
    """PurePosixPath 前綴比對：精確相符，或其中一者為另一者的上層目錄前綴。

    非 string startswith——"lib/foo" 與 "lib/foobar.dart" 字串前綴相符但路徑
    段不同層級，不應誤判為交集。
    """
    try:
        pa = PurePosixPath(path_a.rstrip("/"))
        pb = PurePosixPath(path_b.rstrip("/"))
    except ValueError:
        return path_a == path_b
    if pa == pb:
        return True
    return pa in pb.parents or pb in pa.parents


def _find_nearest_tests_dir(file_path: str, project_root: Path) -> Optional[PurePosixPath]:
    """向上尋找最近的實際存在之 `tests/` 兄弟目錄（掃描真實檔案系統）。

    本專案 `tests/` 目錄一律為套件根目錄的兄弟層（如 `ticket_system/tests/`
    對應 `ticket_system/commands/`、`ticket_system/lib/` 等子目錄下的模組；
    `hooks/tests/` 對應 `hooks/` 下直接放置的檔案），並非緊鄰檔案自身目錄下
    的子目錄——本專案 14 個 `tests/` 目錄實測全數符合此結構，先前「模組同層
    插 `tests/` 子目錄」的假設全為反例（審查實測）。

    逐層往上檢查每個祖先目錄是否有 `tests` 兄弟目錄實際存在，找到最近
    （最深）的一個即回傳；專案內找不到任何符合的 `tests/` 兄弟目錄時回傳
    None（不猜測，寧可漏檢也不可再犯假設同層子目錄的錯誤）。
    """
    p = PurePosixPath(file_path.rstrip("/"))
    current = p.parent
    while True:
        candidate = current / "tests"
        if (project_root / candidate).is_dir():
            return candidate
        if not current.parts:
            return None
        current = current.parent


def _derive_test_candidates(path: str, project_root: Optional[Path] = None) -> List[str]:
    """impl->test 擴張啟發式：由實作檔路徑推導可能的伴生測試檔路徑。

    僅覆蓋本專案已知兩種慣例，不窮舉所有語言慣例：
      - Dart：`lib/...` -> `test/..._test.dart`
      - Python：`.../X.py`（非 test_*.py / conftest.py）-> 實際存在的最近
        `tests/` 兄弟目錄下 `test_X.py`（見 `_find_nearest_tests_dir`）

    未命中任何慣例、或 Python 分支找不到真實存在的 `tests/` 目錄時回傳
    空清單（不衍生候選，維持原宣告值）。`project_root` 為 None 時 Python
    分支無法驗證真實目錄結構，同樣不猜測（寧缺勿錯）。
    """
    p = PurePosixPath(path.rstrip("/"))
    candidates: List[str] = []

    if p.suffix == ".dart" and p.parts and p.parts[0] == "lib":
        rest_parts = p.parts[1:]
        if rest_parts:
            stem = PurePosixPath(rest_parts[-1]).stem
            candidate = PurePosixPath("test", *rest_parts[:-1], f"{stem}_test.dart")
            candidates.append(str(candidate))

    if p.suffix == ".py" and not p.stem.startswith("test_") and p.stem != "conftest":
        if project_root is not None:
            tests_dir = _find_nearest_tests_dir(path, project_root)
            if tests_dir is not None:
                candidates.append(str(tests_dir / f"test_{p.stem}.py"))

    return candidates


def expand_files(declared: List[str], project_root: Optional[Path] = None) -> List[str]:
    """回傳宣告清單 + 啟發式衍生候選的去重聯集（保序）。"""
    expanded: List[str] = list(declared)
    for f in declared:
        expanded.extend(_derive_test_candidates(f, project_root))
    seen: Set[str] = set()
    result: List[str] = []
    for f in expanded:
        if f not in seen:
            seen.add(f)
            result.append(f)
    return result


# ---------------------------------------------------------------------------
# 衝突判定
# ---------------------------------------------------------------------------

def find_conflicts(
    tickets: List[Dict[str, Any]], project_root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """兩兩比對票的 where.files（含擴張啟發式），回傳衝突對清單。

    `project_root` 供 impl->test 啟發式驗證真實 `tests/` 目錄結構（見
    `_derive_test_candidates`）；為 None 時該啟發式停用，僅比對原始宣告值。
    """
    entries: List[Tuple[str, List[str], List[str]]] = []
    for t in tickets:
        if t.get("status") not in _CONFLICT_STATUSES:
            continue
        declared = _where_files(t)
        if not declared:
            continue
        entries.append((t.get("id") or "", declared, expand_files(declared, project_root)))

    conflicts: List[Dict[str, Any]] = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            id_a, declared_a, expanded_a = entries[i]
            id_b, declared_b, expanded_b = entries[j]
            matched_pairs: List[Tuple[str, str]] = []
            heuristic_only = True
            for fa in expanded_a:
                for fb in expanded_b:
                    if _files_intersect(fa, fb):
                        matched_pairs.append((fa, fb))
                        if fa in declared_a and fb in declared_b:
                            heuristic_only = False
            if matched_pairs:
                matched_display = sorted({
                    fa if fa == fb else f"{fa} ~ {fb}" for fa, fb in matched_pairs
                })
                conflicts.append({
                    "ticket_a": id_a,
                    "ticket_b": id_b,
                    "matched_files": matched_display,
                    "heuristic_only": heuristic_only,
                })
    conflicts.sort(key=lambda c: (c["ticket_a"], c["ticket_b"]))
    return conflicts


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
        declared = set(_where_files(t))
        if not declared:
            continue
        if not any(_files_intersect(rf, df) for rf in registry_files for df in declared):
            warnings.append(
                f"registry/ticket file 宣告不一致：{tid} "
                f"registry.files={sorted(registry_files)} vs where.files={sorted(declared)}"
                "（衝突判定僅採 where.files；請校正票面宣告或重跑 claim）"
            )
    return warnings


# ---------------------------------------------------------------------------
# 資料蒐集
# ---------------------------------------------------------------------------

def _gather_tickets(
    explicit_version: Optional[str], all_versions: bool
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
    all_versions = bool(getattr(args, "all", False))

    tickets = _gather_tickets(explicit_version, all_versions)
    project_root = get_project_root()
    conflicts = find_conflicts(tickets, project_root)

    registry = load_registry()
    now = getattr(args, "_now", None) or datetime.now(timezone.utc)
    for warning in cross_check_registry(
        tickets, registry, project_root=str(project_root), now=now
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
        help="相容保留旗標：預設已掃描全部 active 版本，本旗標目前與預設行為無差異",
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
