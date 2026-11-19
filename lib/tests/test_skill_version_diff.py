#!/usr/bin/env python3
"""
skill_version_diff 模組單元測試

extract_skill_versions() 原僅從 SKILL.md 的 `**Version**:` 行擷取版本，
CHANGELOG 版本紀錄外移後大量 skill 的 SKILL.md 不再含該行，擷取全數落空，
使 push/pull 兩端的 before/after 快照比對誤判為「skill 已移除」（pull 端
甚至印出紅色刪除警示）。本檔驗證四層優先序來源（CHANGELOG.md 頂端條目 /
frontmatter metadata.version / SKILL.md 舊格式行 / frontmatter 頂層
version 欄位）與各自的向後相容行為。
"""

import sys
from pathlib import Path

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.skill_version_diff import (
    LOC_BODY,
    LOC_CHANGELOG,
    LOC_PLUGIN,
    LOC_PYPROJECT,
    VersionCheck,
    VersionMismatch,
    check_skill_versions,
    extract_skill_versions,
    find_version_mismatches,
    format_skill_version_diff,
    format_version_check_failure,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ============================================================================
# 新格式來源 1：同目錄 CHANGELOG.md 最上方（新到舊排序）的條目
# ============================================================================


def test_changelog_top_entry_wins(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", "---\nname: demo\n---\n# demo\n")
    _write(
        tmp_path / "demo" / "CHANGELOG.md",
        "# demo 版本紀錄\n\n新到舊。\n\n"
        "**Version**: 2.3.0 — 最新變更\n\n"
        "**Version**: 2.2.0 — 較舊變更\n",
    )
    versions = extract_skill_versions(tmp_path)
    assert versions.get("demo") == "2.3.0"


def test_empty_changelog_falls_through(tmp_path: Path) -> None:
    """僅有標題+引言、無任何 **Version** 條目的 CHANGELOG（Category A
    零版本紀錄 skill）不應誤判為擷取成功，應繼續嘗試其餘來源。"""
    _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\nmetadata:\n  version: 9.0.0\n---\n# demo\n",
    )
    _write(
        tmp_path / "demo" / "CHANGELOG.md",
        "# demo 版本紀錄\n\n新到舊。版號規則見專案的 skill 同步規範。\n",
    )
    versions = extract_skill_versions(tmp_path)
    assert versions.get("demo") == "9.0.0"


# ============================================================================
# 新格式來源 2：SKILL.md frontmatter 巢狀的 metadata.version
# ============================================================================


def test_metadata_version_extracted_without_changelog(tmp_path: Path) -> None:
    _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\nmetadata:\n  portable: true\n  version: 1.5.2\n"
        "  category: writing-methodology\n---\n# demo\n",
    )
    versions = extract_skill_versions(tmp_path)
    assert versions.get("demo") == "1.5.2"


def test_metadata_version_overrides_toplevel_version(tmp_path: Path) -> None:
    """frontmatter 同時有頂層 version 與 metadata.version 時，
    metadata.version 優先（較新格式優先於較舊格式）。"""
    _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\nversion: 1.0.0\nmetadata:\n  version: 2.0.0\n"
        "---\n# demo\n",
    )
    versions = extract_skill_versions(tmp_path)
    assert versions.get("demo") == "2.0.0"


# ============================================================================
# 向後相容：舊格式（SKILL.md body **Version** 行、frontmatter 頂層
# version 欄位）維持既有行為不變
# ============================================================================


def test_legacy_skill_md_version_line(tmp_path: Path) -> None:
    _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\n---\n# demo\n\n**Version**: 0.9.0 — 尚未遷移\n",
    )
    versions = extract_skill_versions(tmp_path)
    assert versions.get("demo") == "0.9.0"


