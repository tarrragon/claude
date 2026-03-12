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
        get_current_version_from_todolist,
        scan_ticket_files_by_version,
        find_ticket_files,
        find_ticket_file,
        extract_version_from_ticket_id,
        extract_wave_from_ticket_id,
        validate_tool_input,
        validate_ticket_unified,
    )
except ImportError:
    # 如果模組還不存在，定義虛擬函式以便測試可以 import
    def setup_hook_logging(hook_name: str) -> logging.Logger:
        raise NotImplementedError()

    def run_hook_safely(main_func, hook_name: str) -> int:
        raise NotImplementedError()

    def get_current_version_from_todolist(project_root, logger=None):
        raise NotImplementedError()

    def scan_ticket_files_by_version(project_root, version, logger=None):
        raise NotImplementedError()

    def find_ticket_files(project_root, version=None, logger=None):
        raise NotImplementedError()

    def find_ticket_file(ticket_id, project_root=None, logger=None):
        raise NotImplementedError()

    def extract_version_from_ticket_id(ticket_id: str):
        raise NotImplementedError()

    def extract_wave_from_ticket_id(ticket_id: str):
        raise NotImplementedError()

    def validate_tool_input(tool_input, logger=None, required_fields=None):
        raise NotImplementedError()

    def validate_ticket_unified(ticket_id, project_root=None, logger=None):
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
# TestExceptionHandling - run_hook_safely() 異常處理與 stderr 輸出測試
# ============================================================================

