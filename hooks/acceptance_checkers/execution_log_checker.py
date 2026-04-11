"""
Execution Log Checker - 執行日誌填寫檢查

檢查 Ticket 的 Solution/Test Results 區段是否有實質內容。
"""

import re


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


def _is_section_empty(content: str, section_name: str) -> bool:
    """檢查 Markdown 區段是否為空（只有模板佔位符或 HTML 註解）"""
    # 匹配 ## Section Name 到下一個 ## 或檔案結尾
    pattern = rf'^## {re.escape(section_name)}\s*\n(.*?)(?=^## |\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        return True

    section_content = match.group(1).strip()

    # 移除 HTML 註解
    section_content = re.sub(r'<!--.*?-->', '', section_content, flags=re.DOTALL).strip()
    # 移除模板佔位符（如 "（待填寫：...）"）
    section_content = re.sub(r'（待填寫[^）]*）', '', section_content).strip()
    # 移除空行
    section_content = '\n'.join(line for line in section_content.split('\n') if line.strip())

    return len(section_content) == 0
