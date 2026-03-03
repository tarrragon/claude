"""
Ticket 驗證模組

提供 Ticket 格式和欄位驗證功能。
"""
# 防止直接執行此模組
import re
from typing import List, Optional, Tuple, Dict, Any

from .constants import TICKET_ID_PATTERN
from .cycle_detector import CycleDetector


def validate_ticket_id(ticket_id: str) -> bool:
    """
    驗證 Ticket ID 格式。

    支援無限深度子任務的 Ticket ID 格式驗證。
    使用 Guard Clause 模式快速返回無效情況。

    格式規則:
    - 基本格式: {version}-W{wave}-{seq[.seq...]}
    - 版本: 數字.數字.數字（如 0.31.0）
    - 波次: W 後跟整數（如 W3, W4）
    - 序號: 整數序列，支援無限深度（如 001, 001.1, 001.1.2）
    - 常數: TICKET_ID_PATTERN 定義了完整的正則表達式

    Args:
        ticket_id: 要驗證的 Ticket ID 字串

    Returns:
        bool: 格式是否符合規則

    Raises:
        無，無效輸入返回 False 而非拋出異常

    Examples:
        >>> validate_ticket_id("0.31.0-W3-001")
        True
        >>> validate_ticket_id("0.31.0-W3-001.1")
        True
        >>> validate_ticket_id("0.31.0-W3-001.1.1")
        True
        >>> validate_ticket_id("invalid")
        False
        >>> validate_ticket_id("")
        False
        >>> validate_ticket_id(None)
        False
    """
    # Guard Clause：輸入為空或非字串型
    if not ticket_id or not isinstance(ticket_id, str):
        return False

    # 編譯正則表達式（TICKET_ID_PATTERN 在 constants 中定義）
    pattern = re.compile(TICKET_ID_PATTERN)
    # 返回匹配結果（bool 型）
    return bool(pattern.match(ticket_id))


def validate_ticket_fields(
    ticket: dict, required_fields: Optional[List[str]] = None
) -> List[str]:
    """
    驗證 Ticket 必填欄位。

    檢查指定的必填欄位是否存在且不為空。
    非常值型（None、空字串、空容器）都視為缺失。

    演算法:
    1. 若未指定必填欄位，使用預設清單（id、status）
    2. 遍歷所有必填欄位
    3. 使用 ticket.get() 安全取值（不存在時返回 None）
    4. 檢查值是否為「空」：None、""、[]、{}
    5. 若為空，加入缺失清單
    6. 返回缺失欄位清單

    Args:
        ticket: Ticket 資料字典（可能無某些欄位）
        required_fields: 必填欄位名稱清單
                        若為 None，使用預設值 ["id", "status"]

    Returns:
        List[str]: 缺失或為空的欄位名稱清單
                  空列表表示全部必填欄位都存在且有值

    Examples:
        >>> ticket = {"id": "test-001", "status": "pending"}
        >>> missing = validate_ticket_fields(ticket, ["id", "status", "title"])
        >>> "title" in missing
        True
        >>> missing
        ['title']
        >>> validate_ticket_fields(ticket)  # 使用預設欄位
        []
    """
    # Guard Clause：未指定欄位時使用預設值
    if required_fields is None:
        # 預設必填欄位：最基本的識別和狀態信息
        required_fields = ["id", "status"]

    missing_fields = []

    # 檢查每個必填欄位
    for field in required_fields:
        # 安全取值：不存在的欄位返回 None
        value = ticket.get(field)

        # 判斷是否為「空」：None、空字串、空列表、空字典
        # 這些值都表示欄位未真正填充
        if value is None or value == "" or value == [] or value == {}:
            # 記錄缺失的欄位
            missing_fields.append(field)

    # 返回缺失欄位清單（空表示驗證通過）
    return missing_fields


