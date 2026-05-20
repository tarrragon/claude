"""Tests for sync-claude-push.py revert commit classification & summary.

涵蓋三案例：
  (a) 純 revert（無對應原 commit）
  (b) revert + 原 commit 同批（淨效應：只剩 revert 行 + 註記原 commit）
  (c) revert 不同類型 commit（revert 與其他 type 並列，無抵銷）

額外覆蓋：
  - parse_commit_type 對 git 原生 `Revert "..."` 的識別
  - parse_revert_info 三種格式
  - generate_commit_summary 中 revert 行的順序與註記
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
    """案例 (a)：純 revert，無對應原 commit 同批。"""
    subjects = [
        'Revert "chore(0.18.0-W14-031): migrate hook-logs path"',
    ]
    cats = sync_mod.categorize_commits(subjects)
    assert "revert" in cats
    assert len(cats["revert"]) == 1
    entry = cats["revert"][0]
    assert "原 commit" in entry
    assert "W14-031" in entry or "0.18.0-W14-031" in entry
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
