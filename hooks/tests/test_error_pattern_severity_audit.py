"""error-pattern frontmatter severity 與內文風險等級分歧掃描測試（0.2.1-W3-106）。

severity_audit 程式碼自包含於 .claude/skills/error-pattern/lib/severity_audit.py；
測試暫借 hooks pytest env 執行（比照 test_error_pattern_readme_index.py 慣例）。

驗證範圍：
- scan_severity：正確擷取 frontmatter `severity` 與內文「風險等級／嚴重度」，
  兩者皆正規化後才比較（避免中英文寫法差異被誤判為分歧）
- classify：五種分類（both_match／both_differ／only_frontmatter／only_body／
  neither）判定正確，涵蓋邊界（僅一方有值、皆無值）
- summarize／discrepancies：統計與分歧清單萃取邏輯正確
- format_report：輸出含總數與分歧項清單
"""

import sys
from pathlib import Path

_skill_lib = (
    Path(__file__).resolve().parent.parent.parent
    / "skills"
    / "error-pattern"
    / "lib"
)
if str(_skill_lib) not in sys.path:
    sys.path.insert(0, str(_skill_lib))

from severity_audit import (  # noqa: E402
    classify,
    discrepancies,
    format_report,
    scan_severity,
    summarize,
)


def _write_pattern(cat_dir, filename, frontmatter_severity, body_severity_line):
    """在分類目錄下寫入一個最小 pattern 檔，frontmatter/body severity 皆可為 None（省略該欄位）。"""
    fm_block = "---\nid: " + filename.split("-", 2)[0] + "-" + filename.split("-", 2)[1] + "\n"
    if frontmatter_severity is not None:
        fm_block += f"severity: {frontmatter_severity}\n"
    fm_block += "---\n"
    body = "# 標題\n\n## 基本資訊\n\n"
    if body_severity_line is not None:
        body += f"- **風險等級**: {body_severity_line}\n"
    (cat_dir / filename).write_text(fm_block + body, encoding="utf-8")


# --- scan_severity ---


def test_scan_severity_extracts_and_normalizes_both_sides(tmp_path):
    """frontmatter 與內文皆有值時，兩者各自正規化後回傳（中英文寫法統一為單字）。"""
    error_patterns_dir = tmp_path / "error-patterns"
    cat_dir = error_patterns_dir / "implementation"
    cat_dir.mkdir(parents=True)
    _write_pattern(cat_dir, "IMP-001-foo.md", "medium", "低")

    results = scan_severity(error_patterns_dir)
    assert len(results) == 1
    row = results[0]
    assert row["id"] == "IMP-001"
    assert row["frontmatter_raw"] == "medium"
    assert row["frontmatter_norm"] == "中"
    assert row["body_raw"] == "低"
    assert row["body_norm"] == "低"


def test_scan_severity_skips_non_pattern_files(tmp_path):
    """非 pattern 命名檔案（不含 PATTERN_ID_RE 可辨識 ID）不列入掃描結果。"""
    error_patterns_dir = tmp_path / "error-patterns"
    cat_dir = error_patterns_dir / "implementation"
    cat_dir.mkdir(parents=True)
    (cat_dir / "README.md").write_text("非 pattern 檔案", encoding="utf-8")

    results = scan_severity(error_patterns_dir)
    assert results == []


def test_scan_severity_skips_missing_category_dir(tmp_path):
    """分類目錄不存在時略過，不拋例外（全量掃描不要求每個分類目錄都存在）。"""
    error_patterns_dir = tmp_path / "error-patterns"
    error_patterns_dir.mkdir()
    results = scan_severity(error_patterns_dir)
    assert results == []


# --- classify ---


def test_classify_both_match_when_normalized_values_equal():
    row = {"frontmatter_norm": "中", "body_norm": "中"}
    assert classify(row) == "both_match"


def test_classify_both_differ_when_normalized_values_differ():
    row = {"frontmatter_norm": "中", "body_norm": "高"}
    assert classify(row) == "both_differ"


def test_classify_only_frontmatter_when_body_missing():
    row = {"frontmatter_norm": "高", "body_norm": None}
    assert classify(row) == "only_frontmatter"


def test_classify_only_body_when_frontmatter_missing():
    row = {"frontmatter_norm": None, "body_norm": "低"}
    assert classify(row) == "only_body"


def test_classify_neither_when_both_missing():
    row = {"frontmatter_norm": None, "body_norm": None}
    assert classify(row) == "neither"


# --- summarize / discrepancies ---


def test_summarize_counts_each_classification(tmp_path):
    error_patterns_dir = tmp_path / "error-patterns"
    cat_dir = error_patterns_dir / "implementation"
    cat_dir.mkdir(parents=True)
    _write_pattern(cat_dir, "IMP-001-a.md", "medium", "中")  # both_match
    _write_pattern(cat_dir, "IMP-002-b.md", "medium", "高")  # both_differ
    _write_pattern(cat_dir, "IMP-003-c.md", "high", None)  # only_frontmatter
    _write_pattern(cat_dir, "IMP-004-d.md", None, "低")  # only_body
    _write_pattern(cat_dir, "IMP-005-e.md", None, None)  # neither

    results = scan_severity(error_patterns_dir)
    stats = summarize(results)
    assert stats["both_match"] == 1
    assert stats["both_differ"] == 1
    assert stats["only_frontmatter"] == 1
    assert stats["only_body"] == 1
    assert stats["neither"] == 1


def test_discrepancies_returns_only_both_differ_rows(tmp_path):
    error_patterns_dir = tmp_path / "error-patterns"
    cat_dir = error_patterns_dir / "implementation"
    cat_dir.mkdir(parents=True)
    _write_pattern(cat_dir, "IMP-001-a.md", "medium", "中")  # both_match
    _write_pattern(cat_dir, "IMP-002-b.md", "medium", "高")  # both_differ

    results = scan_severity(error_patterns_dir)
    diffs = discrepancies(results)
    assert len(diffs) == 1
    assert diffs[0]["id"] == "IMP-002"


# --- format_report ---


def test_format_report_includes_total_and_discrepancy_list(tmp_path):
    error_patterns_dir = tmp_path / "error-patterns"
    cat_dir = error_patterns_dir / "implementation"
    cat_dir.mkdir(parents=True)
    _write_pattern(cat_dir, "IMP-001-a.md", "medium", "高")  # both_differ

    results = scan_severity(error_patterns_dir)
    report = format_report(results)
    assert "共掃描 1 檔" in report
    assert "分歧項（1 檔）" in report
    assert "IMP-001" in report
