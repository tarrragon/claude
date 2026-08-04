#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Worktree Merge Reminder Hook - PostToolUse (Bash)

功能：當偵測到 ticket track complete 命令時，檢查所有 worktree：
1. 未合併（ahead>0）→ 推送 merge 警告（既有功能）
2. 已合併（ahead=0，含 user worktree）→ 推送 cleanup reminder（W11-033 / PC-149 新增）
   - dirty worktree 額外提示先處理變更

Hook 類型：PostToolUse
匹配工具：Bash
退出碼：0 = 通過（stdout 警告顯示給用戶），2 = 阻擋（stderr 回饋給 Claude）
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
    is_subagent_environment,
    get_worktree_list,
    get_uncommitted_files,
    FileStatus,
)


def parse_worktree_list(logger) -> List[Tuple[str, str]]:
    """取得 (路徑, 分支名) 列表（排除 main）。

    0.2.1-W3-286：改用共用層 lib.git_utils.get_worktree_list(exclude_main
    =True)，取代自行 subprocess + porcelain 解析。detached worktree（無
    branch 值）依共用層慣例保留於原始清單，此處以 `wt.get("branch")` 真值
    過濾排除——與原行為一致（detached 無分支可供 `git log main..branch`
    比對，本就不應出現在此 tuple 清單中）。
    """
    worktrees = get_worktree_list(exclude_main=True)
    return [(wt["path"], wt["branch"]) for wt in worktrees if wt.get("branch")]


