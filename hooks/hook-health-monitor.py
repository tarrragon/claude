#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Hook Health Monitor - Hook 系統健康狀態監控

在 SessionStart 時檢查所有 SessionStart Hook 的運作狀態。

檢查內容：
1. 動態解析 settings.json 中所有 SessionStart hooks
2. 驗證每個 hook 的日誌目錄是否正常更新
3. 報告覆蓋全部 SessionStart hooks 的健康狀態

Exit Code:
- 0: 所有 Hook 正常或僅有警告

使用方式：
  由 SessionStart Hook 自動觸發

運作邏輯：
1. 從 settings.json 動態載入所有 SessionStart hooks（不硬編碼）
2. 純機械推導解析各 hook 對應的日誌目錄
3. 檢查日誌目錄最新修改時間
4. 輸出覆蓋全部 hooks 的健康報告
5. 失敗的 hook 信息輸出到 stderr

改進 (v2.0.0):
- 動態解析 settings.json 取得所有 SessionStart hooks
- 移除硬編碼 MONITORED_HOOKS
- 純機械推導解析日誌目錄（命名一致性已修復）
- 失敗 hook 資訊輸出到 stderr
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

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

WARNING_THRESHOLD_HOURS = 24  # 發出警告的時間閾值
CRITICAL_THRESHOLD_HOURS = 48  # 發出嚴重警告的時間閾值


# ============================================================================
# 輔助函式
# ============================================================================

def _extract_filename_from_command(command: str) -> Optional[str]:
    """從 .claude/hooks/ 下的 hook command 字串中提取 .py 檔案名稱

    只處理位於 .claude/hooks/ 目錄下的 hook，
    忽略 skills 腳本或其他路徑的 command（避免無效的監控目標）。

    Args:
        command: hook command 字串

    Returns:
        hook 檔案名稱（如 'foo.py'），或 None（非 hooks 目錄、非 .py、或格式不符）
    """
    if not command:
        return None
    command_parts = command.split()
    hook_path = command_parts[0]
    if hook_path.startswith('$CLAUDE_PROJECT_DIR/'):
        hook_path = hook_path.replace('$CLAUDE_PROJECT_DIR/', '')
    # 只監控 .claude/hooks/ 下的 hook，排除 skills 等其他路徑
    if '.claude/hooks/' not in hook_path:
        return None
    hook_filename = Path(hook_path).name
    return hook_filename if hook_filename.endswith('.py') else None


def load_sessionstart_hooks_from_settings(
    settings_path: Path
) -> List[str]:
    """從 settings.json 動態載入所有 SessionStart hooks 的檔案名稱

    Args:
        settings_path: settings.json 檔案路徑

    Returns:
        去重的 hook 檔案名稱清單（如 ['cli-dependency-check.py', ...]）
    """
    if not settings_path.exists():
        return []

    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(
            f"[hook-health-monitor] Failed to parse settings.json: {e}",
            file=sys.stderr
        )
        return []

    hook_filenames = set()
    hooks = settings.get('hooks', {})
    session_start_hooks = hooks.get('SessionStart', [])

    for hook_group in session_start_hooks:
        hooks_list = hook_group.get('hooks', [])
        for hook in hooks_list:
            filename = _extract_filename_from_command(hook.get('command', ''))
            if filename:
                hook_filenames.add(filename)

    return sorted(hook_filenames)


def resolve_hook_log_dir(
    hook_filename: str, project_root: Path
) -> Tuple[str, Path, bool]:
    """根據 hook 檔案名稱解析對應的日誌目錄

    所有 hook 的日誌目錄名稱已統一為檔名 stem（命名一致性已修復），
    採用純機械推導：去掉 .py 取 stem 即為日誌目錄名稱。

    Args:
        hook_filename: hook 檔案名稱（如 'cli-dependency-check.py'）
        project_root: 專案根目錄

    Returns:
        (log_dir_name, full_path, dir_exists)
        - log_dir_name: 日誌目錄名稱（= 檔名 stem）
        - full_path: .claude/hook-logs/{log_dir_name} 完整路徑
        - dir_exists: 日誌目錄是否實際存在
    """
    stem = Path(hook_filename).stem
    log_dir = project_root / ".claude" / "hook-logs" / stem
    return stem, log_dir, log_dir.is_dir()


