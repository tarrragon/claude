"""
Ticket Parser - Ticket frontmatter 欄位提取和型別判斷

負責從 Ticket frontmatter 提取 children、status、type 等欄位，
以及判斷 Ticket 類型（DOC/ANA）。
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from lib import parse_ticket_date

# 讀寫意圖標記剝離改 import ticket_system 共用實作：本模組屬
# acceptance_checkers 套件，已透過上方 sys.path.insert 取得 `.claude/hooks`
# 存取權，比照同一手法加掛 skill 目錄後即可直接 import ticket_system，
# 不需就地複製正則（PEP 723 單檔限制的是依賴解析，不限制 sys.path 操作）。
_TICKET_SYSTEM_SKILL_DIR = _hooks_dir.parent / "skills" / "ticket"
if str(_TICKET_SYSTEM_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_TICKET_SYSTEM_SKILL_DIR))
from ticket_system.lib.file_conflict import parse_file_intent as _parse_file_intent  # noqa: E402


def extract_children_from_frontmatter(frontmatter: dict, logger) -> List[str]:
    """
    從 frontmatter 提取 children 欄位

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        list - 子任務 ID 清單
    """
    children_raw = frontmatter.get("children", [])

    # YAML 解析後可能是 list 或 string（取決於解析器）
    if isinstance(children_raw, list):
        # 已解析為 list：過濾空值
        children = [str(c).strip() for c in children_raw if c]
    elif isinstance(children_raw, str):
        children_str = children_raw.strip()
        if not children_str or children_str == "[]":
            logger.debug("Ticket 無 children 欄位")
            return []
        children = []
        # 路徑 1：inline YAML list 格式 [id1, id2]
        if children_str.startswith("[") and children_str.endswith("]"):
            inner = children_str[1:-1].strip()
            if inner:
                for item in inner.split(","):
                    cid = item.strip().strip("'\"")
                    if cid:
                        children.append(cid)
        else:
            lines = children_str.split("\n")
            if any(line.strip().startswith("-") for line in lines):
                # 路徑 2：多行 YAML 列表 (e.g., "- 0.31.0-W4-036.1\n- 0.31.0-W4-036.2")
                for line in lines:
                    line = line.strip()
                    if line.startswith("-"):
                        child_id = line[1:].strip()
                        if child_id:
                            children.append(child_id)
            else:
                # 路徑 3：單一純量寫法 (e.g., "children: 0.31.0-W4-036")，
                # 合法 YAML（schema 允許 list 欄位純量化，同 where.files
                # 已知結果），非手寫 parser 缺陷
                children.append(children_str)
    else:
        logger.debug("Ticket 無 children 欄位")
        return []

    if not children:
        logger.debug("Ticket 無 children 欄位")
        return []

    logger.info(f"提取 {len(children)} 個子任務: {children}")
    return children


# 0.2.1-W3-052.1：where.files 佔位符值（與 god_ticket_scale_checker /
# responsibility_scope_checker 共用同一份清單，避免三處各自維護）
_WHERE_FILES_PLACEHOLDERS = frozenset({"待定義", "TBD", "tbd"})


def extract_where_files(frontmatter: dict, logger) -> List[str]:
    """
    從 frontmatter 提取 `where.files` 欄位，正規化為去重、去佔位符的
    `list[str]`（0.2.1-W3-052.1：`god_ticket_scale_checker` /
    `responsibility_scope_checker` 共用）。

    `where.files` 在 frontmatter 中可能是 `list[str]` 或 `str`，兩者皆為
    schema 容忍的合法寫法，非解析器缺陷：
    - `list[str]`：YAML sequence 寫法（`files:\n  - a.py\n  - b.py`）
    - `str`：YAML scalar 寫法——單一路徑不加 `-` dash（`files: a.py`），
      或 `|` block literal scalar（`files: |\n  a.py\n  b.py`）。
      `yaml.safe_load` 對此兩種 scalar 寫法皆正確回傳 str（非解析失敗，
      實測 `yaml.safe_load("files: a.py")` 回 `{'files': 'a.py'}`），
      故 `where.files` 若只寫單一檔案、或以 block scalar 呈現多行路徑，
      恆會呈現為 str。若呼叫端只用 `isinstance(x, list)` 判斷會將此類
      合法輸入靜默視為空清單。
      此正規化函式即為統一處理兩種型別的單一入口，比照
      `extract_children_from_frontmatter` 既有的「同欄位可為 list 或
      scalar 寫法」慣例（見本檔案上方）。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    路徑結尾的讀寫意圖標記（`::read` / `::write`）於去重之前剝離，使
    `a.py::read` 與 `a.py::write` 正規化為同一路徑 `a.py`（若剝離晚於
    去重，兩者會被誤判為相異路徑而各自保留）。本函式回傳完整影響集
    （不分讀寫），僅供需要「本 ticket 觸及哪些路徑」的呼叫端使用；需要
    區分讀寫意圖者見 `extract_where_files_write_only`。

    Returns:
        List[str] - 正規化後的有效檔案路徑清單（去重、去空白、去佔位符、
        去意圖標記；可能為空 list）
    """
    return [path for path, _ in _extract_where_file_intents(frontmatter, logger)]


def extract_where_files_write_only(frontmatter: dict, logger) -> List[str]:
    """從 frontmatter 提取 `where.files` 中意圖為「寫入」的路徑清單。

    未標記與以 `::write` 標記的路徑視為寫入（預設寫入，與
    `file_conflict.py` 的 IMP/DOC/ADJ 型別預設一致，本函式不依 ticket
    type 推導，呼叫端限防護類 hook acceptance 檢查，該情境只適用 IMP
    型 ticket）；以 `::read` 標記者排除。

    僅供需要區分讀寫意圖以決定是否觸發防護類要求的呼叫端使用（目前僅
    `hook_protection_acceptance_checker`），其餘四個 `extract_where_files`
    呼叫端要的是完整影響集，不得改用本函式。

    Returns:
        List[str] - 正規化後的寫入路徑清單（去重、去空白、去佔位符、去
        意圖標記；可能為空 list）
    """
    return [
        path
        for path, intent in _extract_where_file_intents(frontmatter, logger)
        if intent != "read"
    ]


def _extract_where_file_intents(frontmatter: dict, logger) -> List[Tuple[str, Optional[str]]]:
    """`extract_where_files` / `extract_where_files_write_only` 共用的內部
    正規化實作：回傳 (路徑, 意圖) tuple 清單，意圖為 `"read"` / `"write"`
    / `None`（未標記）。
    """
    where = frontmatter.get("where")
    if not isinstance(where, dict):
        return []

    files_raw = where.get("files")
    if isinstance(files_raw, list):
        candidates = [f for f in files_raw if isinstance(f, str)]
    elif isinstance(files_raw, str):
        candidates = files_raw.split("\n")
    else:
        return []

    seen = set()
    result: List[Tuple[str, Optional[str]]] = []
    for f in candidates:
        raw_stripped = f.strip()
        if not raw_stripped or raw_stripped in _WHERE_FILES_PLACEHOLDERS:
            continue
        path, intent = _parse_file_intent(raw_stripped)
        path = path.strip()
        if not path or path in _WHERE_FILES_PLACEHOLDERS:
            continue
        if path not in seen:
            seen.add(path)
            result.append((path, intent))

    if result:
        logger.debug(f"where.files 正規化後 {len(result)} 個有效路徑")
    return result


def get_ticket_status(frontmatter: dict, logger) -> Optional[str]:
    """
    從 Ticket frontmatter 提取狀態

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        str - Ticket 狀態或 None
    """
    status = frontmatter.get("status")

    if status:
        logger.debug(f"Ticket 狀態: {status}")

    return status


def get_ticket_type(frontmatter: dict, logger) -> Optional[str]:
    """
    從 Ticket frontmatter 提取型別

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        str - Ticket 型別或 None
    """
    ticket_type = frontmatter.get("type")

    if ticket_type:
        logger.debug(f"Ticket 型別: {ticket_type}")

    return ticket_type


def is_doc_type(ticket_type: Optional[str]) -> bool:
    """判斷是否為 DOC 類型 Ticket"""
    return ticket_type is not None and ticket_type.upper() == "DOC"


def is_ana_type(ticket_type: Optional[str]) -> bool:
    """判斷是否為 ANA 類型 Ticket"""
    return ticket_type is not None and ticket_type.upper() == "ANA"


def get_ticket_start_time(frontmatter: dict, logger) -> Optional[datetime]:
    """取得 Ticket 開始執行的時間，用於 error-pattern 偵測基準。

    優先使用 started_at（認領時間，有精確時間戳），
    fallback 到 created（建立時間，僅日期精度）。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        datetime 物件或 None（無法解析時）
    """
    try:
        # 優先使用 started_at（精確時間戳）
        started_at = frontmatter.get("started_at")
        if started_at:
            dt = parse_ticket_date(started_at, logger)
            if dt:
                logger.info(f"使用 started_at 作為 error-pattern 偵測基準: {dt.isoformat()}")
                return dt

        # Fallback 到 created（僅日期精度）
        logger.info("started_at 不可用，fallback 到 created")
        created_value = frontmatter.get("created")
        if not created_value:
            logger.warning("Ticket frontmatter 缺少 created 欄位")
            return None

        dt = parse_ticket_date(created_value, logger)
        if dt:
            logger.info(f"使用 created 作為 error-pattern 偵測基準: {dt.isoformat()}")
        return dt

    except Exception as e:
        logger.warning(f"解析 ticket 開始時間失敗: {e}")
        sys.stderr.write(f"WARNING: 解析 ticket 開始時間失敗: {e}\n")
        return None
