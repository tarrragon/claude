#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Worktree Remove Deliverable-On-Main Check Hook - PreToolUse (Bash)

Guard A（來源 1.2.0-W1-028 事故一）：偵測 `git worktree remove`，在移除前檢查
該 worktree 分支是否仍有未 merge 進 main 的 commit（即未落地的交付物）。

事故重現：parsley 在 worktree 建檔+測試通過但只 ticket CLI auto-commit metadata，
未 git commit 產品碼；PM merge 僅得 metadata，再 `worktree remove --force` 致產品碼
永久遺失（git fsck 無 unreachable）。

本 hook 防護：remove 前若 `git log main..<branch>` 有觸及檔案的未合併 commit →
阻擋（exit 2），要求 PM 先 merge/cherry-pick 或顯式確認。
`--force` 不繞過本檢查（檢查在 CC runtime hook 層，先於 git 執行）。

Guard C（來源 0.2.1-W3-280，issue 46 症狀四；0.2.1-W3-285 由 Guard B 改名，避免
與 worktree-pre-dispatch-branch-drift-hook 的 Guard B 撞號，見 worktree-operations.md
第 32 行代號分配說明）：merge 完成後 Guard A 即放行，但 worktree working tree 內
未提交的修改（已追蹤或未追蹤）無人把關，`remove --force` 會使其永久遺失。本
hook 在 remove 前額外檢查 target worktree 的 `git status --porcelain`，非空即
阻擋並列出將遺失的內容（依未追蹤/已追蹤分組，比照 worktree-merge-reminder-hook）。

Hook 類型：PreToolUse
匹配工具：Bash
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）
"""

import os
import re
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    run_git,
    get_worktree_list,
    get_uncommitted_files,
    FileStatus,
)


# git worktree remove [--force] <path>
_REMOVE_PATTERN = re.compile(
    r"git\s+worktree\s+remove\b(?P<rest>[^\n;&|]*)",
)

BLOCK_MESSAGE = """[1.2.0-W1-028 Guard A] worktree 分支有未 merge 進 main 的交付物，禁止 remove

worktree: {path}
分支: {branch}
未合併 commit（{count} 個）觸及檔案：
{files}

事故背景：worktree 建好+測試通過但產品碼未進 main 時 remove，會永久遺失
（git fsck 無 unreachable）。這正是 1.2.0-W1-028 事故一的根因。

修復方式（擇一）：
  1. 先 merge：git checkout main && git merge {branch} --no-edit
  2. 或 cherry-pick 有價值 commit 後再 remove
  3. 用世界平面固定值驗證交付物已在 main（tool-output-trust 規則 3）：
       git show main:<where.files> | head    # 有內容才代表已落地
       git ls-tree -r main --name-only | grep <file>

確認交付物確在 main 後，再執行 remove。

