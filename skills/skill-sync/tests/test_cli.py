"""Unit tests for skill_sync.cli exclude-file logic."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill_sync.cli import _should_exclude_file, compute_diff, EXCLUDE_DIRS  # noqa: E402


def test_hook_logs_top_level_jsonl_excluded():
    assert _should_exclude_file(".claude/hook-logs/cli-force-usage.jsonl") is True


def test_hook_logs_nested_subdir_excluded():
    assert _should_exclude_file(".claude/hook-logs/identity-guard/usage.log") is True


def test_hook_logs_dir_registered_in_exclude_dirs():
    assert "hook-logs" in EXCLUDE_DIRS


def test_regular_skill_file_not_excluded():
    assert _should_exclude_file("SKILL.md") is False
    assert _should_exclude_file("scripts/run.py") is False


def test_existing_exclude_dirs_still_work():
    assert _should_exclude_file(".venv/lib/site-packages/foo.py") is True
    assert _should_exclude_file("__pycache__/cli.cpython-314.pyc") is True
    assert _should_exclude_file(".pytest_cache/v/cache/nodeids") is True


def test_compute_diff_excludes_hook_logs_from_added(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "SKILL.md").write_text("hello")
    hook_logs_dir = src / ".claude" / "hook-logs" / "identity-guard"
    hook_logs_dir.mkdir(parents=True)
    (hook_logs_dir / "usage.log").write_text("runtime state")
    (src / ".claude" / "hook-logs" / "cli-force-usage.jsonl").write_text("{}")

    diff = compute_diff(src, dst)

    assert "SKILL.md" in diff["added"]
    assert not any("hook-logs" in f for f in diff["added"])
    assert not any("hook-logs" in f for f in diff["modified"])
    assert not any("hook-logs" in f for f in diff["dst_only"])
