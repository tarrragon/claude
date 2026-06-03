"""Tests for sync-claude-push.py git-archive 改造（0.19.1-W1-029，C1+K+M1+M5）.

涵蓋：
  - stage_tracked_tree（C1）：以 git archive HEAD -- .claude 取 tracked 樹解到 staging
  - should_exclude 過濾在 git archive 來源上仍生效（M1：tracked 但須排除者如
    settings.local.json / .sync-state.json / 憑證仍被擋）
  - git rm 的檔自然不在 archive → 不出現於 staging（K：刪除傳播）
  - ensure_committed（M5）：有未 commit / 未 staged 的 .claude/ 變更時 abort
  - write_base_sha（單一 last_synced_base_sha，禁雙欄位，與 W1-025 schema 一致）
  - 向後相容：無 base 時 fallback（read_base_sha 回 None）
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# sync-claude-push.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _init_repo_with_claude(root: Path) -> Path:
    """建立含 .claude/ 的 git repo，回傳 .claude 路徑。"""
    _git(["init"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "t"], root)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "rules.md").write_text("# tracked rule\n", encoding="utf-8")
    _git(["add", ".claude/rules.md"], root)
    _git(["commit", "-m", "init"], root)
    return claude


# ---------- C1: stage_tracked_tree 取 git tracked 樹 ----------

def test_stage_tracked_tree_extracts_tracked_files(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    claude = _init_repo_with_claude(root)
    (claude / "sub").mkdir()
    (claude / "sub" / "deep.md").write_text("# deep\n", encoding="utf-8")
    _git(["add", ".claude/sub/deep.md"], root)
    _git(["commit", "-m", "add deep"], root)

    staging = tmp_path / "staging"
    count = sync_mod.stage_tracked_tree(root, staging)

    assert (staging / "rules.md").exists()
    assert (staging / "sub" / "deep.md").exists()
    assert count == 2


# ---------- C1: archive 來源只含 tracked，untracked 不入 staging ----------

def test_untracked_file_not_staged(tmp_path: Path):
    """git archive 只取 tracked 樹：untracked 機密檔自然不外洩（消滅 W1-019 特例）。"""
    root = tmp_path / "proj"
    root.mkdir()
    claude = _init_repo_with_claude(root)
    # untracked 機密檔（檔名不在黑名單內）—— 舊 copy_filtered 會外洩，git archive 不會
    (claude / "my-api-token.txt").write_text("SECRET=abc\n", encoding="utf-8")

    staging = tmp_path / "staging"
    sync_mod.stage_tracked_tree(root, staging)

    assert not (staging / "my-api-token.txt").exists()


# ---------- M1: should_exclude 過濾在 archive 來源上仍生效 ----------

def test_tracked_but_excluded_file_filtered(tmp_path: Path):
    """tracked 但須排除者（settings.local.json 等）git archive 取得後仍須被擋。"""
    root = tmp_path / "proj"
    root.mkdir()
    claude = _init_repo_with_claude(root)
    # 一個 tracked 但屬 local-only 的檔（極端情境：誤被 commit）
    (claude / "settings.local.json").write_text("{}\n", encoding="utf-8")
    _git(["add", "-f", ".claude/settings.local.json"], root)
    _git(["commit", "-m", "track local"], root)

    staging = tmp_path / "staging"
    sync_mod.stage_tracked_tree(root, staging)

    # staging 內含此檔（git archive 取 tracked 全部），但 should_exclude 判定為 True
    assert sync_mod.should_exclude(Path("settings.local.json")) is True


# ---------- K: git rm 的檔不在 archive（刪除傳播） ----------

def test_git_rm_file_absent_from_staging(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    claude = _init_repo_with_claude(root)
    (claude / "obsolete.md").write_text("# old\n", encoding="utf-8")
    _git(["add", ".claude/obsolete.md"], root)
    _git(["commit", "-m", "add obsolete"], root)
    # git rm（從 tracked 樹移除並 commit）
    _git(["rm", ".claude/obsolete.md"], root)
    _git(["commit", "-m", "remove obsolete"], root)

    staging = tmp_path / "staging"
    sync_mod.stage_tracked_tree(root, staging)

    assert not (staging / "obsolete.md").exists()
    assert (staging / "rules.md").exists()


# ---------- M5: ensure_committed ----------

def test_ensure_committed_clean(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    _init_repo_with_claude(root)
    assert sync_mod.ensure_committed(root) is True


def test_ensure_committed_unstaged_change(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    claude = _init_repo_with_claude(root)
    (claude / "rules.md").write_text("# modified\n", encoding="utf-8")  # 改了未 add
    assert sync_mod.ensure_committed(root) is False


def test_ensure_committed_staged_uncommitted(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    claude = _init_repo_with_claude(root)
    (claude / "new.md").write_text("# new\n", encoding="utf-8")
    _git(["add", ".claude/new.md"], root)  # staged 但未 commit
    assert sync_mod.ensure_committed(root) is False


# ---------- base_sha schema：單一 last_synced_base_sha ----------

def test_write_base_sha_single_field(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    sync_mod.write_base_sha(claude, "deadbeef" * 5)

    state = json.loads((claude / ".sync-state.json").read_text(encoding="utf-8"))
    assert state["last_synced_base_sha"] == "deadbeef" * 5
    # 禁雙欄位：不得出現 upstream_base_sha / last_pull_base_sha 等
    assert "upstream_base_sha" not in state
    assert "last_pull_base_sha" not in state


def test_write_base_sha_preserves_existing(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / ".sync-state.json").write_text(
        json.dumps({"last_push_hash": "abc123", "last_push_version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    sync_mod.write_base_sha(claude, "f" * 40)

    state = json.loads((claude / ".sync-state.json").read_text(encoding="utf-8"))
    assert state["last_synced_base_sha"] == "f" * 40
    assert state["last_push_hash"] == "abc123"  # 既有欄位保留


def test_read_base_sha_missing_returns_none(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    # 向後相容：無 .sync-state.json → None（觸發 fallback）
    assert sync_mod.read_base_sha(claude) is None


def test_read_base_sha_roundtrip(tmp_path: Path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    sync_mod.write_base_sha(claude, "cafe" * 10)
    assert sync_mod.read_base_sha(claude) == "cafe" * 10