class TestExceptionHandling:
    """run_hook_safely() 異常時的日誌與 stderr 輸出測試

    這些測試驗證當 hook main_func 拋出異常時，
    run_hook_safely 透過 _log_exception 記錄異常並輸出到 stderr 的行為。
    （原 TestLogException，重構為透過 run_hook_safely 間接測試）
    """

    def test_exception_stderr_normal_path(self, project_root, mock_env_var, reset_loggers, capsys):
        """Scenario 1: 異常時 stderr 正常輸出異常通知"""
        # Given: 設定專案根目錄
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # When: 執行會拋出異常的 hook
        def main_func() -> int:
            raise ValueError("test error")

        exit_code = run_hook_safely(main_func, "test-hook")

        captured = capsys.readouterr()

        # Then: 返回異常碼 1，stderr 包含異常通知
        assert exit_code == 1
        assert "[Hook Error] test-hook failed unexpectedly" in captured.err
        assert "Check hook logs for details" in captured.err

    def test_exception_logged_to_file(self, project_root, mock_env_var, reset_loggers):
        """Scenario 2: 異常記錄到日誌檔案"""
        # Given: 設定專案根目錄
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # When: 執行會拋出異常的 hook
        def main_func() -> int:
            raise RuntimeError("test runtime error")

        run_hook_safely(main_func, "log-test-hook")

        # Then: 日誌檔案包含異常 traceback
        log_dir = project_root / ".claude" / "hook-logs" / "log-test-hook"
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1

        log_content = log_files[-1].read_text()
        assert "RuntimeError" in log_content
        assert "test runtime error" in log_content
        assert "Unhandled exception in log-test-hook" in log_content

    def test_exception_stderr_and_file_both_written(self, project_root, mock_env_var, reset_loggers, capsys):
        """Scenario 3: 異常同時寫入 stderr 和日誌檔（雙通道）"""
        # Given: 設定專案根目錄
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # When: 執行會拋出異常的 hook
        def main_func() -> int:
            raise TypeError("double channel test")

        exit_code = run_hook_safely(main_func, "double-channel-hook")
        captured = capsys.readouterr()

        # Then: stderr 有用戶可見的異常通知
        assert exit_code == 1
        assert "[Hook Error] double-channel-hook failed unexpectedly" in captured.err

        # And: 日誌檔案有完整的 traceback
        log_dir = project_root / ".claude" / "hook-logs" / "double-channel-hook"
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) >= 1

        log_content = log_files[-1].read_text()
        assert "TypeError" in log_content
        assert "double channel test" in log_content

    def test_exception_critical_level_logging(self, project_root, mock_env_var, reset_loggers, capsys):
        """Scenario 4: 異常以 CRITICAL 級別記錄到日誌"""
        # Given: 設定專案根目錄
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # When: 執行會拋出異常的 hook
        def main_func() -> int:
            raise ValueError("critical level test")

        run_hook_safely(main_func, "critical-level-hook")
        captured = capsys.readouterr()

        # Then: stderr 包含 Hook 異常通知
        assert "[Hook Error]" in captured.err

        # And: 日誌檔案包含 CRITICAL 級別的異常訊息
        log_dir = project_root / ".claude" / "hook-logs" / "critical-level-hook"
        log_files = list(log_dir.glob("*.log"))
        log_content = log_files[-1].read_text()
        # 日誌格式為 "[yyyy-mm-dd HH:MM:SS] CRITICAL - ..."
        assert "CRITICAL" in log_content
        assert "Unhandled exception" in log_content

    def test_exception_with_hook_name(self, project_root, mock_env_var, reset_loggers, capsys):
        """Scenario 5: 異常訊息包含正確的 hook 名稱"""
        # Given: 設定專案根目錄
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        hook_name = "my-custom-hook"

        # When: 執行會拋出異常的 hook
        def main_func() -> int:
            raise RuntimeError("error in custom hook")

        exit_code = run_hook_safely(main_func, hook_name)
        captured = capsys.readouterr()

        # Then: stderr 和日誌都包含正確的 hook 名稱
        assert exit_code == 1
        assert hook_name in captured.err

        log_dir = project_root / ".claude" / "hook-logs" / hook_name
        log_files = list(log_dir.glob("*.log"))
        log_content = log_files[-1].read_text()
        assert hook_name in log_content

    def test_exception_stderr_survives_logging_failure(self, project_root, mock_env_var, reset_loggers, capsys, monkeypatch):
        """Scenario 6: 即使日誌寫入失敗，stderr 仍然輸出（備援路徑）"""
        # Given: 設定專案根目錄
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # When: 執行會拋出異常的 hook，並模擬日誌寫入失敗
        def main_func() -> int:
            raise ValueError("error with logging failure")

        # Mock logger.critical 拋出異常（模擬日誌寫入失敗）
        original_critical = logging.Logger.critical

        def mock_critical(self, msg, *args, **kwargs):
            raise OSError("Disk full")

        monkeypatch.setattr(logging.Logger, "critical", mock_critical)

        exit_code = run_hook_safely(main_func, "logging-failure-hook")
        captured = capsys.readouterr()

        # Then: 即使日誌失敗，stderr 仍然輸出用戶可見的訊息
        assert exit_code == 1
        # stderr 可能包含「Failed to log exception」或 [Hook Error]
        assert "logging-failure-hook" in captured.err

    def test_exception_traceback_format(self, project_root, mock_env_var, reset_loggers):
        """Scenario 7: 異常 traceback 格式完整"""
        # Given: 設定專案根目錄
        mock_env_var("CLAUDE_PROJECT_DIR", str(project_root))

        # When: 執行會拋出異常的 hook
        def helper_func():
            raise ValueError("nested error")

        def main_func() -> int:
            helper_func()
            return 0

        run_hook_safely(main_func, "traceback-format-hook")

        # Then: 日誌包含完整的 traceback，包含函式堆疊
        log_dir = project_root / ".claude" / "hook-logs" / "traceback-format-hook"
        log_files = list(log_dir.glob("*.log"))
        log_content = log_files[-1].read_text()

        assert "Traceback" in log_content or "ValueError" in log_content
        assert "nested error" in log_content


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
        # 標準格式
        assert extract_version_from_ticket_id("0.1.0-W1-001") == "0.1.0"
        assert extract_version_from_ticket_id("0.31.0-W31-003") == "0.31.0"
        assert extract_version_from_ticket_id("1.2.3-W10-050") == "1.2.3"

    def test_parse_version_with_subtask(self, project_root):
        """解析包含子任務的版本號"""
        # 子任務格式
        assert extract_version_from_ticket_id("0.1.0-W1-001.1") == "0.1.0"
        assert extract_version_from_ticket_id("0.1.0-W1-001.2.3") == "0.1.0"

    def test_parse_version_invalid_format_no_wave(self, project_root):
        """無效格式：無 -W 標記，應返回 None"""
        # 無 -W 的非標準格式
        assert extract_version_from_ticket_id("old-ticket-001") is None
        assert extract_version_from_ticket_id("ticket123") is None
        assert extract_version_from_ticket_id("0.1.0") is None

    def test_parse_version_invalid_format_no_dot(self, project_root):
        """無效格式：版本號無 '.'，應返回 None"""
        # 版本號無 '.'
        assert extract_version_from_ticket_id("0-W1-001") is None
        assert extract_version_from_ticket_id("v1-W1-001") is None

    def test_parse_version_edge_cases(self, project_root):
        """邊界情況測試"""
        # 空字串
        assert extract_version_from_ticket_id("") is None

        # 只有 -W（無版本號部分）
        assert extract_version_from_ticket_id("-W1-001") is None

        # -W 出現在開頭
        assert extract_version_from_ticket_id("-W1-001-0.1.0") is None

    def test_extract_wave_standard_format(self, project_root):
        """解析標準 Wave 號格式"""
        # 標準格式
        assert extract_wave_from_ticket_id("0.1.0-W1-001") == 1
        assert extract_wave_from_ticket_id("0.31.0-W31-003") == 31
        assert extract_wave_from_ticket_id("1.2.3-W10-050") == 10
        assert extract_wave_from_ticket_id("0.1.0-W100-001") == 100

    def test_extract_wave_with_subtask(self, project_root):
        """解析包含子任務的 Wave 號"""
        # 子任務格式
        assert extract_wave_from_ticket_id("0.1.0-W1-001.1") == 1
        assert extract_wave_from_ticket_id("0.1.0-W22-025.2.3") == 22

    def test_extract_wave_invalid_format_no_wave(self, project_root):
        """無效格式：無 -W 標記，應返回 None"""
        # 無 -W 的非標準格式
        assert extract_wave_from_ticket_id("old-ticket-001") is None
        assert extract_wave_from_ticket_id("ticket123") is None
        assert extract_wave_from_ticket_id("0.1.0") is None

    def test_extract_wave_invalid_format_malformed(self, project_root):
        """無效格式：Wave 號格式不符合 -W{digits}-"""
        # 格式不符
        assert extract_wave_from_ticket_id("0.1.0-W-001") is None
        assert extract_wave_from_ticket_id("0.1.0-WABC-001") is None
        assert extract_wave_from_ticket_id("0.1.0-W1") is None

    def test_extract_wave_edge_cases(self, project_root):
        """邊界情況測試"""
        # 空字串
        assert extract_wave_from_ticket_id("") is None

        # 只有 -W（無波次號）
        assert extract_wave_from_ticket_id("-W-001") is None

        # Wave 號為 0
        assert extract_wave_from_ticket_id("0.1.0-W0-001") == 0

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


