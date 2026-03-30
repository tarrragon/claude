"""解析 Markdown 文件的 YAML frontmatter。"""

from pathlib import Path

import yaml


FRONTMATTER_DELIMITER = "---"


def parse_frontmatter(file_path: str) -> dict | None:
    """解析 Markdown 文件的 YAML frontmatter，回傳 dict 或 None。

    規則：
    - 檔案第一行必須是 '---'
    - 找到第二個 '---' 作為 frontmatter 結尾
    - 用 yaml.safe_load 解析中間內容
    - 檔案不存在、無 frontmatter、解析失敗時回傳 None
    """
    path = Path(file_path)
    if not path.is_file():
        return None

    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None

    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        return None

    end_index = _find_closing_delimiter(lines)
    if end_index is None:
        return None

    yaml_content = "\n".join(lines[1:end_index])
    return _safe_parse_yaml(yaml_content)


def _find_closing_delimiter(lines: list[str]) -> int | None:
    """找到 frontmatter 結尾的 '---' 行索引（從第 2 行開始搜尋）。"""
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIMITER:
            return i
    return None


def _safe_parse_yaml(content: str) -> dict | None:
    """安全解析 YAML 字串，失敗時回傳 None。"""
    try:
        result = yaml.safe_load(content)
    except yaml.YAMLError:
        return None

    if not isinstance(result, dict):
        return None
    return result
