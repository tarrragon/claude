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
    驗證版本是否在 todolist.yaml 中註冊且狀態為 planned 或 active。

    背景：執行早已與版本解耦（lifecycle.py 對版本狀態零檢查），planned
    版本的票今天就能做，「planned = 要等啟用才能執行」的前提不成立。
    原僅收 active 的判準使版本範圍凍結閘門提示的出路「先登記下一版本
    再建票」成為死路——剛登記的版本狀態必為 planned，仍會被本函式拒絕。

    Args:
        version: 版本號（無 v 前綴，如 "0.17.4"）

    Returns:
        tuple[bool, str]: (是否通過驗證, 錯誤訊息)
        - todolist.yaml 不存在 → (True, "") — 向後相容
        - 版本已註冊且 planned 或 active → (True, "")
        - 版本未註冊 → (False, 錯誤訊息)
        - 版本已註冊但非 planned/active（如 completed） → (False, 錯誤訊息)
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
            if status in ("planned", "active"):
                return (True, "")
            error_msg = ErrorMessages.VERSION_NOT_ACTIVE.format(
                version=version, status=status
            )
            return (False, error_msg)

    error_msg = ErrorMessages.VERSION_NOT_REGISTERED.format(version=version)
    return (False, error_msg)


def determine_fallback_version(
    source_ticket: Optional[str] = None,
) -> Optional[tuple[str, str]]:
    """命中版本未註冊錯誤時，推導可繞過的候選版本。

    背景：版本歸屬引導依動詞分類選出的版本可能未在 todolist.yaml 註冊
    （如「新增」被歸類為功能而選到未開版的次版本），此時硬失敗訊息若無
    可執行的繞過指令，使用者只能自行推敲。本函式提供兩層推導依據：

    1. --source-ticket 的 ID 前綴：spawn 場景幾乎必填，且版本語意由 ID
       直接承載，不受 wave 編號跨版本重複所影響（實查已確認同一 wave
       編號會出現在多個版本目錄下，見對應 ticket Problem Analysis）。
    2. todolist.yaml 中狀態為 active 的當前進行中版本（get_current_version）。

    兩者皆須先確認已在 todolist.yaml 註冊，避免推導出另一個同樣未註冊
    的版本。

    Args:
        source_ticket: --source-ticket 參數值（可能為 None）

    Returns:
        Optional[tuple[str, str]]: (候選版本, 推導理由)；無可用候選時 None
    """
    from .ticket_validator import extract_version_from_ticket_id

    if source_ticket:
        extracted = extract_version_from_ticket_id(source_ticket)
        if extracted and is_version_registered(extracted):
            return (extracted, f"依 --source-ticket {source_ticket} 推導")

    current = get_current_version()
    if current:
        normalized = current[1:] if current.startswith("v") else current
        if is_version_registered(normalized):
            return (normalized, "目前進行中版本")

    return None


def is_version_registered(version: str) -> bool:
    """
    檢查版本是否已在 todolist.yaml 中註冊（不限狀態）。

    與 validate_version_registered() 不同：本函式只檢查「是否存在於
    todolist.yaml」，不檢查是否為 active。適用於 migrate 等允許遷入
    planned/active/completed 版本的場景——這些場景合法（如提前規劃跨版本
    遷移），只有完全未註冊的版本才需要阻擋並引導使用者先建立版本。

    Args:
        version: 版本號（無 v 前綴，如 "1.0.0"）

    Returns:
        bool: 已註冊，或 todolist.yaml 不存在（向後相容）時回傳 True；
              版本不在 todolist.yaml 的 versions 列表中則回傳 False
    """
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        return True

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning(
            f"is_version_registered: 解析 todolist.yaml 失敗 "
            f"({type(e).__name__}: {e})，跳過驗證"
        )
        return True

    versions_list = data.get("versions", [])
    return any(str(entry.get("version", "")) == version for entry in versions_list)


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
    """找目前 active 版本，回傳 patch +1（基準與 suggest_overflow_version 一致）。

    原實作相對「最新已完成版本」計算。版本推進後，completed 停留在舊
    版號而 active 已前進，對非功能動詞根票恆建議一個未在 todolist.yaml
    註冊的版本（如 completed 停在 0.0.3、active 已是 0.1.0 時建議
    0.0.4），且與版本範圍凍結閘門印出的溢出目標互相矛盾——兩者基準不
    同源。改為相對 active 版本計算，與 suggest_overflow_version 的
    patch+1 分支同一基準。

    WRAP 補充（canonical #55）：active 版本本身未凍結時，直接建議該
    active（不算 patch+1），消除「建議一個未在 todolist.yaml 註冊的
    版本」噪音；僅 active 已凍結時才走 patch+1 分支。
    """
    active = [
        v for v in versions
        if v.get("status") == "active"
    ]
    if not active:
        return None

    # 取第一個 active（與 _parse_todolist_active_version 的「當前版本」
    # 定義一致：多個 active 並行分支開發時，第一個為主線）
    latest = active[0]
    ver_str = str(latest.get("version", ""))

    if latest.get("scope") != "frozen":
        return (ver_str, "非功能動詞歸目前進行中版本（未凍結）")
    parts = ver_str.split(".")
    if len(parts) != 3:
        return None

    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None

    suggested = f"{major}.{minor}.{patch + 1}"

    # 若建議版本已存在（不限狀態），直接回傳該版本
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


