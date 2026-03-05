"""環境偵測模組 — OS、Python、UV、ripgrep 版本檢查。

此模組提供一組偵測函式，用於檢查開發環境是否符合最低要求。
偵測失敗時回傳 available=False，而不拋異常。
"""

import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class OsInfo:
    """作業系統資訊."""

    system: str
    """OS 類型: 'Darwin' (macOS), 'Linux', 'Windows'."""
    version: str
    """OS 版本字串."""
    is_available: bool
    """是否成功偵測."""


@dataclass
class PythonInfo:
    """Python 環境資訊."""

    version: str
    """Python 版本字串 (如 '3.11.13')."""
    path: Optional[str]
    """Python 執行檔路徑."""
    is_available: bool
    """是否成功偵測."""
    failure_reason: Optional[str] = None
    """失敗原因（若 is_available 為 False）."""


@dataclass
class UvInfo:
    """UV 工具資訊."""

    version: str
    """UV 版本字串."""
    path: Optional[str]
    """UV 執行檔路徑."""
    is_available: bool
    """是否成功偵測."""
    failure_reason: Optional[str] = None
    """失敗原因（若 is_available 為 False）."""


@dataclass
class RipgrepInfo:
    """ripgrep 工具資訊."""

    version: str
    """ripgrep 版本字串."""
    path: Optional[str]
    """ripgrep 執行檔路徑."""
    is_available: bool
    """是否成功偵測."""
    failure_reason: Optional[str] = None
    """失敗原因（若 is_available 為 False）."""


def detect_os() -> OsInfo:
    """偵測作業系統類型和版本.

    Returns:
        OsInfo: 作業系統資訊物件。is_available 通常為 True（標準庫）。
    """
    try:
        system = platform.system()
        version = platform.release()
        return OsInfo(system=system, version=version, is_available=True)
    except Exception:
        return OsInfo(system="Unknown", version="", is_available=False)


def detect_python() -> PythonInfo:
    """偵測 Python 版本和路徑.

    檢查 `python3` 命令是否可用，並提取版本資訊。

    Returns:
        PythonInfo: Python 環境資訊。若未找到，is_available 為 False。
    """
    try:
        python_path = shutil.which("python3")
        if not python_path:
            return PythonInfo(
                version="",
                path=None,
                is_available=False,
                failure_reason="python3 命令未在 PATH 中找到",
            )

        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return PythonInfo(
                version="",
                path=python_path,
                is_available=False,
                failure_reason="無法執行 python3 --version 命令",
            )

        version = result.stdout.strip()
        return PythonInfo(
            version=version, path=python_path, is_available=True
        )
    except subprocess.TimeoutExpired:
        return PythonInfo(
            version="",
            path=None,
            is_available=False,
            failure_reason="執行 python3 --version 超時",
        )
    except Exception as e:
        return PythonInfo(
            version="",
            path=None,
            is_available=False,
            failure_reason=f"偵測失敗: {str(e)}",
        )


def detect_uv() -> UvInfo:
    """偵測 UV 工具版本和路徑.

    檢查 `uv --version` 命令是否可用。

    Returns:
        UvInfo: UV 工具資訊。若未找到，is_available 為 False。
    """
    try:
        uv_path = shutil.which("uv")
        if not uv_path:
            return UvInfo(
                version="",
                path=None,
                is_available=False,
                failure_reason="uv 命令未在 PATH 中找到",
            )

        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return UvInfo(
                version="",
                path=uv_path,
                is_available=False,
                failure_reason="無法執行 uv --version 命令",
            )

        version = result.stdout.strip()
        return UvInfo(version=version, path=uv_path, is_available=True)
    except subprocess.TimeoutExpired:
        return UvInfo(
            version="",
            path=None,
            is_available=False,
            failure_reason="執行 uv --version 超時",
        )
    except Exception as e:
        return UvInfo(
            version="",
            path=None,
            is_available=False,
            failure_reason=f"偵測失敗: {str(e)}",
        )


def detect_ripgrep() -> RipgrepInfo:
    """偵測 ripgrep 工具版本和路徑.

    偵測順序：
    1. shutil.which('rg') — 系統安裝的 ripgrep
    2. Claude Code bundled ripgrep — ~/.local/share/claude/versions/ 下的二進制

    Returns:
        RipgrepInfo: ripgrep 工具資訊。若未找到，is_available 為 False。
    """
    # 嘗試系統安裝的 rg
    rg_path = shutil.which("rg")
    if rg_path:
        try:
            result = subprocess.run(
                [rg_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0]
                return RipgrepInfo(
                    version=version, path=rg_path, is_available=True
                )
        except (subprocess.TimeoutExpired, Exception):
            pass

    # Fallback: Claude Code bundled ripgrep
    bundled = _detect_claude_bundled_ripgrep()
    if bundled:
        return bundled

    return RipgrepInfo(
        version="",
        path=None,
        is_available=False,
        failure_reason="rg 命令未在 PATH 中找到，Claude Code bundled ripgrep 也不可用",
    )


def _detect_claude_bundled_ripgrep() -> Optional[RipgrepInfo]:
    """偵測 Claude Code 內建的 ripgrep.

    Claude Code 將 rg 作為 shell alias 提供（claude_binary --ripgrep），
    Python subprocess 無法看到 alias，需直接查找二進制。

    Returns:
        RipgrepInfo 或 None。
    """
    from pathlib import Path

    claude_dir = Path.home() / ".local" / "share" / "claude" / "versions"
    if not claude_dir.exists():
        return None

    versions = sorted(claude_dir.iterdir(), reverse=True)
    for ver_path in versions:
        if not ver_path.is_file():
            continue
        try:
            result = subprocess.run(
                [str(ver_path), "--ripgrep", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0]
                return RipgrepInfo(
                    version=version,
                    path=f"{ver_path} --ripgrep",
                    is_available=True,
                )
        except (subprocess.TimeoutExpired, OSError):
            continue

    return None
