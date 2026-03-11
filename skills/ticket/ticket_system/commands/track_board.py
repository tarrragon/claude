"""
Ticket 看板命令模組

提供 Kanban 風格的看板視圖，視覺化展示各狀態的任務分佈。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    import sys
    # 模組直接執行時套件 import 不可用，用局部常數替代 SEPARATOR_PRIMARY
    _SEP = "=" * 60
    print(_SEP)
    print("[ERROR] 此檔案不支援直接執行")
    print(_SEP)
    print()
    print("正確使用方式：")
    print("  ticket track board")
    print("  ticket track board --version 0.31.0")
    print("  ticket track board --ascii")
    print()
    print("詳見 SKILL.md")
    print(_SEP)
    sys.exit(1)


import argparse
import shutil
import sys
import unicodedata
from typing import Any, Dict, List

from ticket_system.lib.ticket_loader import (
    list_tickets,
    resolve_version,
)
from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
)
from ticket_system.lib.messages import format_error, format_info
from ticket_system.lib.command_tracking_messages import (
    TrackBoardMessages,
    format_msg,
)
from ticket_system.lib.ui_constants import (
    SEPARATOR_PRIMARY,
    SEPARATOR_SECONDARY,
    SEPARATOR_WIDE,
    SEPARATOR_WIDE_DASH,
)
from ticket_system.lib.ticket_validator import extract_wave_from_ticket_id
from typing import Tuple


def filter_incomplete_tickets(tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """過濾未完成任務（保留 pending, in_progress, blocked），排除無效 ticket"""
    return [
        t for t in tickets
        if t.get("status") is not None and t.get("status") != STATUS_COMPLETED
    ]


def extract_wave_number(ticket_id: str) -> str:
    """從 Ticket ID 提取 Wave 號（顯示格式，如 W9）"""
    wave = extract_wave_from_ticket_id(ticket_id)
    return f"W{wave}" if wave is not None else "Unknown"


def group_by_wave(tickets: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按 Wave 分組，升序排列"""
    groups = {}
    for ticket in tickets:
        wave = extract_wave_number(ticket.get("id", ""))
        if wave not in groups:
            groups[wave] = []
        groups[wave].append(ticket)

    # 按 Wave 號排序（提取數字）
    sorted_waves = sorted(groups.keys(), key=lambda w: int(w[1:]) if w != "Unknown" else 9999)
    return {w: groups[w] for w in sorted_waves}


def build_tree_structure(tickets: List[Dict[str, Any]]) -> Tuple[Dict[str, List[str]], List[str]]:
    """構建樹狀索引"""
    ticket_ids = {t.get("id") for t in tickets}
    parent_to_children: Dict[str, List[str]] = {}
    root_ids = []

    for ticket in tickets:
        tid = ticket.get("id", "")
        # 判斷是否為子任務（ID 包含 "." 如 W7-001.1）
        if "." in tid.split("-")[-1]:
            # 找父任務 ID
            parts = tid.rsplit(".", 1)
            parent_id = parts[0]
            if parent_id in ticket_ids:
                if parent_id not in parent_to_children:
                    parent_to_children[parent_id] = []
                parent_to_children[parent_id].append(tid)
            else:
                root_ids.append(tid)
        else:
            root_ids.append(tid)

    # 排序子任務
    for parent in parent_to_children:
        parent_to_children[parent].sort()
    root_ids.sort()

    return parent_to_children, root_ids


def render_tree_node(
    ticket_id: str,
    tickets_dict: Dict[str, Dict[str, Any]],
    tree_structure: Dict[str, List[str]],
    prefix: str = "",
    is_last: bool = True
) -> List[str]:
    """遞迴渲染單一節點"""
    lines = []
    ticket = tickets_dict.get(ticket_id)
    if not ticket:
        return lines

    # 節點符號
    connector = "└── " if is_last else "├── "

    # 格式化顯示
    short_id = simplify_ticket_id(ticket_id)
    priority = ticket.get("priority", "P2")
    # Tree view 顯示完整標題（不截斷）
    title = ticket.get("title", "")

    lines.append(f"{prefix}{connector}{short_id} [{priority}] {title}")

    # 子節點前綴
    child_prefix = prefix + ("    " if is_last else "│   ")

    # 遞迴渲染子節點
    children = tree_structure.get(ticket_id, [])
    for i, child_id in enumerate(children):
        child_is_last = (i == len(children) - 1)
        lines.extend(render_tree_node(child_id, tickets_dict, tree_structure, child_prefix, child_is_last))

    return lines


