"""Tests for sync-claude-pull.py 上游刪+本地分歧靜默殘留通報（1.0.0-W8-037.1，缺口 1）。

背景（W8-037 重現確認）：
  上游 delta 標記某框架檔為刪除（status==D），但本地已修改過該檔（local != base），
  three_way_merge_file 回 (local_content, False)——保留本地、conflict=False、不進
  .sync-conflicts/，pull 原本完全無通報。客製過框架檔後被上游刪除的孤兒靜默殘留。

涵蓋 acceptance：
  - three_way_merge_file 兩情境：
      上游刪 + 本地改（local != base）→ 回 (local_content, False)（保留本地，待通報）
      上游刪 + 本地未改（local == base）→ 回 (None, False)（自動跟刪，不通報）
  - apply_upstream_delta 端到端：上游刪 + 本地分歧檔被收集進第三個回傳值（殘留清單）；
    上游刪 + 本地未改不入清單
  - warn_upstream_deleted_residue：有殘留時 stdout 通報（非阻擋措辭）；無殘留時靜默
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_residue", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_residue"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers
# ============================================================================

def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True,
        capture_output=True, text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@t.t"], repo)
    _git(["config", "user.name", "t"], repo)
    _git(["config", "commit.gpgsign", "false"], repo)


def _commit_all(repo: Path, msg: str) -> str:
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo),
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


# ============================================================================
# 單元：three_way_merge_file 上游刪除兩情境（airtight 重現）
# ============================================================================

def test_three_way_upstream_deleted_local_diverged_keeps_local(tmp_path):
    """上游刪 + 本地改（local != base）→ 回 (本地內容, False)：保留本地，待通報。"""
    base = b"orig\n"
    local = tmp_path / "f.md"
    local.write_bytes(b"local customized\n")  # 本地已修改（!= base）

    merged, conflict = pull.three_way_merge_file(
        base_content=base,
        local_path=local,
        upstream_path=None,  # 上游刪除此檔
        local_deleted=False,
    )

    assert merged == b"local customized\n"  # 保留本地內容
    assert conflict is False  # 非衝突 → 不進 .sync-conflicts/（正是靜默殘留路徑）


def test_three_way_upstream_deleted_local_unchanged_follows_delete(tmp_path):
    """上游刪 + 本地未改（local == base）→ 回 (None, False)：自動跟刪，不通報。"""
    base = b"orig\n"
    local = tmp_path / "f.md"
    local.write_bytes(b"orig\n")  # 本地與 base 相同

    merged, conflict = pull.three_way_merge_file(
        base_content=base,
        local_path=local,
        upstream_path=None,  # 上游刪除此檔
        local_deleted=False,
    )

    assert merged is None  # 跟著刪
    assert conflict is False


# ============================================================================
# 整合：apply_upstream_delta 殘留清單收集
# ============================================================================

def _setup_upstream_deletion(tmp_path):
    """建立上游刪除兩檔（一檔本地改、一檔本地未改）的 fixture。

    回傳 (project_root, upstream_repo, base_sha)。
    """
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "diverged.md").write_text("base line\n", encoding="utf-8")
    (rules / "untouched.md").write_text("base line\n", encoding="utf-8")
    base = _commit_all(upstream, "base")

    # 上游 HEAD：刪除兩檔
    (rules / "diverged.md").unlink()
    (rules / "untouched.md").unlink()
    _commit_all(upstream, "head deletes both")

    # 本地 project：複製 base 後，diverged 本地改、untouched 維持 base
    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "diverged.md").write_text(
        "local customized\n", encoding="utf-8"
    )  # 本地改 → 殘留候選
    (claude / "rules" / "untouched.md").write_text(
        "base line\n", encoding="utf-8"
    )  # 未改 → 自動跟刪
    return project_root, upstream, base


def test_apply_delta_collects_diverged_residue(tmp_path):
    """上游刪 + 本地改 → 入殘留清單；上游刪 + 本地未改 → 不入。"""
    project_root, upstream, base = _setup_upstream_deletion(tmp_path)
    claude = project_root / ".claude"

    applied, conflicts, residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    # 本地改的孤兒被保留（檔仍在）並列入殘留清單
    assert (claude / "rules" / "diverged.md").exists()
    assert "rules/diverged.md" in residue

    # 本地未改的檔自動跟刪，不入清單
    assert not (claude / "rules" / "untouched.md").exists()
    assert "rules/untouched.md" not in residue

    # 非衝突路徑
    assert conflicts == []
    assert applied >= 1


# ============================================================================
# 通報函式 warn_upstream_deleted_residue
# ============================================================================

def test_warn_residue_prints_non_blocking_notice(capsys):
    """有殘留時 stdout 列出清單，措辭為非阻擋提醒。"""
    pull.warn_upstream_deleted_residue(["rules/diverged.md", "rules/other.md"])
    out = capsys.readouterr().out
    assert "上游已刪除" in out
    assert "rules/diverged.md" in out
    assert "rules/other.md" in out
    # 非阻擋措辭：提示人工判斷孤兒/客製，不自動刪
    assert "孤兒" in out
    assert "客製" in out


def test_warn_residue_silent_when_empty(capsys):
    """無殘留時不輸出任何提醒。"""
    pull.warn_upstream_deleted_residue([])
    out = capsys.readouterr().out
    assert out == ""
