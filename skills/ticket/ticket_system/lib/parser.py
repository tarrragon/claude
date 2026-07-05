"""
格式解析模組

提供 Markdown frontmatter 解析、Ticket 檔案載入和儲存功能。
支援 Markdown（含 frontmatter）和 YAML 格式。
"""
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ticket_system import constants as _enum_constants
from .ui_constants import FRONTMATTER_SPLIT_COUNT
from .paths import get_ticket_path
# Backward-compat alias：原 _file_lock 已搬至 lib/file_lock.py 並 rename 為
# public file_lock。保留此 re-export 避免破壞既有 import；新 caller 應改用
# `from ticket_system.lib.file_lock import file_lock`。
from .file_lock import file_lock as _file_lock  # noqa: F401


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


class EnumGateViolation(Exception):
    """枚舉驗證閘違規（deny 模式）：非法枚舉值或非法狀態轉移被拒絕落盤。

    violations 為 (field, old_value, new_value, valid_values, kind) tuple 清單
    （kind 為 "enum" 枚舉成員違規 / "transition" 狀態轉移違規），
    供呼叫端組錯誤訊息或測試斷言。
    """

    def __init__(self, violations: List[tuple]):
        self.violations = violations
        detail = "; ".join(
            _format_violation(field, old, new, valid, kind)
            for field, old, new, valid, kind in violations
        )
        super().__init__(f"枚舉驗證閘拒絕落盤：{detail}")


def _format_violation(field, old, new, valid, kind) -> str:
    """組單筆違規的人讀訊息（stderr / 例外共用）。"""
    if kind == "transition":
        allowed = ", ".join(sorted(valid)) if valid else "無（終態）"
        return f"{field} 轉移 {old!r} -> {new!r} 非法（{old} 合法出邊：{allowed}）"
    return f"{field} 值 {new!r} 不在正典（{', '.join(sorted(valid))}）"


# ============================================================================
# Process-scoped ticket cache
# ============================================================================

# 使用完整路徑作為 key，避免版本號正規化問題
# 每次 CLI 執行時自動清空（process 結束即失效）
_ticket_cache: Dict[str, Optional[Dict[str, Any]]] = {}


# 特殊欄位常數
SPECIAL_FIELDS = ["chain", "decision_tree_path", "created"]

# 枚舉閘載入時快照欄位名（_ 前綴：僅存在於記憶體 dict，save 時剝除不序列化）
ENUM_SNAPSHOT_FIELD = "_loaded_enum_snapshot"

# 枚舉閘關注欄位（名稱固定；合法值集合於呼叫時讀 constants 模組屬性，
# 使測試可 monkeypatch VALID_* / ENUM_GATE_MODE）
_ENUM_GATE_FIELD_NAMES = ("type", "priority", "status")


def _snapshot_enum_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """擷取枚舉閘關注欄位的載入時快照（changed-fields-only 比對基準）。"""
    return {field: data.get(field) for field in _ENUM_GATE_FIELD_NAMES}


def _collect_enum_violations(
    ticket: Dict[str, Any],
    snapshot: Optional[Dict[str, Any]],
) -> List[tuple]:
    """收集枚舉違規：只驗「相對載入快照有變更」的欄位。

    Why（化石豁免 / Never break userspace）：語料存在正典外化石值
    （type 12 / priority 24 / status 6 筆），全票驗證會讓任何不相關寫入
    （append-log / set-what）對化石票炸警告。以載入快照比對，欄位值未被
    本次操作改動即跳過；無快照（新建票，未經 load_ticket）→ 全欄位驗證。

    邊界：欄位缺席或為 None 不列違規——必填性屬 checklist / auditor 職責，
    本閘只守「有值時必須是正典值」。非字串值（list/dict 誤塞）視為違規。

    Returns:
        List[tuple]: (field, old_value, new_value, valid_values, "enum")
    """
    gate_fields = {
        "type": _enum_constants.VALID_TICKET_TYPES,
        "priority": _enum_constants.VALID_PRIORITIES,
        "status": _enum_constants.VALID_STATUSES,
    }
    violations = []
    for field, valid_values in gate_fields.items():
        if field not in ticket:
            continue
        new_value = ticket.get(field)
        if new_value is None:
            continue
        if snapshot is not None and new_value == snapshot.get(field):
            continue  # 未被本次操作改動 → 化石豁免
        if not isinstance(new_value, str) or new_value not in valid_values:
            violations.append(
                (field, snapshot.get(field) if snapshot else None, new_value, valid_values, "enum")
            )
    return violations


