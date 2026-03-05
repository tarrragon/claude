"""測試環境設定例外類別。

驗證例外類別的建構、屬性和訊息格式。
"""

import pytest
from project_init.lib.exceptions import (
    ConfigurationError,
    DiskSpaceError,
    EnvironmentSetupError,
    ExecutionError,
    NetworkError,
    PermissionDeniedError,
    ToolNotFoundError,
    VersionTooOldError,
)


class TestEnvironmentSetupError:
    """測試基底例外類別."""

    def test_init_with_guidance(self) -> None:
        """測試帶指導的例外初始化."""
        guidance = ["步驟 1", "步驟 2"]
        exc = EnvironmentSetupError("Python", "版本過舊", guidance)
        assert exc.tool == "Python"
        assert exc.reason == "版本過舊"
        assert exc.guidance == guidance

    def test_init_without_guidance(self) -> None:
        """測試無指導的例外初始化."""
        exc = EnvironmentSetupError("UV", "未安裝")
        assert exc.tool == "UV"
        assert exc.reason == "未安裝"
        assert exc.guidance == []

    def test_str_representation(self) -> None:
        """測試字串表示."""
        exc = EnvironmentSetupError("Python", "版本過舊")
        assert str(exc) == "Python: 版本過舊"

    def test_get_full_message_without_guidance(self) -> None:
        """測試不含指導的完整訊息."""
        exc = EnvironmentSetupError("Python", "版本過舊")
        message = exc.get_full_message()
        assert "Python: 版本過舊" in message
        assert "修復步驟" not in message

    def test_get_full_message_with_guidance(self) -> None:
        """測試含指導的完整訊息."""
        guidance = ["安裝 Python 3.11", "驗證安裝"]
        exc = EnvironmentSetupError("Python", "版本過舊", guidance)
        message = exc.get_full_message()
        assert "Python: 版本過舊" in message
        assert "修復步驟:" in message
        assert "1. 安裝 Python 3.11" in message
        assert "2. 驗證安裝" in message


class TestToolNotFoundError:
    """測試工具未找到例外."""

    def test_inheritance(self) -> None:
        """測試例外繼承."""
        exc = ToolNotFoundError("Python", "python3 命令未找到")
        assert isinstance(exc, EnvironmentSetupError)

    def test_tool_not_found(self) -> None:
        """測試工具未找到屬性."""
        exc = ToolNotFoundError("ripgrep", "rg 命令未在 PATH 中找到")
        assert exc.tool == "ripgrep"
        assert "rg 命令" in exc.reason


class TestVersionTooOldError:
    """測試版本過舊例外."""

    def test_version_too_old(self) -> None:
        """測試版本過舊屬性."""
        guidance = ["升級 UV"]
        exc = VersionTooOldError("UV", "版本 0.0.5 太舊，需要 0.1.0+", guidance)
        assert exc.tool == "UV"
        assert "0.0.5" in exc.reason
        assert exc.guidance == guidance


class TestPermissionDeniedError:
    """測試權限被拒例外."""

    def test_permission_denied(self) -> None:
        """測試權限被拒屬性."""
        exc = PermissionDeniedError(
            "安裝目錄", "權限被拒：無法寫入 /usr/local/bin"
        )
        assert exc.tool == "安裝目錄"
        assert "無法寫入" in exc.reason


class TestNetworkError:
    """測試網路錯誤例外."""

    def test_network_error(self) -> None:
        """測試網路錯誤屬性."""
        exc = NetworkError("套件下載", "連接超時：無法連接到 PyPI")
        assert exc.tool == "套件下載"
        assert "超時" in exc.reason


class TestDiskSpaceError:
    """測試磁碟空間不足例外."""

    def test_disk_space_error(self) -> None:
        """測試磁碟空間不足屬性."""
        guidance = ["清理磁碟空間", "重新執行安裝"]
        exc = DiskSpaceError("安裝", "磁碟空間不足", guidance)
        assert exc.tool == "安裝"
        assert exc.reason == "磁碟空間不足"
        assert len(exc.guidance) == 2


class TestConfigurationError:
    """測試設定錯誤例外."""

    def test_configuration_error(self) -> None:
        """測試設定錯誤屬性."""
        exc = ConfigurationError("環境", "缺少 PYTHON_HOME 環境變數")
        assert exc.tool == "環境"
        assert "環境變數" in exc.reason


class TestExecutionError:
    """測試執行錯誤例外."""

    def test_execution_error(self) -> None:
        """測試執行錯誤屬性."""
        exc = ExecutionError("命令", "uv --version 回傳代碼 1")
        assert exc.tool == "命令"
        assert "代碼 1" in exc.reason
