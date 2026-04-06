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

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

STATE_FILE_RELATIVE = ".claude/dispatch-active.json"


def get_state_file_path(project_root: Path) -> Path:
    """取得狀態檔路徑"""
    return project_root / STATE_FILE_RELATIVE


def _read_state(project_root: Path) -> Dict:
    """讀取狀態檔。檔案不存在或格式錯誤時回傳空結構。"""
    state_file = get_state_file_path(project_root)
    if not state_file.exists():
        return {"dispatches": []}
    try:
        content = state_file.read_text(encoding="utf-8")
        data = json.loads(content)
        if not isinstance(data, dict) or "dispatches" not in data:
            return {"dispatches": []}
        return data
    except (json.JSONDecodeError, OSError):
        return {"dispatches": []}


def _write_state(project_root: Path, state: Dict) -> None:
    """寫入狀態檔。自動建立父目錄。"""
    state_file = get_state_file_path(project_root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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


def cleanup_expired(project_root: Path, max_age_hours: int = 4) -> int:
    """清理超時的派發記錄（防止遺留）。

    Args:
        project_root: 專案根目錄
        max_age_hours: 最大存活時數

    Returns:
        清理的記錄數量
    """
    state = _read_state(project_root)
    now = datetime.now(timezone.utc)
    kept = []
    removed_count = 0

    for dispatch in state["dispatches"]:
        dispatched_at_str = dispatch.get("dispatched_at", "")
        try:
            dispatched_at = datetime.fromisoformat(dispatched_at_str)
            # 確保有 timezone 資訊以便比較
            if dispatched_at.tzinfo is None:
                dispatched_at = dispatched_at.replace(tzinfo=timezone.utc)
            age_hours = (now - dispatched_at).total_seconds() / 3600
            if age_hours > max_age_hours:
                removed_count += 1
                continue
        except (ValueError, TypeError):
            # 無法解析時間，視為過期清理
            removed_count += 1
            continue
        kept.append(dispatch)

    if removed_count > 0:
        state["dispatches"] = kept
        _write_state(project_root, state)

    return removed_count


def detect_orphan_branches(project_root: Path) -> List[str]:
    """偵測 orphan worktree 分支（有 worktree 但無對應 dispatch 記錄）。

    執行 git worktree list，比對 dispatch-active.json 中的記錄。
    只檢查 agent- 前綴的 worktree 分支。

    Returns:
        orphan 分支名稱清單
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
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    # 解析 worktree list --porcelain 輸出
    # 格式：每個 worktree 以 "worktree <path>" 開頭，"branch refs/heads/<name>" 標示分支
    worktree_branches = []
    for line in result.stdout.splitlines():
        if line.startswith("branch refs/heads/"):
            branch_name = line[len("branch refs/heads/"):]
            # 只關注 agent- 前綴的分支（代理人 worktree 慣例）
            if branch_name.startswith("agent-"):
                worktree_branches.append(branch_name)

    if not worktree_branches:
        return []

    # 比對 dispatch 記錄：有 worktree 分支但無對應 dispatch 的即為 orphan
    dispatches = get_active_dispatches(project_root)
    dispatch_branch_names = {
        d.get("branch_name", "") for d in dispatches if d.get("branch_name")
    }

    orphans = []
    for branch in worktree_branches:
        # 精確比對 dispatch 記錄中的 branch_name 欄位
        # （需求：linux 審查 — 子字串比對不可靠，Ticket 0.17.2-W8-001）
        if branch not in dispatch_branch_names:
            orphans.append(branch)

    return orphans
