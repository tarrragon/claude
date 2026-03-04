#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 hook-health-monitor.py

Phase 2 設計的 37 個測試案例：
- TC-001~008：load_sessionstart_hooks_from_settings（8 個）
- TC-010~015：resolve_hook_log_dir（6 個）
- TC-020~027：check_hook_logs（8 個）
- TC-030~034：main + stderr 邏輯（5 個）
- TC-040~043：邊界/異常（5 個）
- TC-050~054：驗收條件驗證（5 個）
"""

import json
import logging
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# 添加 hooks 目錄到路徑
hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

# 使用 spec loader 以支援 uv run --script 格式
import importlib.util
spec = importlib.util.spec_from_file_location(
    "hook_health_monitor",
    hooks_dir / "hook-health-monitor.py"
)
hook_module = importlib.util.module_from_spec(spec)
sys.modules["hook_health_monitor"] = hook_module

# Mock hook_utils 和 common_functions 以便導入
class MockLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

def mock_setup_hook_logging(name):
    return MockLogger()

def mock_get_project_root():
    return None

def mock_hook_output(msg, level):
    pass

sys.modules["hook_utils"] = type("module", (), {"setup_hook_logging": mock_setup_hook_logging})()
sys.modules["lib"] = type("module", (), {})()
sys.modules["lib.common_functions"] = type("module", (), {
    "get_project_root": mock_get_project_root,
    "hook_output": mock_hook_output
})()

try:
    spec.loader.exec_module(hook_module)
except Exception as e:
    print(f"[Test Setup Error] Failed to load hook_health_monitor: {e}", file=sys.stderr)
    raise

from hook_health_monitor import (
    load_sessionstart_hooks_from_settings,
    resolve_hook_log_dir,
    check_hook_logs,
)


class TestLoadSessionstartHooks(unittest.TestCase):
    """TC-001~008: load_sessionstart_hooks_from_settings"""

    def test_load_hooks_normal(self):
        """TC-001: 正常讀取 SessionStart hooks"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/cli-dependency-check.py"
                                },
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/ticket-reinstall-hook.py"
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert "cli-dependency-check.py" in result
            assert "ticket-reinstall-hook.py" in result

    def test_load_hooks_empty(self):
        """TC-002: SessionStart 為空"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings = {"hooks": {"SessionStart": []}}
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert result == []

    def test_load_hooks_not_found(self):
        """TC-003: settings.json 不存在"""
        result = load_sessionstart_hooks_from_settings(
            Path("/nonexistent/settings.json")
        )
        assert result == []

    def test_load_hooks_invalid_json(self):
        """TC-004: settings.json 格式錯誤"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_file.write_text("{ invalid json")

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert result == []

    def test_load_hooks_with_arguments(self):
        """TC-005: command 包含參數"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/style-guardian-hook.py \"$CLAUDE_FILE_PATH\""
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert "style-guardian-hook.py" in result

    def test_load_hooks_deduplication(self):
        """TC-006: 去重（同一 hook 出現多次）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/cli-dependency-check.py"
                                },
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/cli-dependency-check.py"
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert result.count("cli-dependency-check.py") == 1

    def test_load_hooks_sorted(self):
        """TC-007: 結果按字母順序排序"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/zzz-hook.py"
                                },
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/aaa-hook.py"
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert result == ["aaa-hook.py", "zzz-hook.py"]

    def test_load_hooks_non_py_files_excluded(self):
        """TC-008: 非 .py 檔案被排除"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/test.sh"
                                },
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/valid-hook.py"
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert "test.sh" not in result
            assert "valid-hook.py" in result


