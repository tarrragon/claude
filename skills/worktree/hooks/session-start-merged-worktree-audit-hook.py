#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
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

Section 3 — Orphan branch audit（W3-021）
  列出無對應 worktree 的孤兒分支，涵蓋 `worktree-agent-*` 與人工命名分支兩類。
  worktree 已被移除（GC 或手動刪除目錄）但分支殘留（git worktree remove 不刪分支）。
  排除保護分支（main / master）與當前 checkout 分支。
  ahead=0 列為可安全刪除（git branch -d）；ahead>0 標記含未落地 commit 需人工確認。
  輸出區分 worktree-agent-* 與人工命名兩類來源，避免混淆既有讀者。

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

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    parse_ticket_frontmatter,
    get_worktree_list,
    get_uncommitted_files,
    get_current_branch,
    is_protected_branch,
)


# ---------- worktree audit ----------

def parse_worktree_list(logger) -> Optional[List[Tuple[str, str]]]:
    """解析 git worktree list，回傳 (path, branch) 列表（排除 main / master / detached）。

    改用 lib.git_utils.get_worktree_list(exclude_main=True)（0.2.1-W3-290），
    detached 項目無 branch 值，經 `if wt.get("branch")` 過濾後與原實作等價。

    Returns:
        None → get_worktree_list 執行失敗，判定失敗，呼叫端不得將 None 等同於
            空清單，否則會把「無法列舉 worktree」誤標為「無 merged worktree」
            （fail-open）。
        非 None 清單（可為空）→ 判定成功。
    """
    try:
        worktrees = get_worktree_list(exclude_main=True)
    except Exception as exc:
        logger.warning("git worktree list 執行失敗，無法判定 worktree 清單: %s", exc)
        return None
    return [(wt["path"], wt["branch"]) for wt in worktrees if wt.get("branch")]


