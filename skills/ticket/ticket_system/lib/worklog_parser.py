"""
Worklog 交接段落解析模組（W17-083 雙軌同步偵測共用模組）

提供 worklog 中 handoff 意圖偵測 + ticket ID 提取 + worklog 路徑解析等功能，
供 S2 (CLI handoff --from-worklog) 和 S3 (Stop hook) 共用，避免 DRY 違反。

API 契約（依 W17-083 Phase 3a / Phase 2 sage 規格）：
- HANDOFF_KEYWORDS: tuple[str, ...]
- detect_handoff_keywords(content) -> bool
- extract_ticket_ids(content, active_version=None) -> list[str]
- extract_recent_content(worklog_path, since_mtime) -> str
- extract_handoff_section(content) -> str
- find_worklog_path(version) -> Path

備註：S3 Stop hook 因 PEP 723 隔離環境無法 import 本模組，需照搬 SOT
（HANDOFF_KEYWORDS / regex pattern）。本模組為 SOT，hook 端複本須與本模組同步維護
（ARCH-020 同構雙寫案例）。
"""

from __future__ import annotations

import re
from pathlib import Path

from .worklog_appender import _build_worklog_path

# ---------------------------------------------------------------------------
# 模組級常數（SOT — Single Source of Truth）
# ---------------------------------------------------------------------------

#: Handoff 意圖關鍵字清單（W17-083 Phase 1 §2 設計；0.2.1-W3-218 補「下一站」）
#:
#: 任一關鍵字命中 worklog content 即視為「交接意圖」。涵蓋：
#: - 標題式（章節標題）：「下個 Session 接手 Context」等
#: - 建議式（句中）：「下 session 優先建議」等
#: - 續行式（ANA complete 強制欄位）：「未完成清單」等
#: - 本專案書寫慣例（0.2.1-W3-218）：「下一站」——0.2.1-W3-178 實測 HANDOFF_KEYWORDS
#:   對本專案 8 份 main worklog 命中總數為 0，本專案實際慣用「下一站」（5 次皆為
#:   交接語境）。0.2.1-W3-218 同時實測「結構判定」（粗體標題行 + 同行含 ticket ID）
#:   對同語料的誤報率達 76%（17 命中僅 4 為真交接段），故採清單擴充而非結構判定。
HANDOFF_KEYWORDS: tuple[str, ...] = (
    # 標題式
    "下個 Session 接手 Context",
    "下一 Session 接手",
    "下 Session 接手",
    "接手指引",
    "Handoff Context",
    "Session Handoff",
    "下一站",
    # 建議式
    "下 session 優先建議",
    "下個 session 優先建議",
    "下一 session 優先建議",
    "下 session 優先順序建議",
    "下次 session 建議",
    "建議下 session",
    # 續行式
    "未完成清單",
    "Spawned 推進清單",
)

#: 完整 ticket ID regex：<version>-W<wave>-<seq>[.<sub>]
#: 例：0.18.0-W17-079、0.18.0-W17-083.1
TICKET_ID_FULL_PATTERN: re.Pattern = re.compile(
    r"\b(\d+\.\d+\.\d+)-(W\d+-[\d\w]+(?:\.\d+)?)\b"
)

#: 短 ticket ID regex：W<wave>-<seq>[.<sub>]（不含版本前綴）
#: 例：W17-079、W17-083.1
TICKET_ID_SHORT_PATTERN: re.Pattern = re.compile(
    r"\b(W\d+-[\d\w]+(?:\.\d+)?)\b"
)


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def detect_handoff_keywords(content: str) -> bool:
    """
    偵測 worklog 內容是否含 handoff 意圖關鍵字。

    Args:
        content: worklog 全文或片段內容

    Returns:
        bool: 任一 HANDOFF_KEYWORDS 出現即回 True；否則 False

    Examples:
        >>> detect_handoff_keywords("下個 Session 接手 Context")
        True
        >>> detect_handoff_keywords("一般工作日誌記錄")
        False
    """
    if not content:
        return False
    return any(kw in content for kw in HANDOFF_KEYWORDS)


