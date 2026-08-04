"""Tests for sync-claude-pull.py base SHA 衝突閘門（0.2.1-W3-165）。

IMP-BAL-002 根本修復第二項：base SHA 寫入移到 delta 套用成功之後，衝突路徑
不推進。涵蓋 acceptance：
  - 三方合併套用成功（無衝突）→ .sync-state.json 的 last_synced_base_sha 更新
  - 三方合併有未解衝突 → last_synced_base_sha 維持原值不推進（且 conflicts
    非空，證明確實走到衝突路徑，非誤判為 no-conflict）
  - apply_upstream_delta 硬失敗（例外）→ 例外往上傳播，last_synced_base_sha
    維持原值（既有安全路徑的回歸測試）

三情境皆透過 `_sync_with_backup` 端到端執行，直接斷言 `.sync-state.json`
檔案內容，而非只斷言函式回傳值（WRAP P 項防護：函式回傳正確不代表寫入點
真的遵守同一判定）。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_base_sha_conflict_gate", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_base_sha_conflict_gate"] = pull
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


def _write_base_sha(claude_dir: Path, base_sha: str) -> None:
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / ".sync-state.json").write_text(
        json.dumps({"last_synced_base_sha": base_sha}), encoding="utf-8"
    )


def _read_base_sha(claude_dir: Path) -> str:
    data = json.loads((claude_dir / ".sync-state.json").read_text(encoding="utf-8"))
    return data["last_synced_base_sha"]


# ============================================================================
# 情境 1：套用成功（無衝突）→ base 推進
# ============================================================================

def test_success_without_conflict_advances_base_sha(tmp_path):
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "keep.md").write_text("base line\n", encoding="utf-8")
    base = _commit_all(upstream, "base")

    # 上游 HEAD 變更，本地未動該檔 → take-upstream，無衝突
    (rules / "keep.md").write_text("upstream new\n", encoding="utf-8")
    head = _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "keep.md").write_text("base line\n", encoding="utf-8")
    _write_base_sha(claude, base)

    pull._sync_with_backup(project_root, upstream)

    assert _read_base_sha(claude) == head
    assert (claude / "rules" / "keep.md").read_text(encoding="utf-8") == "upstream new\n"


# ============================================================================
# 情境 2：有未解衝突 → base 不推進
# ============================================================================

def test_unresolved_conflict_does_not_advance_base_sha(tmp_path):
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "conflict.md").write_text("a\nb\nc\n", encoding="utf-8")
    base = _commit_all(upstream, "base")

    # 上游與本地皆修改同一行 → 三方合併衝突
    (rules / "conflict.md").write_text("a\nUPSTREAM\nc\n", encoding="utf-8")
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "conflict.md").write_text("a\nLOCAL\nc\n", encoding="utf-8")
    _write_base_sha(claude, base)

    pull._sync_with_backup(project_root, upstream)

    # 防假綠：先證明確實走到衝突路徑，而非誤判為 no-conflict
    assert (claude / ".sync-conflicts" / "rules" / "conflict.md").exists()
    # base 維持原值，未推進至上游 HEAD
    assert _read_base_sha(claude) == base


# ============================================================================
# 情境 3：apply_upstream_delta 硬失敗（例外）→ base 不推進（既有安全路徑回歸測試）
# ============================================================================

def test_hard_failure_does_not_advance_base_sha(tmp_path, monkeypatch):
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "keep.md").write_text("base line\n", encoding="utf-8")
    base = _commit_all(upstream, "base")
    (rules / "keep.md").write_text("upstream new\n", encoding="utf-8")
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    (claude / "rules" / "keep.md").write_text("base line\n", encoding="utf-8")
    _write_base_sha(claude, base)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("模擬套用 delta 硬失敗")

    monkeypatch.setattr(pull, "apply_upstream_delta", _boom)

    with pytest.raises(RuntimeError, match="模擬套用 delta 硬失敗"):
        pull._sync_with_backup(project_root, upstream)

    assert _read_base_sha(claude) == base
