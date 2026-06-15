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
    """測試 Python 偵測和 failure_reason（W9-001 多候選 + uv fallback）."""

    def test_python_found_success(self) -> None:
        """測試成功找到 Python（首個候選命中）."""
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="Python 3.14.13\n"
                )
                info = detect_python()
                assert info.is_available
                assert info.version == "Python 3.14.13"
                assert info.failure_reason is None

    def test_python_not_found(self) -> None:
        """測試所有候選與 uv fallback 皆未找到 Python.

        W9-001：多候選邏輯下，PATH 無任何候選且 uv 不可用時，回傳統一
        「未找到」失敗原因（原版單一 python3 的「未在 PATH」訊息已不適用）。
        """
        with patch("shutil.which", return_value=None):
            info = detect_python()
            assert not info.is_available
            assert "未找到 Python" in info.failure_reason

    def test_python_version_command_failed(self) -> None:
        """測試所有候選 --version 皆回非零（含 uv fallback 失敗）→ 統一未找到."""
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)
                info = detect_python()
                assert not info.is_available
                assert "未找到 Python" in info.failure_reason

    def test_python_timeout(self) -> None:
        """測試候選與 uv fallback 皆超時 → 統一未找到（超時被靜默吞並續試）."""
        import subprocess
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("python3", 5)
                info = detect_python()
                assert not info.is_available
                assert "未找到 Python" in info.failure_reason

    def test_python_generic_error(self) -> None:
        """測試 Python 偵測一般例外（非 Timeout/OSError 冒泡至外層 handler）."""
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Permission denied")
                info = detect_python()
                assert not info.is_available
                assert "偵測失敗" in info.failure_reason

    def test_python_found_via_uv_fallback(self) -> None:
        """W9-001：PATH 無 python 候選，但 uv python find 找到 → 偵測成功."""
        def which_side(name):
            return "/usr/local/bin/uv" if name == "uv" else None

        with patch("shutil.which", side_effect=which_side):
            with patch("subprocess.run") as mock_run:
                # 第一次: uv python find → 回傳路徑; 第二次: <path> --version
                mock_run.side_effect = [
                    MagicMock(returncode=0, stdout="/uv/managed/python3\n"),
                    MagicMock(returncode=0, stdout="Python 3.14.3\n"),
                ]
                info = detect_python()
                assert info.is_available
                assert info.version == "Python 3.14.3"
                assert info.path == "/uv/managed/python3"

    def test_python_windows_uses_python_exe_candidate(self) -> None:
        """W9-001：Windows 候選以 python（非 python3）優先，涵蓋 python.exe."""
        tried = []

        def which_side(name):
            tried.append(name)
            return "C:/Python/python.exe" if name == "python" else None

        with patch("platform.system", return_value="Windows"):
            with patch("shutil.which", side_effect=which_side):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="Python 3.14.3\n"
                    )
                    info = detect_python()
                    assert info.is_available
                    assert info.path == "C:/Python/python.exe"
                    assert tried[0] == "python"  # Windows 首候選為 python


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
            version="3.14.13",
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
