#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""commit-msg Layer 2 marker check hook（W17-126）。

職責（事後維度防護）：
    git commit 完成後，若 commit 涉及 framework 路徑（依 W17-127.1 SSOT
    `lib.framework_paths.is_framework_path`），則檢查 commit msg 是否含
    Layer 2 審查標記。缺則輸出機會成本語氣的警告（exit 0，不阻擋）。

設計依據：
    W17-122 ANA linux 視角警示三層防護的「事後 Layer 2」維度僅有 Layer C
    紙本約束，本 hook 補強為 Layer A（事後自動偵測）形成完整防護鏈。

合法 Layer 2 標記格式（任一即可）：
    1. `Layer 2 by <agent-name>`         — 已派 Layer 2 委員審查
    2. `Layer 2 N/A by <理由 ≥ 10 字元>` — 明示豁免並附理由（防空殼）

豁免情境：
    - merge commit（含 `Merge ` 開頭或多 parent）
    - revert commit（commit msg `Revert "..."` 開頭）
    - commit msg 含 `[skip layer2]` 標記

設計原則：
    - 警告語氣機會成本（rules/core/ai-communication-rules.md 規則 6）
    - 非阻擋（exit 0），避免大規模誤擋既有 commit 流程
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    run_git,
    get_project_root,
)
from lib.framework_paths import is_framework_path  # noqa: E402


EXIT_SUCCESS = 0

# Commit msg 內 Layer 2 標記偵測 regex
# - "Layer 2 by <name>"        — name 至少 1 個非空白字元
# - "Layer 2 N/A by <reason>"  — reason 至少 10 字元（防空殼）
LAYER2_BY_PATTERN = re.compile(r"Layer\s*2\s+by\s+(\S.*)", re.IGNORECASE)
LAYER2_NA_PATTERN = re.compile(r"Layer\s*2\s+N/?A\s+by\s+(.+)", re.IGNORECASE)
SKIP_MARKER = "[skip layer2]"
NA_REASON_MIN_LEN = 10

COMMIT_SUCCESS_MARKERS = (
    "files changed", "file changed",
    "insertions(+)", "deletions(-)", "create mode",
)


def _is_commit_successful(stdout: str, stderr: str = "") -> bool:
    combined = stdout + stderr
    if "nothing to commit" in combined or "Aborting" in combined:
        return False
    return any(marker in stdout for marker in COMMIT_SUCCESS_MARKERS)


def _is_git_commit_command(command: str) -> bool:
    if "git commit" not in command:
        return False
    # 排除唯讀或修改型非新建 commit
    for excluded in ("git commit --amend", "git log", "git show", "git diff", "git status"):
        if excluded in command:
            return False
    return True


def _get_changed_files(project_dir: Path, logger) -> List[str]:
    """取得 HEAD commit 的變更檔案清單。"""
    output = run_git(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        cwd=project_dir, timeout=5, logger=logger,
    )
    if not output:
        return []
    return [line.strip() for line in output.split("\n") if line.strip()]


def _get_commit_msg(project_dir: Path, logger) -> str:
    output = run_git(
        ["git", "--no-optional-locks", "log", "-1", "--format=%B", "HEAD"],
        cwd=project_dir, timeout=5, logger=logger,
    )
    return output if output else ""


def _is_merge_or_revert(project_dir: Path, commit_msg: str, logger) -> bool:
    """判斷是否為 merge / revert commit。"""
    msg_first_line = commit_msg.split("\n", 1)[0] if commit_msg else ""
    if msg_first_line.startswith("Merge ") or msg_first_line.startswith("Revert "):
        return True
    # 多 parent → merge commit
    parents = run_git(
        ["git", "--no-optional-locks", "log", "-1", "--format=%P", "HEAD"],
        cwd=project_dir, timeout=5, logger=logger,
    )
    if parents and len(parents.split()) > 1:
        return True
    return False


