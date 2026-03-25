"""setup 指令 — 完整安裝/更新協調器.

檢查環境，執行必要的安裝/更新操作。
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from project_init.lib import (
    PackageMessages,
    RemediationGuidance,
    SetupMessages,
    check_installed_version,
    compare_versions,
    resolve_source_module_dir,
    detect_os,
    detect_python,
    detect_ripgrep,
    detect_uv,
    get_install_instructions,
    scan_custom_packages,
)
from project_init.commands.check import run_check

# 狀態標記常數
STATUS_OK = "[OK]"
STATUS_MISSING = "[MISSING]"
STATUS_OUTDATED = "[OUTDATED]"
STATUS_ERROR = "[ERROR]"

# 分隔線
SEPARATOR = "=" * 60
SUBSEPARATOR = "-" * 40


@dataclass
class SetupAction:
    """單個設定操作."""

    tool: str
    """工具名稱."""
    action_type: str
    """操作類型 ('install', 'update', 'none')."""
    status: str
    """狀態標記."""
    message: str
    """操作訊息."""


@dataclass
class SetupResult:
    """整個設定的結果."""

    all_ok: bool
    """是否設定完成或無需操作."""
    actions: list[SetupAction]
    """所有執行的操作."""
    auto_fixed: int
    """自動修復的項目數."""
    manual_required: int
    """需手動處理的項目數."""
    summary: str
    """簡單摘要."""


def run_setup(project_root: Path) -> SetupResult:
    """檢查環境，執行必要的安裝/更新操作.

    Args:
        project_root: 專案根目錄。

    Returns:
        SetupResult: 設定結果物件。同時輸出進度到 stdout。
    """
    _print_setup_header()
    check_result = run_check(project_root)

    if check_result.all_ok:
        return _handle_no_problems_needed()

    # 計算需要處理的項目
    problems = _identify_problems(project_root)

    # [2] 處理缺失工具
    print(SetupMessages.STEP_HANDLE_TOOLS)
    manual_required = _handle_missing_tools(problems)

    # [3] 更新自製套件
    print(SetupMessages.STEP_HANDLE_PACKAGES)
    auto_fixed = _handle_custom_packages(problems, project_root)

    return _finalize_setup_result(auto_fixed, manual_required)


def _print_setup_header() -> None:
    """輸出 setup 命令的標題."""
    print()
    print(SEPARATOR)
    print("project-init setup — 環境設定")
    print(SEPARATOR)
    print()
    print(SetupMessages.STEP_CHECK)


def _finalize_setup_result(auto_fixed: int, manual_required: int) -> SetupResult:
    """產生並輸出最終設定結果."""
    auto_fixed_str = SetupMessages.AUTO_FIXED.format(count=auto_fixed)
    manual_required_str = SetupMessages.MANUAL_REQUIRED.format(count=manual_required)
    summary = f"{auto_fixed_str}，{manual_required_str}"

    print(SEPARATOR)
    print(SetupMessages.COMPLETE_SUMMARY.format(summary=summary))
    print(SEPARATOR)
    print()

    return SetupResult(
        all_ok=auto_fixed > 0 or manual_required == 0,
        actions=[],
        auto_fixed=auto_fixed,
        manual_required=manual_required,
        summary=summary,
    )


def _handle_no_problems_needed() -> SetupResult:
    """處理環境已完整的情況."""
    print(SetupMessages.STEP_HANDLE_TOOLS)
    print()
    print(SEPARATOR)
    print(SetupMessages.UP_TO_DATE_SUMMARY)
    print(SEPARATOR)
    print()
    return SetupResult(
        all_ok=True,
        actions=[],
        auto_fixed=0,
        manual_required=0,
        summary=SetupMessages.UP_TO_DATE,
    )


def _handle_missing_tools(problems: dict) -> int:
    """處理缺失工具，輸出安裝指令.

    Args:
        problems: 由 _identify_problems 產生的問題字典。

    Returns:
        int: 需手動處理的工具數量。
    """
    manual_count = 0
    os_info = detect_os()

    for tool in ["python3", "uv", "ripgrep"]:
        if tool in problems["missing"]:
            instructions = get_install_instructions(tool, os_info)
            if instructions:
                manual_count += 1
                print(f"  {tool}: {STATUS_MISSING}")
                print(f"  {SetupMessages.INSTALL_COMPLETE_HEADER}:")
                for cmd in instructions.commands:
                    print(f"    {cmd}")
                print(f"  {SetupMessages.MANUAL_REQUIRED.replace('{count}', '')}說明:")
                print(f"    {instructions.notes}")
                print()

    return manual_count


def _handle_custom_packages(problems: dict, project_root: Path) -> int:
    """處理自製套件安裝和更新.

    Args:
        problems: 由 _identify_problems 產生的問題字典。
        project_root: 專案根目錄。

    Returns:
        int: 成功修復的套件數量。
    """
    auto_fixed = 0

    for package_name, action in problems["packages"].items():
        if action == "install":
            auto_fixed += _install_package(package_name, project_root)
        elif action == "update":
            auto_fixed += _update_package(package_name, project_root)

    return auto_fixed


def _install_package(package_name: str, project_root: Path) -> int:
    """安裝自製套件.

    Args:
        package_name: 套件名稱。
        project_root: 專案根目錄。

    Returns:
        int: 成功則回傳 1，失敗則回傳 0。
    """
    print(f"  {package_name}: {STATUS_MISSING} {SetupMessages.INSTALLING}")
    success = _run_uv_tool_install(project_root)
    if success:
        print(f"  → {STATUS_OK} {SetupMessages.INSTALL_SUCCESS}")
        print()
        return 1
    else:
        print(f"  → {STATUS_ERROR} {SetupMessages.INSTALL_FAILED}")
        print()
        return 0


def _update_package(package_name: str, project_root: Path) -> int:
    """更新自製套件.

    Args:
        package_name: 套件名稱。
        project_root: 專案根目錄。

    Returns:
        int: 成功則回傳 1，失敗則回傳 0。
    """
    print(f"  {package_name}: {STATUS_OUTDATED} {SetupMessages.UPDATING}")
    success = _run_uv_tool_install(project_root, force=True)
    if success:
        print(f"  → {STATUS_OK} {SetupMessages.UPDATE_SUCCESS}")
        print()
        return 1
    else:
        print(f"  → {STATUS_ERROR} {SetupMessages.UPDATE_FAILED}")
        print()
        return 0


def _identify_problems(project_root: Path) -> dict:
    """識別缺失和過時的項目.

    Returns:
        dict: {
            'missing': set of missing tool names,
            'packages': {package_name: 'install'|'update'|None}
        }
    """
    problems = {
        "missing": _identify_missing_tools(),
        "packages": _identify_package_problems(project_root),
    }
    return problems


def _identify_missing_tools() -> set[str]:
    """識別缺失的工具.

    Returns:
        set[str]: 缺失的工具名稱。
    """
    missing = set()

    if not detect_python().is_available:
        missing.add("python3")
    if not detect_uv().is_available:
        missing.add("uv")
    if not detect_ripgrep().is_available:
        missing.add("ripgrep")

    return missing


def _identify_package_problems(project_root: Path) -> dict[str, str | None]:
    """識別自製套件的問題.

    Args:
        project_root: 專案根目錄。

    Returns:
        dict: {package_name: 'install'|'update'|None}
    """
    packages_dict = {}

    for package in scan_custom_packages(project_root):
        lookup_name = package.package_name or package.name
        installed = check_installed_version(lookup_name, cli_name=package.cli_name)

        if installed is None:
            packages_dict[package.name] = "install"
        else:
            source_module = resolve_source_module_dir(
                package.source_path, installed.installed_path
            )
            compare_result = compare_versions(
                source_module, installed.installed_path
            )
            action = "update" if not compare_result.is_up_to_date else None
            packages_dict[package.name] = action

    return packages_dict


def _run_uv_tool_install(project_root: Path, force: bool = False) -> bool:
    """執行 uv tool install.

    Args:
        project_root: 專案根目錄。
        force: 是否使用 --force --reinstall 旗標。

    Returns:
        bool: 是否成功。
    """
    try:
        cmd = ["uv", "tool", "install", "."]
        if force:
            cmd.extend(["--force", "--reinstall"])

        result = subprocess.run(
            cmd,
            cwd=project_root / ".claude" / "skills" / "project-init",
            capture_output=True,
            text=True,
            timeout=60,
        )

        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False
