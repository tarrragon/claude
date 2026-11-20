#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""error-pattern frontmatter severity 與內文風險等級分歧全量掃描。

背景：一次抽樣核對 IMP-002、DOC-001 兩例，發現 frontmatter `severity`
與內文「風險等級／嚴重度」分歧且內文較準，`readme_index.extract_row` 據此單
方面選定內文為權威（不讀 frontmatter severity）。但 `/error-pattern query`
（`.claude/skills/error-pattern/SKILL.md`）排序與顯示仍依 frontmatter
`severity`，故該分歧需獨立全量修正——本模組是該修正的可重跑掃描工具，非一
次性腳本，供後續再次覆核或迴歸驗證使用。

複用邊界：正規化與擷取邏輯（`_normalize_severity`／`_first_match`／
`_SEVERITY_PATTERNS`／`_parse_frontmatter`）直接複用 `readme_index.py` 既有
實作，不在本檔複製第二份 regex（DRY，quality-common §1.4）。本模組只新增
「frontmatter 與內文兩值並列比較＋分類統計」這一層，`readme_index.py` 原本
不需要、也不做這件事。

分類語意（`classify`）：
- both_match / both_differ：兩者皆有值，一致／不一致（一面未評估、另一面有等級屬不一致）
- unassessed：兩面皆為「未評估」（allocator 佔位檔的初始狀態），不算缺值，也不是等級
- only_frontmatter／only_body：僅一方有值
- neither：兩者皆無值（該檔未記錄風險等級，非本票分歧範圍）
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

_skill_lib = Path(__file__).resolve().parent
if str(_skill_lib) not in sys.path:
    sys.path.insert(0, str(_skill_lib))

from allocator import (  # noqa: E402  複用 SSOT
    PATTERN_ID_RE,
    UNASSESSED_BODY,
    UNASSESSED_FRONTMATTER,
    _CATEGORY_DIRS,
)
import yaml  # noqa: E402

from readme_index import (  # noqa: E402  複用既有擷取/正規化邏輯，不重寫
    PLACEHOLDER,
    _SEVERITY_PATTERNS,
    _first_match,
    _normalize_severity,
    _parse_frontmatter,
    extract_row,
)


def scan_severity(error_patterns_dir):
    """掃描各分類目錄，回傳每個 pattern 檔的 frontmatter/內文 severity 原始值與正規化值。

    回傳列表元素 schema：
    `{id, path, category, frontmatter_raw, frontmatter_norm, body_raw, body_norm}`。
    """
    error_patterns_dir = Path(error_patterns_dir)
    results = []
    for prefix, dirname in _CATEGORY_DIRS.items():
        cat_dir = error_patterns_dir / dirname
        if not cat_dir.is_dir():
            continue
        for path in sorted(cat_dir.glob("*.md")):
            match = PATTERN_ID_RE.search(path.stem)
            if not match:
                continue
            pattern_id = match.group(0).upper()
            if not pattern_id.startswith(f"{prefix}-"):
                continue
            text = path.read_text(encoding="utf-8")
            frontmatter, body = _parse_frontmatter(text)
            frontmatter_raw = (frontmatter or {}).get("severity")
            body_raw = _first_match(_SEVERITY_PATTERNS, body)
            results.append(
                {
                    "id": pattern_id,
                    "path": str(path),
                    "category": prefix,
                    "frontmatter_raw": frontmatter_raw,
                    "frontmatter_norm": _normalize_severity(frontmatter_raw),
                    "body_raw": body_raw,
                    "body_norm": _normalize_severity(body_raw),
                }
            )
    return results


_UNASSESSED_VALUES = {UNASSESSED_FRONTMATTER.lower(), UNASSESSED_BODY}
_UNASSESSED_MARK = "unassessed"


def is_unassessed(raw):
    """判斷 severity 原始值是否為「未評估」（去除括號附註後比對，大小寫不敏感）。"""
    if not raw:
        return False
    core = re.split(r"[（(\n]", str(raw), maxsplit=1)[0].strip()
    return core.lower() in _UNASSESSED_VALUES


def _side_value(raw, norm):
    """單面的比較值：未評估回傳標記，其餘回傳正規化等級（可能為 None）。"""
    return _UNASSESSED_MARK if is_unassessed(raw) else norm


def classify(row):
    """判定單筆掃描結果的分歧分類（見模組 docstring「分類語意」）。"""
    # 原始值欄位可缺（只帶正規化值的呼叫端照舊判定，不辨識未評估）
    fm = _side_value(row.get("frontmatter_raw"), row["frontmatter_norm"])
    body = _side_value(row.get("body_raw"), row["body_norm"])
    if fm == body == _UNASSESSED_MARK:
        return "unassessed"
    if fm is not None and body is not None:
        return "both_match" if fm == body else "both_differ"
    if fm is not None:
        return "only_frontmatter"
    if body is not None:
        return "only_body"
    return "neither"


