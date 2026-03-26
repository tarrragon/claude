#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Deletion Residual Reference Check Hook

PostToolUse:Edit 觸發。偵測刪除操作後，檢查同檔案中是否有殘留引用。

Hook Type: PostToolUse (Edit)
Source: IMP-042 — 簡化/刪除操作後殘留引用未同步清理

Exit Codes:
    0 - 無問題或不在偵測範圍
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely

# 偵測閾值：old_string 比 new_string 長至少這麼多字元才視為「刪除」
DELETION_THRESHOLD_CHARS = 50

# 忽略的通用詞（不作為殘留引用搜尋目標）
STOPWORDS = {
    "的", "是", "在", "和", "或", "與", "了", "有", "不", "為",
    "以", "及", "等", "到", "從", "中", "上", "下", "也", "但",
    "都", "要", "會", "可", "能", "應", "該", "被", "將", "已",
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "must",
    "and", "or", "but", "if", "then", "else", "when", "where",
    "that", "this", "these", "those", "it", "its", "to", "of",
    "in", "on", "at", "by", "for", "with", "from", "as", "into",
    "not", "no", "so", "than", "too", "very", "just", "about",
}

# 只檢查這些副檔名
SUPPORTED_EXTENSIONS = {".md", ".yaml", ".yml", ".json", ".toml"}


def extract_key_terms(deleted_text: str, remaining_text: str) -> list[str]:
    """從被刪除的文字中提取關鍵詞。

    需求：提取在 deleted_text 中出現但不在 remaining_text 保留段落的標題、
    專有名詞和數量詞，用於搜尋殘留引用。

    策略：
    1. Markdown 標題（## 開頭的行）
    2. 含數字的片語（如「7 個維度」）
    3. 中文專有名詞（連續中文 >= 4 字元）
    4. 英文專有名詞（PascalCase 或全大寫）
    """
    terms = []

    # 1. Markdown 標題
    for match in re.finditer(r'^#{1,6}\s+(.+)$', deleted_text, re.MULTILINE):
        title = match.group(1).strip()
        if len(title) >= 2:
            terms.append(title)

    # 2. 數量詞片語（如「7 個維度」「3 個」）
    for match in re.finditer(r'\d+\s*[個項條份層步種類次張筆]\s*[\u4e00-\u9fff]+', deleted_text):
        term = match.group(0).strip()
        if term not in remaining_text.split('\n')[0]:  # 避免 frontmatter 中的數字
            terms.append(term)

    # 3. 中文專有名詞（4+ 字元連續中文）
    for match in re.finditer(r'[\u4e00-\u9fff]{4,}', deleted_text):
        term = match.group(0)
        # 過濾：只保留在 deleted_text 中出現但可能在其他地方被引用的
        if term not in STOPWORDS and len(term) <= 20:
            terms.append(term)

    # 4. 英文 PascalCase 或全大寫名詞
    for match in re.finditer(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', deleted_text):
        terms.append(match.group(0))
    for match in re.finditer(r'\b[A-Z_]{3,}\b', deleted_text):
        term = match.group(0)
        if term not in {"TODO", "NOTE", "WARNING", "FIXME", "HACK", "XXX"}:
            terms.append(term)

    # 去重，保持順序
    seen = set()
    unique_terms = []
    for t in terms:
        if t not in seen and len(t) >= 2:
            seen.add(t)
            unique_terms.append(t)

    return unique_terms


def find_residual_references(
    file_content: str,
    deleted_text: str,
    terms: list[str],
) -> list[dict]:
    """在檔案內容中搜尋殘留引用。

    需求：逐行搜尋 terms 在 file_content 中的出現，
    排除被刪除段落本身（已不存在），只報告仍然存在的引用。

    Returns:
        list of {"term": str, "line_num": int, "line": str}
    """
    residuals = []
    lines = file_content.split('\n')

    for term in terms:
        for i, line in enumerate(lines, 1):
            if term in line:
                residuals.append({
                    "term": term,
                    "line_num": i,
                    "line": line.strip()[:100],
                })

    return residuals


def main() -> int:
    logger = setup_hook_logging("deletion-residual-reference")

    # 讀取 stdin
    try:
        input_text = sys.stdin.read().strip()
        if not input_text:
            return 0
        input_data = json.loads(input_text)
    except (json.JSONDecodeError, Exception):
        return 0

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    # 只檢查支援的檔案類型
    if not file_path or Path(file_path).suffix not in SUPPORTED_EXTENSIONS:
        return 0

    # 偵測刪除：old_string 比 new_string 長至少 DELETION_THRESHOLD_CHARS
    deleted_chars = len(old_string) - len(new_string)
    if deleted_chars < DELETION_THRESHOLD_CHARS:
        return 0

    # 計算被刪除的文字
    deleted_text = old_string
    if new_string:
        # new_string 不為空時，deleted_text 是 old 中有但 new 中沒有的部分
        # 簡化處理：用 old_string 整體提取關鍵詞，但排除 new_string 中仍存在的詞
        pass

    # 提取關鍵詞
    terms = extract_key_terms(deleted_text, new_string)
    if not terms:
        logger.debug("No key terms extracted from deleted content")
        return 0

    # 過濾：排除在 new_string 中仍存在的詞
    terms = [t for t in terms if t not in new_string]
    if not terms:
        return 0

    # 讀取檔案當前內容（Edit 已完成，檔案已更新）
    try:
        current_content = Path(file_path).read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Cannot read file {file_path}: {e}")
        return 0

    # 搜尋殘留引用
    residuals = find_residual_references(current_content, deleted_text, terms)

    if not residuals:
        return 0

    # 去重：同一 term 只報告一次，且排除被更長 term 包含的短 term
    seen_terms = set()
    unique_residuals = []
    all_terms = [r["term"] for r in residuals]
    for r in residuals:
        term = r["term"]
        if term in seen_terms:
            continue
        # 排除被更長 term 完全包含的短 term
        is_substring = any(
            term != other and term in other
            for other in all_terms
        )
        if is_substring:
            continue
        seen_terms.add(term)
        unique_residuals.append(r)

    if not unique_residuals:
        return 0

    # 輸出 WARNING
    print("=" * 60, file=sys.stderr)
    print("[WARNING] IMP-042 殘留引用檢查", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"檔案: {file_path}", file=sys.stderr)
    print(f"偵測到刪除操作（移除 {deleted_chars} 字元）", file=sys.stderr)
    print(f"以下關鍵詞在檔案中仍有引用：\n", file=sys.stderr)

    for r in unique_residuals[:10]:  # 最多顯示 10 個
        print(f"  [{r['term']}] 第 {r['line_num']} 行: {r['line']}", file=sys.stderr)

    print(f"\n建議：檢查上述引用是否需要同步更新或移除。", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "deletion-residual-reference"))
