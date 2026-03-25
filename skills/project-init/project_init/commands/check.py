"""check 指令 — 唯讀環境狀態掃描.

掃描並輸出環境完整狀態，不修改任何東西。
"""

from dataclasses import dataclass
from pathlib import Path

from project_init.lib import (
    CheckMessages,
    PackageMessages,
    PythonMessages,
    RemediationGuidance,
    RipgrepMessages,
    UVMessages,
    check_installed_version,
    compare_versions,
    resolve_source_module_dir,
    detect_os,
    detect_python,
    detect_ripgrep,
    detect_uv,
    scan_custom_packages,
    verify_hooks_system,
    verify_pep723_execution,
)

# 狀態標記常數
STATUS_OK = "[OK]"
STATUS_MISSING = "[MISSING]"
STATUS_OUTDATED = "[OUTDATED]"
STATUS_ERROR = "[ERROR]"

# 分隔線
SEPARATOR = "=" * 60
SUBSEPARATOR = "-" * 40


@dataclass
class SectionResult:
    """單個檢查區段的結果."""

    name: str
    """區段名稱 (如 'Python', 'UV')."""
    status: str
    """狀態 ([OK], [MISSING], [OUTDATED], [ERROR])."""
    details: list[str]
    """詳細訊息清單."""


@dataclass
class CheckResult:
    """整個檢查的結果."""

    all_ok: bool
    """是否所有項目都正常."""
    sections: list[SectionResult]
    """所有區段的結果."""
    summary: str
    """簡單摘要 (如 '6/6 項目正常')."""


def run_check(project_root: Path) -> CheckResult:
    """掃描並輸出環境完整狀態.

    Args:
        project_root: 專案根目錄。

    Returns:
        CheckResult: 檢查結果物件。同時輸出格式化文字到 stdout。
    """
    sections = _collect_all_sections(project_root)

    # 計算總結
    ok_count = sum(1 for s in sections if s.status == STATUS_OK)
    total_count = len(sections)
    all_ok = ok_count == total_count
    summary = f"{ok_count}/{total_count} 項目正常"

    result = CheckResult(all_ok=all_ok, sections=sections, summary=summary)

    # 輸出格式化結果
    _print_check_result(result)

    return result


def _collect_all_sections(project_root: Path) -> list[SectionResult]:
    """收集所有檢查區段.

    Args:
        project_root: 專案根目錄。

    Returns:
        list[SectionResult]: 所有區段的檢查結果。
    """
    return [
        _check_os(detect_os()),
        _check_python(detect_python()),
        _check_uv(detect_uv()),
        _check_ripgrep(detect_ripgrep()),
        _check_hooks_system(project_root),
        _check_custom_packages(project_root),
    ]


def _check_os(os_info) -> SectionResult:
    """檢查作業系統."""
    if not os_info.is_available:
        return SectionResult(
            name="OS",
            status=STATUS_ERROR,
            details=["無法偵測作業系統"],
        )

    os_type_friendly = {
        "Darwin": "macOS",
        "Linux": "Linux",
        "Windows": "Windows",
    }.get(os_info.system, os_info.system)

    return SectionResult(
        name="OS",
        status=STATUS_OK,
        details=[f"{os_type_friendly} {os_info.version}"],
    )


def _check_python(python_info) -> SectionResult:
    """檢查 Python."""
    if not python_info.is_available:
        details = [
            PythonMessages.NOT_INSTALLED,
            PythonMessages.NOT_INSTALLED_STATUS,
        ]
        if python_info.failure_reason:
            details.append(f"原因: {python_info.failure_reason}")
        details.extend([
            "",
            "修復步驟:",
        ])
        details.extend(RemediationGuidance.get_python_install_steps())
        return SectionResult(
            name="Python",
            status=STATUS_MISSING,
            details=details,
        )

    return SectionResult(
        name="Python",
        status=STATUS_OK,
        details=[
            f"版本: {python_info.version}",
            f"路徑: {python_info.path}",
        ],
    )


def _check_uv(uv_info) -> SectionResult:
    """檢查 UV."""
    if not uv_info.is_available:
        details = [
            UVMessages.NOT_INSTALLED,
            UVMessages.NOT_INSTALLED_STATUS,
        ]
        if uv_info.failure_reason:
            details.append(f"原因: {uv_info.failure_reason}")
        details.extend([
            "",
            "修復步驟:",
        ])
        details.extend(RemediationGuidance.get_uv_install_steps())
        return SectionResult(
            name="UV",
            status=STATUS_MISSING,
            details=details,
        )

    return SectionResult(
        name="UV",
        status=STATUS_OK,
        details=[
            f"版本: {uv_info.version}",
            f"路徑: {uv_info.path}",
        ],
    )