class TestResolveHookLogDir(unittest.TestCase):
    """TC-010~015: resolve_hook_log_dir"""

    def test_resolve_exact_match(self):
        """TC-010: 日誌目錄名稱完全匹配"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "cli-dependency-check"
            log_dir.mkdir(parents=True, exist_ok=True)

            candidate, resolved, found = resolve_hook_log_dir(
                "cli-dependency-check.py", project_root
            )
            assert found
            assert candidate == "cli-dependency-check"
            assert resolved == log_dir

    def test_resolve_with_hook_suffix(self):
        """TC-011: 含 -hook 後綴（命名已修復，純 stem 推導）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "ticket-reinstall-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            candidate, resolved, found = resolve_hook_log_dir(
                "ticket-reinstall-hook.py", project_root
            )
            assert found
            assert candidate == "ticket-reinstall-hook"

    def test_resolve_not_found(self):
        """TC-012: 日誌目錄不存在"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".claude" / "hook-logs").mkdir(parents=True, exist_ok=True)

            candidate, resolved, found = resolve_hook_log_dir(
                "nonexistent-hook.py", project_root
            )
            assert not found
            assert candidate == "nonexistent-hook"

    def test_resolve_pure_stem_derivation(self):
        """TC-013: 純 stem 推導（命名一致性已修復，無候選策略）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # 只建立 stem 對應的目錄
            log_dir = project_root / ".claude" / "hook-logs" / "handoff-reminder-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            candidate, resolved, found = resolve_hook_log_dir(
                "handoff-reminder-hook.py", project_root
            )
            assert found
            assert candidate == "handoff-reminder-hook"
            assert resolved == log_dir

    def test_resolve_no_py_extension(self):
        """TC-014: 檔案名稱沒有 .py 擴展"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            candidate, resolved, found = resolve_hook_log_dir(
                "test-hook", project_root
            )
            assert found

    def test_resolve_multiple_hyphens(self):
        """TC-015: 檔案名稱包含多個連字符（純 stem 推導）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "pre-fix-evaluation-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            candidate, resolved, found = resolve_hook_log_dir(
                "pre-fix-evaluation-hook.py", project_root
            )
            assert found
            assert candidate == "pre-fix-evaluation-hook"


class TestCheckHookLogs(unittest.TestCase):
    """TC-020~027: check_hook_logs"""

    def test_check_hook_logs_all_ok(self):
        """TC-020: 所有 hook 日誌正常"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "cli-dependency-check"
            log_dir.mkdir(parents=True, exist_ok=True)

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, ["cli-dependency-check.py"]
            )
            assert max_severity == 0
            assert len(results) == 1
            assert results[0][0] == 0  # severity OK

    def test_check_hook_logs_missing_dir(self):
        """TC-021: 日誌目錄不存在"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".claude" / "hook-logs").mkdir(parents=True, exist_ok=True)

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, ["nonexistent-hook.py"]
            )
            assert max_severity == 2
            assert results[0][0] == 2

    def test_check_hook_logs_old_log(self):
        """TC-022: 日誌超過 24 小時"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            # 修改時間到 25 小時前
            old_time = (datetime.now() - timedelta(hours=25)).timestamp()
            import os
            os.utime(log_dir, (old_time, old_time))

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, ["test-hook.py"]
            )
            assert max_severity == 1  # WARN
            assert results[0][0] == 1

    def test_check_hook_logs_very_old_log(self):
        """TC-023: 日誌超過 48 小時"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            # 修改時間到 49 小時前
            old_time = (datetime.now() - timedelta(hours=49)).timestamp()
            import os
            os.utime(log_dir, (old_time, old_time))

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, ["test-hook.py"]
            )
            assert max_severity == 2  # FAIL
            assert results[0][0] == 2

    def test_check_hook_logs_multiple(self):
        """TC-024: 多個 hooks 混合狀態"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # 建立兩個日誌目錄
            log_dir1 = project_root / ".claude" / "hook-logs" / "hook1"
            log_dir2 = project_root / ".claude" / "hook-logs" / "hook2"
            log_dir1.mkdir(parents=True, exist_ok=True)
            log_dir2.mkdir(parents=True, exist_ok=True)

            # hook2 設為 50 小時前（FAIL）
            old_time = (datetime.now() - timedelta(hours=50)).timestamp()
            import os
            os.utime(log_dir2, (old_time, old_time))

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, ["hook1.py", "hook2.py"]
            )
            assert max_severity == 2
            assert len(results) == 2

    def test_check_hook_logs_return_format(self):
        """TC-025: 返回格式包含 hook 檔案名稱"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, ["test-hook.py"]
            )
            # 驗證返回格式：(severity, msg, hook_filename)
            assert len(results[0]) == 3
            assert results[0][2] == "test-hook.py"

    def test_check_hook_logs_empty_list(self):
        """TC-026: 空的 hooks 清單"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, []
            )
            assert max_severity == 0
            assert results == []

    def test_check_hook_logs_with_stat_error(self):
        """TC-027: stat() 拋出異常"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            logger = logging.getLogger("test")

            # Mock resolve_hook_log_dir 回傳已存在的目錄，
            # 再 mock stat 只影響 _check_single_hook_log 中的呼叫
            with patch(
                'hook_health_monitor.resolve_hook_log_dir',
                return_value=("test-hook", log_dir, True)
            ):
                with patch.object(Path, 'stat', side_effect=OSError("Permission denied")):
                    max_severity, results = check_hook_logs(
                        project_root, logger, ["test-hook.py"]
                    )
                    assert max_severity == 2
                    assert "[FAIL]" in results[0][1]


