#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Worktree Commit-Before-Dispatch Hook - PreToolUse (Agent)

功能：派發 worktree agent 前，檢查 main 上是否有未 commit 的 tracked 變更。
未 commit 的變更可能在 worktree 操作後因 stash/checkout 丟失（PC-019）。

Hook 類型：PreToolUse
匹配工具：Agent
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    emit_hook_output,
)


# W4-008：origin/main 落後 local main 達此門檻視為高風險，改走 deny（非僅警告）
LAG_DENY_THRESHOLD = 10

BLOCK_MESSAGE = """[PC-019 防護] main 上有未 commit 的 tracked 變更，禁止派發 worktree agent

未 commit 的檔案：
{files}

修復方式：
  先 commit main 上的變更，再派發 worktree agent
  git add <files> && git commit -m "chore: pre-dispatch commit"

詳見: .claude/pm-rules/worktree-operations.md（階段 1：派發前）"""

# W3-007 方案 A：origin/main 落後 local main 警告訊息（非阻擋，走 additionalContext）
ORIGIN_BEHIND_WARNING = """[W3-007 警告] origin/main 落後 local main {count} 個 commit

CC runtime 的 worktree 隔離以 origin/main（remote-tracking ref）為 base，
而非 local main HEAD。origin/main 落後時，worktree 會建在 stale 基底上，
缺少最新本地 commit（W2-013 實證需 agent 手動 recovery）。

建議：派發前先 push local main
  git push origin main

詳見: .claude/pm-rules/parallel-dispatch.md（worktree base 與 push-first 紀律）"""

# W4-008：origin/main 落後達 LAG_DENY_THRESHOLD 以上，改為阻擋派發（stderr，非 JSON）
ORIGIN_BEHIND_DENY_MESSAGE = """[W4-008 防護] origin/main 落後 local main {count} 個 commit，超過門檻 {threshold}，禁止派發 worktree agent

CC runtime 的 worktree 隔離以 origin/main（remote-tracking ref）為 base，
而非 local main HEAD。落後過多時 worktree 會建在嚴重過時的基底上，
代理人可能重建已存在檔案並產生無法直接合併的產出（0.2.0-W4-006 事故實證）。

修復方式：
  git push origin main

詳見: .claude/pm-rules/parallel-dispatch.md（worktree base 與 push-first 紀律）"""


def _check_origin_behind(logger, input_data: dict) -> bool:
    """檢查 origin/main 是否落後 local main，依落後量分派行為矩陣。

    行為矩陣（W4-008）：
      lag == 0            靜默，不輸出
      0 < lag < 閾值       emit_hook_output additionalContext（pm_only），exit 0（不阻擋）
      lag >= 閾值          stderr 輸出修復指令，回傳 True（呼叫端 exit 2 阻擋）

    Args:
        logger: hook logger，供記錄檢查結果與失敗原因（可觀測性規則 4）
        input_data: hook stdin JSON，供 emit_hook_output 判定觸發方（pm_only 過濾）

    Returns:
        bool: True 表示應阻擋派發（lag >= LAG_DENY_THRESHOLD）
    """
    try:
        # 計算 origin/main..main 的 commit 數（local main 領先 origin/main 的量）
        result = subprocess.run(
            ["git", "rev-list", "--count", "origin/main..main"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        # git 不可用 / 超時：無法判斷，記錄後略過（不阻擋派發）
        logger.warning("origin/main 落後檢查失敗：%s", exc)
        return False

    if result.returncode != 0:
        # origin/main ref 不存在（未 push 過 / 無 remote）等情況，略過
        logger.info("origin/main 落後檢查略過（git rev-list 非零退出）")
        return False

    count_str = result.stdout.strip()
    if not count_str.isdigit():
        logger.info("origin/main 落後檢查略過（無法解析 commit 數）")
        return False

    behind_count = int(count_str)

    if behind_count == 0:
        logger.info("origin/main 與 local main 同步，無需警告")
        return False

    if behind_count >= LAG_DENY_THRESHOLD:
        message = ORIGIN_BEHIND_DENY_MESSAGE.format(
            count=behind_count, threshold=LAG_DENY_THRESHOLD
        )
        print(message, file=sys.stderr)
        logger.warning(
            "阻擋 worktree 派發：origin/main 落後 %d 個 commit（>= 門檻 %d）",
            behind_count, LAG_DENY_THRESHOLD,
        )
        return True

    # 0 < behind_count < LAG_DENY_THRESHOLD：警告但不阻擋，走 additionalContext 確保 PM 可見
    emit_hook_output(
        "PreToolUse",
        additional_context=ORIGIN_BEHIND_WARNING.format(count=behind_count),
        audience="pm_only",
        input_data=input_data,
    )
    logger.warning("origin/main 落後 local main %d 個 commit（additionalContext 已發出）", behind_count)
    return False


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("worktree-commit-before-dispatch")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON")
        return 0  # 解析失敗不阻擋

    if not input_data:
        return 0

    tool_input = input_data.get("tool_input", {})
    isolation = tool_input.get("isolation", "")

    # 只檢查 worktree 隔離的派發
    if isolation != "worktree":
        logger.debug("非 worktree 隔離，跳過檢查")
        return 0

    logger.info("偵測到 worktree 派發，檢查未 commit 變更")

    # W4-008：origin/main 落後檢查先於 PC-019 未 commit 變更檢查
    # lag >= LAG_DENY_THRESHOLD 時直接阻擋（stderr，不 emit JSON）
    if _check_origin_behind(logger, input_data):
        return 2

    # 檢查 tracked 檔案是否有未 commit 的變更
    try:
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        staged = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git 命令執行失敗")
        return 0  # git 失敗不阻擋

    changed_files = set()
    if unstaged.stdout.strip():
        changed_files.update(unstaged.stdout.strip().split("\n"))
    if staged.stdout.strip():
        changed_files.update(staged.stdout.strip().split("\n"))

    if not changed_files:
        logger.info("無未 commit 變更，放行")
        return 0

    files_list = "\n".join(f"  - {f}" for f in sorted(changed_files))
    message = BLOCK_MESSAGE.format(files=files_list)
    print(message, file=sys.stderr)
    logger.warning("阻擋 worktree 派發：%d 個未 commit 檔案", len(changed_files))
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "worktree-commit-before-dispatch"))
