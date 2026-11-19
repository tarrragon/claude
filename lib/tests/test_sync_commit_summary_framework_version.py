#!/usr/bin/env python3
"""sync push 摘要剝除：保留框架自身版本號，consumer 版本號照常剝除。

剝除規則原本把所有 `v\\d+.\\d+.\\d+` 換成「某版本」，連框架自己的版本號也剝掉，
推到 canonical 的 CHANGELOG 因此失去版本追溯。保留範圍是「框架當前主版號系列中
已知的版本」：`.claude/VERSION` 加上 `.claude/CHANGELOG.md` 的 `## [x.y.z]` 標題，
且主版號與 VERSION 相同。每組情境都附「不在保留集合」的對照，避免保留邏輯退化為
一律保留時測試照綠。
"""

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.sync_commit_summary import (  # noqa: E402
    categorize_commits,
    framework_version_set,
    strip_project_specific_info,
)

# 守衛與測試用同一判準判定「是否含 ticket ID」
_GUARD_SCRIPT = (
    Path(__file__).resolve().parents[2] / "hooks" / "reference-stability-rule8-guard-hook.py"
)
_guard_spec = importlib.util.spec_from_file_location("rule8_guard_for_summary", _GUARD_SCRIPT)
assert _guard_spec and _guard_spec.loader
guard_mod = importlib.util.module_from_spec(_guard_spec)
sys.modules["rule8_guard_for_summary"] = guard_mod
_guard_spec.loader.exec_module(guard_mod)  # type: ignore[union-attr]


KEEP = frozenset({"3.3.0", "3.3.1"})


def _claude_dir(tmp_path: Path, version: str, headings: list[str]) -> Path:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    body = "".join(f"## [{h}] - 2026-11-01\n\n- 條目\n\n" for h in headings)
    (claude / "CHANGELOG.md").write_text(f"# CHANGELOG\n\n{body}", encoding="utf-8")
    return claude


# --- 三情形 -------------------------------------------------------------------


def test_framework_version_is_kept():
    result = strip_project_specific_info("對齊框架 v3.3.1 的同步規則", keep_versions=KEEP)
    assert result == "對齊框架 v3.3.1 的同步規則"
    assert guard_mod.find_ticket_id_hits(result) == []


def test_consumer_version_is_still_stripped():
    result = strip_project_specific_info("回滾至 v0.31.0 之前的行為", keep_versions=KEEP)
    assert result == "回滾至 某版本 之前的行為"


def test_framework_and_consumer_versions_together():
    result = strip_project_specific_info(
        "專案 v1.4.0 改用框架 v3.3.0 的 W2-015 寫法", keep_versions=KEEP
    )
    assert result == "專案 某版本 改用框架 v3.3.0 的 某票 寫法"
    assert guard_mod.find_ticket_id_hits(result) == []


def test_ticket_id_with_framework_version_prefix_is_still_stripped():
    result = strip_project_specific_info("修正 3.3.1-W1-007 的回歸", keep_versions=KEEP)
    assert result == "修正 某票 的回歸"
    assert guard_mod.find_ticket_id_hits(result) == []


def test_empty_keep_set_strips_framework_version_contrast():
    result = strip_project_specific_info("對齊框架 v3.3.1", keep_versions=frozenset())
    assert result == "對齊框架 某版本"


# --- 保留集合的來源 -----------------------------------------------------------


def test_framework_version_set_limits_to_current_major(tmp_path):
    claude = _claude_dir(tmp_path, "3.3.1", ["3.3.1", "3.3.0", "2.90.0", "1.0.0"])
    assert framework_version_set(claude) == frozenset({"3.3.1", "3.3.0"})


def test_framework_version_set_includes_version_file_without_heading(tmp_path):
    claude = _claude_dir(tmp_path, "3.4.0", ["3.3.1"])
    assert framework_version_set(claude) == frozenset({"3.4.0", "3.3.1"})


def test_framework_version_set_empty_when_version_missing(tmp_path, capsys):
    claude = tmp_path / ".claude"
    claude.mkdir()
    assert framework_version_set(claude) == frozenset()
    assert "VERSION" in capsys.readouterr().err


def test_default_keep_set_comes_from_this_claude_dir():
    real_version = (
        Path(__file__).resolve().parents[2] / "VERSION"
    ).read_text(encoding="utf-8").strip()
    result = strip_project_specific_info(f"框架 v{real_version} 發版")
    assert result == f"框架 v{real_version} 發版"


def test_categorize_commits_keeps_framework_version():
    real_version = (
        Path(__file__).resolve().parents[2] / "VERSION"
    ).read_text(encoding="utf-8").strip()
    categories = categorize_commits(
        [f"docs: 記錄 v{real_version} 的遷移步驟", "fix: 修正 v0.31.0 的回歸"]
    )
    assert categories["docs"] == [f"記錄 v{real_version} 的遷移步驟"]
    assert categories["fix"] == ["修正 某版本 的回歸"]