def get_unmerged_commits(branch: str, logger) -> Optional[List[str]]:
    """取得分支相對於 main 的未合併 commit。

    回傳三態語意：
      - 非 None 空清單 → 判定成功，ahead=0
      - 非 None 非空清單 → 判定成功，ahead>0
      - None → 判定失敗（timeout / 找不到 git / returncode 非 0），呼叫端
        不得將 None 等同於空清單，否則會把「判定失敗」誤標為「ahead=0
        可安全刪除」（fail-open）。
    """
    try:
        result = subprocess.run(
            ["git", "log", f"main..{branch}", "--oneline"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except subprocess.TimeoutExpired:
        logger.warning("git log main..%s 執行逾時，無法判定 ahead 狀態", branch)
        return None
    except FileNotFoundError:
        logger.warning("git log main..%s 找不到 git 執行檔，無法判定 ahead 狀態", branch)
        return None

    if result.returncode != 0:
        logger.warning(
            "git log main..%s 非零退出碼: %d，無法判定 ahead 狀態", branch, result.returncode
        )
        return None

    return [line for line in result.stdout.strip().splitlines() if line]


def is_cc_runtime_worktree(path: str) -> bool:
    """判斷 worktree 是否為 cc runtime 自動建立的 worktree。

    cc runtime worktree 慣例路徑：`.claude/worktrees/agent-*`
    這類由 worktree-zombie-cleanup-hook 處理，本 audit 不重複。
    """
    return ".claude/worktrees/agent-" in path.replace("\\", "/")


def collect_merged_user_worktrees(logger) -> Optional[List[Tuple[str, str]]]:
    """收集 ahead=0 的 user worktree（已排除 main、master 與 cc runtime）。

    get_unmerged_commits 回傳 None 代表判定失敗，非「ahead=0」，此處保守
    略過不列入 merged（避免 fail-open 誤標可安全清理）。

    Returns:
        None → parse_worktree_list 判定失敗，呼叫端不得將 None 等同於
            「無 merged worktree」，需顯性告知稽核已跳過。
    """
    worktrees = parse_worktree_list(logger)
    if worktrees is None:
        logger.warning("無法判定 worktree 清單，跳過 merged worktree 稽核（不輸出任何結論）")
        return None
    merged: List[Tuple[str, str]] = []
    for wt_path, branch in worktrees:
        if is_cc_runtime_worktree(wt_path):
            continue
        unmerged = get_unmerged_commits(branch, logger)
        if unmerged is None:
            continue
        if not unmerged:
            merged.append((wt_path, branch))
    return merged


# ---------- orphan branch audit (W3-021 擴充：人工命名分支) ----------

def list_local_branches(logger) -> Optional[List[str]]:
    """列出所有本地分支名稱（不限 worktree-agent-* 前綴）。

    Returns:
        None → 判定失敗（timeout / 找不到 git / returncode 非 0），呼叫端
            不得將 None 等同於空清單，否則會把「無法列舉本地分支」誤讀為
            「無孤兒分支候選」（fail-open）。
        非 None 清單（可為空）→ 判定成功。
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--list", "--format=%(refname:short)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except subprocess.TimeoutExpired:
        logger.warning("git branch --list 執行逾時，無法判定本地分支清單")
        return None
    except FileNotFoundError:
        logger.warning("git branch --list 找不到 git 執行檔，無法判定本地分支清單")
        return None

    if result.returncode != 0:
        logger.warning(
            "git branch --list 非零退出碼: %d，無法判定本地分支清單", result.returncode
        )
        return None

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_agent_prefixed_branch(branch: str) -> bool:
    """判斷分支名是否為 cc runtime 慣例前綴 `worktree-agent-*`。"""
    return branch.startswith("worktree-agent-")


def list_worktree_branches(logger) -> Optional[List[str]]:
    """列出 git worktree list 中所有仍存在的分支（含 main / cc runtime）。

    改用直接 subprocess 呼叫（不透過 lib.get_worktree_list），因該函式將指令
    失敗與真正無 worktree 兩種狀態均收斂為空清單，呼叫端無法區分（此為修復的
    fail-open 根因）。

    回傳三態語意（與 get_unmerged_commits 一致，同款三態設計）：
      - 非 None 清單（可為空）→ 判定成功
      - None → 判定失敗（timeout / 找不到 git / returncode 非 0），呼叫端
        不得將 None 等同於空清單，否則會把「無法判定 worktree 清單」誤讀為
        「所有分支皆無對應 worktree」，導致仍掛載 worktree 的分支被誤判孤兒。
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except subprocess.TimeoutExpired:
        logger.warning("git worktree list 執行逾時，無法判定 worktree 清單")
        return None
    except FileNotFoundError:
        logger.warning("git worktree list 找不到 git 執行檔，無法判定 worktree 清單")
        return None

    if result.returncode != 0:
        logger.warning(
            "git worktree list 非零退出碼: %d，無法判定 worktree 清單", result.returncode
        )
        return None

    branches: List[str] = []
    for line in result.stdout.splitlines():
        if line.startswith("branch "):
            branch_ref = line[len("branch "):]
            if branch_ref.startswith("refs/heads/"):
                branch_ref = branch_ref[len("refs/heads/"):]
            branches.append(branch_ref)
    return branches


#: collect_orphan_agent_branches 判定失敗時的失敗因代碼，供 reason_out 回填。
#: build_message 依此代碼選擇對應訊息文字，取代硬編碼單一原因。
ORPHAN_BRANCHES_REASON_LOCAL_BRANCHES = "local_branches"
ORPHAN_BRANCHES_REASON_WORKTREE_BRANCHES = "worktree_branches"
ORPHAN_BRANCHES_REASON_CURRENT_BRANCH = "current_branch"


def collect_orphan_agent_branches(
    logger, reason_out: Optional[dict] = None
) -> Optional[List[Tuple[str, Optional[bool], bool]]]:
    """收集無對應 worktree 的孤兒分支（涵蓋 worktree-agent-* 與人工命名分支）。

    worktree 已被移除（GC 或手動刪除目錄）但分支殘留（git worktree remove 不刪分支）。
    排除保護分支（main / master）與當前 checkout 分支——原僅掃 worktree-agent-*
    命名前綴，假設過窄，人工命名分支落在範圍外。

    Args:
        reason_out: 選填。判定失敗時，呼叫端可傳入空 dict 接收失敗因代碼
            （寫入 `reason_out["reason"]`，值為 ORPHAN_BRANCHES_REASON_* 常數
            之一），供 build_message 輸出對應訊息而非單一硬編碼原因——三個
            判定點原先共用同一句「git worktree list 執行失敗」訊息，實際
            失敗因可能是任一點，訊息文字因此可能與實際狀態不符，誤導排查
            方向。不需要區分失敗因的呼叫端可省略。

    Returns:
        None → list_local_branches / list_worktree_branches / get_current_branch
            任一判定失敗（get_current_branch 失敗時無法區分「當前分支未知」
            與「當前分支被誤判為孤兒」），保守處置為不輸出任何孤兒分支結論。
            get_current_branch 回傳 None 時，若以 `if current_branch and ...`
            短路排除守衛，會使當前 checkout 分支未被排除而誤列為孤兒
            （fail-open），故此處直接中止整個稽核。
        List of (branch_name, ahead_state, is_agent_prefixed) → 判定成功：
        ahead_state=False（ahead=0）→ 可安全刪除
        ahead_state=True（ahead>0）→ 含未落地 commit，需人工確認
        ahead_state=None（判定失敗）→ 無法判定，需人工確認（不得視同 ahead=0）
        is_agent_prefixed=True → worktree-agent-* 前綴；False → 人工命名分支
    """
    local_branches = list_local_branches(logger)
    if local_branches is None:
        logger.warning("無法判定本地分支清單，跳過孤兒分支稽核（不輸出任何結論）")
        if reason_out is not None:
            reason_out["reason"] = ORPHAN_BRANCHES_REASON_LOCAL_BRANCHES
        return None
    worktree_branches = list_worktree_branches(logger)
    if worktree_branches is None:
        logger.warning("無法判定 worktree 分支清單，跳過孤兒分支稽核（不輸出任何結論）")
        if reason_out is not None:
            reason_out["reason"] = ORPHAN_BRANCHES_REASON_WORKTREE_BRANCHES
        return None
    active_branches = set(worktree_branches)
    current_branch = get_current_branch()
    if current_branch is None:
        logger.warning("無法判定當前 checkout 分支，跳過孤兒分支稽核（不輸出任何結論）")
        if reason_out is not None:
            reason_out["reason"] = ORPHAN_BRANCHES_REASON_CURRENT_BRANCH
        return None

    orphans: List[Tuple[str, Optional[bool], bool]] = []
    for branch in local_branches:
        if branch in active_branches:
            # 仍有對應 worktree，由 zombie-cleanup 處理，不重複
            continue
        if is_protected_branch(branch):
            continue
        if branch == current_branch:
            continue
        unmerged = get_unmerged_commits(branch, logger)
        ahead_state = None if unmerged is None else bool(unmerged)
        orphans.append((branch, ahead_state, is_agent_prefixed_branch(branch)))
    return orphans


# ---------- metadata orphan audit ----------

def collect_modified_ticket_paths(project_root: Path, logger) -> Optional[List[str]]:
    """從 git status --porcelain 取出所有 modified / added 的 ticket md 相對路徑。

    改用 lib.git_utils.get_uncommitted_files(cwd=...)（0.2.1-W3-290），
    以 FileStatus.is_modified / is_added 取代自行判斷 status_code。

    Returns:
        None → get_uncommitted_files 執行失敗，判定失敗，呼叫端不得將 None
            等同於空清單，否則會把「無法列舉 modified 檔案」誤讀為「無
            metadata orphan ticket」（fail-open）。
        非 None 清單（可為空）→ 判定成功。
    """
    try:
        file_statuses = get_uncommitted_files(cwd=str(project_root))
    except Exception as exc:
        logger.warning("git status 執行失敗，無法判定 modified 檔案清單: %s", exc)
        return None

    paths: List[str] = []
    for fs in file_statuses:
        rel_path = fs.file_path.strip()
        # 偵測 M / A / MM / AM 等變更（不含 ?? 未追蹤）
        if fs.is_modified or fs.is_added:
            # 只關心 ticket md
            if "/tickets/" in rel_path and rel_path.endswith(".md"):
                paths.append(rel_path)
    return paths


def collect_orphan_tickets(project_root: Path, logger) -> Optional[List[Tuple[str, str]]]:
    """收集 metadata orphan ticket：status=completed 但 git status 顯示為 modified/added。

    Returns:
        None → collect_modified_ticket_paths 判定失敗，呼叫端不得將 None
            等同於「無 metadata orphan ticket」，需顯性告知稽核已跳過。
        List of (ticket_id, relative_path) → 判定成功。
    """
    modified_paths = collect_modified_ticket_paths(project_root, logger)
    if modified_paths is None:
        logger.warning("無法判定 modified 檔案清單，跳過 metadata orphan 稽核（不輸出任何結論）")
        return None
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

#: orphan_branches_reason 代碼 → 訊息文字對照表。找不到對應代碼（含 None，
#: 即呼叫端未傳入 reason_out 或該次失敗未寫入代碼）時 fallback 至通用訊息，
#: 維持與既有呼叫端（未傳 reason）的相容輸出。
_ORPHAN_BRANCHES_REASON_MESSAGES = {
    ORPHAN_BRANCHES_REASON_LOCAL_BRANCHES: "無法判定本地分支清單（git branch --list 執行失敗）",
    ORPHAN_BRANCHES_REASON_WORKTREE_BRANCHES: "無法判定 worktree 分支清單（git worktree list 執行失敗）",
    ORPHAN_BRANCHES_REASON_CURRENT_BRANCH: "無法判定當前 checkout 分支（git branch --show-current 執行失敗或無回傳），為避免當前分支被誤判為孤兒已保守跳過",
}


def build_message(
    merged_worktrees: List[Tuple[str, str]],
    orphan_tickets: List[Tuple[str, str]],
    orphan_branches: Optional[List[Tuple[str, Optional[bool], bool]]] = None,
    orphan_branches_undetermined: bool = False,
    merged_worktrees_undetermined: bool = False,
    orphan_tickets_undetermined: bool = False,
    orphan_branches_reason: Optional[str] = None,
) -> str:
    """組裝三個 section 的合併訊息。

    各 *_undetermined=True 代表對應 section 的列舉判定失敗（此時對應清單必為
    空），改輸出說明訊息而非該 section 的正常結論（不得輸出任何刪除/commit 建議）。

    orphan_branches_reason: 選填，ORPHAN_BRANCHES_REASON_* 常數之一，指出孤兒
        分支 section 判定失敗的實際失敗因（三個判定點各自可能失敗，訊息文字
        依實際失敗因而異，非固定單一原因）。未提供或代碼不在對照表時，
        fallback 至通用訊息（沿用既有呼叫端未傳 reason 時的輸出）。
    """
    orphan_branches = orphan_branches or []
    lines: List[str] = []

    if merged_worktrees_undetermined:
        lines.append(
            "[SessionStart Audit] 無法判定 worktree 清單（git worktree list 執行失敗），"
            "merged worktree 稽核已跳過，不輸出任何結論或清理建議。"
        )
        if orphan_tickets or orphan_tickets_undetermined or orphan_branches or orphan_branches_undetermined:
            lines.append("")
    elif merged_worktrees:
        lines.append(f"[SessionStart Audit] 發現 {len(merged_worktrees)} 個 user worktree 已完全合併（ahead=0）尚未清理：")
        lines.append("")
        for wt_path, branch in merged_worktrees:
            lines.append(f"  - 分支 {branch}  路徑 {wt_path}")
            lines.append(f"    清理: git worktree remove {wt_path}")
        lines.append("")
        lines.append("PC-149：合併後 worktree 殘留會累積 disk 佔用與視圖污染。")
        if orphan_tickets or orphan_tickets_undetermined:
            lines.append("")

    if orphan_tickets_undetermined:
        lines.append(
            "[SessionStart Audit] 無法判定 modified 檔案清單（git status 執行失敗），"
            "metadata orphan 稽核已跳過，不輸出任何結論或 commit 建議。"
        )
        if orphan_branches or orphan_branches_undetermined:
            lines.append("")
    elif orphan_tickets:
        lines.append(f"[SessionStart Audit] 發現 {len(orphan_tickets)} 個 metadata orphan ticket（已 complete 但 md 未 commit）：")
        lines.append("")
        for ticket_id, rel_path in orphan_tickets:
            lines.append(f"  - {ticket_id}  ({rel_path})")
        lines.append("")
        lines.append("建議：git add <ticket-md> && git commit -m \"chore: sync ticket metadata\"")
        if orphan_branches or orphan_branches_undetermined:
            lines.append("")

    if orphan_branches_undetermined:
        reason_text = _ORPHAN_BRANCHES_REASON_MESSAGES.get(
            orphan_branches_reason,
            "無法判定 worktree 分支清單（git worktree list 執行失敗）",
        )
        lines.append(
            f"[SessionStart Audit] {reason_text}，"
            "孤兒分支稽核已跳過，不輸出任何孤兒分支結論或刪除建議。"
        )
    elif orphan_branches:
        lines.append(f"[SessionStart Audit] 發現 {len(orphan_branches)} 個無對應 worktree 的孤兒分支：")
        lines.append("")
        for branch, ahead_state, is_agent_prefixed in orphan_branches:
            source_label = "worktree-agent-*" if is_agent_prefixed else "人工命名"
            if ahead_state is None:
                lines.append(f"  - {branch}  [{source_label}][無法判定 ahead 狀態，需人工確認]")
            elif ahead_state:
                lines.append(f"  - {branch}  [{source_label}][含未落地 commit（ahead>0），需人工確認後再刪]")
            else:
                lines.append(f"  - {branch}  [{source_label}][ahead=0 可安全刪除]")
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

    merged_worktrees_undetermined = False
    try:
        merged_result = collect_merged_user_worktrees(logger)
    except Exception as exc:  # noqa: BLE001 — SessionStart 絕不可阻擋
        logger.warning("collect_merged_user_worktrees 失敗: %s", exc)
        merged_result = None
    if merged_result is None:
        merged_worktrees: List[Tuple[str, str]] = []
        merged_worktrees_undetermined = True
    else:
        merged_worktrees = merged_result

    orphan_tickets_undetermined = False
    try:
        orphan_tickets_result = collect_orphan_tickets(project_root, logger)
    except Exception as exc:  # noqa: BLE001
        logger.warning("collect_orphan_tickets 失敗: %s", exc)
        orphan_tickets_result = None
    if orphan_tickets_result is None:
        orphan_tickets: List[Tuple[str, str]] = []
        orphan_tickets_undetermined = True
    else:
        orphan_tickets = orphan_tickets_result

    orphan_branches_undetermined = False
    orphan_branches_reason: Optional[str] = None
    reason_out: dict = {}
    try:
        orphan_result = collect_orphan_agent_branches(logger, reason_out=reason_out)
    except Exception as exc:  # noqa: BLE001
        logger.warning("collect_orphan_agent_branches 失敗: %s", exc)
        orphan_result = None

    if orphan_result is None:
        # list_local_branches / list_worktree_branches / get_current_branch
        # 任一判定失敗：不得視同「無孤兒分支」，需顯性告知使用者稽核已跳過，
        # 而非靜默 suppress；reason_out 記錄實際失敗因供訊息文字區分。
        orphan_branches: List[Tuple[str, Optional[bool], bool]] = []
        orphan_branches_undetermined = True
        orphan_branches_reason = reason_out.get("reason")
    else:
        orphan_branches = orphan_result

    if (
        not merged_worktrees
        and not orphan_tickets
        and not orphan_branches
        and not merged_worktrees_undetermined
        and not orphan_tickets_undetermined
        and not orphan_branches_undetermined
    ):
        # 三 section 皆空且判定未失敗：suppressOutput
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False))
        return 0

    message = build_message(
        merged_worktrees,
        orphan_tickets,
        orphan_branches,
        orphan_branches_undetermined,
        merged_worktrees_undetermined,
        orphan_tickets_undetermined,
        orphan_branches_reason=orphan_branches_reason,
    )
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    logger.info(
        "audit 結果：merged_worktrees=%d (undetermined=%s) orphan_tickets=%d (undetermined=%s) "
        "orphan_branches=%d (undetermined=%s)",
        len(merged_worktrees), merged_worktrees_undetermined,
        len(orphan_tickets), orphan_tickets_undetermined,
        len(orphan_branches), orphan_branches_undetermined,
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-merged-worktree-audit"))
