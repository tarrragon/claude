#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Tests for skill_residue_detector.

執行：uv run --no-project --with pytest pytest .claude/scripts/test_skill_residue_detector.py

這組測試同時釘住偵測與**不**偵測：偵測器的價值取決於精確度，只驗「抓得到」
會讓它一路放寬到把每個示意路徑都當殘留，讀者學會忽略後即失效。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from skill_residue_detector import (  # noqa: E402
    blocking_only,
    format_report,
    is_reader_facing,
    known_versions,
    scan_all,
    scan_skill,
)


@pytest.fixture
def project(tmp_path):
    """A project tree with lib/, a worklog version, and one skill."""
    root = tmp_path / "proj"
    (root / "lib" / "core").mkdir(parents=True)
    (root / "lib" / "core" / "real.dart").write_text("// real", encoding="utf-8")
    (root / "docs" / "work-logs" / "v0" / "v0.2").mkdir(parents=True)
    (root / ".claude" / "skills" / "probe" / "references").mkdir(parents=True)

    def _write(body: str, rel: str = "SKILL.md") -> Path:
        path = root / ".claude" / "skills" / "probe" / rel
        path.write_text(body, encoding="utf-8")
        return root

    return _write


def kinds(root: Path) -> list[str]:
    findings = scan_all(root / ".claude" / "skills", root)
    return [r.kind for items in findings.values() for r in items]


def details(root: Path) -> list[str]:
    findings = scan_all(root / ".claude" / "skills", root)
    return [r.detail for items in findings.values() for r in items]


class TestDetects:
    def test_missing_project_path(self, project):
        root = project("見 `lib/core/gone.dart`\n")
        assert kinds(root) == ["MISSING_PATH"]

    def test_missing_script(self, project):
        root = project("執行 `uv run scripts/gone.py`\n")
        assert kinds(root) == ["MISSING_SCRIPT"]

    def test_foreign_ticket_id(self, project):
        root = project("本 skill 於 9.9.9-W1-001 建立\n")
        assert kinds(root) == ["FOREIGN_TICKET_ID"]

    def test_references_dir_is_scanned(self, project):
        root = project("見 `lib/core/gone.dart`\n", rel="references/detail.md")
        assert kinds(root) == ["MISSING_PATH"]


class TestDoesNotDetect:
    def test_existing_path(self, project):
        root = project("見 `lib/core/real.dart`\n")
        assert kinds(root) == []

    def test_placeholder_path(self, project):
        root = project("見 `lib/path/to/example.dart` 與 `lib/<your-file>.dart`\n")
        assert kinds(root) == []

    def test_exempt_marker(self, project):
        root = project("見 `lib/core/gone.dart` <!-- skill-residue-exempt: 刻意 -->\n")
        assert kinds(root) == []

    def test_top_level_dir_absent_from_project(self, project):
        """專案沒有 tests/ 時，tests/... 是文件的通用示意而非殘留。"""
        root = project("見 `tests/auth/test_login.py`\n")
        assert kinds(root) == []

    def test_known_version_ticket_id(self, project):
        """版本段對應 docs/work-logs/ 下的目錄即屬本專案，含更細的第三段。"""
        root = project("見 0.2.1-W3-001 的結論\n")
        assert kinds(root) == []

    def test_bare_version_string_is_not_a_signal(self, project):
        """裸版本號無從判斷指涉對象，硬判會把 skill 自身版本當殘留。"""
        root = project("**Version**: 1.2.0 — 見 v2.1.133 的行為變更\n")
        assert kinds(root) == []

    def test_skill_internal_module_shorthand(self, project):
        """skill 文件常以簡寫指自身模組，該檔存在於 skill 子樹即不算缺席。"""
        root = project("複用 `lib/helper.py` 的判定\n")
        skill = root / ".claude" / "skills" / "probe"
        (skill / "pkg" / "lib").mkdir(parents=True)
        (skill / "pkg" / "lib" / "helper.py").write_text("", encoding="utf-8")
        assert kinds(root) == []


class TestScopeOfScan:
    @pytest.mark.parametrize(
        "rel,expected",
        [
            ("SKILL.md", True),
            ("references/detail.md", True),
            ("tests/test_x.py", False),
            ("templates/spec-template.md", False),
            ("scripts/tool.py", False),
        ],
    )
    def test_reader_facing_files_only(self, tmp_path, rel, expected):
        skill_dir = tmp_path / "skill"
        path = skill_dir / rel
        assert is_reader_facing(path, skill_dir) is expected


class TestSeverity:
    def test_blocking_excludes_advisory(self, project):
        root = project("見 `lib/core/gone.dart`，出自 9.9.9-W1-001\n")
        findings = scan_all(root / ".claude" / "skills", root)
        assert len(findings["probe"]) == 2
        assert [r.kind for r in blocking_only(findings)["probe"]] == ["MISSING_PATH"]

    def test_advisory_only_yields_no_blocking(self, project):
        root = project("出自 9.9.9-W1-001\n")
        assert blocking_only(scan_all(root / ".claude" / "skills", root)) == {}


class TestVersionDiscovery:
    def test_versions_read_from_worklog_tree(self, project):
        root = project("內容\n")
        assert known_versions(root) == {"0", "0.2"}

    def test_missing_worklog_yields_empty(self, tmp_path):
        assert known_versions(tmp_path) == set()


class TestReport:
    def test_truncation_states_how_many_were_withheld(self, project):
        root = project("\n".join(f"見 `lib/core/gone{i}.dart`" for i in range(8)) + "\n")
        findings = scan_all(root / ".claude" / "skills", root)
        report = "\n".join(format_report(findings, limit_per_skill=3))
        assert "另有 5 項未列出" in report

    def test_no_truncation_notice_when_all_shown(self, project):
        root = project("見 `lib/core/gone.dart`\n")
        findings = scan_all(root / ".claude" / "skills", root)
        report = "\n".join(format_report(findings, limit_per_skill=5))
        assert "未列出" not in report


class TestSkillScan:
    def test_scan_skill_returns_flat_list(self, project):
        root = project("見 `lib/core/gone.dart`\n")
        found = scan_skill(root / ".claude" / "skills" / "probe", root)
        assert len(found) == 1
        assert found[0].skill == "probe"


class TestCaseMismatchWarning:
    """`skill.md`（錯誤大小寫）不會被 is_reader_facing 的精確比對命中，掃描
    器會靜默略過其內容；scan_all 需在掃描前另外告警，避免這種盲區被讀成
    「無殘留」。"""

    def test_scan_all_warns_lowercase_skill_md(self, tmp_path, capsys):
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "wrong-case"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.md").write_text("body\n", encoding="utf-8")

        scan_all(skills_dir, tmp_path)

        captured = capsys.readouterr()
        assert "wrong-case" in captured.err
        assert "skill.md" in captured.err

    def test_scan_all_silent_for_correct_uppercase(self, project, capsys):
        root = project("見 `lib/core/gone.dart`\n")
        scan_all(root / ".claude" / "skills", root)

        captured = capsys.readouterr()
        assert captured.err == ""


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
