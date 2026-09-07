#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
工作日誌格式檢查 Hook

PostToolUse Hook: 檢測工作日誌中表格內的問題 emoji 模式
觸發時機: Edit/Write 操作作用域目錄下的 markdown 檔案（預設 docs/work-logs/，
可用環境變數 WORKLOG_FORMAT_CHECK_SCOPE 覆寫，供不同 consumer 各指自己的路徑）
行為: 警告（非阻擋），輸出問題位置到 stderr

參考規範: .claude/skills/compositional-writing/references/writing-documents.md
（portability-allow: 跨 skill 引用——寫作規範文件的權威版本仍在
compositional-writing，本 hook 遷入 doc-flow 後兩者分屬不同 skill，
consumer 未安裝 compositional-writing 時此連結會失效，屬已知限制而非
可攜性違規）
"""

import json
import os
import re
import sys
from pathlib import Path

_FRAMEWORK_HOOKS = str(Path(__file__).resolve().parents[3] / "hooks")
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, _FRAMEWORK_HOOKS)
try:
    from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output
    from lib.hook_messages import ValidationMessages, format_message
    _LIB_AVAILABLE = True
except ImportError:
    # 消費端未提供 .claude/lib/ 時優雅降級（portability-allow: 選用性依賴，
    # 缺件優雅降級，非可攜性違規）：main() 開頭直接印出 [WARNING] 並
    # return 0（見 main() 開頭的降級分支），不讓整個 Hook 在載入階段崩潰。
    _LIB_AVAILABLE = False


# 問題 emoji 模式清單（使用 Unicode 碼點避免直接使用 emoji）
# 這些 emoji 在 markdown 表格單元格中會導致 Claude Code CLI crash
# 重要：輸出時只使用純文字描述，不輸出原始 emoji
PROBLEMATIC_EMOJI_PATTERNS = [
    (r'\|\s*\u23F3\s*\|', 'hourglass', '待處理'),       # \u23F3
    (r'\|\s*\U0001F504\s*\|', 'cycle', '進行中'),       # \U0001F504
    (r'\|\s*\u274C\s*\|', 'cross-mark', '取消'),        # \u274C
    (r'\|\s*\U0001F6AB\s*\|', 'prohibited', '阻塞'),    # \U0001F6AB
    (r'\|\s*\u23F8\s*\|', 'pause', '暫停'),             # \u23F8
    (r'\|\s*\u23ED\uFE0F?\s*\|', 'skip', '跳過'),       # \u23ED\uFE0F
    (r'\|\s*\U0001F4A5\s*\|', 'collision', '失敗'),     # \U0001F4A5
    (r'\|\s*\u2705\s*\|', 'check-mark', '已完成'),      # \u2705
]


# 作用域設定：預設 docs/work-logs，可用環境變數覆寫（每個 consumer 在
# 自己的 settings.json 命令列各指自己的路徑，不需改程式碼）
DEFAULT_WORKLOG_SCOPE = "docs/work-logs"
WORKLOG_SCOPE_ENV_VAR = "WORKLOG_FORMAT_CHECK_SCOPE"


def get_worklog_scope() -> tuple[str, ...]:
    """讀取作用域設定，回傳正規化後的路徑片段（去除前後斜線並切分）。"""
    scope = os.environ.get(WORKLOG_SCOPE_ENV_VAR, DEFAULT_WORKLOG_SCOPE)
    return tuple(part for part in scope.strip("/").split("/") if part)


def is_worklog_file(file_path: str, scope: tuple[str, ...] | None = None) -> bool:
    """檢查是否為工作日誌檔案（依作用域設定判斷路徑）"""
    if not file_path:
        return False
    path = Path(file_path)
    if path.suffix != '.md':
        return False
    scope_parts = scope if scope is not None else get_worklog_scope()
    if not scope_parts:
        return False
    parts = path.parts
    window = len(scope_parts)
    return any(
        parts[i:i + window] == scope_parts
        for i in range(len(parts) - window + 1)
    )


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
        "Ref: .claude/skills/compositional-writing/references/writing-documents.md",
        "=" * 60,
        "",
    ])

    return "\n".join(lines)


# 抽樣降級：每 N 次觸發 1 次完整檢查（高頻 Hook，候選 3）
# 來源 ANA：Phase 3b P3 五 Hook，0% Action 比、連續 5 次無錯
SAMPLING_N = 10
SAMPLING_COUNTER_FILE = Path(__file__).parent.parent / "hook-logs" / "_sampling" / "worklog-format-check.count"


def should_sample_run(logger) -> bool:
    """抽樣判斷：每 SAMPLING_N 次觸發 1 次完整檢查。

    使用持久計數檔案，避免抽樣偏差；讀寫失敗時保守執行（return True）。
    """
    try:
        SAMPLING_COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        if SAMPLING_COUNTER_FILE.exists():
            try:
                count = int(SAMPLING_COUNTER_FILE.read_text().strip() or "0")
            except (ValueError, OSError):
                count = 0
        count += 1
        SAMPLING_COUNTER_FILE.write_text(str(count))
        run = (count % SAMPLING_N == 0)
        logger.debug("抽樣計數=%d, 本次%s", count, "執行" if run else "跳過")
        return run
    except Exception as exc:
        logger.info("抽樣計數失敗，保守執行: %s", exc)
        return True


def main():
    """主函式"""
    if not _LIB_AVAILABLE:
        sys.stderr.write(
            "[WARNING] worklog-format-check 未執行：找不到 .claude/lib/，此為"
            "消費端需自行提供的框架共用模組（工作日誌格式檢查功能停用，不影響"
            "其他操作）。\n"
        )
        return 0
    logger = setup_hook_logging("worklog-format-check")
    # 讀取 stdin 獲取 Hook 輸入
    try:
        hook_input = read_json_from_stdin(logger)
    except json.JSONDecodeError:
        # 無法解析輸入，靜默退出
        return 0

    if not hook_input:
        return 0

    # 獲取工具輸入
    tool_input = hook_input.get('tool_input') or {}

    # 獲取檔案路徑
    file_path = tool_input.get('file_path', '')

    # 檢查是否為工作日誌檔案（作用域可設定，見 get_worklog_scope）
    if not is_worklog_file(file_path):
        return 0

    # 抽樣降級：每 N 次觸發 1 次完整檢查
    if not should_sample_run(logger):
        return 0

    # 檢查檔案內容
    issues = check_file_content(file_path)

    if issues:
        # worklog 格式提醒為 PM-only：統一出口過濾 subagent 觸發
        # （PC-V1-004 防護 C，避免誘導 subagent 越界寫 worklog）
        warning = format_warning(file_path, issues)
        emit_hook_output(
            "PostToolUse",
            additional_context=warning,
            audience="pm_only",
            input_data=hook_input,
        )

    # 總是返回成功（非阻擋式 Hook）
    return 0


if __name__ == '__main__':
    if _LIB_AVAILABLE:
        sys.exit(run_hook_safely(main, "worklog-format-check"))
    else:
        sys.exit(main())
