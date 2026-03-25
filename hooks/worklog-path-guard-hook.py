#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Worklog 路徑防護 Hook (PostToolUse)

功能:
  偵測 docs/work-logs/ 根目錄下的 .md 檔案寫入操作。
  提醒使用者將檔案放在正確的子目錄下。

觸發時機:
  PostToolUse (Write 工具)
  當目標路徑為 docs/work-logs/*.md（根目錄下的 Markdown 檔案）時觸發

行為:
  輸出 WARNING 提醒（不阻止操作，exit code 0）
  提示檔案應放在：
    - docs/work-logs/v{version}/ （版本工作日誌）
    - docs/work-logs/v{version}/tickets/ （Ticket 檔案）

排除條件:
  - docs/work-logs/v*/*.md （已在版本目錄下）
  - docs/work-logs/v*/tickets/*.md （已在 tickets 目錄下）
  - 非 .md 檔案

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Write",
  "description": "Worklog 路徑防護 - 提醒不要在 docs/work-logs/ 根目錄直接寫入",
  "dependencies": [],
  "version": "1.0.0"
}
"""

import json
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


def is_worklog_root_markdown(file_path: str) -> bool:
    """
    判斷檔案是否在 docs/work-logs/ 根目錄下的 .md 檔案。

    規則:
      - 路徑必須符合 docs/work-logs/*.md （根目錄直接）
      - 排除 docs/work-logs/v{version}/ 下的任何檔案（在版本子目錄或更深層）

    防護目標:
      - ✓ 觸發: docs/work-logs/something.md （根目錄直接）
      - ✗ 跳過: docs/work-logs/v0.1.0/something.md （在版本子目錄）
      - ✗ 跳過: docs/work-logs/v0.1.0/tickets/file.md （在 tickets 子目錄）

    Args:
        file_path: 檔案路徑

    Returns:
        bool - 是否符合防護條件（true = 需要警告）
    """
    # 規範化路徑，使用正斜槓
    normalized_path = file_path.replace("\\", "/")

    # 檢查是否以 .md 結尾
    if not normalized_path.endswith(".md"):
        return False

    # 檢查是否在 docs/work-logs/ 目錄下
    if "docs/work-logs/" not in normalized_path:
        return False

    # 使用正則提取檔案在 docs/work-logs/ 之後的部分
    # 例如:
    #   docs/work-logs/something.md → "something.md"
    #   docs/work-logs/v0.1.0/something.md → "v0.1.0/something.md"
    #   docs/work-logs/v0.1.0/tickets/file.md → "v0.1.0/tickets/file.md"
    match = re.search(r"docs/work-logs/(.+)$", normalized_path)
    if not match:
        return False

    relative_part = match.group(1)

    # 檢查相對部分是否包含目錄分隔符 (/)
    # 如果包含，說明檔案在子目錄下，不需要警告
    # 如果不包含，說明檔案在根目錄下，需要警告
    if "/" in relative_part:
        # 在子目錄下（如 v0.1.0/something.md）
        return False

    # 直接在 docs/work-logs/ 根目錄下（如 something.md）
    return True


def format_warning_message(file_path: str) -> str:
    """
    生成友善的警告訊息。

    Args:
        file_path: 檔案路徑

    Returns:
        str - 格式化的警告訊息
    """
    filename = Path(file_path).name

    # 根據檔名推測應該放在哪個位置
    # 版本工作日誌（如 v0.1.0-release.md）
    if re.match(r"v\d+\.\d+\.\d+-.+\.md", filename):
        suggestion = "應放在 docs/work-logs/v{version}/ 目錄下"
    # Ticket 檔案（如 0.1.0-W1-001.md）
    elif re.match(r"\d+\.\d+\.\d+-W\d+-.+\.md", filename):
        suggestion = "應放在 docs/work-logs/v{version}/tickets/ 目錄下"
    else:
        suggestion = "應放在 docs/work-logs/v{version}/ 或 docs/work-logs/v{version}/tickets/ 目錄下"

    message = (
        f"\n[WARNING] Worklog 檔案路徑不正確\n"
        f"  檔案: {file_path}\n"
        f"  問題: 檔案不應直接放在 docs/work-logs/ 根目錄\n"
        f"  建議: {suggestion}\n"
        f"  說明: 工作日誌必須按版本號組織（v0.1.0、v0.2.0 等），\n"
        f"       Ticket 檔案必須放在 tickets/ 子目錄下。\n"
    )
    return message


def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("worklog-path-guard")

    try:
        # 讀取 JSON 輸入
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        # 檢查是否為 Write 工具
        if tool_name != "Write":
            logger.info("跳過: 工具類型 %s 不是 Write", tool_name)
            return 0

        # 取得檔案路徑
        file_path = tool_input.get("file_path", "")
        if not file_path:
            logger.warning("警告: Write 工具無 file_path 欄位")
            return 0

        # 檢查是否為防護目標
        if not is_worklog_root_markdown(file_path):
            # 不符合防護條件：直接允許
            logger.info("允許: 檔案路徑正確或不在防護範圍內 - %s", file_path)
            return 0

        # 偵測到路徑問題：輸出警告並記錄
        logger.warning("路徑警告: Worklog 檔案在根目錄 - %s", file_path)
        warning_message = format_warning_message(file_path)

        # 同時輸出到 stderr（雙通道）和日誌
        print(warning_message, file=sys.stderr)
        logger.warning(warning_message)

        # 不阻止操作（非阻塞 Hook），允許執行
        return 0

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e, exc_info=True)
        # JSON 解析失敗：直接允許執行，不阻塊
        return 0
    except Exception as e:
        logger.error("執行錯誤: %s", e, exc_info=True)
        # 任何錯誤都不阻塊（非阻塞原則）
        return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "worklog-path-guard")
    sys.exit(exit_code)
