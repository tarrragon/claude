#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
工作日誌格式檢查 Hook

PostToolUse Hook: 檢測工作日誌中表格內的問題 emoji 模式
觸發時機: Edit/Write 操作 docs/work-logs/ 目錄下的 markdown 檔案
行為: 警告（非阻擋），輸出問題位置到 stderr

參考方法論: worklog-writing-methodology.md
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import ValidationMessages, format_message


# 問題 emoji 模式清單（使用 Unicode 碼點避免直接使用 emoji）
# 這些 emoji 在 markdown 表格單元格中會導致 Claude Code CLI crash
# 重要：輸出時只使用純文字描述，不輸出原始 emoji
PROBLEMATIC_EMOJI_PATTERNS = [
    (r'\|\s*\u23F3\s*\|', 'hourglass', '待處理'),       # ⏳
    (r'\|\s*\U0001F504\s*\|', 'cycle', '進行中'),       # 🔄
    (r'\|\s*\u274C\s*\|', 'cross-mark', '取消'),        # ❌
    (r'\|\s*\U0001F6AB\s*\|', 'prohibited', '阻塞'),    # 🚫
    (r'\|\s*\u23F8\s*\|', 'pause', '暫停'),             # ⏸
    (r'\|\s*\u23ED\uFE0F?\s*\|', 'skip', '跳過'),       # ⏭️
    (r'\|\s*\U0001F4A5\s*\|', 'collision', '失敗'),     # 💥
    (r'\|\s*\u2705\s*\|', 'check-mark', '已完成'),      # ✅
]


def is_worklog_file(file_path: str) -> bool:
    """檢查是否為工作日誌檔案"""
    if not file_path:
        return False
    path = Path(file_path)
    # 檢查是否在 docs/work-logs/ 目錄下且為 .md 檔案
    return 'work-logs' in path.parts and path.suffix == '.md'


def check_file_content(file_path: str) -> list[dict]:
    """檢查檔案內容中的問題模式"""
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        return issues

    for line_num, line in enumerate(lines, start=1):
        for pattern, emoji_name, suggestion in PROBLEMATIC_EMOJI_PATTERNS:
            if re.search(pattern, line):
                # 移除 emoji 後再輸出（避免觸發 CLI crash）
                # 擴展範圍涵蓋常見 emoji：Supplementary + Misc Symbols + Dingbats + 更多
                safe_content = re.sub(
                    r'[\U00010000-\U0010ffff]|[\u2300-\u27ff]|[\u2b50-\u2bff]|[\u274c\u2705\u23f3\u23f8\u23ed]',
                    '[emoji]',
                    line.strip()[:80]
                )
                issues.append({
                    'line': line_num,
                    'emoji_name': emoji_name,  # 使用純文字名稱
                    'suggestion': suggestion,
                    'content': safe_content
                })

    return issues


def format_warning(file_path: str, issues: list[dict]) -> str:
    """格式化警告訊息（純文字，避免輸出 emoji 觸發 CLI crash）"""
    lines = [
        "",
        "=" * 60,
        ValidationMessages.WORKLOG_FORMAT_WARNING_HEADER,
        "=" * 60,
        f"File: {file_path}",
        f"Issues: {len(issues)}",
        "",
        ValidationMessages.WORKLOG_EMOJI_DETECTED_MSG,
        ValidationMessages.WORKLOG_PLAIN_TEXT_ADVICE,
        "",
        "Details:",
        "-" * 40,
    ]

    for issue in issues:
        lines.append(f"  Line {issue['line']}: [{issue['emoji_name']}] -> use \"{issue['suggestion']}\"")
        lines.append(f"    Content: {issue['content']}")

    lines.extend([
        "-" * 40,
        "",
        "Ref: .claude/methodologies/worklog-writing-methodology.md",
        "=" * 60,
        "",
    ])

    return "\n".join(lines)


def main():
    logger = setup_hook_logging("worklog-format-check")
    """主函式"""
    # 讀取 stdin 獲取 Hook 輸入
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        # 無法解析輸入，靜默退出
        return 0

    # 獲取工具輸入
    tool_input = hook_input.get('tool_input', {})

    # 獲取檔案路徑
    file_path = tool_input.get('file_path', '')

    # 檢查是否為工作日誌檔案
    if not is_worklog_file(file_path):
        return 0

    # 檢查檔案內容
    issues = check_file_content(file_path)

    if issues:
        # 輸出警告到 stderr（非阻擋）
        warning = format_warning(file_path, issues)
        print(warning)

    # 總是返回成功（非阻擋式 Hook）
    return 0


if __name__ == '__main__':
    sys.exit(run_hook_safely(main, "worklog-format-check"))
