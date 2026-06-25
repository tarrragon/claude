"""
Ticket 重複偵測模組

從 commands/create.py 提取的 duplicate detection 群組。
負責 Jaccard 相似度計算、Tier 1 警告層、Tier 2 阻擋層、
以及 in_progress group 偵測。
"""
if __name__ == "__main__":
    from .messages import print_not_executable_and_exit
    print_not_executable_and_exit()


import os
import re
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ticket_system.lib.ticket_loader import (
    get_ticket_path,
    list_tickets,
)
from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    DUPLICATE_DETECTION_THRESHOLD,
    DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS,
    DUPLICATE_BLOCK_THRESHOLD,
    DUPLICATE_BLOCK_WINDOW_MINUTES,
)
from ticket_system.lib.command_lifecycle_messages import (
    CreateMessages,
    format_msg,
)
from ticket_system.lib.messages import format_warning


def _tokenize(text: str) -> set:
    r"""
    將文字分割為詞集合。

    - 中文字元（一-鿿）逐字提取
    - 英文單詞（\w+）按單詞分割
    - 特殊字元和標點忽略

    Args:
        text: 待分割文字

    Returns:
        集合，包含所有詞彙
    """
    pattern = r'[一-鿿]|\w+'
    tokens = re.findall(pattern, text)
    return set(tokens)


def _calculate_jaccard_similarity(text_a: str, text_b: str) -> float:
    """
    計算兩個字串的 Jaccard 相似度係數。

    使用集合論方式計算相似度：
    Jaccard = |intersection| / |union|

    對中文字元逐字分割，英文單詞以空白和標點分割。

    Args:
        text_a: 第一個比對文字
        text_b: 第二個比對文字

    Returns:
        float: 相似度值 [0.0, 1.0]，1.0 表示完全相同，0.0 表示完全不同

    Raises:
        TypeError: 如果輸入不是字串型別
    """
    # 輸入驗證
    if not isinstance(text_a, str) or not isinstance(text_b, str):
        raise TypeError("text_a 和 text_b 必須是字串型別")

    # 統一轉為小寫，不區分大小寫
    text_a = text_a.lower()
    text_b = text_b.lower()

    # 分割兩個文字
    set_a = _tokenize(text_a)
    set_b = _tokenize(text_b)

    # 邊界情況：兩個集合都為空
    if not set_a and not set_b:
        return 0.0

    # 計算 Jaccard 係數
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    if union == 0:
        return 0.0

    return intersection / union


def _is_in_detection_scope(ticket: Dict[str, Any], window_start: datetime) -> bool:
    """判斷 Ticket 是否在重複偵測掃描範圍內。

    掃描範圍：
    - pending: 始終包含
    - in_progress: 始終包含
    - completed: 僅 7 天內完成者（completed_at >= window_start）
    - 其他狀態: 排除

    Args:
        ticket: Ticket 字典
        window_start: 時間窗口起點（now - N 天）

    Returns:
        True 表示在掃描範圍內
    """
    status = ticket.get("status")

    if status == STATUS_PENDING:
        return True

    if status == STATUS_IN_PROGRESS:
        return True

    if status == STATUS_COMPLETED:
        completed_at_str = ticket.get("completed_at")
        if not completed_at_str:
            return False
        try:
            completed_at = datetime.fromisoformat(completed_at_str)
            return completed_at >= window_start
        except (ValueError, TypeError):
            return False

    return False


def _get_status_label(status: str) -> str:
    """根據 Ticket 狀態返回顯示標籤。

    pending 不加標籤（向下相容），in_progress 和 completed 加中文標籤。

    Args:
        status: Ticket 狀態字串

    Returns:
        狀態標籤字串，pending 返回空字串
    """
    if status == STATUS_IN_PROGRESS:
        return CreateMessages.DUPLICATE_STATUS_LABEL_IN_PROGRESS
    if status == STATUS_COMPLETED:
        return CreateMessages.DUPLICATE_STATUS_LABEL_COMPLETED
    return ""