def extract_ticket_ids(
    content: str, active_version: str | None = None
) -> list[str]:
    """
    從內容提取 ticket ID 清單（去重、保序）。

    處理規則：
    1. 先掃 TICKET_ID_FULL_PATTERN（完整 ID），結果加入清單並標記已見
    2. 若 active_version 提供，再掃 TICKET_ID_SHORT_PATTERN，用 active_version 補全為完整 ID
       （已見的 ID 不重複加入）
    3. 不過濾 code block（W17-083 方案 D 接受此誤報邊界）

    Args:
        content: 內容字串
        active_version: 可選的 active 版本號（如 "0.18.0"），用於短 ID 補全

    Returns:
        list[str]: 完整 ticket ID 清單，順序為首次出現順序，已去重

    Examples:
        >>> extract_ticket_ids("待處理：0.18.0-W17-079 與 W17-080", active_version="0.18.0")
        ['0.18.0-W17-079', '0.18.0-W17-080']
        >>> extract_ticket_ids("純文字無 ID")
        []
    """
    if not content:
        return []

    seen: list[str] = []
    seen_set: set[str] = set()

    # Step 1: 完整 ID 先掃（避免短 pattern 重複命中已被完整 pattern 涵蓋的 ID）
    for match in TICKET_ID_FULL_PATTERN.finditer(content):
        version_part = match.group(1)
        wave_part = match.group(2)
        full_id = f"{version_part}-{wave_part}"
        if full_id not in seen_set:
            seen.append(full_id)
            seen_set.add(full_id)

    # Step 2: 短 ID 補全（僅當提供 active_version）
    if active_version:
        # 為避免短 pattern 命中完整 ID 中的 W 部分（如 0.18.0-W17-079 內的 W17-079），
        # 先用 finditer 並檢查 match 起點是否緊接在「<version>-」之後
        for match in TICKET_ID_SHORT_PATTERN.finditer(content):
            short_id = match.group(1)

            # 檢查此 match 是否實為某完整 ID 的 wave 部分
            start = match.start()
            # 往前看是否為 "<version>-" 格式
            if start > 0 and _preceded_by_version_prefix(content, start):
                continue

            full_id = f"{active_version}-{short_id}"
            if full_id not in seen_set:
                seen.append(full_id)
                seen_set.add(full_id)

    return seen


def _preceded_by_version_prefix(content: str, start: int) -> bool:
    """
    判斷 content[start] 之前的字元序列是否為 "<version>-" 格式。

    用於 extract_ticket_ids() 內部判斷短 pattern 命中是否實為完整 ID 的一部分。

    Args:
        content: 完整內容
        start: 短 pattern match 的起點 index

    Returns:
        bool: 若 start 之前緊接 "X.Y.Z-" 格式回 True；否則 False
    """
    # 從 start - 1 往前掃描，檢查是否符合 ".Y.Z-" 格式（dash 已在 start - 1）
    if start == 0:
        return False
    # 至少需要 "0.0.0-" = 6 字元
    prefix_start = max(0, start - 12)
    prefix = content[prefix_start:start]
    # 比對版本格式 + dash 結尾
    return bool(re.search(r"\d+\.\d+\.\d+-$", prefix))


def extract_recent_content(worklog_path: Path, since_mtime: float) -> str:
    """
    擷取 worklog 最新內容（依 mtime 過濾非本 session 變更）。

    使用情境：Stop hook 在 session 結束時讀取本 session 內被修改的 worklog 段落。

    Args:
        worklog_path: worklog 檔案路徑
        since_mtime: session start timestamp（epoch float），檔案 mtime 必須 >= 此值才回傳內容

    Returns:
        str: 若檔案不存在或 mtime < since_mtime 回 ""，否則回完整檔案內容

    契約（Phase 2 sage S1-T10/T11）：
    - 不存在 → 回 ""（不 raise FileNotFoundError，配合 hook 靜默退出）
    - mtime < since_mtime → 回 ""（過濾非本 session 變更，避免重複提醒）

    Examples:
        >>> extract_recent_content(Path("/non/existent.md"), 0.0)
        ''
    """
    if not worklog_path.exists():
        return ""
    if worklog_path.stat().st_mtime < since_mtime:
        return ""
    return worklog_path.read_text(encoding="utf-8")


#: 行首錨定容許前綴：關鍵字前只能有 '#' / '*' / 空白，排除句中出現
#: （0.2.1-W3-294 根因 1：rfind 未錨定行首，命中自指語料的歷史分析行）
_ANCHOR_PREFIX_PATTERN: re.Pattern = re.compile(r"^[#*\s]*$")

#: 標題式關鍵字行判定：符合 Markdown H1-H6 標題格式
_TITLE_LINE_PATTERN: re.Pattern = re.compile(r"^#{1,6}\s")

#: 行內式段落終點候選：下一個行首條列 '- '
_INLINE_LIST_END_PATTERN: re.Pattern = re.compile(r"^- ", re.MULTILINE)

#: 行內式段落終點候選：下一個 '**' 起始行
_INLINE_BOLD_END_PATTERN: re.Pattern = re.compile(r"^\*\*", re.MULTILINE)


def _iter_anchored_keyword_hits(content: str):
    """找出所有「行首錨定」的 HANDOFF_KEYWORDS 命中位置。

    行首錨定：關鍵字前（同行）只能有 '#' / '*' / 空白字元，排除句中出現
    （如描述本機制的歷史分析行）。

    Yields:
        tuple[int, int]: (關鍵字起點 idx, 該行行首 idx)
    """
    for kw in HANDOFF_KEYWORDS:
        start = 0
        while True:
            idx = content.find(kw, start)
            if idx < 0:
                break
            line_start = content.rfind("\n", 0, idx) + 1
            prefix = content[line_start:idx]
            if _ANCHOR_PREFIX_PATTERN.match(prefix):
                yield idx, line_start
            start = idx + 1


