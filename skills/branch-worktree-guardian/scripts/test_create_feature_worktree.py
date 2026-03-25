#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest", "pytest-mock"]
# ///
"""
Test suite for create_feature_worktree.py

22 test cases covering:
- Unit tests: core function and helper functions (UT-01 to UT-12)
- Integration tests: CLI interface (IT-01 to IT-03)
- Regression tests: API compatibility (RT-01)
"""

import inspect
import os
import subprocess
from unittest.mock import patch

import pytest

from create_feature_worktree import (
    branch_exists,
    create_feature_worktree,
    main,
    run_git_command,
    worktree_exists,
)


class TestCreateFeatureWorktree:
    """create_feature_worktree() 函式的單元測試"""

    def test_success(self, mocker):
        """UT-01: 正常流程 — 原子命令成功"""
        # Setup
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["main"]  # 只有 main 存在
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(True, "")
        )

        # Act
        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../project-abc",
            base_branch="main"
        )

        # Assert
        assert success is True
        assert "feat/abc" in message

        # 驗證呼叫原子命令一次
        mock_run_git.assert_called_once()
        call_args = mock_run_git.call_args[0][0]
        assert call_args == ["worktree", "add", "-b", "feat/abc", mocker.ANY, "main"]

        # 驗證無回滾邏輯
        assert mock_run_git.call_count == 1

    def test_worktree_exists(self, mocker):
        """UT-02: 前置驗證失敗 — worktree 路徑已存在"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=True
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command"
        )

        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../existing-project",
            base_branch="main"
        )

        assert success is False
        assert "Worktree 路徑已存在" in message
        mock_run_git.assert_not_called()  # 未執行任何 git 命令

    def test_branch_exists(self, mocker):
        """UT-03: 前置驗證失敗 — 分支已存在"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            return_value=True  # 分支已存在
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command"
        )

        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../project-abc",
            base_branch="main"
        )

        assert success is False
        assert "分支已存在" in message
        assert "feat/abc" in message
        mock_run_git.assert_not_called()

    def test_base_branch_not_exists(self, mocker):
        """UT-04: 前置驗證失敗 — base_branch 不存在"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["main"]  # 只有 main 存在
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command"
        )

        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../project-abc",
            base_branch="nonexistent"
        )

        assert success is False
        assert "基礎分支不存在" in message
        assert "nonexistent" in message
        mock_run_git.assert_not_called()

    def test_git_command_fails(self, mocker):
        """UT-05: 原子命令失敗 — git 執行錯誤"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["main"]
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(False, "fatal: 路徑已佔用")
        )

        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../project-abc",
            base_branch="main"
        )

        assert success is False
        assert "創建 worktree 失敗" in message
        assert "fatal: 路徑已佔用" in message

        # 驗證沒有回滾（只呼叫一次）
        assert mock_run_git.call_count == 1

    def test_relative_path_conversion(self, mocker):
        """UT-06: 相對路徑正確轉換為絕對路徑"""
        abs_path_mock = "/absolute/path/project-abc"

        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["main"]
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(True, "")
        )
        mock_abspath = mocker.patch(
            "os.path.abspath",
            return_value=abs_path_mock
        )

        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../project-abc",
            base_branch="main"
        )

        assert success is True
        # 驗證絕對路徑在 git 命令中
        args = mock_run_git.call_args[0][0]
        assert abs_path_mock in args

    def test_branch_with_slash(self, mocker):
        """UT-07: branch 名稱包含斜線"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["main"]
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(True, "")
        )

        success, message = create_feature_worktree(
            branch="feat/new-feature/sub",
            worktree_path="../project",
            base_branch="main"
        )

        assert success is True
        # 驗證完整分支名稱被傳遞
        args = mock_run_git.call_args[0][0]
        assert "feat/new-feature/sub" in args


class TestBranchExists:
    """branch_exists() 函式的單元測試"""

    def test_branch_exists_true(self, mocker):
        """UT-08a: branch_exists 回傳 True"""
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(True, "abc123")
        )

        result = branch_exists("main")

        assert result is True
        mock_run_git.assert_called_once_with(["rev-parse", "--verify", "main"], None)

    def test_branch_exists_false(self, mocker):
        """UT-08b: branch_exists 回傳 False"""
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(False, "error")
        )

        result = branch_exists("nonexistent")

        assert result is False


class TestWorktreeExists:
    """worktree_exists() 函式的單元測試"""

    def test_worktree_exists_true(self, mocker):
        """UT-09a: worktree_exists 回傳 True"""
        mock_exists = mocker.patch(
            "os.path.exists",
            return_value=True
        )

        result = worktree_exists("/absolute/path")

        assert result is True
        mock_exists.assert_called_once_with("/absolute/path")

    def test_worktree_exists_false(self, mocker):
        """UT-09b: worktree_exists 回傳 False"""
        mock_exists = mocker.patch(
            "os.path.exists",
            return_value=False
        )

        result = worktree_exists("/absolute/nonexistent")

        assert result is False


class TestRunGitCommand:
    """run_git_command() 函式的單元測試"""

    def test_timeout(self, mocker):
        """UT-10: git 命令執行超時"""
        mock_subprocess = mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("git", 30)
        )

        success, message = run_git_command(["long-running"])

        assert success is False
        assert "命令執行超時" in message


class TestBoundaryConditions:
    """邊界條件測試"""

    def test_remote_tracking_branch(self, mocker):
        """UT-11: base_branch 為遠端追蹤分支"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["origin/main"]
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(True, "")
        )

        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../project",
            base_branch="origin/main"
        )

        assert success is True
        args = mock_run_git.call_args[0][0]
        assert "origin/main" in args

    def test_head_unchanged(self, mocker):
        """UT-12: 主工作目錄 HEAD 不受影響"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["main"]
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(True, "")
        )

        success, _ = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../project",
            base_branch="main"
        )

        assert success is True
        # 驗證沒有執行 checkout -b（原子操作特性）
        args = mock_run_git.call_args[0][0]
        assert "checkout" not in args


class TestMainCLI:
    """main() 函式的整合測試"""

    def test_dry_run_mode(self, mocker, capsys):
        """IT-01: dry-run 模式 — 輸出驗證"""
        mocker.patch(
            "sys.argv",
            ["script", "--branch", "feat/abc", "--worktree", "../project-abc", "--dry-run"]
        )

        exit_code = main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Dry Run 模式" in captured.out
        assert "git worktree add -b" in captured.out
        assert "feat/abc" in captured.out

    def test_main_success(self, mocker, capsys):
        """IT-02: 正常執行完整 CLI 流程"""
        mocker.patch(
            "sys.argv",
            ["script", "--branch", "feat/abc", "--worktree", "../project-abc"]
        )
        mock_create = mocker.patch(
            "create_feature_worktree.create_feature_worktree",
            return_value=(True, "成功創建分支 'feat/abc' 和 worktree '/abs/path'")
        )

        exit_code = main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "成功創建分支" in captured.out
        assert "下一步" in captured.out
        assert "cd" in captured.out

    def test_main_failure(self, mocker, capsys):
        """IT-03: 錯誤流程 — CLI 失敗回傳"""
        mocker.patch(
            "sys.argv",
            ["script", "--branch", "feat/abc", "--worktree", "../project-abc"]
        )
        mock_create = mocker.patch(
            "create_feature_worktree.create_feature_worktree",
            return_value=(False, "分支已存在: feat/abc")
        )

        exit_code = main()
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "分支已存在" in captured.out


class TestBoundaryAdditional:
    """額外邊界條件測試"""

    def test_empty_branch_name(self, mocker):
        """邊界: 空白分支名稱"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b == "main"  # 空字符串返回 False
        )
        # 空分支名稱仍會被檢查，git 命令會失敗
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(False, "fatal: bad refspec")
        )

        success, message = create_feature_worktree(
            branch="",
            worktree_path="../project",
            base_branch="main"
        )

        # 前置檢查通過，但 git 命令會失敗
        assert success is False
        assert "創建 worktree 失敗" in message

    def test_special_characters_in_path(self, mocker):
        """邊界: 路徑包含特殊字符"""
        abs_path_mock = "/path/with space/project"

        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["main"]
        )
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(True, "")
        )
        mocker.patch(
            "os.path.abspath",
            return_value=abs_path_mock
        )

        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../with space/project",
            base_branch="main"
        )

        assert success is True
        args = mock_run_git.call_args[0][0]
        assert abs_path_mock in args

    def test_git_command_empty_output(self, mocker):
        """邊界: git 命令成功但無輸出"""
        mock_worktree_exists = mocker.patch(
            "create_feature_worktree.worktree_exists",
            return_value=False
        )
        mock_branch_exists = mocker.patch(
            "create_feature_worktree.branch_exists",
            side_effect=lambda b: b in ["main"]
        )
        # git 命令成功但沒有輸出（空字符串）
        mock_run_git = mocker.patch(
            "create_feature_worktree.run_git_command",
            return_value=(True, "")
        )

        success, message = create_feature_worktree(
            branch="feat/abc",
            worktree_path="../project",
            base_branch="main"
        )

        assert success is True
        assert "成功創建分支" in message

    def test_run_git_command_generic_exception(self, mocker):
        """邊界: git 命令執行異常"""
        mock_subprocess = mocker.patch(
            "subprocess.run",
            side_effect=OSError("Permission denied")
        )

        success, message = run_git_command(["status"])

        assert success is False
        assert "Permission denied" in message


class TestRegression:
    """迴歸測試"""

    def test_function_signature_unchanged(self):
        """RT-01: 函式簽名向後相容"""
        sig = inspect.signature(create_feature_worktree)
        params = list(sig.parameters.keys())

        assert params == ["branch", "worktree_path", "base_branch"]
        assert sig.parameters["base_branch"].default == "main"
        assert "tuple" in str(sig.return_annotation)
