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
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

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
from lib.ticket_command_parse import has_complete_command
from lib.bash_tool_response import (
    FAILURE_EVENT_NAME, is_failure_event, auto_commit_failure_as_success,
)


def merge_command(branch: str, logger) -> str:
    """落地 main 的建議指令（`/worktree merge`）。

    lazy import worktree_manager，避免為建議字串在載入期引入約 2000 行模組的
    import 失敗點；失敗時退回通用字面並記 warning。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from worktree_manager import merge_suggestion_command
        return merge_suggestion_command(branch)
    except Exception as exc:  # 建議字串不得使 hook 失效；已記日誌後退回
        logger.warning("無法載入 worktree_manager，建議退回通用字面：%s", exc)
        return "/worktree merge --branch {}".format(shlex.quote(branch))


def cleanup_command(branch: str, logger) -> str:
    """已合併 worktree 的清理建議（`/worktree cleanup`）。

    判定沿用 worktree_manager 的 `_cleanup_target_arg`（ticket ID 走 positional，
    其餘走 `--branch <quoted>`）；lazy import 與失敗退回同 merge_command。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from worktree_manager import _cleanup_target_arg, extract_ticket_id_from_branch
        target = _cleanup_target_arg(extract_ticket_id_from_branch(branch) or branch)
        return "/worktree cleanup {}".format(target)
    except Exception as exc:  # 建議字串不得使 hook 失效；已記日誌後退回
        logger.warning("無法載入 worktree_manager，建議退回通用字面：%s", exc)
        return "/worktree cleanup --branch {}".format(shlex.quote(branch))


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


def get_locked_paths(logger) -> Optional[Set[str]]:
    """取得被 git 標為 locked 的 worktree 路徑集合。

    執行中的代理人 worktree 帶 locked 標記，已結束者不帶。
    讀取失敗回傳 None（呼叫端據此 fail-open：不列入建議清理）。
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("讀取 worktree locked 狀態失敗: %s", exc)
        return None
    if result.returncode != 0:
        logger.warning("git worktree list --porcelain 非零退出碼: %d", result.returncode)
        return None

    locked: Set[str] = set()
    current: Optional[str] = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current = line[len("worktree "):]
        elif line == "locked" or line.startswith("locked "):
            if current:
                locked.add(current)
    return locked


def has_no_own_commits(branch: str, logger) -> Optional[bool]:
    """分支 tip 是否落在 main 的 first-parent 歷史上（分支沒有自己的提交）。

    True = 零提交（僅為派發基底）；False = 有自己的提交；None = 判定失敗。
    fast-forward 合併的分支會被判為零提交，結果是少給一筆建議（偏安全）。
    """
    try:
        tip = subprocess.run(
            ["git", "rev-parse", branch],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        history = subprocess.run(
            ["git", "rev-list", "--first-parent", "main"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("判定 %s 是否零提交失敗: %s", branch, exc)
        return None
    tip_sha = tip.stdout.strip()
    if tip.returncode != 0 or history.returncode != 0 or not tip_sha:
        logger.warning("判定 %s 是否零提交失敗: rev-parse/rev-list 無有效輸出", branch)
        return None
    return tip_sha in history.stdout.split()


def classify_worktrees(worktrees: List[Tuple[str, str]], logger):
    """分類 worktree：(unmerged, merged, in_progress)。

    ahead=0 的 worktree 中，locked、零提交、或判定失敗者歸 in_progress
    （不建議清理）；其餘才歸 merged。
    """
    locked = get_locked_paths(logger)
    unmerged = []
    merged = []  # (path, branch, dirty_files)
    in_progress = []  # (path, branch, reason)
    for wt_path, branch in worktrees:
        commits = get_unmerged_commits(branch, logger)
        if commits:
            unmerged.append((wt_path, branch, commits))
            continue
        if locked is None:
            in_progress.append((wt_path, branch, "無法判定 locked 狀態"))
            continue
        if wt_path in locked:
            in_progress.append((wt_path, branch, "worktree 已 locked"))
            continue
        zero = has_no_own_commits(branch, logger)
        if zero is None:
            in_progress.append((wt_path, branch, "無法判定是否零提交"))
        elif zero:
            in_progress.append((wt_path, branch, "分支尚無自己的提交"))
        else:
            merged.append((wt_path, branch, get_dirty_files(wt_path, logger)))
    return unmerged, merged, in_progress


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

    # token 位置辨識（complete / finish / batch-complete）；解析失敗（None）
    # 視為非完成命令，提示類不觸發
    return has_complete_command(command) is True


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

    # PostToolUseFailure：僅結束碼 75（動作完成、auto-commit 失敗）沿用完成後提醒
    event_name = "PostToolUse"
    if is_failure_event(input_data):
        input_data = auto_commit_failure_as_success(input_data)
        if input_data is None:
            logger.debug("失敗事件非結束碼 75，不處理")
            return 0
        event_name = FAILURE_EVENT_NAME

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
    unmerged, merged, in_progress = classify_worktrees(worktrees, logger)

    if not unmerged and not merged and not in_progress:
        logger.info("所有 worktree 已合併且無需清理")
        return 0

    lines: List[str] = []

    # 進行中派發：明示不建議清理，避免移除代理人進行中的工作區
    if in_progress:
        lines.append("[Worktree 進行中派發] 以下 worktree 不建議清理：")
        for wt_path, branch, reason in in_progress:
            lines.append(f"  分支: {branch}  路徑: {wt_path}  原因: {reason}")
        lines.append("")

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
            lines.append(f"  建議: {merge_command(branch, logger)}")
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
                # 規則七：精確 add → 核對 index → 裸 commit（禁 pathspec 提交）；
                # linked worktree 有獨立 index，核對僅涵蓋本 worktree。
                lines.append(f"         git -C {wt_path} add <exact-path>")
                lines.append(f"         git -C {wt_path} diff --cached --name-only   # 確認只含目標檔")
                lines.append(f'         git -C {wt_path} commit -m "<message>"')
                lines.append(f"         {merge_command(branch, logger)}")
                lines.append("    2. 確認變更確為可捨棄後清除：")
                lines.append(f"         git -C {wt_path} restore .   # 還原已追蹤檔案的未提交修改")
                lines.append(f"         git -C {wt_path} clean -fd .   # 清除未追蹤檔案與目錄")
                lines.append("  驗證（處理後執行，確認已 clean 才可 remove）：")
                lines.append(f"    git -C {wt_path} status --porcelain   # 無輸出即代表 clean")
                lines.append(
                    f"    {cleanup_command(branch, logger)}   "
                    "# 不需 --force；dirty 狀態下 --force 會被 Guard C 阻擋"
                )
            else:
                lines.append("  狀態: clean")
                lines.append(f"  建議: {cleanup_command(branch, logger)}")
            lines.append("")
        lines.append("PC-149: ticket 完成後 worktree 殘留會累積 disk 與視圖污染。")

    message = "\n".join(lines)
    output = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
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
