"""error-pattern README 索引保守 upsert 測試（0.2.1-W3-099，0.2.1-W3-105 更正）。

readme_index 程式碼自包含於 .claude/skills/error-pattern/lib/readme_index.py；
測試暫借 hooks pytest env 執行（比照 test_error_pattern_allocator.py 慣例）。

驗證範圍：
- extract_row：標題 frontmatter 優先／H1 fallback；風險等級不讀 frontmatter，
  一律取內文「基本資訊」區塊或佔位符（0.2.1-W3-105：frontmatter severity
  與內文常態性分歧且內文較準，故不信任）
- sync_readme_text／merge_category_table：只動「現有模式」章節資料列，表格
  外內容原樣保留；既有列逐字保留不重新生成（即使掃描結果不同）、新檔案
  的列附加於尾端、已刪除檔案的列被捨棄
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

from readme_index import (  # noqa: E402
    extract_row,
    merge_category_table,
    scan_category_rows,
    sync_readme_text,
)

# --- extract_row ---


def test_frontmatter_title_takes_priority_but_severity_ignores_frontmatter(tmp_path):
    """title 取 frontmatter 值；severity 刻意不讀 frontmatter，一律取內文（0.2.1-W3-105）。"""
    path = tmp_path / "IMP-001-foo.md"
    path.write_text(
        "---\n"
        "id: IMP-001\n"
        "title: frontmatter 標題\n"
        "severity: high\n"
        "---\n"
        "# IMP-001: 內文標題（應被 frontmatter 蓋過）\n"
        "\n"
        "## 基本資訊\n"
        "\n"
        "- **風險等級**: 低\n"
        "- **來源版本**: v0.1.0\n",
        encoding="utf-8",
    )
    row = extract_row(path, "IMP-001")
    assert row["title"] == "frontmatter 標題"
    # frontmatter 寫 high，但內文「風險等級」寫低——取內文值，不取 frontmatter。
    assert row["severity"] == "低"
    # 來源版本無 frontmatter 對應欄位，一律落到內文擷取。
    assert row["source_version"] == "v0.1.0"


def test_frontmatter_severity_without_body_block_falls_back_to_placeholder(tmp_path):
    """frontmatter 有 severity 但內文無對應「風險等級」區塊時，寫佔位符而非取用 frontmatter。"""
    path = tmp_path / "IMP-002-bar.md"
    path.write_text(
        "---\nid: IMP-002\ntitle: 標題\nseverity: medium\n---\n# IMP-002: 標題\n\n純文字內容。\n",
        encoding="utf-8",
    )
    row = extract_row(path, "IMP-002")
    assert row["title"] == "標題"
    assert row["severity"] == "—"


def test_no_frontmatter_falls_back_to_h1_and_body_block(tmp_path):
    """無 frontmatter 時，標題取 H1（去除 ID 前綴），風險/版本取「基本資訊」區塊。"""
    path = tmp_path / "DOC-002-bar.md"
    path.write_text(
        "# DOC-002: 衛星文件引用不存在\n"
        "\n"
        "## 基本資訊\n"
        "\n"
        "- **Pattern ID**: DOC-002\n"
        "- **風險等級**: 中\n"
        "- **來源版本**: v0.28.0\n",
        encoding="utf-8",
    )
    row = extract_row(path, "DOC-002")
    assert row["title"] == "衛星文件引用不存在"
    assert row["severity"] == "中"
    assert row["source_version"] == "v0.28.0"


def test_table_style_body_block_also_recognized(tmp_path):
    """「基本資訊」區塊亦有表格寫法（`| 風險等級 | 值 |`），須同樣可解析。"""
    path = tmp_path / "PC-003-baz.md"
    path.write_text(
        "# PC-003: 表格寫法\n"
        "\n"
        "| 項目 | 值 |\n"
        "|------|------|\n"
        "| 風險等級 | 高 |\n"
        "| 來源版本 | v0.2.1 |\n",
        encoding="utf-8",
    )
    row = extract_row(path, "PC-003")
    assert row["severity"] == "高"
    assert row["source_version"] == "v0.2.1"


def test_missing_fields_use_placeholder_not_guessed(tmp_path):
    """frontmatter、H1、基本資訊區塊皆缺對應欄位時寫佔位符，不臆造。"""
    path = tmp_path / "ARCH-999-qux.md"
    path.write_text(
        "純文字內容，沒有 H1 標題，也沒有風險等級或來源版本欄位。\n",
        encoding="utf-8",
    )
    row = extract_row(path, "ARCH-999")
    assert row["title"] == "—"
    assert row["severity"] == "—"
    assert row["source_version"] == "—"


def test_h1_present_but_metadata_fields_missing(tmp_path):
    """有 H1 可取標題，但風險等級／來源版本缺席時各自獨立走佔位符。"""
    path = tmp_path / "IMP-046-lock.md"
    path.write_text(
        "# IMP-046: git index.lock 競爭條件導致 commit 失敗\n"
        "\n"
        "## 錯誤摘要\n"
        "\n"
        "沒有風險等級或來源版本欄位的自由文字說明。\n",
        encoding="utf-8",
    )
    row = extract_row(path, "IMP-046")
    assert row["title"] == "git index.lock 競爭條件導致 commit 失敗"
    assert row["severity"] == "—"
    assert row["source_version"] == "—"


# --- scan_category_rows ---


def _write_pattern_file(claude_dir, category_dir, filename, content):
    d = claude_dir / "error-patterns" / category_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(content, encoding="utf-8")


def test_scan_category_rows_groups_by_known_prefix(tmp_path):
    claude_dir = tmp_path / ".claude"
    _write_pattern_file(
        claude_dir,
        "implementation",
        "IMP-001-foo.md",
        "---\nid: IMP-001\ntitle: 標題一\nseverity: low\n---\n"
        "# IMP-001: 標題一\n\n- **風險等級**: 低\n",
    )
    _write_pattern_file(
        claude_dir,
        "test",
        "TEST-001-bar.md",
        "---\nid: TEST-001\ntitle: 標題二\nseverity: high\n---\n"
        "# TEST-001: 標題二\n\n- **風險等級**: 高\n",
    )
    rows = scan_category_rows(claude_dir / "error-patterns")
    assert [r["id"] for r in rows["IMP"]] == ["IMP-001"]
    assert [r["id"] for r in rows["TEST"]] == ["TEST-001"]
    assert rows["IMP"][0]["severity"] == "低"
    assert rows["TEST"][0]["severity"] == "高"


# --- sync_readme_text ---

_README_TEMPLATE = """# Error Patterns 錯誤模式歸檔系統

