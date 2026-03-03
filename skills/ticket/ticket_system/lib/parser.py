"""
格式解析模組

提供 Markdown frontmatter 解析、Ticket 檔案載入和儲存功能。
支援 Markdown（含 frontmatter）和 YAML 格式。
"""
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import yaml

from .ui_constants import FRONTMATTER_SPLIT_COUNT
from .paths import get_ticket_path


# ============================================================================
# 自訂異常
# ============================================================================

class YAMLParseError(Exception):
    """
    YAML 解析錯誤異常

    用於區分 YAML 解析失敗和檔案不存在。
    呼叫端可以捕獲此異常並顯示詳細的錯誤訊息給使用者。
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


# 特殊欄位常數
SPECIAL_FIELDS = ["chain", "decision_tree_path", "created"]


def _backup_special_fields(existing_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    備份現有 Ticket 的特殊欄位

    Ticket 中有些欄位（如 chain、decision_tree_path、created）在儲存時
    應該被保留。此函式將這些特殊欄位從現有資料中備份出來。

    Args:
        existing_data: 現有的 Ticket 資料字典

    Returns:
        Dict[str, Any]: 包含所有特殊欄位的備份字典（只含在 existing_data 中存在的欄位）

    Examples:
        >>> data = {"chain": "0.31.0-W4-001", "id": "test"}
        >>> backup = _backup_special_fields(data)
        >>> backup
        {'chain': '0.31.0-W4-001'}
    """
    return {
        field: existing_data[field]
        for field in SPECIAL_FIELDS
        if field in existing_data
    }


