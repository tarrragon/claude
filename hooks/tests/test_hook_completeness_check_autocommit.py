"""Tests for hook-completeness-check auto-commit on chmod-only changes.

原始情境 A/C 來自 W17-133；B 於 0.2.1-W3-319 反轉——舊版要求工作區恰好乾淨才
commit，該條件在真實環境幾乎不成立，是本次要修掉的失效行為，不是要保護的規格。

Covers:
    A) Clean working tree + missing exec bit -> auto-commit created
    B) Other untracked/staged changes present -> still commits, without absorbing them
    C) git commit subprocess failure -> stderr message emitted, hook does not crash
    D) tests/ subdir is out of scan scope -> keeps its 644 mode
    E) Target file itself untracked -> excluded, no commit, no failure noise
    F) Rebase in progress (detached HEAD) -> skipped, no commit injected into replay
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

def test_b_dirty_tree_still_commits_without_absorbing_others(tmp_path, hook_mod):
    """髒工作區仍應提交 mode 修正，且不得吸收無關變更（0.2.1-W3-319）。

    舊行為要求工作區恰好乾淨才 commit，SessionStart 時幾乎不成立，實測連續 4 次
    chmod 全數 skip，mode 變更淪為跨 session 無主遺留。此處同時放入 untracked 與
    已 stage 的無關變更，驗證 `git commit --only` 不會把它們捲進同一個 commit
    （PC-BAL-008）。
    """
    repo_root = tmp_path
    hooks_dir = _init_git_repo(repo_root)
    target = _add_non_exec_file(hooks_dir, "beta.py")

    # Unrelated untracked file
    extra = repo_root / "scratch.txt"
    extra.write_text("not part of chmod fix\n")

    # Unrelated change that another session already staged
    staged = hooks_dir / "baseline.py"
    staged.write_text("#!/usr/bin/env python3\nprint('edited by another session')\n")
    _run(["git", "add", "--", "baseline.py"], hooks_dir)

    before = _git_log_count(repo_root)

    import logging
    logger = logging.getLogger("test_w3_319_b")

    fixed, _ = hook_mod._check_and_fix_permissions(hooks_dir, logger)
    assert "beta.py" in fixed
    assert os.access(target, os.X_OK), "chmod should still have run"

    created = hook_mod._attempt_auto_commit(fixed, hooks_dir, repo_root, logger)
    assert created is True, "dirty tree must no longer block the mode-only commit"

    after = _git_log_count(repo_root)
    assert after == before + 1

    # The commit must contain ONLY the chmod'd file
    changed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert changed == [".claude/hooks/beta.py"], f"commit leaked extra paths: {changed}"

    # Unrelated work survives untouched
    assert extra.exists(), "untracked file must not be swept into the commit"
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "baseline.py" in status, "staged unrelated change must remain uncommitted"


# --- Scenario D: scan scope ----------------------------------------------------

def test_d_tests_subdir_is_not_chmodded(tmp_path, hook_mod):
    """tests/ 下的檔案由 pytest import，不被 shell 執行，不應獲得 exec bit。

    遞迴掃描會給它們 +x，產生無主的 git mode-only 變更（0.2.1-W3-319 根因）。
    """
    repo_root = tmp_path
    hooks_dir = _init_git_repo(repo_root)

    top_level = _add_non_exec_file(hooks_dir, "gamma.py")

    tests_dir = hooks_dir / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_gamma.py"
    test_file.write_text("def test_noop():\n    assert True\n")
    test_file.chmod(0o644)

    import logging
    logger = logging.getLogger("test_w3_319_d")

    fixed, _ = hook_mod._check_and_fix_permissions(hooks_dir, logger)

    assert "gamma.py" in fixed, "top-level hook must still be fixed"
    assert "test_gamma.py" not in fixed
    assert os.access(top_level, os.X_OK)
    assert not os.access(test_file, os.X_OK), "tests/ must keep its 644 mode"


# --- Scenario E: untracked target ----------------------------------------------

def test_e_untracked_target_is_excluded_from_commit(tmp_path, hook_mod):
    """全新未追蹤的 hook 檔不屬於 mode-only 提交範圍（0.2.1-W3-319）。

    它整份內容都是新的，若以「auto-fix executable permissions」的訊息提交，
    commit 訊息會與內容不符，且未經審查的 hook 就此入庫。chmod 仍須執行——
    exec bit 是它能被啟動的前提，提交則留給正常開發流程。
    """
    repo_root = tmp_path
    hooks_dir = _init_git_repo(repo_root)

    newhook = hooks_dir / "newhook.py"
    newhook.write_text("#!/usr/bin/env python3\nprint('brand new')\n")
    newhook.chmod(0o644)

    before = _git_log_count(repo_root)

    import logging
    logger = logging.getLogger("test_w3_319_e")

    fixed, _ = hook_mod._check_and_fix_permissions(hooks_dir, logger)
    assert "newhook.py" in fixed
    assert os.access(newhook, os.X_OK), "chmod must still run on a new hook"

    created = hook_mod._attempt_auto_commit(fixed, hooks_dir, repo_root, logger)
    assert created is False

    assert _git_log_count(repo_root) == before
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "?? .claude/hooks/newhook.py" in status, "file stays untracked for review"


# --- Scenario F: rebase in progress --------------------------------------------

def test_f_rebase_in_progress_skips_commit(tmp_path, hook_mod):
    """rebase 暫停期間不得 commit（0.2.1-W3-319）。

    此時 HEAD 是 detached，commit 會被 `rebase --continue` 收進 replay 序列，
    成為分支永久祖先且其後所有 commit 的 SHA 都改變，全程無警告。git 自身只擋
    merge 中的 partial commit，不擋 rebase。
    """
    repo_root = tmp_path
    hooks_dir = _init_git_repo(repo_root)
    target = _add_non_exec_file(hooks_dir, "delta.py")

    # 製造 rebase 衝突使流程停在 detached HEAD
    conflict = repo_root / "conflict.txt"
    conflict.write_text("base\n")
    _run(["git", "add", "conflict.txt"], repo_root)
    _run(["git", "commit", "-q", "-m", "base_conflict"], repo_root)
    _run(["git", "checkout", "-q", "-b", "feature"], repo_root)
    conflict.write_text("feature\n")
    _run(["git", "commit", "-q", "-am", "feature_change"], repo_root)
    _run(["git", "checkout", "-q", "main"], repo_root)
    conflict.write_text("mainside\n")
    _run(["git", "commit", "-q", "-am", "main_change"], repo_root)
    _run(["git", "checkout", "-q", "feature"], repo_root)
    subprocess.run(["git", "rebase", "main"], cwd=str(repo_root), capture_output=True)

    head_ref = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"],
        cwd=str(repo_root), capture_output=True, text=True,
    )
    assert head_ref.returncode != 0, "precondition: rebase must leave HEAD detached"

    before = _git_log_count(repo_root)

    import logging
    logger = logging.getLogger("test_w3_319_f")

    fixed, _ = hook_mod._check_and_fix_permissions(hooks_dir, logger)
    assert "delta.py" in fixed
    assert os.access(target, os.X_OK), "chmod should still have run"

    created = hook_mod._attempt_auto_commit(fixed, hooks_dir, repo_root, logger)
    assert created is False, "must not commit while rebase is in progress"
    assert _git_log_count(repo_root) == before


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
