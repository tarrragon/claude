"""Python 工具安裝指令產生器 — 根據平台產生安裝指令.

此模組不直接執行安裝，只產生對應平台的安裝指令字串。
支援工具：python3, uv, ripgrep
支援平台：macOS (Darwin), Linux, Windows
"""

from dataclasses import dataclass
from typing import Optional

from .env_detector import OsInfo


SUPPORTED_TOOLS = {"python3", "uv", "ripgrep"}

MINIMUM_PYTHON_VERSION = "3.11"
MINIMUM_UV_VERSION = "0.1.0"
MINIMUM_RIPGREP_VERSION = "13.0.0"


@dataclass
class InstallInstructions:
    """安裝指令資訊."""

    tool: str
    """工具名稱."""
    os_type: str
    """目標平台."""
    commands: list[str]
    """安裝命令列表 (可依序執行)."""
    notes: str
    """額外說明或注意事項."""


def get_install_instructions(tool: str, os_info: OsInfo) -> Optional[InstallInstructions]:
    """根據工具和 OS 產生安裝指令.

    Args:
        tool: 工具名稱 ('python3', 'uv', 'ripgrep')。
        os_info: 作業系統資訊 (含 system 欄位)。

    Returns:
        InstallInstructions: 包含平台特定的安裝指令和說明。
        如果工具不支援或 OS 不支援，回傳 None。
    """
    if tool not in SUPPORTED_TOOLS:
        return None

    os_type = os_info.system.lower()

    if os_type == "darwin":
        return _get_macos_instructions(tool)
    elif os_type == "linux":
        return _get_linux_instructions(tool)
    elif os_type == "windows":
        return _get_windows_instructions(tool)

    return None


def _get_macos_instructions(tool: str) -> InstallInstructions:
    """macOS (Homebrew) 安裝指令."""
    if tool == "python3":
        return InstallInstructions(
            tool="python3",
            os_type="macOS",
            commands=["brew install python@3.11"],
            notes="安裝 Python 3.11。若已存在，可用 `brew upgrade python@3.11`。",
        )
    elif tool == "uv":
        return InstallInstructions(
            tool="uv",
            os_type="macOS",
            commands=["brew install uv"],
            notes="安裝 UV 套件管理工具。若已存在，可用 `brew upgrade uv`。",
        )
    elif tool == "ripgrep":
        return InstallInstructions(
            tool="ripgrep",
            os_type="macOS",
            commands=["brew install ripgrep"],
            notes="安裝 ripgrep 搜尋工具。若已存在，可用 `brew upgrade ripgrep`。",
        )
    return None


def _get_linux_instructions(tool: str) -> InstallInstructions:
    """Linux 安裝指令 (apt-get 優先，fallback dnf)."""
    if tool == "python3":
        return InstallInstructions(
            tool="python3",
            os_type="Linux",
            commands=[
                "sudo apt-get update",
                "sudo apt-get install -y python3.11",
            ],
            notes="使用 apt-get (Debian/Ubuntu)。若系統使用 dnf (Fedora/RHEL)，改用: sudo dnf install -y python3.11",
        )
    elif tool == "uv":
        return InstallInstructions(
            tool="uv",
            os_type="Linux",
            commands=[
                "sudo apt-get update",
                "sudo apt-get install -y uv",
            ],
            notes="使用 apt-get。若系統使用 dnf，改用: sudo dnf install -y uv",
        )
    elif tool == "ripgrep":
        return InstallInstructions(
            tool="ripgrep",
            os_type="Linux",
            commands=[
                "sudo apt-get update",
                "sudo apt-get install -y ripgrep",
            ],
            notes="使用 apt-get。若系統使用 dnf，改用: sudo dnf install -y ripgrep",
        )
    return None


def _get_windows_instructions(tool: str) -> InstallInstructions:
    """Windows 安裝指令 (winget 或 scoop)."""
    if tool == "python3":
        return InstallInstructions(
            tool="python3",
            os_type="Windows",
            commands=[
                "winget install -e --id Python.Python.3.11",
            ],
            notes="使用 winget。若無 winget，可使用 scoop: scoop install python@3.11",
        )
    elif tool == "uv":
        return InstallInstructions(
            tool="uv",
            os_type="Windows",
            commands=[
                "winget install -e --id astral-sh.uv",
            ],
            notes="使用 winget。若無 winget，可使用 scoop: scoop install uv",
        )
    elif tool == "ripgrep":
        return InstallInstructions(
            tool="ripgrep",
            os_type="Windows",
            commands=[
                "winget install -e --id BurntSushi.ripgrep.MSVC",
            ],
            notes="使用 winget。若無 winget，可使用 scoop: scoop install ripgrep",
        )
    return None
