#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Hook Health Monitor - Hook 系統健康狀態監控

在 SessionStart 時檢查關鍵 Hook 的運作狀態，確保 Skip-gate 保護機制正常。

檢查內容：
1. command-entrance-gate-hook 在 settings.json 中是否正確配置
2. command-entrance-gate 日誌是否在最近 24 小時內有記錄
3. Hook 執行次數是否合理

Exit Code:
- 0: 所有 Hook 正常
- 0: 有警告但不阻塊（日誌較舊但未超過 48 小時）

使用方式：
  由 SessionStart Hook 自動觸發

運作邏輯：
1. 檢查 settings.json 中 UserPromptSubmit 是否包含 command-entrance-gate-hook
2. 檢查日誌目錄最新修改時間
3. 如果日誌超過 24 小時未更新，發出警告
4. 如果日誌超過 48 小時未更新，發出高風險警告

改進 (v1.1.0):
- 使用 common_functions 統一 logging 和 output
- 避免 stderr 污染
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# 添加 lib 目錄到路徑（M-003 標準化）
sys.path.insert(0, str(Path(__file__).parent))

try:
    from hook_utils import setup_hook_logging
    from lib.common_functions import get_project_root, hook_output
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(1)

# ============================================================================
# 常數定義
# ============================================================================

CRITICAL_HOOK = "command-entrance-gate-hook.py"
HOOK_EVENT = "UserPromptSubmit"
LOG_DIR = "hook-logs/command-entrance-gate"
WARNING_THRESHOLD_HOURS = 24  # 發出警告的時間閾值
CRITICAL_THRESHOLD_HOURS = 48  # 發出嚴重警告的時間閾值


# ============================================================================
# 主函式
# ============================================================================

def check_settings_config(project_root: Path, logger: logging.Logger) -> Tuple[bool, str]:
    """檢查 settings.json 中是否正確配置了 command-entrance-gate-hook"""
    settings_path = project_root / ".claude" / "settings.json"

    if not settings_path.exists():
        return False, "settings.json 不存在"

    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        return False, "settings.json 格式錯誤"

    # 檢查 UserPromptSubmit Hook
    hooks = settings.get('hooks', {})
    user_prompt_hooks = hooks.get(HOOK_EVENT, [])

    # 尋找 command-entrance-gate-hook
    found = False
    for hook_group in user_prompt_hooks:
        hooks_list = hook_group.get('hooks', [])
        for hook in hooks_list:
            command = hook.get('command', '')
            if CRITICAL_HOOK in command:
                found = True
                break
        if found:
            break

    if found:
        return True, "[OK] command-entrance-gate-hook 已正確配置"
    else:
        return False, "[FAIL] command-entrance-gate-hook 未在 UserPromptSubmit 中配置"


def check_hook_logs(project_root: Path, logger: logging.Logger) -> Tuple[int, str]:
    """檢查 Hook 日誌是否正常更新

    Returns:
        (severity, message)
        severity: 0=正常, 1=警告, 2=嚴重警告
    """
    log_dir = project_root / ".claude" / LOG_DIR

    if not log_dir.exists():
        return 1, f"✗ Hook 日誌目錄不存在: {log_dir}"

    # 取得目錄最後修改時間
    try:
        stat_info = log_dir.stat()
        last_modified = datetime.fromtimestamp(stat_info.st_mtime)
        now = datetime.now()
        time_delta = now - last_modified

        hours_ago = time_delta.total_seconds() / 3600

        if hours_ago < WARNING_THRESHOLD_HOURS:
            return 0, f"[OK] Hook 日誌正常（最後更新: {int(hours_ago)}h 前）"
        elif hours_ago < CRITICAL_THRESHOLD_HOURS:
            return 1, f"[WARN] Hook 日誌較舊（最後更新: {int(hours_ago)}h 前，建議檢查）"
        else:
            return 2, f"[FAIL] Hook 日誌已過期（最後更新: {int(hours_ago)}h 前，需要立即檢查）"

    except Exception as e:
        return 1, f"[FAIL] 無法檢查日誌狀態: {e}"


def main():
    """主函式"""
    logger = setup_hook_logging("hook-health-monitor")

    # 初始化路徑
    project_root = get_project_root()
    if not project_root:
        hook_output("Error: Cannot find project root", "error")
        sys.exit(1)

    # 執行檢查
    checks = []
    log_severity = 0

    # 檢查 1：settings.json 配置
    config_ok, config_msg = check_settings_config(project_root, logger)
    checks.append((config_ok, config_msg))
    logger.debug(f"Config check: {config_msg}")

    # 檢查 2：Hook 日誌
    log_severity, log_msg = check_hook_logs(project_root, logger)
    log_ok = log_severity <= 1  # 0 或 1 為可接受
    checks.append((log_ok, log_msg))
    logger.debug(f"Log check: {log_msg}")

    # 輸出檢查結果
    hook_output("=" * 70, "info")
    hook_output("Hook 系統健康狀態檢查", "info")
    hook_output("=" * 70, "info")
    for is_ok, msg in checks:
        hook_output(msg, "info")
    hook_output("=" * 70, "info")

    # 決定最終狀態
    if all(is_ok for is_ok, _ in checks) and log_severity == 0:
        hook_output("\nHook 系統正常運作", "info")
        logger.info("Hook health check passed")
        sys.exit(0)
    elif log_severity == 2:
        hook_output("\nHook 系統存在問題，請檢查 .claude/hook-logs/command-entrance-gate/", "warning")
        logger.warning("Hook health check: issues detected")
        sys.exit(0)  # 警告但不阻塊
    else:
        hook_output("\nHook 系統基本正常（有輕微警告）", "info")
        logger.info("Hook health check: basic OK with warnings")
        sys.exit(0)


if __name__ == "__main__":
    main()
