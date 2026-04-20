"""
Ticket 有效期 Stale 警告機制（PROP-010 方案 4）

成本極低的提示性防護：依 Ticket frontmatter `created` 欄位與當前日期計算
建立年齡，於 claim/query/list 命令輸出對應級別提示，促使 PM 重新評估
長期未執行的 Ticket 是否仍具效力。

閾值：
- 7 天（INFO）：首次提示
- 14 天（WARNING）：Ticket 上下文可能過時
- 30 天（CRITICAL）：建議標記為 stale 或重新規劃

輸出限制：所有訊息控制在 3 行內，避免警告疲勞。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional

# 閾值（天）
STALE_INFO_DAYS = 7
STALE_WARNING_DAYS = 14
STALE_CRITICAL_DAYS = 30

# 等級常數
LEVEL_INFO = "info"
LEVEL_WARNING = "warning"
LEVEL_CRITICAL = "critical"


def _parse_created(created: Any) -> Optional[date]:
    """將 frontmatter 的 created 欄位解析為 date，解析失敗回 None。"""
    if not created:
        return None
    if isinstance(created, date) and not isinstance(created, datetime):
        return created
    if isinstance(created, datetime):
        return created.date()
    if isinstance(created, str):
        try:
            return date.fromisoformat(created.strip())
        except (ValueError, TypeError):
            return None
    return None


def calculate_stale_level(
    created: Any, today: Optional[date] = None
) -> Optional[str]:
    """
    依據建立日期計算 stale 等級。

    Args:
        created: Ticket frontmatter `created` 欄位（ISO 日期字串或 date 物件）
        today: 當前日期（預設使用系統時間；測試可注入）

    Returns:
        "info" / "warning" / "critical" / None（未達 7 天或解析失敗）
    """
    created_date = _parse_created(created)
    if created_date is None:
        return None

    reference = today or date.today()
    age_days = (reference - created_date).days

    if age_days >= STALE_CRITICAL_DAYS:
        return LEVEL_CRITICAL
    if age_days >= STALE_WARNING_DAYS:
        return LEVEL_WARNING
    if age_days >= STALE_INFO_DAYS:
        return LEVEL_INFO
    return None


def _ticket_age_days(ticket: dict, today: date) -> Optional[int]:
    created_date = _parse_created(ticket.get("created"))
    if created_date is None:
        return None
    return (today - created_date).days


def format_stale_warning(
    ticket: dict, today: Optional[date] = None
) -> Optional[str]:
    """
    為單一 Ticket 產出 stale 警告訊息。

    Returns:
        警告字串（最多 3 行）或 None（未觸發任一閾值）。
    """
    reference = today or date.today()
    age = _ticket_age_days(ticket, reference)
    if age is None:
        return None

    level = calculate_stale_level(ticket.get("created"), today=reference)
    if level is None:
        return None

    ticket_id = ticket.get("id") or ticket.get("ticket_id", "<unknown>")

    if level == LEVEL_CRITICAL:
        return (
            f"[WARNING] Ticket {ticket_id} 建立已 {age} 天（>= {STALE_CRITICAL_DAYS} 天）\n"
            f"   強烈建議：重新審視規格是否仍適用，或標記為 stale 重新規劃"
        )
    if level == LEVEL_WARNING:
        return (
            f"[WARNING] Ticket {ticket_id} 建立已 {age} 天（>= {STALE_WARNING_DAYS} 天）\n"
            f"   建議：確認 Ticket 上下文是否仍有效"
        )
    # INFO
    return (
        f"[INFO] Ticket {ticket_id} 建立已 {age} 天（>= {STALE_INFO_DAYS} 天）"
    )


def format_stale_list_summary(
    tickets: Iterable[dict], today: Optional[date] = None
) -> Optional[str]:
    """
    為 list 命令產出 stale 數量摘要。

    Returns:
        摘要字串（最多 3 行）或 None（無任何 stale Ticket）。
    """
    reference = today or date.today()
    info_count = 0
    warning_count = 0
    critical_count = 0

    for ticket in tickets:
        level = calculate_stale_level(ticket.get("created"), today=reference)
        if level == LEVEL_INFO:
            info_count += 1
        elif level == LEVEL_WARNING:
            warning_count += 1
        elif level == LEVEL_CRITICAL:
            critical_count += 1

    total = info_count + warning_count + critical_count
    if total == 0:
        return None

    parts = []
    if critical_count:
        parts.append(f"critical={critical_count}")
    if warning_count:
        parts.append(f"warning={warning_count}")
    if info_count:
        parts.append(f"info={info_count}")
    detail = " ".join(parts)

    return (
        f"[Stale] 共 {total} 個 stale Ticket（{detail}）\n"
        f"   提示：閾值 {STALE_INFO_DAYS}/{STALE_WARNING_DAYS}/{STALE_CRITICAL_DAYS} 天"
    )