def _check_ripgrep(ripgrep_info) -> SectionResult:
    """檢查 ripgrep."""
    if not ripgrep_info.is_available:
        os_type = detect_os().system.lower()
        details = [
            RipgrepMessages.NOT_INSTALLED,
            RipgrepMessages.NOT_INSTALLED_STATUS,
        ]
        if ripgrep_info.failure_reason:
            details.append(f"原因: {ripgrep_info.failure_reason}")
        details.extend([
            "",
            "修復步驟:",
        ])
        details.extend(RemediationGuidance.get_ripgrep_install_steps(os_type))
        return SectionResult(
            name="ripgrep",
            status=STATUS_MISSING,
            details=details,
        )

    return SectionResult(
        name="ripgrep",
        status=STATUS_OK,
        details=[
            f"版本: {ripgrep_info.version}",
            f"路徑: {ripgrep_info.path}",
        ],
    )


def _check_hooks_system(project_root: Path) -> SectionResult:
    """檢查 Hook 系統."""
    hooks_status = verify_hooks_system(project_root)

    if not hooks_status.all_compilable:
        return SectionResult(
            name="Hook 系統",
            status=STATUS_ERROR,
            details=[
                f"Hook 數量: {hooks_status.hook_count}",
                f"編譯狀態: {len(hooks_status.errors)} 個失敗",
            ]
            + [f"  - {error}" for error in hooks_status.errors],
        )

    # 檢查 PEP 723
    pep723_status = verify_pep723_execution()
    pep723_ok = pep723_status.available

    details = [
        f"Hook 數量: {hooks_status.hook_count}",
        f"編譯狀態: 全部通過",
        f"PEP 723: {STATUS_OK if pep723_ok else STATUS_ERROR}",
    ]

    return SectionResult(
        name="Hook 系統",
        status=STATUS_OK if pep723_ok else STATUS_ERROR,
        details=details,
    )


def _check_custom_packages(project_root: Path) -> SectionResult:
    """檢查自製套件."""
    packages = scan_custom_packages(project_root)

    if not packages:
        return SectionResult(
            name="自製套件",
            status=STATUS_OK,
            details=["無自製套件"],
        )

    details = []
    all_ok = True

    for package in packages:
        is_ok = _check_single_package(package, details)
        if not is_ok:
            all_ok = False

    return SectionResult(
        name="自製套件",
        status=STATUS_OK if all_ok else STATUS_OUTDATED,
        details=details,
    )


def _check_single_package(package, details: list[str]) -> bool:
    """檢查單個套件.

    Args:
        package: PackageInfo 物件。
        details: 詳細訊息清單（會被修改）。

    Returns:
        bool: 套件是否已是最新。
    """
    lookup_name = package.package_name or package.name
    installed = check_installed_version(lookup_name, cli_name=package.cli_name)

    if installed is None:
        return _handle_package_not_installed(package, details)

    # 對齊 source 目錄到模組子目錄後比對版本
    source_module = resolve_source_module_dir(
        package.source_path, installed.installed_path
    )
    compare_result = compare_versions(
        source_module, installed.installed_path
    )
    return _handle_package_version_check(
        package, installed, compare_result, details
    )


def _handle_package_not_installed(package, details: list[str]) -> bool:
    """處理未安裝的套件."""
    details.append(PackageMessages.NOT_INSTALLED.format(
        name=package.name, version=package.version
    ))
    details.append(PackageMessages.NOT_INSTALLED_ACTION)
    return False


def _handle_package_version_check(
    package, installed, compare_result, details: list[str]
) -> bool:
    """處理套件版本檢查結果."""
    if compare_result.is_up_to_date:
        details.append(f"{package.name} ({installed.version}) {STATUS_OK}")
        return True

    details.append(PackageMessages.OUTDATED.format(
        name=package.name, version=installed.version
    ))
    details.append(PackageMessages.OUTDATED_ACTION)
    return False


def _print_check_result(result: CheckResult) -> None:
    """輸出格式化的檢查結果到 stdout."""
    print()
    print(SEPARATOR)
    print(CheckMessages.HEADER)
    print(SEPARATOR)
    print()

    for section in result.sections:
        print(f"[{section.name}]")
        if section.details:
            for detail in section.details:
                print(f"  {detail}")
        else:
            print(f"  狀態: {section.status}")
        print()

    print(SEPARATOR)
    print(CheckMessages.SUMMARY_TOTAL.format(summary=result.summary))
    print(SEPARATOR)
    print()
