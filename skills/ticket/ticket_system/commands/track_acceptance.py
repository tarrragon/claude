"""
Ticket 驗收條件和執行日誌模組

負責管理驗收條件的勾選和執行日誌的追加。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    import sys
    from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY
    print(SEPARATOR_PRIMARY)
    print("[ERROR] 此檔案不支援直接執行")
    print(SEPARATOR_PRIMARY)
    print()
    print("正確使用方式：")
    print("  ticket track summary")
    print("  ticket track claim 0.31.0-W4-001")
    print()
    print("如尚未安裝，請執行：")
    print("  cd .claude/skills/ticket && uv tool install .")
    print()
    print("詳見 SKILL.md")
    print(SEPARATOR_PRIMARY)
    sys.exit(1)



import argparse
import re
from datetime import datetime
from pathlib import Path

from ticket_system.lib.file_lock import file_lock
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
from ticket_system.lib.precondition import require_in_progress
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
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


def _parse_acceptance_index(index_input: str, acceptance_items: list) -> tuple[bool, str, int]:
    """
    解析驗收條件索引，支援三種輸入方式。

    Args:
        index_input: 使用者輸入，可以是：
                     - 1-based 整數："1", "2", "3"（現有功能）
                     - 0-based 整數："0"（新功能，轉換為 1-based）
                     - 文字搜尋："任務實作完成"（新功能，模糊比對）
        acceptance_items: 驗收條件清單

    Returns:
        (成功, 錯誤訊息或資訊, 1-based 索引)
        - 成功時返回 (True, "", 1-based 索引)
        - 失敗時返回 (False, 錯誤訊息, -1)
    """
    # 先嘗試解析為整數
    try:
        n = int(index_input)

        # 特殊情況：0 被視為 0-based 索引，對應第 1 個項目（1-based）
        if n == 0:
            if len(acceptance_items) >= 1:
                return True, "", 1
            else:
                msg = format_error(
                    ErrorMessages.ACCEPTANCE_CRITERIA_INDEX_OUT_OF_RANGE,
                    max_index=len(acceptance_items),
                    index=0
                )
                return False, msg, -1

        # 檢查是否為有效的 1-based（1 到 len 範圍）
        if 1 <= n <= len(acceptance_items):
            return True, "", n

        # 超出範圍
        msg = format_error(
            ErrorMessages.ACCEPTANCE_CRITERIA_INDEX_OUT_OF_RANGE,
            max_index=len(acceptance_items),
            index=n
        )
        return False, msg, -1

    except ValueError:
        # 不是整數，嘗試文字搜尋
        pass

    # 文字搜尋（模糊比對）
    matches = []
    for i, item in enumerate(acceptance_items):
        # 提取文字（移除前綴如 [x] 或 [ ]）
        item_text = item
        if item.startswith("["):
            # 移除 [x] 或 [ ] 前綴
            item_text = item.split("]", 1)[1].strip() if "]" in item else item

        if index_input in item_text:
            matches.append(i + 1)  # 1-based

    if len(matches) == 1:
        return True, "", matches[0]
    elif len(matches) > 1:
        msg = format_error(
            ErrorMessages.ACCEPTANCE_CRITERIA_INDEX_NOT_INTEGER,
            value=f"'{index_input}' 匹配到 {len(matches)} 個項目，請使用索引"
        )
        return False, msg, -1
    else:
        msg = format_error(
            ErrorMessages.ACCEPTANCE_CRITERIA_INDEX_NOT_INTEGER,
            value=f"找不到包含 '{index_input}' 的驗收條件"
        )
        return False, msg, -1


def execute_check_acceptance(args: argparse.Namespace, version: str) -> int:
    """
    勾選或取消勾選驗收條件（在 frontmatter 中操作）

    支援命令格式：
    - ticket track check-acceptance <id> <index>               # 單一勾選（1-based 整數或文字搜尋）
    - ticket track check-acceptance <id> <index> --uncheck     # 單一取消勾選
    - ticket track check-acceptance <id> --all                 # 批量勾選全部
    - ticket track check-acceptance <id> --all --uncheck       # 批量取消勾選全部

    支援三種 index 格式：
    - 1-based 整數："1", "2", "3"（現有功能）
    - 0-based 整數："0", "1", "2"（自動換算為 1-based）
    - 文字搜尋："任務實作完成"（模糊比對驗收條件文字）
    """
    # 驗證參數互斥性
    use_all = getattr(args, "all", False)
    index_arg = getattr(args, "index", None)

    # 用戶輸入錯誤路徑均為業務拒絕（return 2），詳見 cli-exit-code-rules.md 規則 2
    if use_all and index_arg is not None:
        print(format_error(ErrorMessages.CHECK_ACCEPTANCE_ALL_WITH_INDEX))
        return 2

    if not use_all and index_arg is None:
        print(format_error(ErrorMessages.CHECK_ACCEPTANCE_MISSING_INDEX))
        return 2

    # W14-045: file_lock 包圍 load → modify → save，消除 logical race。
    # Lock 範圍涵蓋 _execute_single_check_acceptance / _execute_batch_check_acceptance
    # 內部的 save_ticket 呼叫。
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        # 載入 Ticket（找不到 ticket 為用戶輸入錯誤 → return 2）
        ticket, error = load_and_validate_ticket(version, args.ticket_id)
        if error:
            return 2

        # 取得 acceptance 列表（來自 frontmatter）
        acceptance_list = ticket.get("acceptance", [])
        if not acceptance_list:
            # 業務拒絕：ticket 無 acceptance 條件可勾選
            print(format_error(ErrorMessages.ACCEPTANCE_CRITERIA_NOT_FOUND, ticket_id=args.ticket_id))
            return 2

        uncheck = getattr(args, "uncheck", False)

        if use_all:
            # 批量操作
            return _execute_batch_check_acceptance(
                args, version, ticket, acceptance_list, uncheck
            )
        else:
            # 單一操作
            return _execute_single_check_acceptance(
                args, version, ticket, acceptance_list, index_arg, uncheck
            )


def _execute_single_check_acceptance(
    args: argparse.Namespace,
    version: str,
    ticket: dict,
    acceptance_list: list,
    index_arg: str,
    uncheck: bool,
) -> int:
    """執行單一驗收條件勾選/取消勾選"""
    # 解析 index 參數（支援三種格式）
    success, msg, index = _parse_acceptance_index(index_arg, acceptance_list)
    if not success:
        # 業務拒絕：用戶輸入的 index 無法解析（不存在或格式錯誤）
        print(msg)
        return 2

    # 取得目標項目
    target_item = acceptance_list[index - 1]

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
    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    save_ticket(ticket, ticket_path)

    # 輸出結果
    status_text = TrackAcceptanceMessages.STATUS_TEXT_CHECKED if not uncheck else TrackAcceptanceMessages.STATUS_TEXT_UNCHECKED
    new_status = new_item.split(" ", 1)[0]  # 取前綴如 [x] 或 [ ]
    print(format_info(InfoMessages.ACCEPTANCE_CRITERIA_UPDATED, ticket_id=args.ticket_id, index=index, status_text=status_text))
    print(f"{TrackAcceptanceMessages.NEW_STATUS_PREFIX} {new_status}")

    return 0


def _apply_check_to_item(item: str, uncheck: bool) -> tuple[str | None, bool]:
    """
    應用勾選/取消勾選操作到單一驗收條件項目

    根據 uncheck 參數決定勾選或取消勾選行為。
    返回 (更新後的項目, 是否有變更)。
    無變更時返回 (None, False)。

    Args:
        item: 驗收條件項目文本
        uncheck: True 表示取消勾選，False 表示勾選

    Returns:
        (更新後的項目或 None, 是否有變更)
    """
    if uncheck:
        # 取消勾選：[x] ... → [ ] ...
        if item.startswith("[x]"):
            return item.replace("[x]", "[ ]", 1), True
        # [ ] 或無前綴視為已經未勾選
        return None, False

    # 勾選：[ ] ... → [x] ... 或無前綴 → [x]
    if item.startswith("[x]"):
        # 已經勾選
        return None, False
    elif item.startswith("[ ]"):
        return item.replace("[ ]", "[x]", 1), True
    else:
        # 無前綴的項，加上 [x] 前綴
        return f"[x] {item}", True


def _execute_batch_check_acceptance(
    args: argparse.Namespace,
    version: str,
    ticket: dict,
    acceptance_list: list,
    uncheck: bool,
) -> int:
    """執行批量驗收條件勾選/取消勾選"""
    count = 0

    # 遍歷所有驗收條件，應用狀態變更
    for i, item in enumerate(acceptance_list):
        updated_item, changed = _apply_check_to_item(item, uncheck)
        if changed:
            acceptance_list[i] = updated_item
            count += 1

    # 更新 acceptance 列表
    ticket["acceptance"] = acceptance_list

    # 保存
    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    save_ticket(ticket, ticket_path)

    # 輸出結果
    total_count = len(acceptance_list)
    if uncheck:
        print(format_info(
            InfoMessages.ACCEPTANCE_CRITERIA_UPDATED,
            ticket_id=args.ticket_id,
            index=f"全部 ({count}/{total_count})",
            status_text=TrackAcceptanceMessages.STATUS_TEXT_UNCHECKED
        ))
        print(format_msg(
            TrackAcceptanceMessages.BATCH_UNCHECK_SUMMARY_FORMAT,
            ticket_id=args.ticket_id,
            unchecked_count=count,
            total_count=total_count
        ))
    else:
        print(format_info(
            InfoMessages.ACCEPTANCE_CRITERIA_UPDATED,
            ticket_id=args.ticket_id,
            index=f"全部 ({count}/{total_count})",
            status_text=TrackAcceptanceMessages.STATUS_TEXT_CHECKED
        ))
        print(format_msg(
            TrackAcceptanceMessages.BATCH_CHECK_SUMMARY_FORMAT,
            ticket_id=args.ticket_id,
            checked_count=count,
            total_count=total_count
        ))

    return 0


def execute_accept_creation(args: argparse.Namespace, version: str) -> int:
    """
    標記 Ticket 建立後驗收已通過

    支援命令格式：
    - ticket track accept-creation <id>

    將 frontmatter 中的 creation_accepted 欄位設為 true。
    既有 Ticket 缺少此欄位時視為 false。
    """
    # W14-045: file_lock 包圍 load → modify → save
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
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
        ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
        save_ticket(ticket, ticket_path)

    # 輸出結果
    msg = format_msg(
        TrackAcceptanceMessages.ACCEPT_CREATION_SUCCESS_FORMAT,
        ticket_id=args.ticket_id
    )
    print(msg)

    return 0


def _replace_or_append_section_content(
    *,
    section_text: str,
    section_content: str,
    new_entry: str,
) -> str:
    """W3-035: Schema 章節含 placeholder 時替換，否則正常 append。

    Why: 4/9 W3 ANA saffron 都遇到 append-log 不替換 placeholder 導致
    body-schema-checker false positive 阻擋 complete，被迫用 --skip-body-check。

    策略：
    1. 用 ticket_validator._is_placeholder 偵測 section_content 是否僅含 placeholder
       （已內建剝除 HTML 註解 / 分隔符 / 表格的邏輯，與 body-schema-checker 一致）
    2. 是 placeholder：保留 section header + Schema HTML 註解，移除待填寫文字，
       再 append new_entry
    3. 否：正常 section_text + new_entry

    Args:
        section_text: 完整 section（含 header + content）
        section_content: section content only（不含 header）
        new_entry: 要追加的新內容（已含開頭換行）

    Returns:
        重組後的完整 section 文字
    """
    from ticket_system.lib.ticket_validator import _is_placeholder

    if not _is_placeholder(section_content):
        # 已有實質內容，正常 append
        return section_text + new_entry

    # placeholder-only：保留 header + Schema HTML 註解，移除其他 placeholder 文字
    # section_text 結構：`## Header\n[content_with_placeholders]`
    # 提取 header line
    header_end = section_text.find("\n")
    if header_end == -1:
        # 不可能發生（find_section 保證有 header），保守處理
        return section_text + new_entry

    header_line = section_text[: header_end + 1]  # 含換行
    content_part = section_text[header_end + 1 :]

    # 保留 Schema 註解行（`<!-- Schema[...]: ... -->`），可能跨多行
    preserved_lines = []
    schema_pattern = re.compile(r"<!--\s*Schema\[[^\]]+\]:")
    # 逐行處理：保留 Schema 註解（含其多行延續）；丟棄其他 placeholder 文字
    lines = content_part.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if schema_pattern.search(line):
            # 收集此 Schema 註解（可能跨多行直到 `-->`）
            preserved_lines.append(line)
            if "-->" not in line:
                # 多行 Schema 註解：繼續收集直到 -->
                j = i + 1
                while j < len(lines):
                    preserved_lines.append(lines[j])
                    if "-->" in lines[j]:
                        break
                    j += 1
                i = j + 1
            else:
                i += 1
            continue
        # 其他行（placeholder 文字 / 空行 / 一般 HTML 註解）一律丟棄
        i += 1

    preserved_content = "".join(preserved_lines).rstrip()
    if preserved_content:
        # header + Schema 註解 + 新內容
        return header_line + preserved_content + "\n" + new_entry.lstrip("\n") + "\n"
    # 無 Schema 註解：純 header + 新內容
    return header_line + new_entry.lstrip("\n") + "\n"


def execute_append_log(args: argparse.Namespace, version: str) -> int:
    """
    追加執行日誌

    支援命令格式：
    - ticket track append-log <id> --section "Problem Analysis" "內容"
    - ticket track append-log <id> --section "Solution" "內容"
    - ticket track append-log <id> --section "Test Results" "內容"
    - ticket track append-log <id> --section "Execution Log" "內容"
    """
    # W14-045: file_lock 包圍 load → modify → save，消除 logical race。
    # append-log 為高頻並發 caller（PM/agent 持續寫入），race 風險最高。
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        return _execute_append_log_locked(args, version)


def _execute_append_log_locked(args: argparse.Namespace, version: str) -> int:
    """append-log 主邏輯（已位於 file_lock 內）。"""
    import sys as _sys

    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # W3-044: body-op precondition 檢查（status 必須 in_progress 或 completed-allow）
    force = bool(getattr(args, "force", False))
    ok, error_msg = require_in_progress(
        ticket,
        args.ticket_id,
        "append-log",
        allow_completed=True,  # append-log 支援 completed 補 review
        force=force,
    )
    if not ok:
        _sys.stderr.write(error_msg + "\n")
        return 2

    # 驗證 section 參數
    valid_sections = TrackAcceptanceMessages.VALID_SECTIONS
    section = args.section
    if section not in valid_sections:
        print(format_error(ErrorMessages.INVALID_SECTION, section=section))
        print(f"{TrackAcceptanceMessages.VALID_VALUES_PREFIX} {', '.join(valid_sections)}")
        return 1

    # 取得內容
    content = args.content

    # W17-208 + W1-068: 偵測寫入 Schema 章節時內容含 ## H2 標題
    # W17-208 (stderr warning) + W1-068 方案 B（自動降級 H2 → H3 源頭阻斷）
    # 動機：append-log 寫入應為既有章節 H3 子節；H2 會切斷 Schema 章節範圍（W17-072）
    # W1-038 ANA 結論：source code 規範化（re.sub）比事後偵測更可靠，
    # 避免 W1-037 三 agent 連續違規 + PM 批次降級連帶 H4 false negative 鏈
    # 修改注意：移除 re.sub 自動降級前須評估 W17-072 complete 層是否獨立足夠，
    # 並更新 .claude/pm-rules/context-bundle-spec.md 條款 2「雙層防護」表格。
    schema_sections_for_h2_check = {
        "Solution", "Test Results", "Problem Analysis",
        "Context Bundle", "NeedsContext", "Exit Status", "Completion Info",
    }
    if section in schema_sections_for_h2_check and content:
        if re.search(r'(?m)^## ', content):
            import sys as _sys
            _sys.stderr.write(
                "[append-log] WARNING: 偵測到內容含 H2 標題；append-log 寫入應為既有章節的 "
                "H3 子節，避免切斷 Schema 章節範圍（W17-072）。"
                "已自動降級 H2 → H3（W1-068 方案 B：源頭阻斷）。\n"
            )
            # W1-068（W1-038 方案 B）: 自動降級 H2 → H3 規範化（只匹配行首 H2，不影響 H3+）
            content = re.sub(r'(?m)^## ', '### ', content)

    # 獲取 Ticket 內容
    body = ticket.get("_body", "")
    if not body:
        print(format_error(ErrorMessages.BODY_CONTENT_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    # 尋找對應的區段標題（W17-117.1: 統一抽至 section_locator helper）
    from ticket_system.lib.section_locator import find_section
    match = find_section(body, section)

    if not match.found:
        # 列出該 ticket md 所有 ^## 標題引導用戶（W17-008.9 B 方案）
        print(format_error(ErrorMessages.SECTION_NOT_FOUND, ticket_id=args.ticket_id, section=section))
        if match.all_headers:
            print(f"  該 ticket 現有 ## 標題：")
            for header in match.all_headers:
                print(f"    - {header}")
        else:
            print(f"  該 ticket md 無任何 ## 標題")
        return 1

    # 擷取整個 section 範圍（從標題行到下一個 ## 或文件結尾）
    section_start = match.start
    content_start = match.content_start
    section_end = match.end
    section_text = match.text
    section_content = match.content

    # 生成時間戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 對於 Execution Log，格式化為列表項
    if section == "Execution Log":
        new_entry = f"\n{format_msg(TrackAcceptanceMessages.LOG_TIMESTAMP_FORMAT, timestamp=timestamp, content=content)}"
    else:
        # 其他區段直接追加
        new_entry = f"\n{content}"

    # W3-035: 若 section_content 為 placeholder-only（含 Schema 註解 + 待填寫文字），
    # 改用 new_entry 替換 placeholder 而非 append，避免 placeholder 殘留導致
    # body-schema-checker false positive 阻擋 complete。
    # Execution Log 維持 append 語意（每筆 log 都是新事件）。
    if section != "Execution Log":
        updated_section = _replace_or_append_section_content(
            section_text=section_text,
            section_content=section_content,
            new_entry=new_entry,
        )
    else:
        updated_section = section_text + new_entry

    # 更新 body
    new_body = body[:section_start] + updated_section + body[section_end:]

    # W11-003.3 Layer 2：寫回前 idempotent dedupe 重複 Schema H2，避免歷史殘留 placeholder
    # 與當前內容並存造成 acceptance-auditor 誤報（PC-110 同源防護）
    try:
        from ticket_system.lib.ticket_builder import dedupe_schema_sections
        new_body = dedupe_schema_sections(new_body)
    except Exception as exc:
        # 失敗時保留原 body 寫入；同時將異常訊息輸出到 stderr 供觀察（quality-baseline 規則 4）
        import sys as _sys
        _sys.stderr.write(f"[append-log] dedupe_schema_sections skipped: {exc}\n")

    # 更新 Ticket
    ticket["_body"] = new_body

    # 保存
    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    save_ticket(ticket, ticket_path)

    # 輸出結果
    print(format_info(InfoMessages.LOG_APPENDED, ticket_id=args.ticket_id, section=section))
    print(f"{TrackAcceptanceMessages.TIMESTAMP_PREFIX} {timestamp}")
    print(f"{TrackAcceptanceMessages.CONTENT_PREFIX} {content}")

    return 0