def _collect_transition_violations(
    ticket: Dict[str, Any],
    snapshot: Optional[Dict[str, Any]],
) -> List[tuple]:
    """收集狀態轉移違規：status 變更時查 STATUS_TRANSITIONS[old] 是否含 new。

    邊界（不重複計、化石容忍）：
    - 無快照（新建票）→ 無「轉移」概念，跳過。
    - 舊態非正典（skipped 等化石）→ 跳過：無法從未知狀態斷言邊合法性，
      且矯正化石票回正典狀態不應被阻擋。
    - 新態非正典 → 跳過：已由枚舉成員違規計入，避免同一寫入雙重告警。

    Returns:
        List[tuple]: (field, old, new, allowed_targets, "transition")
    """
    if snapshot is None:
        return []
    old_value = snapshot.get("status")
    new_value = ticket.get("status")
    if new_value is None or new_value == old_value:
        return []
    transitions = getattr(_enum_constants, "STATUS_TRANSITIONS", {})
    if not isinstance(old_value, str) or old_value not in transitions:
        return []
    if not isinstance(new_value, str) or new_value not in transitions:
        return []
    if new_value in transitions[old_value]:
        return []
    return [("status", old_value, new_value, transitions[old_value], "transition")]


def _log_enum_violations(
    violations: List[tuple],
    ticket: Dict[str, Any],
    ticket_path: Path,
    mode: str,
) -> None:
    """違規寫入 hook-logs/enum-gate.log（warn 期誤報率量測資料源）。"""
    try:
        from .paths import get_project_root
        log_dir = get_project_root() / ".claude" / "hook-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_id = ticket.get("id", ticket_path.stem)
        with open(log_dir / "enum-gate.log", "a", encoding="utf-8") as f:
            for field, old, new, _valid, kind in violations:
                f.write(f"{timestamp}\t{mode}\t{kind}\t{entry_id}\t{field}\t{old!r}\t{new!r}\n")
    except OSError as e:
        # 量測日誌失敗不阻斷落盤主流程；stderr 保留可觀測性（雙通道要求）
        sys.stderr.write(
            f"[enum-gate] 日誌寫入失敗（{type(e).__name__}: {e}），僅 stderr 警告\n"
        )


