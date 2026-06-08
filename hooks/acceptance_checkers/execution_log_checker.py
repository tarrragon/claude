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


def check_execution_log_filled(content: str, logger, ticket_type: str = None) -> bool:
    """
    檢查 Ticket 的 execution log（Solution/Test Results）是否有實質內容。

    W8-007：ANA type ticket 的核心產出之一是「重現實驗結果」章節。
    該章節若為 H3 骨架空殼（如「### 實驗方法」+「（必填：...）」placeholder）
    而 Solution/Test Results 不空，舊版會放行 complete。新版對 ANA type
    額外檢查重現實驗結果，空殼即視為未填寫。

    Args:
        content: Ticket 檔案完整文字內容
        logger: 日誌物件
        ticket_type: ticket 類型（如 "ANA" / "IMP"）。為 None 時維持舊行為
            （只查 Solution/Test Results），確保向後相容。

    Returns:
        bool - True 表示未填寫（空的），False 表示已填寫
    """
    # 檢查 Solution 區段
    solution_empty = _is_section_empty(content, "Solution")
    # 檢查 Test Results 區段
    test_results_empty = _is_section_empty(content, "Test Results")

    is_empty = solution_empty and test_results_empty

    # W8-007：ANA type 額外檢查重現實驗結果。ANA 重現實驗是核心產出，
    # 空殼即使 Solution/Test Results 有內容也應視為未填寫（OR 邏輯）。
    if ticket_type == "ANA":
        reproduction_empty = _is_section_empty(content, "重現實驗結果")
        if reproduction_empty:
            is_empty = True
            logger.info("ANA 重現實驗結果章節為空殼（H3 骨架 / placeholder）")

    if is_empty:
        logger.info("Execution log 未填寫")
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

    W8-007 修復重點：
    - Root cause C：ANA 重現實驗結果章節的 schema 範本含 H3 子標題骨架
      （如 `### 實驗方法`）與 `（必填：...）` placeholder。原先未剝除這兩者，
      導致只有骨架的空殼章節被誤判為非空。新增 H3 標題行與「必填」placeholder
      剝除邏輯。
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
    # W8-007：移除 H3（及更深）子標題行（如 `### 實驗方法`）。
    # ANA 重現實驗結果範本以 H3 骨架組織，骨架本身非實質內容。
    section_content = re.sub(
        r'^[ \t]*#{3,}[ \t].*$', '', section_content, flags=re.MULTILINE
    ).strip()
    # 移除模板佔位符（如 "（待填寫：...）" / "（必填：...）"）
    section_content = re.sub(r'（待填寫[^）]*）', '', section_content).strip()
    # W8-007：移除「必填」placeholder（如 "（必填：描述如何重現問題）"）
    section_content = re.sub(r'（必填[^）]*）', '', section_content).strip()
    # 移除空行
    section_content = '\n'.join(line for line in section_content.split('\n') if line.strip())

    return len(section_content) == 0
