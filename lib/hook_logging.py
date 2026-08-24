#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook 日誌與基礎設施模組（SSOT）

為 Hook 提供統一的日誌設定、專案路徑查詢和頂層例外處理。

本模組為 lib/ 與 hook_utils/hook_logging 整併後的單一 SSOT（0.37.0-W6-005）：
取代原 lib/hook_logging.py 的 DEPRECATED stub，採 hook_utils 的 UTF-8 防護版
setup_hook_logging（入口呼叫 ensure_utf8_io），並吸收 save_check_log / run_hook_safely。
額外保留 get_hook_log_dir 以維持向後相容。

核心 API：
- get_project_root()
- setup_hook_logging(hook_name: str) -> logging.Logger
- save_check_log(hook_name, log_content, logger)
- run_hook_safely(main_func, hook_name) -> int
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

from lib.hook_base import get_project_root, ENV_PROJECT_DIR, CLAUDE_MD_SEARCH_DEPTH  # re-export for backward compatibility

# ============================================================================
# 常數定義
# ============================================================================

# 日誌檔名日期粒度格式：每日一檔 append，取代原逐次觸發一檔的時分秒粒度。
# 新格式：<sanitized_hook_name>-YYYYMMDD.log（下游解析器須辨識此格式）
TIMESTAMP_FORMAT = "%Y%m%d"

# 預設 hook 名稱（空字串 fallback）
DEFAULT_HOOK_NAME = "unknown-hook"

# 日誌格式
FILE_FORMAT = "[%(asctime)s] %(levelname)s - %(message)s"
STREAM_FORMAT = "[%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日誌級別
FILE_HANDLER_LEVEL = logging.DEBUG
STREAM_HANDLER_LEVEL_DEBUG = logging.DEBUG
STREAM_HANDLER_LEVEL_NORMAL = logging.CRITICAL
LOGGER_LEVEL = logging.DEBUG

# 環境變數名稱
ENV_HOOK_DEBUG = "HOOK_DEBUG"

# Exit code 常數
EXIT_ERROR = 1
EXIT_DENY = 2  # CC runtime PreToolUse 僅此值觸發 DENY，其餘（含 0 與 1）均放行

# 日誌保留策略（天數）
LOG_RETENTION_DAYS = 7

# 日誌清理觸發間隔（秒數，預設 5 分鐘）
CLEANUP_INTERVAL_SECONDS = 300

# Liveness 索引子目錄：hook 已載入/未載入的正向訊號（見 mark_hook_entry）
LIVENESS_SUBDIR = "_liveness"

# CC runtime 曝露的 session id 環境變數，與 stdin session_id 一致
# （見 hook-architect-technical-reference.md）。取用此 env var 可在 stdin
# 讀取之前即取得 session_id，免除「先記進入、取得 session_id 後補綁」的
# 兩階段設計複雜度。
ENV_SESSION_ID = "CLAUDE_CODE_SESSION_ID"

# env var 未設時的 fallback session 識別（極舊 runtime 或環境變數被清除）
UNKNOWN_SESSION_ID = "unknown-session"


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


def _cleanup_old_logs(log_base_dir: Path, retention_days: int = LOG_RETENTION_DAYS,
                       pattern: str = "*.log") -> None:
    """清理超期日誌檔案

    Args:
        log_base_dir: 日誌基礎目錄
        retention_days: 保留天數（預設 7 天）
        pattern: glob pattern，預設 "*.log"；liveness 索引另傳 "*.jsonl"
    """
    try:
        cutoff_time = datetime.now() - timedelta(days=retention_days)
        for log_file in log_base_dir.glob(pattern):
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


def _maybe_cleanup(log_base_dir: Path, pattern: str = "*.log") -> None:
    """節流觸發日誌清理（基於 mtime 時間間隔，共用於 handler 建立與 liveness 索引）

    Args:
        log_base_dir: 日誌基礎目錄
        pattern: 傳給 _cleanup_old_logs 的 glob pattern
    """
    cleanup_marker = log_base_dir / ".cleanup_trigger"
    current_time = time.time()

    try:
        if cleanup_marker.exists():
            marker_mtime = cleanup_marker.stat().st_mtime
            if current_time - marker_mtime >= CLEANUP_INTERVAL_SECONDS:
                _cleanup_old_logs(log_base_dir, pattern=pattern)
                cleanup_marker.touch()
        else:
            cleanup_marker.touch()
    except OSError:
        pass