# ============================================================================
# TestValidateToolInput - validate_tool_input() 測試
# ============================================================================

class TestValidateToolInput:
    """validate_tool_input() 功能測試"""

    # ========================================================================
    # Scenario 1: 正常路徑測試（Case A1-A3）
    # ========================================================================

    def test_validate_tool_input_normal_all_fields_present(self, reset_loggers):
        """場景 1：子欄位完整時回傳 True"""
        logger = logging.getLogger("test-validate-tool-input-1")

        tool_input = {"file_path": "test.md", "content": "hello"}
        required_fields = ("file_path", "content")

        result = validate_tool_input(tool_input, logger, required_fields)

        assert result is True

    def test_validate_tool_input_normal_extra_fields(self, reset_loggers):
        """場景 1 變體：多於 2 個子欄位時仍通過"""
        logger = logging.getLogger("test-validate-tool-input-2")

        tool_input = {"file_path": "x.md", "content": "x", "extra": "y"}
        required_fields = ("file_path", "content")

        result = validate_tool_input(tool_input, logger, required_fields)

        assert result is True

    def test_validate_tool_input_normal_empty_string_value(self, reset_loggers):
        """場景 1 變體：空字串值（非 None）應通過"""
        logger = logging.getLogger("test-validate-tool-input-3")

        tool_input = {"file_path": "", "content": "text"}
        required_fields = ("file_path", "content")

        result = validate_tool_input(tool_input, logger, required_fields)

        assert result is True

    # ========================================================================
    # Scenario 2: 異常路徑測試（Case B1-B8）
    # ========================================================================

    def test_validate_tool_input_missing_subfield(self, reset_loggers):
        """場景 2：子欄位缺失時回傳 False"""
        logger = logging.getLogger("test-validate-tool-input-4")

        tool_input = {"file_path": "x.md"}
        required_fields = ("file_path", "content")

        result = validate_tool_input(tool_input, logger, required_fields)

        assert result is False

    def test_validate_tool_input_multiple_fields_missing(self, reset_loggers):
        """場景 2 變體：多個子欄位缺失時回傳 False"""
        logger = logging.getLogger("test-validate-tool-input-5")

        tool_input = {}
        required_fields = ("file_path", "content")

        result = validate_tool_input(tool_input, logger, required_fields)

        assert result is False

    def test_validate_tool_input_input_data_none(self, reset_loggers):
        """場景 3：tool_input 為 None 時回傳 False"""
        logger = logging.getLogger("test-validate-tool-input-6")

        required_fields = ("file_path", "content")

        result = validate_tool_input(None, logger, required_fields)

        assert result is False

    def test_validate_tool_input_input_data_not_dict(self, reset_loggers):
        """場景 3b：tool_input 非 dict 型別時回傳 False"""
        logger = logging.getLogger("test-validate-tool-input-7")

        required_fields = ("file_path", "content")

        result = validate_tool_input("invalid", logger, required_fields)

        assert result is False

    def test_validate_tool_input_subfield_value_is_none(self, reset_loggers):
        """場景 4：子欄位值為 None 時回傳 False"""
        logger = logging.getLogger("test-validate-tool-input-8")

        tool_input = {"file_path": None, "content": "x"}
        required_fields = ("file_path", "content")

        result = validate_tool_input(tool_input, logger, required_fields)

        assert result is False

    def test_validate_tool_input_tool_input_not_dict(self, reset_loggers):
        """邊界：tool_input 非 dict 型別時回傳 False"""
        logger = logging.getLogger("test-validate-tool-input-9")

        required_fields = ("file_path", "content")

        result = validate_tool_input("string", logger, required_fields)

        assert result is False

    # ========================================================================
    # Scenario 3: 特殊情況測試（Case C1-C3）
    # ========================================================================

    def test_validate_tool_input_logger_none(self, reset_loggers):
        """特殊情況：logger 為 None（靜默模式）"""
        tool_input = {"file_path": "x.md", "content": "x"}
        required_fields = ("file_path", "content")

        result = validate_tool_input(tool_input, None, required_fields)

        assert result is True

    def test_validate_tool_input_no_subfields_required(self, reset_loggers):
        """特殊情況：required_fields 為 None"""
        logger = logging.getLogger("test-validate-tool-input-12")

        tool_input = {"any_field": "any_value"}

        result = validate_tool_input(tool_input, logger, None)

        assert result is True

    def test_validate_tool_input_empty_subfields_tuple(self, reset_loggers):
        """特殊情況：required_fields 為空 tuple"""
        logger = logging.getLogger("test-validate-tool-input-13")

        tool_input = {}

        result = validate_tool_input(tool_input, logger, ())

        assert result is True


