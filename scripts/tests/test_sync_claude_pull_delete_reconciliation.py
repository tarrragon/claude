"""Tests for sync-claude-pull.py 孤兒清理兩道防護（PC-APP-002，0.32.0-W1-007）。

背景（PC-APP-002）：
  c014eccf「清 16 孤兒」commit 訊息宣稱刪 16，實際 diff-filter=D 刪 30，超出的
  14 個含 preserve 標記的專案特化檔被靜默誤刪。三因素共振：孤兒判定只問上游有無、
  preserve 機制未生效、宣稱數遮蔽實際刪除數。

本檔涵蓋兩道內建防護的 acceptance：
  (a) preserve-aware 孤兒清理：cleanup_stale_files 對 preserve 命中檔不刪（原地保留）。
  (b) 宣稱 vs 實際刪除對帳：reconcile_declared_deletions 比對宣稱刪除數與實際刪除
      清單，不符時 stdout 完整列出超出宣稱的檔（消除宣稱遮蔽實際的盲區）。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# sync-claude-pull.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_delete_reconciliation", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_delete_reconciliation"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers
# ============================================================================

def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.t"], cwd=root, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, capture_output=True)
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"], cwd=root, capture_output=True
    )


def _git_add_commit(root: Path, *rel_paths: str) -> None:
    subprocess.run(["git", "add", *rel_paths], cwd=root, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=root, capture_output=True)


# ============================================================================
# 防護 (a)：preserve-aware 孤兒清理（preserve 命中檔不被刪）
# ============================================================================

def test_preserve_file_not_deleted_when_upstream_absent(tmp_path):
    """preserve 命中之專案特化檔即使上游無，孤兒清理也不刪、不移、不計入 removed。

    重現 PC-APP-002 核心情境：本地有、上游 HEAD 無之專案特化檔，列於 preserve 清單。
    """
    root = tmp_path
    _init_git_repo(root)
    claude = root / ".claude"
    special = claude / "error-patterns" / "process-compliance" / "PC-177-local.md"
    special.parent.mkdir(parents=True)
    special.write_text("project-specific pattern\n", encoding="utf-8")
    _git_add_commit(
        root, ".claude/error-patterns/process-compliance/PC-177-local.md"
    )

    preserve = {"error-patterns/process-compliance/PC-177-local.md"}
    removed, preserved_as_conflict = pull.cleanup_stale_files(
        claude, remote_files=set(), preserve=preserve, project_root=root
    )

    assert special.exists(), "preserve 命中之專案特化檔應原地保留，不被刪除"
    assert not any("PC-177-local" in r for r in removed), "不應計入真刪 removed"
    assert not any(
        "PC-177-local" in p for p in preserved_as_conflict
    ), "preserve 命中不應移至 .sync-conflicts（與 git-tracked 轉存路徑區隔）"
    conflicts_root = claude / pull.SYNC_CONFLICTS_DIR
    assert not conflicts_root.exists() or not list(
        conflicts_root.rglob("*PC-177-local*")
    ), "preserve 命中檔不應出現在 .sync-conflicts/"


def test_non_preserve_untracked_still_removed_alongside_preserve(tmp_path):
    """preserve 過濾不波及其他孤兒：非 preserve 的 untracked stale 檔仍正常刪除。"""
    root = tmp_path
    _init_git_repo(root)
    claude = root / ".claude"
    claude.mkdir()
    keep = claude / "keep.md"
    keep.write_text("project special\n", encoding="utf-8")
    _git_add_commit(root, ".claude/keep.md")
    junk = claude / "runtime" / "junk.txt"
    junk.parent.mkdir(parents=True)
    junk.write_text("runtime garbage\n", encoding="utf-8")  # untracked stale

    removed, _preserved = pull.cleanup_stale_files(
        claude, remote_files=set(), preserve={"keep.md"}, project_root=root
    )

    assert keep.exists(), "preserve 命中檔保留"
    assert not junk.exists(), "非 preserve 的 untracked stale 仍應刪除"
    assert any("junk.txt" in r for r in removed)


# ============================================================================
# 防護 (b)：宣稱 vs 實際刪除數對帳
# ============================================================================

def test_reconcile_silent_when_counts_match(capsys):
    """宣稱數 == 實際刪除數 → 對帳通過，回 (True, [])，stdout 無超出告警。"""
    actual_removed = ["a.md", "b.md", "c.md"]

    matched, excess = pull.reconcile_declared_deletions(
        declared_count=3, actual_removed=actual_removed
    )

    assert matched is True
    assert excess == []
    out = capsys.readouterr().out
    assert "超出宣稱" not in out


def test_reconcile_flags_excess_and_lists_files(capsys):
    """實際刪除 > 宣稱 → 回 (False, 超出清單)，stdout 完整列出超出宣稱的檔。

    重現 c014eccf：宣稱清 16、實際刪 30。對帳必須揭露超出的 14 檔。
    """
    declared = 16
    actual_removed = [f"error-patterns/PC-{n}.md" for n in range(30)]

    matched, excess = pull.reconcile_declared_deletions(
        declared_count=declared, actual_removed=actual_removed
    )

    assert matched is False
    assert len(excess) == 30 - 16, "超出清單應為實際數減宣稱數"
    out = capsys.readouterr().out
    assert "宣稱" in out and "16" in out
    assert "30" in out, "stdout 應同時呈現實際刪除數"
    # 超出部分的具體檔名須逐一列出（不可只給數字）
    for rel in excess:
        assert rel in out


def test_reconcile_excess_uses_tail_of_removed(capsys):
    """超出清單取實際刪除清單尾段（超過宣稱數的部分），順序穩定。"""
    actual_removed = ["x1", "x2", "x3", "x4", "x5"]

    _matched, excess = pull.reconcile_declared_deletions(
        declared_count=2, actual_removed=actual_removed
    )

    assert excess == ["x3", "x4", "x5"]


def test_reconcile_fewer_than_declared_also_flagged(capsys):
    """實際刪除 < 宣稱 → 仍視為不符（回 False），但無超出清單可列。"""
    matched, excess = pull.reconcile_declared_deletions(
        declared_count=5, actual_removed=["a", "b"]
    )

    assert matched is False
    assert excess == []
    out = capsys.readouterr().out
    assert "宣稱" in out
