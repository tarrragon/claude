"""
Execution Log Checker - 執行日誌填寫檢查

檢查 Ticket 的 Solution/Test Results 區段是否有實質內容。
"""

import re

# W17-071：Schema 定義章節名清單（與 ticket_validator._SCHEMA_SECTION_NAMES 同步）。
# 擷取 section 內容時只把這些章節名當作邊界，避免 agent 自定義 H2
# （如 `## 實作摘要`）把 schema section 範圍切斷。
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


def check_execution_log_filled(content: str, logger) -> bool:
    """
    檢查 Ticket 的 execution log（Solution/Test Results）是否有實質內容。

    Args:
        content: Ticket 檔案完整文字內容
        logger: 日誌物件

    Returns:
        bool - True 表示未填寫（空的），False 表示已填寫
    """
    # 檢查 Solution 區段
    solution_empty = _is_section_empty(content, "Solution")
    # 檢查 Test Results 區段
    test_results_empty = _is_section_empty(content, "Test Results")

    is_empty = solution_empty and test_results_empty

    if is_empty:
        logger.info("Execution log 未填寫（Solution 和 Test Results 皆空）")
    else:
        logger.info("Execution log 已有內容")

    return is_empty


def _find_schema_section_boundary_regex() -> str:
    """
    生成 Schema 定義章節標題的 regex alternation（W17-071）。

    只把 `_SCHEMA_SECTION_NAMES` 中的章節名當作區段邊界；
    自定義 H2（如 `## 實作摘要`）或其他非 schema 章節不算邊界。

    支援 `## SectionName` 層級，行首匹配（與 ticket body 結構對齊）。
    """
    names_alt = "|".join(re.escape(n) for n in _SCHEMA_SECTION_NAMES)
    return rf"^## (?:{names_alt})\b"


def _is_section_empty(content: str, section_name: str) -> bool:
    """
    檢查 Markdown 區段是否為空（只有模板佔位符或 HTML 註解或 markdown 分隔符）。

    W17-071 修復重點：
    - Root cause A：HTML 註解剝除後若剩下 markdown 分隔符 `---`（ticket body
      schema 章節間的水平分隔），原先判為非空。新增分隔符剝除邏輯。
    - Root cause B：原先使用「任意 `##`」作為區段邊界，agent 寫自定義 H2
      會把 schema section 切斷。改為僅以 Schema 定義的章節名作為邊界。
    """
    # W17-071：下一個區段邊界只認 Schema 定義的章節名
    boundary_regex = _find_schema_section_boundary_regex()
    pattern = (
        rf'^## {re.escape(section_name)}\s*\n(.*?)(?={boundary_regex}|\Z)'
    )
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        return True

    section_content = match.group(1).strip()

    # 移除 HTML 註解
    section_content = re.sub(r'<!--.*?-->', '', section_content, flags=re.DOTALL).strip()
    # W17-071：移除 markdown 分隔符（行首行尾獨立一行的 `---+`）
    # schema 範本使用 `---` 分隔章節，但分隔符本身非實質內容；
    # 原先未剝除導致「schema note + 分隔符」的空殼章節被誤判為非空。
    section_content = re.sub(
        r'^[ \t]*-{3,}[ \t]*$', '', section_content, flags=re.MULTILINE
    ).strip()
    # 移除模板佔位符（如 "（待填寫：...）"）
    section_content = re.sub(r'（待填寫[^）]*）', '', section_content).strip()
    # 移除空行
    section_content = '\n'.join(line for line in section_content.split('\n') if line.strip())

    return len(section_content) == 0