def test_toplevel_frontmatter_version_third_party_style(tmp_path: Path) -> None:
    """第三方 skill 的 frontmatter schema 與本專案慣例不同，version 欄位
    在頂層而非巢狀於 metadata 之下（既有 fallback，涵蓋既有場景）。"""
    _write(
        tmp_path / "demo" / "SKILL.md",
        "---\nname: demo\ndescription: third-party skill\n"
        "version: 3.5.0\nuser-invocable: true\n---\n# demo\n",
    )
    versions = extract_skill_versions(tmp_path)
    assert versions.get("demo") == "3.5.0"


def test_no_version_anywhere_excluded(tmp_path: Path) -> None:
    """四層來源皆無版本資訊時（如尚未賦予首個版號的 skill），該 skill
    不列入結果——非本次修復範圍（無資料可擷取，非格式解析缺陷）。"""
    _write(tmp_path / "demo" / "SKILL.md", "---\nname: demo\n---\n# demo\n")
    _write(
        tmp_path / "demo" / "CHANGELOG.md",
        "# demo 版本紀錄\n\n新到舊。版號規則見專案的 skill 同步規範。\n",
    )
    versions = extract_skill_versions(tmp_path)
    assert "demo" not in versions


# ============================================================================
# 版號行的格式變體：擷取值只取 semver 本體
# 條目常見寫法「**Version**: X（日期）— 說明」，以及 CHANGELOG 開頭說明句
# 以行內字面提到 `**Version**:`；擷取值不得帶入尾綴或說明句字元
# ============================================================================


