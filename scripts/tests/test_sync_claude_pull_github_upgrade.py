"""Tests: 2.x 版 pull 帶入的 .claude/.github/ 由新版 pull 清除（3.0.1-W1-005）。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_github_upgrade", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_github_upgrade"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

REL = "ISSUE_TEMPLATE/framework-issue.yml"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_identical_legacy_github_removed(tmp_path):
    claude, temp = tmp_path / ".claude", tmp_path / "clone"
    _write(temp, f".github/{REL}", "canonical")
    _write(claude, f".github/{REL}", "canonical")
    assert pull.cleanup_legacy_github_dir(claude, temp) == []
    assert not (claude / ".github").exists()


def test_modified_legacy_github_kept_with_hint(tmp_path, capsys):
    claude, temp = tmp_path / ".claude", tmp_path / "clone"
    _write(temp, f".github/{REL}", "canonical")
    _write(claude, f".github/{REL}", "consumer edit")
    _write(claude, ".github/extra.yml", "mine")
    kept = pull.cleanup_legacy_github_dir(claude, temp)
    captured = capsys.readouterr()
    assert sorted(kept) == sorted([REL, "extra.yml"])
    assert (claude / ".github" / REL).read_text() == "consumer edit"
    assert "保留" in captured.out + captured.err


def test_no_legacy_dir_noop(tmp_path):
    assert pull.cleanup_legacy_github_dir(tmp_path / ".claude", tmp_path / "clone") == []
