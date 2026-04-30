"""extract_where_files / extract_where_files_from_frontmatter 共用 helper 單元測試（W11-004.7.2）。

驗證點：
1. extract_where_files_from_frontmatter 處理 dict / 換行字串 / 空值 / 非預期型別
2. extract_where_files 透過 find_ticket_file + parse_ticket_frontmatter 完整鏈路定位 ticket
3. ticket 不存在 / frontmatter 無 where 時回傳 []
"""

import sys
from pathlib import Path

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from hook_utils.hook_ticket import (
    extract_where_files,
    extract_where_files_from_frontmatter,
)


# ---------------------------------------------------------------------------
# extract_where_files_from_frontmatter
# ---------------------------------------------------------------------------

def test_from_frontmatter_none_returns_empty():
    assert extract_where_files_from_frontmatter(None) == []


def test_from_frontmatter_empty_dict_returns_empty():
    assert extract_where_files_from_frontmatter({}) == []


def test_from_frontmatter_dict_with_list_files():
    fm = {"where": {"files": [".claude/hooks/a.py", ".claude/hooks/b.py"]}}
    assert extract_where_files_from_frontmatter(fm) == [
        ".claude/hooks/a.py",
        ".claude/hooks/b.py",
    ]


def test_from_frontmatter_dict_with_newline_string_files():
    """YAML 解析有時將列表累積為換行字串。"""
    fm = {"where": {"files": ".claude/hooks/a.py\n.claude/hooks/b.py"}}
    assert extract_where_files_from_frontmatter(fm) == [
        ".claude/hooks/a.py",
        ".claude/hooks/b.py",
    ]


def test_from_frontmatter_strips_whitespace_and_filters_blanks():
    fm = {"where": {"files": ["  src/a.py  ", "", "   ", "lib/b.py"]}}
    assert extract_where_files_from_frontmatter(fm) == ["src/a.py", "lib/b.py"]


def test_from_frontmatter_where_string_top_level():
    """where 直接是字串（少見退化情況）。"""
    fm = {"where": "src/a.py\nsrc/b.py"}
    assert extract_where_files_from_frontmatter(fm) == ["src/a.py", "src/b.py"]


def test_from_frontmatter_unexpected_type_returns_empty():
    fm = {"where": {"files": 42}}
    assert extract_where_files_from_frontmatter(fm) == []


def test_from_frontmatter_no_where_key_returns_empty():
    fm = {"id": "x", "title": "y"}
    assert extract_where_files_from_frontmatter(fm) == []


# ---------------------------------------------------------------------------
# extract_where_files (整合：透過實際 ticket md)
# ---------------------------------------------------------------------------

def _write_ticket(tmp_path: Path, ticket_id: str, body: str) -> Path:
    """在 tmp 模擬 hierarchical 結構建立 ticket md。"""
    version = ticket_id.split("-W")[0]  # 0.18.0
    parts = version.split(".")
    major = "v" + parts[0]
    minor = f"v{parts[0]}.{parts[1]}"
    full = f"v{version}"
    ticket_dir = tmp_path / "docs" / "work-logs" / major / minor / full / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    md = ticket_dir / f"{ticket_id}.md"
    md.write_text(body, encoding="utf-8")
    return md


def test_extract_where_files_integration(tmp_path):
    ticket_id = "0.18.0-W11-004.7.2"
    body = """---
id: 0.18.0-W11-004.7.2
title: test
where:
  layer: hooks
  files:
  - .claude/hooks/a.py
  - .claude/hooks/b.py
---

# Body
"""
    _write_ticket(tmp_path, ticket_id, body)
    result = extract_where_files(ticket_id, project_root=tmp_path)
    assert result == [".claude/hooks/a.py", ".claude/hooks/b.py"]


def test_extract_where_files_ticket_missing_returns_empty(tmp_path):
    result = extract_where_files("0.99.0-W1-001", project_root=tmp_path)
    assert result == []


def test_extract_where_files_no_where_section(tmp_path):
    ticket_id = "0.18.0-W11-999"
    body = """---
id: 0.18.0-W11-999
title: no-where
---
"""
    _write_ticket(tmp_path, ticket_id, body)
    assert extract_where_files(ticket_id, project_root=tmp_path) == []


def test_extract_where_files_where_without_files_key(tmp_path):
    ticket_id = "0.18.0-W11-998"
    body = """---
id: 0.18.0-W11-998
title: where-without-files
where:
  layer: x
---
"""
    _write_ticket(tmp_path, ticket_id, body)
    assert extract_where_files(ticket_id, project_root=tmp_path) == []