def render_board_tree(
    tickets: List[Dict[str, Any]],
    version: str,
    show_all: bool = False
) -> str:
    """
    渲染樹狀看板

    Args:
        tickets: Ticket 清單
        version: 版本號
        show_all: 是否顯示所有任務（包含已完成）
    """
    lines = []

    # 標題
    if show_all:
        lines.append(format_msg(TrackBoardMessages.TREE_TITLE_ALL, version=version))
    else:
        lines.append(format_msg(TrackBoardMessages.TREE_TITLE_INCOMPLETE, version=version))
    lines.append(SEPARATOR_SECONDARY)
    lines.append("")

    # 過濾任務
    if show_all:
        filtered = tickets
    else:
        filtered = filter_incomplete_tickets(tickets)

    if not filtered:
        lines.append(TrackBoardMessages.NO_TASKS_TEXT)
        return "\n".join(lines)

    # 按 Wave 分組
    wave_groups = group_by_wave(filtered)

    # 建立 ticket_id -> ticket 映射
    tickets_dict = {t.get("id"): t for t in filtered}

    # 渲染每個 Wave
    for wave, wave_tickets in wave_groups.items():
        # Wave 標題
        lines.append(format_msg(TrackBoardMessages.WAVE_TITLE_FORMAT, wave=wave, count=len(wave_tickets)))

        # 構建該 Wave 的樹狀結構
        tree_structure, root_ids = build_tree_structure(wave_tickets)

        # 渲染根節點
        for i, root_id in enumerate(root_ids):
            is_last = (i == len(root_ids) - 1)
            lines.extend(render_tree_node(root_id, tickets_dict, tree_structure, "", is_last))

        lines.append("")  # Wave 間空行

    return "\n".join(lines)


def simplify_ticket_id(full_id: str) -> str:
    """
    簡化 Ticket ID（去除版本前綴）

    Args:
        full_id: 完整 ID（如 "0.31.0-W7-001"）

    Returns:
        str: 簡化 ID（如 "W7-001"）

    邏輯：
        1. 驗證輸入（None 或空字串 → "Unknown"）
        2. 分割字串（以 "-" 為分隔符）
        3. 組合 Wave 和序號
    """
    # Guard Clause：驗證輸入
    if not full_id:
        return "Unknown"

    # 分割字串
    parts = full_id.split("-")

    # 組合 Wave 和序號
    if len(parts) >= 3:
        # 預期格式: ["版本號", "Wave", "序號"]
        # 如 "0.31.0-W7-001" → ["0.31.0", "W7", "001"]
        return f"{parts[1]}-{parts[2]}"
    else:
        # 如果無法分割，返回原始值
        return full_id


def get_char_display_width(char: str) -> int:
    """
    計算單一字元的顯示寬度（考慮中文字元和全形字元）

    寬字元（CJK 字元、全形標點等）佔 2 寬，其他字元佔 1 寬

    Args:
        char: 單一字元

    Returns:
        int: 顯示寬度（1 或 2）

    說明：
        east_asian_width() 回傳: W(寬), F(全形), A(歧義), H(半形), N(中性), Na(狹義)
        W 和 F 視為寬字元（2 寬），其他視為窄字元（1 寬）
    """
    width_category = unicodedata.east_asian_width(char)
    return 2 if width_category in ('W', 'F') else 1


def calculate_visual_width(text: str) -> int:
    """
    計算文本的視覺寬度（考慮中文字元和全形字元）

    寬字元（CJK 字元、全形標點等）佔 2 寬，其他字元佔 1 寬

    Args:
        text: 輸入文本

    Returns:
        int: 視覺寬度

    邏輯：
        1. 逐字遍歷
        2. 使用 get_char_display_width() 計算單一字元寬度
        3. 累計總寬度
    """
    total_width = 0
    for char in text:
        total_width += get_char_display_width(char)
    return total_width


def ljust_with_chinese_width(text: str, width: int) -> str:
    """
    填充文本至指定視覺寬度（考慮中文字元）

    與 str.ljust() 相似，但正確計算中文字元寬度

    Args:
        text: 輸入文本
        width: 目標視覺寬度

    Returns:
        str: 填充後的文本

    邏輯：
        1. 計算文本的視覺寬度
        2. 計算需要填充的空格數
        3. 返回填充後的文本

    Example:
        >>> ljust_with_chinese_width("測試", 10)  # 中文 2 寬 + 2 寬 = 4 寬
        '測試      '  # 補 6 個空格至 10 寬
    """
    visual_width = calculate_visual_width(text)
    padding_count = max(0, width - visual_width)
    return text + " " * padding_count