def test_changelog_fullwidth_date_suffix_stripped(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", "---\nname: demo\n---\n")
    _write(
        tmp_path / "demo" / "CHANGELOG.md",
        "# demo\n\n**Version**: 1.3.5（2026-11-19）— 新增一節\n",
    )
    assert extract_skill_versions(tmp_path).get("demo") == "1.3.5"


def test_changelog_preamble_literal_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", "---\nname: demo\n---\n")
    _write(
        tmp_path / "demo" / "CHANGELOG.md",
        "# demo\n\n新到舊。版號住址是本檔最上方的 `**Version**:` 條目。\n\n"
        "**Version**: 1.28.0 — 最新\n",
    )
    assert extract_skill_versions(tmp_path).get("demo") == "1.28.0"


def test_changelog_inline_mention_mid_line_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", "---\nname: demo\n---\n")
    _write(
        tmp_path / "demo" / "CHANGELOG.md",
        "# demo\n\n說明：條目寫成 **Version**: 9.9.9 這種形式。\n\n"
        "**Version**: 2.0.1 — 最新\n",
    )
    assert extract_skill_versions(tmp_path).get("demo") == "2.0.1"


def test_changelog_plain_entry_unchanged(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", "---\nname: demo\n---\n")
    _write(tmp_path / "demo" / "CHANGELOG.md", "# demo\n\n**Version**: 4.2.0\n")
    assert extract_skill_versions(tmp_path).get("demo") == "4.2.0"


def test_real_skills_dir_versions_are_semver() -> None:
    import re

    import pytest

    skills_dir = Path(__file__).resolve().parents[2] / "skills"
    if not skills_dir.is_dir():
        pytest.skip("此環境無 .claude/skills/ 目錄，略過實測")

    semver = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
    bad = {
        name: value
        for name, value in extract_skill_versions(skills_dir).items()
        if not semver.match(value)
    }
    assert bad == {}, f"以下 skill 擷取值不是 semver：{bad}"


# ============================================================================
# 對本專案實際 .claude/skills/ 目錄實測，驗證擷取涵蓋率
# （0.2.1-W3-1202 acceptance：58 個 skill 實測零缺漏，格式導致的落空歸零）
# ============================================================================


def test_real_skills_dir_extraction_coverage() -> None:
    skills_dir = Path(__file__).resolve().parents[2] / "skills"
    if not skills_dir.is_dir():
        import pytest
        pytest.skip("此環境無 .claude/skills/ 目錄，略過實測")

    versions = extract_skill_versions(skills_dir)
    all_skill_dirs = sorted(
        p.name for p in skills_dir.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file()
    )
    missing = [s for s in all_skill_dirs if s not in versions]

    # 已知例外：兩個 skill 自建立起即從未記錄過版本號（遷移 commit 自身
    # 標註為「Category A：0 版本紀錄」），非本次格式修復可處理的缺口——
    # 沒有任何檔案含可擷取的版本資訊，不是解析邏輯的問題。若這兩個 skill
    # 日後補上首個版號，本斷言仍會通過（差集只會更小，不會失敗）。
    known_zero_history_skills = {"dart-domain-modeling", "verify"}
    unexpected_missing = set(missing) - known_zero_history_skills

    assert unexpected_missing == set(), (
        f"以下 skill 版本擷取落空且非已知的零版本紀錄例外，"
        f"可能是格式解析缺陷：{sorted(unexpected_missing)}"
    )


# ============================================================================
# P0 症狀重現與修復驗證：CHANGELOG 外移前後皆能正確擷取時，
# format_skill_version_diff 應正確顯示為版本更新，而非誤判移除
# ============================================================================


def test_migration_no_longer_reported_as_removal() -> None:
    # before：consumer 端尚未拉取本輪修復前的舊格式快照
    before = {"compositional-writing": "1.5.0", "skill-sync": "1.12.0"}
    # after：CHANGELOG 外移後，四層優先序仍能正確擷取（本票修復後的狀態）
    after = {"compositional-writing": "1.5.2", "skill-sync": "1.12.1"}

    diff = format_skill_version_diff(before, after)

    assert diff is not None
    assert "移除" not in diff
    assert "更新" in diff


def test_extraction_failure_would_have_caused_false_removal() -> None:
    """反向驗證：若擷取真的落空（修復前的症狀），確認
    format_skill_version_diff 的既有邏輯本身無誤——問題出在擷取端輸入
    全空，不是比對邏輯的 bug。"""
    before = {"compositional-writing": "1.5.0"}
    after_if_extraction_still_broken: dict[str, str] = {}

    diff = format_skill_version_diff(before, after_if_extraction_still_broken)

    assert diff is not None
    assert "移除" in diff


# ============================================================================
# 權威來源：metadata.version 優先於 CHANGELOG（與 skill-sync 讀取順序一致）
# ============================================================================


def _skill_md(version: str | None, body: str = "# demo\n") -> str:
    meta = f"metadata:\n  version: {version}\n" if version else ""
    return f"---\nname: demo\n{meta}---\n{body}"


def test_metadata_version_wins_over_changelog_when_they_differ(tmp_path: Path) -> None:
    """兩處分歧時讀權威欄位；改回 CHANGELOG 優先時本測試轉紅。"""
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("2.54.1"))
    _write(tmp_path / "demo" / "CHANGELOG.md", "# demo\n\n**Version**: 2.54.2 — 新\n")
    assert extract_skill_versions(tmp_path).get("demo") == "2.54.1"


def test_changelog_used_only_when_metadata_missing(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md(None))
    _write(tmp_path / "demo" / "CHANGELOG.md", "# demo\n\n**Version**: 3.0.0 — 新\n")
    assert extract_skill_versions(tmp_path).get("demo") == "3.0.0"


# ============================================================================
# find_version_mismatches：正向對照（分歧要報出）
# ============================================================================


def _locations(mismatches: list[VersionMismatch]) -> set[str]:
    return {m.location for m in mismatches}


def test_mismatch_changelog(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.0.0"))
    _write(tmp_path / "demo" / "CHANGELOG.md", "# demo\n\n**Version**: 1.0.1 — x\n")
    assert find_version_mismatches(tmp_path) == [
        VersionMismatch("demo", LOC_CHANGELOG, "1.0.1", "1.0.0")
    ]


def test_mismatch_body_version_line(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.1.0", "# demo\n\n**Version**: 1.0.0\n"))
    assert _locations(find_version_mismatches(tmp_path)) == {LOC_BODY}


def test_mismatch_pyproject(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.7.0"))
    _write(tmp_path / "demo" / "pyproject.toml", '[project]\nname = "demo"\nversion = "1.1.0"\n')
    assert _locations(find_version_mismatches(tmp_path)) == {LOC_PYPROJECT}


def test_mismatch_dunder_version_reports_relative_path(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.7.0"))
    _write(tmp_path / "demo" / "demo_pkg" / "__init__.py", '__version__ = "0.1.0"\n')
    [m] = find_version_mismatches(tmp_path)
    assert (m.found, m.expected) == ("0.1.0", "1.7.0")
    assert "demo_pkg/__init__.py" in m.location


def test_mismatch_plugin_json(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("0.15.0"))
    _write(tmp_path / "demo" / ".claude-plugin" / "plugin.json", '{"name": "demo", "version": "0.11.0"}')
    assert _locations(find_version_mismatches(tmp_path)) == {LOC_PLUGIN}


def test_missing_authority_with_derived_version_is_reported(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md(None))
    _write(tmp_path / "demo" / "CHANGELOG.md", "# demo\n\n**Version**: 1.0.0 — x\n")
    assert find_version_mismatches(tmp_path) == [
        VersionMismatch("demo", LOC_CHANGELOG, "1.0.0", None)
    ]


# ============================================================================
# find_version_mismatches：反向對照（一致、住址不存在或不屬 skill 本體時不報）
# ============================================================================


def test_all_locations_consistent_reports_nothing(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("2.0.0", "# demo\n\n**Version**: 2.0.0\n"))
    _write(tmp_path / "demo" / "CHANGELOG.md", "# demo\n\n**Version**: 2.0.0 — x\n")
    _write(tmp_path / "demo" / "pyproject.toml", '[project]\nname = "demo"\nversion = "2.0.0"\n')
    _write(tmp_path / "demo" / "pkg" / "__init__.py", '__version__ = "2.0.0"\n')
    _write(tmp_path / "demo" / ".claude-plugin" / "plugin.json", '{"version": "2.0.0"}')
    assert find_version_mismatches(tmp_path) == []


def test_only_authority_present_reports_nothing(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.0.0"))
    assert find_version_mismatches(tmp_path) == []


def test_fenced_changelog_example_in_body_is_ignored(tmp_path: Path) -> None:
    body = "# demo\n\n```markdown\n**Version**: 9.9.9 — 範例\n```\n"
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.0.0", body))
    assert find_version_mismatches(tmp_path) == []


def test_dunder_in_tests_and_venv_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.0.0"))
    _write(tmp_path / "demo" / "tests" / "__init__.py", '__version__ = "0.0.1"\n')
    _write(tmp_path / "demo" / ".venv" / "lib" / "x" / "__init__.py", '__version__ = "5.0.0"\n')
    assert find_version_mismatches(tmp_path) == []


def test_dynamic_pyproject_version_is_not_compared(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.0.0"))
    _write(tmp_path / "demo" / "pyproject.toml", '[project]\nname = "demo"\ndynamic = ["version"]\n')
    assert find_version_mismatches(tmp_path) == []


# ============================================================================
# check_skill_versions：讀不出版號的住址列入 skipped，不當成一致
# （擋閘門的呼叫端以 ok 判定；只看 mismatches 會讓讀不到的住址放行）
# ============================================================================


def _consistent_skill(root: Path, version: str = "1.0.0") -> Path:
    skill = root / "demo"
    _write(skill / "SKILL.md", _skill_md(version))
    _write(skill / "CHANGELOG.md", f"# demo\n\n**Version**: {version} — x\n")
    return skill


def _skipped_locations(root: Path) -> set[str]:
    return {s.location for s in check_skill_versions(root).skipped}


def test_check_consistent_skill_is_ok(tmp_path: Path) -> None:
    _consistent_skill(tmp_path)
    check = check_skill_versions(tmp_path)
    assert check.ok
    assert check == VersionCheck([], [], [])


def test_check_missing_changelog_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", _skill_md("1.0.0"))
    assert _skipped_locations(tmp_path) == {LOC_CHANGELOG}
    assert not check_skill_versions(tmp_path).ok


def test_check_changelog_without_version_line_is_skipped(tmp_path: Path) -> None:
    """`## 1.1.0 — 日期` 標題格式不是慣例格式，擷取不到即略過，不當成一致。"""
    skill = _consistent_skill(tmp_path)
    _write(skill / "CHANGELOG.md", "# CHANGELOG\n\n## 1.0.0 — 2026-10-30\n\n- 初始\n")
    assert _skipped_locations(tmp_path) == {LOC_CHANGELOG}


def test_check_unparseable_pyproject_is_skipped(tmp_path: Path) -> None:
    skill = _consistent_skill(tmp_path)
    _write(skill / "pyproject.toml", "[project\nversion = \n")
    assert _skipped_locations(tmp_path) == {LOC_PYPROJECT}


def test_check_dynamic_pyproject_is_skipped(tmp_path: Path) -> None:
    skill = _consistent_skill(tmp_path)
    _write(skill / "pyproject.toml", '[project]\nname = "demo"\ndynamic = ["version"]\n')
    assert _skipped_locations(tmp_path) == {LOC_PYPROJECT}


def test_check_invalid_plugin_json_is_skipped(tmp_path: Path) -> None:
    skill = _consistent_skill(tmp_path)
    _write(skill / ".claude-plugin" / "plugin.json", "{not json")
    assert _skipped_locations(tmp_path) == {LOC_PLUGIN}


def test_check_plugin_json_without_version_is_skipped(tmp_path: Path) -> None:
    skill = _consistent_skill(tmp_path)
    _write(skill / ".claude-plugin" / "plugin.json", '{"name": "demo"}')
    assert _skipped_locations(tmp_path) == {LOC_PLUGIN}


def test_check_unreadable_init_is_skipped(tmp_path: Path) -> None:
    skill = _consistent_skill(tmp_path)
    (skill / "pkg").mkdir()
    (skill / "pkg" / "__init__.py").write_bytes(b"\xff\xfe__version__ = '1.0.0'\n")
    [s] = check_skill_versions(tmp_path).skipped
    assert "pkg/__init__.py" in s.location


def test_check_unreadable_skill_md_is_skipped(tmp_path: Path) -> None:
    skill = _consistent_skill(tmp_path)
    (skill / "SKILL.md").write_bytes(b"\xff\xfe---\n")
    [s] = check_skill_versions(tmp_path).skipped
    assert s.location == "SKILL.md"


def test_check_missing_authority_is_reported_even_without_derived(tmp_path: Path) -> None:
    _write(tmp_path / "demo" / "SKILL.md", "---\nname: demo\n---\n# demo\n")
    _write(tmp_path / "demo" / "CHANGELOG.md", "# demo\n\n**Version**: 1.0.0 — x\n")
    check = check_skill_versions(tmp_path)
    assert check.missing_authority == ["demo"]
    assert not check.ok


def test_failure_message_states_remedy(tmp_path: Path) -> None:
    skill = _consistent_skill(tmp_path, "1.1.0")
    _write(skill / "pyproject.toml", '[project]\nname = "demo"\nversion = "1.0.0"\n')
    message = format_version_check_failure(check_skill_versions(tmp_path))
    assert "demo: pyproject.toml [project].version 為 1.0.0，應為 1.1.0" in message
    assert "以 metadata.version 為準，補齊衍生住址" in message
    assert "sync-pull 自動解版號衝突後" in message


# ============================================================================
# 閘門：本專案 .claude/skills/ 每個 skill 的版號住址必須一致
# （用戶裁定 2026-11-19：分歧、讀不出版號、缺權威欄位皆紅燈）
# ============================================================================


def test_real_skills_dir_version_locations_consistent() -> None:
    import pytest

    skills_dir = Path(__file__).resolve().parents[2] / "skills"
    if not skills_dir.is_dir():
        pytest.skip("此環境無 .claude/skills/ 目錄，略過實測")
    check = check_skill_versions(skills_dir)
    assert check.ok, format_version_check_failure(check)