def has_valid_layer2_marker(commit_msg: str) -> bool:
    """檢查 commit msg 是否含合法 Layer 2 標記。

    合法形式：
    - `Layer 2 by <agent-name>`（agent-name 至少 1 字元）
    - `Layer 2 N/A by <理由>`（理由 ≥ NA_REASON_MIN_LEN 字元）
    """
    if not commit_msg:
        return False

    # N/A 形式：理由 ≥ 10 字元
    na_match = LAYER2_NA_PATTERN.search(commit_msg)
    if na_match:
        reason = na_match.group(1).strip()
        # 移除尾端可能的句點/說明括號避免誤判
        if len(reason) >= NA_REASON_MIN_LEN:
            return True
        # 理由太短不視為合法（後續會走無標記分支）

    # by <agent> 形式：排除「N/A by」誤命中（regex 已用不同 pattern 隔離）
    by_match = LAYER2_BY_PATTERN.search(commit_msg)
    if by_match:
        first_token = by_match.group(1).strip().split()[0] if by_match.group(1).strip() else ""
        # 排除 "Layer 2 by N/A"（雖不太可能）— first_token != "N/A"
        if first_token and first_token.upper() not in ("N/A", "NA"):
            return True

    return False


def check_layer2_marker(input_data: dict, tool_input: dict, logger) -> Optional[str]:
    """主邏輯：回傳警告訊息或 None。"""
    command = tool_input.get("command", "")
    if not _is_git_commit_command(command):
        logger.debug("非 git commit 命令，跳過")
        return None

    tool_response = input_data.get("tool_response") or {}
    stdout = tool_response.get("stdout", "")
    stderr = tool_response.get("stderr", "")
    if not _is_commit_successful(stdout, stderr):
        logger.debug("commit 未成功，跳過")
        return None

    project_dir = get_project_root()

    commit_msg = _get_commit_msg(project_dir, logger)

    # 豁免：skip 標記
    if SKIP_MARKER in commit_msg:
        logger.info("commit msg 含 [skip layer2]，跳過 Layer 2 標記檢查")
        return None

    # 豁免：merge / revert
    if _is_merge_or_revert(project_dir, commit_msg, logger):
        logger.info("merge / revert commit，跳過 Layer 2 標記檢查")
        return None

    changed_files = _get_changed_files(project_dir, logger)
    if not changed_files:
        logger.debug("無變更檔案，跳過")
        return None

    framework_files = [f for f in changed_files if is_framework_path(f)]
    if not framework_files:
        logger.debug("commit 不涉及 framework 路徑，跳過")
        return None

    if has_valid_layer2_marker(commit_msg):
        logger.info("Layer 2 標記已存在，通過檢查（framework files=%d）", len(framework_files))
        return None

    # 缺標記 → 警告（機會成本語氣）
    logger.info(
        "framework commit 缺 Layer 2 標記，輸出建議補做警告（framework files=%d）",
        len(framework_files),
    )
    sample_files = "\n  - ".join(framework_files[:5])
    more = f"\n  - ...（共 {len(framework_files)} 個 framework 檔案）" if len(framework_files) > 5 else ""
    return (
        "[Layer 2 補審查建議]\n"
        f"本次 commit 修改 framework 規則層檔案：\n  - {sample_files}{more}\n\n"
        "建議補做 Layer 2 委員獨立審查（派 basil-writing-critic 等）並在 commit msg "
        "補上標記，以維持 framework 規則品質：\n"
        "  - 已派審查 → 在後續 commit msg 加入 `Layer 2 by <agent-name>`\n"
        "  - 評估後決定豁免 → 在後續 commit msg 加入 `Layer 2 N/A by <理由（≥10 字元）>`\n"
        "  - 緊急情境暫跳過 → commit msg 含 `[skip layer2]`（屬成本較高的捷徑，建議事後補做）\n\n"
        "豁免條件：merge / revert commit、含 `[skip layer2]` 標記者自動跳過。"
    )


def main() -> int:
    logger = setup_hook_logging("commit-msg-layer2-marker-check-hook")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return EXIT_SUCCESS

    if input_data.get("tool_name", "") != "Bash":
        return EXIT_SUCCESS

    tool_input = input_data.get("tool_input") or {}

    try:
        msg = check_layer2_marker(input_data, tool_input, logger)
    except Exception as e:
        logger.error("Layer 2 標記檢查失敗: %s", e, exc_info=True)
        return EXIT_SUCCESS

    if msg:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": msg,
            }
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "commit-msg-layer2-marker-check-hook"))