def extract_handoff_section(content: str) -> str:
    """
    從 worklog 內容切出 handoff 相關段落（最新一筆，行首錨定命中）。

    策略（0.2.1-W3-294 重設計）：
    1. 只採「行首錨定」的關鍵字命中（關鍵字前僅允許 '#' / '*' / 空白），
       排除句中出現（本專案 worklog 大量記載 handoff 機制本身的分析，
       關鍵字會出現在描述偵測器的歷史行中，此類命中須被排除）。
    2. 取行首錨定命中中最後一個（idx 最大，對應當前 session 寫入的 handoff）。
    3. 依關鍵字所在行的形態分派終點界定：
       - 形態 A 標題式（行符合 `^#{1,6}\\s`）：終點為下一個 H1/H2 標題，
         無下一個標題則到 EOF（維持既有行為，涵蓋 HANDOFF_KEYWORDS 原設計
         的標題式用法）。
       - 形態 B 行內式（其餘，如本專案慣用 `**下一站**：`）：終點為下一個
         空行、下一個行首條列 `- `、或下一個 `**` 起始行，取最先命中；
         皆無命中則到 EOF。至少含關鍵字所在行本身。

    使用行首錨定 + rfind 最後命中的理由：
    worklog 累積多 session 的歷史 handoff 段落，且大量記載 handoff 機制
    本身的分析（W3-178 / W3-218 / W3-221 / W3-222 皆在改 HANDOFF_KEYWORDS），
    這些歷史行內含關鍵字但非交接段落。行首錨定過濾句中出現；取最後一個
    對應「當前 session 寫入的 handoff」，符合本函式「找出本 session 寫了
    什麼 handoff」的呼叫意圖。

    S2 差異（僅 hook 端適用，本函式不涉及）：
    Stop hook（`.claude/skills/ticket/hooks/stop-worklog-handoff-sync-check-hook.py`）
    在呼叫本函式（SOT-mirror）前，另有 session 增量前置過濾（以 git diff
    界定本 session 新增內容），縮小傳入 content 的範圍。CLI `--from-worklog`
    與本模組其他呼叫端無 session 概念，不套用該前置過濾，直接以全文呼叫
    本函式。此差異不構成 ARCH-020 漂移——本函式的段落界定邏輯（S1）三處
    共用且一致，S2 前置過濾是 hook 端獨有的呼叫前處理，非本函式職責。

    Args:
        content: worklog 全文內容（或已經 S2 前置過濾的 session 增量內容）

    Returns:
        str: handoff 段落內容；若無行首錨定關鍵字命中回 ""

    Examples:
        >>> content = "## 一般\\n\\n## 下個 Session 接手 Context\\n\\nW17-079\\n"
        >>> "W17-079" in extract_handoff_section(content)
        True
    """
    if not content:
        return ""

    hits = list(_iter_anchored_keyword_hits(content))
    if not hits:
        return ""

    # 取最後一個行首錨定命中（idx 最大）
    latest_idx, line_start = max(hits, key=lambda h: h[0])

    line_end = content.find("\n", latest_idx)
    if line_end == -1:
        line_end = len(content)
    line_text = content[line_start:line_end]

    if _TITLE_LINE_PATTERN.match(line_text):
        # 形態 A 標題式：終點為下一個 H1/H2 標題
        section_end_pattern = re.compile(r"^(# |## )", re.MULTILINE)
        next_match = section_end_pattern.search(content, latest_idx + 1)
        if next_match:
            return content[line_start : next_match.start()]
        return content[line_start:]

    # 形態 B 行內式：終點為下一個空行 / 下一個行首條列 / 下一個 '**' 起始行，取最先
    candidates: list[int] = []
    blank_idx = content.find("\n\n", line_end)
    if blank_idx != -1:
        candidates.append(blank_idx)
    list_match = _INLINE_LIST_END_PATTERN.search(content, line_end)
    if list_match:
        candidates.append(list_match.start())
    bold_match = _INLINE_BOLD_END_PATTERN.search(content, line_end)
    if bold_match:
        candidates.append(bold_match.start())

    if candidates:
        return content[line_start : min(candidates)]
    return content[line_start:]


def find_worklog_path(version: str) -> Path:
    """
    根據版本號定位 main worklog 檔案路徑（公開包裝）。

    包裝既有 worklog_appender._build_worklog_path() 為公開 API，
    供 S2 CLI 和 S3 Stop hook 共用。

    Args:
        version: 版本號（可帶或不帶 v 前綴），例 "0.18.0" 或 "v0.18.0"

    Returns:
        Path: worklog 檔案路徑（檔案可能不存在；呼叫端需自行檢查 .exists()）

    Examples:
        >>> path = find_worklog_path("0.18.0")
        >>> path.name
        'v0.18.0-main.md'
    """
    return _build_worklog_path(version)


if __name__ == "__main__":
    from .messages import print_not_executable_and_exit

    print_not_executable_and_exit()
