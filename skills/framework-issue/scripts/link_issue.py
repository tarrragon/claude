#!/usr/bin/env python3
"""framework-issue link：把 canonical_issue stamp 寫入 error-pattern 的「## 分類資訊」表格。

用途：error-pattern 升格為 canonical 時，於框架 repo 建立 / 找到對應 framework
issue 後，以本命令把該 issue ref 寫回 error-pattern，作為 canonical 錨點（軸 B
link + provenance）。

落點設計：現行 error-pattern metadata 以「## 分類資訊」表格承載（非 YAML
frontmatter），故 canonical_issue 作該表格新增一列 `| canonical_issue | <ref> |`，
與既有結構一致；重複 link 為「更新該列」而非新增重複列。

降級：沿用 gh_common.preflight()，gh 不可用 / 未登入時優雅降級（exit 3），不
真打 GitHub API（issue ref 由呼叫端提供，link 本身僅寫本地檔）。
"""

import argparse
import re
import sys
from pathlib import Path

from gh_common import emit_degraded, preflight

# error-pattern 根目錄（相對本檔位置，避免依賴 cwd）
ERROR_PATTERN_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent / "error-patterns"
)

# 分類資訊表格列：`| canonical_issue | <ref> |`
CANONICAL_ROW = "| canonical_issue | {ref} |"
# 偵測既有 canonical_issue 列（用於更新而非重複新增）
CANONICAL_ROW_PATTERN = re.compile(
    r"^\|\s*canonical_issue\s*\|.*\|\s*$", re.MULTILINE
)
# 分類資訊表格的最後一個資料列（用於定位插入點）；表頭分隔線之後的列
TABLE_HEADER_SEP = re.compile(r"^\|\s*-+\s*\|\s*-+\s*\|\s*$", re.MULTILINE)


def resolve_pattern_path(pattern_ref: str) -> Path:
    """將 error-pattern id 或路徑解析為實際檔案路徑。

    pattern_ref 可為：
    - 既有檔案路徑（含 .md）
    - error-pattern id（如 PC-020），於 error-patterns/ 下遞迴尋找
      `<id>-*.md`。
    回傳解析後的 Path；找不到時回傳「最可能的」候選讓上層報錯。
    """
    candidate = Path(pattern_ref)
    if candidate.suffix == ".md" and candidate.exists():
        return candidate

    # 以 id 前綴搜尋（如 PC-020 → PC-020-*.md）
    matches = sorted(ERROR_PATTERN_ROOT.rglob(f"{pattern_ref}-*.md"))
    if matches:
        return matches[0]
    # 退而求其次：允許傳入完整檔名（不含目錄）
    by_name = sorted(ERROR_PATTERN_ROOT.rglob(pattern_ref))
    if by_name:
        return by_name[0]
    return candidate


def find_classification_table_end(content: str) -> int:
    """回傳「## 分類資訊」表格最後一列之後的插入位置（字元索引）。

    定位邏輯：找到分類資訊表頭分隔線（`|---|---|`）後，連續的表格列直到
    第一個非表格列為止；回傳該段最後一列結尾的索引。找不到表格回傳 -1。
    """
    section_match = re.search(r"^##\s*分類資訊\s*$", content, re.MULTILINE)
    if not section_match:
        return -1
    sep_match = TABLE_HEADER_SEP.search(content, section_match.end())
    if not sep_match:
        return -1

    # 從分隔線後逐列前進，直到遇到非 `|` 開頭的行
    pos = sep_match.end()
    last_row_end = pos
    for line_match in re.finditer(r"^.*$", content[pos:], re.MULTILINE):
        line = line_match.group()
        abs_end = pos + line_match.end()
        if line.startswith("|"):
            last_row_end = abs_end
        elif line.strip() == "":
            continue
        else:
            break
    return last_row_end


def stamp_canonical_issue(content: str, issue_ref: str) -> str:
    """把 canonical_issue 列寫入分類資訊表格；既有則更新，否則新增。

    回傳更新後的內容；分類資訊表格不存在時拋 ValueError 由上層轉錯誤訊息。
    """
    new_row = CANONICAL_ROW.format(ref=issue_ref)

    if CANONICAL_ROW_PATTERN.search(content):
        # 重複 link：更新既有列（去重，非新增）
        return CANONICAL_ROW_PATTERN.sub(new_row, content, count=1)

    insert_at = find_classification_table_end(content)
    if insert_at < 0:
        raise ValueError("找不到「## 分類資訊」表格，無法寫入 canonical_issue")
    return content[:insert_at] + "\n" + new_row + content[insert_at:]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="framework-issue link",
        description="把 canonical_issue stamp 寫入 error-pattern 的分類資訊表格",
    )
    parser.add_argument(
        "pattern",
        help="error-pattern id（如 PC-020）或 .md 檔案路徑",
    )
    parser.add_argument(
        "issue_ref",
        help="framework issue ref（如 tarrragon/claude#42）",
    )
    parsed = parser.parse_args(argv)

    gate = preflight()
    if gate != 0:
        return gate

    path = resolve_pattern_path(parsed.pattern)
    if not path.exists():
        return emit_degraded(
            f"找不到 error-pattern：{parsed.pattern}",
            "確認 id 或路徑正確（error-patterns/ 下 <id>-*.md）",
        )

    content = path.read_text(encoding="utf-8")
    try:
        updated = stamp_canonical_issue(content, parsed.issue_ref)
    except ValueError as exc:
        return emit_degraded(
            str(exc),
            "確認該檔含標準「## 分類資訊」表格後重試",
        )

    path.write_text(updated, encoding="utf-8")
    sys.stderr.write(
        f"[framework-issue] 已 link canonical_issue={parsed.issue_ref} "
        f"→ {path.name}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