def is_version_scope_frozen(version: str) -> bool:
    """判斷指定版本在 todolist.yaml 是否標記 scope: frozen。

    `scope` 為選填欄位，缺席即視為開放（向後相容）；只有明確值為
    `"frozen"` 才視為凍結。todolist.yaml 不存在或解析失敗時視為未凍結。

    Args:
        version: 版本號（無 v 前綴，如 "0.1.0"）

    Returns:
        bool: 該版本存在且 scope 欄位值為 "frozen" 時回傳 True；
        版本不存在、scope 缺席、scope 非 "frozen"、或檔案不存在/解析失敗
        時回傳 False
    """
    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        return False

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning(
            f"is_version_scope_frozen: 解析 todolist.yaml 失敗 "
            f"({type(e).__name__}: {e})，視為未凍結"
        )
        return False

    versions_list = data.get("versions", [])
    for entry in versions_list:
        if str(entry.get("version", "")) == version:
            return entry.get("scope") == "frozen"

    return False


def _version_tuple(version_str: str) -> Optional[tuple[int, int, int]]:
    """將 "X.Y.Z" 字串轉為可比較的整數元組，格式異常回傳 None。"""
    parts = version_str.split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


_OPEN_STATUSES = frozenset({"planned", "active"})


def find_open_successor(base_version: str) -> Optional[str]:
    """在 todolist.yaml 找排在 base_version 之後、狀態開放、未凍結的最小版本。

    WRAP 結論（canonical #55 觀測流）：溢出目標應優先路由至「最近的開放
    後繼版本」，只有全部後繼皆凍結或不存在時才回退動詞式 patch+1／
    minor+1 計算。「開放」定義為 status 屬 planned 或 active，且
    scope 欄位非 "frozen"（scope 缺席視為開放，向後相容）。

    Args:
        base_version: 基準版本號（無 v 前綴，如 "0.1.1"）

    Returns:
        Optional[str]: 最小的開放後繼版本號；無符合條件者或 todolist.yaml
        缺席/解析失敗時回傳 None（純函式，不拋例外）
    """
    base_tuple = _version_tuple(base_version)
    if base_tuple is None:
        return None

    root = get_project_root()
    todolist_path = root / "docs" / "todolist.yaml"
    if not todolist_path.exists():
        return None

    try:
        import yaml
        with open(todolist_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning(
            f"find_open_successor: 解析 todolist.yaml 失敗 "
            f"({type(e).__name__}: {e})，視為無開放後繼"
        )
        return None

    versions_list = data.get("versions", [])
    candidates: list[tuple[tuple[int, int, int], str]] = []
    for entry in versions_list:
        ver_str = str(entry.get("version", ""))
        ver_tuple = _version_tuple(ver_str)
        if ver_tuple is None or ver_tuple <= base_tuple:
            continue
        if entry.get("status") not in _OPEN_STATUSES:
            continue
        if entry.get("scope") == "frozen":
            continue
        candidates.append((ver_tuple, ver_str))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def suggest_overflow_version(
    frozen_version: str,
    ticket_type: str,
    action: str,
) -> Optional[tuple[str, str]]:
    """計算溢出目標版本：優先最近的開放後繼版本，其次動詞式計算。

    版本範圍凍結閘門擋下根票時，須告知使用者「該去哪個版本」而非只說
    「這裡不收票」。與 `suggest_version_for_ticket` 的差異在於基準點：
    後者查 todolist.yaml 找「最新已完成版本」或「有 proposals 的 active
    版本」，本函式相對「被擋下的這個凍結版本本身」計算，兩者服務不同
    情境（一個是建票起點引導，一個是被擋後的去處）。

    規則（WRAP canonical #55）：
    1. 先呼叫 `find_open_successor`：命中已註冊的開放後繼版本即直接
       採用，不需動詞分類判斷（避免建議未註冊版本的噪音）。
    2. 未命中時沿用舊規則（與 `_FEAT_ACTIONS` 分類一致）：
       - IMP 且 action 屬新功能動詞（實作/新增/建立/開發）→ minor+1.0
       - 其餘（含修復/改善/分析/文件） → patch+1

    Args:
        frozen_version: 被凍結的版本號（無 v 前綴，如 "0.1.0"）
        ticket_type: Ticket 類型（IMP, ANA, DOC 等）
        action: --action 參數值

    Returns:
        Optional[tuple[str, str]]: (溢出目標版本, 理由)；
        frozen_version 格式非 X.Y.Z 時回傳 None
    """
    parts = frozen_version.split(".")
    if len(parts) != 3:
        return None

    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None

    successor = find_open_successor(frozen_version)
    if successor:
        return (successor, "路由至最近的開放後繼版本")

    is_new_feature = ticket_type == "IMP" and action in _FEAT_ACTIONS

    if is_new_feature:
        return (f"{major}.{minor + 1}.0", "新功能歸下一個小版本（相對凍結版本 minor+1）")

    return (f"{major}.{minor}.{patch + 1}", "修復/改善/分析/文件類型歸下一個 patch（相對凍結版本 patch+1）")


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
