#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Memory Upgrade Reminder Hook - 跨專案升級評估提醒

偵測 auto-memory feedback_*.md 新增/修改時，提示 PM 評估原則是否
應升級至 .claude/ 框架（跨專案適用）。

Hook 類型: PostToolUse (matcher: Write|Edit)
觸發條件: tool_input.file_path 指向 memory 目錄下的 feedback_*.md
節流: 同檔案 THROTTLE_MINUTES 分鐘內只提示一次
行為: stderr 提示 + 檔案日誌（雙通道可見性，quality-baseline 規則 4）

參考: pm-quality-baseline 規則 7 + PC-061
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

try:
    from hook_utils import setup_hook_logging, read_json_from_stdin, run_hook_safely
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


# === 常數 ===
THROTTLE_MINUTES = 30
THROTTLE_SECONDS = THROTTLE_MINUTES * 60
THROTTLE_FILE = Path(__file__).parent.parent / "hook-logs" / "memory-upgrade-reminder-throttle.json"

# 偵測 auto-memory feedback 檔案的 regex
# 匹配形如：
#   .../auto-memory/<project>/feedback_xxx.md
#   ~/.claude/projects/<project>/memory/feedback_xxx.md
MEMORY_PATH_PATTERN = re.compile(
    r"(?:/auto-memory/[^/]+/feedback_[^/]+\.md$"
    r"|/\.claude/projects/[^/]+/memory/feedback_[^/]+\.md$)"
)

# === 訊息常數（集中管理） ===
MESSAGES = {
    "STARTUP": "Memory Upgrade Reminder Hook 啟動",
    "SKIP_NON_MATCHING_TOOL": "非 Write/Edit 工具 ({tool_name})，跳過",
    "SKIP_NON_MEMORY_FILE": "非 memory/feedback 檔案 ({file_path})，跳過",
    "THROTTLED": "節流跳過（{file_path} 在 {minutes} 分鐘內已提示過）",
    "TRIGGERED": "偵測到 memory 寫入：{file_path}",
    "REMINDER_TEMPLATE": (
        "\n[MemoryUpgradeReminder] 偵測到新 feedback memory: {filename}\n"
        "請評估此原則是否跨專案適用（pm-quality-baseline 規則 7）：\n"
        "  (1) 此原則對其他專案也適用嗎？\n"
        "  (2) 若是，升級至以下位置之一：\n"
        "       - .claude/rules/core/        （通用品質/流程）\n"
        "       - .claude/rules/core/pm-role.md  （PM 行為規範）\n"
        "       - .claude/error-patterns/     （錯誤學習）\n"
        "       - .claude/methodologies/      （流程方法論）\n"
        "       - .claude/skills/<skill>/     （Skill 引導）\n"
        "  (3) 升級後在 memory 頂部加註「已升級」標註\n"
        "\n"
        "參考：.claude/pm-rules/pm-quality-baseline.md 規則 7 + PC-061\n"
        "（{throttle_minutes} 分鐘內同檔案只提示一次）\n"
    ),
}


def is_memory_feedback_path(file_path: str) -> bool:
    """判斷路徑是否為 auto-memory feedback 檔案。"""
    if not file_path:
        return False
    # 展開 ~
    expanded = os.path.expanduser(file_path)
    return bool(MEMORY_PATH_PATTERN.search(expanded))


def load_throttle_cache(logger) -> dict:
    """載入節流快取，格式：{ file_path: last_reminded_epoch }。"""
    try:
        if THROTTLE_FILE.exists():
            with THROTTLE_FILE.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        # 快取損毀時重建，不阻擋主流程
        logger.warning(f"節流快取讀取失敗，重建空快取：{e}")
    return {}


def save_throttle_cache(cache: dict, logger) -> None:
    """寫入節流快取。"""
    try:
        THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with THROTTLE_FILE.open("w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"節流快取寫入失敗：{e}")


def is_throttled(file_path: str, cache: dict, now: float) -> bool:
    """檢查此檔案是否在節流期內。"""
    last = cache.get(file_path)
    if last is None:
        return False
    return (now - float(last)) < THROTTLE_SECONDS


def prune_expired(cache: dict, now: float) -> dict:
    """移除已過期項目，保持快取小巧。"""
    return {k: v for k, v in cache.items() if (now - float(v)) < THROTTLE_SECONDS}


def emit_reminder(file_path: str, logger) -> None:
    """輸出提示到 stderr 並記錄日誌（雙通道）。"""
    filename = Path(file_path).name
    message = MESSAGES["REMINDER_TEMPLATE"].format(
        filename=filename,
        throttle_minutes=THROTTLE_MINUTES,
    )
    sys.stderr.write(message)
    sys.stderr.flush()
    logger.info(f"已發出升級提醒：{filename}")


def main() -> int:
    """Hook 主入口。"""
    logger = setup_hook_logging("memory-upgrade-reminder")
    logger.info(MESSAGES["STARTUP"])

    input_data = read_json_from_stdin(logger)
    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        logger.debug(MESSAGES["SKIP_NON_MATCHING_TOOL"].format(tool_name=tool_name))
        return 0

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")

    if not is_memory_feedback_path(file_path):
        logger.debug(MESSAGES["SKIP_NON_MEMORY_FILE"].format(file_path=file_path))
        return 0

    now = time.time()
    cache = load_throttle_cache(logger)

    if is_throttled(file_path, cache, now):
        logger.info(MESSAGES["THROTTLED"].format(
            file_path=file_path, minutes=THROTTLE_MINUTES,
        ))
        return 0

    logger.info(MESSAGES["TRIGGERED"].format(file_path=file_path))
    emit_reminder(file_path, logger)

    # 更新節流快取（順便清理過期項）
    cache = prune_expired(cache, now)
    cache[file_path] = now
    save_throttle_cache(cache, logger)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "memory-upgrade-reminder"))