def validate_ticket_dict(ticket: dict) -> Tuple[bool, List[str]]:
    """
    執行完整的 Ticket 驗證

    驗證 ID 格式和必填欄位。

    Args:
        ticket: Ticket 資料字典

    Returns:
        Tuple[bool, List[str]]: (驗證通過, 錯誤訊息列表)

    Examples:
        >>> ticket = {"id": "0.31.0-W3-001", "status": "pending"}
        >>> passed, errors = validate_ticket_dict(ticket)
        >>> passed
        True
    """
    errors = []

    # 檢查 ID 格式
    ticket_id = ticket.get("id")
    if ticket_id:
        if not validate_ticket_id(ticket_id):
            errors.append(f"Invalid Ticket ID format: {ticket_id}")
    else:
        errors.append("Missing 'id' field")

    # 檢查必填欄位
    missing = validate_ticket_fields(ticket)
    if missing:
        errors.extend([f"Missing field: {field}" for field in missing])

    return len(errors) == 0, errors


def validate_claimable_status(
    ticket_id: str,
    current_status: str
) -> Tuple[bool, Optional[str]]:
    """
    驗證 Ticket 是否可被認領。

    檢查 Ticket 的當前狀態是否允許認領操作。
    - pending: 可認領（未被接手）
    - in_progress: 不可認領（已被接手）
    - completed: 不可認領（已完成）
    - blocked: 可認領（需要重新開始）

    使用 Guard Clause 模式判斷不可認領的狀態。

    Args:
        ticket_id: Ticket ID（用於錯誤訊息）
        current_status: 當前狀態（來自 Ticket 的 status 欄位）

    Returns:
        Tuple[bool, Optional[str]]: (可認領, 錯誤訊息)
        - (True, None): 允許認領（pending 或其他）
        - (False, error_message): 不允許認領且返回原因

    Examples:
        >>> validate_claimable_status("0.31.0-W3-001", "pending")
        (True, None)
        >>> valid, msg = validate_claimable_status("0.31.0-W3-001", "in_progress")
        >>> valid
        False
        >>> msg
        '0.31.0-W3-001 已被接手'
    """
    from .constants import STATUS_IN_PROGRESS, STATUS_COMPLETED

    # Guard Clause 1：已被接手
    if current_status == STATUS_IN_PROGRESS:
        return False, f"{ticket_id} 已被接手"

    # Guard Clause 2：已完成
    if current_status == STATUS_COMPLETED:
        return False, f"{ticket_id} 已完成"

    # 其他狀態（pending、blocked）都允許認領
    return True, None


def validate_completable_status(
    ticket_id: str,
    current_status: str,
    completed_at: Optional[str] = None
) -> Tuple[bool, Optional[str], bool]:
    """
    驗證 Ticket 是否可被標記完成。

    檢查 Ticket 的當前狀態，判斷是否允許完成操作。
    返回三元組 (can_complete, message, is_already_complete)。

    狀態機制:
    - completed: 已完成（返回友好訊息，用於幂等操作）
    - pending: 未認領（阻止，需先 claim）
    - blocked: 被阻塞（阻止，需先解除依賴）
    - in_progress: 可完成

    使用 Guard Clause 模式逐一判斷異常情況。

    Args:
        ticket_id: Ticket ID（用於錯誤訊息和友好訊息）
        current_status: 當前狀態（STATUS_COMPLETED、STATUS_PENDING 等）
        completed_at: 完成時間戳（若狀態為 completed，傳入此值可生成詳細訊息）

    Returns:
        Tuple[bool, Optional[str], bool]: (可完成, 訊息, 已完成標誌)
        - (True, None, False): 允許完成（in_progress）
        - (False, error_message, False): 阻止完成，返回原因
        - (True, friendly_message, True): 已完成（幂等返回）

    Examples:
        >>> validate_completable_status("0.31.0-W3-001", "in_progress")
        (True, None, False)
        >>> can, msg, is_complete = validate_completable_status("0.31.0-W3-001", "completed", "2026-02-01T10:00:00")
        >>> can
        True
        >>> is_complete
        True
        >>> msg
        '0.31.0-W3-001 已完成於 2026-02-01T10:00:00'
    """
    from .constants import STATUS_COMPLETED, STATUS_PENDING, STATUS_BLOCKED

    # Guard Clause 1：已完成的 Ticket
    # 返回友好訊息（實現幂等操作：多次 complete 都返回 0）
    if current_status == STATUS_COMPLETED:
        # 若提供了完成時間，包含在訊息中；否則簡短訊息
        friendly_msg = f"{ticket_id} 已完成於 {completed_at}" if completed_at else f"{ticket_id} 已完成"
        return True, friendly_msg, True

    # Guard Clause 2：未認領的 Ticket
    # 阻止完成，提示用戶先進行 claim 操作
    if current_status == STATUS_PENDING:
        error_msg = f"{ticket_id} 尚未被接手，請先執行 /ticket track claim {ticket_id}"
        return False, error_msg, False

    # Guard Clause 3：被阻塞的 Ticket
    # 阻止完成，提示用戶先解除依賴
    if current_status == STATUS_BLOCKED:
        error_msg = f"{ticket_id} 被阻塞，請先解除阻塞依賴"
        return False, error_msg, False

    # 預設情況：in_progress 可完成
    # 返回成功標誌，無訊息
    return True, None, False


