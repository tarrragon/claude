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
    """Python 版本字串 (如 '3.14.13')."""
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


def _query_python_version(executable: str) -> Optional[PythonInfo]:
    """查詢單一 Python 執行檔的版本；失敗回傳 None（不丟 Timeout/OSError）。

    Note:
        部分 Python 版本將版本字串輸出至 stderr，故 stdout 為空時取 stderr。
    """
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    version = (result.stdout or result.stderr).strip()
    return PythonInfo(version=version, path=executable, is_available=True)


def detect_python() -> PythonInfo:
    """偵測 Python 版本和路徑（OS 感知多候選 + uv fallback）。

    Why（W9-001 跨平台）：原版只查 `shutil.which("python3")`，但 Windows
    的執行檔名為 `python.exe`（無 python3），且 uv 下載的 Python 不進系統
    PATH，導致正常 Windows 環境被誤判「未安裝」（framework issue #1 問題1）。
    改為多候選命令（Windows: python/python3/py；類 Unix: python3/python），
    全部 miss 時 fallback `uv python find` 以涵蓋 uv 管理但不在 PATH 的
    Python。

    Returns:
        PythonInfo: Python 環境資訊。若未找到，is_available 為 False。
    """
    try:
        if platform.system() == "Windows":
            candidates = ["python", "python3", "py"]
        else:
            candidates = ["python3", "python"]
        for name in candidates:
            resolved = shutil.which(name)
            if not resolved:
                continue
            info = _query_python_version(resolved)
            if info is not None:
                return info

        # fallback：uv 管理的 Python 可能不在系統 PATH。
        if shutil.which("uv"):
            try:
                found = subprocess.run(
                    ["uv", "python", "find"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except (subprocess.TimeoutExpired, OSError):
                found = None
            if found is not None and found.returncode == 0 and found.stdout.strip():
                info = _query_python_version(found.stdout.strip())
                if info is not None:
                    return info

        return PythonInfo(
            version="",
            path=None,
            is_available=False,
            failure_reason="未找到 Python（已嘗試 PATH 候選與 uv 管理的 Python）",
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
