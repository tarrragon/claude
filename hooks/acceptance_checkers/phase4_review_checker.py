"""
Phase 4 Review Evidence Checker（0.38.1-W1-080.1）

IMP ticket complete 時檢查 Solution 章節是否含 Phase 4 審查證據。
缺少時 emit WARNING（不阻擋 complete），提醒執行 /parallel-evaluation。

觸發範圍：僅 IMP type（ANA/DOC 不適用 Phase 4 重構評估）。
行為：warning only（exit 0 + stderr），與 self_check_visibility_checker 同強度。

Phase 4 證據關鍵字：審查結果以多種形式記錄在 Solution 中，
任一命中即視為有審查證據（寬鬆匹配避免 false positive）。
"""

import re
from typing import Optional

_APPLICABLE_TYPES = {"IMP"}

_PHASE4_EVIDENCE_KEYWORDS = [
    "並行評估",
    "parallel-evaluation",
    "多視角",
    "Phase 4",
    "phase4",
    "重構評估",
    "code-reviewer",
    "code review",
    "Layer 2",
]


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    match = re.search(r"^---\s*$", content[3:], flags=re.MULTILINE)
    if not match:
        return content
    return content[3 + match.end():]


def _extract_solution_section(body: str) -> Optional[str]:
    pattern = r"^## Solution\s*$(.*?)(?=^## |\Z)"
    match = re.search(pattern, body, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return None
    return match.group(1)


def _has_phase4_evidence(solution_text: str) -> bool:
    text_lower = solution_text.lower()
    for keyword in _PHASE4_EVIDENCE_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False


def check_phase4_review_evidence(
    content: str, ticket_type: str, logger
) -> Optional[str]:
    """檢查 IMP ticket Solution 是否含 Phase 4 審查證據。

    Returns:
        warning 訊息（違規時）；通過或不適用則 None。
    """
    type_upper = (ticket_type or "").upper()
    if type_upper not in _APPLICABLE_TYPES:
        logger.debug(f"ticket type={type_upper} 非 IMP，跳過 Phase 4 審查檢查")
        return None

    body = _strip_frontmatter(content)
    solution_text = _extract_solution_section(body)

    if solution_text is None:
        logger.debug("ticket body 無 ## Solution 章節，跳過 Phase 4 審查檢查")
        return None

    if _has_phase4_evidence(solution_text):
        logger.info("Phase 4 審查證據已存在，靜默通過")
        return None

    logger.info(f"ticket type={type_upper} 的 Solution 缺 Phase 4 審查證據，輸出 warning")
    return (
        "[Phase 4 審查] Solution 中未見 Phase 4 審查證據（0.38.1-W1-080.1）\n"
        "依 quality-baseline 規則 2，IMP ticket 必須完成 Phase 4 重構評估（無論是否走 TDD 流程）。\n"
        "建議執行 /parallel-evaluation 並將結論記錄到 Solution。\n"
        "本檢查為 warning（不阻擋 complete）。豁免：DOC type / 小型修改（<= 2 檔案）。"
    )
