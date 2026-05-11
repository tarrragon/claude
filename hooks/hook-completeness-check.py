#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Hook Completeness Check

Verifies that all Python hook files in .claude/hooks/ directory are
properly registered in settings.json. Uses a directory scan + exclude
list mechanism instead of relying on hook-registry.json.

Runs on SessionStart to catch missing configurations and help maintain
comprehensive hook registration.

Exit codes:
    0 - All hooks properly configured (or warning only)
    0 - Missing/unregistered hooks detected (warning, does not block)
"""

import os
import stat
import subprocess
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).parent
_CLAUDE_DIR = _HOOKS_DIR.parent
_PROJECT_INIT_DIR = _CLAUDE_DIR / "skills" / "project-init"

sys.path.insert(0, str(_HOOKS_DIR))
sys.path.insert(0, str(_PROJECT_INIT_DIR))

from hook_utils import setup_hook_logging, run_hook_safely
from project_init.lib.hook_checker import (
    extract_registered_hooks,
    extract_registered_skill_hooks,
    get_exclude_patterns,
    load_json_file,
    scan_hooks_directory,
    scan_skill_hooks,
    should_exclude_file,
)


def _check_and_fix_permissions(hooks_dir, logger):
    """Check execute permissions for all .py files under hooks_dir and auto-fix.

    Scans recursively, skipping __pycache__ and .venv directories.
    Returns (fixed_count, already_ok_count).
    """
    fixed = []
    already_ok = 0

    for py_file in sorted(hooks_dir.rglob("*.py")):
        # Skip non-essential directories
        parts = py_file.relative_to(hooks_dir).parts
        if any(p in ("__pycache__", ".venv", "node_modules") for p in parts):
            continue

        if os.access(py_file, os.X_OK):
            already_ok += 1
        else:
            current_mode = py_file.stat().st_mode
            py_file.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            fixed.append(py_file.name)
            logger.info(f"chmod +x: {py_file.name}")

    return fixed, already_ok


def _run_git(args, cwd, logger):
    """Run a git command, return CompletedProcess. Never raises."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning(f"[HookCheck] git {' '.join(args)} 執行失敗: {exc}")
        sys.stderr.write(f"[HookCheck] git {' '.join(args)} 執行失敗: {exc}\n")
        return None


def _attempt_auto_commit(fixed_files, hooks_dir, project_root, logger):
    """If working tree only contains the chmod mode-only changes for fixed_files,
    auto-commit them as chore. Otherwise print a warning and skip.

    fixed_files: list of file names (basenames) that were chmod'd.
    Returns True if a commit was created, False otherwise.
    """
    if not fixed_files:
        return False

    # Compute repo-relative paths for each fixed file
    fixed_paths_abs = [hooks_dir / name for name in fixed_files]
    try:
        fixed_rel_set = {
            str(p.resolve().relative_to(project_root.resolve()))
            for p in fixed_paths_abs
            if p.exists()
        }
    except ValueError as exc:
        msg = f"[HookCheck] 無法計算相對路徑，跳過自動 commit: {exc}"
        print(msg)
        logger.warning(msg)
        return False

    # 1) git status --porcelain - examine working tree
    status = _run_git(["status", "--porcelain"], project_root, logger)
    if status is None or status.returncode != 0:
        msg = "[HookCheck] git status 失敗，跳過自動 commit"
        print(msg)
        logger.warning(msg)
        if status and status.stderr:
            sys.stderr.write(status.stderr)
        return False

    # Parse porcelain entries: each line "XY path"
    changed_paths = set()
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        # porcelain format: 2 status chars + space + path
        path = line[3:].strip()
        # Strip rename arrow if present
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed_paths.add(path)

    if changed_paths != fixed_rel_set:
        extra = changed_paths - fixed_rel_set
        msg = (
            f"[HookCheck] 偵測到其他未提交變更（{len(extra)} 項），跳過自動 commit。"
            f" 請手動處理後再執行；或使用 git revert HEAD 不適用此情境。"
        )
        print(msg)
        logger.info(msg)
        return False

    # 2) Verify each file is mode-only change (git diff <file> empty content)
    diff = _run_git(
        ["diff", "--", *sorted(fixed_rel_set)],
        project_root,
        logger,
    )
    if diff is None or diff.returncode != 0:
        msg = "[HookCheck] git diff 失敗，跳過自動 commit"
        print(msg)
        logger.warning(msg)
        return False

    # Mode-only changes show in `git diff` as a header with "old mode"/"new mode"
    # but no @@ hunks. If we see any hunk markers, it's not mode-only.
    if "@@" in diff.stdout:
        msg = "[HookCheck] 偵測到非 mode-only 變更，跳過自動 commit"
        print(msg)
        logger.info(msg)
        return False

    # 3) git add + git commit
    add = _run_git(["add", "--", *sorted(fixed_rel_set)], project_root, logger)
    if add is None or add.returncode != 0:
        err = (add.stderr if add else "") or "unknown error"
        msg = f"[HookCheck] git add 失敗，跳過自動 commit: {err}"
        print(msg)
        logger.warning(msg)
        sys.stderr.write(msg + "\n")
        return False

    commit_msg = "chore: auto-fix executable permissions for hook files (IMP-054)"
    commit = _run_git(["commit", "-m", commit_msg], project_root, logger)
    if commit is None or commit.returncode != 0:
        err = (commit.stderr if commit else "") or "unknown error"
        out = (commit.stdout if commit else "") or ""
        msg = f"[HookCheck] git commit 失敗: {err}{out}"
        print(msg)
        logger.warning(msg)
        sys.stderr.write(msg + "\n")
        return False

    success_msg = (
        f"[HookCheck] 已自動 commit {len(fixed_rel_set)} 個權限修正檔案。"
        f" 如需撤銷請執行: git revert HEAD"
    )
    print(success_msg)
    logger.info(success_msg)
    return True


