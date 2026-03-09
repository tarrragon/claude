#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Commit Handoff Hook - PostToolUse Hook

功能: 偵測 git commit 成功後，輸出 AskUserQuestion 場景 11 提醒。
每次 commit 都是 context 切換的決策點。

觸發時機: Bash 工具執行後
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 檢查 command 是否包含 git commit（排除 --amend 等變體）
  3. 檢查 stdout 是否包含 commit 成功標記
  4. 若偵測成功，輸出 AskUserQuestionMessages.COMMIT_HANDOFF_REMINDER

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息
"""

import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    get_current_version_from_todolist,
)
from lib.hook_messages import AskUserQuestionMessages, CoreMessages
from lib.ask_user_question_reminders import AskUserQuestionReminders

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# 排除的命令模式（非 commit 操作）
EXCLUDED_COMMAND_PATTERNS = [
    "git log",
    "git show",
    "git diff",
    "git status",
    "git commit --amend",
]

# 自動跳過 #16 的 commit 類型（conventional commit 前綴）
SKIP_SCENE16_COMMIT_PREFIXES = frozenset({
    "docs",
    "chore",
    "style",
    "revert",
    "test",
    "ci",
    "build",
})

# commit 成功標記
COMMIT_SUCCESS_MARKERS = [
    "files changed",
    "file changed",
    "insertions(+)",
    "deletions(-)",
    "create mode",
]

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}


# ============================================================================
# 主要邏輯
# ============================================================================

def is_git_commit_command(command: str) -> bool:
    """
    判斷是否為 git commit 命令

    Args:
        command: Bash 命令字串

    Returns:
        bool - 是否為 git commit 操作（排除 --amend 等特殊情況）
    """
    if "git commit" not in command:
        return False

    # 排除不需要提醒的 commit 變體
    for excluded in EXCLUDED_COMMAND_PATTERNS:
        if excluded in command:
            return False

    return True


def is_commit_successful(stdout: str) -> bool:
    """
    判斷 commit 是否成功

    Args:
        stdout: Bash 命令的標準輸出

    Returns:
        bool - 是否偵測到 commit 成功標記
    """
    for marker in COMMIT_SUCCESS_MARKERS:
        if marker in stdout:
            return True
    return False


def extract_commit_type(command: str) -> str:
    """
    從 git commit 命令中提取 conventional commit 類型

    支援格式：
    - git commit -m "type: ..."
    - git commit -m "type(scope): ..."
    - git commit -m "$(cat <<'EOF'\ntype: ...\nEOF\n)"

    Args:
        command: Bash 命令字串

    Returns:
        str - commit 類型（如 "docs", "chore"），無法提取時回傳 ""
    """
    # 匹配 -m "type: ..." 或 -m "type(scope): ..."
    match = re.search(r'-m\s+["\']([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    # 匹配 heredoc 中的類型（COMMIT_MSG=... 或直接在 EOF 區塊）
    match = re.search(r'\n\s*([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    return ""


# ============================================================================
# Wave 完成偵測邏輯
# ============================================================================


def scan_wave_tickets(
    project_dir: Path,
    version: str,
    logger
) -> List[Dict[str, Optional[str]]]:
    """
    掃描版本目錄中的 Ticket 檔案，回傳 wave 和 status 的清單

    Args:
        project_dir: 專案根目錄
        version: 版本號（如 "0.1.0"）
        logger: 日誌物件

    Returns:
        list - [{wave, status}] 清單，其中 wave 和 status 可能為 None
    """
    tickets_dir = project_dir / "docs" / "work-logs" / f"v{version}" / "tickets"

    if not tickets_dir.exists():
        logger.debug(f"Ticket 目錄不存在: {tickets_dir}")
        return []

    tickets = []

    try:
        ticket_files = list(tickets_dir.glob("*.md"))
        logger.debug(f"在 {tickets_dir} 找到 {len(ticket_files)} 個 Ticket 檔案")

        for ticket_file in ticket_files:
            try:
                content = ticket_file.read_text(encoding="utf-8")

                # 解析 YAML frontmatter
                wave = None
                status = None

                if content.startswith("---"):
                    frontmatter_end = content.find("---", 3)
                    if frontmatter_end > 0:
                        frontmatter = content[:frontmatter_end]

                        # 提取 wave: 和 status: 欄位
                        wave_match = re.search(r"wave:\s*(\d+)", frontmatter)
                        if wave_match:
                            wave = wave_match.group(1)

                        status_match = re.search(r"status:\s*(\S+)", frontmatter)
                        if status_match:
                            status = status_match.group(1)

                tickets.append({"wave": wave, "status": status, "file": ticket_file.name})
            except Exception as e:
                logger.debug(f"無法解析 Ticket 檔案 {ticket_file.name}: {e}")
                tickets.append({"wave": None, "status": None, "file": ticket_file.name})

        logger.debug(f"掃描完成，共 {len(tickets)} 個 Ticket")
        return tickets

    except Exception as e:
        logger.warning(f"掃描 Ticket 目錄失敗: {e}")
        return []


def detect_wave_completion(logger) -> bool:
    """
    偵測是否為情境 C（當前 Wave 完成，同 Wave 無 pending ticket）

    邏輯：
    1. 讀取 current_version from docs/todolist.yaml
    2. 掃描 ticket 目錄
    3. 解析 frontmatter 取得 wave 和 status
    4. 找到 in_progress ticket 的 wave（當前 Wave）
    5. 統計同 wave 的 pending ticket 數量
    6. pending == 0 → 情境 C（True）

    Args:
        logger: 日誌物件

    Returns:
        bool - 是否為情境 C（Wave 完成）。若無 in_progress ticket 或讀取失敗，安全降級為 False
    """
    try:
        project_dir = get_project_root()

        # Step 1: 讀取當前版本
        current_version = get_current_version_from_todolist(project_dir, logger)
        if not current_version:
            logger.debug("無法讀取 current_version，無法判斷 Wave 完成狀態")
            return False

        # Step 2: 掃描 Ticket 目錄
        tickets = scan_wave_tickets(project_dir, current_version, logger)
        if not tickets:
            logger.debug("未找到任何 Ticket 檔案")
            return False

        # Step 3: 找到 in_progress ticket 的 wave（當前 Wave）
        current_wave = None
        for ticket in tickets:
            if ticket.get("status") == "in_progress":
                current_wave = ticket.get("wave")
                logger.debug(f"找到 in_progress ticket，所屬 Wave: {current_wave}")
                break

        if current_wave is None:
            logger.debug("未找到 in_progress ticket，無法判斷當前 Wave")
            return False

        # Step 4: 統計同 wave 的 pending ticket 數量
        pending_count = 0
        for ticket in tickets:
            if ticket.get("wave") == current_wave and ticket.get("status") == "pending":
                pending_count += 1

        logger.debug(f"Wave {current_wave} 中有 {pending_count} 個 pending ticket")

        # Step 5: pending == 0 → 情境 C
        if pending_count == 0:
            logger.info(f"偵測到情境 C：Wave {current_wave} 完成（無 pending ticket）")
            return True

        logger.debug(f"Wave {current_wave} 仍有 pending ticket，非情境 C")
        return False

    except Exception as e:
        logger.warning(f"偵測 Wave 完成狀態時發生錯誤: {e}")
        return False


def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查命令是否為 git commit
    4. 檢查輸出是否包含成功標記
    5. 若全部符合，輸出 AskUserQuestion 提醒
    """
    logger = setup_hook_logging("commit-handoff")

    # 讀取 PostToolUse JSON（使用統一的 stdin 讀取方法）
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        # 空輸入或 JSON 解析失敗：輸出預設允許訊息
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和輸出
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response") or {}
    stdout = tool_response.get("stdout", "")

    # 檢測 git commit 成功
    if is_git_commit_command(command) and is_commit_successful(stdout):
        commit_type = extract_commit_type(command)
        should_skip_scene16 = commit_type in SKIP_SCENE16_COMMIT_PREFIXES

        if should_skip_scene16:
            logger.info(
                "偵測到 git commit 成功（type=%s），自動跳過場景 #16，輸出 Skip16 提醒",
                commit_type,
            )
            reminder = AskUserQuestionMessages.COMMIT_HANDOFF_SKIP16_REMINDER
        else:
            logger.info(
                "偵測到 git commit 成功（type=%s），輸出含 #16 的 AskUserQuestion 提醒",
                commit_type or "unknown",
            )
            reminder = AskUserQuestionMessages.COMMIT_HANDOFF_REMINDER

        # 偵測情境 C（Wave 完成）
        is_wave_completion = detect_wave_completion(logger)
        if is_wave_completion:
            logger.info("偵測到情境 C（Wave 完成），附加 WAVE_COMPLETION_REMINDER")
            reminder += "\n" + AskUserQuestionReminders.WAVE_COMPLETION_REMINDER

        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": reminder
            }
        }
    else:
        # 不符合條件：正常流程
        logger.debug("未偵測到 commit 成功或不符合條件")
        output = DEFAULT_OUTPUT

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "commit-handoff")
    sys.exit(exit_code)
