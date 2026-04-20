"""AC 解析器：解析 Ticket frontmatter 的 acceptance list 為結構化 AC 物件。

本模組為 PROP-010 Phase 1 MVP 基礎設施，供 W5-002 (claim 命令) 於派發前
對照 AC 實況，避免代理人重做已完成工作 (PC-055 ticket AC drift)。

公開 API：
    parse_ac(ticket_id) -> list[AC]

資料結構：
    AC: frozen dataclass，含 index/text/checked/raw 四欄位。
"""

from __future__ import annotations

from dataclasses import dataclass

from ticket_system.lib import checkbox_utils, id_parser, parser


@dataclass(frozen=True)
class AC:
    """Acceptance Criterion 物件（frozen）。

    Attributes:
        index: 於 acceptance list 的 0-based 位置。
        text: 已剝除 checkbox 前綴的純文字（模板匹配輸入）。
        checked: 該項是否已勾選（[x] → True, [ ] → False）。
        raw: 原始字串（含 checkbox 標記），回寫與除錯用。
    """

    index: int
    text: str
    checked: bool
    raw: str


def parse_ac(ticket_id: str) -> list[AC]:
    """解析 Ticket frontmatter 的 acceptance list。

    Args:
        ticket_id: Ticket ID（如 "0.18.0-W5-001"）。

    Returns:
        依出現順序（index 從 0）的 AC 物件清單。
        若 frontmatter 無 acceptance 欄位或為空清單，回傳 []。

    Raises:
        ValueError: ticket_id 格式無效，或 acceptance 欄位型別非 list，
            或 Ticket YAML 解析失敗。
        FileNotFoundError: 找不到對應的 Ticket 檔案。

    Note:
        本函式依賴 `parser.load_ticket` 回傳 None 而非 raise 的既有契約。
        若 `load_ticket` 未來改為 raise FileNotFoundError，本函式的 None 檢查路徑
        將變為 dead code，需同步調整。
    """
    # 步驟 1：解析版本
    components = id_parser.extract_id_components(ticket_id)
    if components is None:
        raise ValueError(f"無效的 ticket_id 格式: {ticket_id}")
    version = components["version"]

    # 步驟 2：載入 Ticket（既有 API 回 None 而非 raise）
    ticket = parser.load_ticket(version, ticket_id)
    if ticket is None:
        raise FileNotFoundError(f"找不到 Ticket: {ticket_id}")

    # 步驟 2.5：檢查 YAML 解析錯誤（load_ticket 損毀檔案時回傳含 _yaml_error 的 dict）
    if "_yaml_error" in ticket:
        raise ValueError(f"Ticket YAML 解析失敗: {ticket['_yaml_error']}")

    # 步驟 3：取出 acceptance 欄位
    acceptance = ticket.get("acceptance")
    if acceptance is None:
        return []

    # 步驟 4：型別防護（空 list 亦為 list，會落入步驟 5 並回 []）
    if not isinstance(acceptance, list):
        raise ValueError(
            f"acceptance 欄位型別錯誤，預期 list，實際: {type(acceptance).__name__}"
        )

    # 步驟 5：逐項解析
    result: list[AC] = []
    for index, raw_item in enumerate(acceptance):
        result.append(_parse_single_item(index, raw_item))

    return result


def _parse_single_item(index: int, raw_item: object) -> AC:
    """將單一 acceptance 項目解析為 AC 物件。

    YAML 引號已由 parser 層剝除，此處只需處理 checkbox 前綴。
    未帶 checkbox 的項目保守視為未勾選，text = 原文（技術債 4.2）。
    """
    raw_str = str(raw_item)
    checked, text = checkbox_utils.strip_checkbox_prefix(raw_str)
    return AC(index=index, text=text, checked=checked, raw=raw_str)
