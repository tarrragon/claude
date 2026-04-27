"""
Custom H2 Checker - 自定義 H2 章節偵測（W17-072）

W17-072：偵測 ticket body 中出現的非 Schema H2 章節，於 complete 時輸出 warning
（不阻擋）。配合 `.claude/rules/core/agent-definition-standard.md` v1.2.0「禁止自定義
H2」條款，讓 agent 違規寫入 `## 實作摘要` / `## 驗證指令與結果` 等自定義 H2 時能被
主線程及時察覺。

設計要點：
- 不阻擋（僅警告）：避免與 W17-071 既有 hook 邏輯重複擋，warning 是對 PM + agent 的
  可見訊號，落實「失敗案例學習」（quality-baseline 規則 6）。
- 與 `_SCHEMA_SECTION_NAMES` 同步：與 `execution_log_checker` / `ticket_validator`
  共用 Schema 章節清單，避免三處分裂定義。
- 僅掃描 body（frontmatter 後）：`---` 之後的第一個 `^## ` 起算。
"""

import re
from typing import List

# W17-072：Schema 定義章節名清單（必須與 `execution_log_checker._SCHEMA_SECTION_NAMES`
# 及 `ticket_validator._SCHEMA_SECTION_NAMES` 同步；三處將於 ARCH-020 refactor 收斂）。
# 來源：.claude/pm-rules/ticket-body-schema.md
_SCHEMA_SECTION_NAMES = [
    "Task Summary",
    "Problem Analysis",
    "Solution",
    "Test Results",
    "Completion Info",
    "NeedsContext",
    "Exit Status",
    "重現實驗結果",
    "Context Bundle",
]


def _strip_frontmatter(content: str) -> str:
    """
    剝除 YAML frontmatter，僅回傳 body 文字。

    Frontmatter 格式：以 `---\\n` 開頭，以 `\\n---\\n` 結尾（符合 Jekyll 慣例）。
    若無 frontmatter（content 不以 `---` 開頭），直接回傳 content。
    """
    if not content.startswith("---"):
        return content

    # 找第二個 `---` 分隔符（frontmatter 結束）
    # 跳過第一行的 `---` 開頭，從第 4 字元後搜尋下一個 `^---\s*$`
    match = re.search(r"^---\s*$", content[3:], flags=re.MULTILINE)
    if not match:
        return content

    frontmatter_end = 3 + match.end()
    return content[frontmatter_end:]


def find_custom_h2_sections(content: str) -> List[str]:
    """
    掃描 ticket body 中的 H2 章節標題，回傳非 Schema 章節的 H2 名稱清單。

    Args:
        content: Ticket 檔案完整文字內容（含 frontmatter）

    Returns:
        List[str]: 非 Schema H2 章節名稱清單（例：`["實作摘要", "驗證指令與結果"]`）；
                   無違規時回傳空 list。

    範例：
        >>> content = "## Solution\\n內容\\n\\n## 實作摘要\\n違規章節\\n"
        >>> find_custom_h2_sections(content)
        ['實作摘要']
    """
    body = _strip_frontmatter(content)

    # 掃描所有 `## HeadingName`（行首 H2）
    # 排除 `### ` 子章節（allowed）與 `#### ` 以下
    h2_pattern = r"^## (.+?)\s*$"
    all_h2 = re.findall(h2_pattern, body, flags=re.MULTILINE)

    # 過濾出非 Schema 章節
    schema_set = set(_SCHEMA_SECTION_NAMES)
    custom_h2 = []
    for heading in all_h2:
        heading_stripped = heading.strip()
        # 逐一比對 Schema 章節名（行首 match 後取章節名部分）
        if not any(heading_stripped.startswith(name) for name in schema_set):
            custom_h2.append(heading_stripped)

    return custom_h2


def check_custom_h2_sections(content: str, logger) -> List[str]:
    """
    檢查 ticket body 是否含非 Schema H2 章節，回傳違規清單並記錄 log。

    Args:
        content: Ticket 檔案完整文字內容
        logger: 日誌物件

    Returns:
        List[str]: 非 Schema H2 章節名稱清單（空 list 表示無違規）
    """
    custom_h2 = find_custom_h2_sections(content)

    if custom_h2:
        logger.info(
            f"偵測到 {len(custom_h2)} 個非 Schema H2 章節: {custom_h2}"
        )
    else:
        logger.info("未偵測到非 Schema H2 章節")

    return custom_h2