class TestMainAndStderr(unittest.TestCase):
    """TC-030~034: main + stderr 邏輯"""

    def test_main_outputs_to_stderr_on_failure(self):
        """TC-030: 失敗 hook 資訊輸出到 stderr"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # 建立 settings.json
            settings_file = project_root / ".claude" / "settings.json"
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/missing-hook.py"
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            # 不建立日誌目錄，觸發失敗
            (project_root / ".claude" / "hook-logs").mkdir(parents=True, exist_ok=True)

            # 捕獲 stderr
            old_stderr = sys.stderr
            sys.stderr = StringIO()
            try:
                with patch("hook_health_monitor.get_project_root", return_value=project_root):
                    with patch("hook_health_monitor.setup_hook_logging"):
                        with patch("hook_health_monitor.hook_output"):
                            from hook_health_monitor import main
                            main()

                stderr_output = sys.stderr.getvalue()
                self.assertTrue(
                    "missing-hook.py" in stderr_output or "critical issues" in stderr_output
                )
            finally:
                sys.stderr = old_stderr

    def test_main_healthy_no_stderr(self):
        """TC-031: 健康狀態不輸出 stderr"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # 建立 settings.json
            settings_file = project_root / ".claude" / "settings.json"
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/healthy-hook.py"
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            # 建立日誌目錄，確保健康
            log_dir = project_root / ".claude" / "hook-logs" / "healthy-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            # 捕獲 stderr
            old_stderr = sys.stderr
            sys.stderr = StringIO()
            try:
                with patch("hook_health_monitor.get_project_root", return_value=project_root):
                    with patch("hook_health_monitor.setup_hook_logging"):
                        with patch("hook_health_monitor.hook_output"):
                            from hook_health_monitor import main
                            main()

                stderr_output = sys.stderr.getvalue()
                self.assertEqual(stderr_output, "")
            finally:
                sys.stderr = old_stderr

    def test_stderr_contains_hook_filename(self):
        """TC-032: stderr 包含 hook 檔案名稱"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            settings_file = project_root / ".claude" / "settings.json"
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/failing-hook.py"
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            (project_root / ".claude" / "hook-logs").mkdir(parents=True, exist_ok=True)

            old_stderr = sys.stderr
            sys.stderr = StringIO()
            try:
                with patch("hook_health_monitor.get_project_root", return_value=project_root):
                    with patch("hook_health_monitor.setup_hook_logging"):
                        with patch("hook_health_monitor.hook_output"):
                            from hook_health_monitor import main
                            main()

                stderr_output = sys.stderr.getvalue()
                # 應該看到 hook 檔案名稱或 critical issues 訊息
                self.assertIn("failing-hook.py", stderr_output)
            finally:
                sys.stderr = old_stderr

    def test_main_returns_zero(self):
        """TC-033: main 總是回傳 0"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            settings_file = project_root / ".claude" / "settings.json"
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings = {"hooks": {"SessionStart": []}}
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            with patch("hook_health_monitor.get_project_root", return_value=project_root):
                with patch("hook_health_monitor.setup_hook_logging"):
                    with patch("hook_health_monitor.hook_output"):
                        from hook_health_monitor import main
                        result = main()
                        assert result == 0

    def test_main_project_root_not_found(self):
        """TC-034: 找不到 project root"""
        with patch("hook_health_monitor.get_project_root", return_value=None):
            with patch("hook_health_monitor.setup_hook_logging"):
                with patch("hook_health_monitor.hook_output"):
                    from hook_health_monitor import main
                    result = main()
                    assert result == 1


