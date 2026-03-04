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

import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
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

# 日誌保留策略（天數）
LOG_RETENTION_DAYS = 7

# 日誌清理觸發頻率（每 N 次呼叫執行一次清理）
LOG_CLEANUP_TRIGGER_FREQUENCY = 10


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
    # 觸發日誌清理（降低頻率，每 LOG_CLEANUP_TRIGGER_FREQUENCY 次呼叫執行一次）
    cleanup_marker = log_base_dir / ".cleanup_trigger"
    try:
        if cleanup_marker.exists():
            count = int(cleanup_marker.read_text().strip() or "0")
            if count >= LOG_CLEANUP_TRIGGER_FREQUENCY:
                _cleanup_old_logs(log_base_dir)
                cleanup_marker.write_text("0")
            else:
                cleanup_marker.write_text(str(count + 1))
        else:
            cleanup_marker.write_text("1")
    except (OSError, ValueError):
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
        # 備援路徑：日誌寫入失敗時輸出到 stderr（W3-004）
        sys.stderr.write("Failed to log exception: {}\n".format(logging_error))
        sys.stderr.write(tb_str + "\n")
    # 輸出到 stderr 確保用戶可見（W25-005）
    sys.stderr.write("[Hook Error] {} failed unexpectedly. Check hook logs for details.\n".format(hook_name))


def read_json_from_stdin(logger: logging.Logger) -> Optional[dict]:
    """從 stdin 讀取 JSON 輸入

    處理三種情況：
    1. 空輸入（SessionStart 等事件無輸入）
    2. JSON 解析失敗
    3. 有效的 JSON 物件

    Args:
        logger: Logger 實例

    Returns:
        dict: 解析後的 JSON，或 None（空輸入或解析失敗）
    """
    try:
        input_text = sys.stdin.read().strip()

        # 空輸入：直接返回 None
        if not input_text:
            return None

        # 解析 JSON
        return json.loads(input_text)

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: {}".format(e))
        return None
    except Exception as e:
        logger.error("讀取 stdin 失敗: {}".format(e))
        return None


def parse_ticket_frontmatter(file_path: Path, logger: logging.Logger) -> Optional[dict]:
    """簡易 YAML frontmatter 解析（無外部依賴）

    只解析頂層 key-value，忽略巢狀結構和陣列。

    Args:
        file_path: Ticket 檔案路徑
        logger: Logger 實例

    Returns:
        dict: 解析出的 frontmatter key-value；若檔案無 frontmatter 則回傳 None
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        if not content.startswith('---'):
            return None

        # 找到第二個 ---
        end_idx = content.find('---', 3)
        if end_idx == -1:
            return None

        frontmatter_text = content[3:end_idx]
        result = {}

        for line in frontmatter_text.strip().split('\n'):
            # 跳過空行和註解
            if not line.strip() or line.strip().startswith('#'):
                continue

            # 跳過已縮排的行（巢狀結構）
            if line.startswith(' ') or line.startswith('\t'):
                continue

            # 只解析頂層 key
            if ':' in line:
                key, _, value = line.partition(':')
                result[key.strip()] = value.strip().strip("'\"")

        return result if result else None

    except Exception as e:
        logger.warning("解析 frontmatter 失敗 ({}): {}".format(file_path.name, e))
        return None


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
