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


def check_version_all_completed(
    version: str, tickets: Optional[list] = None
) -> tuple[bool, Optional[str]]:
    """
    檢查指定版本的所有 ticket 是否皆為終結狀態。

    Args:
        version: 版本號（無 v 前綴，如 "1.3.0"）
        tickets: 已載入的 ticket 清單；None 時自行 list_tickets。

    Returns:
        tuple[bool, Optional[str]]:
            - bool: 是否全部終結（completed / closed）
            - Optional[str]: 下一個 active 版本 ID（無 v 前綴），若無則 None
    """
    from .constants import TERMINAL_STATUSES

    if tickets is None:
        from .ticket_loader import list_tickets
        tickets = list_tickets(version)
    if not tickets:
        return (False, None)

    all_terminal = all(
        t.get("status", "pending") in TERMINAL_STATUSES
        for t in tickets
    )

    if not all_terminal:
        return (False, None)

    next_version = _find_next_active_version(version)
    return (True, next_version)


def _find_next_active_version(current_version: str) -> Optional[str]:
    """
    從 todolist.yaml 找出排在 current_version 之後的第一個 active 版本。

    Returns:
        Optional[str]: 版本號（無 v 前綴），若無則 None
    """
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        return None

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        versions = data.get("versions", [])
        found_current = False
        for v in versions:
            v_str = str(v.get("version", ""))
            if v_str == current_version:
                found_current = True
                continue
            if found_current and v.get("status") == "active":
                return v_str
        # current 可能排第一，往前找其他 active
        for v in versions:
            v_str = str(v.get("version", ""))
            if v_str == current_version:
                continue
            if v.get("status") == "active":
                return v_str
    except Exception:
        pass

    return None


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

    # 蒐集版本目錄（支援階層結構和舊式平行結構）
    versions = []
    # 新式階層：docs/work-logs/v{major}/v{major}.{minor}/v{version}/
    for major_dir in work_logs.iterdir():
        if not major_dir.is_dir() or not major_dir.name.startswith("v"):
            continue
        for minor_dir in major_dir.iterdir():
            if not minor_dir.is_dir() or not minor_dir.name.startswith("v"):
                continue
            for patch_dir in minor_dir.iterdir():
                if patch_dir.is_dir() and version_pattern.match(patch_dir.name):
                    versions.append(patch_dir.name)
    # 舊式平行：docs/work-logs/v{version}/（向後相容）
    for d in work_logs.iterdir():
        if d.is_dir() and version_pattern.match(d.name) and d.name not in versions:
            versions.append(d.name)

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


def validate_version_registered(version: str) -> tuple[bool, str]:
    """
    驗證版本是否在 todolist.yaml 中註冊且狀態為 active。

    Args:
        version: 版本號（無 v 前綴，如 "0.17.4"）

    Returns:
        tuple[bool, str]: (是否通過驗證, 錯誤訊息)
        - todolist.yaml 不存在 → (True, "") — 向後相容
        - 版本已註冊且 active → (True, "")
        - 版本未註冊 → (False, 錯誤訊息)
        - 版本已註冊但非 active → (False, 錯誤訊息)
    """
    from .messages import ErrorMessages

    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        return (True, "")

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning(
            f"validate_version_registered: 解析 todolist.yaml 失敗 "
            f"({type(e).__name__}: {e})，跳過驗證"
        )
        return (True, "")

    versions_list = data.get("versions", [])
    for entry in versions_list:
        entry_version = str(entry.get("version", ""))
        if entry_version == version:
            status = entry.get("status", "")
            if status == "active":
                return (True, "")
            error_msg = ErrorMessages.VERSION_NOT_ACTIVE.format(
                version=version, status=status
            )
            return (False, error_msg)

    error_msg = ErrorMessages.VERSION_NOT_REGISTERED.format(version=version)
    return (False, error_msg)


_FEAT_ACTIONS = frozenset({"實作", "新增", "建立", "開發"})
_PATCH_TYPES = frozenset({"ANA", "ADJ", "DOC", "RES"})


def suggest_version_for_ticket(
    ticket_type: str,
    action: str,
) -> Optional[tuple[str, str]]:
    """根據 ticket 類型和 action 建議目標版本。

    規則：
    - 新功能（IMP + 實作/新增/建立/開發）→ 下一個大版本（0.x+1.0）
    - 修復/改善/分析/文件 → 最新已完成版本 +1 patch（0.x.y+1）
    - ANA/ADJ/DOC/RES 類型 → 一律 patch

    Args:
        ticket_type: Ticket 類型（IMP, ANA, DOC 等）
        action: --action 參數值（如「實作」「修復」「分析」）

    Returns:
        (suggested_version, reason) 或 None（無法判斷）
    """
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"
    if not todolist_path.exists():
        return None

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return None

    versions = data.get("versions", [])
    if not versions:
        return None

    is_new_feature = (
        ticket_type == "IMP" and action in _FEAT_ACTIONS
    )

    if is_new_feature or ticket_type == "INV":
        return _suggest_next_major(versions)

    if ticket_type in _PATCH_TYPES or not is_new_feature:
        return _suggest_next_patch(versions)

    return None


def _suggest_next_patch(
    versions: list[dict],
) -> Optional[tuple[str, str]]:
    """找最新已完成版本，回傳 patch +1。"""
    completed = [
        v for v in versions
        if v.get("status") == "completed"
    ]
    if not completed:
        return None

    latest = completed[-1]
    ver_str = str(latest.get("version", ""))
    parts = ver_str.split(".")
    if len(parts) != 3:
        return None

    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None

    suggested = f"{major}.{minor}.{patch + 1}"

    # 若建議版本已存在（active 或 completed），直接回傳該版本
    for v in versions:
        if str(v.get("version", "")) == suggested:
            return (suggested, "修復/改善/分析/文件類型歸小版本")

    return (suggested, "修復/改善/分析/文件類型歸小版本（版本尚未在 todolist 註冊）")


def _suggest_next_major(
    versions: list[dict],
) -> Optional[tuple[str, str]]:
    """找最高的大版本 active，或算出下一個大版本。"""
    active = [
        v for v in versions
        if v.get("status") == "active"
    ]
    # 找有 proposals 的 active 版本（大版本特徵）
    for v in active:
        if v.get("proposals"):
            return (str(v["version"]), "新功能歸大版本")

    # fallback: 取最高版本 minor+1
    all_vers = []
    for v in versions:
        ver_str = str(v.get("version", ""))
        parts = ver_str.split(".")
        if len(parts) == 3:
            try:
                all_vers.append((int(parts[0]), int(parts[1]), int(parts[2])))
            except ValueError:
                continue
    if not all_vers:
        return None

    max_ver = max(all_vers)
    suggested = f"{max_ver[0]}.{max_ver[1] + 1}.0"
    return (suggested, "新功能歸大版本")


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
