"""Tests for skill_case_guard module."""

from pathlib import Path

from lib.skill_case_guard import warn_skill_md_case_mismatch


def test_lowercase_variant_produces_warning(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "error-pattern"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text("# error-pattern\n", encoding="utf-8")

    warnings = warn_skill_md_case_mismatch(skills_dir)

    assert len(warnings) == 1
    assert "error-pattern" in warnings[0]
    assert "skill.md" in warnings[0]


def test_correct_uppercase_produces_no_warning(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "wrap-decision"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# wrap-decision\n", encoding="utf-8")

    assert warn_skill_md_case_mismatch(skills_dir) == []


def test_missing_base_dir_returns_empty_list(tmp_path: Path) -> None:
    assert warn_skill_md_case_mismatch(tmp_path / "no-such-dir") == []


def test_multiple_mismatched_skills_each_produce_own_warning(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    for name in ("alpha", "beta"):
        d = skills_dir / name
        d.mkdir(parents=True)
        (d / "skill.md").write_text("# body\n", encoding="utf-8")

    warnings = warn_skill_md_case_mismatch(skills_dir)

    assert len(warnings) == 2
    assert any("alpha" in w for w in warnings)
    assert any("beta" in w for w in warnings)