class TestEdgeCases(unittest.TestCase):
    """TC-040~043: 邊界/異常"""

    def test_load_hooks_with_missing_keys(self):
        """TC-040: settings.json 缺少部分鍵"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings = {}  # 缺少 hooks 鍵
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert result == []

    def test_check_hook_logs_permission_error(self):
        """TC-041: 日誌目錄無法訪問"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            logger = logging.getLogger("test")

            # Mock resolve_hook_log_dir 回傳已存在的目錄，
            # 再 mock stat 只影響 _check_single_hook_log 中的呼叫
            with patch(
                'hook_health_monitor.resolve_hook_log_dir',
                return_value=("test-hook", log_dir, True)
            ):
                with patch.object(Path, 'stat', side_effect=PermissionError("Access denied")):
                    max_severity, results = check_hook_logs(
                        project_root, logger, ["test-hook.py"]
                    )
                    assert max_severity == 2

    def test_resolve_hook_log_dir_edge_names(self):
        """TC-042: 邊界情況的檔案名稱"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # 只有 -hook 的檔案名稱（純 stem 推導）
            candidate, resolved, found = resolve_hook_log_dir(
                "-hook.py", project_root
            )
            # 純 stem 推導：去掉 .py 得到 "-hook"
            self.assertEqual(candidate, "-hook")
            self.assertFalse(found)  # 目錄不存在

    def test_load_hooks_with_empty_command(self):
        """TC-043: command 欄位為空"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": ""
                                }
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert result == []


class TestAcceptanceCriteria(unittest.TestCase):
    """TC-050~054: 驗收條件驗證"""

    def test_coverage_all_sessionstart_hooks(self):
        """TC-050: 報告覆蓋全部 SessionStart hooks"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            settings_file = project_root / ".claude" / "settings.json"
            settings_file.parent.mkdir(parents=True, exist_ok=True)

            # 建立 13 個 hooks（settings.json 中的實際數量）
            hooks_list = [
                "cli-dependency-check.py",
                "ticket-reinstall-hook.py",
                "package-version-sync-hook.py",
                "hook-completeness-check.py",
                "hook-health-monitor.py",
                "skill-registration-check-hook.py",
                "branch-status-reminder.py",
                "output-style-check.py",
                "handoff-reminder-hook.py",
                "doc-sync-check-hook.py",
                "lsp-environment-check.py",
                "tech-debt-reminder.py",
                "project-init-env-check-hook.py",
            ]

            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"$CLAUDE_PROJECT_DIR/.claude/hooks/{hook}"
                                }
                                for hook in hooks_list
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            assert len(result) == 13
            for hook in hooks_list:
                assert hook in result

    def test_report_format_contains_status(self):
        """TC-051: 報告包含狀態（success/warning/error）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, ["test-hook.py"]
            )

            # 檢查報告包含狀態標記
            msg = results[0][1]
            assert "[OK]" in msg or "[WARN]" in msg or "[FAIL]" in msg

    def test_report_contains_log_path(self):
        """TC-052: 報告包含日誌目錄路徑資訊"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            log_dir = project_root / ".claude" / "hook-logs" / "test-hook"
            log_dir.mkdir(parents=True, exist_ok=True)

            logger = logging.getLogger("test")
            max_severity, results = check_hook_logs(
                project_root, logger, ["test-hook.py"]
            )

            # 檢查報告包含時間資訊
            msg = results[0][1]
            assert "h ago" in msg or "error" in msg.lower()

    def test_py_compile_success(self):
        """TC-053: hook-health-monitor.py 通過 py_compile"""
        import py_compile
        import tempfile as tf

        hook_file = Path(__file__).parent.parent / "hook-health-monitor.py"
        assert hook_file.exists()

        # 嘗試編譯
        with tf.TemporaryDirectory() as tmpdir:
            py_compile.compile(str(hook_file), cfile=str(Path(tmpdir) / "hook.pyc"))

    def test_dynamic_parsing_not_hardcoded(self):
        """TC-054: 動態解析，不使用硬編碼清單"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # 建立自訂 hooks 清單（不是預定義的 5 個）
            custom_hooks = [
                "custom-hook-1.py",
                "custom-hook-2.py",
                "custom-hook-3.py",
            ]

            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"$CLAUDE_PROJECT_DIR/.claude/hooks/{hook}"
                                }
                                for hook in custom_hooks
                            ]
                        }
                    ]
                }
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)

            result = load_sessionstart_hooks_from_settings(settings_file)
            # 應該找到自訂 hooks，不依賴硬編碼清單
            assert len(result) == 3
            assert "custom-hook-1.py" in result


if __name__ == "__main__":
    unittest.main(verbosity=2)
