"""
Self-Check Visibility Checker - Layer 1 自檢可觀測性檢查（W17-064）

W17-064：偵測 IMP/ANA/DOC ticket 的 Solution 章節是否含 `### 自檢結果` 子章節。
若缺少則輸出 warning（不阻擋 complete），提示代理人執行 Layer 1 自檢
（依 `.claude/references/agent-self-check-template.md`）。

設計依據（W17-064.1 ANA 三維度決策）：
- Hook 行為：B warning only（exit 0 + stderr，不阻擋 complete）
- 觸發範圍：全 IMP/ANA/DOC type；非適用 type 直接 return None
- 豁免機制：不需要（warning 已是最低強度）

設計要點：
- 不阻擋（僅警告）：對 PM + agent 的可見訊號，落實 Layer 1 自檢落地。
- 範圍精準：僅檢查 `## Solution` 章節下的 `### 自檢結果`，不掃描整個 body。
- type 過濾：非 IMP/ANA/DOC（如 TST/RES/INV/ADJ）直接跳過。
"""

import re
from typing import Optional

# 觸發 Layer 1 自檢檢查的 ticket type 集合
_APPLICABLE_TYPES = {"IMP", "ANA", "DOC"}

# 自檢結果子章節標題（H3）
_SELF_CHECK_HEADING = "自檢結果"


def _strip_frontmatter(content: str) -> str:
    """剝除 YAML frontmatter，僅回傳 body 文字。"""
    if not content.startswith("---"):
        return content
    match = re.search(r"^---\s*$", content[3:], flags=re.MULTILINE)
    if not match:
        return content
    return content[3 + match.end():]


def _extract_solution_section(body: str) -> Optional[str]:
    """
    從 body 抽取 `## Solution` 章節內容（直到下一個 H2 或檔案結尾）。

    Returns:
        Solution 章節文字（不含 `## Solution` 標題行）；若無此章節則回傳 None。
    """
    # 匹配 `## Solution` 行（可能後接空白），擷取到下一個 `^## ` 或檔案結尾
    pattern = r"^## Solution\s*$(.*?)(?=^## |\Z)"
    match = re.search(pattern, body, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return None
    return match.group(1)


def _has_self_check_subsection(solution_text: str) -> bool:
    """
    檢查 Solution 章節文字中是否含 `### 自檢結果` 子章節（H3）。

    前綴匹配（W10-124 / W10-118 Case C）：標題後允許接補充說明，但補充說明必須
    以分隔符（whitespace / 全形或半形括號）開始，避免 `### 自檢結果摘要` 等異義
    標題誤匹配。
    """
    # 標題後需為 end-of-line，或接 whitespace / `（` / `(` 後跟任意字元
    pattern = rf"^### {re.escape(_SELF_CHECK_HEADING)}(?:[\s（(].*)?$"
    return bool(re.search(pattern, solution_text, flags=re.MULTILINE))


def check_self_check_visibility(
    content: str, ticket_type: str, logger
) -> Optional[str]:
    """
    檢查 ticket Solution 是否含 `### 自檢結果` 子章節。

    Args:
        content: Ticket 檔案完整文字內容（含 frontmatter）
        ticket_type: Ticket 類型（IMP/ANA/DOC/TST/...）
        logger: 日誌物件

    Returns:
        warning 訊息字串（非 None 時表示違規）；若靜默通過或不適用則 None。

    觸發條件：
        - ticket_type 屬於 IMP/ANA/DOC，且
        - body 含 `## Solution` 章節，且
        - Solution 下無 `### 自檢結果` 子章節

    範例：
        >>> content = "## Solution\\n內容\\n"
        >>> check_self_check_visibility(content, "IMP", logger)
        '[Layer 1] ...'  # 違規 warning
    """
    type_upper = (ticket_type or "").upper()
    if type_upper not in _APPLICABLE_TYPES:
        logger.debug(f"ticket type={type_upper} 非 IMP/ANA/DOC，跳過 Layer 1 自檢檢查")
        return None

    body = _strip_frontmatter(content)
    solution_text = _extract_solution_section(body)

    if solution_text is None:
        # 無 Solution 章節（可能 ticket 還沒填寫），交由其他 checker 處理
        logger.debug("ticket body 無 ## Solution 章節，跳過 Layer 1 自檢檢查")
        return None

    if _has_self_check_subsection(solution_text):
        logger.info("Layer 1 自檢結果子章節已存在，靜默通過")
        return None

    logger.info(f"ticket type={type_upper} 的 Solution 缺 ### 自檢結果 子章節，輸出 warning")
    return (
        "[Layer 1 自檢可觀測性] Solution 中未見 ### 自檢結果 子章節（W17-064）\n"
        "依 `.claude/references/agent-self-check-template.md`，IMP/ANA/DOC ticket 完成前\n"
        "建議於 `## Solution` 下新增 `### 自檢結果` 子章節，記錄 Layer 1 自檢清單檢視結果。\n"
        "本檢查為 warning（不阻擋 complete），目的為提升自檢流程可觀測性。"
    )
