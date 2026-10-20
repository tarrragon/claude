"""
hook_ticket where.files 單一實作測試（0.5.0-W1-338.2.1）。

四個讀票面 where.files 的呼叫端（parallel-dispatch-verification、
bare-commit-guard、agent-dispatch-validation、acceptance_checkers/ticket_parser）
收斂到 lib.hook_ticket 後，各自原有的行為差異以參數表達；本檔逐一鎖定：

1. intent=None   原樣回傳（agent-dispatch / bare-commit 現行）
2. intent="write" 剝 ::read/::write 後綴並排除 ::read（parallel-dispatch 現行）
3. canonical=True 去重 + 去佔位符 + 嚴格型別（ticket_parser 現行）
4. raise_on_missing 找不到票時拋 ValueError（bare-commit 現行）；預設回 []
每組皆含正向對照（有後綴／找得到票）與反向對照（無後綴／找不到票）。
"""

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.hook_ticket import (  # noqa: E402
    extract_where_files,
    extract_where_files_from_frontmatter,
)

_LOGGER = logging.getLogger("test_hook_ticket_where_files")


def _fm(*files):
    return {"where": {"files": list(files)}}


def _write_ticket(root: Path, ticket_id: str, body: str) -> None:
    version = ticket_id.split("-W")[0]
    major, minor, _ = version.split(".")
    ticket_dir = (
        root / "docs" / "work-logs" / f"v{major}" / f"v{major}.{minor}"
        / f"v{version}" / "tickets"
    )
    ticket_dir.mkdir(parents=True, exist_ok=True)
    (ticket_dir / f"{ticket_id}.md").write_text(body, encoding="utf-8")


# ---- intent=None：原樣 ----

def test_raw_keeps_suffix_untouched():
    fm = _fm("a.py::write", "b.py::read", "c.py")
    assert extract_where_files_from_frontmatter(fm) == [
        "a.py::write", "b.py::read", "c.py",
    ]


def test_raw_accepts_newline_string_where():
    assert extract_where_files_from_frontmatter({"where": "a.py\nb.py"}) == ["a.py", "b.py"]


# ---- intent="write"：parallel-dispatch ----

def test_write_intent_strips_suffix_and_drops_read():
    fm = _fm("a.py::write", "b.py::read", "c.py")
    assert extract_where_files_from_frontmatter(fm, intent="write") == ["a.py", "c.py"]


def test_write_intent_does_not_dedupe_or_drop_placeholder():
    fm = _fm("a.py", "a.py::write", "待定義")
    assert extract_where_files_from_frontmatter(fm, intent="write") == [
        "a.py", "a.py", "待定義",
    ]


def test_all_intent_strips_suffix_but_keeps_read():
    fm = _fm("a.py::write", "b.py::read")
    assert extract_where_files_from_frontmatter(fm, intent="all") == ["a.py", "b.py"]


def test_escaped_marker_restored_as_path_text():
    fm = _fm("dir/x.md\\::read")
    assert extract_where_files_from_frontmatter(fm, intent="all") == ["dir/x.md::read"]


# ---- canonical=True：ticket_parser ----

def test_canonical_dedupes_after_suffix_strip_and_drops_placeholders():
    fm = _fm("a.py::read", "a.py::write", "待定義", "TBD", "b.py")
    assert extract_where_files_from_frontmatter(
        fm, _LOGGER, intent="all", canonical=True
    ) == ["a.py", "b.py"]


def test_canonical_write_only_excludes_read_marked():
    fm = _fm("a.py", "b.py::write", "c.py::read")
    assert extract_where_files_from_frontmatter(
        fm, _LOGGER, intent="write", canonical=True
    ) == ["a.py", "b.py"]


def test_canonical_is_strict_about_where_shape():
    assert extract_where_files_from_frontmatter(
        {"where": "a.py"}, _LOGGER, intent="all", canonical=True
    ) == []
    assert extract_where_files_from_frontmatter(
        {"where": {"files": "a.py\nb.py::read"}}, _LOGGER, intent="all", canonical=True
    ) == ["a.py", "b.py"]
    assert extract_where_files_from_frontmatter(
        _fm("a.py", 7, None), _LOGGER, intent="all", canonical=True
    ) == ["a.py"]


# ---- ticket 層：找不到票 ----

_BODY = "---\nid: 0.18.0-W11-004\nwhere:\n  files:\n  - a.py::write\n  - b.py::read\n---\n"


def test_ticket_found_returns_files_for_each_mode(tmp_path):
    _write_ticket(tmp_path, "0.18.0-W11-004", _BODY)
    tid = "0.18.0-W11-004"
    assert extract_where_files(tid, tmp_path) == ["a.py::write", "b.py::read"]
    assert extract_where_files(tid, tmp_path, intent="write") == ["a.py"]
    assert extract_where_files(tid, tmp_path, raise_on_missing=True) == [
        "a.py::write", "b.py::read",
    ]


def test_ticket_missing_returns_empty_by_default(tmp_path):
    assert extract_where_files("0.99.0-W1-001", tmp_path) == []


def test_ticket_missing_raises_when_requested(tmp_path):
    with pytest.raises(ValueError):
        extract_where_files("0.99.0-W1-001", tmp_path, raise_on_missing=True)


def test_ticket_readable_without_where_returns_empty_even_when_raising(tmp_path):
    _write_ticket(tmp_path, "0.18.0-W11-005", "---\nid: 0.18.0-W11-005\ntitle: x\n---\n")
    assert extract_where_files("0.18.0-W11-005", tmp_path, raise_on_missing=True) == []