def main():
    logger = setup_hook_logging("hook-completeness-check")
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    hooks_dir = script_dir
    settings_path = project_root / '.claude' / 'settings.json'
    exclude_list_path = script_dir / 'hook-exclude-list.json'

    # --- Permission check (IMP-054) ---
    fixed_files, ok_count = _check_and_fix_permissions(hooks_dir, logger)

    if fixed_files:
        log_output = f"[HookCheck] 權限修正: {len(fixed_files)} 個檔案已自動加上執行權限 (IMP-054)"
        print(log_output)
        logger.info(log_output)
        for name in fixed_files[:10]:
            detail = f"  chmod +x: {name}"
            print(detail)
            logger.info(detail)
        if len(fixed_files) > 10:
            more = f"  ... 還有 {len(fixed_files) - 10} 個"
            print(more)
            logger.info(more)

        # --- Auto-commit (IMP-054 / W17-133) ---
        try:
            _attempt_auto_commit(fixed_files, hooks_dir, project_root, logger)
        except Exception as exc:  # noqa: BLE001 - hook must not crash session
            err = f"[HookCheck] 自動 commit 流程發生未預期例外: {exc}"
            print(err)
            logger.warning(err)
            sys.stderr.write(err + "\n")

    # --- Registration check ---

    # Load configuration files
    settings = load_json_file(settings_path, logger)
    if settings is None:
        log_output = "[HookCheck] Warning: settings.json not found, skipping check"
        print(log_output)
        logger.info(log_output)
        return 0

    exclude_list = load_json_file(exclude_list_path, logger)
    exact_excludes, patterns = get_exclude_patterns(exclude_list)

    # Scan hooks directory (主層 .claude/hooks/)
    all_hooks = scan_hooks_directory(hooks_dir, exact_excludes, patterns)
    registered_hooks = extract_registered_hooks(settings)

    # Scan skill hooks (.claude/skills/<skill>/hooks/，W10-091 雙層架構)
    skills_dir = project_root / '.claude' / 'skills'
    all_skill_hooks = scan_skill_hooks(skills_dir, exact_excludes, patterns)
    registered_skill_hooks = extract_registered_skill_hooks(settings)

    # Find unregistered hooks
    unregistered = all_hooks - registered_hooks
    unregistered_skill_hooks = all_skill_hooks - registered_skill_hooks
    count_excluded = sum(
        1 for f in hooks_dir.glob('*.py')
        if should_exclude_file(f.name, exact_excludes, patterns)
    )

    # Report results
    log_output = "\n[HookCheck] Hook 完整性檢查結果"

    print(log_output)

    logger.info(log_output)
    log_output = "=" * 60
    print(log_output)
    logger.info(log_output)
    log_output = f"已註冊: {len(registered_hooks)} 個"
    print(log_output)
    logger.info(log_output)
    log_output = f"未註冊: {len(unregistered)} 個"
    print(log_output)
    logger.info(log_output)
    log_output = f"排除: {count_excluded} 個"
    print(log_output)
    logger.info(log_output)
    log_output = (
        f"Skill Hooks (.claude/skills/*/hooks/): 共 {len(all_skill_hooks)} 個"
        f"，已註冊 {len(registered_skill_hooks)} 個"
        f"，未註冊 {len(unregistered_skill_hooks)} 個"
    )
    print(log_output)
    logger.info(log_output)
    log_output = f"權限: {ok_count + len(fixed_files)} 個已確認可執行" + (f" ({len(fixed_files)} 個本次修正)" if fixed_files else "")
    print(log_output)
    logger.info(log_output)

    if unregistered:
        log_output = "\n未註冊的 Hook（最多顯示 15 個）:"

        print(log_output)

        logger.info(log_output)
        for hook in sorted(unregistered)[:15]:
            log_output = f"  - {hook}"

            print(log_output)

            logger.info(log_output)

        if len(unregistered) > 15:
            log_output = f"  ... 還有 {len(unregistered) - 15} 個"

            print(log_output)

            logger.info(log_output)

        log_output = "\n建議: 檢查這些 Hook 是否需要在 settings.json 中註冊"

        print(log_output)

        logger.info(log_output)
    else:
        log_output = "\n所有 Hook 檔案都已在 settings.json 中註冊"

        print(log_output)

        logger.info(log_output)

    if unregistered_skill_hooks:
        log_output = "\n未註冊的 Skill Hook（最多顯示 15 個）:"
        print(log_output)
        logger.info(log_output)
        for hook in sorted(unregistered_skill_hooks)[:15]:
            log_output = f"  - [skill] {hook}"
            print(log_output)
            logger.info(log_output)
        if len(unregistered_skill_hooks) > 15:
            log_output = f"  ... 還有 {len(unregistered_skill_hooks) - 15} 個"
            print(log_output)
            logger.info(log_output)
        log_output = "\n建議: 檢查這些 Skill Hook 是否需要在 settings.json 中註冊（路徑形式: $CLAUDE_PROJECT_DIR/.claude/skills/<skill>/hooks/<file>.py）"
        print(log_output)
        logger.info(log_output)

    log_output = "=" * 60

    print(log_output)

    logger.info(log_output)

    # Exit 0 to not block session start (warning only)
    return 0


if __name__ == '__main__':
    sys.exit(run_hook_safely(main, "hook-completeness-check"))
