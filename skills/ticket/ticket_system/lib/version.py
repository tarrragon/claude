"""
版本管理模組

提供版本號的取得、解析和驗證功能。
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

from .constants import WORK_LOGS_DIR
from .paths import get_project_root
from .ui_constants import VERSION_PREFIX, VERSION_PREFIX_LENGTH


def get_current_version() -> Optional[str]:
    """
    自動偵測當前版本

    優先級：
    1. 解析 todolist.yaml 的 versions 列表，找 status=active 的第一個
    2. Fallback: 掃描 work-logs 目錄取最高版本號（向後相容）

    Returns:
        Optional[str]: 版本字串（如 "v0.31.0"），若無版本目錄返回 None

    Examples:
        >>> version = get_current_version()
        >>> version.startswith("v")
        True
    """
    version = _parse_todolist_active_version()
    if version:
        return version
    return _scan_worklog_directories()


def get_active_versions() -> list[str]:
    """
    回傳所有 status=active 的版本（支援分支並行開發）

    Returns:
        list[str]: 版本字串列表（如 ["v0.31.0"]），若無則回傳空列表
    """
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        # Fallback: 回傳目錄掃描的最高版本
        version = _scan_worklog_directories()
        return [version] if version else []

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        versions = data.get("versions", [])
        return [
            f"v{v['version']}"
            for v in versions
            if v.get("status") == "active"
        ]
    except Exception:
        version = _scan_worklog_directories()
        return [version] if version else []


def _parse_todolist_active_version() -> Optional[str]:
    """
    解析 todolist.yaml，回傳第一個 status=active 的版本

    Returns:
        Optional[str]: 版本字串（如 "v0.31.0"），解析失敗回傳 None
    """
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        return None

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 格式一：versions 列表（.claude 框架標準格式）
        versions = data.get("versions", [])
        for v in versions:
            if v.get("status") == "active":
                return f"v{v['version']}"

        # 格式二：current_version 頂層欄位（專案自訂格式）
        current_version = data.get("current_version")
        if current_version:
            version_str = str(current_version)
            if not version_str.startswith("v"):
                version_str = f"v{version_str}"
            return version_str
    except Exception as e:
        logger.warning(f"解析 todolist.yaml 失敗 ({type(e).__name__}: {e})，將使用目錄掃描方式偵測版本")

    return None


def _scan_worklog_directories() -> Optional[str]:
    """
    掃描 work-logs 目錄，找出版本號最高的目錄（Fallback 邏輯）

    Returns:
        Optional[str]: 版本字串（如 "v0.31.0"），若無版本目錄返回 None
    """
    root = get_project_root()
    work_logs = root / WORK_LOGS_DIR

    if not work_logs.exists():
        return None

    # 版本號格式正則
    version_pattern = re.compile(r"^v\d+\.\d+\.\d+$")

    # 蒐集版本目錄
    versions = [
        d.name for d in work_logs.iterdir()
        if d.is_dir() and version_pattern.match(d.name)
    ]

    if not versions:
        logger.warning("無法在 work-logs 目錄中找到版本目錄，請確保 docs/work-logs/v*/tickets 目錄存在")
        return None

    # 按版本號降序排列
    def version_key(v: str) -> tuple:
        """轉換版本字串為可比較的元組"""
        version_parts = v[1:].split(".")
        return tuple(int(p) for p in version_parts)

    versions.sort(key=version_key, reverse=True)
    selected_version = versions[0]

    logger.warning(
        f"使用目錄掃描的版本 {selected_version}（未從 todolist.yaml 找到 active 版本）。"
        f"提示：確保 docs/todolist.yaml 中 status=active 的版本配置正確"
    )

    return selected_version


def normalize_version(version_str: str) -> str:
    """
    標準化版本號（去除 'v' 前綴）。

    將版本號標準化為無 'v' 前綴的格式。
    如果輸入為空字串，直接返回空字串。

    Args:
        version_str: 版本號字串，可帶 'v' 前綴也可不帶

    Returns:
        str: 標準化後的版本號（無 'v' 前綴），
             如 "0.31.0"；空輸入返回空字串

    Examples:
        >>> normalize_version("v0.31.0")
        '0.31.0'
        >>> normalize_version("0.31.0")
        '0.31.0'
        >>> normalize_version("")
        ''
    """
    if not version_str:
        return ""

    version_str = version_str.strip()
    if version_str.lower().startswith("v"):
        version_str = version_str[1:]

    return version_str


def resolve_version(explicit_version: Optional[str] = None) -> Optional[str]:
    """
    解析版本號（優先級：明確指定 > 自動偵測）

    用於統一版本號解析邏輯，避免重複程式碼。
    版本號會被標準化為無 'v' 前綴的格式（如 "0.31.0"）。

    Args:
        explicit_version: 明確指定的版本號
                         可帶 'v' 前綴也可不帶

    Returns:
        Optional[str]: 標準化後的版本號（無 'v' 前綴），
                      若無法取得版本返回 None

    Examples:
        >>> resolve_version("v0.31.0")
        '0.31.0'
        >>> resolve_version("0.31.0")
        '0.31.0'
        >>> resolve_version(None)  # 自動偵測
        '0.31.0'
    """
    # 優先使用明確指定的版本
    version = explicit_version or get_current_version()

    if not version:
        return None

    # 標準化：移除 'v' 前綴
    if version.startswith(VERSION_PREFIX):
        version = version[VERSION_PREFIX_LENGTH:]

    return version


def require_version(explicit_version: Optional[str] = None) -> str:
    """
    要求版本號（失敗時拋出異常）

    用於需要版本號才能繼續執行的場景。
    與 resolve_version() 不同的是，此函式失敗時會拋出例外，
    確保呼叫者必須處理缺少版本號的情況。

    Args:
        explicit_version: 明確指定的版本號
                         可帶 'v' 前綴也可不帶

    Returns:
        str: 標準化後的版本號（無 'v' 前綴）

    Raises:
        ValueError: 無法取得版本號

    Examples:
        >>> require_version("v0.31.0")
        '0.31.0'
        >>> require_version(None)  # 自動偵測
        '0.31.0'
        >>> require_version()  # 如果偵測失敗會拋出異常
        Traceback (most recent call last):
        ...
        ValueError: 無法偵測版本，請使用 --version 指定
    """
    version = resolve_version(explicit_version)

    if not version:
        raise ValueError("無法偵測版本，請使用 --version 指定")

    return version


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
