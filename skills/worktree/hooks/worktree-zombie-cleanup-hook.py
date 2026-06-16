#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Worktree Zombie Cleanup Hook (SessionStart)

Purpose: 自動清理 .claude/worktrees/agent-* 中已殭屍的 worktree。
Source: 0.18.0-W17-119 / 0.18.0-W17-119.1 — 4 週累積 24 個殭屍 worktree，PID 全死，缺自動 GC。

邏輯:
1. 列舉 .claude/worktrees/agent-*
2. 對每個 worktree：
   - 跳過環境變數 WORKTREE_ZOMBIE_CLEANUP_DISABLE 非空時的整體執行
   - 跳過建立時間 < RECENT_THRESHOLD_SECONDS（30 分鐘）的 worktree
   - 從 .git/worktrees/<name>/locked 解析 PID
   - 用 ps -p 確認 PID 死活（含 claude/cc 名稱驗證）
   - PID dead + clean → git worktree unlock + git worktree remove --force
   - PID dead + dirty → 警告，不清
   - PID alive → 跳過
3. 輸出 stderr + 檔案日誌（quality-baseline 規則 4）

輸出非阻塞：任何錯誤皆 suppressOutput，不中斷 Session 啟動。
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from hook_utils import setup_hook_logging, run_hook_safely, get_project_root  # type: ignore

HOOK_NAME = "worktree-zombie-cleanup"

# 排除最近建立的 worktree（避免清掉正在啟動中的代理人）
RECENT_THRESHOLD_SECONDS = 30 * 60

# 進程名稱驗證關鍵字（PID 重用時降低誤判）
PROCESS_NAME_KEYWORDS = ("claude", "cc")

DISABLE_ENV_VAR = "WORKTREE_ZOMBIE_CLEANUP_DISABLE"

# locked 檔案 PID 解析正則
_PID_PATTERN = re.compile(r"\(pid\s+(\d+)\)")


# ---------- 純函式（易於 unit test） ----------

def parse_pid_from_locked_content(content: str) -> Optional[int]:
    """從 .git/worktrees/<name>/locked 檔案內容解析 PID。

    範例內容: "claude agent agent-a04636c2 (pid 45136)\n"
    """
    if not content:
        return None
    match = _PID_PATTERN.search(content)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (ValueError, TypeError):
        return None


def is_recent(worktree_dir: Path, now: float, threshold: float = RECENT_THRESHOLD_SECONDS) -> bool:
    """worktree 目錄建立時間是否在 threshold 秒內。"""
    try:
        ctime = worktree_dir.stat().st_mtime
    except OSError:
        return False
    return (now - ctime) < threshold


def is_disabled() -> bool:
    """是否被環境變數停用。"""
    return bool(os.environ.get(DISABLE_ENV_VAR, "").strip())


# ---------- 系統呼叫包裝（可在 test 中 monkeypatch） ----------

def check_pid_alive(pid: int) -> Tuple[bool, str]:
    """檢查 PID 是否存活，回傳 (alive, process_name)。

    使用 ps -p <pid> -o comm= 取得進程名稱。
    """
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        # 無法判定 → 保守視為 alive，不清
        return True, ""

    if result.returncode != 0:
        return False, ""

    name = (result.stdout or "").strip()
    return bool(name), name


