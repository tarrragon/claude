"""Section locator helper — 統一 Markdown section 標題定位邏輯。

抽取自 4 處重複（W17-117.1）：
- commands/track_acceptance.py（append-log 寫入點）
- commands/track_query.py（--section 過濾分支）
- lib/acceptance_auditor.py（必填章節驗證，雙層級 ##/###）

容錯規則（W17-008.9 一致）：
- MULTILINE 模式 + `\\s+` 容多空白 + `\\s*$` 容尾空白
- `re.escape(name)` 避前綴誤匹配（"Section Name" 不應匹配 "SectionName Plus"）
- 邊界判定使用 `\\n## `（同層級 H2）；多層級時 ### 子標題屬於父 section 內容
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SectionMatch:
    """Section 定位結果。

    Attributes:
        found: 是否找到 section
        start: section header 起點（body 索引）
        content_start: header 結束、content 起點
        end: section 結束（next ## 起點 或 len(body)）
        text: full section_text（含 header + content）
        content: section content only（不含 header）
        all_headers: body 中所有 ## 標題清單（供 SECTION_NOT_FOUND 列舉）
    """

    found: bool
    start: int = 0
    content_start: int = 0
    end: int = 0
    text: str = ""
    content: str = ""
    all_headers: list[str] = field(default_factory=list)


def _collect_h2_headers(body: str) -> list[str]:
    """擷取 body 中所有 ## 標題（去尾空白）。"""
    return [h.strip() for h in re.findall(r"^##\s+.+$", body, re.MULTILINE)]


def find_section(
    body: str,
    name: str,
    *,
    levels: tuple[int, ...] = (2,),
) -> SectionMatch:
    """定位 Markdown section 並擷取範圍。

    Args:
        body: 完整 markdown body 文字
        name: section 名稱（如 "Solution"、"Problem Analysis"）
        levels: 接受的標題層級。預設 `(2,)` 僅 `##`；`(2, 3)` 同時容許 `##` 與 `###`
            （acceptance_auditor 雙層級需求）。優先嘗試低 level（##）

    Returns:
        SectionMatch — found=False 表示未找到；all_headers 一律填入 H2 標題清單
        供 SECTION_NOT_FOUND 錯誤列舉。

    Note:
        邊界統一以 `\\n## `（H2）為終止點；即使 levels=(2, 3) 找到 ### 也以下一個
        同層級或上層 ## 為邊界（與 acceptance_auditor 既有行為一致）。
    """
    all_headers = _collect_h2_headers(body) if body else []

    if not body:
        return SectionMatch(found=False, all_headers=all_headers)

    header_match = None
    for level in levels:
        prefix = "#" * level
        pattern = rf"^{prefix}\s+{re.escape(name)}\s*$"
        header_match = re.search(pattern, body, re.MULTILINE)
        if header_match:
            break

    if not header_match:
        return SectionMatch(found=False, all_headers=all_headers)

    start = header_match.start()
    content_start = header_match.end()
    next_match = re.search(r"\n## ", body[content_start:])
    end = content_start + next_match.start() if next_match else len(body)

    return SectionMatch(
        found=True,
        start=start,
        content_start=content_start,
        end=end,
        text=body[start:end],
        content=body[content_start:end],
        all_headers=all_headers,
    )