def truncate_title(title: str, max_length: int = 15) -> str:
    """
    截斷標題並加上省略符號

    考慮字元視覺寬度（CJK 字元和全形字元 = 2 寬，其他 = 1 寬）

    Args:
        title: 原始標題
        max_length: 最大寬度（預設 15）

    Returns:
        str: 截斷後的標題

    邏輯：
        1. 驗證輸入
        2. 逐字計算視覺寬度
        3. 當寬度超過上限時截斷
        4. 新增省略符號 ".."
    """
    # Guard Clause：驗證輸入
    if not title or max_length <= 0:
        return ""

    # 逐字計算視覺寬度，找出截斷位置
    total_width = 0
    truncate_pos = len(title)

    for i, char in enumerate(title):
        char_width = get_char_display_width(char)

        # 當加入當前字元會超過上限時截斷
        if total_width + char_width > max_length:
            truncate_pos = i
            break

        total_width += char_width

    # 截斷並加省略符
    if truncate_pos < len(title):
        return title[:truncate_pos] + ".."
    else:
        return title


def organize_by_status(tickets: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    將 Ticket 清單按狀態分組

    Args:
        tickets: Ticket 清單

    Returns:
        Dict[str, List]: 按狀態分組的 Ticket 字典
            - pending: 待處理清單
            - in_progress: 進行中清單
            - completed: 已完成清單
            - blocked: 被阻塞清單

    邏輯：
        1. 初始化結果字典
        2. 驗證輸入
        3. 按狀態分組
    """
    # 初始化結果字典
    result = {
        STATUS_PENDING: [],
        STATUS_IN_PROGRESS: [],
        STATUS_COMPLETED: [],
        STATUS_BLOCKED: [],
    }

    # Guard Clause：驗證輸入
    if not tickets:
        return result

    # 按狀態分組
    for ticket in tickets:
        status = ticket.get("status", STATUS_PENDING)

        if status == STATUS_PENDING:
            result[STATUS_PENDING].append(ticket)
        elif status == STATUS_IN_PROGRESS:
            result[STATUS_IN_PROGRESS].append(ticket)
        elif status == STATUS_COMPLETED:
            result[STATUS_COMPLETED].append(ticket)
        elif status == STATUS_BLOCKED:
            result[STATUS_BLOCKED].append(ticket)
        # 無效狀態被忽略

    return result


def prepare_cards(
    board_data: Dict[str, List[Dict[str, Any]]], args: argparse.Namespace
) -> Dict[str, List[Dict[str, Any]]]:
    """
    準備卡片資料（提取並格式化顯示欄位）

    Args:
        board_data: 按狀態分組的 Ticket 資料
        args: 命令列參數（用於取得寬度等設定）

    Returns:
        Dict[str, List[Card]]: 按狀態分組的卡片資料

    處理邏輯：
        - 簡化 ID（去除版本前綴）
        - 截斷標題（超過 15 字則加 ".."）
        - 格式化優先級（[P0]/[P1]/[P2]/[P3]）
        - 計算卡片高度（3-4 行）
    """
    # 提取參數
    max_width = getattr(args, "width", 20) or 20

    # 初始化結果字典（結構同 board_data）
    result = {
        STATUS_PENDING: [],
        STATUS_IN_PROGRESS: [],
        STATUS_COMPLETED: [],
        STATUS_BLOCKED: [],
    }

    # 遍歷每個狀態，處理卡片
    for status in [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_BLOCKED]:
        for ticket in board_data[status]:
            # 簡化 ID
            short_id = simplify_ticket_id(ticket.get("id", "Unknown"))

            # 截斷標題
            title = ticket.get("title", "")
            short_title = truncate_title(title, max_width - 4)

            # 取得優先級（預設 P2）
            priority = ticket.get("priority", "P2")
            priority_tag = f"[{priority}]"

            # 建立卡片
            card = {
                "id": short_id,
                "title": short_title,
                "priority": priority_tag,
                "status": status,
                "height": 3,
            }

            result[status].append(card)

    return result


def calculate_layout(
    cards_by_status: Dict[str, List[Dict[str, Any]]], args: argparse.Namespace
) -> Dict[str, Any]:
    """
    計算看板佈局參數

    Args:
        cards_by_status: 按狀態分組的卡片資料
        args: 命令列參數

    Returns:
        Dict[str, Any]: 佈局參數字典
            - terminal_width: 終端寬度
            - card_width: 卡片寬度
            - column_spacing: 欄位間距
            - max_rows: 最大行數
            - use_ascii: 是否使用 ASCII 版本

    邏輯：
        1. 取得終端寬度
        2. 判斷 ASCII 版本
        3. 計算卡片寬度
        4. 計算欄距
        5. 計算最大行數
    """
    # Step 1: 取得終端寬度
    try:
        terminal_width = shutil.get_terminal_size().columns
    except Exception:
        terminal_width = 120  # 預設寬度

    # Step 2: 判斷 ASCII 版本
    use_ascii = getattr(args, "ascii", False)
    if not use_ascii and terminal_width < 100:
        use_ascii = True  # 自動降級

    # Step 3: 計算卡片寬度
    if hasattr(args, "width") and args.width:
        card_width = args.width
    else:
        available_width = terminal_width - 10
        card_width = max(available_width // 4, 15)  # 最小寬度 15

    # Step 4: 計算欄距
    column_spacing = 3 if use_ascii else 2

    # Step 5: 計算最大行數
    max_rows = 0
    for status in [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_BLOCKED]:
        rows_in_status = sum(card.get("height", 3) for card in cards_by_status[status])
        max_rows = max(max_rows, rows_in_status)

    # Return layout dict
    return {
        "terminal_width": terminal_width,
        "card_width": card_width,
        "column_spacing": column_spacing,
        "max_rows": max_rows,
        "use_ascii": use_ascii,
    }


def render_board_unicode(
    cards_by_status: Dict[str, List[Dict[str, Any]]], layout: Dict[str, Any], version: str = ""
) -> str:
    """
    使用 Unicode 方框字元渲染看板

    Args:
        cards_by_status: 按狀態分組的卡片資料
        layout: 佈局參數
        version: 版本號（用於標題）

    Returns:
        str: 完整的看板字串（多行）

    使用字元：
        - 方框：┌─┐│├┤└─┘
        - 雙線：╔═╗║╚═╝
        - 分隔：─
    """
    lines = []
    card_width = layout["card_width"]
    max_rows = layout["max_rows"]

    # 計算總寬度（4 列 + 3 個間隔）
    total_width = card_width * 4 + 6

    # 渲染標題區
    title_line = "╔" + "═" * (total_width - 2) + "╗"
    lines.append(title_line)

    version_text = format_msg(TrackBoardMessages.UNICODE_BOARD_TITLE, version=version)
    # 使用 calculate_visual_width 而非 len()，以正確處理中文字元寬度
    version_text_width = calculate_visual_width(version_text)
    padding = (total_width - 2 - version_text_width) // 2
    version_line = "║" + " " * padding + version_text + " " * (total_width - 2 - padding - version_text_width) + "║"
    lines.append(version_line)

    lines.append("╚" + "═" * (total_width - 2) + "╝")
    lines.append("")

    # 渲染統計行
    pending_count = len(cards_by_status[STATUS_PENDING])
    in_progress_count = len(cards_by_status[STATUS_IN_PROGRESS])
    completed_count = len(cards_by_status[STATUS_COMPLETED])
    blocked_count = len(cards_by_status[STATUS_BLOCKED])

    stats_line = (
        f"{TrackBoardMessages.UNICODE_STATS_PENDING} {pending_count} {TrackBoardMessages.UNICODE_STATS_TASKS_SUFFIX}  "
        f"{TrackBoardMessages.UNICODE_STATS_IN_PROGRESS} {in_progress_count} {TrackBoardMessages.UNICODE_STATS_TASKS_SUFFIX}  "
        f"{TrackBoardMessages.UNICODE_STATS_COMPLETED} {completed_count} {TrackBoardMessages.UNICODE_STATS_TASKS_SUFFIX}  "
        f"{TrackBoardMessages.UNICODE_STATS_BLOCKED} {blocked_count} {TrackBoardMessages.UNICODE_STATS_TASKS_SUFFIX}"
    )
    lines.append(stats_line)
    lines.append("─" * total_width)
    lines.append("")

    # 渲染欄標題
    headers = TrackBoardMessages.UNICODE_HEADERS
    header_line = " " * 2
    for header in headers:
        header_line += ljust_with_chinese_width(header, card_width) + "  "
    lines.append(header_line)

    # 渲染分隔線
    sep_line = "┌" + "─" * (card_width - 1) + "┐  "
    sep_line += "┌" + "─" * (card_width - 1) + "┐  "
    sep_line += "┌" + "─" * (card_width - 1) + "┐  "
    sep_line += "┌" + "─" * (card_width - 1) + "┐"
    lines.append(sep_line)

    # 逐行渲染卡片
    for row_idx in range(max_rows):
        # 構建該行的 4 欄內容
        cols = []
        for status in [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_BLOCKED]:
            cards = cards_by_status[status]
            if row_idx < len(cards):
                card = cards[row_idx]
                # 卡片內容（3 行）
                col_content = [
                    ljust_with_chinese_width(card["id"], card_width),
                    ljust_with_chinese_width(card["title"], card_width),
                    ljust_with_chinese_width(card["priority"], card_width),
                ]
            else:
                col_content = ["", "", ""]
            cols.append(col_content)

        # 輸出卡片行
        for line_in_card in range(3):
            line_content = ""
            for col_idx, col in enumerate(cols):
                if line_in_card < len(col):
                    line_content += "│ " + ljust_with_chinese_width(col[line_in_card], card_width - 2) + " "
                else:
                    line_content += "│ " + " " * (card_width - 2) + " "
            line_content += "│"
            lines.append(line_content)

        # 輸出分隔線
        if row_idx < max_rows - 1:
            sep_line = "├" + "─" * (card_width - 1) + "┤  "
            sep_line += "├" + "─" * (card_width - 1) + "┤  "
            sep_line += "├" + "─" * (card_width - 1) + "┤  "
            sep_line += "├" + "─" * (card_width - 1) + "┤"
            lines.append(sep_line)

    # 渲染邊界
    lines.append("└" + "─" * (card_width - 1) + "┘  " * 3 + "└" + "─" * (card_width - 1) + "┘")
    lines.append("")

    # 渲染圖例
    lines.append(TrackBoardMessages.UNICODE_LEGEND_TITLE)
    lines.append(TrackBoardMessages.UNICODE_LEGEND_PRIORITY_HIGH)
    lines.append(TrackBoardMessages.UNICODE_LEGEND_PRIORITY_LOW)

    return "\n".join(lines)


def render_board_ascii(
    cards_by_status: Dict[str, List[Dict[str, Any]]], layout: Dict[str, Any]
) -> str:
    """
    使用純 ASCII 字元渲染看板（表格式）

    Args:
        cards_by_status: 按狀態分組的卡片資料
        layout: 佈局參數

    Returns:
        str: 表格形式的看板字串

    格式：
        ============================== BOARD ==============================
        Status    | Count | Tickets
        ----------|-------|------------------------------------------
        pending   | 4     | W7-001, W7-002, W7-003, W7-004
    """
    lines = []

    # 渲染表格標題
    title_line = SEPARATOR_WIDE
    lines.append(title_line)

    board_title = TrackBoardMessages.ASCII_BOARD_TITLE
    title_padding = (70 - len(board_title)) // 2
    title_row = " " * title_padding + board_title + " " * (70 - title_padding - len(board_title))
    lines.append(title_row)

    lines.append(title_line)
    lines.append("")

    # 渲染欄標題
    lines.append(TrackBoardMessages.ASCII_HEADER_ROW)
    lines.append(SEPARATOR_WIDE_DASH)

    # 遍歷每個狀態建立行
    for status in [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_BLOCKED]:
        count = len(cards_by_status[status])
        ids = [card["id"] for card in cards_by_status[status]]
        id_string = ", ".join(ids)

        if len(id_string) > 40:
            id_string = id_string[:40] + "..."

        status_label = status.replace("_", " ")
        row = f"{status_label:10}| {count:>5} | {id_string}"
        lines.append(row)

    # 渲染表格邊界
    lines.append(SEPARATOR_WIDE)

    return "\n".join(lines)


def execute_board(args: argparse.Namespace, version: str) -> int:
    """
    執行 board 命令主入口（預設輸出樹狀看板）

    Args:
        args: 命令列參數（包含 --version, --wave, --all 選項）
        version: 目標版本號（從 resolve_version 取得）

    Returns:
        int: 0 表示成功，1 表示失敗
    """
    try:
        # 載入 Ticket 資料
        tickets = list_tickets(version)

        # 套用 Wave 過濾
        if hasattr(args, "wave") and args.wave:
            wave = args.wave
            tickets = [t for t in tickets if f"-{wave}-" in t.get("id", "")]

        # 判斷是否顯示所有任務
        show_all = getattr(args, "all", False)

        # 渲染樹狀看板
        output = render_board_tree(tickets, version, show_all=show_all)
        print(output)

        return 0

    except Exception as e:
        print(format_error(f"{TrackBoardMessages.ERROR_RENDERING_BOARD_PREFIX} {str(e)}"))
        return 1
