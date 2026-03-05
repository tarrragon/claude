"""測試環境偵測模組。

驗證 failure_reason 欄位在各種場景下的值。
"""

import pytest
from unittest.mock import patch, MagicMock
from project_init.lib.env_detector import (
    detect_python,
    detect_uv,
    detect_ripgrep,
    PythonInfo,
    UvInfo,
    RipgrepInfo,
)


class TestPythonDetection:
    """測試 Python 偵測和 failure_reason."""

    def test_python_found_success(self) -> None:
        """測試成功找到 Python."""
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="Python 3.11.13\n"
                )
                info = detect_python()
                assert info.is_available
                assert info.version == "Python 3.11.13"
                assert info.failure_reason is None

    def test_python_not_found(self) -> None:
        """測試 Python 命令未找到."""
        with patch("shutil.which", return_value=None):
            info = detect_python()
            assert not info.is_available
            assert info.failure_reason == "python3 命令未在 PATH 中找到"

    def test_python_version_command_failed(self) -> None:
        """測試 python3 --version 命令失敗."""
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)
                info = detect_python()
                assert not info.is_available
                assert "無法執行" in info.failure_reason

    def test_python_timeout(self) -> None:
        """測試 Python 偵測超時."""
        import subprocess
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("python3", 5)
                info = detect_python()
                assert not info.is_available
                assert "超時" in info.failure_reason

    def test_python_generic_error(self) -> None:
        """測試 Python 偵測一般例外."""
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Permission denied")
                info = detect_python()
                assert not info.is_available
                assert "偵測失敗" in info.failure_reason


class TestUVDetection:
    """測試 UV 偵測和 failure_reason."""

    def test_uv_found_success(self) -> None:
        """測試成功找到 UV."""
        with patch("shutil.which", return_value="/usr/local/bin/uv"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="uv 0.4.0\n"
                )
                info = detect_uv()
                assert info.is_available
                assert info.version == "uv 0.4.0"
                assert info.failure_reason is None

    def test_uv_not_found(self) -> None:
        """測試 UV 命令未找到."""
        with patch("shutil.which", return_value=None):
            info = detect_uv()
            assert not info.is_available
            assert info.failure_reason == "uv 命令未在 PATH 中找到"

    def test_uv_version_command_failed(self) -> None:
        """測試 uv --version 命令失敗."""
        with patch("shutil.which", return_value="/usr/local/bin/uv"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)
                info = detect_uv()
                assert not info.is_available
                assert "無法執行" in info.failure_reason

    def test_uv_timeout(self) -> None:
        """測試 UV 偵測超時."""
        import subprocess
        with patch("shutil.which", return_value="/usr/local/bin/uv"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("uv", 5)
                info = detect_uv()
                assert not info.is_available
                assert "超時" in info.failure_reason


class TestRipgrepDetection:
    """測試 ripgrep 偵測和 failure_reason."""

    def test_ripgrep_not_found(self) -> None:
        """測試 ripgrep 命令未找到."""
        with patch("shutil.which", return_value=None):
            with patch("project_init.lib.env_detector._detect_claude_bundled_ripgrep", return_value=None):
                info = detect_ripgrep()
                assert not info.is_available
                assert "rg 命令未在 PATH 中找到" in info.failure_reason
                assert "Claude Code bundled ripgrep" in info.failure_reason

    def test_ripgrep_found_success(self) -> None:
        """測試成功找到 ripgrep."""
        with patch("shutil.which", return_value="/usr/local/bin/rg"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="ripgrep 13.0.0\n"
                )
                info = detect_ripgrep()
                assert info.is_available
                assert info.version == "ripgrep 13.0.0"
                assert info.failure_reason is None


class TestPythonInfoDataclass:
    """測試 PythonInfo dataclass."""

    def test_failure_reason_optional(self) -> None:
        """測試 failure_reason 是可選欄位."""
        info = PythonInfo(
            version="3.11.13",
            path="/usr/bin/python3",
            is_available=True
        )
        assert info.failure_reason is None

    def test_failure_reason_set(self) -> None:
        """測試 failure_reason 設定值."""
        info = PythonInfo(
            version="",
            path=None,
            is_available=False,
            failure_reason="python3 命令未找到"
        )
        assert info.failure_reason == "python3 命令未找到"


class TestUVInfoDataclass:
    """測試 UvInfo dataclass."""

    def test_failure_reason_optional(self) -> None:
        """測試 failure_reason 是可選欄位."""
        info = UvInfo(
            version="0.4.0",
            path="/usr/local/bin/uv",
            is_available=True
        )
        assert info.failure_reason is None


class TestRipgrepInfoDataclass:
    """測試 RipgrepInfo dataclass."""

    def test_failure_reason_optional(self) -> None:
        """測試 failure_reason 是可選欄位."""
        info = RipgrepInfo(
            version="13.0.0",
            path="/usr/local/bin/rg",
            is_available=True
        )
        assert info.failure_reason is None