def _restore_special_fields(
    new_data: Dict[str, Any],
    backup: Dict[str, Any]
) -> Dict[str, Any]:
    """
    恢復特殊欄位到新資料

    在更新 Ticket 資料後，可能需要恢復某些特殊欄位（如果它們不在新資料中）。
    這確保了特殊欄位的完整性。

    Args:
        new_data: 新的 Ticket 資料字典
        backup: 備份的特殊欄位字典

    Returns:
        Dict[str, Any]: 包含恢復後欄位的結果字典

    Examples:
        >>> new_data = {"id": "test"}
        >>> backup = {"chain": "0.31.0-W4-001"}
        >>> result = _restore_special_fields(new_data, backup)
        >>> result
        {'id': 'test', 'chain': '0.31.0-W4-001'}
    """
    result = new_data.copy()
    for field, value in backup.items():
        if field not in result:
            result[field] = value
    return result


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    解析 Markdown frontmatter

    分離 YAML frontmatter 和 body。Frontmatter 必須在檔案開頭，由 --- 分隔。
    使用 Guard Clause 模式快速返回異常情況。

    演算法:
    1. 檢查內容是否以 --- 開頭，否則無 frontmatter
    2. 以 --- 分割成三部分：[空, YAML, body]
    3. 驗證分割結果有三部分
    4. 嘗試解析 YAML，失敗時丟出 YAMLParseError

    Args:
        content: 完整檔案內容（可能包含 frontmatter）

    Returns:
        Tuple[Dict, str]: (frontmatter_dict, body_text)
                         frontmatter_dict 為空時表示無 frontmatter

    Raises:
        YAMLParseError: YAML 解析失敗時丟出

    Examples:
        >>> content = '---\\ntitle: test\\n---\\nBody content'
        >>> fm, body = parse_frontmatter(content)
        >>> fm['title']
        'test'
        >>> body.strip()
        'Body content'
        >>> parse_frontmatter('No frontmatter')
        ({}, 'No frontmatter')
    """
    # Guard Clause 1：內容不以 --- 開頭 → 無 frontmatter
    if not content.startswith("---"):
        return {}, content

    # 分割內容成三部分：空、YAML、body
    # FRONTMATTER_SPLIT_COUNT=3 表示最多分割3次，得到3+1=4部分
    frontmatter_sections = content.split("---", FRONTMATTER_SPLIT_COUNT)

    # Guard Clause 2：分割不成三部分 → 格式錯誤
    if len(frontmatter_sections) < FRONTMATTER_SPLIT_COUNT + 1:
        return {}, content

    try:
        # 分割結果: [開頭空字串, YAML內容, body內容, ...]
        # 索引1是 YAML frontmatter，索引2是 body
        frontmatter = yaml.safe_load(frontmatter_sections[1])
        body = frontmatter_sections[2].strip()
        # 如果 YAML 解析為 None，返回空字典，否則返回解析結果
        return frontmatter or {}, body
    except yaml.YAMLError as e:
        # YAML 解析失敗時，丟出 YAMLParseError 傳遞錯誤訊息
        error_msg = str(e).strip()
        raise YAMLParseError(error_msg)


def load_ticket(version: str, ticket_id: str) -> Optional[Dict[str, Any]]:
    """
    載入 Ticket 資料

    支援 Markdown（含 frontmatter）和 YAML 格式。使用 Guard Clause 快速返回失敗情況。
    返回的字典包含特殊欄位：
    - _body: Markdown body 內容（Markdown 格式）
    - _path: Ticket 檔案路徑（絕對路徑字串）
    - _yaml_error: 若有 YAML 解析錯誤，包含錯誤訊息

    演算法:
    1. 取得 Ticket 檔案路徑
    2. 檢查檔案是否存在
    3. 讀取檔案內容（支援 UTF-8 編碼）
    4. 根據副檔名選擇解析策略：
       - .md: 解析 frontmatter（YAML）和 body，捕獲 YAMLParseError
       - 其他: 直接解析為 YAML，捕獲 yaml.YAMLError
    5. 附加元資料並返回；若有解析錯誤則在字典中記錄

    Args:
        version: 版本號（如 "0.31.0" 或 "v0.31.0"）
        ticket_id: Ticket ID（如 "0.31.0-W4-001"）

    Returns:
        Optional[Dict]: 完整的 Ticket 資料字典。
                       若 YAML 解析失敗，返回包含 _yaml_error 欄位的字典。
                       若檔案不存在或無法讀取，返回 None。

    Raises:
        無，所有異常都安全處理

    Examples:
        >>> ticket = load_ticket("0.31.0", "0.31.0-W4-001")
        >>> ticket is not None and ticket['id'] == '0.31.0-W4-001'
        True
        >>> load_ticket("0.31.0", "nonexistent")
        None
        >>> ticket = load_ticket("0.31.0", "broken-yaml")
        >>> ticket is not None and '_yaml_error' in ticket
        True
    """
    # Guard Clause 1：檔案不存在
    ticket_path = get_ticket_path(version, ticket_id)
    if not ticket_path.exists():
        return None

    # 嘗試讀取檔案內容（Guard Clause 2：讀取失敗）
    try:
        with open(ticket_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return None

    # 根據副檔名選擇解析策略
    if ticket_path.suffix == ".md":
        # Markdown 格式：含 YAML frontmatter 和 body
        try:
            frontmatter, body = parse_frontmatter(content)
        except YAMLParseError as e:
            # 若 YAML 解析失敗，返回包含錯誤訊息的字典
            return {
                "id": ticket_id,
                "_path": str(ticket_path),
                "_yaml_error": e.message
            }

        # Guard Clause 3：frontmatter 為空（無 frontmatter）
        if not frontmatter:
            return None

        # 附加元資料：body 內容和檔案路徑
        frontmatter["_body"] = body
        frontmatter["_path"] = str(ticket_path)
        return frontmatter
    else:
        # YAML 格式：純 YAML 或 { ticket: {...} } 包裝格式
        try:
            ticket_content = yaml.safe_load(content)

            # Guard Clause 4：YAML 解析為空
            if not ticket_content:
                return None

            # 附加檔案路徑
            ticket_content["_path"] = str(ticket_path)

            # 支援包裝格式：如果 YAML 頂層有 'ticket' 欄位，
            # 則使用該欄位值作為實際 Ticket 資料
            if "ticket" in ticket_content:
                ticket_content = ticket_content["ticket"]
                ticket_content["_path"] = str(ticket_path)

            return ticket_content
        except yaml.YAMLError as e:
            # YAML 解析失敗時，返回包含錯誤訊息的字典
            error_msg = str(e).strip()
            return {
                "id": ticket_id,
                "_path": str(ticket_path),
                "_yaml_error": error_msg
            }


def save_ticket(ticket: Dict[str, Any], ticket_path: Path) -> None:
    """
    儲存 Ticket 資料

    根據檔案副檔名自動決定格式（Markdown 或 YAML）。
    自動備份和恢復特殊欄位（_body、_path、chain、decision_tree_path）
    以保持傳入的 ticket 物件完整性。

    演算法:
    1. 備份元資料欄位（_body、_path）
    2. 備份特殊欄位（chain、decision_tree_path、created）
    3. 建立目標目錄
    4. 根據副檔名選擇格式序列化
    5. 寫入檔案
    6. finally 區塊恢復所有備份欄位到 ticket 物件

    Args:
        ticket: Ticket 資料字典（會被臨時修改但最終會恢復）
        ticket_path: 目標檔案路徑（副檔名決定格式）

    Raises:
        IOError: 檔案寫入失敗
        OSError: 目錄建立或無寫入權限

    Examples:
        >>> ticket = {'id': 'test-001', 'status': 'pending', '_body': '# Content'}
        >>> save_ticket(ticket, Path('/tmp/test.md'))
        >>> ticket['_body']  # 已恢復
        '# Content'
    """
    # 備份元資料欄位（Markdown 格式需要，YAML 格式不需要儲存）
    body = ticket.pop("_body", "")
    path_str = ticket.pop("_path", None)

    # 備份特殊欄位（需要在儲存時保留但不序列化）
    # 這些欄位代表 Ticket 的內部狀態，由系統自動管理
    special_fields_backup = _backup_special_fields(ticket)

    # 建立目標目錄（父目錄），必要時遞迴建立
    ticket_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if ticket_path.suffix == ".md":
            # Markdown 格式：YAML frontmatter + body
            # 序列化 frontmatter 為 YAML
            frontmatter_yaml = yaml.dump(
                ticket,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
            # 組合 frontmatter 和 body：---\nYAML\n---\n\nbody
            content = f"---\n{frontmatter_yaml}---\n\n{body}"
        else:
            # YAML 格式：用 { ticket: {...} } 包裝
            # 支援包裝格式以提高相容性
            content = yaml.dump(
                {"ticket": ticket},
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        # 寫入檔案（UTF-8 編碼）
        with open(ticket_path, "w", encoding="utf-8") as f:
            f.write(content)

    finally:
        # 必須恢復所有備份欄位，確保 ticket 物件完整性
        # 即使寫入失敗也要恢復，保持傳入物件的狀態
        ticket.update(special_fields_backup)
        if body:
            ticket["_body"] = body
        if path_str:
            ticket["_path"] = path_str


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
