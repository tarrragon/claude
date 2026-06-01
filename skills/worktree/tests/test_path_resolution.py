"""
Regression test for W1-118: worktree skill project_root 推導修復

驗證 _resolve_project_root() 雙策略 fallback：
1. 優先讀 CLAUDE_PROJECT_DIR 環境變數
2. Fallback：git rev-parse --show-toplevel
3. 雙雙失敗報錯
"""

import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 確保可 import worktree_manager
_THIS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _THIS_DIR.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import worktree_manager  # noqa: E402


class TestResolveProjectRoot:
    """測試 _resolve_project_root 雙策略 fallback"""

    def test_strategy1_env_var_set_and_exists(self, tmp_path, monkeypatch):
        """策略 1：CLAUDE_PROJECT_DIR 指向有效路徑時優先採用"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
        result = worktree_manager._resolve_project_root()
        assert result == tmp_path.resolve()

    def test_strategy1_env_var_set_but_not_exists_falls_back(
        self, tmp_path, monkeypatch
    ):
        """策略 1：CLAUDE_PROJECT_DIR 指向不存在路徑時降級到策略 2"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "nonexistent"))

        # Mock 策略 2 成功
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = str(tmp_path) + "\n"
        with patch.object(subprocess, "run", return_value=mock_result):
            result = worktree_manager._resolve_project_root()
            assert result == tmp_path.resolve()

    def test_strategy2_git_rev_parse_success(self, tmp_path, monkeypatch):
        """策略 2：環境變數未設時，git rev-parse 成功"""
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = str(tmp_path) + "\n"
        with patch.object(subprocess, "run", return_value=mock_result):
            result = worktree_manager._resolve_project_root()
            assert result == tmp_path.resolve()

    def test_strategy2_git_rev_parse_returns_nonzero(self, monkeypatch):
        """策略 2：git rev-parse 失敗（非 0 returncode）時報錯"""
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        with patch.object(subprocess, "run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="無法定位專案根目錄"):
                worktree_manager._resolve_project_root()

    def test_both_strategies_fail_raises_runtime_error(self, monkeypatch):
        """雙策略皆失敗時拋 RuntimeError 含明確訊息"""
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        with patch.object(
            subprocess, "run", side_effect=FileNotFoundError("git not found")
        ):
            with pytest.raises(RuntimeError, match="CLAUDE_PROJECT_DIR"):
                worktree_manager._resolve_project_root()

    def test_strategy2_timeout_handled(self, monkeypatch):
        """策略 2：git rev-parse timeout 時報錯"""
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

        with patch.object(
            subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
        ):
            with pytest.raises(RuntimeError, match="無法定位專案根目錄"):
                worktree_manager._resolve_project_root()
