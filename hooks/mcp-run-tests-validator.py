#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
MCP run_tests 使用規範驗證 Hook (PreToolUse)

功能: 防止 mcp__dart__run_tests 在無 paths 參數情況下執行全量測試
規範: 必須指定 paths 參數限制測試範圍，防止卡住超過 20 分鐘

觸發時機: 執行 mcp__dart__run_tests 工具前
檢查位置: roots 參數中的每個 root 物件

執行結果:
  - 有效用法 (包含 paths): 允許執行
  - 無效用法 (缺少 paths): 阻止執行並提示正確用法
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """取得專案根目錄"""
    return Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))


def setup_log_directory() -> Path:
    """建立日誌目錄"""
    project_root = get_project_root()
    log_dir = project_root / ".claude" / "hook-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def log_violation(log_dir: Path, violation_type: str, details: dict) -> None:
    """記錄違規事件"""
    log_file = log_dir / "mcp-run-tests-violations.log"
    timestamp = datetime.now().isoformat()

    log_entry = {
        "timestamp": timestamp,
        "violation_type": violation_type,
        "details": details
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def validate_roots_parameter(roots: list) -> tuple[bool, list]:
    """
    驗證 roots 參數

    Args:
        roots: mcp__dart__run_tests 的 roots 參數列表

    Returns:
        (is_valid, invalid_roots) - 是否有效，無效的 root 清單
    """
    if not isinstance(roots, list):
        return False, ["roots 參數必須是陣列"]

    invalid_roots = []

    for idx, root in enumerate(roots):
        if not isinstance(root, dict):
            invalid_roots.append(f"root[{idx}]: 必須是物件，收到 {type(root).__name__}")
            continue

        # 檢查是否有 paths 參數
        has_paths = "paths" in root
        paths_value = root.get("paths", [])

        # 驗證邏輯: paths 必須存在且非空
        if not has_paths or not paths_value:
            root_str = root.get("root", f"root[{idx}]")
            invalid_roots.append(
                f"{root_str}: 缺少 paths 參數或 paths 為空陣列"
            )

    return len(invalid_roots) == 0, invalid_roots


def format_error_message(invalid_roots: list) -> str:
    """格式化錯誤訊息"""
    message_parts = [
        "❌ MCP run_tests 使用規範違規",
        "",
        "問題描述:",
        "mcp__dart__run_tests 在無 paths 參數時會執行全量測試，",
        "導致卡住超過 20 分鐘。必須指定 paths 限制測試範圍。",
        "",
        "違規詳情:",
    ]

    for invalid in invalid_roots:
        message_parts.append(f"  • {invalid}")

    message_parts.extend([
        "",
        "✅ 正確用法示例:",
        "",
        "1. 指定單一測試目錄:",
        '   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/"]}])',
        "",
        "2. 指定多個測試目錄:",
        '   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/unit/core/", "test/unit/models/"]}])',
        "",
        "3. 指定單一測試檔案:",
        '   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/import/events_test.dart"]}])',
        "",
        "📋 推薦方案:",
        "  • 使用 ./.claude/hooks/test-summary.sh 執行全量測試",
        "  • 或使用 flutter test --reporter compact 直接執行",
        "",
        "📚 相關規範: FLUTTER.md 第 72-101 行",
    ])

    return "\n".join(message_parts)


def main():
    """主程式邏輯"""
    try:
        # 讀取 stdin 輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # 只處理 mcp__dart__run_tests 工具
        if tool_name != "mcp__dart__run_tests":
            # 其他工具直接允許
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow"
                }
            }
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0)

        # 提取 roots 參數
        roots = tool_input.get("roots", [])

        # 驗證 roots 參數
        is_valid, invalid_roots = validate_roots_parameter(roots)

        if is_valid:
            # 有效用法，允許執行
            result = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "✅ mcp__dart__run_tests 使用規範檢查通過"
                }
            }
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0)

        # 無效用法，阻止執行
        log_dir = setup_log_directory()
        log_violation(log_dir, "mcp_run_tests_no_paths", {
            "roots": roots,
            "invalid_roots": invalid_roots
        })

        error_message = format_error_message(invalid_roots)

        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": error_message
            }
        }

        # 輸出錯誤訊息到 stderr 供調試
        print(error_message, file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(2)  # 阻塊錯誤 exit code

    except json.JSONDecodeError as e:
        error_msg = f"❌ Hook 錯誤: 無效的 JSON 輸入: {e}"
        print(error_msg, file=sys.stderr)
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": error_msg
            }
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(2)

    except Exception as e:
        error_msg = f"❌ Hook 執行失敗: {type(e).__name__}: {str(e)}"
        print(error_msg, file=sys.stderr)
        # 發生未預期的錯誤時，允許工具執行以防 Hook 故障
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"Hook 檢查失敗，允許執行: {str(e)}"
            }
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)


if __name__ == "__main__":
    main()
