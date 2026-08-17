"""Ticket ID 正規表達式單一權威（SSOT）。

背景：hooks 全域曾各自 re.compile ticket ID pattern（約 10 處定義點），
後綴（子票）處理已分歧為三種形態並存——不支援後綴、單層可選後綴、多層
後綴——比對行為不一致必然產生跨 hook 判定漂移（源自 Reuse 視角重複實作
審查發現；error-pattern ID 已有 pattern_id.py SSOT 先例可循）。

設計原則：
- 僅依賴標準函式庫（`re`），不 import ticket_system——hooks 以
  `uv run --script` + PEP 723 `dependencies = []` 執行，拉入 ticket_system
  會連帶引入 PyYAML 依賴鏈（見 version-tracking-consistency-guard-hook.py
  舊註解，本模組承接該約束）。
- 各變體行為原樣保留（不默改任何既有呼叫端的比對邏輯），僅將重複定義
  收斂為具名常數；canonical 完整驗證語意另見
  `.claude/skills/ticket/ticket_system/constants.py` 的 TICKET_ID_PATTERN
  （兩者結構同構，但跨套件邊界不互相 import，理由同上）。

變體對照表（呼叫端 -> 變體，收斂盤點結果）：

| 變體 | 原定義點 | 形態 |
|------|---------|------|
| SEARCH_NO_SUFFIX_RE | askuserquestion-reminder-hook.py | 完整形，無後綴，無群組（findall 用） |
| SEARCH_SINGLE_SUFFIX_RE | agent-dispatch-logger-hook.py | 完整形，單層可選後綴，無群組 |
| SEARCH_WITH_SUFFIX_RE | dispatch-record-hook.py／dispatch-identity-bind-hook.py | 完整形，多層後綴，單一群組（整段） |
| SEARCH_WITH_SUFFIX_AND_SLUG_RE | version-tracking-consistency-guard-hook.py（TICKET_ID_REF_PATTERN） | 完整形，多層後綴＋選填 slug，無群組 |
| SEARCH_BOUNDED_RE | command-entrance-gate-hook.py／reference-stability-rule8-guard-hook.py（VERSIONED_TICKET_PATTERN） | 完整形，無後綴，兩側 `\\b` 邊界，無群組（兩處定義原本字面即相同） |
| MATCH_GROUPED_STR | file-ownership-guard-hook.py | 完整形，三個獨立群組（版本／wave／seq含後綴），原生字串（呼叫端用 `re.match`） |
| FULL_ANCHORED_RE | version-tracking-consistency-guard-hook.py（CLOSED_BY_TICKET_ID_PATTERN） | 完整形，`^...$` 全字串錨定，三群組＋選填 slug 群組，與 ticket_system/constants.py 同構 |
| BARE_START_BOUNDED_RE | phase4-decision-enforcement-hook.py | 裸形（無版本號），起始 `\\b` 邊界 |
| BARE_BOTH_BOUNDED_RE | reference-stability-rule8-guard-hook.py（BARE_TICKET_PATTERN） | 裸形，兩側 `\\b` 邊界 |

此外新增 `extract_ticket_id_anchored()`：處理「prompt 首行同時含多個票號」
殘留缺口（位置優先的 `.search()` 未必命中目標票，改為優先信任
『Ticket:』/『[Ticket]』/『#Ticket-』等標籤錨定），於本次 SSOT 收斂一併
處理。
"""

import re
from typing import Optional

# ============================================================================
# 核心片段（供各變體組裝，避免手打分歧）
# ============================================================================

_VERSION = r"\d+\.\d+\.\d+"
_WAVE_NUM = r"\d+"
_SEQ_BASE = r"\d+"
_SUFFIX_MULTI = r"(?:\.\d+)*"
_SUFFIX_SINGLE = r"(?:\.\d+)?"
_SLUG_NONCAP = r"(?:-[a-z0-9][a-z0-9-]{0,59})?"
_SLUG_CAPTURED = r"(-[a-z0-9][a-z0-9-]{0,59})?"

# 完整形核心：版本號-W波次-序號（不含後綴、不含群組）
# rule8-exempt: illustration:核心片段組裝說明，非具體票號引用
_FULL_CORE = rf"{_VERSION}-W{_WAVE_NUM}-{_SEQ_BASE}"

# ============================================================================
# 完整形變體（含版本號）
# ============================================================================

