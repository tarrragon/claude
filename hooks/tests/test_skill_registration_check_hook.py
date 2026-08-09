"""skill-registration-check-hook.py 的 check_skill_registration 測試（0.2.1-W3-109）。

原偵測用 `Path.exists()` 判斷小寫 `skill.md`，在 case-insensitive 檔案系統
（macOS APFS）上兩個 `.exists()` 對同一檔皆回 True，分支永不可達。修正後改
消費 `lib.skill_case_guard.find_case_variant`（讀真實 dirent 名稱），與檔案
系統大小寫敏感性無關。本測試用 tmp fixture 覆蓋，不依賴 repo 內樣本
（0.2.1-W3-370 已將僅存的小寫 skill 統一為大寫，repo 內現無小寫樣本）。
"""

import importlib.util
import sys
from pathlib import Path

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
_PROJECT_ROOT = _HOOKS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "skill_registration_check_hook",
    _HOOKS_DIR / "skill-registration-check-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

check_skill_registration = _hook.check_skill_registration


def _valid_frontmatter() -> str:
    return "---\nname: foo\ndescription: bar\n---\nbody\n"


def test_lowercase_skill_md_detected(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text(_valid_frontmatter(), encoding="utf-8")

    is_registered, problem = check_skill_registration(skill_dir)

    assert is_registered is False
    assert problem is not None
    assert "skill.md" in problem
    assert "SKILL.md" in problem


def test_mixed_case_skill_md_detected(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "Skill.md").write_text(_valid_frontmatter(), encoding="utf-8")

    is_registered, problem = check_skill_registration(skill_dir)

    assert is_registered is False
    assert problem is not None
    assert "Skill.md" in problem


def test_correct_uppercase_skill_md_not_flagged(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(_valid_frontmatter(), encoding="utf-8")

    is_registered, problem = check_skill_registration(skill_dir)

    assert is_registered is True
    assert problem is None


def test_empty_directory_reports_empty(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()

    is_registered, problem = check_skill_registration(skill_dir)

    assert is_registered is False
    assert problem == "empty directory"


def test_missing_skill_md_reports_missing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "README.md").write_text("# foo\n", encoding="utf-8")

    is_registered, problem = check_skill_registration(skill_dir)

    assert is_registered is False
    assert problem == "missing SKILL.md"