def _is_placeholder(text: str) -> bool:
    """
    判斷文字是否為佔位符。

    支援多種佔位符格式：
    - HTML 註解：<!-- To be filled by executing agent -->
    - 待填寫標記：(pending), TBD, TODO, N/A
    - 空白或僅有換行

    這個函式與 acceptance_auditor.py 中的 _is_placeholder 功能一致，
    用於統一驗證邏輯。

    Args:
        text: 要檢查的文字內容

    Returns:
        bool: 若為佔位符格式返回 True，否則返回 False
    """
    if not text or not isinstance(text, str):
        return True

    stripped = text.strip()

    # 空白或僅有換行
    if not stripped:
        return True

    # HTML 註解（包括 "To be filled by executing agent"）
    if re.search(r"<!--.*?-->", stripped, re.DOTALL):
        return True

    # 待填寫標記
    if re.search(r"\(pending\)|TBD|TODO|N/A", stripped, re.IGNORECASE):
        return True

    return False


def validate_execution_log(
    ticket_id: str,
    body: str,
) -> tuple[bool, list[str]]:
    """
    檢查 Ticket 的執行日誌是否已填寫。

    掃描 Ticket body 內容，偵測是否仍包含佔位符。支援多種佔位符格式：
    - HTML 註解：<!-- To be filled by executing agent --> 等
    - 待填寫標記：(pending), TBD, TODO, N/A
    - 空白區段

    對於包含佔位符的區段，會回傳區段名稱清單。
    這是一個「軟檢查」：回傳結果供呼叫者決定是否警告或阻止。

    Args:
        ticket_id: Ticket ID（用於錯誤訊息）
        body: Ticket 的 body 文字內容（Markdown）

    Returns:
        tuple[bool, list[str]]:
            (已填寫, 未填寫區段名稱列表)
            - (True, []): 所有區段已填寫
            - (False, ["Problem Analysis", ...]): 仍有佔位符的區段

    Examples:
        >>> body = "## Execution Log\\n### Problem Analysis\\ncontent here"
        >>> validate_execution_log("W4-001", body)
        (True, [])
        >>> body = "### Problem Analysis\\n<!-- To be filled by executing agent -->"
        >>> validate_execution_log("W4-001", body)
        (False, ['Problem Analysis'])
        >>> body = "### Problem Analysis\\n(pending)"
        >>> validate_execution_log("W4-001", body)
        (False, ['Problem Analysis'])
    """
    SECTIONS_TO_CHECK = ["Problem Analysis", "Solution", "Test Results"]

    # Guard Clause：無 body 內容時視為未填寫
    if not body or not isinstance(body, str):
        return False, SECTIONS_TO_CHECK[:]

    unfilled_sections: list[str] = []

    for section in SECTIONS_TO_CHECK:
        # 找到區段標題位置（支援 ### 或 ## 層級）
        header_patterns = [f"### {section}", f"## {section}"]
        section_start = -1
        for pattern in header_patterns:
            idx = body.find(pattern)
            if idx != -1:
                section_start = idx
                break

        # 若找不到此區段，視為未填寫
        if section_start == -1:
            unfilled_sections.append(section)
            continue

        # 擷取區段內容（從標題到下一個 ## 或 ### 或文件結尾）
        content_start = body.find("\n", section_start)
        if content_start == -1:
            # 標題之後沒有內容
            unfilled_sections.append(section)
            continue

        content_start += 1  # 跳過換行符

        # 找到下一個區段的開頭
        next_section_idx = len(body)
        for marker in ["## ", "### "]:
            idx = body.find(marker, content_start)
            if idx != -1 and idx < next_section_idx:
                next_section_idx = idx

        section_content = body[content_start:next_section_idx].strip()

        # 使用 _is_placeholder 進行更精確的檢查，支援多種佔位符格式
        if _is_placeholder(section_content):
            unfilled_sections.append(section)

    is_filled = len(unfilled_sections) == 0
    return is_filled, unfilled_sections


