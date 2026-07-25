"""validate 子命令 — 依 frontmatter subdomain 分派章節 schema 驗證。

目前僅實作 subdomain: data-contract 的驗證（可攜性邊界原則節 / A.1-A.6 /
B.1-B.3 / 適用判準節兩旗標非空）。非 data-contract 文件明確路由至
`/spec validate`，避免誤報。
"""

import argparse
import re
import sys

from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter


# 錨點關鍵字：容忍章節標題的合理變體（如「A.1 表/欄位語意」「A.1：xxx」等），
# 以子字串比對 header 行是否含此關鍵字，不要求完全比對整行標題。
DATA_CONTRACT_ANCHORS: list[tuple[str, str]] = [
    ("可攜性邊界原則", r"可攜性邊界原則"),
    ("A.1", r"A\.1"),
    ("A.2", r"A\.2"),
    ("A.3", r"A\.3"),
    ("A.4", r"A\.4"),
    ("A.5", r"A\.5"),
    ("A.6", r"A\.6"),
    ("B.1", r"B\.1"),
    ("B.2", r"B\.2"),
    ("B.3", r"B\.3"),
    ("適用判準", r"適用判準"),
]

# 適用判準節內兩個必填旗標的表格列關鍵字
FLAG_ROW_KEYWORDS = ["契約文件", "migration 治理"]

# 判定「旗標未填」的佔位符樣式（模板留白），非空但仍視為未填
_PLACEHOLDER_PATTERN = re.compile(r"^\{.*\}$")


def _extract_headers(text: str) -> list[str]:
    """取出所有 Markdown 標題行（# 開頭），保留原文供錨點比對。"""
    return [line for line in text.splitlines() if line.lstrip().startswith("#")]


def _find_missing_anchors(headers: list[str]) -> list[str]:
    """回傳未在任何標題行中命中的錨點名稱清單。"""
    missing = []
    for anchor_name, pattern in DATA_CONTRACT_ANCHORS:
        if not any(re.search(pattern, header) for header in headers):
            missing.append(anchor_name)
    return missing


def _extract_section(text: str, section_pattern: str) -> str | None:
    """擷取指定章節標題後、下一個同層或更高層標題前的內容。

    以「適用判準」錨點所在標題行為起點，擷取到下一個 `##` 標題（不含）
    為止；找不到起點時回傳 None。
    """
    lines = text.splitlines()
    start = None
    start_level = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("#") and re.search(section_pattern, line):
            start = i
            start_level = len(stripped) - len(stripped.lstrip("#"))
            break
    if start is None:
        return None

    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].lstrip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            if level <= start_level:
                end = j
                break
    return "\n".join(lines[start:end])


def _flag_value_filled(row_line: str) -> bool:
    """判斷「適用判準」表格列的判定欄位是否已填寫（非空、非模板佔位符）。

    row_line 格式：`| 旗標 | 判定 | 理由 |`，取第二個 cell 作為判定欄。
    """
    cells = [cell.strip() for cell in row_line.strip().strip("|").split("|")]
    if len(cells) < 2:
        return False
    judgment = cells[1].strip("*")  # 容忍 **不要** 等強調語法
    if not judgment:
        return False
    return not _PLACEHOLDER_PATTERN.match(judgment)


def _find_empty_flags(applicability_section: str | None) -> list[str]:
    """回傳「適用判準」節中判定欄仍空白/佔位符的旗標名稱清單。"""
    if applicability_section is None:
        # 章節本身缺失時，由 _find_missing_anchors 報告，這裡不重複報
        return []

    empty = []
    for keyword in FLAG_ROW_KEYWORDS:
        row_lines = [
            line
            for line in applicability_section.splitlines()
            if line.strip().startswith("|") and keyword in line
        ]
        if not row_lines:
            empty.append(keyword)
            continue
        if not any(_flag_value_filled(line) for line in row_lines):
            empty.append(keyword)
    return empty


def _validate_data_contract(text: str) -> list[str]:
    """驗證 data-contract 章節 schema，回傳缺失項清單（空清單代表通過）。"""
    headers = _extract_headers(text)
    missing = _find_missing_anchors(headers)

    applicability_section = _extract_section(text, r"適用判準")
    empty_flags = _find_empty_flags(applicability_section)
    missing.extend(f"適用判準旗標未填：{name}" for name in empty_flags)

    return missing


def execute(args: argparse.Namespace) -> None:
    """依 frontmatter subdomain 分派章節 schema 驗證。"""
    doc_id = args.doc_id
    locator = FileLocator(FileLocator.get_project_root())

    file_path = locator.resolve_file(doc_id)
    if file_path is None:
        print(f"找不到文件: {doc_id}")
        sys.exit(2)

    frontmatter = parse_frontmatter(file_path)
    if frontmatter is None:
        print(f"無法解析 frontmatter: {file_path}")
        sys.exit(2)

    subdomain = frontmatter.get("subdomain")
    if subdomain != "data-contract":
        print(f"非 data-contract 文件，請用 /spec validate（subdomain={subdomain!r}）")
        sys.exit(0)

    with open(file_path, encoding="utf-8-sig") as f:
        text = f.read()

    missing = _validate_data_contract(text)
    if not missing:
        print(f"通過: {doc_id} 符合 data-contract 章節 schema")
        sys.exit(0)

    print(f"驗證失敗: {doc_id} 缺少以下項目")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)
