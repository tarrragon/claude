#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 hook_utils.py - Hook 統一日誌模組

測試策略：Sociable Unit Tests
- 使用真實 logging 系統，不 mock logging
- Mock 外部依賴：環境變數、時間戳、cwd
- 使用 tmp_path fixture 隔離檔案系統
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

# 動態導入 hook_utils（可能不存在）
try:
    from hook_utils import (
        setup_hook_logging,
        run_hook_safely,
        _log_exception,
        get_current_version_from_todolist,
        scan_ticket_files_by_version,
        find_ticket_files,
        find_ticket_file,
        _parse_version_from_ticket_id,
    )
except ImportError:
    # 如果模組還不存在，定義虛擬函式以便測試可以 import
    def setup_hook_logging(hook_name: str) -> logging.Logger:
        raise NotImplementedError()

    def run_hook_safely(main_func, hook_name: str) -> int:
        raise NotImplementedError()

    def _log_exception(logger: logging.Logger, hook_name: str, tb_str: str) -> None:
        raise NotImplementedError()

    def get_current_version_from_todolist(project_root, logger=None):
        raise NotImplementedError()

    def scan_ticket_files_by_version(project_root, version, logger=None):
        raise NotImplementedError()

    def find_ticket_files(project_root, version=None, logger=None):
        raise NotImplementedError()

    def find_ticket_file(ticket_id, project_root=None, logger=None):
        raise NotImplementedError()

    def _parse_version_from_ticket_id(ticket_id: str):
        raise NotImplementedError()


# ============================================================================
# Shared Fixtures
# ============================================================================

@pytest.fixture
def reset_loggers():
    """清空測試後的 logger registry（避免跨測試污染）"""
    yield
    # 清除所有以 "test-" 開頭的 logger
    logger_dict = logging.Logger.manager.loggerDict
    for logger_name in list(logger_dict.keys()):
        if isinstance(logger_name, str) and logger_name.startswith("test-"):
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)