def summarize(results):
    """回傳各分類的檔案數統計（`Counter`，key 見 `classify` 回傳值）。"""
    return Counter(classify(row) for row in results)


def discrepancies(results):
    """回傳 `both_differ` 分類的列表（frontmatter 與內文皆有值但不一致者）。"""
    return [row for row in results if classify(row) == "both_differ"]


_REPORT_ORDER = (
    "both_match", "unassessed", "both_differ", "only_frontmatter", "only_body", "neither",
)
_REPORT_LABELS = {
    "both_match": "兩者皆有值且一致",
    "unassessed": "兩者皆為未評估",
    "both_differ": "兩者皆有值但分歧",
    "only_frontmatter": "僅 frontmatter 有值",
    "only_body": "僅內文有值",
    "neither": "兩者皆無值",
}


def format_report(results):
    """將掃描結果格式化為人類可讀的統計＋分歧清單報告字串。"""
    stats = summarize(results)
    lines = [f"共掃描 {len(results)} 檔"]
    for key in _REPORT_ORDER:
        lines.append(f"  {_REPORT_LABELS[key]}（{key}）: {stats.get(key, 0)}")

    diffs = discrepancies(results)
    if diffs:
        lines.append(f"\n分歧項（{len(diffs)} 檔）：")
        for row in diffs:
            lines.append(
                f"  [{row['id']}] frontmatter={row['frontmatter_raw']!r}"
                f"(正規化: {row['frontmatter_norm']}) "
                f"內文={row['body_raw']!r}(正規化: {row['body_norm']}) "
                f"{row['path']}"
            )
    return "\n".join(lines)


# 鏡射寫入 frontmatter 的等級值：沿用語料多數的英文寫法
_SEVERITY_TO_FRONTMATTER = {"高": "high", "中": "medium", "低": "low"}


def _yaml_line(key, value):
    """單一 key 的 YAML 行（值含冒號、引號等由 safe_dump 處理引號）。"""
    return yaml.safe_dump({key: value}, allow_unicode=True, sort_keys=False, width=10_000)


def _mirrored_text(path, row):
    """回傳把內文等級鏡射進 frontmatter 後的全文；內文部分逐字不變。

    - 無 frontmatter：前置新建 id／title／severity（title 取不到時省略）
    - 已有 frontmatter：只在結尾 `---` 前插入 severity 一行
    """
    text = Path(path).read_text(encoding="utf-8")
    severity_line = _yaml_line("severity", _SEVERITY_TO_FRONTMATTER[row["body_norm"]])
    if text.startswith("---"):
        end = text.find("\n---", 3)
        return text[: end + 1] + severity_line + text[end + 1:]
    index_row = extract_row(Path(path), row["id"]) or {}
    block = _yaml_line("id", row["id"])
    title = index_row.get("title")
    if title and title != PLACEHOLDER:
        block += _yaml_line("title", title)
    block += severity_line
    return f"---\n{block}---\n\n{text}"


def mirror_only_body(error_patterns_dir, write=False):
    """把 only_body 類檔案的內文等級鏡射進 frontmatter `severity`。

    回傳會變更（`write=True` 時已變更）的檔案路徑列表。其他分類不動。
    """
    changed = []
    for row in scan_severity(error_patterns_dir):
        if classify(row) != "only_body":
            continue
        new_text = _mirrored_text(row["path"], row)
        if write:
            Path(row["path"]).write_text(new_text, encoding="utf-8")
        changed.append(row["path"])
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="severity_audit",
        description="error-pattern frontmatter severity 與內文風險等級分歧掃描",
    )
    parser.add_argument("--claude-dir", default=".claude", help="claude 目錄路徑（預設 .claude）")
    parser.add_argument("--category", help="僅顯示指定分類前綴（如 IMP/PC/ARCH/...）")
    parser.add_argument(
        "--mirror-only-body",
        action="store_true",
        help="把 only_body 類的內文風險等級鏡射進 frontmatter severity（預設只列出，加 --write 才寫入）",
    )
    parser.add_argument("--write", action="store_true", help="與 --mirror-only-body 併用時實際寫檔")
    args = parser.parse_args(argv)

    error_patterns_dir = Path(args.claude_dir) / "error-patterns"
    if args.mirror_only_body:
        changed = mirror_only_body(error_patterns_dir, write=args.write)
        verb = "已寫入" if args.write else "將寫入（dry-run）"
        print(f"only_body 鏡射{verb} {len(changed)} 檔")
        for path in changed:
            print(f"  {path}")
        return 0
    results = scan_severity(error_patterns_dir)
    if args.category:
        results = [row for row in results if row["category"] == args.category]

    print(format_report(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
