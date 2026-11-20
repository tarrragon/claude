"""allocator 佔位檔的 severity 雙面欄位與「未評估」值辨識測試。

背景：`allocate_and_reserve_pattern_id` 建立的佔位檔原本不含 frontmatter
`severity` 與內文「風險等級」，走預設路徑就產出 severity_audit 判為 `neither`
的檔，違反 SKILL「frontmatter 與內文必須一致」的不變式。修正後佔位檔兩面都寫入
明確的「未評估」值，severity_audit 另立 `unassessed` 分類，不把它當成任何等級。

驗證範圍：
- 佔位檔兩面皆為未評估，分類為 unassessed（不落在 only_body／only_frontmatter／neither）
- 正向對照：舊版佔位檔文字（無 severity 兩面欄位）分類為 neither
- 未評估值不正規化成高／中／低（不進入等級排序，README sync 仍視為缺值）
- 一面未評估、一面有等級：判為 both_differ（漂移）
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

from allocator import allocate_and_reserve_pattern_id  # noqa: E402
from readme_index import _normalize_severity  # noqa: E402
from severity_audit import (  # noqa: E402
    UNASSESSED_BODY,
    UNASSESSED_FRONTMATTER,
    classify,
    format_report,
    is_unassessed,
    scan_severity,
    summarize,
)

_VIOLATION_CLASSES = {"only_body", "only_frontmatter", "neither"}

# 修正前 allocator 寫出的佔位檔全文（正向對照用；不可隨實作變動）
_OLD_STUB = (
    "---\n"
    "id: IMP-V1-001\n"
    "title: (reserved - 內容待補)\n"
    "status: reserved\n"
    "reserved_by: unknown\n"
    "reserved_at: 2026-11-20T00:00:00+00:00\n"
    "---\n\n"
    "# IMP-V1-001: (reserved - 內容待補)\n\n"
    "此檔案由 allocate_and_reserve_pattern_id 建立，用於原子化保留編號，"
    "尚未填入實際內容。\n"
)


def _scan_one(claude_dir):
    rows = scan_severity(Path(claude_dir) / "error-patterns")
    assert len(rows) == 1
    return rows[0]


def test_stub_has_unassessed_on_both_sides(tmp_path):
    claude_dir = tmp_path / ".claude"
    stub = allocate_and_reserve_pattern_id("IMP", claude_dir, "V1")
    text = stub.read_text(encoding="utf-8")
    assert f"severity: {UNASSESSED_FRONTMATTER}\n" in text
    assert f"**風險等級**: {UNASSESSED_BODY}" in text


def test_stub_classified_unassessed_not_violation(tmp_path):
    claude_dir = tmp_path / ".claude"
    allocate_and_reserve_pattern_id("IMP", claude_dir, "V1")
    category = classify(_scan_one(claude_dir))
    assert category == "unassessed"
    assert category not in _VIOLATION_CLASSES


def test_old_stub_is_violation(tmp_path):
    """正向對照：修正前的佔位檔必須被判為違規分類。"""
    cat_dir = tmp_path / ".claude" / "error-patterns" / "implementation"
    cat_dir.mkdir(parents=True)
    (cat_dir / "IMP-V1-001.md").write_text(_OLD_STUB, encoding="utf-8")
    assert classify(_scan_one(tmp_path / ".claude")) in _VIOLATION_CLASSES


def test_unassessed_not_ranked_as_level():
    for raw in (UNASSESSED_FRONTMATTER, UNASSESSED_BODY):
        assert is_unassessed(raw)
        assert _normalize_severity(raw) is None


def test_is_unassessed_rejects_levels_and_none():
    for raw in ("高", "low", "medium", None, ""):
        assert not is_unassessed(raw)


def test_half_unassessed_is_drift(tmp_path):
    cat_dir = tmp_path / ".claude" / "error-patterns" / "implementation"
    cat_dir.mkdir(parents=True)
    (cat_dir / "IMP-V1-001.md").write_text(
        f"---\nid: IMP-V1-001\nseverity: {UNASSESSED_FRONTMATTER}\n---\n"
        "# 標題\n\n## 基本資訊\n\n- **風險等級**: 高\n",
        encoding="utf-8",
    )
    assert classify(_scan_one(tmp_path / ".claude")) == "both_differ"


def test_report_lists_unassessed_count(tmp_path):
    claude_dir = tmp_path / ".claude"
    allocate_and_reserve_pattern_id("IMP", claude_dir, "V1")
    rows = scan_severity(claude_dir / "error-patterns")
    assert summarize(rows)["unassessed"] == 1
    assert "unassessed" in format_report(rows)