def _enforce_enum_gate(
    ticket: Dict[str, Any],
    snapshot: Optional[Dict[str, Any]],
    ticket_path: Path,
) -> None:
    """save_ticket 落盤前的枚舉驗證閘（31 個寫入呼叫點的單點防線）。

    warn 模式：stderr 警告 + enum-gate.log 記錄後照常落盤（量測期預設）。
    deny 模式：raise EnumGateViolation，呼叫端不落盤。
    模式讀 constants.ENUM_GATE_MODE（切 deny 須經 warn 期誤報率量測裁定）。
    """
    violations = _collect_enum_violations(ticket, snapshot)
    violations += _collect_transition_violations(ticket, snapshot)
    if not violations:
        return
    mode = getattr(_enum_constants, "ENUM_GATE_MODE", "warn")
    _log_enum_violations(violations, ticket, ticket_path, mode)
    entry_id = ticket.get("id", ticket_path.stem)
    for field, old, new, valid, kind in violations:
        sys.stderr.write(
            f"[enum-gate:{mode}] {entry_id} {_format_violation(field, old, new, valid, kind)}\n"
        )
    if mode == "deny":
        raise EnumGateViolation(violations)


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

    實作 process-scoped 記憶體快取，避免同一 process 內重複讀取相同 ticket。

    演算法:
    1. 取得 Ticket 檔案路徑
    2. 檢查快取（命中則直接返回）
    3. 檢查檔案是否存在
    4. 讀取檔案內容（支援 UTF-8 編碼）
    5. 根據副檔名選擇解析策略：
       - .md: 解析 frontmatter（YAML）和 body，捕獲 YAMLParseError
       - 其他: 直接解析為 YAML，捕獲 yaml.YAMLError
    6. 附加元資料、更新快取並返回；若有解析錯誤則在字典中記錄

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
    cache_key = str(ticket_path)

    # Guard Clause 1.5：檢查快取
    if cache_key in _ticket_cache:
        return _ticket_cache[cache_key]

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
            # 若 YAML 解析失敗，返回包含錯誤訊息的字典（並快取）
            result = {
                "id": ticket_id,
                "_path": str(ticket_path),
                "_yaml_error": e.message
            }
            _ticket_cache[cache_key] = result
            return result

        # Guard Clause 3：frontmatter 為空（無 frontmatter）
        if not frontmatter:
            return None

        # 附加元資料：body 內容和檔案路徑
        frontmatter["_body"] = body
        frontmatter["_path"] = str(ticket_path)
        # 枚舉閘載入時快照（save 時 changed-fields-only 比對基準）
        frontmatter[ENUM_SNAPSHOT_FIELD] = _snapshot_enum_fields(frontmatter)
        # 更新快取
        _ticket_cache[cache_key] = frontmatter
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

            # 枚舉閘載入時快照（save 時 changed-fields-only 比對基準）
            ticket_content[ENUM_SNAPSHOT_FIELD] = _snapshot_enum_fields(ticket_content)

            # 更新快取
            _ticket_cache[cache_key] = ticket_content
            return ticket_content
        except yaml.YAMLError as e:
            # YAML 解析失敗時，返回包含錯誤訊息的字典（並快取）
            error_msg = str(e).strip()
            result = {
                "id": ticket_id,
                "_path": str(ticket_path),
                "_yaml_error": error_msg
            }
            _ticket_cache[cache_key] = result
            return result


def save_ticket(ticket: Dict[str, Any], ticket_path: Path) -> None:
    """
    儲存 Ticket 資料

    根據檔案副檔名自動決定格式（Markdown 或 YAML）。
    自動備份和恢復特殊欄位（_body、_path、chain、decision_tree_path）
    以保持傳入的 ticket 物件完整性。
    寫入成功後失效快取以確保後續讀取取得最新資料。

    演算法:
    1. 備份元資料欄位（_body、_path）
    2. 備份特殊欄位（chain、decision_tree_path、created）
    3. 建立目標目錄
    4. 根據副檔名選擇格式序列化
    5. 寫入檔案
    6. finally 區塊恢復所有備份欄位到 ticket 物件
    7. 寫入成功後失效對應的快取 entry

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
    # 枚舉閘快照：剝除避免序列化進 frontmatter；deny raise 時由 finally 恢復
    enum_snapshot = ticket.pop(ENUM_SNAPSHOT_FIELD, None)

    # 備份特殊欄位（需要在儲存時保留但不序列化）
    # 這些欄位代表 Ticket 的內部狀態，由系統自動管理
    special_fields_backup = _backup_special_fields(ticket)

    # 建立目標目錄（父目錄），必要時遞迴建立
    ticket_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # 枚舉驗證閘：置於 try 內使 deny 模式 raise 時 finally 仍恢復備份欄位
        _enforce_enum_gate(ticket, enum_snapshot, ticket_path)

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

        # 保留檔尾單一換行（W9-005 / issue #1 問題5）：load 不保證 body 帶
        # 檔尾換行，直接寫回會讓 claim/release roundtrip 吃掉檔尾換行，產生
        # 「No newline at end of file」git diff 雜訊。僅在缺換行時補一個，
        # 不動既有換行（避免改動帶尾換行的 body）。
        if not content.endswith("\n"):
            content += "\n"

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
        if enum_snapshot is not None:
            ticket[ENUM_SNAPSHOT_FIELD] = enum_snapshot

    # 寫入成功後失效快取，確保後續讀取取得最新資料
    # 注意：這行在 try-finally 後執行，只有寫入成功才到達
    _ticket_cache.pop(str(ticket_path), None)

    # 落盤成功後刷新快照為當前值：同一 dict 再次 save 時不對已持久化的
    # 變更重複告警（快照語意 = 「相對最後一次成功落盤」）
    ticket[ENUM_SNAPSHOT_FIELD] = _snapshot_enum_fields(ticket)


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
