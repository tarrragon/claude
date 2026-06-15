"""Tests for sync-claude-pull.py 衝突處理標準化（1.0.0-W1-084）。

涵蓋 acceptance：
  - VERSION / CHANGELOG.md 衝突時自動採 upstream，.sync-conflicts/ 仍留對照副本，
    且不計入 conflicts 清單（已自動解決）
  - 非版本檔衝突維持原 local-保留路徑（行為不破壞）
  - detect_conflict_residue：pull 開始時偵測 .sync-conflicts/ 既有殘留
    （mtime 早於本次、排除 .gitignore、目錄不存在回空）
  - warn_conflict_residue：殘留時 stdout 警告列出
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_conflict_handling", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_conflict_handling"] = pull
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


def _setup_version_conflict(tmp_path: Path):
    """建立版本檔 + 一般檔皆衝突的 fixture。

    上游 repo root 直接對應本地 .claude/。三檔皆 base / local / upstream 三方不同：
      - VERSION：版本檔，預期自動採 upstream
      - CHANGELOG.md：版本檔，預期自動採 upstream
      - rules/other.md：一般檔，預期維持原 local-保留路徑

    回傳 (project_root, upstream_repo, base_sha)。
    """
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    (upstream / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (upstream / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.0.0\n- base\n", encoding="utf-8"
    )
    rules = upstream / "rules"
    rules.mkdir()
    (rules / "other.md").write_text("a\nb\nc\n", encoding="utf-8")
    base = _commit_all(upstream, "base")

    (upstream / "VERSION").write_text("1.2.0\n", encoding="utf-8")
    (upstream / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.2.0\n- upstream bump\n", encoding="utf-8"
    )
    (rules / "other.md").write_text("a\nUPSTREAM\nc\n", encoding="utf-8")
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    (claude / "rules").mkdir(parents=True)
    # 本地三檔皆有別於 base 與 upstream 的修改 → 三方合併必衝突
    (claude / "VERSION").write_text("1.1.0-local\n", encoding="utf-8")
    (claude / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.1.0-local\n- local drift\n", encoding="utf-8"
    )
    (claude / "rules" / "other.md").write_text("a\nLOCAL\nc\n", encoding="utf-8")
    return project_root, upstream, base


# ============================================================================
# 版本檔衝突自動採 upstream
# ============================================================================

def test_version_file_conflict_takes_upstream(tmp_path):
    """VERSION 衝突 → 本地檔自動覆蓋為 upstream 內容，不列入 conflicts。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert (claude / "VERSION").read_text(encoding="utf-8") == "1.2.0\n"
    assert "VERSION" not in conflicts


def test_changelog_conflict_takes_upstream(tmp_path):
    """CHANGELOG.md 衝突 → 同樣自動採 upstream。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert "upstream bump" in (claude / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "CHANGELOG.md" not in conflicts


def test_version_file_conflict_keeps_reference_copy(tmp_path):
    """自動採 upstream 後 .sync-conflicts/ 仍留對照副本（含衝突標記）。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)
    claude = project_root / ".claude"

    pull.apply_upstream_delta(project_root, upstream, base)

    version_copy = claude / ".sync-conflicts" / "VERSION"
    changelog_copy = claude / ".sync-conflicts" / "CHANGELOG.md"
    assert version_copy.exists()
    assert changelog_copy.exists()
    # 對照副本是 git merge-file 的衝突標記結果，含 local 與 upstream 雙方內容
    copy_text = version_copy.read_text(encoding="utf-8")
    assert "1.1.0-local" in copy_text
    assert "1.2.0" in copy_text


def test_version_file_auto_resolve_prints_note(tmp_path, capsys):
    """自動採 upstream 時 stdout 有註記。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)

    pull.apply_upstream_delta(project_root, upstream, base)

    out = capsys.readouterr().out
    assert "版本檔衝突自動採 upstream: VERSION" in out
    assert "版本檔衝突自動採 upstream: CHANGELOG.md" in out


def test_non_version_conflict_preserves_local(tmp_path):
    """非版本檔衝突維持原行為：本地原檔保留 + 列入 conflicts + 衝突副本。"""
    project_root, upstream, base = _setup_version_conflict(tmp_path)
    claude = project_root / ".claude"

    _applied, conflicts, _residue = pull.apply_upstream_delta(
        project_root, upstream, base
    )

    assert "rules/other.md" in conflicts
    assert (claude / "rules" / "other.md").read_text(encoding="utf-8") == "a\nLOCAL\nc\n"
    assert (claude / ".sync-conflicts" / "rules" / "other.md").exists()


def test_version_files_whitelist_is_exact(tmp_path):
    """白名單限定 .claude/ 頂層 VERSION 與 CHANGELOG.md 兩檔。"""
    assert pull.VERSION_FILES_TAKE_UPSTREAM == frozenset({"VERSION", "CHANGELOG.md"})
    # 巢狀同名檔不在白名單（claude_rel 為完整相對路徑，精確比對）
    assert "rules/VERSION" not in pull.VERSION_FILES_TAKE_UPSTREAM


# ============================================================================
# 殘留偵測 detect_conflict_residue / warn_conflict_residue
# ============================================================================

def test_residue_empty_when_dir_absent(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    assert pull.detect_conflict_residue(claude) == []


def test_residue_lists_existing_files_excluding_gitignore(tmp_path):
    claude = tmp_path / ".claude"
    conflicts = claude / ".sync-conflicts"
    (conflicts / "rules").mkdir(parents=True)
    (conflicts / ".gitignore").write_text("*\n", encoding="utf-8")
    (conflicts / "VERSION").write_text("old conflict\n", encoding="utf-8")
    (conflicts / "rules" / "x.md").write_text("old conflict\n", encoding="utf-8")

    residue = pull.detect_conflict_residue(claude)

    assert residue == ["VERSION", "rules/x.md"]


def test_residue_respects_before_time(tmp_path):
    """mtime 晚於 before_time 的檔（本次新寫入）不列為殘留。"""
    claude = tmp_path / ".claude"
    conflicts = claude / ".sync-conflicts"
    conflicts.mkdir(parents=True)
    (conflicts / "stale.md").write_text("previous run\n", encoding="utf-8")
    cutoff = time.time() + 100  # 全部早於 cutoff → 殘留
    assert pull.detect_conflict_residue(claude, before_time=cutoff) == ["stale.md"]
    cutoff = time.time() - 100  # 全部晚於 cutoff → 非殘留
    assert pull.detect_conflict_residue(claude, before_time=cutoff) == []


def test_warn_conflict_residue_prints_listing(tmp_path, capsys):
    claude = tmp_path / ".claude"
    conflicts = claude / ".sync-conflicts"
    conflicts.mkdir(parents=True)
    (conflicts / "leftover.md").write_text("unhandled\n", encoding="utf-8")

    residue = pull.warn_conflict_residue(claude)

    out = capsys.readouterr().out
    assert residue == ["leftover.md"]
    assert "1 個前次 pull 衝突殘留未處理" in out
    assert "leftover.md" in out
    assert "pull 後檢查清單" in out


def test_warn_conflict_residue_silent_when_clean(tmp_path, capsys):
    claude = tmp_path / ".claude"
    claude.mkdir()

    residue = pull.warn_conflict_residue(claude)

    assert residue == []
    assert "殘留" not in capsys.readouterr().out
