#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
UTF-8 Integrity Check Hook - 偵測檔案中的 U+FFFD replacement character

功能：
- PostToolUse:Write/Edit/MultiEdit 事件觸發
- 讀取被寫入/編輯的檔案，掃描 U+FFFD (replacement character)
- 偵測到損壞字元時，輸出 WARNING 到 stderr 並在 additionalContext 提醒

背景：
- IMP-059: auto-compaction 在 UTF-8 多字節字元中間截斷，導致中文字元損壞
- 損壞表現為 U+FFFD replacement character（顯示為方塊或問號）

Hook Type: PostToolUse (Write, Edit, MultiEdit)

Exit Codes:
    0 - 無損壞或檔案不可讀
    0 - 偵測到損壞（warning only，不阻擋）
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    extract_tool_input,
    emit_hook_output,
)


# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "utf8-integrity-check-hook"
HOOK_EVENT = "PostToolUse"

# U+FFFD replacement character — UTF-8 截斷的標誌
REPLACEMENT_CHAR = "\ufffd"

# 每個檔案最多報告的損壞位置數
MAX_REPORTED_LOCATIONS = 5

# 忽略的檔案類型（二進位或非文字檔案）
BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".br",
    ".pdf", ".doc", ".docx",
    ".mp3", ".mp4", ".wav",
    ".pyc", ".pyo", ".class",
    ".db", ".sqlite", ".sqlite3",
})


# ============================================================================
# 核心邏輯
# ============================================================================

def extract_file_paths(tool_input: dict) -> list:
    """從 tool_input 提取被操作的檔案路徑

    支援 Write（file_path）、Edit（file_path）、MultiEdit（file_path）。
    """
    paths = []

    file_path = tool_input.get("file_path")
    if file_path:
        paths.append(file_path)

    return paths


def is_binary_file(file_path: str) -> bool:
    """判斷是否為二進位檔案（不掃描）"""
    return Path(file_path).suffix.lower() in BINARY_EXTENSIONS


def scan_file_for_replacement_chars(file_path: str, logger: logging.Logger):
    """掃描檔案中的 U+FFFD replacement character

    Returns:
        list[tuple[int, str]]: 損壞位置清單 [(行號, 該行內容截取), ...]
        空清單表示無損壞
    """
    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.info("無法讀取 %s: %s", file_path, exc)
        return []

    if REPLACEMENT_CHAR not in text:
        return []

    # 定位損壞位置
    corrupted_locations = []
    for line_num, line in enumerate(text.splitlines(), start=1):
        if REPLACEMENT_CHAR in line:
            # 截取損壞位置附近的內容（前後各 20 字元）
            idx = line.index(REPLACEMENT_CHAR)
            start = max(0, idx - 20)
            end = min(len(line), idx + 20)
            snippet = line[start:end]
            corrupted_locations.append((line_num, snippet))

            if len(corrupted_locations) >= MAX_REPORTED_LOCATIONS:
                break

    return corrupted_locations


def build_warning_message(file_path: str, locations: list) -> str:
    """建立警告訊息"""
    rel_path = file_path
    try:
        rel_path = str(Path(file_path).relative_to(Path.cwd()))
    except ValueError:
        pass

    lines = [
        f"[UTF-8 INTEGRITY] 偵測到 U+FFFD replacement character: {rel_path}",
        f"  共 {len(locations)} 處損壞（可能因 auto-compaction UTF-8 截斷導致）：",
    ]
    for line_num, snippet in locations:
        # 將 U+FFFD 標記為可見
        visible_snippet = snippet.replace(REPLACEMENT_CHAR, "[U+FFFD]")
        lines.append(f"  L{line_num}: ...{visible_snippet}...")

    lines.append("  建議：請手動檢查並修復損壞的字元（參考 IMP-059）")
    return "\n".join(lines)


# ============================================================================
# 主入口
# ============================================================================

def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)

    input_data = read_json_from_stdin(logger)
    if not input_data:
        emit_hook_output(HOOK_EVENT)
        return 0

    tool_input = extract_tool_input(input_data, logger)
    if not tool_input:
        emit_hook_output(HOOK_EVENT)
        return 0

    file_paths = extract_file_paths(tool_input)
    if not file_paths:
        emit_hook_output(HOOK_EVENT)
        return 0

    # 掃描每個檔案
    all_warnings = []
    for fp in file_paths:
        if is_binary_file(fp):
            logger.debug("跳過二進位檔案: %s", fp)
            continue

        locations = scan_file_for_replacement_chars(fp, logger)
        if locations:
            warning = build_warning_message(fp, locations)
            all_warnings.append(warning)
            # 同步輸出到 stderr 確保可見（quality-baseline 規則 4）
            sys.stderr.write(warning + "\n")

    if all_warnings:
        combined = "\n\n".join(all_warnings)
        emit_hook_output(HOOK_EVENT, additional_context=combined)
    else:
        emit_hook_output(HOOK_EVENT)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