def get_unmerged_commits(branch: str, logger) -> List[str]:
    """取得分支相對於 main 的未合併 commit 摘要。"""
    try:
        result = subprocess.run(
            ["git", "log", f"main..{branch}", "--oneline"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git log main..%s 執行失敗", branch)
        return []

    if result.returncode != 0:
        logger.debug("git log main..%s 非零退出碼: %d", branch, result.returncode)
        return []

    commits = [line for line in result.stdout.strip().splitlines() if line]
    return commits


def get_dirty_files(path: str, logger) -> List[Tuple[str, str]]:
    """取得 worktree 未提交變更的檔案清單（含未追蹤檔案）。

    0.2.1-W3-273：由布林 dirty 判定升級為檔案清單，供呼叫端區分「未追蹤」
    （`git worktree remove --force` 會靜默丟棄，issue 46 症狀三）與「已追蹤
    但未 commit」（至少仍有 base 版本留在分支歷史，遺失風險較低）。

    Args:
        path: worktree 絕對路徑
        logger: logger 實例

    Returns:
        (status_code, filename) tuple 列表；``git status --porcelain`` 的原始
        兩字元狀態碼（如 ``"??"``、``" M"``、``"A "``）與檔名。無法判斷或無
        變更時回傳空列表。

    0.2.1-W3-286：改用共用層 lib.git_utils.get_uncommitted_files(cwd=...)，
    取代自行 subprocess + porcelain 解析；FileStatus 已封裝相同的
    (status, file_path) 結構，取捨與 worktree-remove-deliverable-check-hook
    的 _dirty_status 一致（不再區分 git 失敗與無變更，皆回傳空清單）。
    """
    return [(fs.status, fs.file_path) for fs in get_uncommitted_files(cwd=path)]


def is_worktree_dirty(path: str, logger) -> bool:
    """檢查 worktree 是否有未提交變更（含未追蹤檔案）。

    Args:
        path: worktree 絕對路徑
        logger: logger 實例

    Returns:
        True 表示 dirty（status --porcelain 非空），False 表示 clean 或無法判斷。
    """
    return bool(get_dirty_files(path, logger))


def is_ticket_complete_command(input_data: dict) -> bool:
    """判斷 Bash 輸出是否為 ticket track complete 命令。"""
    # 檢查工具輸入（命令本身）
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "ticket" in command and "complete" in command:
        return True

    return False


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("worktree-merge-reminder")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0

    if not input_data:
        return 0

    # subagent 環境跳過（代理人不執行 complete）
    if is_subagent_environment(input_data):
        return 0

    # 只在 ticket complete 命令時觸發
    if not is_ticket_complete_command(input_data):
        return 0

    logger.info("偵測到 ticket complete，檢查 worktree 合併狀態")

    worktrees = parse_worktree_list(logger)
    if not worktrees:
        logger.debug("無非 main 的 worktree")
        return 0

    # 分類：未合併 vs 已合併（ahead=0）
    unmerged = []
    merged = []  # (path, branch, dirty_files)
    for wt_path, branch in worktrees:
        commits = get_unmerged_commits(branch, logger)
        if commits:
            unmerged.append((wt_path, branch, commits))
        else:
            dirty_files = get_dirty_files(wt_path, logger)
            merged.append((wt_path, branch, dirty_files))

    if not unmerged and not merged:
        logger.info("所有 worktree 已合併且無需清理")
        return 0

    lines: List[str] = []

    # Section 1: 未合併警告（既有區塊）
    if unmerged:
        lines.append("[Worktree 合併提醒] 以下 worktree 有未合併回 main 的 commit：")
        lines.append("")
        for wt_path, branch, commits in unmerged:
            lines.append(f"  分支: {branch}")
            lines.append(f"  路徑: {wt_path}")
            lines.append(f"  待合併 commit: {len(commits)} 個")
            for commit in commits[:5]:
                lines.append(f"    - {commit}")
            if len(commits) > 5:
                lines.append(f"    ... 還有 {len(commits) - 5} 個")
            lines.append(f"  建議: git merge {branch} --no-edit")
            lines.append("")
        lines.append("請在 ticket 完成前合併這些 worktree 的變更。")
        if merged:
            lines.append("")

    # Section 2: 已合併 cleanup reminder（W11-033 / PC-149 新增）
    if merged:
        lines.append("[Worktree 清理提醒] 以下 worktree 已完全合併回 main，建議清理：")
        lines.append("")
        for wt_path, branch, dirty_files in merged:
            lines.append(f"  分支: {branch}")
            lines.append(f"  路徑: {wt_path}")
            if dirty_files:
                untracked = [f for code, f in dirty_files if code == "??"]
                tracked_modified = [f for code, f in dirty_files if code != "??"]
                lines.append("  狀態: 未提交變更（dirty）— 請先處理未提交/未追蹤檔案再移除")
                # 0.2.1-W3-273（issue 46 症狀三）：未追蹤檔案在 `worktree remove
                # --force` 下不進 git 追蹤，直接隨 worktree 目錄靜默丟棄（非
                # 「保留在分支歷史但需另行清理」——merge 只作用於已 commit 物件，
                # 未追蹤檔案從未進入該分支的任何 commit）。明確列出檔名而非僅
                # 標記 dirty，避免操作者誤判「反正已合併，強制移除頂多丟掉暫存」。
                if untracked:
                    lines.append("  [遺失警告] 以下檔案為未追蹤，強制移除將永久遺失：")
                    for f in untracked[:10]:
                        lines.append(f"    - {f}")
                    if len(untracked) > 10:
                        lines.append(f"    ... 還有 {len(untracked) - 10} 個")
                # 0.2.1-W3-280（issue 46 症狀四）：已追蹤但未 commit 的檔案，
                # base 版本雖留在分支歷史，但代理人寫入的「修改內容」本身從未
                # 進入任何 commit，強制移除仍會遺失該內容（與未追蹤檔同級風險，
                # 差別僅在遺失對象是「修改」而非「整檔」）。
                if tracked_modified:
                    lines.append(
                        "  [遺失警告] 以下檔案已追蹤但未提交，強制移除將遺失修改內容："
                    )
                    for f in tracked_modified[:10]:
                        lines.append(f"    - {f}")
                    if len(tracked_modified) > 10:
                        lines.append(f"    ... 還有 {len(tracked_modified) - 10} 個")
                # 0.2.1-W3-285：先前建議直接 `remove --force`，但 dirty worktree
                # 必然被 worktree-remove-deliverable-check-hook 的 Guard C 阻擋
                # （--force 不繞過該檢查），與本行建議互斥。改為導向「commit
                # 後 merge 再 remove」；--force 僅在確認可捨棄變更並清除後才
                # 有意義（因為那之後 working tree 已 clean，remove 本不需要
                # --force，故不建議捨棄路徑再加 --force）。
                lines.append("  建議（擇一）：")
                lines.append("    1. 保留變更並落地 main：")
                lines.append(
                    f"         git -C {wt_path} add <paths> && "
                    f'git -C {wt_path} commit -m "<message>" -- <paths>'
                )
                lines.append(f"         git merge {branch} --no-edit")
                lines.append("    2. 確認變更確為可捨棄後清除：")
                lines.append(f"         git -C {wt_path} restore .   # 還原已追蹤檔案的未提交修改")
                lines.append(f"         git -C {wt_path} clean -fd .   # 清除未追蹤檔案與目錄")
                lines.append("  驗證（處理後執行，確認已 clean 才可 remove）：")
                lines.append(f"    git -C {wt_path} status --porcelain   # 無輸出即代表 clean")
                lines.append(
                    f"    git worktree remove {wt_path}   "
                    "# 不需 --force；dirty 狀態下 --force 會被 Guard C 阻擋"
                )
            else:
                lines.append("  狀態: clean")
                lines.append(f"  建議: git worktree remove {wt_path}")
            lines.append("")
        lines.append("PC-149: ticket 完成後 worktree 殘留會累積 disk 與視圖污染。")

    message = "\n".join(lines)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    if unmerged:
        logger.warning("發現 %d 個 worktree 有未合併 commit", len(unmerged))
    if merged:
        logger.info("發現 %d 個已合併 worktree 待清理", len(merged))

    # 回傳 0（警告但不阻擋），讓 PM 決定是否處理
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-merge-reminder"))
