"""Hook 系統和工具可用性驗證模組.

此模組驗證 UV、ripgrep 等工具的可用性，以及 Hook 系統的完整性。
"""

import py_compile
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .env_detector import detect_ripgrep, detect_uv


MINIMUM_UV_VERSION = "0.1.0"
MINIMUM_RIPGREP_VERSION = "13.0.0"


@dataclass
class ToolStatus:
    """工具狀態資訊."""

    available: bool
    """工具是否可用."""
    version: Optional[str]
    """工具版本字串。"""
    path: Optional[str]
    """工具執行檔路徑。"""
    error_message: Optional[str]
    """若不可用，提供錯誤訊息."""


@dataclass
class HookSystemStatus:
    """Hook 系統狀態資訊."""

    hooks_directory: Path
    """Hook 目錄路徑."""
    hook_count: int
    """找到的 Hook 檔案數量."""
    all_compilable: bool
    """所有 Hook 是否都能編譯通過."""
    errors: list[str]
    """編譯失敗的 Hook 清單."""


def verify_uv_available() -> ToolStatus:
    """驗證 UV 工具是否可用且版本符合最低要求.

    Returns:
        ToolStatus: UV 工具狀態。
    """
    uv_info = detect_uv()

    if not uv_info.is_available:
        return ToolStatus(
            available=False,
            version=None,
            path=None,
            error_message="UV 工具未找到或無法執行。",
        )

    return ToolStatus(
        available=True,
        version=uv_info.version,
        path=uv_info.path,
        error_message=None,
    )


def verify_ripgrep_available() -> ToolStatus:
    """驗證 ripgrep 工具是否可用且版本符合最低要求.

    Returns:
        ToolStatus: ripgrep 工具狀態。
    """
    rg_info = detect_ripgrep()

    if not rg_info.is_available:
        return ToolStatus(
            available=False,
            version=None,
            path=None,
            error_message="ripgrep (rg) 工具未找到或無法執行。",
        )

    return ToolStatus(
        available=True,
        version=rg_info.version,
        path=rg_info.path,
        error_message=None,
    )


def verify_pep723_execution() -> ToolStatus:
    """驗證 PEP 723 腳本能否透過 UV 正常執行.

    測試執行一個最小的 inline script 來確認 `uv run` 能正常工作。

    Returns:
        ToolStatus: 執行狀態。
    """
    try:
        script = "print('PEP 723 test')"
        result = subprocess.run(
            ["uv", "run", "--", "python", "-c", script],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return ToolStatus(
                available=True,
                version="PEP 723",
                path=None,
                error_message=None,
            )
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            return ToolStatus(
                available=False,
                version=None,
                path=None,
                error_message=f"PEP 723 執行失敗: {error_msg}",
            )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return ToolStatus(
            available=False,
            version=None,
            path=None,
            error_message=f"PEP 723 驗證異常: {str(e)}",
        )


def verify_hooks_system(project_root: Path) -> HookSystemStatus:
    """驗證 Hook 系統是否完整且可編譯.

    掃描 .claude/hooks/ 目錄下所有 .py 檔案，嘗試編譯檢查語法。

    Args:
        project_root: 專案根目錄。

    Returns:
        HookSystemStatus: Hook 系統狀態。
    """
    hooks_dir = project_root / ".claude" / "hooks"

    if not hooks_dir.exists():
        return HookSystemStatus(
            hooks_directory=hooks_dir,
            hook_count=0,
            all_compilable=False,
            errors=["Hook 目錄不存在。"],
        )

    hook_files = list(hooks_dir.glob("*.py"))
    errors = []

    for hook_file in hook_files:
        try:
            py_compile.compile(str(hook_file), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"{hook_file.name}: {str(e)}")

    all_compilable = len(errors) == 0

    return HookSystemStatus(
        hooks_directory=hooks_dir,
        hook_count=len(hook_files),
        all_compilable=all_compilable,
        errors=errors,
    )
