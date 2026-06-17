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
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Tuple

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


# ---------------------------------------------------------------------------
# 反向檢查：已註冊但檔案不存在的幽靈註冊 + 跨檔重複註冊（W9-004 / framework issue #2）
# ---------------------------------------------------------------------------
#
# Why：正向檢查（檔存在但未註冊）抓不到「已註冊但 command 指向不存在的檔」。
# 後者才是會造成 runtime 崩潰的類型——hook relocate 後 settings.local.json
# 殘留舊路徑註冊，每次該事件（如 Stop）觸發都因 No such file or directory 報錯，
# 卻無守衛。本組函式掃描所有 settings*.json 已註冊 command，解析檔路徑，對
# 不存在者發 WARNING，並標記同一 hook 跨檔（settings.json + settings.local.json）
# 的重複註冊（additive 關係會重複執行，auto-resume 類有副作用風險）。


def _resolve_command_path(command: str, project_root: Path) -> Optional[Path]:
    """從 hook command 字串解析出 .py 檔絕對路徑。

    處理 $CLAUDE_PROJECT_DIR / ${CLAUDE_PROJECT_DIR} 前綴與 interpreter 前綴
    （如 `python3 .../foo.py args`，取第一個以 .py 結尾的 token）。

    Returns:
        指向 .py 檔的絕對路徑；command 不含 .py token（inline shell 等）時回 None。
    """
    if not command:
        return None
    py_token = next(
        (tok for tok in command.split() if tok.endswith(".py")), None
    )
    if py_token is None:
        return None
    resolved = py_token.replace("${CLAUDE_PROJECT_DIR}", str(project_root))
    resolved = resolved.replace("$CLAUDE_PROJECT_DIR", str(project_root))
    path = Path(resolved)
    if not path.is_absolute():
        path = project_root / path
    return path


def extract_registered_commands(settings: dict) -> List[Tuple[str, str, str]]:
    """從 settings dict 提取所有 (event_type, matcher, command) 三元組。

    保留 matcher：同一 hook 在同事件下以不同 matcher（如 Edit / Write）註冊
    屬合法多工具覆蓋，非重複；重複偵測須以 (event, matcher, 路徑) 為鍵。
    """
    triples: List[Tuple[str, str, str]] = []
    hooks_config = settings.get("hooks", {})
    for event_type, event_hooks in hooks_config.items():
        if isinstance(event_hooks, list):
            for hook_group in event_hooks:
                if isinstance(hook_group, dict):
                    matcher = hook_group.get("matcher", "")
                    for hook in hook_group.get("hooks", []):
                        if isinstance(hook, dict):
                            command = hook.get("command", "")
                            if command:
                                triples.append((event_type, matcher, command))
    return triples


def find_phantom_registrations(
    settings_sources: List[Tuple[str, Optional[dict]]], project_root: Path
) -> List[Tuple[str, str, str]]:
    """找出「已註冊但 command 指向不存在的 .py 檔」的幽靈註冊。

    Args:
        settings_sources: [(來源標籤, settings dict 或 None), ...]。
        project_root: 專案根目錄（解析 $CLAUDE_PROJECT_DIR）。

    Returns:
        [(來源標籤, event_type, 解析後不存在的路徑字串), ...]。
    """
    phantoms: List[Tuple[str, str, str]] = []
    for label, settings in settings_sources:
        if not settings:
            continue
        for event_type, _matcher, command in extract_registered_commands(settings):
            path = _resolve_command_path(command, project_root)
            if path is None:
                continue  # 非 .py 檔 hook（inline shell 等）不檢查
            if not path.exists():
                phantoms.append((label, event_type, str(path)))
    return phantoms