def _check_single_hook_log(
    hook_filename: str, project_root: Path
) -> Tuple[int, str, str]:
    """檢查單個 hook 的日誌狀態

    Args:
        hook_filename: hook 檔案名稱
        project_root: 專案根目錄

    Returns:
        (severity, message, hook_filename)
    """
    candidate, log_dir, found = resolve_hook_log_dir(hook_filename, project_root)

    if not found:
        msg = "[WARN] {} log dir not found".format(hook_filename)
        return 2, msg, hook_filename

    try:
        stat_info = log_dir.stat()
        last_modified = datetime.fromtimestamp(stat_info.st_mtime)
        hours_ago = (datetime.now() - last_modified).total_seconds() / 3600

        if hours_ago < WARNING_THRESHOLD_HOURS:
            severity, msg = 0, "[OK] {} (last update: {}h ago)".format(
                hook_filename, int(hours_ago)
            )
        elif hours_ago < CRITICAL_THRESHOLD_HOURS:
            severity, msg = 1, "[WARN] {} (last update: {}h ago)".format(
                hook_filename, int(hours_ago)
            )
        else:
            severity, msg = 2, "[FAIL] {} (last update: {}h ago)".format(
                hook_filename, int(hours_ago)
            )

        return severity, msg, hook_filename

    except OSError as e:
        msg = "[FAIL] {} error: {}".format(hook_filename, str(e))
        return 2, msg, hook_filename


def check_hook_logs(
    project_root: Path,
    logger: logging.Logger,
    hook_filenames: List[str]
) -> Tuple[int, List[Tuple[int, str, str]]]:
    """檢查所有 SessionStart Hook 的日誌是否正常更新

    Args:
        project_root: 專案根目錄
        logger: 日誌物件，記錄每個 hook 的檢查結果到日誌檔
        hook_filenames: hook 檔案名稱清單

    Returns:
        (max_severity, check_results_list)
        max_severity: 0=正常, 1=警告, 2=嚴重警告
    """
    results = []
    max_severity = 0

    for hook_filename in hook_filenames:
        severity, msg, _ = _check_single_hook_log(hook_filename, project_root)
        results.append((severity, msg, hook_filename))
        max_severity = max(max_severity, severity)
        # 持久化每個 hook 的檢查結果到日誌檔
        if severity == 0:
            logger.debug(msg)
        elif severity == 1:
            logger.warning(msg)
        else:
            logger.error(msg)

    return max_severity, results


def _output_health_report(
    hook_filenames: List[str], log_results: List[Tuple[int, str, str]]
) -> None:
    """輸出健康檢查報告（純輸出，無回傳值）

    Args:
        hook_filenames: hook 檔案名稱清單
        log_results: 檢查結果清單
    """
    hook_output("=" * 70, "info")
    hook_output("Hook system health check", "info")
    hook_output("=" * 70, "info")
    hook_output("Checking {} SessionStart hooks".format(len(hook_filenames)), "info")

    for _, msg, _ in log_results:
        hook_output(msg, "info")

    hook_output("=" * 70, "info")


def main() -> int:
    """主函式"""
    logger = setup_hook_logging("hook-health-monitor")

    project_root = get_project_root()
    if not project_root:
        hook_output("Error: Cannot find project root", "error")
        return 1

    settings_path = project_root / ".claude" / "settings.json"
    hook_filenames = load_sessionstart_hooks_from_settings(settings_path)

    # 排除自身：monitor 的 setup_hook_logging 會立即更新 mtime，
    # 導致永遠自報健康，無法偵測自身故障
    own_filename = Path(__file__).name
    hook_filenames = [f for f in hook_filenames if f != own_filename]

    if not hook_filenames:
        hook_output(
            "Warning: No SessionStart hooks found in settings.json",
            "warning"
        )
        logger.warning("No SessionStart hooks found")

    log_severity, log_results = check_hook_logs(
        project_root, logger, hook_filenames
    )

    _output_health_report(hook_filenames, log_results)
    failure_hooks = [f for s, _, f in log_results if s == 2]

    # 失敗 hook 資訊輸出到 stderr
    if failure_hooks:
        stderr_msg = "Hook health check: {} hook(s) have critical issues: {}".format(
            len(failure_hooks), ", ".join(failure_hooks)
        )
        print(stderr_msg, file=sys.stderr)
        logger.warning(stderr_msg)

    # 決定最終狀態
    if log_severity == 0:
        hook_output("\nHook system is healthy", "info")
        logger.info("Hook health check passed")
    else:
        hook_output(
            "\nHook system has warnings. Please check .claude/hook-logs/",
            "warning"
        )
        logger.info("Hook health check: completed with warnings")

    return 0


if __name__ == "__main__":
    sys.exit(main())