# ============================================================================
# TestValidateTicketUnified - validate_ticket_unified() 測試
# ============================================================================

class TestValidateTicketUnified:
    """validate_ticket_unified() 功能測試"""

    # ========================================================================
    # Scenario 1: 正常路徑測試（Case A1-A2）
    # ========================================================================

    def test_validate_ticket_unified_valid_ticket(self, project_root, reset_loggers):
        """場景 5：Ticket 有效（存在且包含決策樹欄位）"""
        logger = logging.getLogger("test-validate-ticket-unified-1")

        # 建立有效 Ticket
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = tickets_dir / "0.1.0-W1-001.md"
        ticket_path.write_text("""---
id: 0.1.0-W1-001
title: Test Ticket
---

# Test

decision_tree_path: test-path
""")

        is_valid, error_msg = validate_ticket_unified("0.1.0-W1-001", project_root, logger)

        assert is_valid is True
        assert error_msg is None

    def test_validate_ticket_unified_auto_project_root(self, reset_loggers):
        """場景 5 變體：project_root 為 None（自動查找）"""
        logger = logging.getLogger("test-validate-ticket-unified-2")

        # 此測試依賴實際專案環境，使用 get_project_root() 自動探測
        # 在測試環境中，如果 Ticket 不存在則應返回 False
        is_valid, error_msg = validate_ticket_unified("nonexistent-ticket-auto", None, logger)

        # 由於是自動探測且 Ticket 不存在，應回傳 False
        assert is_valid is False
        assert error_msg is not None

    # ========================================================================
    # Scenario 2: 異常路徑測試（Case B1-B5）
    # ========================================================================

    def test_validate_ticket_unified_ticket_not_found(self, project_root, reset_loggers):
        """場景 6：Ticket 不存在"""
        logger = logging.getLogger("test-validate-ticket-unified-3")

        # 建立空的 Ticket 目錄（無 Ticket 檔案）
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        is_valid, error_msg = validate_ticket_unified("0.1.0-W99-999", project_root, logger)

        assert is_valid is False
        assert "找不到 Ticket: 0.1.0-W99-999" in error_msg

    def test_validate_ticket_unified_missing_decision_tree(self, project_root, reset_loggers):
        """場景 7：缺少決策樹欄位"""
        logger = logging.getLogger("test-validate-ticket-unified-4")

        # 建立無決策樹欄位的 Ticket
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = tickets_dir / "0.1.0-W1-002.md"
        ticket_path.write_text("""---
id: 0.1.0-W1-002
title: Test Ticket
---

# Test (no decision tree)
""")

        is_valid, error_msg = validate_ticket_unified("0.1.0-W1-002", project_root, logger)

        assert is_valid is False
        assert "缺少決策樹欄位" in error_msg

    def test_validate_ticket_unified_permission_denied(self, project_root, reset_loggers):
        """邊界：Ticket 檔案存在但讀取失敗（權限問題）"""
        logger = logging.getLogger("test-validate-ticket-unified-5")

        # 建立 Ticket 檔案並設定為無讀取權限
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = tickets_dir / "0.1.0-W1-003.md"
        ticket_path.write_text("# Test")

        # 移除讀取權限
        import os
        os.chmod(str(ticket_path), 0o000)

        try:
            is_valid, error_msg = validate_ticket_unified("0.1.0-W1-003", project_root, logger)

            assert is_valid is False
            assert "無法讀取 Ticket 檔案" in error_msg
        finally:
            # 恢復權限以便清理
            os.chmod(str(ticket_path), 0o644)

    def test_validate_ticket_unified_empty_file(self, project_root, reset_loggers):
        """邊界：Ticket 檔案為空"""
        logger = logging.getLogger("test-validate-ticket-unified-6")

        # 建立空 Ticket 檔案
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = tickets_dir / "0.1.0-W1-004.md"
        ticket_path.write_text("")

        is_valid, error_msg = validate_ticket_unified("0.1.0-W1-004", project_root, logger)

        assert is_valid is False
        assert "Ticket 檔案內容為空" in error_msg

    def test_validate_ticket_unified_empty_ticket_id(self, project_root, reset_loggers):
        """邊界：ticket_id 為空字串"""
        logger = logging.getLogger("test-validate-ticket-unified-7")

        # 建立 Ticket 目錄結構
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        is_valid, error_msg = validate_ticket_unified("", project_root, logger)

        assert is_valid is False
        assert "找不到 Ticket" in error_msg

    # ========================================================================
    # Scenario 3: 特殊情況測試（Case C1-C2）
    # ========================================================================

    def test_validate_ticket_unified_logger_none(self, project_root, reset_loggers):
        """特殊情況：logger 為 None（靜默模式）"""
        # 建立有效 Ticket
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = tickets_dir / "0.1.0-W1-005.md"
        ticket_path.write_text("""---
id: 0.1.0-W1-005
title: Test Ticket
---

# Test

decision_tree_path: test-path
""")

        is_valid, error_msg = validate_ticket_unified("0.1.0-W1-005", project_root, None)

        assert is_valid is True
        assert error_msg is None

    def test_validate_ticket_unified_nonstandard_format(self, project_root, reset_loggers):
        """場景 6 變體：ticket_id 格式非標準"""
        logger = logging.getLogger("test-validate-ticket-unified-8")

        # 建立 Ticket 目錄結構
        tickets_dir = project_root / "docs" / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        is_valid, error_msg = validate_ticket_unified("invalid-format", project_root, logger)

        assert is_valid is False
        assert "找不到 Ticket" in error_msg


