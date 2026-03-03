#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook 統一日誌模組

為 44 個 Python hook 提供統一的日誌設定和頂層例外處理。
取代現有兩套分散實作（common_functions.setup_hook_logging 和 hook_logging.setup_hook_logging）。

Python 版本：3.9 相容（禁用 PEP 604、634、613）
外部依賴：無（僅標準庫）

核心 API：
- setup_hook_logging(hook_name: str) -> logging.Logger
- run_hook_safely(main_func: Callable[[], int], hook_name: str) -> int
"""

import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# ============================================================================
# 常數定義
# ============================================================================

# 時間戳格式（無冒號，避免 Windows 路徑問題）
TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"

# 預設 hook 名稱（空字串 fallback）
DEFAULT_HOOK_NAME = "unknown-hook"

# 日誌格式
FILE_FORMAT = "[%(asctime)s] %(levelname)s - %(message)s"
STREAM_FORMAT = "[%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日誌級別
FILE_HANDLER_LEVEL = logging.DEBUG
STREAM_HANDLER_LEVEL_DEBUG = logging.DEBUG
STREAM_HANDLER_LEVEL_NORMAL = logging.WARNING
LOGGER_LEVEL = logging.DEBUG

# 環境變數名稱
ENV_PROJECT_DIR = "CLAUDE_PROJECT_DIR"
ENV_HOOK_DEBUG = "HOOK_DEBUG"

# 搜尋深度
CLAUDE_MD_SEARCH_DEPTH = 5

# Exit code 常數
EXIT_ERROR = 1


# ============================================================================
# 內部輔助函式
# ============================================================================

def _find_project_root() -> Path:
    """查詢專案根目錄

    優先順序：
    1. 環境變數 CLAUDE_PROJECT_DIR
    2. 從 cwd 向上搜尋 CLAUDE.md（最多 5 層）
    3. os.getcwd() fallback（永不失敗）

    Returns:
        Path: 專案根目錄路徑
    """
    # 優先級 1：環境變數
    env_dir = os.getenv(ENV_PROJECT_DIR)
    if env_dir:
        return Path(env_dir)

    # 優先級 2：搜尋 CLAUDE.md（從 cwd 向上）
    current_dir = Path.cwd()
    for _ in range(CLAUDE_MD_SEARCH_DEPTH):
        if (current_dir / "CLAUDE.md").exists():
            return current_dir

        # 檢查是否已到達檔案系統根目錄
        parent = current_dir.parent
        if parent == current_dir:
            break

        current_dir = parent

    # 優先級 3：Fallback 到 cwd
    return Path.cwd()


def _sanitize_hook_name(name: str) -> str:
    """淨化 hook 名稱，移除無法用於檔案系統的字元

    替換規則：
    - "/" → "-"
    - "\\" → "-"
    - "<>" 和 "|" → "-"
    - 連續的 "-" 合併為單一 "-"
    - 前後的 "-" 移除

    空字串或 None 返回 "unknown-hook"

    Args:
        name: 原始 hook 名稱

    Returns:
        str: 淨化後的 hook 名稱
    """
    if not name:
        return DEFAULT_HOOK_NAME

    # 特殊字元替換
    for char in ["<", ">", "|"]:
        name = name.replace(char, "-")
    name = name.replace("/", "-").replace("\\", "-")

    # 合併連續 "-" 並移除前後
    while "--" in name:
        name = name.replace("--", "-")
    name = name.strip("-")

    return name if name else DEFAULT_HOOK_NAME


def _clear_logger_handlers(logger: logging.Logger) -> None:
    """清除 logger 的所有 handlers"""
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


def _create_stream_handler(is_debug: bool = False) -> logging.StreamHandler:
    """建立 StreamHandler（stdout）

    Args:
        is_debug: 是否為 DEBUG 模式

    Returns:
        logging.StreamHandler: 配置完成的 handler
    """
    handler = logging.StreamHandler(sys.stdout)
    level = STREAM_HANDLER_LEVEL_DEBUG if is_debug else STREAM_HANDLER_LEVEL_NORMAL
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(STREAM_FORMAT))
    return handler


def _create_file_handler(log_file_path: Path) -> Optional[logging.FileHandler]:
    """建立 FileHandler（檔案）

    Args:
        log_file_path: 日誌檔案路徑

    Returns:
        logging.FileHandler 或 None（失敗）
    """
    try:
        handler = logging.FileHandler(log_file_path, encoding='utf-8')
        handler.setLevel(FILE_HANDLER_LEVEL)
        handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=DATE_FORMAT))
        return handler
    except OSError:
        return None


def _create_fallback_logger(hook_name: str) -> logging.Logger:
    """建立 Fallback Logger（僅 StreamHandler）

    用於目錄建立失敗等異常場景。

    Args:
        hook_name: Hook 名稱

    Returns:
        logging.Logger: 配置完成的 Logger
    """
    logger = logging.getLogger(hook_name)
    _clear_logger_handlers(logger)
    logger.setLevel(LOGGER_LEVEL)
    logger.addHandler(_create_stream_handler())
    return logger


def _setup_logger_handlers(logger: logging.Logger, log_base_dir: Path,
                           sanitized_name: str, is_debug: bool) -> None:
    """為 logger 配置 handlers"""
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    log_file_path = log_base_dir / "{}-{}.log".format(sanitized_name, timestamp)
    file_handler = _create_file_handler(log_file_path)
    if file_handler:
        logger.addHandler(file_handler)
    logger.addHandler(_create_stream_handler(is_debug))


# ============================================================================
# 公開 API
# ============================================================================


def setup_hook_logging(hook_name: str) -> logging.Logger:
    """建立並設定 Hook 日誌系統

    功能：
    - 建立日誌目錄 .claude/hook-logs/{hook_name}/
    - 建立日誌檔案 {hook_name}-{YYYYMMDD-HHMMSS}.log
    - 配置 FileHandler + StreamHandler

    Args:
        hook_name: Hook 識別名稱

    Returns:
        logging.Logger: 已配置的 named Logger 實例
    """
    if not hook_name:
        hook_name = DEFAULT_HOOK_NAME

    sanitized_name = _sanitize_hook_name(hook_name)
    root_dir = _find_project_root()
    log_base_dir = root_dir / ".claude" / "hook-logs" / sanitized_name

    # 建立日誌目錄
    try:
        log_base_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return _create_fallback_logger(hook_name)

    # 取得 logger 並初始化
    logger = logging.getLogger(hook_name)
    _clear_logger_handlers(logger)
    logger.setLevel(LOGGER_LEVEL)

    # 配置 handlers
    is_debug = os.getenv(ENV_HOOK_DEBUG, "").lower() == "true"
    _setup_logger_handlers(logger, log_base_dir, sanitized_name, is_debug)

    return logger


def _log_exception(logger: logging.Logger, hook_name: str, tb_str: str) -> None:
    """記錄異常 traceback 到日誌

    Args:
        logger: Logger 實例
        hook_name: Hook 名稱
        tb_str: Traceback 字串
    """
    try:
        logger.critical("Unhandled exception in {}".format(hook_name))
        logger.critical(tb_str)
    except Exception as logging_error:
        print("Failed to log exception: {}".format(logging_error), file=sys.stdout)
        print(tb_str, file=sys.stdout)
    # 輸出到 stderr 確保用戶可見（W25-005）
    print("[Hook Error] {} failed unexpectedly. Check hook logs for details.".format(hook_name), file=sys.stderr)


def run_hook_safely(main_func: Callable[[], int], hook_name: str) -> int:
    """安全執行 Hook 函式，頂層例外處理

    功能：
    - 呼叫 setup_hook_logging 獲取 logger
    - 執行 main_func，捕獲 Exception（非 SystemExit/KeyboardInterrupt）
    - 異常時記錄完整 traceback 到日誌，返回 1

    Args:
        main_func: Hook 主入口函式，必須返回 int
        hook_name: Hook 識別名稱

    Returns:
        int: main_func 的返回值（正常），或 1（異常）
    """
    logger = setup_hook_logging(hook_name)

    try:
        exit_code = main_func()
        # 驗證返回值是整數
        if not isinstance(exit_code, int):
            try:
                exit_code = int(exit_code)
            except (ValueError, TypeError):
                exit_code = 0
        return exit_code
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        tb_str = traceback.format_exc()
        _log_exception(logger, hook_name, tb_str)
        return EXIT_ERROR
