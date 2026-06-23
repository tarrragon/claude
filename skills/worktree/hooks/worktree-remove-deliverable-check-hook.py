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

Hook 類型：PreToolUse
匹配工具：Bash
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）
"""

import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin, run_git


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

    解析 `git worktree list --porcelain`，匹配 worktree 路徑（容許相對/絕對差異）。

    Returns:
        分支名（去 refs/heads/ 前綴），或 None（detached / 找不到 / git 失敗）
    """
    output = run_git(["git", "worktree", "list", "--porcelain"], timeout=10, logger=logger)
    if not output:
        return None

    target = Path(worktree_path).name  # 用末段比對，避免相對/絕對路徑差異
    current_path = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line.startswith("branch ") and current_path is not None:
            if Path(current_path).name == target:
                branch_full = line[len("branch "):]
                if branch_full.startswith("refs/heads/"):
                    return branch_full[len("refs/heads/"):]
                return branch_full
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
        if not branch:
            logger.info("worktree %s 無對應分支（detached/找不到），略過", path)
            continue

        files = _unmerged_files(branch, logger)
        if files is None:
            logger.warning("分支 %s 未合併檢查失敗（git 錯誤），放行", branch)
            continue
        if not files:
            logger.info("分支 %s 無未合併交付物，放行 remove", branch)
            continue

        files_list = "\n".join("  - {}".format(f) for f in sorted(files))
        message = BLOCK_MESSAGE.format(
            path=path, branch=branch, count=len(files), files=files_list
        )
        print(message, file=sys.stderr)
        logger.warning(
            "阻擋 remove：分支 %s 有 %d 個未合併交付物檔案", branch, len(files)
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-remove-deliverable-check"))
