#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Session Start Merged Worktree Audit Hook - SessionStart

W11-033 / PC-149：session 啟動時統一 audit 兩種「ticket complete 後系統性缺口」：

Section 1 — Merged worktree audit
  列出 ahead=0 的 user worktree（排除主 repo 與 cc runtime worktree `.claude/worktrees/agent-*`）。
  cc runtime worktree 由 worktree-zombie-cleanup-hook 處理；本 audit 只負責 user worktree。

Section 2 — Metadata orphan audit
  列出 `status: completed` 但 ticket md 仍 modified（git status `M` / `A`）的孤兒。
  in_progress ticket md modified 屬正常狀態（agent 還在寫），不列入。

Section 3 — Orphan worktree-agent branch audit（W3-021）
  列出無對應 worktree 的孤兒 `worktree-agent-*` 分支。
  worktree 已被 zombie-cleanup GC 但分支殘留（git worktree remove 不刪分支）。
  ahead=0 列為可安全刪除（git branch -d）；ahead>0 標記含未落地 commit 需人工確認。

Hook 類型：SessionStart
退出碼：永遠 0（SessionStart 不阻擋 session 啟動）
輸出格式：
  - 兩 section 皆空 → `{"suppressOutput": true}`
  - 任一非空 → `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}`
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    parse_ticket_frontmatter,
)


# ---------- worktree audit ----------

def parse_worktree_list(logger) -> List[Tuple[str, str]]:
    """解析 git worktree list，回傳 (path, branch) 列表（排除 main / master / detached）。"""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git worktree list 執行失敗")
        return []

    if result.returncode != 0:
        logger.debug("git worktree list 非零退出碼: %d", result.returncode)
        return []

    worktrees: List[Tuple[str, str]] = []
    current_path: Optional[str] = None
    current_branch: Optional[str] = None

    def flush():
        nonlocal current_path, current_branch
        if current_path and current_branch and current_branch not in ("main", "master"):
            worktrees.append((current_path, current_branch))
        current_path = None
        current_branch = None

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            # 新條目開始前先 flush 前一個
            flush()
            current_path = line[len("worktree "):]
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            current_branch = ref.replace("refs/heads/", "")
        elif line == "":
            flush()
    flush()
    return worktrees


