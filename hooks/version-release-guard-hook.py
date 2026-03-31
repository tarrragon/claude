#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Version Release Guard Hook

Purpose: 攔截版本推進相關的 git commit，確保透過正式版本發布流程執行

Trigger: PreToolUse (Bash git commit)
Detection: commit message 包含 feat(v 或版本號模式

Checks:
1. 是否透過 version_release.py 執行
2. pubspec.yaml 版本是否已更新
3. CHANGELOG.md 版本是否一致

重構紀錄 (v0.28.0):
- 使用 .claude/lib/hook_io 共用模組
- 使用 .claude/lib/git_utils 共用模組
- 消除重複程式碼

重構紀錄 (v0.31.0-W22-001.3):
- 遷移至統一日誌系統 (hook_utils)
"""

import logging
import os
import re
import sys
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent))

from hook_io import (
    read_hook_input,
    write_hook_output,
    create_simple_output,
)
from git_utils import get_project_root
from hook_utils import setup_hook_logging, run_hook_safely


def is_version_release_commit(tool_input: dict, logger: logging.Logger) -> tuple:
    """檢查是否為版本發布相關的 commit。"""
    command = tool_input.get("command", "")

    # 檢查是否為 git commit 命令
    if "git commit" not in command:
        return False, None

    # 檢查是否包含版本號模式
    # 模式 1: feat(v0.XX.X): 或 feat(vX.X.X):
    version_pattern_feat = r"feat\(v\d+\.\d+\.?\d*\)"
    # 模式 2: 直接包含版本號 v0.XX.X
    version_pattern_direct = r"v\d+\.\d+\.?\d*"

    match_feat = re.search(version_pattern_feat, command)
    match_direct = re.search(version_pattern_direct, command)

    if match_feat:
        logger.debug(f"Detected version release commit (feat pattern): {match_feat.group()}")
        return True, match_feat.group()
    elif match_direct and ("release" in command.lower() or "version" in command.lower()):
        logger.debug(f"Detected version release commit (direct pattern): {match_direct.group()}")
        return True, match_direct.group()

    return False, None


def is_via_version_release_script(logger: logging.Logger) -> bool:
    """檢查是否透過 version_release.py 執行。"""
    result = os.environ.get("VERSION_RELEASE_SCRIPT") == "1"
    logger.debug(f"Version release script check: {result}")
    return result


def check_pubspec_version(logger: logging.Logger) -> tuple:
    """檢查 pubspec.yaml 版本是否符合 CHANGELOG 版本。"""
    project_root = Path(get_project_root())
    pubspec_path = project_root / "pubspec.yaml"
    changelog_path = project_root / "CHANGELOG.md"

    if not pubspec_path.exists():
        error_msg = "pubspec.yaml 不存在"
        logger.warning(error_msg)
        return False, error_msg

    if not changelog_path.exists():
        error_msg = "CHANGELOG.md 不存在"
        logger.warning(error_msg)
        return False, error_msg

    # 讀取 pubspec.yaml 版本
    pubspec_content = pubspec_path.read_text()
    pubspec_match = re.search(r"version:\s*(\d+\.\d+\.?\d*)", pubspec_content)
    if not pubspec_match:
        error_msg = "無法從 pubspec.yaml 解析版本號"
        logger.warning(error_msg)
        return False, error_msg
    pubspec_version = pubspec_match.group(1)

    # 讀取 CHANGELOG.md 最新版本
    changelog_content = changelog_path.read_text()
    changelog_match = re.search(r"\[(\d+\.\d+\.?\d*)\]", changelog_content)
    if not changelog_match:
        error_msg = "無法從 CHANGELOG.md 解析版本號"
        logger.warning(error_msg)
        return False, error_msg
    changelog_version = changelog_match.group(1)

    # 比較版本
    if pubspec_version != changelog_version:
        error_msg = f"版本不一致: pubspec.yaml={pubspec_version}, CHANGELOG.md={changelog_version}"
        logger.warning(error_msg)
        return False, error_msg

    logger.info(f"Version check passed: {pubspec_version}")
    return True, pubspec_version


def main() -> int:
    """主函式。"""
    logger = setup_hook_logging("version-release-guard")

    hook_input = read_hook_input()
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input") or {}

    # 只處理 Bash 工具
    if tool_name != "Bash":
        logger.debug("Tool is not Bash, skipping version check")
        output = create_simple_output("approve")
        write_hook_output(output)
        return 0

    # 檢查是否為版本發布相關的 commit
    is_version_commit, version_tag = is_version_release_commit(tool_input, logger)

    if not is_version_commit:
        logger.debug("Not a version release commit")
        output = create_simple_output("approve")
        write_hook_output(output)
        return 0

    logger.info(f"Detected version release commit: {version_tag}")

    # 檢查 1: 是否透過 version_release.py 執行
    if not is_via_version_release_script(logger):
        # 不強制攔截，改為警告提示
        warning_msg = f"""
[Version Release Guard] 版本推進檢測

偵測到版本相關 commit: {version_tag}

建議使用正式版本發布流程:
  uv run .claude/skills/version-release/scripts/version_release.py check
  uv run .claude/skills/version-release/scripts/version_release.py release

若確認要直接 commit，請確保:
1. pubspec.yaml 版本已更新
2. CHANGELOG.md 已更新
3. 所有相關 Tickets 已完成

繼續執行中...
"""
        logger.warning("Not executing via version_release.py")
        print(warning_msg)

    # 檢查 2: pubspec.yaml 版本一致性
    version_ok, version_info = check_pubspec_version(logger)
    if not version_ok:
        print(f"[Version Release Guard] 警告: {version_info}")

    # 通過檢查（改為警告模式而非阻止）
    logger.info("Version release guard passed")
    output = create_simple_output("approve")
    write_hook_output(output)
    return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "version-release-guard")
    sys.exit(exit_code)
