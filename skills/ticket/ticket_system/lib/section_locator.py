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


# Code fence 開頭行：行首最多 3 個空白，接 3 個以上 ` 或 ~（CommonMark fenced code block）
_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _find_fence_close(lines: list[str], open_index: int, marker: str) -> Optional[int]:
    """從 open_index 之後找關閉行：同字元、長度不短於開頭、該行只有 fence 字元。"""
    close = re.compile(rf"^ {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}\s*$")
    for index in range(open_index + 1, len(lines)):
        if close.match(lines[index]):
            return index
    return None


def fenced_line_flags(lines: list[str]) -> list[bool]:
    """標記每一行是否位於 code fence 內（含開頭與關閉行）。

    章節定位與 append-log 的 H2 降級共用本判定：fence 內的 `## ` 是範例文字，
    不是章節標題。未關閉的 fence 不視為 fence——若照 CommonMark 延伸到文件結尾，
    一個遺漏的關閉行會讓其後所有章節消失，定位失敗的代價高於維持既有行為。
    """
    flags = [False] * len(lines)
    index = 0
    while index < len(lines):
        opening = _FENCE_OPEN.match(lines[index])
        if not opening:
            index += 1
            continue
        marker = opening.group(1)
        # backtick fence 的 info string 不可含 backtick，否則該行是行內程式碼而非 fence
        if marker[0] == "`" and "`" in lines[index][opening.end():]:
            index += 1
            continue
        close_index = _find_fence_close(lines, index, marker)
        if close_index is None:
            index += 1
            continue
        for fenced in range(index, close_index + 1):
            flags[fenced] = True
        index = close_index + 1
    return flags


def mask_fenced_lines(text: str) -> str:
    """把 fence 內各行換成等長空白，保留換行；回傳字串與原文索引一一對應。"""
    lines = text.split("\n")
    flags = fenced_line_flags(lines)
    return "\n".join(" " * len(line) if fenced else line for line, fenced in zip(lines, flags))


def demote_h2_outside_fences(content: str) -> tuple[str, bool]:
    """把 fence 外的行首 `## ` 降為 `### `；回傳 (結果, 是否有降級)。"""
    lines = content.split("\n")
    flags = fenced_line_flags(lines)
    demoted = False
    result = []
    for line, fenced in zip(lines, flags):
        if not fenced and line.startswith("## "):
            line = "#" + line
            demoted = True
        result.append(line)
    return "\n".join(result), demoted


def _collect_h2_headers(masked_body: str) -> list[str]:
    """擷取已遮罩 fence 的 body 中所有 ## 標題（去尾空白）。"""
    return [h.strip() for h in re.findall(r"^##\s+.+$", masked_body, re.MULTILINE)]


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
        標題與邊界都在遮罩 fence 後的副本上搜尋（fenced_line_flags），fence 內的
        `## ` 不構成章節；副本與原文等長，索引直接用於切原文。
    """
    if not body:
        return SectionMatch(found=False, all_headers=[])

    masked = mask_fenced_lines(body)
    all_headers = _collect_h2_headers(masked)

    header_match = None
    for level in levels:
        prefix = "#" * level
        pattern = rf"^{prefix}\s+{re.escape(name)}\s*$"
        header_match = re.search(pattern, masked, re.MULTILINE)
        if header_match:
            break

    if not header_match:
        return SectionMatch(found=False, all_headers=all_headers)

    start = header_match.start()
    content_start = header_match.end()
    next_match = re.search(r"\n## ", masked[content_start:])
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
