"""自製套件掃描及版本管理模組.

此模組用於掃描 .claude/skills/ 下的自製 Python 套件，並比對已安裝版本。
使用 SHA256 檔案雜湊進行版本比對。
"""

import hashlib
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# 導入共用掃描模組
_lib_path = Path(__file__).parent.parent.parent.parent.parent / 'lib'
sys.path.insert(0, str(_lib_path))

from pyproject_scanner import (
    scan_skills_directory,
    extract_version_from_pyproject,
    extract_package_name_from_pyproject,
    extract_cli_name_from_pyproject,
)


@dataclass
class PackageInfo:
    """自製套件資訊."""

    name: str
    """目錄名稱 (skill 目錄名)."""
    source_path: Path
    """套件原始碼位置 (含 pyproject.toml)."""
    version: Optional[str]
    """pyproject.toml 中定義的版本字串。"""
    package_name: Optional[str] = None
    """pyproject.toml 中的 [project] name（pip/uv 用的套件名）。"""
    cli_name: Optional[str] = None
    """pyproject.toml 中的 [project.scripts] 入口名稱（CLI 命令名）。"""


@dataclass
class InstalledInfo:
    """已安裝套件資訊."""

    name: str
    """套件名稱."""
    installed_path: Path
    """已安裝位置."""
    version: Optional[str]
    """已安裝版本。"""


@dataclass
class VersionCompareResult:
    """版本比對結果."""

    package_name: str
    """套件名稱."""
    is_up_to_date: bool
    """原始碼和已安裝版本是否一致 (SHA256 比對)."""
    source_hash: Optional[str]
    """原始碼的 SHA256 雜湊."""
    installed_hash: Optional[str]
    """已安裝版本的 SHA256 雜湊."""
    note: str
    """說明性文字."""


def scan_custom_packages(project_root: Path) -> list[PackageInfo]:
    """掃描 .claude/skills/ 下所有含 pyproject.toml 的套件.

    Args:
        project_root: 專案根目錄。

    Returns:
        list[PackageInfo]: 找到的所有自製套件清單。
    """
    packages: list[PackageInfo] = []
    
    # 使用共用模組掃描
    scanned = scan_skills_directory(project_root)
    
    # 轉換為 PackageInfo 格式
    for pkg_name, pkg_info in scanned.items():
        # 找到對應的 skill 目錄
        skill_dir = project_root / pkg_info["path"]
        pyproject_path = skill_dir / "pyproject.toml"
        
        if not skill_dir.exists() or not pyproject_path.exists():
            continue
        
        # 提取 CLI 名稱
        cli_name = extract_cli_name_from_pyproject(pyproject_path)
        
        packages.append(
            PackageInfo(
                name=skill_dir.name,
                source_path=skill_dir,
                version=pkg_info.get("version"),
                package_name=pkg_name,
                cli_name=cli_name,
            )
        )
    
    return sorted(packages, key=lambda p: p.name)


def check_installed_version(
    package_name: str,
    *,
    cli_name: Optional[str] = None,
) -> Optional[InstalledInfo]:
    """檢查全局安裝的套件版本.

    偵測順序：
    1. uv tool list（偵測 uv tool install 安裝的套件）
    2. pip show（偵測 pip install 安裝的套件）

    Args:
        package_name: 套件名稱（pyproject.toml 的 [project] name，如 'ticket-system'）。
        cli_name: CLI 命令名稱（如 'ticket'），用於 uv tool 路徑定位。

    Returns:
        InstalledInfo: 已安裝資訊。若未找到，回傳 None。
    """
    result = _check_via_uv_tool(package_name)
    if result is not None:
        return result

    return _check_via_pip(package_name)


def _check_via_uv_tool(package_name: str) -> Optional[InstalledInfo]:
    """透過 uv tool list 偵測套件.

    Args:
        package_name: pyproject.toml 中的套件名稱。

    Returns:
        InstalledInfo 或 None。
    """
    if not shutil.which("uv"):
        return None

    try:
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        # uv tool list 輸出格式：
        #   ticket-system v1.0.0
        #   - ticket
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.startswith("-") and package_name in line:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == package_name:
                    version = parts[1].lstrip("v")
                    installed_path = _find_uv_tool_site_packages(package_name)
                    if installed_path:
                        return InstalledInfo(
                            name=package_name,
                            installed_path=installed_path,
                            version=version,
                        )
    except (subprocess.TimeoutExpired, Exception):
        pass

    return None


def _locate_module_subdir(parent_dir: Path, module_name: str) -> Optional[Path]:
    """在父目錄下搜尋特定名稱的模組子目錄.

    用於定位已安裝模組或 source 目錄下的特定子目錄。
    若 parent_dir 下存在直接或深層嵌套的同名目錄，回傳第一個找到的。

    Args:
        parent_dir: 父目錄路徑。
        module_name: 欲搜尋的模組名稱。

    Returns:
        找到的模組子目錄 Path，或 None。
    """
    if not parent_dir.exists():
        return None

    for candidate in parent_dir.rglob(module_name):
        if candidate.is_dir():
            return candidate

    return None