def find_duplicate_registrations(
    settings_sources: List[Tuple[str, Optional[dict]]], project_root: Path
) -> List[Tuple[str, str, List[str]]]:
    """找出同一 hook 檔在相同事件類型下被重複註冊（跨檔或同檔多次）。

    Returns:
        [(event_type, 解析後路徑字串, [來源標籤(可含重複), ...]), ...]，
        僅含註冊次數 > 1 者。
    """
    occurrences: dict = defaultdict(list)
    for label, settings in settings_sources:
        if not settings:
            continue
        for event_type, matcher, command in extract_registered_commands(settings):
            path = _resolve_command_path(command, project_root)
            if path is None:
                continue
            occurrences[(event_type, matcher, str(path))].append(label)
    dups: List[Tuple[str, str, List[str]]] = []
    for (event_type, _matcher, path_str), labels in occurrences.items():
        if len(labels) > 1:
            dups.append((event_type, path_str, sorted(labels)))
    return dups


def find_local_hook_registrations(
    settings_local: Optional[dict], project_root: Path
) -> List[Tuple[str, str]]:
    """找出 settings.local.json 內的任何 hook 註冊（latent ghost 預防）。

    單一註冊來源原則：hook 註冊一律歸 settings.json，settings.local.json
    僅放 permissions / env / mcp / outputStyle。即使 local 層的註冊目前
    合法（檔案存在、未重複），一旦該 hook relocate，local 副本即成幽靈，
    而 sync 排除 local 檔無法自癒。故在註冊「尚未出事」時即示警，把偵測
    時機從 relocate 後提前到註冊當下（對應 hook relocate phantom 根因）。

    Returns:
        [(event_type, command 字串), ...]，settings.local.json 內每個 hook 註冊一筆。
    """
    registrations: List[Tuple[str, str]] = []
    if not settings_local:
        return registrations
    for event_type, _matcher, command in extract_registered_commands(settings_local):
        registrations.append((event_type, command))
    return registrations


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

    # --- 反向檢查：幽靈註冊 + 跨檔重複（W9-004 / framework issue #2）---
    settings_local_path = project_root / '.claude' / 'settings.local.json'
    settings_local = load_json_file(settings_local_path, logger)
    settings_sources = [
        ("settings.json", settings),
        ("settings.local.json", settings_local),
    ]
    phantoms = find_phantom_registrations(settings_sources, project_root)
    duplicates = find_duplicate_registrations(settings_sources, project_root)

    if phantoms:
        header = "\n[WARNING] 幽靈註冊（已註冊但 command 檔不存在，會致 runtime 崩潰）:"
        print(header)
        logger.warning(header)
        sys.stderr.write(header + "\n")
        for label, event_type, path in phantoms:
            line = f"  - [{label}] {event_type}: {path}"
            print(line)
            logger.warning(line)
            sys.stderr.write(line + "\n")
        advice = "建議: 移除殘留註冊或修正 command 路徑（hook relocate 後常見於 settings.local.json）"
        print(advice)
        logger.warning(advice)

    if duplicates:
        header = "\n[WARNING] 重複註冊（同一 hook 同事件註冊多次，會重複執行）:"
        print(header)
        logger.warning(header)
        for event_type, path, labels in duplicates:
            line = f"  - {event_type}: {path}（來源: {', '.join(labels)}）"
            print(line)
            logger.warning(line)
        advice = "建議: 同一 hook 僅在單一 settings 檔註冊，避免 auto-resume 類副作用重複觸發"
        print(advice)
        logger.warning(advice)

    # latent ghost 預防：settings.local.json 不該註冊 hook（單一註冊來源原則）
    local_hook_regs = find_local_hook_registrations(settings_local, project_root)
    if local_hook_regs:
        header = (
            "\n[WARNING] settings.local.json 內含 hook 註冊"
            "（違反單一註冊來源原則，relocate 後會變幽靈）:"
        )
        print(header)
        logger.warning(header)
        for event_type, command in local_hook_regs:
            line = f"  - {event_type}: {command}"
            print(line)
            logger.warning(line)
        advice = (
            "建議: hook 註冊一律移至 settings.json；"
            "settings.local.json 僅放 permissions / env / mcp / outputStyle"
        )
        print(advice)
        logger.warning(advice)

    log_output = "=" * 60

    print(log_output)

    logger.info(log_output)

    # Exit 0 to not block session start (warning only)
    return 0


if __name__ == '__main__':
    sys.exit(run_hook_safely(main, "hook-completeness-check"))
