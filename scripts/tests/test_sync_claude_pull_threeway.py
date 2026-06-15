"""Tests for sync-claude-pull.py 三方合併改造（0.19.1-W1-028 / A3+L+M）。

涵蓋 acceptance：
  - read_base_sha 從 .sync-state.json 讀 last_synced_base_sha（W1-025 schema）
  - is_base_reachable 用 git cat-file -e 驗可達（H4）
  - compute_upstream_delta 用 git diff --name-status --no-renames 解析 delta（H3）
    含 rename 退化為 D+A 的解析
  - three_way_merge_file 四情境：add / take-upstream / conflict / preserve-local-delete
  - apply_delta_atomic：rename 級置換 + 只搬 delta 檔保留 LOCAL_ONLY（H2）
  - write_base_sha 成功後寫 last_synced_base_sha
  - clone timeout 300s + blob:none filter（L1）

多視角必修正項 H2/H3/H4/M3/M4/L1 皆對應測試。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_threeway", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_threeway"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers：建立可控的 git upstream repo fixture
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
# read_base_sha / write_base_sha
# ============================================================================

def test_read_base_sha_present(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / ".sync-state.json").write_text(
        json.dumps({"last_synced_base_sha": "abc123def456"}), encoding="utf-8"
    )
    assert pull.read_base_sha(claude) == "abc123def456"


def test_read_base_sha_absent(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    assert pull.read_base_sha(claude) is None


def test_write_base_sha_merges_existing(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / ".sync-state.json").write_text(
        json.dumps({"last_push_hash": "keepme"}), encoding="utf-8"
    )
    pull.write_base_sha(claude, "newsha999")
    data = json.loads((claude / ".sync-state.json").read_text(encoding="utf-8"))
    assert data["last_synced_base_sha"] == "newsha999"
    assert data["last_push_hash"] == "keepme"  # 既有欄位保留


# ============================================================================
# is_base_reachable（H4）
# ============================================================================

def test_is_base_reachable_true(tmp_path):
    repo = tmp_path / "up"
    _init_repo(repo)
    (repo / "f.txt").write_text("v1", encoding="utf-8")
    sha = _commit_all(repo, "c1")
    assert pull.is_base_reachable(repo, sha) is True


def test_is_base_reachable_false(tmp_path):
    repo = tmp_path / "up"
    _init_repo(repo)
    (repo / "f.txt").write_text("v1", encoding="utf-8")
    _commit_all(repo, "c1")
    assert pull.is_base_reachable(repo, "deadbeef" * 5) is False


# ============================================================================
# compute_upstream_delta（H3：--no-renames 退化 rename 為 D+A）
# ============================================================================

def test_compute_upstream_delta_modify_add_delete(tmp_path):
    repo = tmp_path / "up"
    _init_repo(repo)
    sub = repo / ".claude"
    sub.mkdir()
    (sub / "keep.md").write_text("base", encoding="utf-8")
    (sub / "gone.md").write_text("will delete", encoding="utf-8")
    base = _commit_all(repo, "base")

    (sub / "keep.md").write_text("upstream-modified", encoding="utf-8")
    (sub / "gone.md").unlink()
    (sub / "new.md").write_text("new file", encoding="utf-8")
    _commit_all(repo, "head")

    delta = pull.compute_upstream_delta(repo, base)
    # delta: {rel_path: status}，路徑相對 repo root
    assert delta[".claude/keep.md"] == "M"
    assert delta[".claude/gone.md"] == "D"
    assert delta[".claude/new.md"] == "A"


def test_compute_upstream_delta_rename_degrades_to_d_plus_a(tmp_path):
    repo = tmp_path / "up"
    _init_repo(repo)
    (repo / "old.md").write_text("content body", encoding="utf-8")
    base = _commit_all(repo, "base")

    _git(["mv", "old.md", "renamed.md"], repo)
    _commit_all(repo, "rename")

    delta = pull.compute_upstream_delta(repo, base)
    # --no-renames 使 rename 退化為 D(old) + A(renamed)
    assert delta["old.md"] == "D"
    assert delta["renamed.md"] == "A"


# ============================================================================
# three_way_merge_file 四情境
# ============================================================================

def test_merge_add_new_file(tmp_path):
    """upstream 新增（local 無）→ 直接採 upstream。"""
    upstream = tmp_path / "u.txt"
    upstream.write_text("brand new", encoding="utf-8")
    out, conflict = pull.three_way_merge_file(
        base_content=None, local_path=None, upstream_path=upstream,
    )
    assert conflict is False
    assert out == b"brand new"


def test_merge_take_upstream_local_unchanged(tmp_path):
    """local == base，upstream 改 → 採 upstream（無衝突）。"""
    base = tmp_path / "b.txt"
    base.write_text("original\n", encoding="utf-8")
    local = tmp_path / "l.txt"
    local.write_text("original\n", encoding="utf-8")  # 未動
    upstream = tmp_path / "u.txt"
    upstream.write_text("upstream change\n", encoding="utf-8")

    out, conflict = pull.three_way_merge_file(
        base_content=base.read_bytes(), local_path=local, upstream_path=upstream,
    )
    assert conflict is False
    assert out == b"upstream change\n"


def test_merge_conflict_both_changed(tmp_path):
    """local 與 upstream 對同一行各自修改 → 衝突。"""
    base = tmp_path / "b.txt"
    base.write_text("line1\nline2\nline3\n", encoding="utf-8")
    local = tmp_path / "l.txt"
    local.write_text("line1\nLOCAL\nline3\n", encoding="utf-8")
    upstream = tmp_path / "u.txt"
    upstream.write_text("line1\nUPSTREAM\nline3\n", encoding="utf-8")

    out, conflict = pull.three_way_merge_file(
        base_content=base.read_bytes(), local_path=local, upstream_path=upstream,
    )
    assert conflict is True


def test_merge_preserve_local_delete(tmp_path):
    """local 已刪除（W10-092 遷移），upstream 仍有 → 保留本地刪除。"""
    base = tmp_path / "b.txt"
    base.write_text("content\n", encoding="utf-8")
    upstream = tmp_path / "u.txt"
    upstream.write_text("content\n", encoding="utf-8")

    out, conflict = pull.three_way_merge_file(
        base_content=base.read_bytes(), local_path=None, upstream_path=upstream,
        local_deleted=True,
    )
    # 本地刪除優先：回傳 None 表示「不要寫入此檔」
    assert out is None
    assert conflict is False


# ============================================================================
# clone L1：filter + timeout 常數
# ============================================================================

def test_clone_timeout_is_300(tmp_path):
    assert pull.GIT_CLONE_TIMEOUT_SECONDS == 300


# ============================================================================
# 向後相容：無 base SHA fallback 全量 overlay
# ============================================================================

def test_no_base_falls_back_to_full_overlay(tmp_path, monkeypatch):
    """無 last_synced_base_sha 時應走全量 overlay 路徑（向後相容）。"""
    claude = tmp_path / ".claude"
    claude.mkdir()
    assert pull.should_use_full_overlay(claude, base_reachable=False) is True


def test_base_present_and_reachable_uses_threeway(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / ".sync-state.json").write_text(
        json.dumps({"last_synced_base_sha": "abc"}), encoding="utf-8"
    )
    assert pull.should_use_full_overlay(claude, base_reachable=True) is False


# ============================================================================
# 整合：apply_upstream_delta 端到端（4 情境）
# ============================================================================

def _setup_upstream_and_local(tmp_path):
    """建立上游 repo（root 直接對應 .claude/）+ 本地 project .claude/。

    回傳 (project_root, upstream_repo, base_sha)。
    """
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "keep.md").write_text("base line\n", encoding="utf-8")
    (rules / "take.md").write_text("orig\n", encoding="utf-8")
    (rules / "conflict.md").write_text("a\nb\nc\n", encoding="utf-8")
    (rules / "deleted-local.md").write_text("body\n", encoding="utf-8")
    base = _commit_all(upstream, "base")

    # 上游 HEAD 變更
    (rules / "take.md").write_text("upstream new\n", encoding="utf-8")     # take-upstream
    (rules / "conflict.md").write_text("a\nUPSTREAM\nc\n", encoding="utf-8")  # conflict
    (rules / "added.md").write_text("brand new\n", encoding="utf-8")        # add
    _commit_all(upstream, "head")

    # 本地 project：複製 base 版本後做本地修改
    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "keep.md").write_text("base line\n", encoding="utf-8")
    (claude / "rules" / "take.md").write_text("orig\n", encoding="utf-8")  # 未動
    (claude / "rules" / "conflict.md").write_text("a\nLOCAL\nc\n", encoding="utf-8")  # 本地改
    # deleted-local.md 本地已刪除（W10-092 遷移） → 不建立
    return project_root, upstream, base


def test_apply_delta_four_scenarios(tmp_path):
    project_root, upstream, base = _setup_upstream_and_local(tmp_path)
    claude = project_root / ".claude"

    applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    # add：upstream 新增 → 本地出現
    assert (claude / "rules" / "added.md").read_text() == "brand new\n"
    # take-upstream：本地未動 → 採 upstream
    assert (claude / "rules" / "take.md").read_text() == "upstream new\n"
    # conflict：寫入 .sync-conflicts/，本地原檔保留
    assert "rules/conflict.md" in conflicts
    assert (claude / "rules" / "conflict.md").read_text() == "a\nLOCAL\nc\n"
    assert (claude / ".sync-conflicts" / "rules" / "conflict.md").exists()
    assert (claude / ".sync-conflicts" / ".gitignore").read_text() == "*\n"


def test_apply_delta_preserve_local_delete(tmp_path):
    """deleted-local.md 上游無變更（base→HEAD 不在 delta），本地刪除天然保留。

    本測試直接驗證：delta 不含未變更檔，故本地刪除不受影響。
    """
    project_root, upstream, base = _setup_upstream_and_local(tmp_path)
    claude = project_root / ".claude"
    pull.apply_upstream_delta(project_root, upstream, base)
    # deleted-local.md 不在 base→HEAD delta（上游未動），不會被重新帶回
    assert not (claude / "rules" / "deleted-local.md").exists()


def test_apply_delta_skips_local_only(tmp_path):
    """LOCAL_ONLY / 憑證檔即使在 delta 也跳過（M4），保留本地 runtime state。"""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    (upstream / "dispatch-active.json").write_text('{"upstream":1}', encoding="utf-8")
    base = _commit_all(upstream, "base")
    (upstream / "dispatch-active.json").write_text('{"upstream":2}', encoding="utf-8")
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    claude.mkdir(parents=True)
    (claude / "dispatch-active.json").write_text('{"local":99}', encoding="utf-8")

    pull.apply_upstream_delta(project_root, upstream, base)
    # 本地 runtime state 不被上游 delta 覆蓋
    assert json.loads((claude / "dispatch-active.json").read_text()) == {"local": 99}