def validate_acceptance_criteria(
    ticket_id: str,
    acceptance_list: Optional[List[str]] = None
) -> Tuple[bool, List[str]]:
    """
    驗證 Ticket 的驗收條件是否全部完成。

    檢查 acceptance 欄位中是否有未完成的項目。
    項目格式支援三種：
    - "[x] 描述" 表示完成（新格式）
    - "[ ] 描述" 表示未完成（新格式）
    - "描述"（無前綴） 表示未完成（舊格式，向後相容）

    演算法:
    1. Guard Clause：若無驗收條件，自動通過
    2. 遍歷每個條件項
    3. 移除前後空白
    4. 檢查是否以 "[x]" 開頭（完成標記）
    5. 若未完成，加入未完成清單（標準化為 "[ ] 內容" 格式）
    6. 返回結果

    向後相容性：
    - 舊格式（無前綴的純字串）視為未完成
    - 新建 Ticket 會自動加入 "[ ] " 前綴
    - 已存在的無前綴項目也會被正確識別為未完成

    Args:
        ticket_id: Ticket ID（當前未在函式中使用，保留以供擴展）
        acceptance_list: 驗收條件清單（YAML list 或 None）
                        可包含三種格式的字串

    Returns:
        Tuple[bool, List[str]]: (全部完成, 未完成項清單)
        - (True, []): 全部完成或無驗收條件
        - (False, [未完成項...]): 有未完成項（已標準化為 "[ ] ..." 格式）

    Examples:
        >>> validate_acceptance_criteria("0.31.0-W3-001", None)
        (True, [])
        >>> validate_acceptance_criteria("0.31.0-W3-001", [])
        (True, [])
        >>> criteria = ["[x] 完成項", "[ ] 未完成項", "[x] 另一完成項"]
        >>> complete, incomplete = validate_acceptance_criteria("0.31.0-W3-001", criteria)
        >>> complete
        False
        >>> len(incomplete)
        1
        >>> incomplete[0]
        '[ ] 未完成項'
        >>> # 向後相容：舊格式無前綴
        >>> criteria = ["[x] 完成", "未完成", "[x] 另一完成"]
        >>> complete, incomplete = validate_acceptance_criteria("0.31.0-W3-001", criteria)
        >>> complete
        False
        >>> incomplete[0]
        '[ ] 未完成'
    """
    # Guard Clause：無驗收條件
    # None 或空列表都視為「無驗收條件」，自動通過驗證
    if not acceptance_list:
        return True, []

    incomplete_items = []

    # 檢查每個驗收條件項
    for item in acceptance_list:
        # 僅處理字串型項目（跳過其他型態）
        if isinstance(item, str):
            # 移除項目前後的空白（包括換行、Tab等）
            stripped = item.strip()

            # 判斷完成狀態：以 "[x]" 開頭表示完成
            # 其他所有格式（如 "[ ]"、無前綴等）都視為未完成
            if not stripped.startswith("[x]"):
                # 將未完成項加入清單，統一標準化格式
                # 如果項目已有 "[ ] " 前綴，保留原樣
                # 如果項目無前綴（舊格式），加上 "[ ] " 前綴
                if stripped.startswith("[ ]"):
                    incomplete_items.append(stripped)
                else:
                    incomplete_items.append(f"[ ] {stripped}")

    # 若有未完成項，返回 False 和未完成清單
    if incomplete_items:
        return False, incomplete_items

    # 所有項都完成
    return True, []


