"""Tests for hook-completeness-check auto-commit on chmod-only changes (W17-133).

Covers:
    A) Clean working tree + missing exec bit -> auto-commit created
    B) Other untracked/modified files present -> chmod done, no new commit
    C) git commit subprocess failure -> stderr message emitted, hook does not crash
"""

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
HOOK_PATH = HOOKS_DIR / "hook-completeness-check.py"


def _load_hook_module():
    """Load hook-completeness-check.py as a module (filename has hyphens)."""
    spec = importlib.util.spec_from_file_location(
        "hook_completeness_check_under_test", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    # Make sure parent dir is on sys.path so its `from hook_utils import ...` works
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def _run(cmd, cwd):
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=True
    )


def _init_git_repo(root: Path) -> Path:
    """Initialize a tmp git repo with a baseline committed file under .claude/hooks/."""
    _run(["git", "init", "-q", "-b", "main"], root)
    _run(["git", "config", "user.email", "test@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    _run(["git", "config", "commit.gpgsign", "false"], root)
    # Disable any pre-commit hooks that might exist via core.hooksPath
    _run(["git", "config", "core.hooksPath", "/dev/null"], root)

    hooks_dir = root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)

    baseline = hooks_dir / "baseline.py"
    baseline.write_text("#!/usr/bin/env python3\nprint('baseline')\n")
    baseline.chmod(0o755)

    _run(["git", "add", "."], root)
    _run(["git", "commit", "-q", "-m", "init"], root)
    return hooks_dir


def _add_non_exec_file(hooks_dir: Path, name: str = "needs_chmod.py") -> Path:
    """Add a tracked .py file committed WITH exec bit, then strip locally so
    that running chmod +x produces a mode-only diff vs HEAD (worktree clean
    after fix means nothing to commit; we want HEAD<->worktree to differ on
    mode only). To create a real auto-commit candidate we instead commit the
    file WITHOUT exec bit, so chmod +x creates a mode-only diff to commit."""
    f = hooks_dir / name
    f.write_text("#!/usr/bin/env python3\nprint('x')\n")
    f.chmod(0o644)
    repo_root = hooks_dir.parent.parent
    _run(["git", "add", str(f.relative_to(repo_root))], repo_root)
    _run(["git", "commit", "-q", "-m", "add file"], repo_root)
    # File is committed with mode 644 (no exec). Hook will chmod +x to 755,
    # producing a mode-only diff vs HEAD that auto-commit can capture.
    return f


def _git_log_count(repo_root: Path) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return int(out.stdout.strip())


def _last_commit_msg(repo_root: Path) -> str:
    out = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


# --- Scenario A ----------------------------------------------------------------

def test_a_clean_tree_creates_autocommit(tmp_path, hook_mod, capsys, caplog):
    repo_root = tmp_path
    hooks_dir = _init_git_repo(repo_root)
    target = _add_non_exec_file(hooks_dir, "alpha.py")

    assert not os.access(target, os.X_OK), "precondition: target lacks exec bit"
    before = _git_log_count(repo_root)

    import logging
    logger = logging.getLogger("test_w17_133_a")

    fixed, ok = hook_mod._check_and_fix_permissions(hooks_dir, logger)
    assert "alpha.py" in fixed

    created = hook_mod._attempt_auto_commit(fixed, hooks_dir, repo_root, logger)
    assert created is True

    after = _git_log_count(repo_root)
    assert after == before + 1, "should have one new commit"

    msg = _last_commit_msg(repo_root)
    assert "auto-fix executable permissions" in msg
    assert "IMP-054" in msg

    # Working tree should now be clean
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout.strip() == ""


# --- Scenario B ----------------------------------------------------------------

def test_b_dirty_tree_skips_commit(tmp_path, hook_mod):
    repo_root = tmp_path
    hooks_dir = _init_git_repo(repo_root)
    target = _add_non_exec_file(hooks_dir, "beta.py")

    # Introduce an unrelated untracked file
    extra = repo_root / "scratch.txt"
    extra.write_text("not part of chmod fix\n")

    before = _git_log_count(repo_root)

    import logging
    logger = logging.getLogger("test_w17_133_b")

    fixed, _ = hook_mod._check_and_fix_permissions(hooks_dir, logger)
    assert "beta.py" in fixed
    assert os.access(target, os.X_OK), "chmod should still have run"

    created = hook_mod._attempt_auto_commit(fixed, hooks_dir, repo_root, logger)
    assert created is False

    after = _git_log_count(repo_root)
    assert after == before, "no new commit should be created"

    # The untracked file is still there
    assert extra.exists()


# --- Scenario C ----------------------------------------------------------------

def test_c_commit_failure_does_not_crash(tmp_path, hook_mod, capsys):
    repo_root = tmp_path
    hooks_dir = _init_git_repo(repo_root)
    _add_non_exec_file(hooks_dir, "gamma.py")

    import logging
    logger = logging.getLogger("test_w17_133_c")
    fixed, _ = hook_mod._check_and_fix_permissions(hooks_dir, logger)
    assert "gamma.py" in fixed

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        # Force `git commit` to fail; let other git commands pass through
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "commit":
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="simulated commit failure\n"
            )
        return real_run(cmd, *args, **kwargs)

    with patch.object(hook_mod.subprocess, "run", side_effect=fake_run):
        created = hook_mod._attempt_auto_commit(fixed, hooks_dir, repo_root, logger)

    assert created is False

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "simulated commit failure" in combined or "git commit 失敗" in combined
