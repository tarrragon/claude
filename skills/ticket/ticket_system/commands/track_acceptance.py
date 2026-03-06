"""
Ticket 驗收條件和執行日誌模組

負責管理驗收條件的勾選和執行日誌的追加。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("[ERROR] 此檔案不支援直接執行")
    print("=" * 60)
    print()
    print("正確使用方式：")
    print("  ticket track summary")
    print("  ticket track claim 0.31.0-W4-001")
    print()
    print("如尚未安裝，請執行：")
    print("  cd .claude/skills/ticket && uv tool install .")
    print()
    print("詳見 SKILL.md")
    print("=" * 60)
    sys.exit(1)



import argparse
import re
from datetime import datetime
from pathlib import Path

from ticket_system.lib.ticket_loader import (
    get_ticket_path,
    load_ticket,
    save_ticket,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    WarningMessages,
    InfoMessages,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_tracking_messages import (
    TrackAcceptanceMessages,
    format_msg,
)


def _validate_acceptance_context(
    ticket_id: str, ticket_body: str
) -> tuple[bool, str, str, str]:
    """
    驗證驗收條件上下文

    檢查 Ticket 是否包含有效的 Acceptance Criteria 區段。

    Args:
        ticket_id: Ticket ID
        ticket_body: Ticket body 內容

    Returns:
        (成功, 錯誤訊息, acceptance_section, acceptance_content)
        - 成功時返回 (True, "", section, content)
        - 失敗時返回 (False, 錯誤訊息, "", "")
    """
    if not ticket_body:
        return False, format_error(ErrorMessages.BODY_CONTENT_NOT_FOUND, ticket_id=ticket_id), "", ""

    acceptance_pattern = r"## Acceptance Criteria\n\n(.*?)(?=\n##|\Z)"
    match = re.search(acceptance_pattern, ticket_body, re.DOTALL)

    if not match:
        return False, format_error(ErrorMessages.ACCEPTANCE_CRITERIA_NOT_FOUND, ticket_id=ticket_id), "", ""

    acceptance_section = match.group(0)
    acceptance_content = match.group(1)
    return True, "", acceptance_section, acceptance_content


def _is_valid_data_row(line: str) -> bool:
    """
    判斷一行是否是有效的資料行

    檢查行是否以 | 開頭、不是分隔線、且第一個欄位是數字。

    Args:
        line: 表格行

    Returns:
        True 如果是有效的資料行
    """
    if not line.startswith("|") or "---" in line:
        return False

    cols = line.split("|")
    if len(cols) <= 1:
        return False

    first_col = cols[1].strip()
    if first_col == "#":
        return False

    try:
        int(first_col)
        return True
    except ValueError:
        return False


def _extract_data_rows(table_lines: list[str]) -> list[tuple[int, str]]:
    """
    提取表格中的資料行

    從 Markdown 表格中過濾出實際資料行（跳過標題、分隔線）。

    Args:
        table_lines: 表格所有行

    Returns:
        資料行清單，每個元素為 (行索引, 行內容)
    """
    return [(i, line) for i, line in enumerate(table_lines)
            if _is_valid_data_row(line)]


def _parse_acceptance_table(
    ticket_id: str, acceptance_content: str, index: int
) -> tuple[bool, str, list, int]:
    """
    解析驗收條件表格並驗證 index

    從 Markdown 表格中提取資料行，並驗證 index 是否有效。

    Args:
        ticket_id: Ticket ID（用於錯誤訊息）
        acceptance_content: Acceptance Criteria 區段的內容
        index: 目標行的索引（1-based）

    Returns:
        (成功, 錯誤訊息, data_lines, target_line_idx)
        - 成功時返回 (True, "", data_lines, target_line_idx)
        - 失敗時返回 (False, 錯誤訊息, [], -1)
    """
    table_lines = acceptance_content.strip().split("\n")
    data_lines = _extract_data_rows(table_lines)

    if not data_lines:
        return False, format_error(ErrorMessages.ACCEPTANCE_CRITERIA_PARSE_FAILED), [], -1

    # 驗證 index 範圍
    if index < 1 or index > len(data_lines):
        msg = format_error(ErrorMessages.ACCEPTANCE_CRITERIA_INDEX_OUT_OF_RANGE, max_index=len(data_lines), index=index)
        return False, msg, [], -1

    target_line_idx, target_line = data_lines[index - 1]
    return True, "", data_lines, target_line_idx


def _update_acceptance_status(
    table_lines: list[str],
    target_line_idx: int,
    new_status: str,
) -> str:
    """
    更新驗收條件狀態

    更新表格中目標行的狀態欄位。

    Args:
        table_lines: 表格所有行
        target_line_idx: 目標行的索引
        new_status: 新狀態（例：[x] 或 [ ]）

    Returns:
        更新後的表格內容（join 後的字串）
    """
    target_line = table_lines[target_line_idx]
    columns = target_line.split("|")

    # 狀態在最後一個 | 之前的欄位
    status_idx = len(columns) - 2
    columns[status_idx] = f" {new_status} "

    # 更新行
    table_lines[target_line_idx] = "|".join(columns)

    return "\n".join(table_lines)


def execute_check_acceptance(args: argparse.Namespace, version: str) -> int:
    """
    勾選或取消勾選驗收條件（在 frontmatter 中操作）

    支援命令格式：
    - ticket track check-acceptance <id> <index>
    - ticket track check-acceptance <id> <index> --uncheck

    改為操作 frontmatter 的 acceptance 欄位，而非 body 表格。
    """
    # 載入 Ticket
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 驗證 index 參數
    try:
        index = int(args.index)
        if index <= 0:
            print(format_error(ErrorMessages.ACCEPTANCE_CRITERIA_INDEX_NOT_POSITIVE, value=index))
            return 1
    except ValueError:
        print(format_error(ErrorMessages.ACCEPTANCE_CRITERIA_INDEX_NOT_INTEGER, value=args.index))
        return 1

    # 取得 acceptance 列表（來自 frontmatter）
    acceptance_list = ticket.get("acceptance", [])
    if not acceptance_list:
        print(format_error(ErrorMessages.ACCEPTANCE_CRITERIA_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 驗證 index 範圍
    if index < 1 or index > len(acceptance_list):
        msg = format_error(ErrorMessages.ACCEPTANCE_CRITERIA_INDEX_OUT_OF_RANGE, max_index=len(acceptance_list), index=index)
        print(msg)
        return 1

    # 取得目標項目
    target_item = acceptance_list[index - 1]
    uncheck = getattr(args, "uncheck", False)

    # 判斷當前狀態和新狀態
    if uncheck:
        # 取消勾選：[x] ... → [ ] ...
        if target_item.startswith("[x]"):
            new_item = target_item.replace("[x]", "[ ]", 1)
        elif target_item.startswith("[ ]"):
            print(format_msg(TrackAcceptanceMessages.ALREADY_UNCHECKED_INFO, index=index))
            return 0
        else:
            # 無前綴的項視為未勾選，無需更新
            print(format_msg(TrackAcceptanceMessages.ALREADY_UNCHECKED_INFO, index=index))
            return 0
    else:
        # 勾選：[ ] ... → [x] ... 或無前綴 → [x]
        if target_item.startswith("[x]"):
            print(format_msg(TrackAcceptanceMessages.ALREADY_CHECKED_INFO, index=index))
            return 0
        elif target_item.startswith("[ ]"):
            new_item = target_item.replace("[ ]", "[x]", 1)
        else:
            # 無前綴的項，加上 [x] 前綴
            new_item = f"[x] {target_item}"

    # 更新 acceptance 列表
    acceptance_list[index - 1] = new_item
    ticket["acceptance"] = acceptance_list

    # 保存
    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    # 輸出結果
    status_text = TrackAcceptanceMessages.STATUS_TEXT_CHECKED if not uncheck else TrackAcceptanceMessages.STATUS_TEXT_UNCHECKED
    new_status = new_item.split(" ", 1)[0]  # 取前綴如 [x] 或 [ ]
    print(format_info(InfoMessages.ACCEPTANCE_CRITERIA_UPDATED, ticket_id=args.ticket_id, index=index, status_text=status_text))
    print(f"{TrackAcceptanceMessages.NEW_STATUS_PREFIX} {new_status}")

    return 0


def execute_accept_creation(args: argparse.Namespace, version: str) -> int:
    """
    標記 Ticket 建立後驗收已通過

    支援命令格式：
    - ticket track accept-creation <id>

    將 frontmatter 中的 creation_accepted 欄位設為 true。
    既有 Ticket 缺少此欄位時視為 false。
    """
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 取得當前 creation_accepted 狀態（預設為 false）
    creation_accepted = ticket.get("creation_accepted", False)

    if creation_accepted:
        # 已經通過驗收
        msg = format_msg(
            TrackAcceptanceMessages.ACCEPT_CREATION_ALREADY_ACCEPTED_FORMAT,
            ticket_id=args.ticket_id
        )
        print(msg)
        return 0

    # 標記建立後驗收已通過
    ticket["creation_accepted"] = True

    # 保存
    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    # 輸出結果
    msg = format_msg(
        TrackAcceptanceMessages.ACCEPT_CREATION_SUCCESS_FORMAT,
        ticket_id=args.ticket_id
    )
    print(msg)

    return 0


def execute_append_log(args: argparse.Namespace, version: str) -> int:
    """
    追加執行日誌

    支援命令格式：
    - ticket track append-log <id> --section "Problem Analysis" "內容"
    - ticket track append-log <id> --section "Solution" "內容"
    - ticket track append-log <id> --section "Test Results" "內容"
    - ticket track append-log <id> --section "Execution Log" "內容"
    """
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 驗證 section 參數
    valid_sections = TrackAcceptanceMessages.VALID_SECTIONS
    section = args.section
    if section not in valid_sections:
        print(format_error(ErrorMessages.INVALID_SECTION, section=section))
        print(f"{TrackAcceptanceMessages.VALID_VALUES_PREFIX} {', '.join(valid_sections)}")
        return 1

    # 取得內容
    content = args.content

    # 獲取 Ticket 內容
    body = ticket.get("_body", "")
    if not body:
        print(format_error(ErrorMessages.BODY_CONTENT_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 尋找對應的區段（## Section Name）
    section_pattern = rf"## {re.escape(section)}\n(.*?)(?=\n##|\Z)"
    match = re.search(section_pattern, body, re.DOTALL)

    if not match:
        print(format_error(ErrorMessages.SECTION_NOT_FOUND, ticket_id=args.ticket_id, section=section))
        return 1

    section_start = match.start()
    section_end = match.end()
    section_text = match.group(0)
    section_content = match.group(1)

    # 生成時間戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 對於 Execution Log，格式化為列表項
    if section == "Execution Log":
        new_entry = f"\n{format_msg(TrackAcceptanceMessages.LOG_TIMESTAMP_FORMAT, timestamp=timestamp, content=content)}"
    else:
        # 其他區段直接追加
        new_entry = f"\n{content}"

    # 追加內容
    updated_section = section_text + new_entry

    # 更新 body
    new_body = body[:section_start] + updated_section + body[section_end:]

    # 更新 Ticket
    ticket["_body"] = new_body

    # 保存
    ticket_path = Path(ticket.get("_path", get_ticket_path(version, args.ticket_id)))
    save_ticket(ticket, ticket_path)

    # 輸出結果
    print(format_info(InfoMessages.LOG_APPENDED, ticket_id=args.ticket_id, section=section))
    print(f"{TrackAcceptanceMessages.TIMESTAMP_PREFIX} {timestamp}")
    print(f"{TrackAcceptanceMessages.CONTENT_PREFIX} {content}")

    return 0