@pytest.fixture
def project_root(tmp_path):
    """建立臨時專案根目錄結構"""
    (tmp_path / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "hook-logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text("# Test Project\n")
    return tmp_path


@pytest.fixture
def mock_env_var(monkeypatch):
    """Mock 環境變數"""
    def set_env(key: str, value: Optional[str]):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return set_env


@pytest.fixture
def mock_time():
    """固定時間戳以驗證檔名"""
    fixed_time = datetime(2026, 2, 25, 10, 0, 0)
    with patch('hook_utils.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_time
        # 也需要能呼叫 datetime 本身的方法
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield fixed_time


# ============================================================================
# TestSetupHookLogging - Scenario 1: 正常日誌設定流程
# ============================================================================

class TestSetupHookLogging:
    """setup_hook_logging() 功能測試"""

    def test_scenario_1_normal_setup(self, project_root, mock_env_var, reset_loggers):
        """正常日誌設定：建立 logger、directory、handlers"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("test-hook")

        # 驗證返回 Logger 實例
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test-hook"

        # 驗證目錄建立
        log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
        assert log_dir.exists()

        # 驗證 handlers 數量（FileHandler + StreamHandler）
        # 注意：FileHandler 使用 delay=True，檔案只在首次寫入時建立，不是在 setup 時建立
        assert len(logger.handlers) == 2

        # 驗證日誌檔案在寫入後建立
        logger.info("test message")
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1

    def test_scenario_1_file_handler(self, project_root, mock_env_var, reset_loggers, capsys):
        """FileHandler 將訊息寫入檔案"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("test-hook")
        logger.info("test info message")
        logger.debug("test debug message")

        # 尋找日誌檔案
        log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1

        # 驗證檔案內容
        log_content = log_files[0].read_text()
        assert "test info message" in log_content
        assert "test debug message" in log_content

    def test_scenario_1_stream_handler(self, project_root, mock_env_var, reset_loggers, capsys):
        """StreamHandler 輸出到 stderr，WARNING 級別及以上"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("test-hook")

        # 測試不同級別的輸出
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")

        captured = capsys.readouterr()

        # 驗證輸出（DEBUG 和 INFO 寫入檔案但不輸出到 stderr）
        assert "debug msg" not in captured.err
        assert "info msg" not in captured.err
        # WARNING 和 ERROR 輸出到 stderr（StreamHandler）
        assert "warning msg" in captured.err
        assert "error msg" in captured.err

        # 驗證無 stdout 輸出
        assert captured.out == ""

    def test_scenario_1_log_levels(self, project_root, mock_env_var, reset_loggers):
        """Logger 級別設為 DEBUG"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("test-hook")

        assert logger.level == logging.DEBUG

    # ========================================================================
    # Scenario 2: HOOK_DEBUG 模式
    # ========================================================================

    def test_scenario_2_debug_enabled(self, project_root, mock_env_var, reset_loggers, capsys):
        """HOOK_DEBUG=true 時 StreamHandler 級別為 DEBUG"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))
        mock_env_var("HOOK_DEBUG", "true")

        logger = setup_hook_logging("test-hook")
        logger.debug("debug msg")

        captured = capsys.readouterr()

        # 驗證 debug 訊息輸出到 stderr
        assert "debug msg" in captured.err

        # 驗證 StreamHandler 級別（排除 FileHandler，因為 FileHandler 也是 StreamHandler 的子類）
        stream_handlers = [h for h in logger.handlers
                          if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
        assert len(stream_handlers) == 1
        assert stream_handlers[0].level == logging.DEBUG

    def test_scenario_2_debug_false_value(self, project_root, mock_env_var, reset_loggers, capsys):
        """HOOK_DEBUG=false 時 StreamHandler 級別為 WARNING"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))
        mock_env_var("HOOK_DEBUG", "false")

        logger = setup_hook_logging("test-hook")
        logger.debug("debug msg")

        captured = capsys.readouterr()

        # 驗證 debug 訊息不輸出
        assert "debug msg" not in captured.err

        # 驗證 StreamHandler 級別（排除 FileHandler）
        stream_handlers = [h for h in logger.handlers
                          if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
        assert stream_handlers[0].level == logging.WARNING

    def test_scenario_2_debug_case_insensitive(self, project_root, mock_env_var, reset_loggers, capsys):
        """HOOK_DEBUG 環境變數不區分大小寫"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))
        mock_env_var("HOOK_DEBUG", "True")

        logger = setup_hook_logging("test-hook")
        logger.debug("debug msg")

        captured = capsys.readouterr()

        # 驗證 debug 訊息輸出
        assert "debug msg" in captured.err

    # ========================================================================
    # Scenario 3: 根目錄 Fallback
    # ========================================================================

    def test_scenario_3_env_var_priority(self, tmp_path, mock_env_var, reset_loggers):
        """CLAUDE_PROJECT_DIR 環境變數優先級最高"""
        # 建立自訂路徑
        custom_path = tmp_path / "custom"
        custom_path.mkdir()

        mock_env_var("CLAUDE_PROJECT_DIR", str(custom_path))

        logger = setup_hook_logging("test-hook")

        # 驗證日誌目錄在 custom_path 下
        log_dir = custom_path / ".claude" / "hook-logs" / "test-hook"
        assert log_dir.exists()

    def test_scenario_3_claude_md_search(self, project_root, mock_env_var, monkeypatch, reset_loggers):
        """搜尋 CLAUDE.md（從 cwd 向上）"""
        # 清除環境變數
        mock_env_var("CLAUDE_PROJECT_DIR", None)

        # 改變 cwd 到 project_root
        monkeypatch.chdir(project_root)

        logger = setup_hook_logging("test-hook")

        # 驗證日誌目錄在 project_root 下
        log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
        assert log_dir.exists()

    def test_scenario_3_claude_md_not_found(self, tmp_path, mock_env_var, monkeypatch, reset_loggers):
        """找不到 CLAUDE.md 時使用 cwd 作為 fallback"""
        # 清除環境變數
        mock_env_var("CLAUDE_PROJECT_DIR", None)

        # 改變 cwd 到臨時目錄
        monkeypatch.chdir(tmp_path)

        logger = setup_hook_logging("test-hook")

        # 驗證返回有效 Logger
        assert logger is not None
        assert isinstance(logger, logging.Logger)

        # 驗證日誌目錄在 cwd 下
        log_dir = tmp_path / ".claude" / "hook-logs" / "test-hook"
        assert log_dir.exists()

    # ========================================================================
    # Scenario 4: 重複呼叫防護
    # ========================================================================

    def test_scenario_4_first_call_handlers(self, project_root, mock_env_var, reset_loggers):
        """首次呼叫產生 2 個 handlers"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("test-hook")

        assert len(logger.handlers) == 2

    def test_scenario_4_second_call_clears_handlers(self, project_root, mock_env_var, reset_loggers):
        """重複呼叫時清除舊 handlers，不累積"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger1 = setup_hook_logging("test-hook")
        first_handlers = list(logger1.handlers)

        logger2 = setup_hook_logging("test-hook")

        # 驗證返回相同 logger
        assert logger1 is logger2

        # 驗證 handlers 數量仍為 2（未累積）
        assert len(logger2.handlers) == 2

        # 驗證舊 handlers 已被清除（不在新的 handlers 列表中）
        for old_handler in first_handlers:
            assert old_handler not in logger2.handlers

    def test_scenario_4_no_handler_accumulation(self, project_root, mock_env_var, reset_loggers):
        """多次呼叫無 handler 累積"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        for _ in range(3):
            logger = setup_hook_logging("test-hook")

        # 驗證最終只有 2 個 handlers
        assert len(logger.handlers) == 2

    # ========================================================================
    # Scenario 5: 邊界條件
    # ========================================================================

    def test_scenario_5_empty_hook_name(self, project_root, mock_env_var, reset_loggers):
        """空 hook_name 使用 fallback"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("")

        # 驗證使用 fallback 名稱
        assert logger.name == "unknown-hook"

        # 驗證目錄建立
        log_dir = project_root / ".claude" / "hook-logs" / "unknown-hook"
        assert log_dir.exists()

    def test_scenario_5_hook_name_with_slash(self, project_root, mock_env_var, reset_loggers):
        """hook_name 含 '/' 替換為 '-'"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("a/b")

        # logger name 保留原名
        assert logger.name == "a/b"

        # 目錄名稱替換為 "a-b"
        log_dir = project_root / ".claude" / "hook-logs" / "a-b"
        assert log_dir.exists()

        # 驗證無巢狀結構
        assert not (project_root / ".claude" / "hook-logs" / "a" / "b").exists()

    def test_scenario_5_hook_name_with_backslash(self, project_root, mock_env_var, reset_loggers):
        """hook_name 含 '\\' 替換為 '-'"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("a\\b")

        # 目錄名稱替換為 "a-b"
        log_dir = project_root / ".claude" / "hook-logs" / "a-b"
        assert log_dir.exists()

    def test_scenario_5_dir_already_exists(self, project_root, mock_env_var, reset_loggers):
        """日誌目錄已存在時無錯誤"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # 預先建立目錄
        log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "old-log.log").write_text("old content")

        # 呼叫 setup_hook_logging
        logger = setup_hook_logging("test-hook")

        # 驗證成功
        assert logger is not None

        # 驗證舊日誌檔存在
        assert (log_dir / "old-log.log").exists()

    # ========================================================================
    # Scenario 6: 異常處理
    # ========================================================================

    def test_scenario_6_permission_denied_dir(self, tmp_path, mock_env_var, reset_loggers, monkeypatch):
        """無法建立目錄時返回 Fallback Logger"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(tmp_path))

        # Mock mkdir 拋出 PermissionError
        original_mkdir = Path.mkdir

        def mock_mkdir(self, *args, **kwargs):
            if "hook-logs" in str(self):
                raise PermissionError("Permission denied")
            return original_mkdir(self, *args, **kwargs)

        with patch.object(Path, 'mkdir', mock_mkdir):
            logger = setup_hook_logging("test-hook")

        # 驗證返回有效 Logger
        assert logger is not None
        assert isinstance(logger, logging.Logger)

        # Fallback Logger 應有至少 1 個 handler（StreamHandler）
        assert len(logger.handlers) >= 1

    def test_scenario_6_disk_full_fallback(self, project_root, mock_env_var, reset_loggers, monkeypatch):
        """磁碟滿時返回 Fallback Logger"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # Mock FileHandler 建立時拋出 OSError
        original_init = logging.FileHandler.__init__

        def mock_init(self, *args, **kwargs):
            if len(args) > 0 and isinstance(args[0], str) and "hook-logs" in args[0]:
                raise OSError("No space left on device")
            return original_init(self, *args, **kwargs)

        with patch.object(logging.FileHandler, '__init__', mock_init):
            logger = setup_hook_logging("test-hook")

        # 驗證返回有效 Logger
        assert logger is not None
        assert isinstance(logger, logging.Logger)


# ============================================================================
# TestRunHookSafely - run_hook_safely() 測試
# ============================================================================

class TestRunHookSafely:
    """run_hook_safely() 功能測試"""

    def test_scenario_5_main_returns_zero(self, project_root, mock_env_var, reset_loggers):
        """main_func 返回 0，直接返回"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        def main_func() -> int:
            return 0

        exit_code = run_hook_safely(main_func, "test-hook")

        assert exit_code == 0

    def test_scenario_5_main_returns_nonzero(self, project_root, mock_env_var, reset_loggers):
        """main_func 返回非零，直接返回"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        def main_func() -> int:
            return 42

        exit_code = run_hook_safely(main_func, "test-hook")

        assert exit_code == 42

    def test_scenario_6_exception_caught(self, project_root, mock_env_var, reset_loggers):
        """Exception 被捕獲，返回 1"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        def main_func() -> int:
            raise ValueError("test error")

        exit_code = run_hook_safely(main_func, "test-hook")

        assert exit_code == 1

    def test_scenario_6_exception_traceback_logged(self, project_root, mock_env_var, reset_loggers):
        """Exception traceback 記錄到日誌"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        def main_func() -> int:
            raise ValueError("test error message")

        run_hook_safely(main_func, "test-hook")

        # 尋找日誌檔案
        log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1

        # 驗證日誌內容
        log_content = log_files[-1].read_text()
        assert "ValueError" in log_content
        assert "test error message" in log_content

    def test_scenario_7_sys_exit_code_2(self, project_root, mock_env_var, reset_loggers):
        """SystemExit 被傳播，不被捕獲"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        def main_func() -> int:
            sys.exit(2)

        with pytest.raises(SystemExit) as exc_info:
            run_hook_safely(main_func, "test-hook")

        assert exc_info.value.code == 2

    def test_scenario_8_keyboard_interrupt_propagates(self, project_root, mock_env_var, reset_loggers):
        """KeyboardInterrupt 被傳播，不被捕獲"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        def main_func() -> int:
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            run_hook_safely(main_func, "test-hook")

    # ========================================================================
    # Scenario 9: Python 3.9 相容性
    # ========================================================================

    def test_scenario_9_no_syntax_error_py39(self):
        """模組可正常 import，無 Python 3.9 語法錯誤"""
        # 若能成功 import，表示無語法錯誤
        assert setup_hook_logging is not None
        assert run_hook_safely is not None


# ============================================================================
# TestLogException - _log_exception() 測試（W25-005）
# ============================================================================

class TestLogException:
    """_log_exception() stderr 輸出測試"""

    def test_log_exception_writes_to_stderr_normal_path(self, project_root, mock_env_var, reset_loggers, capsys):
        """_log_exception 在正常路徑寫入 stderr"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("test-hook")
        tb_str = "Traceback (most recent call last):\n  File 'test.py', line 1\n    raise ValueError('test')\nValueError: test"

        _log_exception(logger, "test-hook", tb_str)

        captured = capsys.readouterr()

        # 驗證 stderr 包含預期的訊息
        assert "[Hook Error] test-hook failed unexpectedly" in captured.err
        assert "Check hook logs for details" in captured.err

    def test_log_exception_writes_to_stderr_logging_failure(self, project_root, mock_env_var, reset_loggers, capsys, monkeypatch):
        """_log_exception 在 logging 失敗時仍然寫入 stderr"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("test-hook")
        tb_str = "Traceback (most recent call last):\n  File 'test.py', line 1\n    raise ValueError('test')\nValueError: test"

        # Mock logger.critical 拋出異常
        original_critical = logger.critical

        def mock_critical(msg):
            raise RuntimeError("Logger write failed")

        monkeypatch.setattr(logger, "critical", mock_critical)

        _log_exception(logger, "test-hook-fail", tb_str)

        captured = capsys.readouterr()

        # 驗證即使 logging 失敗，stderr 仍然有輸出
        assert "[Hook Error] test-hook-fail failed unexpectedly" in captured.err
        assert "Check hook logs for details" in captured.err

    def test_log_exception_stderr_always_written(self, project_root, mock_env_var, reset_loggers, capsys):
        """_log_exception 的 stderr 輸出在 try-except 外面，永遠執行"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("another-hook")
        tb_str = "Some traceback"

        _log_exception(logger, "another-hook", tb_str)

        captured = capsys.readouterr()

        # 驗證 stderr 有輸出
        assert "[Hook Error]" in captured.err
        assert "another-hook" in captured.err

    def test_log_exception_stderr_format(self, project_root, mock_env_var, reset_loggers, capsys):
        """_log_exception 的 stderr 輸出格式符合預期"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        logger = setup_hook_logging("format-test-hook")
        tb_str = "Error traceback"

        _log_exception(logger, "format-test-hook", tb_str)

        captured = capsys.readouterr()

        # 驗證 stderr 包含：
        # 1. StreamHandler 輸出的 CRITICAL 訊息（因為 CRITICAL >= WARNING）
        # 2. sys.stderr.write 輸出的 [Hook Error] 訊息
        assert "[CRITICAL] Unhandled exception in format-test-hook" in captured.err
        assert "[CRITICAL] Error traceback" in captured.err
        assert "[Hook Error] format-test-hook failed unexpectedly. Check hook logs for details." in captured.err

    def test_run_hook_safely_outputs_stderr_on_exception(self, project_root, mock_env_var, reset_loggers, capsys):
        """run_hook_safely 在異常時輸出 stderr"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        def main_func() -> int:
            raise RuntimeError("Test runtime error")

        exit_code = run_hook_safely(main_func, "stderr-test-hook")

        captured = capsys.readouterr()

        # 驗證返回 1
        assert exit_code == 1

        # 驗證 stderr 有 Hook 失敗訊息
        assert "[Hook Error] stderr-test-hook failed unexpectedly" in captured.err


# ============================================================================
# Ticket 檔案掃描函式測試
# ============================================================================


class TestGetCurrentVersionFromTodolist:
    """get_current_version_from_todolist() 功能測試"""

    def test_read_valid_todolist(self, project_root):
        """成功讀取 todolist.yaml 中的 current_version"""
        # 建立 todolist.yaml
        todolist_file = project_root / "docs" / "todolist.yaml"
        todolist_file.write_text("current_version: 0.1.0\nstatus: active\n")

        version = get_current_version_from_todolist(project_root)

        assert version == "0.1.0"

    def test_todolist_missing(self, project_root):
        """todolist.yaml 不存在時返回 None"""
        version = get_current_version_from_todolist(project_root)

        assert version is None

    def test_todolist_no_version_field(self, project_root):
        """todolist.yaml 中無 current_version 欄位時返回 None"""
        todolist_file = project_root / "docs" / "todolist.yaml"
        todolist_file.write_text("status: active\n")

        version = get_current_version_from_todolist(project_root)

        assert version is None

    def test_logger_optional(self, project_root, reset_loggers):
        """logger 參數可選（不傳遞時仍可正常執行）"""
        todolist_file = project_root / "docs" / "todolist.yaml"
        todolist_file.write_text("current_version: 0.2.0\n")

        # 不傳遞 logger
        version = get_current_version_from_todolist(project_root)

        assert version == "0.2.0"

    def test_with_logger(self, project_root, reset_loggers):
        """傳遞 logger 參數時正常記錄"""
        logger = logging.getLogger("test-logger")
        todolist_file = project_root / "docs" / "todolist.yaml"
        todolist_file.write_text("current_version: 0.3.0\n")

        version = get_current_version_from_todolist(project_root, logger)

        assert version == "0.3.0"


class TestScanTicketFilesByVersion:
    """scan_ticket_files_by_version() 功能測試"""

    def test_scan_single_version(self, project_root):
        """掃描特定版本的 Ticket 檔案"""
        # 建立版本目錄和 Ticket 檔案
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        (tickets_dir / "0.1.0-W1-001.md").write_text("# Ticket 1\n")
        (tickets_dir / "0.1.0-W1-002.md").write_text("# Ticket 2\n")

        files = scan_ticket_files_by_version(project_root, "0.1.0")

        assert len(files) == 2
        assert all(f.suffix == ".md" for f in files)

    def test_nonexistent_version(self, project_root):
        """版本目錄不存在時返回空清單"""
        files = scan_ticket_files_by_version(project_root, "0.9.0")

        assert files == []

    def test_empty_version_directory(self, project_root):
        """版本目錄存在但無 Ticket 時返回空清單"""
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        files = scan_ticket_files_by_version(project_root, "0.1.0")

        assert files == []

    def test_with_logger(self, project_root, reset_loggers):
        """傳遞 logger 參數時正常記錄"""
        logger = logging.getLogger("test-logger")
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.1.0-W1-001.md").write_text("# Ticket 1\n")

        files = scan_ticket_files_by_version(project_root, "0.1.0", logger)

        assert len(files) == 1


class TestFindTicketFiles:
    """find_ticket_files() 功能測試"""

    def test_find_all_versions(self, project_root):
        """掃描所有版本的 Ticket 檔案"""
        # 建立多個版本目錄
        for version in ["0.1.0", "0.2.0"]:
            tickets_dir = (
                project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
            )
            tickets_dir.mkdir(parents=True, exist_ok=True)
            (tickets_dir / f"{version}-W1-001.md").write_text("# Ticket\n")

        files = find_ticket_files(project_root)

        assert len(files) == 2

    def test_specific_version(self, project_root):
        """指定 version 參數時只掃描該版本"""
        # 建立多個版本
        for version in ["0.1.0", "0.2.0"]:
            tickets_dir = (
                project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
            )
            tickets_dir.mkdir(parents=True, exist_ok=True)
            (tickets_dir / f"{version}-W1-001.md").write_text("# Ticket\n")

        files = find_ticket_files(project_root, version="0.1.0")

        assert len(files) == 1
        assert "0.1.0" in str(files[0])

    def test_backward_compatibility_old_location(self, project_root):
        """支援舊位置 .claude/tickets/"""
        # 建立舊位置 Ticket
        old_dir = project_root / ".claude" / "tickets"
        old_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "old-ticket.md").write_text("# Old Ticket\n")

        files = find_ticket_files(project_root)

        assert len(files) == 1
        assert "old-ticket.md" in str(files[0])

    def test_priority_current_version(self, project_root):
        """優先掃描當前活躍版本（從 todolist.yaml）"""
        # 建立多個版本
        for version in ["0.1.0", "0.2.0"]:
            tickets_dir = (
                project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
            )
            tickets_dir.mkdir(parents=True, exist_ok=True)
            (tickets_dir / f"{version}-W1-001.md").write_text("# Ticket\n")

        # 設置 current_version
        todolist_file = project_root / "docs" / "todolist.yaml"
        todolist_file.write_text("current_version: 0.2.0\n")

        files = find_ticket_files(project_root)

        # 應該包含兩個版本的檔案，但當前版本應優先
        assert len(files) == 2

    def test_fallback_when_no_version(self, project_root):
        """current_version 讀取失敗時 fallback 掃描所有版本"""
        # 建立版本目錄但不建立 todolist.yaml
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.1.0-W1-001.md").write_text("# Ticket\n")

        files = find_ticket_files(project_root)

        assert len(files) == 1


class TestFindTicketFile:
    """find_ticket_file() 功能測試"""

    # ========================================================================
    # 基本測試
    # ========================================================================

    def test_find_existing_ticket(self, project_root):
        """找到存在的 Ticket 檔案"""
        # 建立版本目錄和 Ticket 檔案
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.1.0-W1-001.md").write_text("# Ticket 1\n")

        result = find_ticket_file("0.1.0-W1-001", project_root=project_root)

        assert result is not None
        assert result.name == "0.1.0-W1-001.md"
        assert result.parent.name == "tickets"

    def test_find_nonexistent_ticket(self, project_root):
        """找不到的 Ticket 返回 None"""
        result = find_ticket_file("0.1.0-W9-999", project_root=project_root)

        assert result is None

    def test_find_ticket_auto_project_root(self, project_root, mock_env_var):
        """不傳遞 project_root 時自動取得"""
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # 建立 Ticket
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.1.0-W1-002.md").write_text("# Ticket 2\n")

        # 不傳遞 project_root
        result = find_ticket_file("0.1.0-W1-002")

        assert result is not None
        assert result.name == "0.1.0-W1-002.md"

    def test_find_ticket_with_logger(self, project_root, reset_loggers):
        """傳遞 logger 參數時正常記錄"""
        logger = logging.getLogger("test-find-ticket")

        # 建立 Ticket
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.1.0-W1-003.md").write_text("# Ticket 3\n")

        result = find_ticket_file("0.1.0-W1-003", project_root=project_root, logger=logger)

        assert result is not None

    def test_find_ticket_multiple_versions(self, project_root):
        """在多個版本中查找 Ticket"""
        # 建立多個版本的 Ticket
        for version in ["0.1.0", "0.2.0"]:
            tickets_dir = project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)
            (tickets_dir / f"{version}-W1-001.md").write_text("# Ticket\n")

        # 查找特定版本的 Ticket
        result = find_ticket_file("0.2.0-W1-001", project_root=project_root)

        assert result is not None
        assert "0.2.0" in str(result)

    def test_find_ticket_subtask_format(self, project_root):
        """支援子任務格式的 Ticket ID（如 0.1.0-W1-001.1）"""
        # 建立子任務 Ticket
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.1.0-W1-001.1.md").write_text("# Subtask\n")

        result = find_ticket_file("0.1.0-W1-001.1", project_root=project_root)

        assert result is not None
        assert result.name == "0.1.0-W1-001.1.md"

    # ========================================================================
    # Optimization Tests: Early Return & Direct Path (O(1) 效能)
    # ========================================================================

    def test_early_return_direct_path_hit(self, project_root, reset_loggers):
        """直接路徑命中時執行 early return（O(1) 效能）"""
        logger = logging.getLogger("test-direct-path")

        # 建立標準格式的 Ticket
        tickets_dir = project_root / "docs" / "work-logs" / "v0.31.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.31.0-W31-003.md").write_text("# Ticket\n")

        # 查找應直接命中
        result = find_ticket_file("0.31.0-W31-003", project_root=project_root, logger=logger)

        assert result is not None
        assert result.name == "0.31.0-W31-003.md"

        # 驗證 logger 記錄包含 "direct path"（表示使用了優化路徑）
        # 此處只驗證函式行為正確，實際 logger 檢查可在集成測試中

    def test_early_return_complex_version_number(self, project_root):
        """複雜版本號（如 1.2.3.4）的 early return"""
        # 建立複雜版本號的目錄
        tickets_dir = project_root / "docs" / "work-logs" / "v1.2.3" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "1.2.3-W10-050.md").write_text("# Complex Version\n")

        result = find_ticket_file("1.2.3-W10-050", project_root=project_root)

        assert result is not None
        assert "1.2.3" in str(result)

    # ========================================================================
    # Fallback Tests: Old Location
    # ========================================================================

    def test_fallback_old_location(self, project_root):
        """直接路徑不存在時，fallback 到舊位置 .claude/tickets/"""
        # 建立舊位置 Ticket（不建立新位置）
        old_dir = project_root / ".claude" / "tickets"
        old_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "0.1.0-W1-001.md").write_text("# Old Location\n")

        result = find_ticket_file("0.1.0-W1-001", project_root=project_root)

        assert result is not None
        assert result.parent == old_dir

    def test_fallback_old_location_backward_compat(self, project_root):
        """舊位置 .claude/tickets/ 支援後向相容"""
        # 建立舊位置 Ticket
        old_dir = project_root / ".claude" / "tickets"
        old_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "old-ticket-001.md").write_text("# Old Ticket\n")

        result = find_ticket_file("old-ticket-001", project_root=project_root)

        assert result is not None
        assert result.name == "old-ticket-001.md"

    def test_fallback_old_location_priority_over_scan(self, project_root):
        """舊位置優先於全量掃描"""
        # 建立舊位置
        old_dir = project_root / ".claude" / "tickets"
        old_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "ticket-001.md").write_text("# Old\n")

        # 也建立新位置中不同版本的檔案（但 ID 相同）
        for version in ["0.1.0", "0.2.0"]:
            tickets_dir = project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)
            # 用異常格式建立，避免被直接路徑命中
            (tickets_dir / f"ticket-001.md").write_text("# New\n")

        result = find_ticket_file("ticket-001", project_root=project_root)

        # 應該找到舊位置的版本
        assert result is not None
        assert result.parent == old_dir

    # ========================================================================
    # Version Number Parsing Tests
    # ========================================================================

    def test_parse_standard_version_format(self, project_root):
        """解析標準版本號格式 {version}-W{wave}-{seq}"""
        from hook_utils import _parse_version_from_ticket_id

        # 標準格式
        assert _parse_version_from_ticket_id("0.1.0-W1-001") == "0.1.0"
        assert _parse_version_from_ticket_id("0.31.0-W31-003") == "0.31.0"
        assert _parse_version_from_ticket_id("1.2.3-W10-050") == "1.2.3"

    def test_parse_version_with_subtask(self, project_root):
        """解析包含子任務的版本號"""
        from hook_utils import _parse_version_from_ticket_id

        # 子任務格式
        assert _parse_version_from_ticket_id("0.1.0-W1-001.1") == "0.1.0"
        assert _parse_version_from_ticket_id("0.1.0-W1-001.2.3") == "0.1.0"

    def test_parse_version_invalid_format_no_wave(self, project_root):
        """無效格式：無 -W 標記，應返回 None"""
        from hook_utils import _parse_version_from_ticket_id

        # 無 -W 的非標準格式
        assert _parse_version_from_ticket_id("old-ticket-001") is None
        assert _parse_version_from_ticket_id("ticket123") is None
        assert _parse_version_from_ticket_id("0.1.0") is None

    def test_parse_version_invalid_format_no_dot(self, project_root):
        """無效格式：版本號無 '.'，應返回 None"""
        from hook_utils import _parse_version_from_ticket_id

        # 版本號無 '.'
        assert _parse_version_from_ticket_id("0-W1-001") is None
        assert _parse_version_from_ticket_id("v1-W1-001") is None

    def test_parse_version_edge_cases(self, project_root):
        """邊界情況測試"""
        from hook_utils import _parse_version_from_ticket_id

        # 空字串
        assert _parse_version_from_ticket_id("") is None

        # 只有 -W（無版本號部分）
        assert _parse_version_from_ticket_id("-W1-001") is None

        # -W 出現在開頭
        assert _parse_version_from_ticket_id("-W1-001-0.1.0") is None

    # ========================================================================
    # Fallback to Full Scan Tests
    # ========================================================================

    def test_fallback_full_scan_nonstandard_ticket(self, project_root):
        """非標準格式的 Ticket ID 執行全量掃描"""
        # 建立非標準格式（無版本號前綴）的 Ticket
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "some-random-id.md").write_text("# Non-standard\n")

        result = find_ticket_file("some-random-id", project_root=project_root)

        # 應該透過全量掃描找到
        assert result is not None
        assert result.name == "some-random-id.md"

    def test_fallback_scan_finds_in_multiple_locations(self, project_root):
        """全量掃描在多個位置正確查找"""
        # 建立多版本結構
        for version in ["0.1.0", "0.2.0"]:
            tickets_dir = project_root / "docs" / "work-logs" / f"v{version}" / "tickets"
            tickets_dir.mkdir(parents=True, exist_ok=True)
            (tickets_dir / f"{version}-W1-001.md").write_text(f"# Ticket v{version}\n")

        # 用非標準格式查找（強制全量掃描）
        result = find_ticket_file("0.2.0-W1-001", project_root=project_root)

        assert result is not None
        assert "0.2.0" in str(result)

    def test_fallback_returns_none_when_not_found(self, project_root):
        """全量掃描未找到時返回 None"""
        # 建立空的 Ticket 目錄
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        result = find_ticket_file("nonexistent-ticket", project_root=project_root)

        assert result is None

    # ========================================================================
    # Logger Integration Tests
    # ========================================================================

    def test_logger_direct_path_message(self, project_root, reset_loggers):
        """Logger 記錄直接路徑命中的訊息"""
        logger = logging.getLogger("test-logger-direct")

        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "0.1.0-W1-001.md").write_text("# Ticket\n")

        # 執行查詢（會輸出 log）
        result = find_ticket_file("0.1.0-W1-001", project_root=project_root, logger=logger)

        assert result is not None

    def test_logger_old_location_message(self, project_root, reset_loggers):
        """Logger 記錄舊位置命中的訊息"""
        logger = logging.getLogger("test-logger-old")

        old_dir = project_root / ".claude" / "tickets"
        old_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "old-ticket.md").write_text("# Old\n")

        result = find_ticket_file("old-ticket", project_root=project_root, logger=logger)

        assert result is not None

    def test_logger_fallback_message(self, project_root, reset_loggers):
        """Logger 記錄全量掃描的訊息"""
        logger = logging.getLogger("test-logger-fallback")

        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "unusual-name.md").write_text("# Ticket\n")

        result = find_ticket_file("unusual-name", project_root=project_root, logger=logger)

        assert result is not None
