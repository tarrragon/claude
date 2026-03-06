"""集成測試 — 驗證 check/setup 命令的實際輸出。

測試完整的使用者流程，包括訊息格式和引導。
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from project_init.commands.check import run_check
from project_init.lib import (
    PythonInfo,
    UvInfo,
    RipgrepInfo,
    OsInfo,
)


class TestCheckCommandOutput:
    """測試 check 命令的輸出格式."""

    def test_check_with_missing_python(self, capsys, tmp_path: Path) -> None:
        """測試 Python 缺失時的輸出."""
        with patch("project_init.commands.check.detect_python") as mock_python:
            with patch("project_init.commands.check.detect_os") as mock_os:
                with patch("project_init.commands.check.detect_uv") as mock_uv:
                    with patch("project_init.commands.check.detect_ripgrep") as mock_rg:
                        with patch("project_init.commands.check.verify_hooks_system") as mock_hooks:
                            with patch("project_init.commands.check.scan_custom_packages") as mock_packages:
                                # 設定 mock 返回值
                                mock_python.return_value = PythonInfo(
                                    version="",
                                    path=None,
                                    is_available=False,
                                    failure_reason="python3 命令未在 PATH 中找到"
                                )
                                mock_os.return_value = OsInfo(
                                    system="Darwin",
                                    version="24.3.0",
                                    is_available=True
                                )
                                mock_uv.return_value = UvInfo(
                                    version="uv 0.4.0",
                                    path="/usr/local/bin/uv",
                                    is_available=True
                                )
                                mock_rg.return_value = RipgrepInfo(
                                    version="ripgrep 13.0.0",
                                    path="/usr/local/bin/rg",
                                    is_available=True
                                )
                                mock_hooks.return_value.all_compilable = True
                                mock_hooks.return_value.hook_count = 0
                                mock_hooks.return_value.errors = []
                                mock_packages.return_value = []

                                # 執行 check
                                result = run_check(tmp_path)

                                # 驗證結果
                                assert not result.all_ok
                                captured = capsys.readouterr()

                                # 驗證輸出包含引導訊息
                                assert "Python" in captured.out
                                assert "python3 命令未在 PATH 中找到" in captured.out
                                assert "修復步驟:" in captured.out
                                assert "python.org" in captured.out

    def test_check_with_all_ok(self, capsys, tmp_path: Path) -> None:
        """測試所有工具都正常時的輸出."""
        with patch("project_init.commands.check.detect_python") as mock_python:
            with patch("project_init.commands.check.detect_os") as mock_os:
                with patch("project_init.commands.check.detect_uv") as mock_uv:
                    with patch("project_init.commands.check.detect_ripgrep") as mock_rg:
                        with patch("project_init.commands.check.verify_hooks_system") as mock_hooks:
                            with patch("project_init.commands.check.scan_custom_packages") as mock_packages:
                                # 所有工具都正常
                                mock_python.return_value = PythonInfo(
                                    version="Python 3.14.13",
                                    path="/usr/bin/python3",
                                    is_available=True
                                )
                                mock_os.return_value = OsInfo(
                                    system="Darwin",
                                    version="24.3.0",
                                    is_available=True
                                )
                                mock_uv.return_value = UvInfo(
                                    version="uv 0.4.0",
                                    path="/usr/local/bin/uv",
                                    is_available=True
                                )
                                mock_rg.return_value = RipgrepInfo(
                                    version="ripgrep 13.0.0",
                                    path="/usr/local/bin/rg",
                                    is_available=True
                                )
                                mock_hooks.return_value.all_compilable = True
                                mock_hooks.return_value.hook_count = 0
                                mock_hooks.return_value.errors = []
                                mock_packages.return_value = []

                                # 執行 check
                                result = run_check(tmp_path)

                                # 驗證結果
                                assert result.all_ok
                                captured = capsys.readouterr()

                                # 驗證輸出格式
                                assert "project-init check" in captured.out
                                assert "6/6 項目正常" in captured.out


class TestExceptionUsageExample:
    """測試異常的實際使用例子."""

    def test_toolnotfound_usage(self) -> None:
        """測試 ToolNotFoundError 的典型使用."""
        from project_init.lib.exceptions import ToolNotFoundError

        try:
            guidance = [
                "訪問 https://www.python.org/downloads/",
                "下載 Python 3.14 或更高版本",
                "執行安裝程式",
                "驗證: python3 --version"
            ]
            raise ToolNotFoundError("Python", "python3 命令未在 PATH 中找到", guidance)
        except ToolNotFoundError as exc:
            assert exc.tool == "Python"
            message = exc.get_full_message()
            assert "修復步驟:" in message
            assert all(step in message for step in guidance)

    def test_version_too_old_usage(self) -> None:
        """測試 VersionTooOldError 的典型使用."""
        from project_init.lib.exceptions import VersionTooOldError

        try:
            guidance = ["升級 UV: brew upgrade uv"]
            raise VersionTooOldError(
                "UV",
                "版本 0.0.5 太舊，需要 0.1.0+",
                guidance
            )
        except VersionTooOldError as exc:
            assert exc.tool == "UV"
            assert "太舊" in exc.reason
