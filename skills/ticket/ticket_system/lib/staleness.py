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

# W17-031.4: stale in_progress 閾值（小時）
# 用於 runqueue 識別 agent 中斷 / timeout 後遺留的 in_progress ticket。
# W17-033 已落地 agent 自律 complete 規則 + acceptance-gate-hook 安全網，
# 此閾值僅捕捉 W17-033 機制無法覆蓋的案例（agent 已不在，無法觸發 complete）。
STALE_IN_PROGRESS_HOURS = 24

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


def _parse_started_at(started_at: Any) -> Optional[datetime]:
    """解析 frontmatter 的 started_at（ISO datetime 字串或 datetime 物件），失敗回 None。"""
    if not started_at:
        return None
    if isinstance(started_at, datetime):
        return started_at
    if isinstance(started_at, str):
        try:
            # 接受 ISO 格式（含/不含 timezone）；ticket md 通常為 naive 'YYYY-MM-DDTHH:MM:SS'
            return datetime.fromisoformat(started_at.strip())
        except (ValueError, TypeError):
            return None
    return None


def compute_stale_minutes(
    ticket: dict, now: Optional[datetime] = None
) -> Optional[int]:
    """
    計算 in_progress ticket 自 started_at 起經過的分鐘數（W10-114 dashboard）。

    純函式：不執行 stale 判定，僅回傳分鐘數（caller 自行套門檻）。
    解析失敗（缺 started_at / 格式錯誤）→ 回傳 None。

    Args:
        ticket: ticket frontmatter dict
        now: 當前時間（測試可注入）；預設 datetime.now()

    Returns:
        int 分鐘數（>= 0），或 None
    """
    started = _parse_started_at(ticket.get("started_at"))
    if started is None:
        return None
    reference = now or datetime.now()
    # 兼容 timezone-aware / naive：兩者只要其中一邊 aware 就轉同 naive
    if started.tzinfo is not None and reference.tzinfo is None:
        started = started.replace(tzinfo=None)
    elif started.tzinfo is None and reference.tzinfo is not None:
        reference = reference.replace(tzinfo=None)
    elapsed = (reference - started).total_seconds() / 60
    if elapsed < 0:
        return 0
    return int(elapsed)


def is_stale_in_progress(
    ticket: dict, now: Optional[datetime] = None
) -> bool:
    """
    判斷 ticket 是否為 stale in_progress（W17-031.4）。

    條件：
    - status == "in_progress"
    - completed_at 為 None / 缺欄位
    - compute_stale_minutes >= STALE_IN_PROGRESS_HOURS * 60

    解析失敗（缺 started_at / 格式錯誤）→ False（fail-open，不誤標）。

    W10-120 重構：原獨立邏輯改為呼叫 compute_stale_minutes，消除時區處理
    與 started_at 解析的雙函式重複（DRY）。語意不變。

    Args:
        ticket: ticket frontmatter dict
        now: 當前時間（測試可注入）；預設使用 datetime.now()

    Returns:
        True 若符合 stale in_progress；否則 False
    """
    if ticket.get("status") != "in_progress":
        return False
    if ticket.get("completed_at"):
        return False
    minutes = compute_stale_minutes(ticket, now)
    if minutes is None:
        return False
    return minutes >= STALE_IN_PROGRESS_HOURS * 60


def _is_trigger_bound(ticket: dict) -> bool:
    """判斷 ticket 是否為 trigger_bound（trigger 綁定延後）。

    trigger_bound ticket 的觸發條件為上游 release 或累積證據，created 日期
    永不變動，依日期判定 stale 屬誤報。僅 frontmatter `trigger_bound` 嚴格為
    True 才排除（顯式 False / 缺欄位皆視為一般票，不誤傷）。
    """
    return ticket.get("trigger_bound") is True


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
        警告字串（最多 3 行）或 None（未觸發任一閾值，或 trigger_bound 排除）。
    """
    # trigger_bound ticket：trigger 為外部/累積條件，依日期判 stale 屬誤報，跳過
    if _is_trigger_bound(ticket):
        return None

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
        # trigger_bound ticket 不計入 stale 統計（同 format_stale_warning 排除）
        if _is_trigger_bound(ticket):
            continue
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