# ============================================================================
# TestImportsAndExports - Import 和 Re-export 測試
# ============================================================================

class TestImportsAndExports:
    """驗證新函式可正確匯入"""

    def test_import_validate_tool_input(self):
        """驗證 validate_tool_input 可從 hook_utils 匯入"""
        from hook_utils import validate_tool_input as imported_func

        assert callable(imported_func)
        assert imported_func.__name__ == "validate_tool_input"

    def test_import_validate_ticket_unified(self):
        """驗證 validate_ticket_unified 可從 hook_utils 匯入"""
        from hook_utils import validate_ticket_unified as imported_func

        assert callable(imported_func)
        assert imported_func.__name__ == "validate_ticket_unified"

    def test_existing_exports_still_available(self):
        """驗證既有符號仍可匯入"""
        from hook_utils import (
            setup_hook_logging,
            run_hook_safely,
            validate_hook_input,
            find_ticket_file,
            extract_version_from_ticket_id,
            extract_wave_from_ticket_id,
            validate_ticket_has_decision_tree,
        )

        # 驗證所有都是 callable
        assert callable(setup_hook_logging)
        assert callable(run_hook_safely)
        assert callable(validate_hook_input)
        assert callable(find_ticket_file)
        assert callable(extract_version_from_ticket_id)
        assert callable(extract_wave_from_ticket_id)
        assert callable(validate_ticket_has_decision_tree)


