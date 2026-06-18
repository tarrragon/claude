#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Uncommitted Ticket MD Reminder Hook - PreToolUse Hook

功能: git commit 前偵測 working tree 內「已修改但未 commit 的 ticket md」，
      輸出 stderr 警告（不阻擋，exit 0），提醒人為將 ticket md 一併納入提交，
      避免手動 Edit ticket body 後遺失（W8-002 ANA 方案 4：狀態偵測）。

觸發時機: Bash 工具執行前（PreToolUse）

設計定位（W8-002 結論）:
  - auto-commit（W7-001）僅覆蓋 append-log 路徑；PM/agent 手動 Edit ticket md
    後 body 停留 working tree，最長暴露窗口至下次 commit。
  - 本 hook 為「狀態偵測」——偵測「ticket md 已修改但未 commit」此危險狀態本身，
    覆蓋所有修改路徑（含手動 Edit），不限 git 還原時刻。
  - 警告而非阻擋（exit 0），避免過度防護干擾流程。

可觀測性（quality-baseline 規則 4 / PC：避免 UI hook error）:
  - 提示走 stderr 直接 print（非 logger.error/warning，後者寫 stderr 會被
    CC runtime 當作 hook 失敗觸發 UI hook error，IMP-048）。
  - 內部例外與 debug 走檔案日誌（logger.debug/info）。

行為: 不阻擋（exit 0）；偵測到 modified/staged/untracked ticket md → stderr 警告。
"""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# git_utils 位於 .claude/lib/（專案級共用程式庫）
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

try:
    from hook_utils import (
        setup_hook_logging,
        run_hook_safely,
        read_json_from_stdin,
    )
    from git_utils import get_uncommitted_files
except ImportError as e:
    # ImportError 不應 exit(1) 阻斷流程；降級為 no-op（fail-open）
    print(f"[Hook Import Warning] {Path(__file__).name}: {e}", file=sys.stderr)

    def setup_hook_logging(name):
        import logging
        return logging.getLogger(name)

    def run_hook_safely(fn, name):
        try:
            return fn()
        except Exception:
            return 0

    def read_json_from_stdin(logger):
        return None

    def get_uncommitted_files():
        return []


# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# 排除的命令模式（非 commit 操作或不需提醒的 commit 變體）
EXCLUDED_COMMAND_PATTERNS = (
    "git log",
    "git show",
    "git diff",
    "git status",
)

# ticket md 路徑特徵：docs/work-logs/.../tickets/*.md
# 同時支援階層結構（v1/v1.0/v1.0.0/tickets/）與扁平結構（v0.29.0/tickets/）
_TICKET_MD_PATTERN = re.compile(r"docs/work-logs/.*/tickets/[^/]+\.md$")


# ============================================================================
# 偵測邏輯
# ============================================================================

def is_git_commit_command(command: str) -> bool:
    """判斷 Bash 命令是否為 git commit 操作（排除 log/show/diff/status 等讀取）。"""
    if not command or "git commit" not in command:
        return False
    for excluded in EXCLUDED_COMMAND_PATTERNS:
        if excluded in command:
            return False
    return True


def is_ticket_md_path(file_path: str) -> bool:
    """判斷檔案路徑是否為 ticket md（docs/work-logs/**/tickets/*.md）。"""
    if not file_path:
        return False
    return bool(_TICKET_MD_PATTERN.search(file_path))


def find_uncommitted_ticket_md() -> list[str]:
    """
    回傳 working tree 內所有未 commit 的 ticket md 路徑。

    涵蓋 modified（已追蹤改動）、staged（已暫存）、untracked（新增）三類，
    任一未進入 commit 的 ticket md 都屬遺失風險範圍。
    """
    result = []
    for file_status in get_uncommitted_files():
        path = file_status.file_path
        # Renamed/Copied 格式 "old -> new" 取新名比對
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if is_ticket_md_path(path):
            result.append(path)
    return result


def build_warning_message(ticket_md_paths: list[str]) -> str:
    """組裝 stderr 警告訊息。"""
    lines = [
        "[未 commit ticket md 提醒]",
        "偵測到以下 ticket md 已修改但尚未納入此次 commit，",
        "若手動 Edit 後未一併提交，body 內容可能在後續 git 還原時遺失（PC-185）：",
    ]
    for path in ticket_md_paths:
        lines.append(f"  - {path}")
    lines.append("建議：確認這些 ticket md 是否應 git add 後一併 commit。")
    return "\n".join(lines)


# ============================================================================
# 主入口
# ============================================================================

def main() -> int:
    logger = setup_hook_logging("uncommitted-ticket-md-reminder")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return EXIT_SUCCESS

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        return EXIT_SUCCESS

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    if not is_git_commit_command(command):
        logger.debug("跳過: 非 git commit 命令")
        return EXIT_SUCCESS

    ticket_md_paths = find_uncommitted_ticket_md()
    if not ticket_md_paths:
        logger.debug("無未 commit 的 ticket md，靜默通過")
        return EXIT_SUCCESS

    logger.info("偵測到 %d 個未 commit 的 ticket md，輸出警告", len(ticket_md_paths))
    # 直接 print 至 stderr（非 logger.warning，避免被當 hook 失敗，IMP-048）
    print(build_warning_message(ticket_md_paths), file=sys.stderr)
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "uncommitted-ticket-md-reminder")
    sys.exit(exit_code)
