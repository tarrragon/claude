"""
Ticket Quality Gate - 資訊提取函式

提供從 Ticket 內容提取各種資訊的輔助函式
"""

import re
from typing import List


def has_section(ticket_content: str, section_name: str) -> bool:
    """
    檢查章節存在性

    支援多種章節標題格式:
    - ## 驗收條件
    - ### 驗收條件
    - ## ✅ 驗收條件
    - ### ✅ 驗收條件

    Args:
        ticket_content: Ticket 內容
        section_name: 章節名稱（如「驗收條件」）

    Returns:
        bool - 章節是否存在
    """
    # 支援多種章節標題格式
    patterns = [
        rf"## {re.escape(section_name)}",    # ## 驗收條件
        rf"### {re.escape(section_name)}",   # ### 驗收條件
        rf"## .*{re.escape(section_name)}",  # ## ✅ 驗收條件
        rf"### .*{re.escape(section_name)}"  # ### ✅ 驗收條件
    ]

    for pattern in patterns:
        if re.search(pattern, ticket_content):
            return True

    return False


def extract_section(ticket_content: str, section_name: str) -> str:
    """
    提取章節內容

    策略: 提取章節標題到下一個同級標題之間的內容

    正則說明:
    - ##+ : 章節標題（2個或以上#）
    - .*? : 章節前後綴內容（非貪婪）
    - \n(.*?) : 章節內容（捕獲組，非貪婪）
    - (?=\n##|$) : 前瞻下一個章節或檔案結尾

    Args:
        ticket_content: Ticket 內容
        section_name: 章節名稱

    Returns:
        str - 章節內容（不包含標題），如果章節不存在則回傳空字串
    """
    # 匹配: ## 章節名 ... (到下一個 ## 或檔案結尾)
    pattern = rf"##+ .*?{re.escape(section_name)}.*?\n(.*?)(?=\n##|$)"
    match = re.search(pattern, ticket_content, re.DOTALL)

    if match:
        return match.group(1).strip()
    else:
        return ""


def extract_acceptance_criteria(ticket_content: str) -> List[str]:
    """
    提取驗收條件列表

    策略: 提取驗收條件章節中的 checkbox 或編號列表

    Args:
        ticket_content: Ticket 內容

    Returns:
        List[str] - 驗收條件列表
    """
    # 先提取驗收條件章節
    section_content = extract_section(ticket_content, "驗收條件")

    if not section_content:
        return []

    acceptance_items = []

    # 模式 1: Checkbox 列表（- [ ] 項目）
    checkbox_pattern = r"- \[ \] (.+)"
    matches = re.findall(checkbox_pattern, section_content)
    acceptance_items.extend(matches)

    # 模式 2: 編號列表（1. 項目）
    numbered_pattern = r"\d+\. (.+)"
    matches = re.findall(numbered_pattern, section_content)
    acceptance_items.extend(matches)

    return acceptance_items


def extract_file_paths(ticket_content: str) -> List[str]:
    """
    提取檔案路徑（支援多種格式）

    支援格式:
    1. 程式碼區塊中的路徑
    2. Inline code 格式（`lib/.../*.dart`）
    3. 列表項目格式（- lib/.../*.dart）
    4. 步驟中路徑（步驟 1: 修改 lib/.../*.dart）

    策略: 使用多個正則表達式模式，依序匹配並合併結果

    Args:
        ticket_content: Ticket 內容

    Returns:
        List[str] - 檔案路徑列表（已去重並排序）
    """
    paths = _extract_paths_from_all_formats(ticket_content)
    return _normalize_and_deduplicate_paths(paths)


def _extract_paths_from_all_formats(content: str) -> List[str]:
    """
    從所有支援的格式中提取路徑

    Args:
        content: Ticket 內容

    Returns:
        List[str] - 所有匹配的路徑（未去重）
    """
    paths = []
    paths.extend(_extract_code_block_paths(content))
    paths.extend(_extract_inline_code_paths(content))
    paths.extend(_extract_list_item_paths(content))
    paths.extend(_extract_step_paths(content))
    return paths