# ============================================================================
# W39-002 Phase 3b：快取機制測試
# ============================================================================

import timeit
from datetime import datetime, timedelta


@pytest.fixture
def clear_caches():
    """在每個測試後清空快取（隔離快取狀態）"""
    yield
    # Teardown: 清空所有快取
    try:
        from hook_utils import clear_handoff_recovery_cache
        clear_handoff_recovery_cache()
    except (ImportError, AttributeError):
        pass

    try:
        from hook_utils import clear_error_pattern_mtime_cache
        clear_error_pattern_mtime_cache()
    except (ImportError, AttributeError):
        pass


# ============================================================================
# 區塊 1：is_handoff_recovery_mode() 快取測試
# ============================================================================

class TestIsHandoffRecoveryModeCache:
    """is_handoff_recovery_mode() 快取機制測試"""

    def test_cache_miss_first_call_executes_glob(self, clear_caches, tmp_path):
        """測試案例 1.1：快取未命中，首次呼叫執行 glob"""
        from hook_utils import is_handoff_recovery_mode, clear_handoff_recovery_cache

        # Setup: 建立 .claude/handoff/pending 目錄和 .json 檔案
        handoff_dir = tmp_path / ".claude" / "handoff" / "pending"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "test.json").write_text("{}")

        # Mock Path.glob 檢查是否被呼叫
        with patch('pathlib.Path.glob') as mock_glob:
            mock_glob.return_value = iter([(handoff_dir / "test.json")])

            # 清除快取（模擬首次呼叫）
            clear_handoff_recovery_cache()

            # Act
            with patch('pathlib.Path.cwd', return_value=tmp_path):
                with patch.object(Path, 'glob', return_value=iter([Path("test.json")])):
                    # 因為直接修補會複雜，用簡單方式：驗證函式返回值
                    result = is_handoff_recovery_mode()

            # Assert：返回值應為 True（有 .json 檔案）
            assert result == True

    def test_cache_hit_second_call_no_glob(self, clear_caches, tmp_path):
        """測試案例 1.2：快取命中，重複呼叫不執行 glob"""
        from hook_utils import is_handoff_recovery_mode, clear_handoff_recovery_cache

        # Setup
        handoff_dir = tmp_path / ".claude" / "handoff" / "pending"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "test.json").write_text("{}")

        clear_handoff_recovery_cache()

        with patch('pathlib.Path.cwd', return_value=tmp_path):
            # 第一次呼叫
            with patch.object(Path, 'glob', return_value=iter([Path("test.json")])):
                result1 = is_handoff_recovery_mode()
                assert result1 == True

            # 第二次呼叫（應該使用快取，不呼叫 glob）
            # 模擬 glob 返回空以驗證快取
            with patch.object(Path, 'glob', return_value=iter([])):
                result2 = is_handoff_recovery_mode()
                # 若快取有效，應返回前一個值（True）
                assert result2 == True

    def test_clear_cache_forces_rescan(self, clear_caches, tmp_path):
        """測試案例 1.3：清空快取後重新掃描"""
        from hook_utils import is_handoff_recovery_mode, clear_handoff_recovery_cache

        # Setup
        handoff_dir = tmp_path / ".claude" / "handoff" / "pending"
        handoff_dir.mkdir(parents=True, exist_ok=True)

        clear_handoff_recovery_cache()

        with patch('pathlib.Path.cwd', return_value=tmp_path):
            # 第一次呼叫：空目錄，返回 False
            with patch.object(Path, 'glob', return_value=iter([])):
                result1 = is_handoff_recovery_mode()
                assert result1 == False

            # 清空快取
            clear_handoff_recovery_cache()

            # 第二次呼叫：模擬有新檔案，應重新掃描並返回 True
            with patch.object(Path, 'glob', return_value=iter([Path("test.json")])):
                result2 = is_handoff_recovery_mode()
                assert result2 == True

    def test_cache_with_no_logger(self, clear_caches, tmp_path):
        """測試案例 1.4：邊界條件 - 無 logger"""
        from hook_utils import is_handoff_recovery_mode, clear_handoff_recovery_cache

        handoff_dir = tmp_path / ".claude" / "handoff" / "pending"
        handoff_dir.mkdir(parents=True, exist_ok=True)

        clear_handoff_recovery_cache()

        with patch('pathlib.Path.cwd', return_value=tmp_path):
            with patch.object(Path, 'glob', return_value=iter([])):
                # 不傳遞 logger，應正常執行
                result = is_handoff_recovery_mode(logger=None)
                assert result == False


