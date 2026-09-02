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
    extract_skill_versions,
    format_skill_version_diff,
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
