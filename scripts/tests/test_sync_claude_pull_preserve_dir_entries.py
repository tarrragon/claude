"""Tests for sync-preserve.yaml 目錄項（3.4.0-W1-307.4，tarrragon/claude#50）。

改前 pull 的 preserve 比對點皆為 `rel in preserve` 精確比對，目錄項（含或不含
結尾 /）對其下檔案永不命中且無提示。改為共用 _is_preserved：檔案項精確比對，
目錄項以 `<項目>/` 前綴比對。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_preserve_dir", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_preserve_dir"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "entry",
    ["skills/foo/", "skills/foo"],
)
def test_dir_entry_covers_nested_files(entry):
    preserve = {entry}
    assert pull._is_preserved("skills/foo/SKILL.md", preserve)
    assert pull._is_preserved("skills/foo/references/a.md", preserve)


def test_dir_entry_does_not_match_sibling_with_same_prefix():
    assert not pull._is_preserved("skills/foobar/SKILL.md", {"skills/foo"})


def test_file_entry_still_exact():
    preserve = {"rules/core/x.md"}
    assert pull._is_preserved("rules/core/x.md", preserve)
    assert not pull._is_preserved("rules/core/x.md.bak", preserve)
    assert not pull._is_preserved("rules/core/y.md", preserve)


def test_empty_preserve_matches_nothing():
    assert not pull._is_preserved("skills/foo/SKILL.md", set())


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_sync_directory_keeps_files_under_preserved_dir(tmp_path):
    """full overlay：目錄項之下的本地特化不被上游覆寫；目錄外的檔照常同步。"""
    src = tmp_path / "upstream"
    dst = tmp_path / "local"
    _write(src, "skills/foo/SKILL.md", "upstream")
    _write(src, "skills/other/SKILL.md", "upstream")
    _write(dst, "skills/foo/SKILL.md", "local customization")
    _write(dst, "skills/other/SKILL.md", "old")

    pull.sync_directory(src, dst, {"skills/foo/"}, Path(), None, None)

    assert (dst / "skills/foo/SKILL.md").read_text(encoding="utf-8") == "local customization"
    assert (dst / "skills/other/SKILL.md").read_text(encoding="utf-8") == "upstream"


def test_sync_directory_does_not_resurrect_preserved_dir_missing_locally(tmp_path):
    """本地已刪除的 preserve 目錄，不被整批複製捷徑帶回。"""
    src = tmp_path / "upstream"
    dst = tmp_path / "local"
    _write(src, "skills/foo/SKILL.md", "upstream")
    dst.mkdir()

    pull.sync_directory(src, dst, {"skills/foo"}, Path(), None, None)

    assert not (dst / "skills/foo/SKILL.md").exists()


def test_sync_directory_new_dir_without_preserve_still_copied(tmp_path):
    """正向對照：沒有 preserve 涉及的新目錄照常整批帶入。"""
    src = tmp_path / "upstream"
    dst = tmp_path / "local"
    _write(src, "skills/new/SKILL.md", "upstream")
    dst.mkdir()

    pull.sync_directory(src, dst, {"skills/foo"}, Path(), None, None)

    assert (dst / "skills/new/SKILL.md").read_text(encoding="utf-8") == "upstream"