def get_unmerged_commits(branch: str, logger) -> List[str]:
    """取得分支相對於 main 的未合併 commit。"""
    try:
        result = subprocess.run(
            ["git", "log", f"main..{branch}", "--oneline"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.debug("git log main..%s 執行失敗", branch)
        return []

    if result.returncode != 0:
        return []

    return [line for line in result.stdout.strip().splitlines() if line]


def is_cc_runtime_worktree(path: str) -> bool:
    """判斷 worktree 是否為 cc runtime 自動建立的 worktree。

    cc runtime worktree 慣例路徑：`.claude/worktrees/agent-*`
    這類由 worktree-zombie-cleanup-hook 處理，本 audit 不重複。
    """
    return ".claude/worktrees/agent-" in path.replace("\\", "/")


def collect_merged_user_worktrees(logger) -> List[Tuple[str, str]]:
    """收集 ahead=0 的 user worktree（已排除 main、master 與 cc runtime）。"""
    worktrees = parse_worktree_list(logger)
    merged: List[Tuple[str, str]] = []
    for wt_path, branch in worktrees:
        if is_cc_runtime_worktree(wt_path):
            continue
        if not get_unmerged_commits(branch, logger):
            merged.append((wt_path, branch))
    return merged


# ---------- orphan worktree-agent branch audit (W3-021) ----------

def list_agent_branches(logger) -> List[str]:
    """列出所有 worktree-agent-* 分支名稱。"""
    try:
        result = subprocess.run(
            ["git", "branch", "--list", "worktree-agent-*", "--format=%(refname:short)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git branch --list worktree-agent-* 執行失敗")
        return []

    if result.returncode != 0:
        logger.debug("git branch --list 非零退出碼: %d", result.returncode)
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def list_worktree_branches(logger) -> List[str]:
    """列出 git worktree list 中所有仍存在的分支（含 main / cc runtime）。"""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git worktree list 執行失敗")
        return []

    if result.returncode != 0:
        logger.debug("git worktree list 非零退出碼: %d", result.returncode)
        return []

    branches: List[str] = []
    for line in result.stdout.splitlines():
        if line.startswith("branch "):
            ref = line[len("branch "):]
            branches.append(ref.replace("refs/heads/", ""))
    return branches


def collect_orphan_agent_branches(logger) -> List[Tuple[str, bool]]:
    """收集無對應 worktree 的孤兒 worktree-agent-* 分支。

    worktree 已被 zombie-cleanup GC 但分支殘留（git worktree remove 不刪分支）。

    Returns:
        List of (branch_name, has_unmerged_commits)
        has_unmerged_commits=False（ahead=0）→ 可安全刪除
        has_unmerged_commits=True（ahead>0）→ 含未落地 commit，需人工確認
    """
    agent_branches = list_agent_branches(logger)
    active_branches = set(list_worktree_branches(logger))

    orphans: List[Tuple[str, bool]] = []
    for branch in agent_branches:
        if branch in active_branches:
            # 仍有對應 worktree，由 zombie-cleanup 處理，不重複
            continue
        has_unmerged = bool(get_unmerged_commits(branch, logger))
        orphans.append((branch, has_unmerged))
    return orphans


# ---------- metadata orphan audit ----------

def collect_modified_ticket_paths(project_root: Path, logger) -> List[str]:
    """從 git status --porcelain 取出所有 modified / added 的 ticket md 相對路徑。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git status 執行失敗")
        return []

    if result.returncode != 0:
        logger.debug("git status 非零退出碼: %d", result.returncode)
        return []

    paths: List[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        # porcelain 格式：XY <path>
        status_code = line[:2]
        rel_path = line[3:].strip()
        # 偵測 M / A / MM / AM 等變更（不含 ?? 未追蹤）
        if "M" in status_code or "A" in status_code:
            # 只關心 ticket md
            if "/tickets/" in rel_path and rel_path.endswith(".md"):
                paths.append(rel_path)
    return paths


def collect_orphan_tickets(project_root: Path, logger) -> List[Tuple[str, str]]:
    """收集 metadata orphan ticket：status=completed 但 git status 顯示為 modified/added。

    Returns:
        List of (ticket_id, relative_path)
    """
    modified_paths = collect_modified_ticket_paths(project_root, logger)
    orphans: List[Tuple[str, str]] = []
    for rel_path in modified_paths:
        abs_path = project_root / rel_path
        if not abs_path.exists():
            continue
        fm = parse_ticket_frontmatter(abs_path, logger)
        if not fm:
            continue
        if fm.get("status") == "completed":
            ticket_id = fm.get("id") or abs_path.stem
            orphans.append((str(ticket_id), rel_path))
    return orphans


# ---------- main ----------

def build_message(
    merged_worktrees: List[Tuple[str, str]],
    orphan_tickets: List[Tuple[str, str]],
    orphan_branches: Optional[List[Tuple[str, bool]]] = None,
) -> str:
    """組裝三個 section 的合併訊息。"""
    orphan_branches = orphan_branches or []
    lines: List[str] = []

    if merged_worktrees:
        lines.append(f"[SessionStart Audit] 發現 {len(merged_worktrees)} 個 user worktree 已完全合併（ahead=0）尚未清理：")
        lines.append("")
        for wt_path, branch in merged_worktrees:
            lines.append(f"  - 分支 {branch}  路徑 {wt_path}")
            lines.append(f"    清理: git worktree remove {wt_path}")
        lines.append("")
        lines.append("PC-149：合併後 worktree 殘留會累積 disk 佔用與視圖污染。")
        if orphan_tickets:
            lines.append("")

    if orphan_tickets:
        lines.append(f"[SessionStart Audit] 發現 {len(orphan_tickets)} 個 metadata orphan ticket（已 complete 但 md 未 commit）：")
        lines.append("")
        for ticket_id, rel_path in orphan_tickets:
            lines.append(f"  - {ticket_id}  ({rel_path})")
        lines.append("")
        lines.append("建議：git add <ticket-md> && git commit -m \"chore: sync ticket metadata\"")
        if orphan_branches:
            lines.append("")

    if orphan_branches:
        lines.append(f"[SessionStart Audit] 發現 {len(orphan_branches)} 個無對應 worktree 的孤兒 worktree-agent-* 分支：")
        lines.append("")
        for branch, has_unmerged in orphan_branches:
            if has_unmerged:
                lines.append(f"  - {branch}  [含未落地 commit（ahead>0），需人工確認後再刪]")
            else:
                lines.append(f"  - {branch}  [ahead=0 可安全刪除]")
                lines.append(f"    清理: git branch -d {branch}")
        lines.append("")
        lines.append("W3-021：git worktree remove 不刪分支，孤兒分支殘留會污染分支清單（quality-baseline 規則 5）。")

    return "\n".join(lines)


def main() -> int:
    """SessionStart hook 主邏輯。"""
    logger = setup_hook_logging("session-start-merged-worktree-audit")

    # SessionStart 不一定有 stdin，read_json_from_stdin 容錯
    _ = read_json_from_stdin(logger)

    project_root = get_project_root()
    logger.debug("專案根目錄: %s", project_root)

    try:
        merged_worktrees = collect_merged_user_worktrees(logger)
    except Exception as exc:  # noqa: BLE001 — SessionStart 絕不可阻擋
        logger.warning("collect_merged_user_worktrees 失敗: %s", exc)
        merged_worktrees = []

    try:
        orphan_tickets = collect_orphan_tickets(project_root, logger)
    except Exception as exc:  # noqa: BLE001
        logger.warning("collect_orphan_tickets 失敗: %s", exc)
        orphan_tickets = []

    try:
        orphan_branches = collect_orphan_agent_branches(logger)
    except Exception as exc:  # noqa: BLE001
        logger.warning("collect_orphan_agent_branches 失敗: %s", exc)
        orphan_branches = []

    if not merged_worktrees and not orphan_tickets and not orphan_branches:
        # 三 section 皆空：suppressOutput
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False))
        return 0

    message = build_message(merged_worktrees, orphan_tickets, orphan_branches)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    logger.info(
        "audit 結果：merged_worktrees=%d orphan_tickets=%d orphan_branches=%d",
        len(merged_worktrees), len(orphan_tickets), len(orphan_branches),
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-merged-worktree-audit"))