def detect_duplicate_tickets(
    version: str,
    new_title: str,
    new_what: str,
    new_ticket_id: str,
) -> None:
    """
    偵測並警告同版本中可能重複的 Ticket。

    掃描同版本的 pending/in_progress/completed（7 天內）Ticket，
    使用 Jaccard 相似度與即將建立的 Ticket 比對標題和目標。
    若發現相似度達閾值的 Ticket，輸出 WARNING 提示使用者。

    此函式設計為容錯式：內部所有異常都被靜默捕捉，不影響後續建立流程。

    Args:
        version: 目標版本號（如 "0.1.2"）
        new_title: 即將建立的 Ticket 標題
        new_what: 即將建立的 Ticket 目標描述
        new_ticket_id: 即將建立的 Ticket ID（用於排除自身）

    Returns:
        None（不返回偵測結果，以簽名方式消費 WARNING）
    """

    try:
        # 步驟 A：驗證輸入
        # 若 title 和 what 均為空，無法進行比對
        if not new_title and not new_what:
            return

        # 步驟 B：載入同版本 Ticket 並過濾候選範圍
        all_tickets = list_tickets(version)

        # 計算需排除的 ID 清單
        exclude_ids = {new_ticket_id}
        # 若是子任務，額外排除父任務 ID
        # 只檢查序號段（最後一個 - 之後）是否含 "."
        seq_part = new_ticket_id.rsplit("-", 1)[-1]
        if "." in seq_part:
            parent_id = new_ticket_id.rsplit(".", 1)[0]
            exclude_ids.add(parent_id)

        # 計算時間窗口（迴圈外一次計算）
        window_start = datetime.now() - timedelta(
            days=DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS
        )

        # 過濾候選 Ticket：pending + in_progress + 7 天內 completed
        candidate_tickets = [
            ticket
            for ticket in all_tickets
            if ticket.get("id") not in exclude_ids
            and _is_in_detection_scope(ticket, window_start)
        ]

        # 若無候選 Ticket，靜默通過
        if not candidate_tickets:
            return

        # 步驟 C：相似度計算
        new_combined = f"{new_title} {new_what}"
        similar_tickets = []

        for ticket in candidate_tickets:
            try:
                # 合併候選 Ticket 的 title 和 what 進行比對
                candidate_title = ticket.get("title", "")
                candidate_what = ticket.get("what", "")
                candidate_combined = f"{candidate_title} {candidate_what}"

                # 計算相似度
                similarity = _calculate_jaccard_similarity(
                    new_combined, candidate_combined
                )

                # 若達閾值，加入相似列表（含狀態供標籤使用）
                if similarity >= DUPLICATE_DETECTION_THRESHOLD:
                    similar_tickets.append(
                        (ticket.get("id", ""), candidate_title, ticket.get("status", ""))
                    )
            except Exception as e:
                # 單項異常不影響整體，跳過此 Ticket，繼續下一個
                sys.stderr.write(f"[DEBUG] 相似度計算異常 ({type(e).__name__}): {e}\n")
                continue

        # 步驟 D：輸出結果（含狀態標籤）
        if similar_tickets:
            # 組裝警告訊息
            warning_lines = [
                format_warning(
                    CreateMessages.DUPLICATE_TICKETS_WARNING_HEADER,
                    count=len(similar_tickets),
                )
            ]

            for ticket_id, title, status in similar_tickets:
                status_label = _get_status_label(status)
                if status_label:
                    warning_lines.append(
                        format_msg(
                            CreateMessages.DUPLICATE_TICKETS_WARNING_ITEM_WITH_STATUS,
                            ticket_id=ticket_id,
                            title=title,
                            status_label=status_label,
                        )
                    )
                else:
                    warning_lines.append(
                        format_msg(
                            CreateMessages.DUPLICATE_TICKETS_WARNING_ITEM,
                            ticket_id=ticket_id,
                            title=title,
                        )
                    )

            warning_lines.append(
                format_msg(CreateMessages.DUPLICATE_TICKETS_WARNING_SUGGESTION)
            )

            # 輸出警告
            print("\n".join(warning_lines))

    except Exception as e:
        # 外層容錯：任何異常都靜默通過
        # 重複偵測是輔助功能，不應阻斷核心建立流程
        # 異常類型輸出到 stderr，供除錯用
        sys.stderr.write(f"[DEBUG] 重複偵測異常 ({type(e).__name__}): {e}\n")


def _get_ticket_creation_time(version: str, ticket_id: str) -> Optional[datetime]:
    """取得候選 Ticket 的建立時間（用於 Tier 2 短窗口判定）。

    frontmatter 的 `created` 僅日期粒度，無法支撐 60 分鐘級窗口判定，
    故改用 ticket md 檔案的 birth time（無則 fallback mtime）作為實際
    建立時間估計——ghost 雙執行流同 turn 數分鐘內 spawn 的場景下，
    檔案時間戳是最貼近真實建立時刻的可得訊號（Phase 1 決策，見 ticket）。

    Args:
        version: 版本號
        ticket_id: 候選 Ticket ID

    Returns:
        建立時間 datetime；無法取得時返回 None（視為不在窗口內）
    """
    try:
        path = get_ticket_path(version, ticket_id)
        stat = os.stat(path)
        # macOS 提供 st_birthtime；其他平台 fallback st_mtime
        ts = getattr(stat, "st_birthtime", None) or stat.st_mtime
        return datetime.fromtimestamp(ts)
    except (OSError, ValueError, TypeError):
        return None


