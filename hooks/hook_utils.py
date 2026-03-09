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
import re
import subprocess
import sys
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

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

# 日誌清理觸發間隔（秒數，預設 5 分鐘）
CLEANUP_INTERVAL_SECONDS = 300

# 決策樹欄位識別標記（統一版本，合併 command-entrance-gate-hook 和 agent-ticket-validation-hook）
DECISION_TREE_MARKERS = [
    "decision_tree_path:",
    "## 決策樹路徑",
    "decision_nodes:",
    "## 決策樹",
    "## Decision Tree",
    "## 決策流程",
]


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


# ============================================================================
# 公開 API
# ============================================================================


def get_project_root() -> Path:
    """取得專案根目錄

    優先順序：
    1. 環境變數 CLAUDE_PROJECT_DIR
    2. 從 cwd 向上搜尋 CLAUDE.md（最多 5 層）
    3. os.getcwd() fallback（永不失敗）

    Returns:
        Path: 專案根目錄路徑
    """
    return _find_project_root()


def run_git(
    args: List[str],
    cwd: "str | Path | None" = None,
    timeout: int = 5,
    logger: "logging.Logger | None" = None,
) -> "str | None":
    """執行 git 命令並回傳 stdout

    Args:
        args: git 子命令和參數，如 ["log", "-1", "--format=%ct"]
        cwd: 工作目錄（預設為當前目錄）
        timeout: 執行超時秒數（預設 5）
        logger: 可選日誌物件，失敗時記錄 warning

    Returns:
        stdout 輸出（stripped），或 None 若執行失敗
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            if logger:
                logger.warning("git 命令失敗: {} (exit code: {})".format(
                    " ".join(args), result.returncode
                ))
            return None
    except subprocess.TimeoutExpired:
        if logger:
            logger.warning("git 命令超時: {}".format(" ".join(args)))
        return None
    except FileNotFoundError:
        if logger:
            logger.warning("git 命令未找到")
        return None
    except OSError as e:
        if logger:
            logger.warning("執行 git 命令失敗: {}".format(e))
        return None


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


def extract_tool_input(
    input_data: "dict | None",
    logger: "logging.Logger | None" = None
) -> dict:
    """安全提取 input_data 中的 tool_input 欄位

    處理三種情況：
    1. input_data 為 None 或空值 → 返回 {}
    2. tool_input 欄位缺失或為 None → 返回 {}
    3. tool_input 為有效的 dict → 返回該 dict

    Args:
        input_data: Hook 輸入資料（dict 或 None）
        logger: 可選 Logger 實例，用於記錄詳細資訊

    Returns:
        dict: 提取出的 tool_input（始終返回 dict，無欄位時返回空 dict）

    Examples:
        >>> extract_tool_input({"tool_input": {"file_path": "test.py"}})
        {'file_path': 'test.py'}

        >>> extract_tool_input({"other": "value"})
        {}

        >>> extract_tool_input(None)
        {}
    """
    if input_data is None:
        if logger:
            logger.debug("input_data 為 None，返回空 dict")
        return {}

    if not isinstance(input_data, dict):
        if logger:
            logger.warning("input_data 非 dict 類型，返回空 dict: {}".format(type(input_data)))
        return {}

    tool_input = input_data.get("tool_input")

    # tool_input 為 None 或不存在時返回 {}
    if tool_input is None:
        if logger:
            logger.debug("tool_input 欄位為 None 或不存在，返回空 dict")
        return {}

    # tool_input 應為 dict，但可能是其他型別
    if not isinstance(tool_input, dict):
        if logger:
            logger.warning("tool_input 非 dict 類型，返回空 dict: {}".format(type(tool_input)))
        return {}

    if logger:
        logger.debug("成功提取 tool_input，欄位數: {}".format(len(tool_input)))

    return tool_input


def extract_tool_response(
    input_data: "dict | None",
    logger: "logging.Logger | None" = None
) -> dict:
    """安全提取 input_data 中的 tool_response 欄位

    處理三種情況：
    1. input_data 為 None 或空值 → 返回 {}
    2. tool_response 欄位缺失或為 None → 返回 {}
    3. tool_response 為有效的 dict → 返回該 dict

    Args:
        input_data: Hook 輸入資料（dict 或 None）
        logger: 可選 Logger 實例，用於記錄詳細資訊

    Returns:
        dict: 提取出的 tool_response（始終返回 dict，無欄位時返回空 dict）

    Examples:
        >>> extract_tool_response({"tool_response": {"stdout": "OK", "exit_code": 0}})
        {'stdout': 'OK', 'exit_code': 0}

        >>> extract_tool_response({"other": "value"})
        {}

        >>> extract_tool_response(None)
        {}
    """
    if input_data is None:
        if logger:
            logger.debug("input_data 為 None，返回空 dict")
        return {}

    if not isinstance(input_data, dict):
        if logger:
            logger.warning("input_data 非 dict 類型，返回空 dict: {}".format(type(input_data)))
        return {}

    tool_response = input_data.get("tool_response")

    # tool_response 為 None 或不存在時返回 {}
    if tool_response is None:
        if logger:
            logger.debug("tool_response 欄位為 None 或不存在，返回空 dict")
        return {}

    # tool_response 應為 dict，但可能是其他型別
    if not isinstance(tool_response, dict):
        if logger:
            logger.warning("tool_response 非 dict 類型，返回空 dict: {}".format(type(tool_response)))
        return {}

    if logger:
        logger.debug("成功提取 tool_response，欄位數: {}".format(len(tool_response)))

    return tool_response


def parse_ticket_frontmatter(
    content_or_path: "str | Path",
    logger: "logging.Logger | None" = None
) -> dict:
    """統一的 YAML frontmatter 解析（支援 str 和 Path 輸入）

    支援以下 YAML 特性：
    - 頂層 key-value 對
    - 多行字串（|, >, |-, >-）
    - 嵌套結構（縮排鍵值對）
    - 簡單列表

    無外部依賴，支援 Python 3.9+。

    Args:
        content_or_path: Ticket 檔案內容（字串）或檔案路徑（Path）
        logger: 可選 Logger 實例，用於記錄錯誤

    Returns:
        dict: 解析出的 frontmatter key-value（始終返回 dict，無 frontmatter 時返回空 dict、
              或解析失敗時也返回空 dict 並記錄警告）
    """
    try:
        # 步驟 1：取得文件內容
        if isinstance(content_or_path, Path):
            try:
                content = content_or_path.read_text(encoding='utf-8')
                file_name = content_or_path.name
            except Exception as e:
                if logger:
                    logger.warning("讀取檔案失敗 ({}): {}".format(content_or_path.name, e))
                return {}
        else:
            content = str(content_or_path) if content_or_path else ""
            file_name = "frontmatter"

        # 步驟 2：驗證 frontmatter 標記
        if not content.startswith('---'):
            return {}

        # 步驟 3：找到 frontmatter 結束標記
        end_idx = content.find('---', 3)
        if end_idx == -1:
            return {}

        frontmatter_text = content[3:end_idx].strip()
        if not frontmatter_text:
            return {}

        # 步驟 4：解析 YAML
        result = {}
        current_key = None
        multiline_marker = None

        lines = frontmatter_text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # 跳過空行和註解
            if not line.strip() or line.strip().startswith('#'):
                i += 1
                continue

            # 檢查是否為嵌套行（以 2 個空格開頭）
            if line.startswith('  ') and not line.startswith('    '):
                nested_line = line.strip()

                # 若有多行標記，直接收集縮排行
                if multiline_marker is not None:
                    if current_key:
                        if current_key not in result:
                            result[current_key] = ""
                        result[current_key] += "\n" + nested_line if result[current_key] else nested_line
                    i += 1
                    continue

                # 否則作為嵌套鍵值對
                if ':' in nested_line:
                    nested_key, nested_value = nested_line.split(':', 1)
                    nested_key = nested_key.strip()
                    nested_value = nested_value.strip().strip("'\"")

                    if current_key:
                        if not isinstance(result.get(current_key), dict):
                            result[current_key] = {}
                        result[current_key][nested_key] = nested_value
                i += 1
                continue

            # 頂層鍵值對
            if ':' in line:
                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()

                # 檢查多行標記
                if value in ('|', '>', '|-', '>-'):
                    current_key = key
                    multiline_marker = value
                    result[key] = ""
                    i += 1
                    continue

                # 移除引號
                value_clean = value.strip("'\"") if value else ""
                result[key] = value_clean
                current_key = key
                multiline_marker = None

            i += 1

        return result

    except Exception as e:
        if logger:
            logger.warning("解析 frontmatter 失敗: {}".format(e))
        return {}


def parse_ticket_date(value: "Any", logger: "logging.Logger | None" = None) -> Optional[datetime]:
    """支援多格式的 Ticket 日期解析。

    格式優先級：
    1. datetime.date 物件（YAML 直接解析）
    2. ISO 8601 / RFC 3339 字串（fromisoformat）
    3. 簡單日期字串 YYYY-MM-DD

    Args:
        value: 日期值（可能是 datetime、date 或字串）
        logger: 日誌物件（可選）

    Returns:
        datetime 物件或 None（無法解析時）
    """
    # 已經是 datetime 物件
    if isinstance(value, datetime):
        return value

    # 是 date 物件，轉為 datetime
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    # 字串解析
    if not isinstance(value, str):
        if logger:
            logger.warning("無法解析日期類型: {}".format(type(value)))
        return None

    value = value.strip()
    if not value:
        return None

    # 優先級 1: ISO 8601 / RFC 3339（使用 fromisoformat）
    try:
        dt = datetime.fromisoformat(value)
        if logger:
            logger.debug("日期解析成功（ISO 8601）: {}".format(dt.isoformat()))
        return dt
    except ValueError:
        pass

    # 優先級 2: 簡單日期 YYYY-MM-DD（strptime）
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        if logger:
            logger.debug("日期解析成功（YYYY-MM-DD）: {}".format(dt.isoformat()))
        return dt
    except ValueError:
        pass

    # 所有格式都失敗
    if logger:
        logger.warning("無法解析日期字串: {}".format(value))
    return None


def check_error_patterns_changed(
    project_root: Path,
    ticket_created: datetime,
    logger: "logging.Logger | None" = None
) -> "Tuple[bool, List[str]]":
    """掃描 .claude/error-patterns/ 目錄，找出所有 mtime > ticket_created 的 .md 檔案。

    Args:
        project_root: 專案根目錄
        ticket_created: Ticket 建立時間
        logger: 日誌物件（可選）

    Returns:
        tuple - (has_changed, file_list)
            - has_changed: 是否有新增/修改的 error-pattern
            - file_list: 新增/修改的檔案相對路徑清單
    """
    # 前置檢查
    if ticket_created is None:
        if logger:
            logger.warning("ticket created time 為 None，跳過檢查")
        return False, []

    # 檢查目錄是否存在
    error_patterns_dir = project_root / ".claude" / "error-patterns"
    if not error_patterns_dir.exists():
        if logger:
            logger.info("error-patterns 目錄不存在，跳過檢查")
        return False, []

    changed_files = []
    ticket_created_timestamp = ticket_created.timestamp()

    try:
        # 遞迴掃描所有 .md 檔案
        for file_path in error_patterns_dir.rglob("*.md"):
            try:
                file_mtime = file_path.stat().st_mtime
                if file_mtime > ticket_created_timestamp:
                    relative_path = file_path.relative_to(project_root)
                    changed_files.append(str(relative_path))
                    if logger:
                        logger.debug("找到新增檔案: {}".format(relative_path))
            except (OSError, PermissionError) as e:
                if logger:
                    logger.warning("無法讀取檔案 stat: {}: {}".format(file_path, e))
                continue

    except (OSError, PermissionError) as e:
        if logger:
            logger.warning("讀取 error-patterns 目錄失敗: {}".format(e))
        return False, []

    if logger:
        logger.info("掃描 error-patterns 目錄完成：發現 {} 個新增/修改檔案".format(len(changed_files)))
    has_changed = len(changed_files) > 0
    return has_changed, changed_files


# ============================================================================
# Ticket 檔案掃描函式（共用）
# ============================================================================


def get_current_version_from_todolist(
    project_root: Path, logger: "Optional[logging.Logger]" = None
) -> "Optional[str]":
    """從 docs/todolist.yaml 讀取 current_version 欄位

    Args:
        project_root: 專案根目錄
        logger: 可選日誌物件

    Returns:
        版本號字串（如 "0.1.0"）或 None（若讀取失敗）
    """
    todolist_file = project_root / "docs" / "todolist.yaml"

    if not todolist_file.exists():
        if logger:
            logger.debug("todolist.yaml 不存在: {}".format(todolist_file))
        return None

    try:
        content = todolist_file.read_text(encoding="utf-8")

        # 簡單正則提取 current_version: 欄位值
        match = re.search(r"current_version:\s*(\S+)", content)
        if match:
            version = match.group(1).strip()
            if logger:
                logger.info("從 todolist.yaml 讀取 current_version: {}".format(version))
            return version
        else:
            if logger:
                logger.debug("todolist.yaml 中未找到 current_version 欄位")
            return None
    except Exception as e:
        if logger:
            logger.warning("讀取 todolist.yaml 失敗: {}".format(e))
        return None


def scan_ticket_files_by_version(
    project_root: Path, version: str, logger: "Optional[logging.Logger]" = None
) -> List[Path]:
    """掃描特定版本的 Ticket 檔案

    Args:
        project_root: 專案根目錄
        version: 版本號（如 "0.1.0"）
        logger: 可選日誌物件

    Returns:
        Ticket 檔案路徑清單
    """
    tickets_dir = project_root / "docs" / "work-logs" / "v{}".format(version) / "tickets"

    if not tickets_dir.exists():
        if logger:
            logger.debug("Ticket 目錄不存在: {}".format(tickets_dir))
        return []

    try:
        ticket_files = list(tickets_dir.glob("*.md"))
        if logger:
            logger.debug("從版本 v{} 找到 {} 個 Ticket 檔案".format(version, len(ticket_files)))
        return ticket_files
    except (OSError, PermissionError) as e:
        if logger:
            logger.warning("掃描 Ticket 目錄失敗 (v{}): {}".format(version, e))
        return []


def find_ticket_files(
    project_root: Path, version: "Optional[str]" = None, logger: "Optional[logging.Logger]" = None
) -> List[Path]:
    """尋找所有 Ticket 檔案（支援版本優先和後向相容）

    功能：
    - 如指定 version，只掃描該版本目錄
    - 如未指定 version，優先掃描當前活躍版本（從 todolist.yaml 讀取）
    - 若讀取失敗或目錄不存在，掃描所有版本目錄
    - 支援後向相容：檢查舊位置 .claude/tickets/

    Args:
        project_root: 專案根目錄
        version: 版本號（可選，如 "0.1.0"）；若不指定則自動讀取
        logger: 可選日誌物件

    Returns:
        Ticket 檔案路徑清單
    """
    all_tickets = []

    # 檢查舊位置 .claude/tickets/（後向相容）
    old_tickets_dir = project_root / ".claude" / "tickets"
    if old_tickets_dir.exists():
        try:
            old_tickets = list(old_tickets_dir.glob("*.md"))
            all_tickets.extend(old_tickets)
            if logger:
                logger.debug("從 .claude/tickets/ 找到 {} 個 Ticket 檔案".format(len(old_tickets)))
        except (OSError, PermissionError) as e:
            if logger:
                logger.warning("掃描舊 Ticket 位置失敗: {}".format(e))

    # 如指定 version，只掃描該版本
    if version:
        version_tickets = scan_ticket_files_by_version(project_root, version, logger)
        all_tickets.extend(version_tickets)
        return all_tickets

    # 未指定 version：優先掃描當前活躍版本
    current_version = get_current_version_from_todolist(project_root, logger)

    if current_version:
        # 優先掃描當前版本
        current_tickets = scan_ticket_files_by_version(project_root, current_version, logger)
        all_tickets.extend(current_tickets)

        # Fallback：掃描其他版本（非當前版本）
        work_logs_dir = project_root / "docs" / "work-logs"
        if work_logs_dir.exists():
            try:
                for version_dir in work_logs_dir.glob("v*"):
                    if version_dir.name != "v{}".format(current_version):
                        other_tickets = scan_ticket_files_by_version(
                            project_root, version_dir.name[1:], logger
                        )
                        all_tickets.extend(other_tickets)
            except (OSError, PermissionError) as e:
                if logger:
                    logger.warning("掃描其他版本目錄失敗: {}".format(e))
    else:
        # Fallback：讀取失敗時，掃描所有版本目錄
        if logger:
            logger.info("current_version 讀取失敗，fallback 到掃描所有版本目錄")

        work_logs_dir = project_root / "docs" / "work-logs"
        if work_logs_dir.exists():
            try:
                for version_dir in work_logs_dir.glob("v*"):
                    version_tickets = scan_ticket_files_by_version(
                        project_root, version_dir.name[1:], logger
                    )
                    all_tickets.extend(version_tickets)
            except (OSError, PermissionError) as e:
                if logger:
                    logger.warning("掃描版本目錄失敗: {}".format(e))

    if logger:
        logger.debug("總計找到 {} 個 Ticket 檔案".format(len(all_tickets)))
    return all_tickets


def find_ticket_file(
    ticket_id: str,
    project_root: Optional[Path] = None,
    logger: Optional[logging.Logger] = None
) -> Optional[Path]:
    """尋找特定 ID 的 Ticket 檔案

    優化策略（O(1) early return）：
    1. 從 ticket_id 解析版本號（格式：{version}-W{wave}-{seq}）
    2. 直接構建路徑：docs/work-logs/v{version}/tickets/{ticket_id}.md
    3. 如果直接路徑存在 → 立即返回（early return）
    4. 檢查舊位置 .claude/tickets/{ticket_id}.md（向後相容）
    5. 如果上述路徑都不存在 → fallback 到 find_ticket_files() 全量掃描

    Args:
        ticket_id: Ticket ID（如 "0.1.0-W1-001" 或非標準格式）
        project_root: 專案根目錄（可選，若為 None 則自動取得）
        logger: 日誌物件（可選）

    Returns:
        Path: Ticket 檔案路徑，或 None 如未找到
    """
    if project_root is None:
        project_root = get_project_root()

    # 嘗試解析 ticket_id 中的版本號（格式：{version}-W{wave}-{seq}）
    # 範例：0.1.0-W31-003 → version="0.1.0"
    version = _parse_version_from_ticket_id(ticket_id)

    # Strategy 1: 直接構建路徑（如果能解析出版本號）
    if version:
        direct_path = (
            project_root / "docs" / "work-logs" / f"v{version}" / "tickets" / f"{ticket_id}.md"
        )
        if direct_path.exists():
            if logger:
                logger.info("找到 Ticket: {} 於 {} (direct path)".format(ticket_id, direct_path))
            return direct_path
        else:
            if logger:
                logger.debug("直接路徑不存在，嘗試舊位置: {}".format(ticket_id))

    # Strategy 2: 檢查舊位置 .claude/tickets/{ticket_id}.md（向後相容）
    old_path = project_root / ".claude" / "tickets" / f"{ticket_id}.md"
    if old_path.exists():
        if logger:
            logger.info("找到 Ticket: {} 於 {} (old location)".format(ticket_id, old_path))
        return old_path

    # Strategy 3: Fallback 到全量掃描（版本號解析失敗或直接路徑不存在）
    if logger:
        logger.debug("全部直接路徑未找到，執行全量掃描: {}".format(ticket_id))

    all_tickets = find_ticket_files(project_root, logger=logger)

    # 根據檔名篩選符合的 ticket_id
    expected_name = "{}.md".format(ticket_id)
    for ticket_file in all_tickets:
        if ticket_file.name == expected_name:
            if logger:
                logger.info("找到 Ticket: {} 於 {} (fallback scan)".format(ticket_id, ticket_file))
            return ticket_file

    if logger:
        logger.warning("未找到 Ticket 檔案: {}".format(ticket_id))
    return None


def _parse_version_from_ticket_id(ticket_id: str) -> Optional[str]:
    """從 Ticket ID 解析版本號

    Ticket ID 標準格式：{version}-W{wave}-{seq}
    範例：0.1.0-W31-003 → "0.1.0"

    Args:
        ticket_id: Ticket ID 字串

    Returns:
        版本號字串，或 None 如無法解析
    """
    if not ticket_id:
        return None

    # 尋找第一個 '-W' 分隔符
    wave_marker = "-W"
    wave_index = ticket_id.find(wave_marker)

    if wave_index <= 0:
        # 未找到 '-W' 或位置不合法
        return None

    # 版本號是 '-W' 之前的部分
    version = ticket_id[:wave_index]

    # 驗證版本號不為空，且形如 "x.y.z" 或類似格式
    if version and "." in version:
        return version

    return None


def validate_ticket_has_decision_tree(ticket_content: str, logger: "logging.Logger") -> bool:
    """驗證 Ticket 是否包含決策樹欄位

    檢查 Ticket 是否在 YAML frontmatter 或內容中包含決策樹相關欄位。
    支援多個決策樹標記變體（YAML 欄位、中文標題、英文標題）。

    Args:
        ticket_content: Ticket 檔案內容
        logger: Logger 物件

    Returns:
        bool: 是否包含決策樹欄位
    """
    if not ticket_content:
        logger.debug("Ticket 內容為空")
        return False

    # 檢查任何決策樹欄位（包含 YAML frontmatter 和標題區段）
    for marker in DECISION_TREE_MARKERS:
        if marker in ticket_content:
            logger.debug("在 Ticket 中找到決策樹標記: {}".format(marker))
            return True

    logger.debug("未在 Ticket 中找到決策樹欄位")
    return False


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
