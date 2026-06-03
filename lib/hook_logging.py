#!/usr/bin/env python3
"""
Hook 日誌系統

[DEPRECATED] v0.31.0
- 已遷移至 .claude/hooks/hook_utils.py
- 使用 hook_utils.setup_hook_logging 代替

提供統一的 Hook 日誌設定功能。
消除 task-dispatch-readiness-check.py, ticket-quality-gate-hook.py 等檔案中的重複程式碼。

主要功能:
- setup_hook_logging: 設定 Hook 日誌（已遷移）

參考：.claude/hooks/hook_utils.py（新日誌系統）
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_hook_logging(
    hook_name: str,
    log_subdir: Optional[str] = None,
    log_level: Optional[int] = None,
    include_stderr: bool = False
) -> logging.Logger:
    """
    設定 Hook 日誌系統

    Args:
        hook_name: Hook 名稱，用於識別日誌來源和檔案名稱
        log_subdir: 日誌子目錄，預設為 hook_name
        log_level: 日誌等級，預設根據 HOOK_DEBUG 環境變數決定
        include_stderr: 是否同時輸出到 stderr

    Returns:
        logging.Logger: 配置好的 Logger 實例

    Example:
        logger = setup_hook_logging("branch-verify")
        logger.info("Hook started")
        logger.error("Something went wrong")

    日誌檔案位置:
        .claude/hook-logs/{log_subdir}/{hook_name}-{YYYYMMDD-HHMMSS}.log
    """
    # 決定日誌等級
    if log_level is None:
        debug_mode = os.getenv("HOOK_DEBUG", "").lower() == "true"
        log_level = logging.DEBUG if debug_mode else logging.INFO

    # 建立 Logger
    logger = logging.getLogger(hook_name)
    logger.setLevel(log_level)

    # 避免重複添加 handler
    if logger.handlers:
        return logger

    # 建立日誌目錄
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    subdir = log_subdir or hook_name
    log_dir = Path(project_root) / ".claude" / "hook-logs" / subdir
    log_dir.mkdir(parents=True, exist_ok=True)

    # 日誌檔案路徑
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"{hook_name}-{timestamp}.log"

    # 設定 formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 檔案 handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 可選的 stderr handler
    if include_stderr:
        import sys
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(formatter)
        logger.addHandler(stderr_handler)

    return logger


def get_hook_log_dir(hook_name: str) -> Path:
    """
    獲取 Hook 日誌目錄路徑

    Args:
        hook_name: Hook 名稱

    Returns:
        Path: 日誌目錄路徑
    """
    project_root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return Path(project_root) / ".claude" / "hook-logs" / hook_name
