#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook 日誌與基礎設施模組

為 Hook 提供統一的日誌設定、專案路徑查詢和頂層例外處理。

核心 API：
- get_project_root()
- setup_hook_logging(hook_name: str) -> logging.Logger
- save_check_log(hook_name, log_content, logger)
- run_hook_safely(main_func, hook_name) -> int
"""

import logging
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from .hook_base import get_project_root, ENV_PROJECT_DIR, CLAUDE_MD_SEARCH_DEPTH  # re-export for backward compatibility

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
ENV_HOOK_DEBUG = "HOOK_DEBUG"

# Exit code 常數
EXIT_ERROR = 1

# 日誌保留策略（天數）
LOG_RETENTION_DAYS = 7

# 日誌清理觸發間隔（秒數，預設 5 分鐘）
CLEANUP_INTERVAL_SECONDS = 300


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
    """建立 StreamHandler（stderr）

    Args:
        is_debug: 是否為 DEBUG 模式

    Returns:
        logging.StreamHandler: 配置完成的 handler
    """
    handler = logging.StreamHandler(sys.stderr)
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
    except OSError as e:
        # 檔案操作失敗（如無權限、磁碟滿）時輸出到 stderr 並回傳 None，
        # 由上層呼叫者決定是否使用 fallback logger（如 _setup_logger_handlers）
        sys.stderr.write("Failed to create file handler for {}: {}\n".format(log_file_path, e))
        return None


def _cleanup_old_logs(log_base_dir: Path, retention_days: int = LOG_RETENTION_DAYS) -> None:
    """清理超期日誌檔案

    Args:
        log_base_dir: 日誌基礎目錄
        retention_days: 保留天數（預設 7 天）
    """
    try:
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        for log_file in log_base_dir.glob("*.log"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_time:
                    log_file.unlink()
            except (OSError, ValueError):
                # 檔案已被刪除或無法存取，忽略
                pass
    except OSError:
        # 目錄不存在或無法存取，忽略
        pass


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
    """為 logger 配置 handlers

    採用 lazy file creation 策略：只在實際寫入日誌時才建立檔案，
    避免產生空日誌檔案（W3-004）。使用 FileHandler 的 delay=True 參數。
    """
    # 觸發日誌清理（基於 mtime 時間間隔）
    cleanup_marker = log_base_dir / ".cleanup_trigger"
    current_time = time.time()

    try:
        if cleanup_marker.exists():
            # 檢查檔案的 mtime
            marker_mtime = cleanup_marker.stat().st_mtime
            if current_time - marker_mtime >= CLEANUP_INTERVAL_SECONDS:
                _cleanup_old_logs(log_base_dir)
                cleanup_marker.touch()
        else:
            # 檔案不存在，建立它
            cleanup_marker.touch()
    except OSError:
        pass

    # 配置 FileHandler（使用 delay=True 實現 lazy file creation）
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    log_file_path = log_base_dir / "{}-{}.log".format(sanitized_name, timestamp)

    try:
        # delay=True 延遲檔案建立至第一次寫入時
        file_handler = logging.FileHandler(
            str(log_file_path), encoding='utf-8', delay=True
        )
        file_handler.setLevel(FILE_HANDLER_LEVEL)
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(file_handler)
    except OSError:
        # 檔案創建失敗，忽略，僅使用 StreamHandler
        pass

    logger.addHandler(_create_stream_handler(is_debug))


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
        # 備援路徑：日誌寫入失敗時輸出到 stderr（W3-004）
        sys.stderr.write("Failed to log exception: {}\n".format(logging_error))
        sys.stderr.write(tb_str + "\n")
    # 輸出到 stderr 確保用戶可見（W25-005）
    sys.stderr.write("[Hook Error] {} failed unexpectedly. Check hook logs for details.\n".format(hook_name))


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
    root_dir = get_project_root()
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


def save_check_log(
    hook_name: str,
    log_content: str,
    logger: Optional[logging.Logger] = None
) -> None:
    """統一的 Hook 檢查日誌儲存函式

    功能：
    - 建立日誌目錄 .claude/hook-logs/{hook_name}/
    - 建立日誌檔案 checks-{YYYYMMDD}.log（每日一個檔案）
    - 寫入檢查結果日誌

    Args:
        hook_name: Hook 識別名稱，用於識別日誌目錄
        log_content: 要寫入的日誌內容（字串）
        logger: 可選的 Logger 實例，用於記錄錯誤

    Returns:
        None

    Example:
        >>> save_check_log(
        ...     hook_name="command-entrance-gate",
        ...     log_content=f"[{datetime.now().isoformat()}] Prompt: ...",
        ...     logger=logger
        ... )
    """
    try:
        project_dir = get_project_root()
        log_dir = project_dir / ".claude" / "hook-logs" / hook_name
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"checks-{datetime.now().strftime('%Y%m%d')}.log"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_content)
            if logger:
                logger.debug("檢查日誌已儲存: {}".format(log_file))
        except Exception as e:
            if logger:
                logger.warning("寫入日誌檔案失敗: {}".format(e))
    except Exception as e:
        if logger:
            logger.warning("儲存檢查日誌失敗: {}".format(e))


def run_hook_safely(main_func: Callable[[], int], hook_name: str) -> int:
    """安全執行 Hook 函式，頂層例外處理

    功能：
    - 呼叫 setup_hook_logging 獲取 logger
    - 執行 main_func，捕獲 Exception（非 SystemExit/KeyboardInterrupt）
    - 異常時記錄完整 traceback 到日誌，返回 1
    - 記錄執行時間到日誌

    Args:
        main_func: Hook 主入口函式，必須返回 int
        hook_name: Hook 識別名稱

    Returns:
        int: main_func 的返回值（正常），或 1（異常）
    """
    logger = setup_hook_logging(hook_name)
    start_time = time.time()

    try:
        exit_code = main_func()
        # 驗證返回值是整數
        if not isinstance(exit_code, int):
            try:
                exit_code = int(exit_code)
            except (ValueError, TypeError):
                exit_code = 0

        # 記錄執行時間
        elapsed_time = time.time() - start_time
        logger.debug("Hook execution time: {:.2f}s".format(elapsed_time))
        return exit_code
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        elapsed_time = time.time() - start_time
        tb_str = traceback.format_exc()
        logger.debug("Hook execution time before failure: {:.2f}s".format(elapsed_time))
        _log_exception(logger, hook_name, tb_str)
        return EXIT_ERROR