詳見：.claude/pm-rules/worktree-operations.md（階段 3：清理後 / Guard A）"""


def _split_dirty_lines(dirty_lines: List[str]) -> Tuple[List[str], List[str]]:
    """依 porcelain 狀態碼分組：未追蹤（``??``）vs 已追蹤但未提交（其餘）。

    比照 worktree-merge-reminder-hook.py 的 ``get_dirty_files`` 分組邏輯
    （0.2.1-W3-285），讓 Guard C 阻擋訊息呈現與清理提醒訊息一致，避免同一
    worktree 在兩個 hook 的訊息中出現不同分類。
    """
    untracked = [line[3:] for line in dirty_lines if line[:2] == "??"]
    tracked_modified = [line[3:] for line in dirty_lines if line[:2] != "??"]
    return untracked, tracked_modified


def _format_dirty_block_message(path: str, branch: Optional[str], dirty_lines: List[str]) -> str:
    """組出 Guard C（未提交變更）阻擋訊息。

    0.2.1-W3-285 三項修正：(a) 依未追蹤/已追蹤分組列出檔案，比照
    worktree-merge-reminder-hook 的清理提醒呈現；(b) restore 與 clean 拆為
    可逐字執行的獨立命令並標明作用對象（原「restore/clean」非合法命令
    語法），commit 選項補上後續的 merge 步驟（否則 commit 後分支仍未合併，
    Guard A 會接著擋下 remove）；(c) `git status --porcelain` 為唯讀命令，
    移出「修復方式擇一」改列為獨立的「驗證」步驟——原本混列會讓選它的人
    誤以為已處理，實際仍會被擋。
    """
    untracked, tracked_modified = _split_dirty_lines(dirty_lines)

    lines: List[str] = [
        "[0.2.1-W3-280 Guard C] worktree 有未提交的變更，禁止 remove",
        "",
        "worktree: {}".format(path),
    ]
    if untracked:
        lines.append("未追蹤（{} 項，remove --force 會靜默丟棄）：".format(len(untracked)))
        lines.extend("  - {}".format(f) for f in untracked)
    if tracked_modified:
        lines.append("已追蹤但未提交（{} 項，remove --force 會遺失修改內容）：".format(len(tracked_modified)))
        lines.extend("  - {}".format(f) for f in tracked_modified)

    lines.extend([
        "",
        "背景：merge 完成後 Guard A 即放行，但 working tree 內未提交的修改（已追蹤或",
        "未追蹤）不在 commit 歷史中，`remove --force` 會使其永久遺失。這是 1.2.0-W1-028",
        "事故一在「merge 已完成」路徑下的變體（issue 46 症狀四）。",
        "",
        "修復方式（擇一，完成後執行下方「驗證」步驟確認）：",
        "  1. 保留變更並落地 main：",
        '       git -C {} add <paths> && git -C {} commit -m "<message>" -- <paths>'.format(path, path),
    ])
    if branch:
        lines.append("       git merge {} --no-edit".format(branch))
    else:
        lines.append("       git merge <branch> --no-edit   # <branch> 為此 worktree 對應分支")
    lines.extend([
        "  2. 確認變更確為可捨棄（如暫存/測試殘留）後清除：",
        "       git -C {} restore .   # 還原已追蹤檔案的未提交修改".format(path),
        "       git -C {} clean -fd .   # 清除未追蹤檔案與目錄".format(path),
        "",
        "驗證（處理後執行，確認 working tree 已 clean 才可 remove）：",
        "  git -C {} status --porcelain   # 無輸出即代表 clean".format(path),
        "",
        "詳見：.claude/pm-rules/worktree-operations.md（階段 3：清理後 / Guard C）",
    ])
    return "\n".join(lines)


def _extract_remove_paths(command: str, logger) -> List[str]:
    """從 Bash 命令抽取所有 `git worktree remove` 的目標路徑。

    支援單命令與 `&&` / `;` 串接的多個 remove。批量清理（while read）形式
    無法靜態解析路徑，回傳空清單由呼叫端略過（不阻擋，避免誤擋批次腳本）。

    Args:
        command: 完整 Bash 命令字串
        logger: hook logger，供記錄解析結果（可觀測性規則 4）

    Returns:
        目標 worktree 路徑清單（去除 flag）
    """
    paths: List[str] = []
    for match in _REMOVE_PATTERN.finditer(command):
        rest = match.group("rest").strip()
        # 拆 token，濾掉 flag（--force / -f 等）
        tokens = [t for t in rest.split() if not t.startswith("-")]
        if tokens:
            # 第一個非 flag token 視為路徑
            paths.append(tokens[0].strip("'\""))
    logger.debug("解析到 %d 個 remove 路徑：%s", len(paths), paths)
    return paths


def _branch_of_worktree(worktree_path: str, logger) -> Optional[str]:
    """查 worktree 路徑對應的分支名。

    0.2.1-W3-286：改用共用層 lib.git_utils.get_worktree_list，路徑比對鍵
    採正規化後的絕對路徑（Context Bundle 分歧表結論）——原本以 `Path(...).
    name` 末段比對，同名不同層的兩個 worktree（如
    `.claude/worktrees/agent-abc` 與另一 repo 下同名目錄）會誤配；絕對路徑
    比對可正確區分。

    Returns:
        分支名（get_worktree_list 已剝除 refs/heads/ 前綴），或 None
        （detached / 找不到 / git 失敗）
    """
    worktrees = get_worktree_list()
    if not worktrees:
        return None

    target = os.path.normpath(os.path.abspath(worktree_path))
    for wt in worktrees:
        wt_path = wt.get("path", "")
        if wt_path and os.path.normpath(os.path.abspath(wt_path)) == target:
            return wt.get("branch")
    return None


def _unmerged_files(branch: str, logger) -> Optional[List[str]]:
    """查 `main..<branch>` 未合併 commit 觸及的檔案。

    Returns:
        檔案清單（可能空 = 無未合併產出）；None = git 查詢失敗（不阻擋）
    """
    # 先確認有未合併 commit
    log_out = run_git(
        ["git", "log", "main..{}".format(branch), "--oneline"], timeout=10, logger=logger
    )
    if log_out is None:
        return None  # git 失敗，不阻擋
    if not log_out.strip():
        return []  # 無未合併 commit

    diff_out = run_git(
        ["git", "diff", "--name-only", "main...{}".format(branch)], timeout=10, logger=logger
    )
    if diff_out is None:
        return None
    return [f for f in diff_out.splitlines() if f.strip()]


def _dirty_status(worktree_path: str, logger) -> List[str]:
    """查 target worktree 的未提交變更清單（0.2.1-W3-286 改用共用層）。

    改用 lib.git_utils.get_uncommitted_files(cwd=...)，回傳與原 porcelain
    行格式相容的字串清單（FileStatus.__str__ 輸出 "XY filename"）。

    行為變更（收斂取捨，記入 Solution）：共用層不區分「git 查詢失敗」與
    「無變更」，兩者皆回傳空清單。對主呼叫端 main() 而言結果一致——
    兩者都落在 `if not dirty_lines` 分支（不阻擋 remove，Guard C 放行），
    差異僅在無法輸出「git 查詢失敗」的獨立 debug 訊息。

    Returns:
        `"XY filename"` 格式的行清單（可能空 = clean 或查詢失敗）
    """
    return [str(fs) for fs in get_uncommitted_files(cwd=worktree_path)]


def _guard_a(path: str, branch: Optional[str], logger) -> Optional[str]:
    """Guard A：檢查分支是否有未 merge 進 main 的交付物。

    回傳非 None 即為阻擋訊息；回傳 None 表示放行（含分支查找失敗、無對應
    分支、git 查詢失敗、無未合併交付物等各種放行情境，皆已於函式內記錄
    對應日誌）。
    """
    if not branch:
        logger.info("worktree %s 無對應分支（detached/找不到），略過 Guard A", path)
        return None

    files = _unmerged_files(branch, logger)
    if files is None:
        logger.warning("分支 %s 未合併檢查失敗（git 錯誤），放行 Guard A", branch)
        return None
    if not files:
        logger.info("分支 %s 無未合併交付物，Guard A 放行", branch)
        return None

    files_list = "\n".join("  - {}".format(f) for f in sorted(files))
    logger.warning("阻擋 remove：分支 %s 有 %d 個未合併交付物檔案", branch, len(files))
    return BLOCK_MESSAGE.format(path=path, branch=branch, count=len(files), files=files_list)


def _guard_c(path: str, branch: Optional[str], logger) -> Optional[str]:
    """Guard C（0.2.1-W3-280，0.2.1-W3-285 由 Guard B 改名避免撞號）：檢查
    target working tree 本身是否有未提交變更。不依賴 Guard A 的分支查找是否
    成功——即使找不到分支，working tree 仍可能有需要保留的未提交內容。
    """
    dirty_lines = _dirty_status(path, logger)
    if dirty_lines is None:
        logger.warning("worktree %s 狀態查詢失敗（git 錯誤），放行 Guard C", path)
        return None
    if not dirty_lines:
        logger.info("worktree %s 無未提交變更，Guard C 放行", path)
        return None

    logger.warning("阻擋 remove：worktree %s 有 %d 項未提交變更", path, len(dirty_lines))
    return _format_dirty_block_message(path, branch, dirty_lines)


# 表驅動 Guard 清單：新增 Guard 只需在此 tuple 加一個元素，不需在 main() 加分支。
# 每個 guard 簽章一致：(path, branch, logger) -> Optional[str]（阻擋訊息或 None）。
GUARDS: Tuple[Callable[[str, Optional[str], "object"], Optional[str]], ...] = (
    _guard_a,
    _guard_c,
)


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("worktree-remove-deliverable-check")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        return 0

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")
    if not command or "worktree" not in command or "remove" not in command:
        logger.debug("非 worktree remove 命令，放行")
        return 0

    paths = _extract_remove_paths(command, logger)
    if not paths:
        logger.info("worktree remove 命令但無法靜態解析路徑（批量腳本？），放行")
        return 0

    for path in paths:
        branch = _branch_of_worktree(path, logger)
        for guard in GUARDS:
            message = guard(path, branch, logger)
            if message:
                print(message, file=sys.stderr)
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-remove-deliverable-check"))
