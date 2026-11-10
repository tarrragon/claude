"""
訊息渲染與 prompt 摘錄（自 wrap-decision-tripwire-hook.py 拆出，行為不變）。
"""

import re
from typing import Optional

from .config import SignalDef
from .signals import DetectResult


# ============================================================================
# Message rendering
# ============================================================================

def render_message(sd: SignalDef, result: DetectResult,
                   current_ticket: Optional[str]) -> str:
    # 使用 format_map + 白名單 keys 避免 f-string 注入風險
    safe = {
        "count": result.count if result.count is not None else "",
        "ticket_id": result.ticket_id or current_ticket or "",
        "matched_keyword": result.matched_keyword or "",
        "signal_id": sd.id,
    }
    # 使用 defaultdict-style 處理缺 key
    class _Safe(dict):
        def __missing__(self, key):
            return "{" + key + "}"
    try:
        text = sd.message_template.format_map(_Safe(**safe))
    except Exception:
        return sd.message_template
    if not safe["ticket_id"]:
        # 推不出票號：不顯示空的 Ticket 欄位
        text = re.sub(r"[（(]Ticket:\s*[）)]", "", text)
    return text


# ============================================================================
# Log 觀測欄位輔助
# ============================================================================

# excerpt 半徑：以 matched keyword 在 prompt 中的位置為中心，向前後各取 N 字。
# 50 為 ticket Problem Analysis 指定值，避免單行 log 過長。
_EXCERPT_RADIUS = 50


def _build_prompt_excerpt(prompt: str, matched_keyword: Optional[str]) -> str:
    """從 prompt 抽取以 matched_keyword 為中心的前後 50 字 excerpt。

    無 prompt 或無關鍵字時返回 "-"（log 欄位佔位）。
    換行字元統一替換為空格，並 strip 兩端 whitespace。
    keyword 比對採大小寫不敏感（與 RestrictiveKeywordsStrategy 一致）。
    若 keyword 不在 prompt 中（例如非 S2 訊號），返回 "-"。
    """
    if not prompt or not matched_keyword:
        return "-"
    haystack = prompt.lower()
    needle = matched_keyword.lower()
    idx = haystack.find(needle)
    if idx < 0:
        return "-"
    start = max(0, idx - _EXCERPT_RADIUS)
    end = min(len(prompt), idx + len(matched_keyword) + _EXCERPT_RADIUS)
    excerpt = prompt[start:end]
    # 換行轉空格，避免 plain text log 多行錯位
    excerpt = excerpt.replace("\n", " ").replace("\r", " ").strip()
    return excerpt
