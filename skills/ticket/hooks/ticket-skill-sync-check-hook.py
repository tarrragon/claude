#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Ticket Skill Sync-Check Hook - PostToolUse Bash Matcher

職責: 偵測 git commit 成功後，當 commit 範圍含 ticket skill src 行為變更
      （feat / refactor 性質）但未同步決策層文件時，輸出 INFO 級別提示。

觸發時機: PostToolUse Bash matcher（git commit 成功後）

偵測流程:
  1. 驗證 tool_name == "Bash" 且為 git commit 成功命令
  2. git show --name-only HEAD 取本次 commit 的 file list
  3. 路徑過濾：含 .claude/skills/ticket/ticket_system/** 改動才繼續
  4. commit msg 詞元過濾：feat / refactor 觸發；fix / test / docs / chore 跳過
  5. meta 防護：
     a. 路徑白名單豁免：本 hook 自身路徑改動不觸發（PC-099 教訓）
     b. ticket 級豁免：同 commit 已含 .claude/pm-rules/ 或
        .claude/skills/ticket/SKILL.md 改動 → 視為已同步，不提示
  6. 滿足條件時輸出 INFO 提示（不阻擋 commit）

設計骨架參考: doc-sync-check-hook.py / commit-handoff-hook.py

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    is_subagent_environment,
)


# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# 排除的命令模式（非 commit 寫入操作）
EXCLUDED_COMMAND_PATTERNS = [
    "git log",
    "git show",
    "git diff",
    "git status",
    "git commit --amend",
]

# commit 成功標記
COMMIT_SUCCESS_MARKERS = [
    "files changed",
    "file changed",
    "insertions(+)",
    "deletions(-)",
    "create mode",
]

# 觸發提示的 commit type（行為變更性質）
TRIGGER_COMMIT_TYPES = frozenset({"feat", "refactor"})

# ticket skill src 路徑前綴（行為層）
TICKET_SKILL_SRC_PREFIX = ".claude/skills/ticket/ticket_system/"

# 同步豁免路徑前綴（決策層 / 對外契約）
SYNC_EXEMPT_PREFIXES = (
    ".claude/pm-rules/",
    ".claude/skills/ticket/SKILL.md",
)

# 本 hook 自身路徑（meta 自我引用豁免，PC-099 教訓）
META_SELF_PATH = ".claude/skills/ticket/hooks/ticket-skill-sync-check-hook.py"  # W10-092: moved into skill

# PostToolUse 預設輸出
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}


# ============================================================================
# 偵測邏輯
# ============================================================================


def is_git_commit_command(command: str) -> bool:
    """判斷是否為 git commit 命令（排除 read-only / amend 變體）"""
    if "git commit" not in command:
        return False
    for excluded in EXCLUDED_COMMAND_PATTERNS:
        if excluded in command:
            return False
    return True


def is_commit_successful(stdout: str) -> bool:
    """判斷 commit 是否成功（檢查 git output 標記）"""
    for marker in COMMIT_SUCCESS_MARKERS:
        if marker in stdout:
            return True
    return False


def extract_commit_type(command: str) -> str:
    """
    從 git commit 命令提取 conventional commit type。

    支援格式：
    - git commit -m "type: ..."
    - git commit -m "type(scope): ..."
    - heredoc 內 "type: ..."
    """
    match = re.search(r'-m\s+["\']([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    match = re.search(r'\n\s*([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    return ""


def get_commit_files(project_root: Path, logger) -> List[str]:
    """
    執行 git show --name-only HEAD 取得 commit file list。

    Returns:
        list[str] - 檔案路徑（相對 repo root）；失敗時回傳空 list
    """
    try:
        result = subprocess.run(
            ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.debug("git show 非零退出: %s", result.stderr.strip())
            return []
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return files
    except Exception as e:
        logger.warning("取得 commit file list 失敗: %s", e)
        return []


def has_ticket_skill_src_change(files: List[str]) -> List[str]:
    """過濾出 ticket skill src 改動檔案"""
    return [f for f in files if f.startswith(TICKET_SKILL_SRC_PREFIX)]


def has_sync_exempt_change(files: List[str]) -> bool:
    """檢查是否同 commit 已含決策層 / 對外契約改動（同步豁免）"""
    for f in files:
        for prefix in SYNC_EXEMPT_PREFIXES:
            if f.startswith(prefix) or f == prefix:
                return True
    return False


def is_meta_self_only(files: List[str]) -> bool:
    """
    檢查是否僅 hook 自身路徑改動（meta 自我引用豁免）。

    若 commit file list 含本 hook 自身路徑且不含其他 ticket skill src 改動，
    視為自我引用（PC-099 教訓），不觸發提示。
    """
    return META_SELF_PATH in files


def build_reminder(skill_files: List[str]) -> str:
    """組裝 INFO 提示訊息"""
    lines = [
        "=" * 60,
        "[INFO] Ticket Skill 行為變更同步檢查提醒",
        "=" * 60,
        "",
        "本次 commit 含 ticket skill src 行為變更（feat / refactor），",
        "但未在同 commit 同步決策層文件。",
        "",
        "改動檔案：",
    ]
    for f in skill_files:
        lines.append(f"  - {f}")
    lines.extend([
        "",
        "建議掃描清單（確認無過時引用）：",
        "  - .claude/skills/ticket/SKILL.md（對外契約）",
        "  - .claude/pm-rules/decision-tree.md（決策路由）",
        "  - .claude/pm-rules/*.md（情境 SOP）",
        "",
        "建議指令：",
        "  grep -rln 'ticket track' .claude/pm-rules/",
        "",
        "若行為變更影響 PM 決策路徑或 SOP，請建立 follow-up ticket 同步更新。",
        "=" * 60,
    ])
    return "\n".join(lines)


# ============================================================================
# 主入口
# ============================================================================


def main() -> int:
    logger = setup_hook_logging("ticket-skill-sync-check-hook")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 偵測 subagent 環境：agent_id 僅在 subagent 中出現（W1-071 / PC-V1-004 入口污染防護）
    # 建 follow-up ticket / 掃描 pm-rules 等動作性提示屬 PM 決策，不注入 subagent context
    if is_subagent_environment(input_data):
        logger.info(
            "偵測到 subagent 環境（agent_id=%s），跳過同步檢查提醒",
            input_data.get("agent_id"),
        )
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response") or {}
    stdout = tool_response.get("stdout", "")

    if not (is_git_commit_command(command) and is_commit_successful(stdout)):
        logger.debug("非 git commit 成功")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    commit_type = extract_commit_type(command)
    if commit_type not in TRIGGER_COMMIT_TYPES:
        logger.debug("commit type=%s 不觸發（僅 feat/refactor 觸發）", commit_type or "unknown")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    project_root = get_project_root()
    files = get_commit_files(project_root, logger)
    if not files:
        logger.debug("無法取得 commit file list，跳過")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # meta 自我引用豁免
    if is_meta_self_only(files):
        logger.info("meta 自我引用豁免：commit 含本 hook 自身路徑改動")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    skill_files = has_ticket_skill_src_change(files)
    if not skill_files:
        logger.debug("commit 不含 ticket skill src 改動，跳過")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # ticket 級同步豁免
    if has_sync_exempt_change(files):
        logger.info("同步豁免：commit 已含 pm-rules/ 或 ticket SKILL.md 改動")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    logger.info("觸發提醒：commit type=%s + ticket skill src 改動 %d 檔，無同步", commit_type, len(skill_files))
    reminder = build_reminder(skill_files)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reminder,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "ticket-skill-sync-check-hook"))