def _setup_logger_handlers(logger: logging.Logger, log_base_dir: Path,
                           sanitized_name: str, is_debug: bool) -> None:
    """為 logger 配置 handlers

    採用 lazy file creation 策略：只在實際寫入日誌時才建立檔案，
    避免產生空日誌檔案。使用 FileHandler 的 delay=True 參數。
    """
    _maybe_cleanup(log_base_dir, pattern="*.log")

    # 配置 FileHandler（使用 delay=True 實現 lazy file creation）
    timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
    log_file_path = log_base_dir / "{}-{}.log".format(sanitized_name, timestamp)

    try:
        # delay=True 延遲檔案建立至第一次寫入時；mode='a'（append，非覆寫）
        # 明確指定：同日多次觸發須 append 至同檔，FileHandler 預設雖為 'a'，
        # 顯式聲明避免未來誤改為 'w' 而破壞每日輪替 append 語意
        file_handler = logging.FileHandler(
            str(log_file_path), mode='a', encoding='utf-8', delay=True
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
        # 備援路徑：日誌寫入失敗時輸出到 stderr
        sys.stderr.write("Failed to log exception: {}\n".format(logging_error))
        sys.stderr.write(tb_str + "\n")
    # 輸出到 stderr 確保用戶可見
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

    # 跨平台 UTF-8 強制：在所有 Hook 入口統一設定
    # 防止 Windows cp950/cp936 locale 造成 JSON 解析失敗或輸出亂碼
    from lib.hook_base import ensure_utf8_io
    ensure_utf8_io()

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


def _liveness_log_dir() -> Path:
    """回傳 liveness 索引目錄（.claude/hook-logs/_liveness/）"""
    return get_project_root() / ".claude" / "hook-logs" / LIVENESS_SUBDIR


def _current_session_id() -> str:
    """取得當前 session id，取自 CC runtime 曝露的環境變數

    未設定時回傳 UNKNOWN_SESSION_ID，使該筆訊號仍可被彙整為
    「已載入但無法歸戶 session」，而非因取值失敗整筆遺失。
    """
    value = os.environ.get(ENV_SESSION_ID, "").strip()
    return value if value else UNKNOWN_SESSION_ID


def resolve_session_id(input_data: Optional[dict] = None) -> str:
    """優先取 stdin session_id，缺失時 fallback CC runtime 環境變數。

    收斂自 session-registry-*-hook.py（4 支）與 dispatch-record-hook.py
    共 5 處逐字重複定義（DRY 下沉，多 hook 共用邏輯應有單一定義）。

    與 _current_session_id() 的差異（刻意不重用，非疏漏）：
    _current_session_id() 缺環境變數時回傳 UNKNOWN_SESSION_ID 哨兵值——
    liveness 訊號用途，需非空字串以利彙整「已載入但無法歸戶」的訊號。
    本函式缺 stdin 與環境變數時回傳空字串，保留原 5 處呼叫端既有的
    `if not session_id:` truthiness 判斷語意（session-registry-*-hook.py
    藉此判斷「無法取得 session_id」以跳過 registry 寫入；若改回傳
    UNKNOWN_SESSION_ID，該判斷恆為 False，會靜默用假值繼續寫入 registry，
    是本次收斂時發現的行為陷阱，非本函式該解決的既有問題）。

    Args:
        input_data: PreToolUse/PostToolUse 等 hook 事件的完整 stdin JSON；
            None 或缺 session_id 鍵時跳過此來源，直接 fallback 環境變數。

    Returns:
        str: session id；stdin 與環境變數皆無時回傳空字串。
    """
    if input_data:
        sid = input_data.get("session_id")
        if sid:
            return sid
    return os.environ.get(ENV_SESSION_ID, "")


def mark_hook_entry(hook_name: str, logger: Optional[logging.Logger] = None) -> None:
    """寫入 hook liveness 進入訊號

    在 hook 執行判準（main_func）之前無條件寫入一筆「已進入」訊號到
    session-scoped 索引檔 `.claude/hook-logs/_liveness/<session_id>.jsonl`，
    使「已載入且執行中」成為可直接查詢的事實，不需靠日誌缺席推論或依賴
    對照組（如另一持續寫入的 hook）與即時探針。session 維度取自
    CLAUDE_CODE_SESSION_ID 環境變數，於 stdin 讀取之前即可取得，故單次
    寫入即完成綁定，不需「先記進入、取得 session_id 後補綁」的兩階段設計。

    已知殘留缺口：本函式由 run_hook_safely 呼叫，時序上晚於 hook 檔案自身
    的 module-level import（stdlib 之外的相依）。若 hook 在自身 import
    階段崩潰（而非 lib 本身），run_hook_safely 從未被呼叫，本函式也不會
    執行——此殘留情形與「從未被呼叫」同形，且無法在不修改每個 hook 檔案
    的前提下消除，故不在本次範圍內處理。

    Args:
        hook_name: Hook 識別名稱（原始值，未經 _sanitize_hook_name 淨化；
                   彙整入口以此值與 settings.json 註冊表比對）
        logger: 可選 Logger，寫入失敗時額外記錄 warning（雙通道：亦寫 stderr）
    """
    entry = {
        "hook": hook_name,
        "session_id": _current_session_id(),
        "pid": os.getpid(),
        "ts": datetime.now().isoformat(),
    }
    try:
        log_dir = _liveness_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        _maybe_cleanup(log_dir, pattern="*.jsonl")
        log_path = log_dir / "{}.jsonl".format(entry["session_id"])
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        message = "liveness 訊號寫入失敗（hook={}）: {}".format(hook_name, e)
        sys.stderr.write(message + "\n")
        if logger:
            logger.warning(message)


def run_hook_safely(
    main_func: Callable[[], int], hook_name: str, fail_closed: bool = False
) -> int:
    """安全執行 Hook 函式，頂層例外處理

    功能：
    - 呼叫 setup_hook_logging 獲取 logger
    - 執行 main_func，捕獲 Exception（非 SystemExit/KeyboardInterrupt）
    - 異常時記錄完整 traceback 到日誌檔，返回 EXIT_ERROR 或 EXIT_DENY（依 fail_closed）
    - 記錄執行時間到日誌

    Args:
        main_func: Hook 主入口函式，必須返回 int
        hook_name: Hook 識別名稱
        fail_closed: 異常時的失敗語意。False（預設）維持向後相容，回傳
            EXIT_ERROR（1）；CC runtime PreToolUse 僅 exit 2 觸發 DENY，故
            此值下任何執行期異常都會靜默放行。True 時回傳 EXIT_DENY（2），
            使異常本身觸發 DENY——僅適用於資料遺失防護類與保護分支類等
            「fail-open 代價不可逆」的守衛。預設值不可誤改為 True，否則會
            使非防護類 hook 的執行期異常一併全域轉為 fail-closed（DENY）。

    Returns:
        int: main_func 的返回值（正常），或異常時依 fail_closed 回傳
            EXIT_ERROR（1）/ EXIT_DENY（2）

    Note:
        exit 1 在 CLI 中可能觸發 "hook error" 顯示（IMP-049 已知 CLI bug），
        但這是 CLI 層問題，不應在 Hook 層繞過。異常記錄到日誌檔即可。
    """
    logger = setup_hook_logging(hook_name)
    mark_hook_entry(hook_name, logger)
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
        return EXIT_DENY if fail_closed else EXIT_ERROR


def get_hook_log_dir(hook_name: str) -> Path:
    """獲取 Hook 日誌目錄路徑（向後相容保留，lib 既有 API）

    Args:
        hook_name: Hook 名稱

    Returns:
        Path: 日誌目錄路徑
    """
    project_root = get_project_root()
    return project_root / ".claude" / "hook-logs" / hook_name
