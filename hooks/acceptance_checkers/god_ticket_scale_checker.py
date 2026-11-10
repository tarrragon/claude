"""
God Ticket Scale Checker - Ticket 規模判準（0.2.1-W3-052.1 由 C1 移植）

移植自 `.claude/lib/ticket_quality/detectors.py` 的 C1 God Ticket 檢測，僅保留
「檔案數量」指標並改讀 frontmatter `where.files`（新執行點 acceptance-gate 落在
`ticket track complete` 的 PreToolUse，看不到即將寫入的完整內容，只能讀 ticket
現況；原 hook 掛 PostToolUse + Write，可看到寫入內容）。

不移植的部分：
- 層級跨度指標（`determine_layer()` 依賴路徑模式對應 5 層架構）：既有 ticket
  `where.layer` 欄位 81% 為「待定義」，且已有樣本值為誤填（逗號分隔檔案清單
  混入 layer 欄位），數值不可靠，移植會產生高誤判率。
- 預估工時指標（`step_count * 0.5 + file_count * 0.5 + layer_span * 2`）：公式
  依賴上述層級跨度與步驟計數 regex，同樣缺乏現行 schema 對應基礎。

檔案數閾值不沿用 v0.12.G 的 10（該值以 PostToolUse 讀取的完整 body 內容做
regex 抽取，涵蓋範圍較寬鬆）；改採 `.claude/rules/core/cognitive-load.md`
「任務拆分閾值」表既有 SSOT：「修改檔案數 > 5 必須拆分」，避免同一概念在框架內
維護兩套門檻。
"""

from typing import List

from acceptance_checkers.ticket_parser import extract_where_files

# SSOT: .claude/rules/core/cognitive-load.md 任務拆分閾值表「修改檔案數 > 5 必須拆分」
_FILE_COUNT_THRESHOLD = 5

# Type-aware 豁免（沿用 ticket-body-schema.md「Type-aware Quality Gate」既有慣例：
# ANA/DOC 跳過 C1/C3 檢查，只有 IMP 觸發；缺 type 視為向後相容仍觸發）
_EXEMPT_TYPES = {"ANA", "DOC"}


def check_god_ticket_scale(frontmatter: dict, logger) -> List[str]:
    """
    檢查 ticket 規模（檔案數）是否超過拆分閾值。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        List[str] - 違規項目清單（空清單表示通過）。超標時內容為
        `["file_count:{實際數}>{閾值}"]`（單一元素，保留 list 型別以與其他
        checker 介面慣例一致）。
    """
    ticket_type = (frontmatter.get("type") or "").upper()
    if ticket_type in _EXEMPT_TYPES:
        logger.info(f"ticket type={ticket_type} 豁免規模檢查（ANA/DOC 不適用）")
        return []

    valid_files = extract_where_files(frontmatter, logger)
    file_count = len(valid_files)

    if file_count > _FILE_COUNT_THRESHOLD:
        violation = f"file_count:{file_count}>{_FILE_COUNT_THRESHOLD}"
        logger.info(f"規模檢查未通過: {violation}")
        return [violation]

    logger.info(f"規模檢查通過（檔案數 {file_count} <= {_FILE_COUNT_THRESHOLD}）")
    return []
