#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Skill CLI Sync-Check Hook - PostToolUse Bash Matcher

職責: 偵測 git commit 成功後，當 commit 範圍含任一具 CLI 入口點的 skill
      src 行為變更（feat / refactor 性質）但未同步該 skill 的決策層文件時，
      輸出 INFO 級別提示。

背景（0.2.1-W3-136 ANA）: 舊版 ticket-skill-sync-check-hook.py 僅硬編碼
      保護 ticket 一個 skill（TICKET_SKILL_SRC_PREFIX），但「CLI 行為變更
      須同步 SKILL.md」語意對任何具 CLI 的 skill 皆成立。0.2.1-W3-131 修改
      skill_sync/cli.py 行為後 SKILL.md 描述過期、全程無 hook 提示，缺口
      已實證。本 hook 改採顯式 registry（SKILL_CLI_REGISTRY），泛化涵蓋
      專案內全部 7 個 CLI skill（ticket / doc / skill-sync / worktree /
      version-release / project-init / mermaid-ascii）。

觸發時機: PostToolUse Bash matcher（git commit 成功後）

偵測流程:
  1. 驗證 tool_name == "Bash" 且為 git commit 成功命令
  2. git show --name-only HEAD 取本次 commit 的 file list
  3. 依 SKILL_CLI_REGISTRY 逐一比對 src_prefix，找出有變更的 skill
  4. commit msg 詞元過濾：feat / refactor 觸發；fix / test / docs / chore 跳過
  5. meta 防護：
     a. 路徑白名單豁免：本 hook 自身路徑改動不觸發（PC-099 教訓）
     b. skill 級豁免：同 commit 已含該 skill 的 sync_targets 改動
        → 視為已同步，該 skill 不提示
  6. 對每個「有變更但未同步」的 skill 輸出 INFO 提示（不阻擋 commit）

設計骨架參考: doc-sync-check-hook.py / commit-handoff-hook.py（前身：
      舊版 ticket-skill-sync-check-hook.py，0.2.1-W3-239 泛化並搬遷）

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
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

# 具 CLI 入口點的 skill registry（0.2.1-W3-136 ANA Option B，顯式定義）
# 每條: name（skill 名稱）/ src_prefix（CLI 行為程式碼路徑前綴）/
#       sync_targets（描述該行為的決策層文件，同 commit 含其中之一即視為已同步）
SKILL_CLI_REGISTRY = [
    {
        "name": "ticket",
        "src_prefix": ".claude/skills/ticket/ticket_system/",
        "sync_targets": (".claude/pm-rules/", ".claude/skills/ticket/SKILL.md"),
    },
    {
        "name": "doc",
        "src_prefix": ".claude/skills/doc/doc_system/",
        "sync_targets": (".claude/skills/doc/SKILL.md",),
    },
    {
        "name": "skill-sync",
        "src_prefix": ".claude/skills/skill-sync/skill_sync/",
        "sync_targets": (".claude/skills/skill-sync/SKILL.md",),
    },
    {
        "name": "worktree",
        "src_prefix": ".claude/skills/worktree/scripts/",
        "sync_targets": (".claude/skills/worktree/SKILL.md",),
    },
    {
        "name": "version-release",
        "src_prefix": ".claude/skills/version-release/scripts/",
        "sync_targets": (".claude/skills/version-release/SKILL.md",),
    },
    {
        "name": "project-init",
        "src_prefix": ".claude/skills/project-init/project_init/",
        "sync_targets": (".claude/skills/project-init/SKILL.md",),
    },
    {
        "name": "mermaid-ascii",
        "src_prefix": ".claude/skills/mermaid-ascii/mermaid_ascii/",
        "sync_targets": (".claude/skills/mermaid-ascii/SKILL.md",),
    },
]

# 本 hook 自身路徑（meta 自我引用豁免，PC-099 教訓）
META_SELF_PATH = ".claude/hooks/skill-cli-sync-check-hook.py"  # 0.2.1-W3-239: 由 skills/ticket/hooks/ 搬遷並泛化

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


def find_skill_src_changes(files: List[str]) -> Dict[str, List[str]]:
    """
    依 SKILL_CLI_REGISTRY 逐一比對 src_prefix，找出有變更的 skill。

    Returns:
        dict[str, list[str]] - {skill_name: [matched_files]}，僅含有變更的 skill
    """
    result: Dict[str, List[str]] = {}
    for entry in SKILL_CLI_REGISTRY:
        matched = [f for f in files if f.startswith(entry["src_prefix"])]
        if matched:
            result[entry["name"]] = matched
    return result


def _get_registry_entry(skill_name: str) -> Optional[dict]:
    for entry in SKILL_CLI_REGISTRY:
        if entry["name"] == skill_name:
            return entry
    return None


def is_sync_exempt_for_skill(files: List[str], skill_name: str) -> bool:
    """檢查是否同 commit 已含該 skill 的 sync_targets 改動（同步豁免）"""
    entry = _get_registry_entry(skill_name)
    if entry is None:
        return False
    for f in files:
        for target in entry["sync_targets"]:
            if f.startswith(target) or f == target:
                return True
    return False


def is_meta_self_only(files: List[str]) -> bool:
    """
    檢查是否含 hook 自身路徑改動（meta 自我引用豁免）。

    若 commit file list 含本 hook 自身路徑，視為自我引用（PC-099 教訓），
    不觸發提示。
    """
    return META_SELF_PATH in files


def find_unsynced_skills(files: List[str]) -> Dict[str, List[str]]:
    """
    找出「有 CLI 行為變更但未同步決策層文件」的 skill 清單。

    Returns:
        dict[str, list[str]] - {skill_name: [matched_files]}，僅含未同步 skill
    """
    skill_changes = find_skill_src_changes(files)
    return {
        name: matched_files
        for name, matched_files in skill_changes.items()
        if not is_sync_exempt_for_skill(files, name)
    }


def build_reminder(unsynced: Dict[str, List[str]]) -> str:
    """組裝 INFO 提示訊息（依觸發的 skill 動態生成）"""
    lines = [
        "=" * 60,
        "[INFO] Skill CLI 行為變更同步檢查提醒",
        "=" * 60,
        "",
        "本次 commit 含以下 skill 的 CLI 行為變更（feat / refactor），",
        "但未在同 commit 同步該 skill 的決策層文件。",
        "",
    ]
    for skill_name in sorted(unsynced.keys()):
        entry = _get_registry_entry(skill_name)
        lines.append(f"[{skill_name}]")
        lines.append("  改動檔案：")
        for f in unsynced[skill_name]:
            lines.append(f"    - {f}")
        if entry is not None:
            lines.append("  建議同步目標：")
            for target in entry["sync_targets"]:
                lines.append(f"    - {target}")
        lines.append("")
    lines.extend([
        "若行為變更影響該 skill 的對外契約或 PM 決策路徑，請建立 follow-up ticket 同步更新。",
        "=" * 60,
    ])
    return "\n".join(lines)


# ============================================================================
# 主入口
# ============================================================================


def main() -> int:
    logger = setup_hook_logging("skill-cli-sync-check-hook")

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

    unsynced = find_unsynced_skills(files)
    if not unsynced:
        logger.debug("commit 不含未同步的 skill CLI src 改動，跳過")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    logger.info(
        "觸發提醒：commit type=%s + %d 個 skill 未同步 (%s)",
        commit_type, len(unsynced), ", ".join(sorted(unsynced.keys())),
    )
    reminder = build_reminder(unsynced)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reminder,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "skill-cli-sync-check-hook"))
