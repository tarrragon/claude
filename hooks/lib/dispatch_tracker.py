"""
Active Dispatch Tracker 共用模組

追蹤背景代理人的派發狀態，防止 PM 重複執行同一 Ticket。

狀態檔案：.claude/dispatch-active.json

公開 API：
- record_dispatch: 記錄新派發
- clear_dispatch: 清理已完成派發
- get_active_dispatches: 取得所有活躍派發
- is_file_under_dispatch: 檢查檔案是否在派發中
- cleanup_expired: 清理超時記錄
- detect_orphan_branches: 偵測 orphan worktree 分支

Ticket: 0.17.2-W7-004
"""

import fcntl
import json
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

STATE_FILE_RELATIVE = ".claude/dispatch-active.json"
LOCK_FILE_RELATIVE = ".claude/dispatch-active.lock"

# 記憶體快取：避免同一 Hook 執行中重複讀取 JSON 檔案
# 使用檔案 mtime 判斷是否需要重新讀取（W8-007）
_state_cache: Dict = {"data": None, "mtime": 0.0}


def reset_cache() -> None:
    """重設記憶體快取（供測試使用）。"""
    _state_cache["data"] = None
    _state_cache["mtime"] = 0.0


def get_state_file_path(project_root: Path) -> Path:
    """取得狀態檔路徑"""
    return project_root / STATE_FILE_RELATIVE


@contextmanager
def _state_lock(project_root: Path):
    """排他鎖保護 read-modify-write 週期，防止並行寫入資料遺失。"""
    lock_file = project_root / LOCK_FILE_RELATIVE
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = lock_file.open("w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def _read_state(project_root: Path) -> Dict:
    """讀取狀態檔。檔案不存在或格式錯誤時回傳空結構。

    使用檔案 mtime 驅動的記憶體快取：檔案未變更時直接回傳快取，
    避免同一 session 中多次 Edit/Write 觸發重複 JSON 解析（W8-007）。
    """
    state_file = get_state_file_path(project_root)
    if not state_file.exists():
        return {"dispatches": []}
    try:
        current_mtime = state_file.stat().st_mtime
        if _state_cache["data"] is not None and _state_cache["mtime"] == current_mtime:
            return _state_cache["data"]

        content = state_file.read_text(encoding="utf-8")
        data = json.loads(content)
        if not isinstance(data, dict) or "dispatches" not in data:
            return {"dispatches": []}

        _state_cache["data"] = data
        _state_cache["mtime"] = current_mtime
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"[dispatch_tracker] _read_state: 狀態檔讀取失敗 ({state_file}): {e}", file=sys.stderr)
        return {"dispatches": []}


def _write_state(project_root: Path, state: Dict) -> None:
    """寫入狀態檔。自動建立父目錄。寫入後使快取失效。"""
    state_file = get_state_file_path(project_root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # 寫入後使快取失效，下次 _read_state 會重新讀取（W8-007）
    _state_cache["data"] = None
    _state_cache["mtime"] = 0.0


def record_dispatch(
    project_root: Path,
    agent_description: str,
    ticket_id: str = "",
    files: Optional[List[str]] = None,
    branch_name: str = "",
) -> None:
    """記錄一個新的派發。寫入 dispatch-active.json。

    Args:
        project_root: 專案根目錄
        agent_description: 代理人描述（用於比對清理）
        ticket_id: 關聯的 Ticket ID
        files: 代理人處理的檔案清單
        branch_name: worktree 分支名稱（用於 orphan 偵測精確比對）
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        entry = {
            "agent_description": agent_description,
            "ticket_id": ticket_id,
            "files": files or [],
            "branch_name": branch_name,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
        }
        state["dispatches"].append(entry)
        _write_state(project_root, state)


def clear_dispatch(project_root: Path, agent_description: str) -> bool:
    """清理已完成的派發。依 agent_description 比對。

    Args:
        project_root: 專案根目錄
        agent_description: 要清理的代理人描述

    Returns:
        是否成功找到並清理記錄
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        original_count = len(state["dispatches"])
        state["dispatches"] = [
            d for d in state["dispatches"]
            if d.get("agent_description") != agent_description
        ]
        if len(state["dispatches"]) < original_count:
            _write_state(project_root, state)
            return True
        return False


def get_active_dispatches(project_root: Path) -> List[Dict]:
    """取得所有活躍的派發記錄。

    Returns:
        派發記錄清單
    """
    state = _read_state(project_root)
    return state["dispatches"]


def is_file_under_dispatch(project_root: Path, filepath: str) -> Optional[Dict]:
    """檢查檔案是否正在被派發的代理人處理。

    Args:
        project_root: 專案根目錄
        filepath: 要檢查的檔案路徑

    Returns:
        匹配的 dispatch 記錄，或 None
    """
    dispatches = get_active_dispatches(project_root)
    for dispatch in dispatches:
        if filepath in dispatch.get("files", []):
            return dispatch
    return None


def _is_dispatch_expired(dispatch: Dict, now: datetime, max_age_hours: int) -> bool:
    """判斷單一派發記錄是否已超時。解析失敗視為超時。"""
    dispatched_at_str = dispatch.get("dispatched_at", "")
    try:
        dispatched_at = datetime.fromisoformat(dispatched_at_str)
        if dispatched_at.tzinfo is None:
            dispatched_at = dispatched_at.replace(tzinfo=timezone.utc)
        return (now - dispatched_at).total_seconds() / 3600 > max_age_hours
    except (ValueError, TypeError) as e:
        print(f"[dispatch_tracker] cleanup_expired: 時間解析失敗 (dispatched_at='{dispatched_at_str}'): {e}", file=sys.stderr)
        return True


def cleanup_expired(project_root: Path, max_age_hours: int = 4) -> int:
    """清理超時的派發記錄（防止遺留）。

    Args:
        project_root: 專案根目錄
        max_age_hours: 最大存活時數

    Returns:
        清理的記錄數量
    """
    with _state_lock(project_root):
        state = _read_state(project_root)
        now = datetime.now(timezone.utc)

        kept = [d for d in state["dispatches"] if not _is_dispatch_expired(d, now, max_age_hours)]
        removed_count = len(state["dispatches"]) - len(kept)

        if removed_count > 0:
            state["dispatches"] = kept
            _write_state(project_root, state)

        return removed_count


def _parse_agent_worktree_branches(project_root: Path) -> List[str]:
    """從 git worktree list 解析 agent- 前綴的分支名稱。

    Returns:
        agent- 前綴的 worktree 分支名稱清單，失敗時回傳空清單
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"[dispatch_tracker] _parse_agent_worktree_branches: git worktree list 失敗: {e}", file=sys.stderr)
        return []

    branches = []
    for line in result.stdout.splitlines():
        if line.startswith("branch refs/heads/agent-"):
            branches.append(line[len("branch refs/heads/"):])
    return branches


def detect_orphan_branches(project_root: Path) -> List[str]:
    """偵測 orphan worktree 分支（有 worktree 但無對應 dispatch 記錄）。

    Returns:
        orphan 分支名稱清單
    """
    worktree_branches = _parse_agent_worktree_branches(project_root)
    if not worktree_branches:
        return []

    dispatch_branch_names = {
        d.get("branch_name", "") for d in get_active_dispatches(project_root)
        if d.get("branch_name")
    }

    # 精確比對（W8-001：子字串比對不可靠）
    return [b for b in worktree_branches if b not in dispatch_branch_names]