def validate_blocked_by(
    ticket_id: str,
    blocked_by: Optional[List[str]] = None,
    all_tickets: Optional[List[Dict[str, Any]]] = None
) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """
    驗證 Ticket 的 blockedBy 依賴是否會產生循環。

    使用 CycleDetector 檢測設定 blockedBy 時是否會產生循環依賴。
    若會產生循環，應拒絕設定此依賴。

    演算法:
    1. Guard Clause：入參檢查
    2. 呼叫 CycleDetector.validate_blocked_by 進行循環檢測
    3. 返回驗證結果

    Args:
        ticket_id: 要設定依賴的 Ticket ID
        blocked_by: 要設定的依賴清單（List[str] 或 None）
        all_tickets: 現有的所有 Ticket 資料

    Returns:
        Tuple[bool, Optional[str], Optional[List[str]]]:
        - (True, None, None): 驗證通過，無循環依賴
        - (False, error_msg, cycle_path): 驗證失敗，返回錯誤訊息和環路

    Examples:
        >>> tickets = [
        ...     {"id": "B", "blockedBy": ["C"]},
        ...     {"id": "C", "blockedBy": ["A"]},
        ... ]
        >>> # 嘗試設定 A -> B（會產生環 A -> B -> C -> A）
        >>> valid, msg, path = validate_blocked_by("A", ["B"], tickets)
        >>> valid
        False
        >>> path
        ['A', 'B', 'C', 'A']

        >>> # 正常情況：無環
        >>> tickets = [
        ...     {"id": "B", "blockedBy": []},
        ... ]
        >>> valid, msg, path = validate_blocked_by("A", ["B"], tickets)
        >>> valid
        True
        >>> msg is None
        True
    """
    # Guard Clause 1：無依賴清單
    if not blocked_by:
        return True, None, None

    # Guard Clause 2：無其他 Ticket（無法形成環）
    if not all_tickets:
        return True, None, None

    # 呼叫 CycleDetector 進行循環檢測
    return CycleDetector.validate_blocked_by(
        ticket_id,
        blocked_by,
        all_tickets
    )


def validate_related_to(
    ticket_id: str,
    related_to: Optional[List[str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    驗證 relatedTo 欄位的格式和內容。

    relatedTo 是一個資訊性欄位，表示與此 Ticket 相關但非層級的多對多關聯。
    與 blockedBy（執行順序）不同，relatedTo 不影響任務執行順序。

    驗證規則：
    1. relatedTo 為 None 或空清單時自動通過
    2. 每個 ID 必須符合 Ticket ID 格式
    3. ID 列表中不應出現重複
    4. ID 不應自我參考（不能指向當前 Ticket）

    Args:
        ticket_id: 當前 Ticket ID（用於自我參考檢查）
        related_to: 相關 Ticket IDs 清單（可為 None 或 []）

    Returns:
        Tuple[bool, Optional[str]]: (有效, 錯誤訊息)
        - (True, None): 驗證通過
        - (False, error_message): 驗證失敗，返回錯誤訊息

    Examples:
        >>> validate_related_to("0.31.0-W5-001", None)
        (True, None)
        >>> validate_related_to("0.31.0-W5-001", [])
        (True, None)
        >>> validate_related_to("0.31.0-W5-001", ["0.31.0-W5-002", "0.31.0-W5-003"])
        (True, None)
        >>> valid, msg = validate_related_to("0.31.0-W5-001", ["invalid-id"])
        >>> valid
        False
        >>> msg
        '0.31.0-W5-001: relatedTo 包含無效的 Ticket ID: invalid-id'
        >>> valid, msg = validate_related_to("0.31.0-W5-001", ["0.31.0-W5-001"])
        >>> valid
        False
        >>> msg
        '0.31.0-W5-001: relatedTo 不能包含自我參考'
        >>> valid, msg = validate_related_to("0.31.0-W5-001", ["0.31.0-W5-002", "0.31.0-W5-002"])
        >>> valid
        False
    """
    # Guard Clause 1：無相關 Ticket（空或 None）
    if not related_to:
        return True, None

    # Guard Clause 2：檢查所有 ID 的格式
    for ticket_ref in related_to:
        if not validate_ticket_id(ticket_ref):
            return False, f"{ticket_id}: relatedTo 包含無效的 Ticket ID: {ticket_ref}"

    # Guard Clause 3：檢查自我參考
    if ticket_id in related_to:
        return False, f"{ticket_id}: relatedTo 不能包含自我參考"

    # Guard Clause 4：檢查重複
    if len(related_to) != len(set(related_to)):
        duplicates = [item for item in related_to if related_to.count(item) > 1]
        unique_duplicates = list(set(duplicates))
        return False, f"{ticket_id}: relatedTo 包含重複 ID: {', '.join(unique_duplicates)}"

    return True, None


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
