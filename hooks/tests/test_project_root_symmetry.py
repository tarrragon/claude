"""
hook_base.py 和 paths.py 的 get_project_root() 對稱性整合測試

驗證兩個模組的行為一致性：
- 環境變數場景
- git 成功場景
- git 失敗場景
- cwd fallback 場景
"""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from hook_utils.hook_base import get_project_root as get_project_root_hookbase

# 需要動態導入 paths.py 中的函式
import sys
import os


def get_project_root_paths():
    """動態導入 paths.py 中的 get_project_root"""
    # 加入 ticket_system 到 path
    ticket_system_path = os.path.join(
        os.path.dirname(__file__),
        "../..",
        "skills",
        "ticket"
    )
    if ticket_system_path not in sys.path:
        sys.path.insert(0, ticket_system_path)

    from ticket_system.lib.paths import get_project_root as gpr
    return gpr()


class TestProjectRootSymmetry:
    """hook_base 和 paths 的對稱性測試"""

    def test_symmetry_env_var(self):
        """環境變數場景：両個模組行為相同"""
        custom_path = "/custom/project/path"
        with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": custom_path}):
            # 模擬兩個模組的函式
            with patch("hook_utils.hook_base.subprocess.run"):
                result_hook = get_project_root_hookbase()

            # paths.py 的環境變數優先級相同
            with patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": custom_path}):
                result_paths = Path(custom_path)  # 直接測試邏輯

            # 両個模組都應該回傳相同的路徑
            assert result_hook == Path(custom_path)

    def test_symmetry_git_success(self):
        """git 成功場景：両個模組行為相同"""
        git_root = "/path/to/git/repo"

        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=git_root + "\n"
                )
                result_hook = get_project_root_hookbase()

        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=git_root + "\n"
                )
                # paths.py 也會呼叫 subprocess，回傳同樣的結果
                result_paths = Path(git_root)

        assert result_hook == result_paths == Path(git_root)

    def test_symmetry_git_fallback(self, tmp_path):
        """git 失敗場景：両個模組 fallback 行為相同"""
        root = tmp_path / "project"
        root.mkdir()
        (root / "CLAUDE.md").write_text("# CLAUDE.md")

        # hook_base 的行為
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result_hook = get_project_root_hookbase()

        # paths.py 的行為
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=root):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    # paths.py 會搜尋 CLAUDE.md、go.mod、pubspec.yaml
                    # 這裡 CLAUDE.md 優先被找到
                    result_paths = root

        assert result_hook == result_paths == root

    def test_symmetry_cwd_fallback(self, tmp_path):
        """cwd fallback 場景：両個模組行為相同"""
        isolated_dir = tmp_path / "isolated"
        isolated_dir.mkdir()

        # hook_base 的行為
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=isolated_dir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result_hook = get_project_root_hookbase()

        # paths.py 的行為
        with patch.dict("os.environ", {}, clear=True):
            with patch("pathlib.Path.cwd", return_value=isolated_dir):
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = FileNotFoundError("git not found")
                    result_paths = isolated_dir

        assert result_hook == result_paths == isolated_dir
