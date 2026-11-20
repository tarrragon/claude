"""readme_index 既有列刷新（--refresh）與來源版本正規化測試。

背景：sync 是保守 upsert，既有列逐字保留；某列一旦以佔位符 `—` 寫入，事後補齊
檔案內文也無法經工具更新，而 SKILL 禁止手改資料列。來源版本欄另有 `v0.2.1` 與
`0.2.1` 兩種寫法並存。

驗證範圍：
- 刷新只覆寫佔位符格；有實值的格不動（索引可能是該資料唯一的載體）
- 正向對照：不加 refresh 時佔位符列維持原樣
- 來源版本正規化：`N.N.N...` 補 `v`，其他寫法不動；新增列與刷新皆套用
- 一 ID 對多檔的無 slug 列不刷新（無法判定對應哪個檔）
- CLI `sync --refresh --write` 寫入刷新結果
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
    PLACEHOLDER,
    extract_row,
    main,
    normalize_version,
    sync,
)

_README = """# Error Patterns

## 現有模式

### 實作 (IMP)

| ID | 標題 | 風險 | 來源版本 |
|----|------|------|---------|
| IMP-001 | — | — | — |
| IMP-002 | 索引獨有標題 | 中 | 0.1.1 |

## 查詢方法
"""


def _pattern(title, severity_line, version_line):
    body = f"# {title}\n\n## 基本資訊\n\n"
    if severity_line:
        body += f"- **風險等級**: {severity_line}\n"
    if version_line:
        body += f"- **來源版本**: {version_line}\n"
    return body


def _setup(tmp_path, files):
    claude_dir = tmp_path / ".claude"
    ep = claude_dir / "error-patterns"
    impl = ep / "implementation"
    impl.mkdir(parents=True)
    (ep / "README.md").write_text(_README, encoding="utf-8")
    for name, content in files.items():
        (impl / name).write_text(content, encoding="utf-8")
    return claude_dir


def _row_line(text, pattern_id):
    return next(l for l in text.splitlines() if l.startswith(f"| {pattern_id}"))


def test_normalize_version():
    assert normalize_version("0.2.1") == "v0.2.1"
    assert normalize_version("v0.2.1") == "v0.2.1"
    assert normalize_version("0.29.0-W1") == "v0.29.0-W1"
    assert normalize_version("feat/workflow-improvement") == "feat/workflow-improvement"
    assert normalize_version(PLACEHOLDER) == PLACEHOLDER


def test_new_row_version_normalized(tmp_path):
    claude_dir = _setup(tmp_path, {"IMP-003-x.md": _pattern("新", "高", "0.3.0")})
    row = extract_row(claude_dir / "error-patterns/implementation/IMP-003-x.md", "IMP-003")
    assert row["source_version"] == "v0.3.0"


def test_without_refresh_placeholder_row_unchanged(tmp_path):
    """正向對照：預設 sync 不動既有佔位符列。"""
    claude_dir = _setup(tmp_path, {
        "IMP-001-a.md": _pattern("內文標題", "高", "v0.1.0"),
        "IMP-002-b.md": _pattern("檔案標題", "低", "v9.9.9"),
    })
    _orig, updated, _diff = sync(claude_dir)
    assert _row_line(updated, "IMP-001") == "| IMP-001 | — | — | — |"


def test_refresh_fills_placeholder_cells(tmp_path):
    claude_dir = _setup(tmp_path, {
        "IMP-001-a.md": _pattern("內文標題", "高", "0.1.0"),
        "IMP-002-b.md": _pattern("檔案標題", "低", "v9.9.9"),
    })
    _orig, updated, _diff = sync(claude_dir, refresh=True)
    assert _row_line(updated, "IMP-001") == "| IMP-001 | 內文標題 | 高 | v0.1.0 |"


def test_refresh_keeps_real_values_and_normalizes_version(tmp_path):
    """有實值的格不被檔案內容覆寫；來源版本只補 v 前綴。"""
    claude_dir = _setup(tmp_path, {
        "IMP-001-a.md": _pattern("內文標題", "高", "v0.1.0"),
        "IMP-002-b.md": _pattern("檔案標題", "低", "v9.9.9"),
    })
    _orig, updated, _diff = sync(claude_dir, refresh=True)
    assert _row_line(updated, "IMP-002") == "| IMP-002 | 索引獨有標題 | 中 | v0.1.1 |"


def test_refresh_leaves_placeholder_when_file_lacks_value(tmp_path):
    claude_dir = _setup(tmp_path, {
        "IMP-001-a.md": _pattern("內文標題", None, None),
        "IMP-002-b.md": _pattern("檔案標題", "低", "v9.9.9"),
    })
    _orig, updated, _diff = sync(claude_dir, refresh=True)
    assert _row_line(updated, "IMP-001") == "| IMP-001 | 內文標題 | — | — |"


def test_refresh_skips_plain_row_with_id_collision(tmp_path):
    """同一 ID 對兩個檔、索引列無 slug：無法判定對應哪個檔，不刷新。"""
    claude_dir = _setup(tmp_path, {
        "IMP-001-a.md": _pattern("甲", "高", "v0.1.0"),
        "IMP-001-b.md": _pattern("乙", "低", "v0.2.0"),
        "IMP-002-b.md": _pattern("檔案標題", "低", "v9.9.9"),
    })
    _orig, updated, _diff = sync(claude_dir, refresh=True)
    assert _row_line(updated, "IMP-001 |") == "| IMP-001 | — | — | — |"


def test_cli_refresh_write(tmp_path, capsys):
    claude_dir = _setup(tmp_path, {
        "IMP-001-a.md": _pattern("內文標題", "高", "0.1.0"),
        "IMP-002-b.md": _pattern("檔案標題", "低", "v9.9.9"),
    })
    rc = main(["sync", "--refresh", "--write", "--claude-dir", str(claude_dir)])
    assert rc == 0
    text = (claude_dir / "error-patterns/README.md").read_text(encoding="utf-8")
    assert _row_line(text, "IMP-001") == "| IMP-001 | 內文標題 | 高 | v0.1.0 |"
    assert _row_line(text, "IMP-002") == "| IMP-002 | 索引獨有標題 | 中 | v0.1.1 |"