def _find_uv_tool_site_packages(package_name: str) -> Optional[Path]:
    """定位 uv tool 安裝的套件 site-packages 路徑.

    Args:
        package_name: pyproject.toml 中的套件名稱。

    Returns:
        套件在 site-packages 下的路徑，或 None。
    """
    uv_tools_dir = Path.home() / ".local" / "share" / "uv" / "tools" / package_name
    if not uv_tools_dir.exists():
        return None

    # 搜尋 lib/pythonX.Y/site-packages/{package_module}/
    package_module = package_name.replace("-", "_")
    for site_packages in uv_tools_dir.rglob("site-packages"):
        candidate = _locate_module_subdir(site_packages, package_module)
        if candidate:
            return candidate

    return None


def _check_via_pip(package_name: str) -> Optional[InstalledInfo]:
    """透過 pip show 偵測套件.

    Args:
        package_name: 套件名稱。

    Returns:
        InstalledInfo 或 None。
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.split("\n")
        location = None
        version = None

        for line in lines:
            if line.startswith("Location:"):
                location = line.split(":", 1)[1].strip()
            elif line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()

        if not location:
            return None

        installed_path = Path(location) / package_name.replace("-", "_")
        return InstalledInfo(
            name=package_name,
            installed_path=installed_path,
            version=version,
        )
    except (subprocess.TimeoutExpired, Exception):
        return None


def resolve_source_module_dir(source_dir: Path, installed_dir: Path) -> Path:
    """從 skill 根目錄定位到與 installed 對應的模組子目錄.

    當 source_dir 是 skill 根目錄（含 pyproject.toml、tests/ 等），
    而 installed_dir 是 site-packages 下的模組目錄時，
    兩者的掃描範圍不對齊。此函式定位到 source_dir 下
    與 installed_dir 同名的模組子目錄，確保比較範圍一致。

    Args:
        source_dir: 原始碼目錄（skill 根目錄或模組子目錄）。
        installed_dir: 已安裝目錄（site-packages 下的模組目錄）。

    Returns:
        Path: 對齊後的 source 模組目錄。若無法定位則回傳原 source_dir。
    """
    if (source_dir / "pyproject.toml").exists():
        module_subdir = _locate_module_subdir(source_dir, installed_dir.name)
        if module_subdir:
            return module_subdir
    return source_dir


def compare_versions(
    source_dir: Path, installed_dir: Path
) -> VersionCompareResult:
    """使用 SHA256 比對兩個對等模組目錄.

    計算兩個目錄下所有 .py 檔案的 SHA256 雜湊，並比較。
    忽略 __pycache__ 和 .venv 目錄。

    兩個目錄應為對等的模組目錄（相同的檔案結構）。
    若需要從 skill 根目錄定位到模組子目錄，
    請先使用 resolve_source_module_dir()。

    Args:
        source_dir: 原始碼模組目錄。
        installed_dir: 已安裝模組目錄。

    Returns:
        VersionCompareResult: 版本比對結果。
    """
    package_name = source_dir.name

    source_hashes = _compute_file_hashes(source_dir)
    installed_hashes = _compute_file_hashes(installed_dir)

    source_hash = _hash_dict_to_string(source_hashes)
    installed_hash = _hash_dict_to_string(installed_hashes)

    is_up_to_date = source_hash == installed_hash

    if is_up_to_date:
        note = f"'{package_name}' 版本一致"
    else:
        note = f"'{package_name}' 需要重新安裝 (SHA256 雜湊不同)"

    return VersionCompareResult(
        package_name=package_name,
        is_up_to_date=is_up_to_date,
        source_hash=source_hash,
        installed_hash=installed_hash,
        note=note,
    )








def _compute_file_hashes(directory: Path) -> dict[str, str]:
    """計算目錄下所有 .py 檔案的 SHA256 雜湊.

    Args:
        directory: 目錄路徑。

    Returns:
        dict: {相對路徑: SHA256 雜湊} 的字典。
    """
    hashes = {}

    if not directory.exists():
        return hashes

    for py_file in sorted(directory.rglob("*.py")):
        if "__pycache__" in py_file.parts or ".venv" in py_file.parts:
            continue

        try:
            with open(py_file, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
                rel_path = py_file.relative_to(directory)
                hashes[str(rel_path)] = file_hash
        except Exception:
            continue

    return hashes


def _hash_dict_to_string(hashes: dict[str, str]) -> str:
    """將雜湊字典轉換為單一字串.

    將所有檔案雜湊合併為一個 SHA256 雜湊，用於版本比較。

    Args:
        hashes: {檔案路徑: 雜湊} 字典。

    Returns:
        str: 合併後的 SHA256 雜湊。
    """
    combined = ""
    for file_path in sorted(hashes.keys()):
        combined += f"{file_path}:{hashes[file_path]}\n"

    return hashlib.sha256(combined.encode()).hexdigest()
