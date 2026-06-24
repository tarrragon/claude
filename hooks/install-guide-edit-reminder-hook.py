#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Install Guide Edit Reminder Hook - 安裝指南檔案編輯提醒 (PC-159 Hook 層防護)

偵測 docs/development-setup.md / docs/environment-recovery-guide.md 被
Edit/Write 修改時，輸出 fresh shell 驗證 INFO reminder（不阻擋）。

Hook 類型: PostToolUse (matcher: Edit|Write)
觸發條件: tool_input.file_path 含 "development-setup" 或 "environment-recovery"
節流: 同檔案 THROTTLE_MINUTES 分鐘內只提示一次
行為: stderr 提示 + 檔案日誌（雙通道可見性，quality-baseline 規則 4）

參考: PC-159 (安裝指令短名假設未驗證) + 0.19.0-W3-052 ANA Solution
"""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib import setup_hook_logging, read_json_from_stdin, run_hook_safely
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


# === 常數 ===
THROTTLE_MINUTES = 30
THROTTLE_SECONDS = THROTTLE_MINUTES * 60
THROTTLE_FILE = (
    Path(__file__).parent.parent / "hook-logs" / "install-guide-edit-reminder-throttle.json"
)

# 偵測安裝指南檔案的 regex
# 命中：
#   docs/development-setup.md
#   docs/environment-recovery-guide.md
#   任意路徑下的 development-setup* 或 environment-recovery* 檔案
INSTALL_GUIDE_PATTERN = re.compile(
    r"(?:development-setup|environment-recovery)",
    re.IGNORECASE,
)

# === 訊息常數 ===
MESSAGES = {
    "STARTUP": "Install Guide Edit Reminder Hook 啟動",
    "SKIP_NON_MATCHING_TOOL": "非 Write/Edit 工具 ({tool_name})，跳過",
    "SKIP_NON_INSTALL_GUIDE": "非安裝指南檔案 ({file_path})，跳過",
    "THROTTLED": "節流跳過（{file_path} 在 {minutes} 分鐘內已提示過）",
    "TRIGGERED": "偵測到安裝指南檔案修改：{file_path}",
    "REMINDER_TEMPLATE": (
        "\n[install-guide-reminder] 偵測到安裝指南檔案修改：{filename}\n"
        "請於 commit 前完成 fresh shell 驗證（PC-159 防護）：\n"
        "  (1) 安裝指令使用完整 scoped package name（如 @scope/pkg-name），非短名\n"
        "  (2) 開新 terminal（fresh shell，無既有環境變數污染）執行修改後的指令\n"
        "  (3) 若為 IMP ticket，acceptance 須包含 fresh shell 驗證條件\n"
        "  (4) 驗證輸出建議附於 ticket Test Results 或 Solution\n"
        "\n"
        "參考：.claude/error-patterns/process-compliance/PC-159*.md\n"
        "      docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W3-052.md\n"
        "（{throttle_minutes} 分鐘內同檔案只提示一次）\n"
    ),
}


def is_install_guide_path(file_path: str) -> bool:
    """判斷路徑是否為安裝指南檔案。"""
    if not file_path:
        return False
    return bool(INSTALL_GUIDE_PATTERN.search(file_path))


def load_throttle_cache(logger) -> dict:
    """載入節流快取，格式：{ file_path: last_reminded_epoch }。"""
    try:
        if THROTTLE_FILE.exists():
            with THROTTLE_FILE.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
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
    logger.info(f"已發出 fresh shell 驗證提醒：{filename}")


def main() -> int:
    """Hook 主入口。"""
    logger = setup_hook_logging("install-guide-edit-reminder")
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

    if not is_install_guide_path(file_path):
        logger.debug(MESSAGES["SKIP_NON_INSTALL_GUIDE"].format(file_path=file_path))
        return 0

    now = time.time()
    cache = load_throttle_cache(logger)

    if is_throttled(file_path, cache, now):
        logger.info(
            MESSAGES["THROTTLED"].format(file_path=file_path, minutes=THROTTLE_MINUTES)
        )
        return 0

    logger.info(MESSAGES["TRIGGERED"].format(file_path=file_path))
    emit_reminder(file_path, logger)

    cache = prune_expired(cache, now)
    cache[file_path] = now
    save_throttle_cache(cache, logger)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "install-guide-edit-reminder"))
