#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
測試前環境檢查 Hook (PreToolUse)

功能:
  在執行 flutter test 前檢查開發環境就緒狀態:
  1. Flutter SDK 可用性
  2. pubspec.lock 存在（依賴已安裝）
  3. .dart_tool/package_config.json 存在（pub get 已執行）

觸發時機: PreToolUse (Bash: flutter test, mcp__dart__run_tests)

輸出:
  環境就緒: allow，附帶確認訊息
  環境異常: allow + stderr 警告（不阻止，但提醒問題）

HOOK_METADATA (JSON):
{
  "event_type": "PreToolUse",
  "matcher": "Bash",
  "description": "測試前環境檢查 - 確保 Flutter SDK 和依賴完整",
  "dependencies": [],
  "version": "1.0.0"
}
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import ValidationMessages


def is_test_command(tool_name: str, tool_input: dict) -> bool:
    """判斷是否為測試命令。"""
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        return "flutter test" in command or "dart test" in command
    return tool_name == "mcp__dart__run_tests"


def check_flutter_sdk() -> tuple[bool, str]:
    """檢查 Flutter SDK 可用性。"""
    try:
        result = subprocess.run(
            ["flutter", "--version", "--machine"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, ValidationMessages.PRE_TEST_SDK_OK
        return False, ValidationMessages.PRE_TEST_SDK_ERROR
    except FileNotFoundError:
        return False, ValidationMessages.PRE_TEST_SDK_NOT_FOUND
    except subprocess.TimeoutExpired:
        return False, ValidationMessages.PRE_TEST_SDK_TIMEOUT


def check_dependencies(project_dir: Path) -> list[str]:
    """檢查依賴是否已安裝。"""
    warnings = []

    pubspec_lock = project_dir / "pubspec.lock"
    if not pubspec_lock.exists():
        warnings.append(ValidationMessages.PRE_TEST_PUBSPEC_LOCK_MISSING)
        return warnings

    package_config = project_dir / ".dart_tool" / "package_config.json"
    if not package_config.exists():
        warnings.append(ValidationMessages.PRE_TEST_PACKAGE_CONFIG_MISSING)
        return warnings

    # 檢查 pubspec.yaml 是否比 pubspec.lock 更新
    pubspec_yaml = project_dir / "pubspec.yaml"
    if pubspec_yaml.exists() and pubspec_lock.exists():
        yaml_mtime = pubspec_yaml.stat().st_mtime
        lock_mtime = pubspec_lock.stat().st_mtime
        if yaml_mtime > lock_mtime:
            warnings.append(ValidationMessages.PRE_TEST_PUBSPEC_OUTDATED)

    return warnings


def main():
    logger = setup_hook_logging("pre-test-hook")
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if not is_test_command(tool_name, tool_input):
        return 0

    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    issues = []

    # 1. 檢查 Flutter SDK
    sdk_ok, sdk_msg = check_flutter_sdk()
    if not sdk_ok:
        issues.append(f"[ERROR] {sdk_msg}")

    # 2. 檢查依賴
    dep_warnings = check_dependencies(project_dir)
    for warning in dep_warnings:
        issues.append(f"[WARNING] {warning}")

    # 輸出結果
    if issues:
        warning_text = "\n".join(issues)
        print(f"{ValidationMessages.PRE_TEST_CHECK_HEADER}\n{warning_text}")

    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": (
                f"{ValidationMessages.PRE_TEST_ENV_CHECK_PREFIX}{len(issues)}{ValidationMessages.PRE_TEST_ENV_CHECK_SUFFIX}" if issues else ValidationMessages.PRE_TEST_ENV_READY
            ),
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "pre-test-hook"))
