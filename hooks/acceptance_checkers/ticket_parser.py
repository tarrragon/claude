"""
Ticket Parser - Ticket frontmatter 欄位提取和型別判斷

負責從 Ticket frontmatter 提取 children、status、type 等欄位，
以及判斷 Ticket 類型（DOC/ANA）。
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# 加入 hooks 目錄（acceptance_checkers 的上層）
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from lib import parse_ticket_date


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
            # 路徑 2：多行 YAML 列表 (e.g., "- 0.31.0-W4-036.1\n- 0.31.0-W4-036.2")
            for line in children_str.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    child_id = line[1:].strip()
                    if child_id:
                        children.append(child_id)
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

    `where.files` 在不同解析器下呈現型別不同：
    - `list[str]`：完整 YAML 解析（如 `ticket track` CLI 內部使用的
      ticket_system parser）
    - 換行分隔字串：本 hook 套件內建輕量解析器
      `lib.hook_ticket.parse_ticket_frontmatter`（`acceptance-gate-hook.py`
      實際 runtime 使用者）對「dict 欄位內巢狀 block-style 列表」的已知限制
      —— `where: {files: [- a, - b]}` 這種巢狀列表會被 `_parse_yaml_lines`
      累積為單一換行字串而非 list（該函式頂層列表才會產出真正的 list；
      dict 內巢狀列表走不同分支，見該檔案 `_parse_yaml_lines` docstring）。
      實測驗證：runtime hook 對真實 ticket 檔案呼叫 `parse_ticket_frontmatter`
      時，`where['files']` 為 `'.claude/a.py\\n.claude/b.py'` 字串，而非
      `['.claude/a.py', '.claude/b.py']`；若呼叫端只用 `isinstance(x, list)`
      判斷會靜默視為空清單，兩個新 checker 在真實 complete 流程中永遠不觸發。
      此正規化函式即為修復此落差的單一入口，比照 `extract_children_from_frontmatter`
      既有的「同欄位跨解析器雙型別容忍」慣例（見本檔案上方）。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        List[str] - 正規化後的有效檔案路徑清單（去重、去空白、去佔位符；
        可能為空 list）
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
    result = []
    for f in candidates:
        stripped = f.strip()
        if not stripped or stripped in _WHERE_FILES_PLACEHOLDERS:
            continue
        if stripped not in seen:
            seen.add(stripped)
            result.append(stripped)

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