def is_worktree_dirty(worktree_path: Path) -> bool:
    """檢查 worktree 是否有未提交變更。失敗時保守視為 dirty。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(worktree_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return True

    if result.returncode != 0:
        return True
    return bool((result.stdout or "").strip())


def remove_worktree(project_root: Path, worktree_path: Path, name: str, logger) -> bool:
    """執行 git worktree unlock + remove --force。回傳是否成功。"""
    for cmd in (
        ["git", "-C", str(project_root), "worktree", "unlock", str(worktree_path)],
        ["git", "-C", str(project_root), "worktree", "remove", "--force", str(worktree_path)],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
            logger.error("[%s] %s 執行失敗: %s", name, " ".join(cmd[3:]), exc)
            return False
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            # unlock 對未 lock 的 worktree 會失敗，視為非致命，繼續嘗試 remove
            if cmd[3] == "unlock":
                logger.info("[%s] unlock 非致命失敗（可能未 lock）: %s", name, stderr)
                continue
            logger.error("[%s] %s 失敗: %s", name, " ".join(cmd[3:]), stderr)
            return False
    return True


# ---------- 核心決策邏輯（純函式） ----------

def decide_action(
    pid: Optional[int],
    pid_alive: bool,
    process_name: str,
    dirty: bool,
    recent: bool,
) -> Tuple[str, str]:
    """決策動作，回傳 (action, reason)。

    action ∈ {"clean", "warn-dirty", "skip-alive", "skip-recent", "skip-no-pid", "skip-name-mismatch"}
    """
    if recent:
        return "skip-recent", "建立時間 < 30 分鐘"
    if pid is None:
        return "skip-no-pid", "locked 檔案缺 PID"
    if pid_alive:
        # 進程名稱不匹配（PID 已被其他進程重用）→ 視為 dead
        if process_name and not any(kw in process_name.lower() for kw in PROCESS_NAME_KEYWORDS):
            return _decide_dead(dirty, f"PID 重用（process={process_name}）")
        return "skip-alive", f"PID {pid} alive ({process_name})"
    return _decide_dead(dirty, f"PID {pid} dead")


def _decide_dead(dirty: bool, base_reason: str) -> Tuple[str, str]:
    if dirty:
        return "warn-dirty", f"{base_reason}，但 worktree dirty"
    return "clean", base_reason


# ---------- 主流程 ----------

def list_agent_worktrees(project_root: Path) -> List[Path]:
    base = project_root / ".claude" / "worktrees"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and p.name.startswith("agent-"))


def read_locked_pid(project_root: Path, name: str) -> Optional[int]:
    locked_file = project_root / ".git" / "worktrees" / name / "locked"
    try:
        content = locked_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return parse_pid_from_locked_content(content)


def process_worktree(project_root: Path, worktree_dir: Path, now: float, logger) -> Dict[str, Any]:
    """處理單一 worktree，回傳結果摘要。"""
    name = worktree_dir.name
    pid = read_locked_pid(project_root, name)
    recent = is_recent(worktree_dir, now)

    pid_alive, process_name = (False, "")
    if pid is not None and not recent:
        pid_alive, process_name = check_pid_alive(pid)

    dirty = False
    if not recent and not pid_alive:
        dirty = is_worktree_dirty(worktree_dir)

    action, reason = decide_action(pid, pid_alive, process_name, dirty, recent)

    result: Dict[str, Any] = {
        "name": name,
        "pid": pid,
        "action": action,
        "reason": reason,
    }

    if action == "clean":
        success = remove_worktree(project_root, worktree_dir, name, logger)
        result["success"] = success
        if success:
            logger.info("[%s] 清理成功: %s", name, reason)
        else:
            logger.error("[%s] 清理失敗: %s", name, reason)
    elif action == "warn-dirty":
        logger.warning("[%s] 殭屍但 dirty，不清: %s", name, reason)
    else:
        logger.info("[%s] 跳過: %s", name, reason)

    return result


def summarize(results: List[Dict[str, Any]]) -> str:
    cleaned = [r for r in results if r.get("action") == "clean" and r.get("success")]
    failed = [r for r in results if r.get("action") == "clean" and not r.get("success")]
    dirty = [r for r in results if r.get("action") == "warn-dirty"]
    if not (cleaned or failed or dirty):
        return ""
    lines = [f"[worktree-zombie-cleanup] 掃描 {len(results)} 個 agent worktree:"]
    if cleaned:
        lines.append(f"  - 已清理: {len(cleaned)} 個")
    if dirty:
        lines.append(f"  - 殭屍但 dirty 保留: {len(dirty)} 個")
        for r in dirty:
            lines.append(f"      * {r['name']} ({r['reason']})")
    if failed:
        lines.append(f"  - 清理失敗: {len(failed)} 個")
        for r in failed:
            lines.append(f"      * {r['name']} ({r['reason']})")
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)

    if is_disabled():
        logger.info("已透過 %s 環境變數停用", DISABLE_ENV_VAR)
        print(json.dumps({"suppressOutput": True}))
        return 0

    try:
        project_root = Path(get_project_root())
    except Exception as exc:
        logger.error("無法取得 project root: %s", exc)
        print(json.dumps({"suppressOutput": True}))
        return 0

    worktrees = list_agent_worktrees(project_root)
    if not worktrees:
        logger.info("無 agent worktree，跳過")
        print(json.dumps({"suppressOutput": True}))
        return 0

    logger.info("掃描 %d 個 agent worktree", len(worktrees))
    now = time.time()
    results = [process_worktree(project_root, wt, now, logger) for wt in worktrees]

    summary = summarize(results)
    if summary:
        # stderr + log 雙通道（quality-baseline 規則 4）
        print(summary, file=sys.stderr)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": summary,
            },
            "suppressOutput": False,
        }, ensure_ascii=False))
    else:
        print(json.dumps({"suppressOutput": True}))

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
