#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook Ticket 操作模組

提供 Ticket 檔案掃描、解析和驗證等功能。

核心 API：
- parse_ticket_frontmatter(content_or_path, logger)
- parse_ticket_date(value, logger)
- check_error_patterns_changed(project_root, ticket_created, logger)
- get_current_version_from_todolist(project_root, logger)
- scan_ticket_files_by_version(project_root, version, logger)
- find_ticket_files(project_root, version, logger)
- find_ticket_file(ticket_id, project_root, logger)
- extract_version_from_ticket_id(ticket_id)
- extract_wave_from_ticket_id(ticket_id)
- validate_ticket_has_decision_tree(ticket_content, logger)
"""

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, NamedTuple, Optional, Tuple, Union

from .hook_logging import get_project_root

# ============================================================================
# 常數定義
# ============================================================================

# 決策樹欄位識別標記（統一版本，合併 command-entrance-gate-hook 和 agent-ticket-validation-hook）
DECISION_TREE_MARKERS = [
    "decision_tree_path:",
    "## 決策樹路徑",
    "decision_nodes:",
    "## 決策樹",
    "## Decision Tree",
    "## 決策流程",
]


# ============================================================================
# 私有資料結構
# ============================================================================

class _NestedLineResult(NamedTuple):
    """_parse_nested_line 的回傳值結構

    表達嵌套行的解析結果，語義明確。
    """
    multiline_marker: Optional[str]  # 多行標記（|, >, |-, >-）或 None
    update_action: Optional[Tuple[str, Any, bool]]  # (鍵名, 值, 是否為嵌套字典) 或 None


# ============================================================================
# Ticket 解析函式
# ============================================================================

def _read_content(content_or_path: "Union[str, Path]", logger: Optional[logging.Logger]) -> Optional[str]:
    """讀取檔案或字串內容

    Args:
        content_or_path: 檔案路徑（Path）或內容字串（str）
        logger: 可選 Logger 實例

    Returns:
        str: 讀取的內容，或 None 如果讀取失敗
    """
    if isinstance(content_or_path, Path):
        try:
            return content_or_path.read_text(encoding='utf-8')
        except Exception as e:
            if logger:
                logger.warning("讀取檔案失敗 ({}): {}".format(content_or_path.name, e))
            return None
    else:
        return str(content_or_path) if content_or_path else ""


def _skip_empty_or_comment(line: str) -> bool:
    """判斷是否為空行或註解行（應跳過）

    Args:
        line: 單行字串

    Returns:
        bool: 若為空行或註解行則返回 True，應跳過
    """
    stripped = line.strip()
    return not stripped or stripped.startswith('#')


def _parse_nested_line(
    line: str,
    current_key: Optional[str],
    multiline_marker: Optional[str],
    current_nested_key: Optional[str] = None
) -> _NestedLineResult:
    """處理嵌套行（以 2 個空格開頭的縮排行）

    嵌套行可能是：
    1. 多行字串的延續行（若 multiline_marker 已設定）
    2. 嵌套鍵值對（若無 multiline_marker）
    3. 列表項目（以 "- " 開頭）

    此函式無副作用，回傳明確的結果以供呼叫端處理。

    Args:
        line: 嵌套行（縮排）
        current_key: 當前頂層鍵名
        multiline_marker: 多行標記（|, >, |-, >-）或 None
        current_nested_key: 當前嵌套鍵名（用於列表項目累積）

    Returns:
        _NestedLineResult: 含有：
            - multiline_marker: 多行標記（保留或清空）
            - update_action: (鍵名, 值, 是否為嵌套字典) 或 None
              當為多行模式時，值為增量內容（呼叫端需累積）
              當為嵌套鍵值對時，值為新增的鍵值對
              當為列表項目時，值為列表項目內容（呼叫端負責累積）
    """
    nested_line = line.strip()

    # 路徑 1：多行字串延續行
    if multiline_marker is not None:
        if current_key:
            # 回傳增量內容，呼叫端負責累積
            # 第一行（result[key] 為空）直接設定，後續行前面加換行符
            return _NestedLineResult(
                multiline_marker=multiline_marker,
                update_action=(current_key, nested_line, False)
            )
        else:
            # 無當前鍵，保留 multiline_marker 但無動作
            return _NestedLineResult(
                multiline_marker=multiline_marker,
                update_action=None
            )

    # 路徑 2：列表項目（以 "- " 開頭）
    if nested_line.startswith('- ') and current_nested_key and current_key:
        # 列表項目內容
        item_content = nested_line[2:]  # 去除 "- " 前綴
        # 特殊標記：使用 None 作為鍵名的第一個元素，表示這是列表項目
        # 呼叫端會識別 None 並累積到 current_nested_key
        return _NestedLineResult(
            multiline_marker=None,
            update_action=(current_nested_key, item_content, False)
        )

    # 路徑 3：嵌套鍵值對
    if ':' in nested_line:
        nested_key, nested_value = nested_line.split(':', 1)
        nested_key = nested_key.strip()
        nested_value = nested_value.strip().strip("'\"")

        if current_key:
            # 回傳嵌套鍵值對資訊
            return _NestedLineResult(
                multiline_marker=None,
                update_action=(current_key, {nested_key: nested_value}, True)
            )

    # 無 multiline_marker 也無冒號，無動作
    return _NestedLineResult(
        multiline_marker=None,
        update_action=None
    )


def _parse_yaml_lines(frontmatter_text: str) -> dict:
    """解析 YAML frontmatter 文本（逐行）

    支援列表項目：當遇到 "key:" 後跟著 "  - item" 格式的行時，
    會將這些項目累積到該鍵底下（以換行符分隔）。

    Args:
        frontmatter_text: frontmatter 內容（已去除---標記）

    Returns:
        dict: 解析出的 key-value 對
    """
    result = {}
    current_key = None
    current_nested_key = None  # 追蹤嵌套鍵（用於列表項目的累積）
    multiline_marker = None

    for line in frontmatter_text.split('\n'):
        if _skip_empty_or_comment(line):
            continue

        # 判斷行的縮排層級
        if line.startswith('    '):
            # 4 格以上：深層嵌套（如列表項目或多層嵌套）
            # 如果 current_nested_key 存在，累積到該鍵
            if current_nested_key and current_key:
                nested_line = line.strip()
                # 處理列表項目（以 - 開頭）或其他深層內容
                if not isinstance(result.get(current_key), dict):
                    result[current_key] = {}

                nested_dict = result[current_key]
                if current_nested_key not in nested_dict:
                    nested_dict[current_nested_key] = ""

                # 累積內容（處理列表項目或其他深層行）
                if nested_line.startswith('- '):
                    # 列表項目：去除 '- ' 前綴
                    item_content = nested_line[2:]
                else:
                    # 其他深層行
                    item_content = nested_line

                # 累積內容
                nested_dict[current_nested_key] += "\n" + item_content if nested_dict[current_nested_key] else item_content
            continue
        elif line.startswith('  '):
            # 2 格：嵌套鍵值對、多行標記或列表項目
            nested_result = _parse_nested_line(line, current_key, multiline_marker, current_nested_key)
            multiline_marker = nested_result.multiline_marker

            # 根據回傳的 update_action 更新 result
            if nested_result.update_action is not None:
                key, value, is_nested_dict = nested_result.update_action
                if is_nested_dict:
                    # 嵌套字典模式：初始化或更新嵌套字典
                    if not isinstance(result.get(key), dict):
                        result[key] = {}
                    result[key].update(value)
                    # 記錄最後更新的嵌套鍵（用於後續列表項目的累積）
                    if value:
                        current_nested_key = list(value.keys())[0]
                else:
                    # 多行模式或列表項目：累積內容
                    # 如果 current_nested_key 存在且 current_key 是字典，視為列表項目
                    if current_nested_key and isinstance(result.get(current_key), dict):
                        # 列表項目模式：累積到 current_nested_key
                        nested_dict = result[current_key]
                        if current_nested_key not in nested_dict:
                            nested_dict[current_nested_key] = ""
                        nested_dict[current_nested_key] += "\n" + value if nested_dict[current_nested_key] else value
                    else:
                        # 多行模式：累積到 key（頂層）
                        if key not in result:
                            result[key] = ""
                        result[key] += "\n" + value if result[key] else value
            continue

        if ':' in line:
            # 頂層鍵值對
            current_key, multiline_marker = _parse_top_level_pair(line, result)
            current_nested_key = None  # 重設嵌套鍵追蹤

    return result


def _parse_top_level_pair(line: str, result: dict) -> Tuple[Optional[str], Optional[str]]:
    """處理頂層鍵值對

    頂層鍵值對可能包含：
    1. 簡單值（移除引號）
    2. 多行標記（|, >, |-, >-）後續跟縮排行

    Args:
        line: 頂層鍵值對（不縮排）
        result: 結果字典（會被修改）

    Returns:
        Tuple[Optional[str], Optional[str]]: (current_key, multiline_marker)
            - current_key: 解析出的鍵名
            - multiline_marker: 若有多行標記則返回標記，否則為 None
    """
    key, _, value = line.partition(':')
    key = key.strip()
    value = value.strip()

    # 檢查多行標記
    if value in ('|', '>', '|-', '>-'):
        result[key] = ""
        return key, value

    # 移除引號
    value_clean = value.strip("'\"") if value else ""
    result[key] = value_clean
    return key, None


def parse_ticket_frontmatter(
    content_or_path: "str | Path",
    logger: "logging.Logger | None" = None
) -> dict:
    """統一的 YAML frontmatter 解析（支援 str 和 Path 輸入）

    支援以下 YAML 特性：
    - 頂層 key-value 對
    - 多行字串（|, >, |-, >-）
    - 嵌套結構（縮排鍵值對）
    - 簡單列表

    無外部依賴，支援 Python 3.9+。

    Args:
        content_or_path: Ticket 檔案內容（字串）或檔案路徑（Path）
        logger: 可選 Logger 實例，用於記錄錯誤

    Returns:
        dict: 解析出的 frontmatter key-value（始終返回 dict，無 frontmatter 時返回空 dict、
              或解析失敗時也返回空 dict 並記錄警告）
    """
    # 步驟 1：取得文件內容
    content = _read_content(content_or_path, logger)
    if content is None:
        return {}

    # 步驟 2：驗證 frontmatter 標記和邊界
    if not content.startswith('---'):
        return {}

    end_idx = content.find('---', 3)
    if end_idx == -1:
        return {}

    frontmatter_text = content[3:end_idx].strip()
    if not frontmatter_text:
        return {}

    try:
        # 步驟 3：解析 YAML
        return _parse_yaml_lines(frontmatter_text)
    except Exception as e:
        if logger:
            logger.warning("解析 frontmatter 失敗: {}".format(e))
        return {}


def parse_ticket_date(value: "any", logger: "logging.Logger | None" = None) -> Optional[datetime]:
    """支援多格式的 Ticket 日期解析。

    格式優先級：
    1. datetime.date 物件（YAML 直接解析）
    2. ISO 8601 / RFC 3339 字串（fromisoformat）
    3. 簡單日期字串 YYYY-MM-DD

    Args:
        value: 日期值（可能是 datetime、date 或字串）
        logger: 日誌物件（可選）

    Returns:
        datetime 物件或 None（無法解析時）
    """
    # 已經是 datetime 物件
    if isinstance(value, datetime):
        return value

    # 是 date 物件，轉為 datetime
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    # 字串解析
    if not isinstance(value, str):
        if logger:
            logger.warning("無法解析日期類型: {}".format(type(value)))
        return None

    value = value.strip()
    if not value:
        return None

    # 優先級 1: ISO 8601 / RFC 3339（使用 fromisoformat）
    # Python 3.9 不支援 "Z" 後綴，替換為 "+00:00"（RFC 3339 相容格式）
    try:
        normalized_value = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(normalized_value)
        if logger:
            logger.debug("日期解析成功（ISO 8601）: {}".format(dt.isoformat()))
        return dt
    except ValueError:
        pass

    # 優先級 2: 簡單日期 YYYY-MM-DD（strptime）
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        if logger:
            logger.debug("日期解析成功（YYYY-MM-DD）: {}".format(dt.isoformat()))
        return dt
    except ValueError:
        pass

    # 所有格式都失敗
    if logger:
        logger.warning("無法解析日期字串: {}".format(value))
    return None


def check_error_patterns_changed(
    project_root: Path,
    ticket_created: datetime,
    logger: "logging.Logger | None" = None
) -> "Tuple[bool, List[str]]":
    """掃描 .claude/error-patterns/ 目錄，找出所有 mtime > ticket_created 的 .md 檔案。

    Args:
        project_root: 專案根目錄
        ticket_created: Ticket 建立時間
        logger: 日誌物件（可選）

    Returns:
        tuple - (has_changed, file_list)
            - has_changed: 是否有新增/修改的 error-pattern
            - file_list: 新增/修改的檔案相對路徑清單
    """
    # 前置檢查
    if ticket_created is None:
        if logger:
            logger.warning("ticket created time 為 None，跳過檢查")
        return False, []

    # 檢查目錄是否存在
    error_patterns_dir = project_root / ".claude" / "error-patterns"
    if not error_patterns_dir.exists():
        if logger:
            logger.info("error-patterns 目錄不存在，跳過檢查")
        return False, []

    changed_files = []
    ticket_created_timestamp = ticket_created.timestamp()

    try:
        # 遞迴掃描所有 .md 檔案
        for file_path in error_patterns_dir.rglob("*.md"):
            try:
                file_mtime = file_path.stat().st_mtime
                if file_mtime > ticket_created_timestamp:
                    relative_path = file_path.relative_to(project_root)
                    changed_files.append(str(relative_path))
                    if logger:
                        logger.debug("找到新增檔案: {}".format(relative_path))
            except (OSError, PermissionError) as e:
                if logger:
                    logger.warning("無法讀取檔案 stat: {}: {}".format(file_path, e))
                continue

    except (OSError, PermissionError) as e:
        if logger:
            logger.warning("讀取 error-patterns 目錄失敗: {}".format(e))
        return False, []

    if logger:
        logger.info("掃描 error-patterns 目錄完成：發現 {} 個新增/修改檔案".format(len(changed_files)))
    has_changed = len(changed_files) > 0
    return has_changed, changed_files


# ============================================================================
# Ticket 檔案掃描函式
# ============================================================================

def get_current_version_from_todolist(
    project_root: Path, logger: "Optional[logging.Logger]" = None
) -> "Optional[str]":
    """從 docs/todolist.yaml 讀取 current_version 欄位

    Args:
        project_root: 專案根目錄
        logger: 可選日誌物件

    Returns:
        版本號字串（如 "0.1.0"）或 None（若讀取失敗）
    """
    todolist_file = project_root / "docs" / "todolist.yaml"

    if not todolist_file.exists():
        if logger:
            logger.debug("todolist.yaml 不存在: {}".format(todolist_file))
        return None

    try:
        content = todolist_file.read_text(encoding="utf-8")

        # 簡單正則提取 current_version: 欄位值
        match = re.search(r"current_version:\s*(\S+)", content)
        if match:
            version = match.group(1).strip()
            if logger:
                logger.info("從 todolist.yaml 讀取 current_version: {}".format(version))
            return version
        else:
            if logger:
                logger.debug("todolist.yaml 中未找到 current_version 欄位")
            return None
    except Exception as e:
        if logger:
            logger.warning("讀取 todolist.yaml 失敗: {}".format(e))
        return None


def scan_ticket_files_by_version(
    project_root: Path, version: str, logger: "Optional[logging.Logger]" = None
) -> List[Path]:
    """掃描特定版本的 Ticket 檔案

    Args:
        project_root: 專案根目錄
        version: 版本號（如 "0.1.0"）
        logger: 可選日誌物件

    Returns:
        Ticket 檔案路徑清單
    """
    tickets_dir = project_root / "docs" / "work-logs" / "v{}".format(version) / "tickets"

    if not tickets_dir.exists():
        if logger:
            logger.debug("Ticket 目錄不存在: {}".format(tickets_dir))
        return []

    try:
        ticket_files = list(tickets_dir.glob("*.md"))
        if logger:
            logger.debug("從版本 v{} 找到 {} 個 Ticket 檔案".format(version, len(ticket_files)))
        return ticket_files
    except (OSError, PermissionError) as e:
        if logger:
            logger.warning("掃描 Ticket 目錄失敗 (v{}): {}".format(version, e))
        return []


def find_ticket_files(
    project_root: Path, version: "Optional[str]" = None, logger: "Optional[logging.Logger]" = None
) -> List[Path]:
    """尋找所有 Ticket 檔案（支援版本優先和後向相容）

    功能：
    - 如指定 version，只掃描該版本目錄
    - 如未指定 version，優先掃描當前活躍版本（從 todolist.yaml 讀取）
    - 若讀取失敗或目錄不存在，掃描所有版本目錄
    - 支援後向相容：檢查舊位置 .claude/tickets/

    Args:
        project_root: 專案根目錄
        version: 版本號（可選，如 "0.1.0"）；若不指定則自動讀取
        logger: 可選日誌物件

    Returns:
        Ticket 檔案路徑清單
    """
    all_tickets = []

    # 檢查舊位置 .claude/tickets/（後向相容）
    old_tickets_dir = project_root / ".claude" / "tickets"
    if old_tickets_dir.exists():
        try:
            old_tickets = list(old_tickets_dir.glob("*.md"))
            all_tickets.extend(old_tickets)
            if logger:
                logger.debug("從 .claude/tickets/ 找到 {} 個 Ticket 檔案".format(len(old_tickets)))
        except (OSError, PermissionError) as e:
            if logger:
                logger.warning("掃描舊 Ticket 位置失敗: {}".format(e))

    # 如指定 version，只掃描該版本
    if version:
        version_tickets = scan_ticket_files_by_version(project_root, version, logger)
        all_tickets.extend(version_tickets)
        return all_tickets

    # 未指定 version：優先掃描當前活躍版本
    current_version = get_current_version_from_todolist(project_root, logger)

    if current_version:
        # 優先掃描當前版本
        current_tickets = scan_ticket_files_by_version(project_root, current_version, logger)
        all_tickets.extend(current_tickets)

        # Fallback：掃描其他版本（非當前版本）
        work_logs_dir = project_root / "docs" / "work-logs"
        if work_logs_dir.exists():
            try:
                for version_dir in work_logs_dir.glob("v*"):
                    if version_dir.name != "v{}".format(current_version):
                        other_tickets = scan_ticket_files_by_version(
                            project_root, version_dir.name[1:], logger
                        )
                        all_tickets.extend(other_tickets)
            except (OSError, PermissionError) as e:
                if logger:
                    logger.warning("掃描其他版本目錄失敗: {}".format(e))
    else:
        # Fallback：讀取失敗時，掃描所有版本目錄
        if logger:
            logger.info("current_version 讀取失敗，fallback 到掃描所有版本目錄")

        work_logs_dir = project_root / "docs" / "work-logs"
        if work_logs_dir.exists():
            try:
                for version_dir in work_logs_dir.glob("v*"):
                    version_tickets = scan_ticket_files_by_version(
                        project_root, version_dir.name[1:], logger
                    )
                    all_tickets.extend(version_tickets)
            except (OSError, PermissionError) as e:
                if logger:
                    logger.warning("掃描版本目錄失敗: {}".format(e))

    if logger:
        logger.debug("總計找到 {} 個 Ticket 檔案".format(len(all_tickets)))
    return all_tickets


def find_ticket_file(
    ticket_id: str,
    project_root: Optional[Path] = None,
    logger: Optional[logging.Logger] = None
) -> Optional[Path]:
    """尋找特定 ID 的 Ticket 檔案

    優化策略（O(1) early return）：
    1. 從 ticket_id 解析版本號（格式：{version}-W{wave}-{seq}）
    2. 直接構建路徑：docs/work-logs/v{version}/tickets/{ticket_id}.md
    3. 如果直接路徑存在 → 立即返回（early return）
    4. 檢查舊位置 .claude/tickets/{ticket_id}.md（向後相容）
    5. 如果上述路徑都不存在 → fallback 到 find_ticket_files() 全量掃描

    Args:
        ticket_id: Ticket ID（如 "0.1.0-W1-001" 或非標準格式）
        project_root: 專案根目錄（可選，若為 None 則自動取得）
        logger: 日誌物件（可選）

    Returns:
        Path: Ticket 檔案路徑，或 None 如未找到
    """
    if project_root is None:
        project_root = get_project_root()

    # 嘗試解析 ticket_id 中的版本號（格式：{version}-W{wave}-{seq}）
    # 範例：0.1.0-W31-003 → version="0.1.0"
    version = extract_version_from_ticket_id(ticket_id)

    # Strategy 1: 直接構建路徑（如果能解析出版本號）
    if version:
        direct_path = (
            project_root / "docs" / "work-logs" / f"v{version}" / "tickets" / f"{ticket_id}.md"
        )
        if direct_path.exists():
            if logger:
                logger.info("找到 Ticket: {} 於 {} (direct path)".format(ticket_id, direct_path))
            return direct_path
        else:
            if logger:
                logger.debug("直接路徑不存在，嘗試舊位置: {}".format(ticket_id))

    # Strategy 2: 檢查舊位置 .claude/tickets/{ticket_id}.md（向後相容）
    old_path = project_root / ".claude" / "tickets" / f"{ticket_id}.md"
    if old_path.exists():
        if logger:
            logger.info("找到 Ticket: {} 於 {} (old location)".format(ticket_id, old_path))
        return old_path

    # Strategy 3: Fallback 到全量掃描（版本號解析失敗或直接路徑不存在）
    if logger:
        logger.debug("全部直接路徑未找到，執行全量掃描: {}".format(ticket_id))

    all_tickets = find_ticket_files(project_root, logger=logger)

    # 根據檔名篩選符合的 ticket_id
    expected_name = "{}.md".format(ticket_id)
    for ticket_file in all_tickets:
        if ticket_file.name == expected_name:
            if logger:
                logger.info("找到 Ticket: {} 於 {} (fallback scan)".format(ticket_id, ticket_file))
            return ticket_file

    if logger:
        logger.warning("未找到 Ticket 檔案: {}".format(ticket_id))
    return None


def extract_version_from_ticket_id(ticket_id: str) -> Optional[str]:
    """從 Ticket ID 中提取版本號

    Ticket ID 標準格式：{version}-W{wave}-{seq}
    範例：0.1.0-W31-003 → "0.1.0"

    Args:
        ticket_id: Ticket ID 字串

    Returns:
        版本號字串（如 "0.1.0"），或 None 如無法解析
    """
    if not ticket_id:
        return None

    # 使用正則表達式提取版本號（格式：\d+\.\d+\.\d+）
    version_match = re.match(r'(\d+\.\d+\.\d+)-W', ticket_id)
    if version_match:
        return version_match.group(1)

    return None


def extract_wave_from_ticket_id(ticket_id: str) -> Optional[int]:
    """從 Ticket ID 中提取 Wave 號

    Ticket ID 標準格式：{version}-W{wave}-{seq}
    範例：0.1.0-W31-003 → 31

    Args:
        ticket_id: Ticket ID 字串

    Returns:
        Wave 號（整數），或 None 如無法解析
    """
    if not ticket_id:
        return None

    # 使用正則表達式提取 Wave 號
    wave_match = re.search(r'-W(\d+)-', ticket_id)
    if wave_match:
        return int(wave_match.group(1))

    return None


def _parse_version_from_ticket_id(ticket_id: str) -> Optional[str]:
    """[已棄用] 改用 extract_version_from_ticket_id

    此函式保留以維持後向相容。
    """
    return extract_version_from_ticket_id(ticket_id)


def validate_ticket_has_decision_tree(ticket_content: str, logger: "Optional[logging.Logger]" = None) -> bool:
    """驗證 Ticket 是否包含決策樹欄位

    檢查 Ticket 是否在 YAML frontmatter 或內容中包含決策樹相關欄位。
    支援多個決策樹標記變體（YAML 欄位、中文標題、英文標題）。

    Args:
        ticket_content: Ticket 檔案內容
        logger: Logger 物件（可選）

    Returns:
        bool: 是否包含決策樹欄位
    """
    if not ticket_content:
        if logger:
            logger.debug("Ticket 內容為空")
        return False

    # 檢查任何決策樹欄位（包含 YAML frontmatter 和標題區段）
    for marker in DECISION_TREE_MARKERS:
        if marker in ticket_content:
            if logger:
                logger.debug("在 Ticket 中找到決策樹標記: {}".format(marker))
            return True

    if logger:
        logger.debug("未在 Ticket 中找到決策樹欄位")
    return False