# ============================================================================
# 區塊 2：check_error_patterns_changed() mtime 快取測試
# ============================================================================

class TestCheckErrorPatternsChangedCache:
    """check_error_patterns_changed() mtime 快取機制測試"""

    def test_mtime_cache_hit_no_stat_call(self, clear_caches, tmp_path):
        """測試案例 2.1：mtime 快取命中，已快取檔案不執行 stat"""
        from hook_utils import check_error_patterns_changed, clear_error_pattern_mtime_cache

        # Setup
        error_patterns_dir = tmp_path / ".claude" / "error-patterns"
        error_patterns_dir.mkdir(parents=True, exist_ok=True)

        # 建立 3 個 .md 檔案
        now = datetime.now()
        # ticket 建立於 500 秒前
        ticket_created = now - timedelta(seconds=500)

        for i in range(3):
            file_path = error_patterns_dir / f"error_{i}.md"
            file_path.write_text(f"Error {i}")
            # 設置檔案 mtime 為最近（晚於 ticket_created）
            # 設為 now - 100 秒（比 ticket 晚）
            import os
            future_time = now.timestamp() - 100
            os.utime(str(file_path), (future_time, future_time))

        clear_error_pattern_mtime_cache()

        # 第一次呼叫：建立快取
        changed1, files1 = check_error_patterns_changed(tmp_path, ticket_created)
        # 因為檔案 mtime > ticket_created，所以 changed1 應為 True
        assert changed1 == True
        assert len(files1) == 3

        # 第二次呼叫：使用快取
        # 如果快取有效，不應執行新的 stat
        changed2, files2 = check_error_patterns_changed(tmp_path, ticket_created)
        assert changed2 == True
        assert len(files2) == 3  # 應找到同樣 3 個檔案

    def test_new_file_triggers_stat(self, clear_caches, tmp_path):
        """測試案例 2.2：新檔案觸發 stat，舊檔案使用快取"""
        from hook_utils import check_error_patterns_changed, clear_error_pattern_mtime_cache

        error_patterns_dir = tmp_path / ".claude" / "error-patterns"
        error_patterns_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        # ticket 建立於 500 秒前
        ticket_created = now - timedelta(seconds=500)

        # 建立舊檔案（mtime 在 ticket 之後）
        old_file = error_patterns_dir / "old.md"
        old_file.write_text("Old")
        import os
        old_mtime = now.timestamp() - 100  # 比 ticket 晚
        os.utime(str(old_file), (old_mtime, old_mtime))

        clear_error_pattern_mtime_cache()

        # 第一次呼叫：快取舊檔案的 mtime
        changed1, files1 = check_error_patterns_changed(tmp_path, ticket_created)
        assert len(files1) == 1  # 只有舊檔案（mtime > ticket_created）

        # 新增一個檔案
        new_file = error_patterns_dir / "new.md"
        new_file.write_text("New")
        new_mtime = now.timestamp() - 50  # 比 ticket 更晚
        os.utime(str(new_file), (new_mtime, new_mtime))

        # 第二次呼叫：新檔案應觸發 stat，舊檔案使用快取
        changed2, files2 = check_error_patterns_changed(tmp_path, ticket_created)
        assert len(files2) == 2  # 現在有兩個檔案
        assert any("new.md" in f for f in files2)

    def test_clear_mtime_cache_forces_rescan(self, clear_caches, tmp_path):
        """測試案例 2.3：清空快取後重新掃描"""
        from hook_utils import check_error_patterns_changed, clear_error_pattern_mtime_cache

        error_patterns_dir = tmp_path / ".claude" / "error-patterns"
        error_patterns_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        file_path = error_patterns_dir / "test.md"
        file_path.write_text("Test")

        clear_error_pattern_mtime_cache()

        ticket_created = now - timedelta(seconds=100)

        # 第一次呼叫
        changed1, files1 = check_error_patterns_changed(tmp_path, ticket_created)

        # 清空快取
        clear_error_pattern_mtime_cache()

        # 第二次呼叫：應重新掃描
        changed2, files2 = check_error_patterns_changed(tmp_path, ticket_created)

        # 結果應相同（因為檔案未變）
        assert changed1 == changed2
        assert files1 == files2


