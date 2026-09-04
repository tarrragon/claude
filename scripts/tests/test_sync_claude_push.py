"""Tests for sync-claude-push.py revert commit classification & summary.

涵蓋三案例：
  (a) 純 revert（無對應原 commit）
  (b) revert + 原 commit 同批（淨效應：只剩 revert 行 + 註記原 commit）
  (c) revert 不同類型 commit（revert 與其他 type 並列，無抵銷）

額外覆蓋：
  - parse_commit_type 對 git 原生 `Revert "..."` 的識別
  - parse_revert_info 三種格式
  - generate_commit_summary 中 revert 行的順序與註記
  - CHANGELOG 產生器不再把 revert 原 commit 的 ticket ID 寫入條目（0.2.1-W3-1224）
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# sync-claude-push.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]

# reference-stability-rule8-guard-hook.py 的 find_ticket_id_hits 是「文字是否
# 含專案 ticket ID」的唯一事實來源（守衛與測試須用同一判準，避免各自寫
# regex 導致「已剝乾淨」的結論失真——見本票 Context Bundle 指示）。
_GUARD_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "hooks"
    / "reference-stability-rule8-guard-hook.py"
)
_guard_spec = importlib.util.spec_from_file_location(
    "reference_stability_rule8_guard", _GUARD_SCRIPT
)
assert _guard_spec and _guard_spec.loader
guard_mod = importlib.util.module_from_spec(_guard_spec)
sys.modules["reference_stability_rule8_guard"] = guard_mod
_guard_spec.loader.exec_module(guard_mod)  # type: ignore[union-attr]


# ---------- parse_commit_type ----------

def test_parse_commit_type_conventional_revert():
    assert sync_mod.parse_commit_type("revert(W14-031): migrate logs") == (
        "revert",
        "migrate logs",
    )


def test_parse_commit_type_git_default_revert():
    assert sync_mod.parse_commit_type(
        'Revert "chore(W14-031): migrate logs to new path"'
    ) == ("revert", "chore(W14-031): migrate logs to new path")


def test_parse_commit_type_non_revert_unchanged():
    assert sync_mod.parse_commit_type("feat(scope): add X") == ("feat", "add X")
    assert sync_mod.parse_commit_type("plain subject") == ("other", "plain subject")


# ---------- parse_revert_info ----------

def test_parse_revert_info_conventional_with_ticket():
    info = sync_mod.parse_revert_info("revert(W14-031): chore: migrate logs W14-031")
    assert info is not None
    original, ref = info
    assert "migrate logs" in original
    assert ref == "W14-031"


def test_parse_revert_info_git_default_with_ticket():
    info = sync_mod.parse_revert_info(
        'Revert "chore(0.18.0-W14-031): migrate hook-logs path"'
    )
    assert info is not None
    original, ref = info
    assert original.startswith("chore(")
    assert ref == "0.18.0-W14-031"


def test_parse_revert_info_with_hash_only():
    info = sync_mod.parse_revert_info('Revert "fix something abc1234def"')
    assert info is not None
    _, ref = info
    assert ref == "abc1234def"


def test_parse_revert_info_returns_none_for_non_revert():
    assert sync_mod.parse_revert_info("feat: add X") is None
    assert sync_mod.parse_revert_info("chore(W14-031): migrate") is None


# ---------- categorize_commits 三案例 ----------

def test_categorize_case_a_pure_revert():
    """案例 (a)：純 revert，無對應原 commit 同批。

    original_ref（0.18.0-W14-031）為 ticket ID 樣式，屬 consumer 專屬識別符，
    不可寫入 CHANGELOG（0.2.1-W3-1224）：「(原 commit)」保留但不含 ticket ID。
    """
    subjects = [
        'Revert "chore(0.18.0-W14-031): migrate hook-logs path"',
    ]
    cats = sync_mod.categorize_commits(subjects)
    assert "revert" in cats
    assert len(cats["revert"]) == 1
    entry = cats["revert"][0]
    assert "原 commit" in entry
    assert "W14-031" not in entry and "0.18.0-W14-031" not in entry
    # 不應該意外冒出 chore 分類
    assert "chore" not in cats


def test_categorize_case_b_revert_plus_original_net_effect():
    """案例 (b)：同批含 X 與 revert(X) → 僅保留 revert 行，X 被抵銷。"""
    subjects = [
        "chore(W14-031): migrate hook-logs path",
        'Revert "chore(W14-031): migrate hook-logs path"',
    ]
    cats = sync_mod.categorize_commits(subjects)
    # X 被抵銷，chore 不應出現（或為空）
    assert cats.get("chore", []) == []
    assert "revert" in cats
    assert len(cats["revert"]) == 1
    assert "原 commit" in cats["revert"][0]


def test_categorize_case_c_revert_different_type_no_cancel():
    """案例 (c)：revert 與不相關 commit 並列，無抵銷。"""
    subjects = [
        "feat(scope): add new feature A",
        'Revert "chore(W14-031): old migration"',
        "fix(other): bug in B",
    ]
    cats = sync_mod.categorize_commits(subjects)
    assert "feat" in cats and len(cats["feat"]) == 1
    assert "fix" in cats and len(cats["fix"]) == 1
    assert "revert" in cats and len(cats["revert"]) == 1
    assert "原 commit" in cats["revert"][0]


# ---------- generate_commit_summary ----------

def test_generate_summary_revert_listed_first():
    """revert 應排在 display_order 第一位，summary subject 含 revert。"""
    cats = {
        "feat": ["add X"],
        "revert": ["chore: old migration (原 commit: W14-031)"],
    }
    summary = sync_mod.generate_commit_summary(cats, "patch")
    first_line = summary.split("\n")[0]
    assert "revert" in first_line.lower()


def test_generate_summary_net_effect_end_to_end():
    """端到端：純 revert+原 commit 同批 → summary 不含 X，只含 revert + 註記。"""
    subjects = [
        "chore(W14-031): migrate hook-logs path",
        'Revert "chore(W14-031): migrate hook-logs path"',
    ]
    cats = sync_mod.categorize_commits(subjects)
    bump = sync_mod.suggest_version_bump(cats)
    summary = sync_mod.generate_commit_summary(cats, bump)
    # 不應有獨立的 "- chore:" detail 行（被抵銷）
    detail_lines = [line for line in summary.split("\n") if line.startswith("- ")]
    chore_lines = [line for line in detail_lines if line.startswith("- chore:")]
    assert chore_lines == [], f"chore 應被 revert 抵銷，但發現: {chore_lines}"
    # revert 行應註記原 commit
    assert "原 commit" in summary
    # Changes stats 不應該列 chore（被抵銷後 categories 不含 chore）
    stats_line = [line for line in summary.split("\n") if line.startswith("Changes:")][0]
    assert "chore" not in stats_line


# ---------- CHANGELOG 條目不含 consumer 專屬 ticket ID（0.2.1-W3-1224） ----------

def test_revert_entry_with_versioned_ticket_id_has_no_hits():
    """revert 訊息帶版本化 ticket ID（0.2.1-W3-868 樣式）時，生成的條目須通過
    守衛自身的 find_ticket_id_hits 零命中檢查（判準與守衛一致，非自訂 regex）。
    """
    subjects = [
        "revert(0.2.1-W3-868): chore: metadata sync post-completion",
    ]
    cats = sync_mod.categorize_commits(subjects)
    entry = cats["revert"][0]
    assert guard_mod.find_ticket_id_hits(entry) == []
    assert "原 commit" in entry


def test_revert_entry_with_bare_ticket_id_has_no_hits():
    """revert 訊息的原 subject 帶裸格式 ticket ID（W3-878 樣式）時同樣須零命中。"""
    subjects = [
        'Revert "chore: 還原 readme_index 欄位級 upsert 至基線 W3-878"',
    ]
    cats = sync_mod.categorize_commits(subjects)
    entry = cats["revert"][0]
    assert guard_mod.find_ticket_id_hits(entry) == []
    assert "原 commit" in entry


def test_revert_entry_with_hash_ref_still_preserved():
    """original_ref 為 commit hash（非 ticket ID）時不受剝除影響，仍寫入條目
    （既有存量條目不被改寫，見 acceptance）。"""
    subjects = ['Revert "fix something abc1234def"']
    cats = sync_mod.categorize_commits(subjects)
    entry = cats["revert"][0]
    assert "abc1234def" in entry
    assert guard_mod.find_ticket_id_hits(entry) == []


def test_is_project_specific_ref_distinguishes_ticket_id_from_hash():
    """_is_project_specific_ref 只對 ticket ID 樣式回傳 True，hash 與空字串回傳 False。"""
    assert sync_mod._is_project_specific_ref("0.2.1-W3-868") is True
    assert sync_mod._is_project_specific_ref("W3-878") is True
    assert sync_mod._is_project_specific_ref("abc1234def") is False
    assert sync_mod._is_project_specific_ref("") is False
