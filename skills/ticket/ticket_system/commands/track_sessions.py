"""
ticket track sessions 命令（multi-PM 協調層 Phase 1，issue tarrragon/claude#77）

read-only 查詢 pm-registry.json，列出同專案 session 清單（heartbeat 新鮮度 /
認領 tickets 與 files 數）。Registry Schema 契約 v1 為 hooks 與 CLI 兩職責
共同 SSOT（本檔不得自行變更 schema，如需調整先回報並取得共識）。

設計約束：
- version-agnostic（不需 active version；操作對象為
  `<git-common-dir>/pm-registry.json`，非 ticket md）
- registry 缺檔 / JSON 解析失敗 / git 不可用：一律降級為空表 + exit 0
  （契約「損毀/缺檔處置」條款；read-only 查詢不應阻擋 PM 工作流）
- 僅列 `project` 欄位等於當前 git toplevel 絕對路徑的 session（同專案篩選）
- stale 判定：委派 `.claude/lib/pm_registry.is_fresh`（本檔原自帶獨立
  `STALE_THRESHOLD_MINUTES` 常數 + 整數分鐘比較，與 `pm_registry.is_fresh`
  的秒級比較在邊界值有分歧——30.5 分鐘時前者判 FRESH、後者判 STALE，導致
  同一票 sessions 與 runqueue 顯示矛盾。改為單一判準來源，本檔不再自帶
  常數，Phase 4 五視角審查修正）
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ticket_system.lib.claude_lib_loader import load_claude_lib, resolve_toplevel

# git 命令逾時秒數，對齊 ticket_system/lib/paths.py GIT_TOPLEVEL_TIMEOUT 慣例
_GIT_TIMEOUT = 5

FORMAT_TABLE = "table"
FORMAT_JSON = "json"


# ---------------------------------------------------------------------------
# Lib 載入：lazy import `.claude/lib/pm_registry` / `.claude/lib/git_utils`
# （收斂自五處近乎相同複本，共用實作見 ticket_system.lib.claude_lib_loader）
# ---------------------------------------------------------------------------


def _load_pm_registry():
    """Lazy 載入 `.claude/lib/pm_registry`（薄封裝，保留模組內名稱供既有
    測試 `patch.object(track_sessions, "_load_pm_registry", ...)` 直接
    覆寫）。"""
    return load_claude_lib("pm_registry")


def _load_git_utils():
    """Lazy 載入 `.claude/lib/git_utils`（薄封裝，同 `_load_pm_registry`；
    保留模組內名稱供既有測試 `patch.object(track_sessions, "_load_git_utils",
    ...)` 直接覆寫）。"""
    return load_claude_lib("git_utils")


def _run_git(*args: str) -> Optional[str]:
    """執行 git 命令，回傳去除頭尾空白的 stdout；失敗回傳 None。

    薄封裝供測試 patch（見 test_track_sessions.py），單元測試不觸碰真實
    `.git/`，僅以此函式的回傳值模擬 git 拓樸。

    優先透過 `git_utils.run_git_command`（帶 `--no-optional-locks`，
    避免與並行 PM session 的其他 git 操作競爭 `.git/index.lock`，
    IMP-046 同型風險）；`.claude/lib/` 不可用時（dev 環境結構異常）
    降級為原生 `subprocess.run`，維持本模組不強制依賴 `.claude/lib/`
    的既有韌性設計。
    """
    git_utils = _load_git_utils()
    if git_utils is not None:
        ok, output = git_utils.run_git_command(list(args), timeout=_GIT_TIMEOUT)
        return output.strip() if ok else None

    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _registry_path() -> Optional[Path]:
    """解析 pm-registry.json 路徑（Registry Schema 契約 v1）。

    `git rev-parse --git-common-dir` 於 worktree 內亦解析回主 repo `.git/`，
    使跨 worktree 的多 PM session 共用同一份 registry。git 命令失敗
    （非 git repo / git 不可用）回傳 None，呼叫端走降級路徑。
    """
    common_dir = _run_git("rev-parse", "--git-common-dir")
    if not common_dir:
        return None
    return Path(common_dir).resolve() / "pm-registry.json"


def _current_project_root() -> Optional[str]:
    """取得當前 git toplevel 絕對路徑字串，供同專案篩選比對。核心解析算法
    （git rev-parse --show-toplevel + 路徑正規化）收斂至
    `ticket_system.lib.claude_lib_loader.resolve_toplevel`；本檔繼續提供
    `_run_git` 作為執行 callable，既有測試對 `_run_git` 的直接 patch 不受
    影響。"""
    return resolve_toplevel(_run_git)


def _load_registry(path: Path) -> Optional[Dict[str, Any]]:
    """載入 registry JSON；缺檔 / 解析失敗回傳 None（呼叫端降級為空表）。"""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"[track sessions] registry 解析失敗，降級為空表: {e}\n")
        return None
    if not isinstance(data, dict):
        return None
    return data


def _parse_heartbeat_age_minutes(
    heartbeat_ts: Optional[str], now: datetime
) -> Optional[int]:
    """計算 heartbeat 與 now 的分鐘差（整數，無條件捨去）；解析失敗回傳 None。"""
    if not heartbeat_ts:
        return None
    try:
        ts = datetime.fromisoformat(str(heartbeat_ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = now - ts
    return int(delta.total_seconds() // 60)


def _build_rows(
    registry: Dict[str, Any],
    *,
    project_root: Optional[str],
    now: datetime,
    pm_registry: Any = None,
) -> List[Dict[str, Any]]:
    """依 Registry Schema 契約 v1 建立輸出列，過濾同專案 session。

    `project_root` 為 None（git 不可用）時不做同專案篩選，保留全部
    session——寧可多顯示也不可因判斷不了而整批隱藏。

    `pm_registry` 未提供時自行 lazy load（向後相容既有呼叫端，如
    `track_conflicts.py` 的 `_fresh_session_ids` 未傳此參數）。FRESH/STALE
    判定一律委派 `pm_registry.is_fresh`（單一判準來源）；模組不可用時保守
    視為 STALE（同 `is_fresh` 的 fail 語意，不可靜默呈現新鮮假象）。
    """
    if pm_registry is None:
        pm_registry = _load_pm_registry()

    sessions = registry.get("sessions")
    if not isinstance(sessions, dict):
        return []

    rows: List[Dict[str, Any]] = []
    for session_id, data in sessions.items():
        if not isinstance(data, dict):
            continue
        if project_root is not None and data.get("project") != project_root:
            continue

        heartbeat_ts = data.get("heartbeat_ts")
        age_minutes = _parse_heartbeat_age_minutes(heartbeat_ts, now)
        is_fresh = pm_registry.is_fresh(heartbeat_ts, now) if pm_registry is not None else False
        status = "FRESH" if is_fresh else "STALE"
        tickets = data.get("tickets")
        files = data.get("files")
        tickets_list = tickets if isinstance(tickets, list) else []

        # multi-PM 協調層 Phase 3：STALE session 持有的全部 tickets 即為
        # reclaimable 候選（heartbeat 逾 TTL = 該 session 對這些票的認領
        # 不再有存活佐證，父票設計要點 2）。無需逐票額外查詢，STALE 狀態
        # 本身即判準。
        reclaimable_tickets = list(tickets_list) if status == "STALE" else []

        rows.append({
            "session_id": session_id,
            "name": data.get("name") or session_id,
            "heartbeat_age_minutes": age_minutes,
            "status": status,
            "tickets_count": len(tickets_list),
            "files_count": len(files) if isinstance(files, list) else 0,
            "reclaimable_tickets": reclaimable_tickets,
        })

    rows.sort(key=lambda r: r["session_id"])
    return rows


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _render_table(rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = ["=== PM Sessions ==="]
    if not rows:
        lines.append("（無同專案 session；registry 缺檔或無資料時屬正常降級）")
        return "\n".join(lines)

    col_id = max(len("session_id"), max(len(r["session_id"]) for r in rows))
    col_name = max(len("name"), max(len(r["name"]) for r in rows))

    header = (
        f"  {'session_id':<{col_id}}  {'name':<{col_name}}  "
        f"{'age(min)':>8}  {'status':<6}  {'tickets':>7}  {'files':>5}  reclaimable"
    )
    lines.append(header)
    lines.append("  " + "-" * (col_id + col_name + 40))
    for r in rows:
        age_display = (
            "?" if r["heartbeat_age_minutes"] is None else str(r["heartbeat_age_minutes"])
        )
        reclaimable_tickets = r.get("reclaimable_tickets") or []
        reclaimable_display = ", ".join(reclaimable_tickets) if reclaimable_tickets else "-"
        lines.append(
            f"  {r['session_id']:<{col_id}}  {r['name']:<{col_name}}  "
            f"{age_display:>8}  {r['status']:<6}  {r['tickets_count']:>7}  {r['files_count']:>5}"
            f"  {reclaimable_display}"
        )
    return "\n".join(lines)


def _render_json(rows: List[Dict[str, Any]]) -> str:
    return json.dumps({"sessions": rows}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def execute_sessions(args: argparse.Namespace) -> int:
    """執行 track sessions 命令（version-agnostic，read-only）。

    Returns:
        0: 恆為 0（含降級路徑；本命令為 read-only 查詢，不應以非零 exit
           阻擋 PM 工作流，見 Registry Schema 契約 v1「損毀/缺檔處置」）
    """
    fmt = getattr(args, "format", FORMAT_TABLE) or FORMAT_TABLE
    now = getattr(args, "_now", None) or datetime.now(timezone.utc)

    registry_path = _registry_path()
    registry = _load_registry(registry_path) if registry_path is not None else None
    project_root = _current_project_root()

    rows: List[Dict[str, Any]] = []
    if registry is not None:
        rows = _build_rows(registry, project_root=project_root, now=now)

    if fmt == FORMAT_JSON:
        print(_render_json(rows))
    else:
        print(_render_table(rows))
    return 0


def register_sessions(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 sessions 子命令 parser。"""
    p = subparsers.add_parser(
        "sessions",
        help=(
            "列出同專案 pm-registry session 清單（heartbeat 新鮮度 / "
            "認領 tickets 與 files 數，read-only，multi-PM 協調層 Phase 1）"
        ),
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