def _extract_code_block_paths(content: str) -> List[str]:
    """
    提取程式碼區塊中的路徑

    模式: ```dart\nlib/domain/entities/book.dart\n```
    """
    pattern = r"```(?:dart|python|text)?\s*\n((?:lib/|test/|docs/)[\w/]+\.(?:dart|py|md))\s*\n"
    return re.findall(pattern, content)


def _extract_inline_code_paths(content: str) -> List[str]:
    """
    提取 inline code 格式的路徑

    模式: `lib/domain/entities/book.dart`
    """
    pattern = r"`((?:lib/|test/|docs/)[\w/._-]+\.(?:dart|py|md))`"
    return re.findall(pattern, content)


def _extract_list_item_paths(content: str) -> List[str]:
    """
    提取列表項目格式的路徑

    模式: - lib/domain/entities/book.dart
    """
    pattern = r"^-\s+((?:lib/|test/|docs/)[\w/._-]+\.(?:dart|py|md))"
    return re.findall(pattern, content, re.MULTILINE)


def _extract_step_paths(content: str) -> List[str]:
    """
    提取步驟中的路徑

    模式: 步驟 1: 修改 lib/domain/entities/book.dart
    """
    # 使用 re.VERBOSE 提升可讀性
    pattern = r"""
        (?:步驟|修改|新增|刪除|更新|撰寫)  # 步驟關鍵字
        \s+                                  # 空白
        \d*:?\s*                             # 可選的編號和冒號
        (?:修改|新增|刪除|更新|撰寫)?        # 可選的動作關鍵字
        (?:測試)?                            # 可選的「測試」關鍵字
        \s+                                  # 空白
        ((?:lib/|test/|docs/)[\w/._-]+\.(?:dart|py|md))  # 檔案路徑（捕獲組）
    """
    return re.findall(pattern, content, re.VERBOSE)


def _normalize_and_deduplicate_paths(paths: List[str]) -> List[str]:
    """
    路徑標準化和去重

    處理:
    1. 移除多餘空白
    2. 統一分隔符（反斜線 → 正斜線）
    3. 去重並排序
    """
    normalized = [p.strip().replace("\\", "/") for p in paths]
    return sorted(set(normalized))


def count_steps(ticket_content: str) -> int:
    """
    計算步驟數量

    支援 4 種步驟格式識別:
    - 步驟 1:
    - 1.
    - - [ ]
    - - 步驟

    Args:
        ticket_content: Ticket 內容

    Returns:
        int - 步驟數量
    """
    section_content = extract_section(ticket_content, "實作步驟")
    if not section_content:
        return 0
    return _count_unique_steps(section_content)


def _count_unique_steps(content: str) -> int:
    """
    統計唯一步驟數

    策略: 合併所有格式的步驟標記，去重後計數
    """
    steps = []
    steps.extend(_find_numbered_steps(content))
    steps.extend(_find_numbered_list(content))
    steps.extend(_find_checkbox_items(content))
    steps.extend(_find_step_bullets(content))
    return len(set(steps)) if steps else 0


def _find_numbered_steps(content: str) -> List[str]:
    """
    提取「步驟 1」格式

    模式: 步驟 1, 步驟 2, ...
    """
    return re.findall(r"步驟\s+\d+", content)


def _find_numbered_list(content: str) -> List[str]:
    """
    提取「1.」編號列表格式

    模式: 1. xxx, 2. xxx, ...
    """
    return re.findall(r"^\d+\.\s+", content, re.MULTILINE)


def _find_checkbox_items(content: str) -> List[str]:
    """
    提取「- [ ]」checkbox 格式

    模式: - [ ] xxx
    """
    return re.findall(r"^- \[ \]", content, re.MULTILINE)


def _find_step_bullets(content: str) -> List[str]:
    """
    提取「- 步驟」格式

    模式: - 步驟 xxx
    """
    return re.findall(r"^-\s+步驟", content, re.MULTILINE)