## 命名規範

| 分類 | 前綴 |
|------|------|
| 實作 | IMP |

## 現有模式

### 實作 (IMP)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| IMP-001 | 舊標題一 | 低 | v0.1.0 |
| IMP-002 | 舊標題二 | 中 | v0.1.1 |

### 文件 (DOC)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| DOC-001 | 文件標題 | 高 | v0.2.0 |

## 查詢方法

```bash
grep -r "關鍵字" .claude/error-patterns/
```
"""


def test_sync_preserves_content_outside_category_tables():
    """「現有模式」以外的章節（命名規範表格、查詢方法程式碼區塊）逐字不動。"""
    category_rows = {
        "IMP": [
            {"id": "IMP-001", "title": "舊標題一", "severity": "低", "source_version": "v0.1.0"}
        ],
        "DOC": [
            {"id": "DOC-001", "title": "文件標題", "severity": "高", "source_version": "v0.2.0"}
        ],
    }
    updated = sync_readme_text(_README_TEMPLATE, category_rows)

    assert "## 命名規範" in updated
    assert "| 實作 | IMP |" in updated
    assert '```bash\ngrep -r "關鍵字" .claude/error-patterns/\n```' in updated


def test_sync_preserves_existing_row_verbatim_even_if_scan_differs():
    """既有列的 ID 若在掃描結果中仍存在，逐字保留原內容，不以掃描結果覆寫（保守 upsert 核心約束）。"""
    category_rows = {
        "IMP": [
            # 掃描結果與現行索引內容不同（標題/風險/版本皆異），但檔案仍存在，
            # 依保守 upsert 語意既有列不得被覆寫。
            {
                "id": "IMP-001",
                "title": "掃描出的新標題",
                "severity": "高",
                "source_version": "v0.3.0",
            },
            {"id": "IMP-002", "title": "掃描出的標題二", "severity": "高", "source_version": "—"},
        ],
        "DOC": [
            {"id": "DOC-001", "title": "文件標題", "severity": "高", "source_version": "v0.2.0"}
        ],
    }
    updated = sync_readme_text(_README_TEMPLATE, category_rows)

    # 既有列原樣保留，掃描結果的差異值完全不出現。
    assert "| IMP-001 | 舊標題一 | 低 | v0.1.0 |" in updated
    assert "| IMP-002 | 舊標題二 | 中 | v0.1.1 |" in updated
    assert "掃描出的新標題" not in updated
    assert "掃描出的標題二" not in updated


def test_sync_appends_new_row_and_drops_deleted_row():
    """新檔案的列附加於分類表格尾端；對應檔案已刪除的既有列從表格移除。"""
    category_rows = {
        "IMP": [
            # IMP-002 對應檔案已刪除（不在掃描結果中）；IMP-003 為新增檔案。
            {"id": "IMP-001", "title": "舊標題一", "severity": "低", "source_version": "v0.1.0"},
            {"id": "IMP-003", "title": "新增檔案", "severity": "中", "source_version": "v0.4.0"},
        ],
        "DOC": [
            {"id": "DOC-001", "title": "文件標題", "severity": "高", "source_version": "v0.2.0"}
        ],
    }
    updated = sync_readme_text(_README_TEMPLATE, category_rows)

    assert "IMP-002" not in updated
    assert "| IMP-003 | 新增檔案 | 中 | v0.4.0 |" in updated
    # 新增列附加在 IMP-001 之後、DOC 分類表格之前。
    imp_section = updated.split("### 實作 (IMP)")[1].split("### 文件 (DOC)")[0]
    assert imp_section.index("IMP-001") < imp_section.index("IMP-003")


def test_merge_category_table_row_order_stable_when_unchanged():
    existing_lines = [
        "| IMP-001 | 標題一 | 低 | v0.1.0 |",
        "| IMP-002 | 標題二 | 中 | v0.1.1 |",
    ]
    new_rows = [
        {"id": "IMP-001", "title": "標題一", "severity": "低", "source_version": "v0.1.0"},
        {"id": "IMP-002", "title": "標題二", "severity": "中", "source_version": "v0.1.1"},
    ]
    merged = merge_category_table(existing_lines, new_rows)
    assert merged == existing_lines


def test_merge_category_table_does_not_overwrite_existing_row_placeholder():
    """既有列即使欄位是佔位符也不補齊——佔位符列本身可能是索引獨有一級資料的鄰居列，不因掃描結果不同而被覆寫。"""
    existing_lines = ["| PC-BAL-001 | 舊標題 | — | v0.2.1 |"]
    new_rows = [
        {
            "id": "PC-BAL-001",
            "title": "掃描出的標題",
            "severity": "中",
            "source_version": "—",
        }
    ]
    merged = merge_category_table(existing_lines, new_rows)
    assert merged == existing_lines