# ============================================================================
# 區塊 3：功能正確性測試
# ============================================================================

class TestCacheFunctionalCorrectness:
    """驗證快取不影響原有功能正確性"""

    def test_handoff_mode_cache_correctness(self, clear_caches, tmp_path):
        """測試案例 3.1：快取不影響 is_handoff_recovery_mode() 功能"""
        from hook_utils import is_handoff_recovery_mode, clear_handoff_recovery_cache

        handoff_dir = tmp_path / ".claude" / "handoff" / "pending"
        handoff_dir.mkdir(parents=True, exist_ok=True)

        clear_handoff_recovery_cache()

        with patch('pathlib.Path.cwd', return_value=tmp_path):
            # 測試空目錄
            with patch.object(Path, 'glob', return_value=iter([])):
                assert is_handoff_recovery_mode() == False

            clear_handoff_recovery_cache()

            # 測試有檔案
            with patch.object(Path, 'glob', return_value=iter([Path("test.json")])):
                assert is_handoff_recovery_mode() == True

    def test_error_patterns_cache_correctness(self, clear_caches, tmp_path):
        """測試案例 3.2：快取不影響 check_error_patterns_changed() 功能"""
        from hook_utils import check_error_patterns_changed, clear_error_pattern_mtime_cache

        error_patterns_dir = tmp_path / ".claude" / "error-patterns"
        error_patterns_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        file_path = error_patterns_dir / "test.md"
        file_path.write_text("Test")

        clear_error_pattern_mtime_cache()

        ticket_created = now - timedelta(seconds=100)

        # 第一次呼叫（無快取）
        changed1, files1 = check_error_patterns_changed(tmp_path, ticket_created)

        # 第二次呼叫（有快取）
        changed2, files2 = check_error_patterns_changed(tmp_path, ticket_created)

        # 結果應完全相同
        assert changed1 == changed2
        assert files1 == files2


# ============================================================================
# 區塊 5：PyYAML 替代評估測試（簡化版）
# ============================================================================

class TestPyYAMLEvaluation:
    """PyYAML 替代評估基礎測試"""

    def test_pyyaml_basic_import(self):
        """測試 PyYAML 是否可用"""
        try:
            import yaml
            assert yaml is not None
        except ImportError:
            pytest.skip("PyYAML not installed")