# 無後綴、無群組 —— askuserquestion-reminder-hook.py（.findall() 用途）
SEARCH_NO_SUFFIX_RE = re.compile(_FULL_CORE)

# 單層可選後綴、無群組 —— agent-dispatch-logger-hook.py
SEARCH_SINGLE_SUFFIX_RE = re.compile(_FULL_CORE + _SUFFIX_SINGLE)

# 多層後綴、單一群組（整段皆為 group 1）—— dispatch-record-hook.py／
# dispatch-identity-bind-hook.py
SEARCH_WITH_SUFFIX_RE = re.compile(rf"({_FULL_CORE}{_SUFFIX_MULTI})")

# 多層後綴＋選填 slug、無群組 —— version-tracking-consistency-guard-hook.py
# 的 TICKET_ID_REF_PATTERN
SEARCH_WITH_SUFFIX_AND_SLUG_RE = re.compile(_FULL_CORE + _SUFFIX_MULTI + _SLUG_NONCAP)

# 無後綴、兩側 \b 邊界、無群組 —— command-entrance-gate-hook.py 與
# reference-stability-rule8-guard-hook.py 的 VERSIONED_TICKET_PATTERN
# （兩處原定義字面完全相同，收斂為同一常數）
SEARCH_BOUNDED_RE = re.compile(rf"\b{_FULL_CORE}\b")

# 三個獨立群組（版本／wave 號／seq含多層後綴）、無邊界、無 slug —— 保留原生
# 字串型態，因原呼叫端以 re.match(TICKET_ID_PATTERN, ...) 使用未預編譯物件
MATCH_GROUPED_STR = rf"({_VERSION})-W({_WAVE_NUM})-({_SEQ_BASE}{_SUFFIX_MULTI})"

# 全字串錨定驗證（^...$）、三群組＋選填 slug 群組 —— version-tracking 的
# CLOSED_BY_TICKET_ID_PATTERN，與 ticket_system/constants.py 的
# TICKET_ID_PATTERN 同構（各自獨立維護，不互相 import，見模組頂部說明）
FULL_ANCHORED_RE = re.compile(
    rf"^({_VERSION})-W({_WAVE_NUM})-({_SEQ_BASE}{_SUFFIX_MULTI}){_SLUG_CAPTURED}$"
)

# ============================================================================
# 裸形變體（無版本號）
# ============================================================================

# 起始 \b 邊界 —— phase4-decision-enforcement-hook.py
BARE_START_BOUNDED_RE = re.compile(rf"\bW{_WAVE_NUM}-{_SEQ_BASE}")

# 兩側 \b 邊界 —— reference-stability-rule8-guard-hook.py 的 BARE_TICKET_PATTERN
BARE_BOTH_BOUNDED_RE = re.compile(rf"\bW{_WAVE_NUM}-{_SEQ_BASE}\b")

# ============================================================================
# 標籤錨定提取（多票號同行殘留缺口處理）
# ============================================================================

# 『Ticket』標籤後接（至多一個 `:`/`]`/`-` 標點 + 空白）再接完整形 ID，
# 涵蓋既有三種標籤慣例：「Ticket: X」「[Ticket] X」「#Ticket-X」
_TICKET_LABEL_ANCHOR_RE = re.compile(
    rf"Ticket[:\]\-]?\s*({_FULL_CORE}{_SUFFIX_MULTI})"
)


def extract_ticket_id_anchored(line: str) -> Optional[str]:
    """從單行文字提取 Ticket ID，優先命中『Ticket』標籤錨定的 ID；
    無標籤命中時退回行內第一個 ID 形狀字串（原始純位置定位邏輯）。

    背景：prompt 首行同時提及多個票號時（背景／參考票在前、目標票在後
    且有標籤），純位置優先（search 取第一命中）未必是目標票；『Ticket:』／
    『[Ticket]』／『#Ticket-』等標籤慣例通常明確指向目標票，故優先信任
    標籤命中。

    Args:
        line: 待搜尋的單行文字（呼叫端負責先取出目標行，如 prompt 首行）。

    Returns:
        Optional[str]: 命中的 Ticket ID（含子票後綴）；無命中回傳 None。
    """
    anchored = _TICKET_LABEL_ANCHOR_RE.search(line)
    if anchored:
        return anchored.group(1)
    fallback = SEARCH_WITH_SUFFIX_RE.search(line)
    return fallback.group(1) if fallback else None
