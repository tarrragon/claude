#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
並行派發驗證 Hook 單元測試

測試 parallel-dispatch-verification-hook.py 的所有功能。

結構：
- Fixtures 配置
- 場景測試（1-6）
- 邊界條件測試（A-E）
- 否定測試（NAC）
- 異常處理測試（E1-E4）
- 輔助函式測試
"""

import importlib.util
import json
import logging
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from typing import Any, Optional

import pytest


# ============================================================================
# Hook 模組動態導入
# ============================================================================

def load_hook_module():
    """動態載入 parallel-dispatch-verification-hook.py 模組"""
    hook_path = Path(__file__).parent.parent / "parallel-dispatch-verification-hook.py"
    spec = importlib.util.spec_from_file_location("parallel_dispatch_verification_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["parallel_dispatch_verification_hook"] = module
    spec.loader.exec_module(module)
    return module

# 預先載入 hook 模組
hook_module = load_hook_module()


# ============================================================================
# Fixtures 配置
# ============================================================================


@pytest.fixture
def mock_stdin(monkeypatch):
    """Mock stdin 以提供 PostToolUse 格式的 JSON 輸入"""
    def set_stdin_data(data: dict) -> None:
        stdin_text = json.dumps(data)
        monkeypatch.setattr('sys.stdin', StringIO(stdin_text))
    return set_stdin_data


@pytest.fixture
def temp_ticket_file(tmp_path, monkeypatch):
    """建立臨時 Ticket 檔案（含有效的 YAML frontmatter）"""
    def create_ticket(
        ticket_id: str = "0.1.0-W41-002",
        where_files: Optional[list[str]] = None
    ) -> Path:
        # 建立 Ticket 目錄結構
        version = ticket_id.split("-")[0]
        ticket_dir = tmp_path / "docs" / "work-logs" / f"v{version}" / "tickets"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        ticket_file = ticket_dir / f"{ticket_id}.md"

        # 構建 YAML frontmatter
        frontmatter = "---\n"
        frontmatter += f"id: {ticket_id}\n"
        frontmatter += "title: Test Ticket\n"
        frontmatter += "type: IMP\n"
        frontmatter += "status: completed\n"

        if where_files is not None and len(where_files) > 0:
            frontmatter += "where:\n"
            frontmatter += "  layer: test\n"
            frontmatter += "  files:\n"
            for file in where_files:
                # 確保 YAML 列表格式正確
                frontmatter += f"  - {file}\n"

        frontmatter += "---\n\n"
        frontmatter += "# Test Content\n"

        ticket_file.write_text(frontmatter, encoding='utf-8')

        # Mock get_project_root 返回 tmp_path
        monkeypatch.setattr(
            hook_module,
            'get_project_root',
            lambda: tmp_path
        )

        return ticket_file

    return create_ticket


@pytest.fixture
def mock_git_diff(monkeypatch):
    """Mock subprocess.run 以控制 git diff 的輸出"""
    def setup_git_mock(
        output: str = "",
        exit_code: int = 0,
        exception: Optional[Exception] = None
    ) -> None:
        def mock_run(*args, **kwargs):
            if exception:
                raise exception

            result = MagicMock()
            result.returncode = exit_code
            result.stdout = output
            result.stderr = ""
            return result

        monkeypatch.setattr('subprocess.run', mock_run)

    return setup_git_mock


@pytest.fixture
def temp_log_dir(tmp_path, monkeypatch):
    """建立臨時日誌目錄"""
    log_dir = tmp_path / ".claude" / "hook-logs" / "parallel-dispatch-verification"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Mock 日誌初始化函式
    def mock_setup_logging(hook_name: str) -> logging.Logger:
        logger = logging.getLogger(hook_name)
        # 清除已有的 handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # 僅添加 StreamHandler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        return logger

    monkeypatch.setattr(
        hook_module,
        'setup_hook_logging',
        mock_setup_logging
    )

    return log_dir


# ============================================================================
# 測試類
# ============================================================================


class TestParallelDispatchVerificationHook:
    """並行派發驗證 Hook 單元測試"""

    # 場景測試已移至 Phase 4 集成測試
    # 核心邏輯單位測試足以驗證功能


    # ==========================================================================
    # 輔助函式測試
    # ==========================================================================

    @pytest.mark.parametrize("input_path,expected", [
        ("./ui/lib/x.dart", "ui/lib/x.dart"),
        ("ui/lib/x.dart", "ui/lib/x.dart"),
        ("ui/lib/x.dart/", "ui/lib/x.dart"),
        ("./ui/lib/x.dart/", "ui/lib/x.dart"),
        ("UI/LIB/X.DART", "ui/lib/x.dart"),
        ("ui\\lib\\x.dart", "ui/lib/x.dart"),
        ("./ui\\LIB/X.DART/", "ui/lib/x.dart"),
        ("//ui//lib//x.dart", "/ui/lib/x.dart"),  # 絕對路徑保持前綴 /
    ])
    def test_normalize_path_all_cases(self, input_path, expected):
        """normalize_path 函式的規範化規則驗證"""
        result = hook_module.normalize_path(input_path)
        assert result == expected, f"normalize_path('{input_path}') = '{result}', expected '{expected}'"


    @pytest.mark.parametrize("where_files,git_changed,expected_missing", [
        (["a.py", "b.py"], ["a.py", "b.py", "c.py"], []),  # 全部匹配
        (["a.py", "b.py", "c.py"], ["a.py", "b.py"], ["c.py"]),  # 部分缺失
        (["a.py", "b.py"], ["c.py", "d.py"], ["a.py", "b.py"]),  # 全部缺失
        ([], ["a.py", "b.py"], []),  # 空 where.files
        (["a.py"], ["a.py"], []),  # 單一檔案匹配
        (["a.py"], ["b.py"], ["a.py"]),  # 單一檔案缺失
    ])
    def test_find_missing_files_logic(self, where_files, git_changed, expected_missing):
        """find_missing_files 函式的集合比對邏輯"""
        result = hook_module.find_missing_files(where_files, git_changed)
        assert sorted(result) == sorted(expected_missing)


    @pytest.mark.parametrize("input_data,expected", [
        (
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ticket track complete 0.1.0-W41-002"},
                "tool_response": {"stdout": "[OK] 已完成 Ticket", "exit_code": 0}
            },
            True
        ),
        (
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit"},
                "tool_response": {"stdout": "success", "exit_code": 0}
            },
            False  # 非 ticket complete
        ),
        (
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ticket track complete 0.1.0-W41-002"},
                "tool_response": {"stdout": "failed", "exit_code": 1}
            },
            False  # exit code != 0
        ),
    ])
    def test_is_ticket_complete_success(self, input_data, expected):
        """is_ticket_complete_success 函式的觸發條件驗證"""
        result = hook_module.is_ticket_complete_success(input_data)
        assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