def _find_blocking_duplicate(
    version: str,
    new_title: str,
    new_what: str,
    new_ticket_id: str,
) -> Optional[tuple]:
    """Tier 2 阻擋層偵測：尋找同窗口高相似度的 pending/in_progress 候選票。

    阻擋條件（三者交集）：
    1. 候選為同版本 pending 或 in_progress（不含 completed——重建已完成票
       屬合法重做，交 Tier 1 警告即可）
    2. 相似度 >= DUPLICATE_BLOCK_THRESHOLD（高相似）
    3. 候選建立時間在 DUPLICATE_BLOCK_WINDOW_MINUTES 內（短窗口）

    Args:
        version: 目標版本號
        new_title: 即將建立的標題
        new_what: 即將建立的目標描述
        new_ticket_id: 即將建立的 Ticket ID（用於排除自身與 parent）

    Returns:
        命中時返回 (ticket_id, title, status, similarity)；無命中返回 None。
        內部異常一律返回 None（不阻斷建立，與 Tier 1 容錯設計一致）。
    """
    try:
        if not new_title and not new_what:
            return None

        all_tickets = list_tickets(version)

        exclude_ids = {new_ticket_id}
        seq_part = new_ticket_id.rsplit("-", 1)[-1]
        if "." in seq_part:
            parent_id = new_ticket_id.rsplit(".", 1)[0]
            exclude_ids.add(parent_id)

        window_start = datetime.now() - timedelta(
            minutes=DUPLICATE_BLOCK_WINDOW_MINUTES
        )
        new_combined = f"{new_title} {new_what}"

        for ticket in all_tickets:
            ticket_id = ticket.get("id", "")
            if ticket_id in exclude_ids:
                continue
            # 條件 1：僅 pending / in_progress
            if ticket.get("status") not in (STATUS_PENDING, STATUS_IN_PROGRESS):
                continue
            # 條件 2：高相似度
            candidate_combined = (
                f"{ticket.get('title', '')} {ticket.get('what', '')}"
            )
            try:
                similarity = _calculate_jaccard_similarity(
                    new_combined, candidate_combined
                )
            except Exception:
                continue
            if similarity < DUPLICATE_BLOCK_THRESHOLD:
                continue
            # 條件 3：短窗口內建立
            created_time = _get_ticket_creation_time(version, ticket_id)
            if created_time is None or created_time < window_start:
                continue
            return (ticket_id, ticket.get("title", ""), ticket.get("status", ""), similarity)

        return None

    except Exception as e:
        sys.stderr.write(f"[DEBUG] 阻擋層偵測異常 ({type(e).__name__}): {e}\n")
        return None


def enforce_blocking_duplicate(
    version: str,
    new_title: str,
    new_what: str,
    new_ticket_id: str,
    allow_duplicate: bool,
) -> bool:
    """Tier 2 阻擋層強制：命中時輸出阻擋訊息，回傳是否放行。

    Args:
        version: 版本號
        new_title: 即將建立的標題
        new_what: 即將建立的目標描述
        new_ticket_id: 即將建立的 Ticket ID
        allow_duplicate: 是否啟用 --allow-duplicate 旁路

    Returns:
        True 表示放行（無命中或已旁路）；False 表示阻擋（呼叫端應 exit 1）
    """
    hit = _find_blocking_duplicate(version, new_title, new_what, new_ticket_id)
    if hit is None:
        return True

    ticket_id, title, status, similarity = hit

    if allow_duplicate:
        print(format_msg(CreateMessages.DUPLICATE_BLOCK_BYPASSED))
        return True

    lines = [
        format_msg(CreateMessages.DUPLICATE_BLOCK_HEADER),
        format_msg(
            CreateMessages.DUPLICATE_BLOCK_ITEM,
            ticket_id=ticket_id,
            title=title,
            status_label=_get_status_label(status) or status,
            similarity=similarity,
        ),
        format_msg(CreateMessages.DUPLICATE_BLOCK_SUGGESTION),
    ]
    print("\n".join(lines))
    return False


def detect_in_progress_groups(
    version: str, wave: Optional[int]
) -> List[Dict[str, Any]]:
    """偵測當前 wave 內 status=in_progress 且 children 非空的 group ticket。

    用於 ticket create 不帶 --parent 時的提示，協助 PM 判斷是否該掛在
    既有 group 之下（W17-008.15 方案 D 第 3 項）。

    Args:
        version: 版本號
        wave: 當前 wave；None 時不過濾

    Returns:
        List[Dict]: 候選 group ticket 清單（可能為空）
    """
    try:
        all_tickets = list_tickets(version) or []
    except Exception:
        return []

    groups: List[Dict[str, Any]] = []
    for ticket in all_tickets:
        if ticket.get("status") != STATUS_IN_PROGRESS:
            continue
        children = ticket.get("children") or []
        if not children:
            continue
        if wave is not None and ticket.get("wave") != wave:
            continue
        groups.append(ticket)
    return groups
