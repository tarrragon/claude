"""Tests for update_changelog() 對 old_content 套用 strip_project_specific_info（0.2.1-W3-1253）。

涵蓋三種 ticket ID 形態的剝除，以及無 ID 內文逐位元不變的不變式：
  - 版本化 ticket ID（如 0.2.1-W3-868）
  - 裸格式 ticket ID（如 W3-1226）
  - revert 句中 ticket ID（如「原 commit: 0.2.1-W3-868」）

注意：new_entry（本次新版本標頭，如 `## [0.2.2]`）本就未經剝除（只有
old_content 是本票範圍），其版本號會命中裸版本號 pattern，故「0 命中」
的驗證只針對 old_content 對應的輸出片段，非整檔（整檔含 new_entry 的
裸版本號恆會命中，非本票缺陷）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# sync-claude-push.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_changelog_strip", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_changelog_strip"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _old_content_portion(output: str) -> str:
    """從 update_changelog() 輸出中取出對應 old_content 的片段（new_entry 之後）。"""
    marker = "---\n\n"
    idx = output.index(marker)
    return output[idx + len(marker):]


def test_versioned_ticket_id_stripped_from_old_content(tmp_path: Path) -> None:
    old_content = "## [1.0.0] - 2026-09-01\n\n### Summary\n完成 0.2.1-W3-868 修正\n\n---\n\n"
    sync_mod.update_changelog(tmp_path, "0.2.2", "測試訊息", old_content)

    output = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    old_portion = _old_content_portion(output)

    assert "0.2.1-W3-868" not in old_portion
    assert sync_mod.strip_project_specific_info(old_portion) == old_portion.strip()


def test_bare_ticket_id_stripped_from_old_content(tmp_path: Path) -> None:
    old_content = "## [1.0.0] - 2026-09-01\n\n### Summary\n修正 W3-1226 問題\n\n---\n\n"
    sync_mod.update_changelog(tmp_path, "0.2.2", "測試訊息", old_content)

    output = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    old_portion = _old_content_portion(output)

    assert "W3-1226" not in old_portion
    assert sync_mod.strip_project_specific_info(old_portion) == old_portion.strip()


def test_revert_sentence_ticket_id_stripped_from_old_content(tmp_path: Path) -> None:
    old_content = (
        "## [1.0.0] - 2026-09-01\n\n### Summary\n"
        "回退變更（原 commit: 0.2.1-W3-868）\n\n---\n\n"
    )
    sync_mod.update_changelog(tmp_path, "0.2.2", "測試訊息", old_content)

    output = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    old_portion = _old_content_portion(output)

    assert "0.2.1-W3-868" not in old_portion
    assert sync_mod.strip_project_specific_info(old_portion) == old_portion.strip()


def test_old_content_without_ticket_id_unchanged_byte_for_byte(tmp_path: Path) -> None:
    old_content = "## [1.0.0] - 2026-09-01\n\n### Summary\n一般說明文字，無任何 ID\n\n---\n\n"
    sync_mod.update_changelog(tmp_path, "0.2.2", "測試訊息", old_content)

    output = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

    assert output.endswith(old_content)


def test_new_entry_still_prepended(tmp_path: Path) -> None:
    old_content = "## [1.0.0] - 2026-09-01\n\n### Summary\n舊條目\n\n---\n\n"
    sync_mod.update_changelog(tmp_path, "0.2.2", "新版本訊息", old_content)

    output = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

    assert output.startswith("## [0.2.2]")
    assert "新版本訊息" in output
