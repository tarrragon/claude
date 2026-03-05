"""測試訊息常數模組。

驗證訊息常數的定義和使用。
"""

import pytest
from project_init.lib.messages import (
    CheckMessages,
    HookSystemMessages,
    OSMessages,
    PackageMessages,
    PythonMessages,
    RemediationGuidance,
    RipgrepMessages,
    SetupMessages,
    UVMessages,
)


class TestPythonMessages:
    """測試 Python 訊息常數."""

    def test_not_installed_message(self) -> None:
        """測試未安裝訊息."""
        assert PythonMessages.NOT_INSTALLED == "版本: 未安裝"

    def test_install_guidance(self) -> None:
        """測試安裝指導連結."""
        assert "python.org" in PythonMessages.INSTALL_GUIDANCE


class TestUVMessages:
    """測試 UV 訊息常數."""

    def test_not_installed_message(self) -> None:
        """測試未安裝訊息."""
        assert UVMessages.NOT_INSTALLED == "版本: 未安裝"

    def test_install_guidance(self) -> None:
        """測試安裝指導連結."""
        assert "astral.sh" in UVMessages.INSTALL_GUIDANCE


class TestRipgrepMessages:
    """測試 ripgrep 訊息常數."""

    def test_platform_specific_guidance(self) -> None:
        """測試平台特定的安裝指導."""
        assert RipgrepMessages.INSTALL_GUIDANCE_MACOS == "安裝指令: brew install ripgrep"
        assert RipgrepMessages.INSTALL_GUIDANCE_LINUX == "安裝指令: apt-get install ripgrep"


class TestPackageMessages:
    """測試套件訊息常數."""

    def test_not_installed_format(self) -> None:
        """測試未安裝訊息格式."""
        msg = PackageMessages.NOT_INSTALLED.format(name="ticket", version="0.1.0")
        assert "ticket" in msg
        assert "0.1.0" in msg
        assert "[MISSING]" in msg

    def test_outdated_format(self) -> None:
        """測試過時訊息格式."""
        msg = PackageMessages.OUTDATED.format(name="ticket", version="0.0.9")
        assert "ticket" in msg
        assert "0.0.9" in msg
        assert "[OUTDATED]" in msg


class TestSetupMessages:
    """測試 Setup 訊息常數."""

    def test_step_messages(self) -> None:
        """測試步驟訊息."""
        assert "[1/3]" in SetupMessages.STEP_CHECK
        assert "[2/3]" in SetupMessages.STEP_HANDLE_TOOLS
        assert "[3/3]" in SetupMessages.STEP_HANDLE_PACKAGES

    def test_auto_fixed_format(self) -> None:
        """測試自動修復訊息格式."""
        msg = SetupMessages.AUTO_FIXED.format(count=3)
        assert "3" in msg
        assert "自動修復" in msg

    def test_manual_required_format(self) -> None:
        """測試手動處理訊息格式."""
        msg = SetupMessages.MANUAL_REQUIRED.format(count=2)
        assert "2" in msg
        assert "手動處理" in msg


class TestCheckMessages:
    """測試 Check 訊息常數."""

    def test_header_message(self) -> None:
        """測試標題訊息."""
        assert "project-init check" in CheckMessages.HEADER
        assert "環境狀態報告" in CheckMessages.HEADER

    def test_summary_format(self) -> None:
        """測試摘要訊息格式."""
        msg = CheckMessages.SUMMARY_TOTAL.format(summary="6/6 項目正常")
        assert "6/6 項目正常" in msg


class TestRemediationGuidance:
    """測試修復指導."""

    def test_python_install_steps(self) -> None:
        """測試 Python 安裝步驟."""
        steps = RemediationGuidance.get_python_install_steps()
        assert len(steps) == 4
        assert any("python.org" in step for step in steps)
        assert any("3.14" in step for step in steps)

    def test_uv_install_steps(self) -> None:
        """測試 UV 安裝步驟."""
        steps = RemediationGuidance.get_uv_install_steps()
        assert len(steps) == 4
        assert any("docs.astral.sh" in step for step in steps)

    def test_ripgrep_macos_steps(self) -> None:
        """測試 macOS ripgrep 安裝步驟."""
        steps = RemediationGuidance.get_ripgrep_install_steps("darwin")
        assert len(steps) == 4
        assert any("brew" in step for step in steps)

    def test_ripgrep_linux_steps(self) -> None:
        """測試 Linux ripgrep 安裝步驟."""
        steps = RemediationGuidance.get_ripgrep_install_steps("linux")
        assert len(steps) == 5
        assert any("apt-get" in step or "dnf" in step or "pacman" in step for step in steps)

    def test_ripgrep_windows_steps(self) -> None:
        """測試 Windows ripgrep 安裝步驟."""
        steps = RemediationGuidance.get_ripgrep_install_steps("windows")
        assert len(steps) == 4
        assert any("winget" in step or "scoop" in step for step in steps)

    def test_ripgrep_default_is_windows(self) -> None:
        """測試未知平台預設為 Windows."""
        steps = RemediationGuidance.get_ripgrep_install_steps("unknown")
        assert any("winget" in step or "scoop" in step for step in steps)
