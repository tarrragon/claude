#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Hook Completeness Check

Verifies that all Python hook files in .claude/hooks/ directory are
properly registered in settings.json. Uses a directory scan + exclude
list mechanism.

Runs on SessionStart to catch missing configurations and help maintain
comprehensive hook registration.

Exit codes:
    0 - All hooks properly configured (or warning only)
    0 - Missing/unregistered hooks detected (warning, does not block)
"""

import json
import os
import re
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
sys.path.insert(0, str(_CLAUDE_DIR))  # for `from lib import ...`
sys.path.insert(0, str(_PROJECT_INIT_DIR))

from lib import setup_hook_logging, run_hook_safely
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


_MERGE_DECL_BLOCK_RE = re.compile(
    r'合併以下\s*\d+\s*個\s*Hook[:：]\s*\n((?:\d+\.\s*\S+\.py.*\n?)+)'
)
_MERGE_DECL_FILENAME_RE = re.compile(r'\d+\.\s*(\S+\.py)')


def extract_merge_declarations(hooks_dir: Path) -> dict:
    """解析 hook 檔案 docstring 中的合併宣告（如「合併以下 3 個 Hook：」後列舉的檔名）。

    Returns:
        {合併版檔名: [被合併檔名, ...]}，僅含有合併宣告的 hook。
    """
    declarations: dict = {}
    for py_file in sorted(hooks_dir.glob('*.py')):
        try:
            text = py_file.read_text(encoding='utf-8')
        except OSError:
            continue
        match = _MERGE_DECL_BLOCK_RE.search(text)
        if not match:
            continue
        merged_files = _MERGE_DECL_FILENAME_RE.findall(match.group(1))
        if merged_files:
            declarations[py_file.name] = merged_files
    return declarations


def find_merge_declaration_violations(
    hooks_dir: Path,
    settings_sources: List[Tuple[str, Optional[dict]]],
    project_root: Path,
) -> List[Tuple[str, str, str]]:
    """找出「合併版與被合併版並存」的語意重複註冊。

    正向檢查（find_duplicate_registrations）只抓「同一檔案被註冊多次」，
    抓不到「合併版 hook 已涵蓋被合併版的功能，但被合併版仍各自獨立註冊」
    這種語意重複——兩者路徑不同，逐字比對不會命中，卻在同一事件下重複
    執行相同業務邏輯（1.4.0-W2-029）。

    Returns:
        [(event_type, 合併版檔名, 被合併版檔名), ...]，僅含合併版與被合併版
        於同一 event_type 下同時註冊者。
    """
    declarations = extract_merge_declarations(hooks_dir)
    if not declarations:
        return []

    registered_by_event: dict = defaultdict(set)
    for _label, settings in settings_sources:
        if not settings:
            continue
        for event_type, _matcher, command in extract_registered_commands(settings):
            path = _resolve_command_path(command, project_root)
            if path is not None:
                registered_by_event[event_type].add(path.name)

    violations: List[Tuple[str, str, str]] = []
    for merger_name, merged_names in declarations.items():
        merger_events = [
            evt for evt, names in registered_by_event.items()
            if merger_name in names
        ]
        for merged_name in merged_names:
            for evt in merger_events:
                if merged_name in registered_by_event[evt]:
                    violations.append((evt, merger_name, merged_name))
    return violations


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


def prune_phantom_local_registrations(
    settings_local_path: Path, project_root: Path, apply: bool = False
) -> List[Tuple[str, str]]:
    """移除 settings.local.json 中 command 指向不存在 .py 檔的幽靈 hook 註冊。

    opt-in remediation：只刪「command 解析出的 .py 路徑不存在」的 entry，保留
    working hook（檔案存在）與 inline 非 .py 指令（無法驗證存在性）。`apply=False`
    為 dry-run（僅回報、不寫檔）。幽靈刪除後清理空的 matcher group / event 陣列 /
    `hooks` key，避免殘留空殼。

    僅作用於 settings.local.json：該層為 sync 排除檔，relocate 後無法自癒
    （ARCH-TUNL-001）；settings.json 的幽靈由 sync overlay 自癒且屬 SSOT，不在此
    自動改寫範圍。設計依據：settings.local.json 為 sync 外層無法自癒機制、PC-148 固化原則。

    Returns:
        [(event_type, 解析後不存在的路徑字串), ...]，已移除（或 dry-run 將移除）的 entry。
    """
    removed: List[Tuple[str, str]] = []
    if not settings_local_path.is_file():
        return removed
    try:
        data = json.loads(settings_local_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return removed
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return removed

    for event_type in list(hooks.keys()):
        kept_groups = []
        for group in hooks.get(event_type) or []:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            kept_inner = []
            for entry in group.get("hooks", []):
                command = entry.get("command", "") if isinstance(entry, dict) else ""
                path = _resolve_command_path(command, project_root)
                if path is not None and not path.exists():
                    removed.append((event_type, str(path)))
                    continue  # 幽靈 entry，丟棄
                kept_inner.append(entry)
            if kept_inner:
                group["hooks"] = kept_inner
                kept_groups.append(group)
            # group 內 hooks 全為幽靈 → 整個 group 丟棄
        if kept_groups:
            hooks[event_type] = kept_groups
        else:
            del hooks[event_type]

    if not hooks:
        data.pop("hooks", None)

    if apply and removed:
        settings_local_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return removed


def _check_and_fix_permissions(hooks_dir, logger):
    """為 hooks_dir 頂層的 hook 補上缺少的 exec bit。

    Claude Code 以 `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>.py` 的形式直接執行
    hook，故只有「會被當作可執行檔啟動」的檔案需要 exec bit，而 hook 本體一律放
    在頂層。以目錄層級界定而非解析 settings.json，是為了避開「已註冊但本輪尚未
    chmod 就被執行」的競態——那正是 IMP-054 的原始失效。

    刻意不遞迴：`tests/`、`acceptance_checkers/`、`archived/` 下的 .py 由 pytest 或
    import 載入，從不被 shell 直接執行。對其 chmod 會產生無主的 git mode-only 變更
    （0.2.1-W3-319）。

    真要支援子目錄 hook，先決條件是本函式改回傳相對路徑——目前回傳 basename，
    `_attempt_auto_commit` 以 `hooks_dir / name` 還原，子目錄檔案會還原到錯誤位置。

    Returns:
        (fixed_file_names, already_ok_count)
    """
    fixed = []
    already_ok = 0

    for py_file in sorted(hooks_dir.glob("*.py")):
        if not py_file.is_file():
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


def _repo_is_safe_to_autocommit(project_root, logger):
    """僅在 HEAD 掛在分支上、且無進行中的 merge 時，才允許自動 commit。

    不逐一檢查 `.git/rebase-merge`、`.git/CHERRY_PICK_HEAD` 等狀態檔：那份清單會
    隨 git 版本增長，漏一項就是一個洞；更關鍵的是 linked worktree 的 `.git` 是
    gitfile 而非目錄，真正的狀態檔位在 `<main>/.git/worktrees/<name>/` 下，路徑存在
    性檢查在 worktree 中必然失效——而本專案常以 worktree 開發。

    改判 HEAD 是否 detached 可一次覆蓋 rebase（兩種 backend 皆 detach HEAD）、
    bisect 與一般 detached 狀態。若在 rebase 暫停期間 commit，該 commit 會被
    `rebase --continue` 收進 replay 序列，成為分支的永久祖先且其後所有 commit 的
    SHA 都改變，全程無警告（0.2.1-W3-319 實測）。

    merge 進行中 HEAD 仍掛在分支上，故需另行檢查 MERGE_HEAD。git 自身雖會擋下
    partial commit，但先行判斷可省去一則對使用者無意義的 fatal 訊息。
    """
    head = _run_git(["symbolic-ref", "-q", "HEAD"], project_root, logger)
    if head is None or head.returncode != 0:
        msg = "[HookCheck] HEAD 未掛在分支上（rebase / bisect / detached），跳過自動 commit"
        print(msg)
        logger.info(msg)
        return False

    merge_head = _run_git(
        ["rev-parse", "-q", "--verify", "MERGE_HEAD"], project_root, logger
    )
    if merge_head is not None and merge_head.returncode == 0:
        msg = "[HookCheck] merge 進行中，跳過自動 commit"
        print(msg)
        logger.info(msg)
        return False

    return True


def _attempt_auto_commit(fixed_files, hooks_dir, project_root, logger):
    """提交本次 chmod 產生的 mode-only 變更。

    工作區有其他變更時仍會提交，但範圍只涵蓋指定路徑。刻意不要求工作區乾淨——
    SessionStart 時工作區通常已有開發中變更，舊版的「工作區恰好只含本次 chmod
    變更」條件在真實環境幾乎不成立（0.2.1-W3-319 實證連續 4 次 chmod 全數跳過），
    使 mode 變更淪為跨 session 無主遺留，最終在 git pull 時阻擋合併。

    fixed_files: 本次 chmod 的檔名（basename，位於 hooks_dir 頂層）。
    Returns True if a commit was created, False otherwise.
    """
    if not fixed_files:
        return False

    if not _repo_is_safe_to_autocommit(project_root, logger):
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

    # 1) 以 numstat 一次取得「已被追蹤、相對 HEAD 有變更、且為 mode-only」的精確集合。
    # `0\t0\t<path>` 表示零增刪行，即純 mode 變更。基準取 HEAD 而非 index，才能涵蓋
    # 其他 session 已將內容變更 stage 起來的情形。未被追蹤的檔案不會出現在輸出中，
    # 因而自然被排除——新建的 hook 檔整份內容都是新的，不屬於本函式的提交範圍，
    # 若一併提交會讓「auto-fix executable permissions」的 commit 訊息與內容不符。
    # --no-renames 必要：純改名在 numstat 下同樣顯示為 0 0，會偽裝成 mode-only。
    diff = _run_git(
        ["diff", "HEAD", "--numstat", "--no-renames", "--", *sorted(fixed_rel_set)],
        project_root,
        logger,
    )
    if diff is None or diff.returncode != 0:
        msg = "[HookCheck] git diff 失敗，跳過自動 commit"
        print(msg)
        logger.warning(msg)
        return False

    committable = set()
    for line in diff.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] == "0" and parts[1] == "0":
            committable.add(parts[2])

    if not committable:
        msg = (
            "[HookCheck] 本次 chmod 的檔案沒有可提交的 mode-only 變更"
            "（未被追蹤、已提交或含內容變更），跳過自動 commit。"
        )
        print(msg)
        logger.info(msg)
        return False

    skipped = fixed_rel_set - committable
    if skipped:
        logger.info(
            f"[HookCheck] {len(skipped)} 個 chmod 檔案無 mode-only 變更可提交，"
            f"僅提交其餘 {len(committable)} 個: {', '.join(sorted(skipped))}"
        )

    # 2) git commit --only：僅提交指定路徑，不吸收其他 session 已 stage 的內容。
    # 不先 git add——`--only` 自帶「以這些路徑為準」語意，額外的 add 會把檔案留在
    # index 中，一旦後續 commit 失敗即污染共用 index（PC-BAL-008）。
    commit_msg = "chore: auto-fix executable permissions for hook files (IMP-054)"
    commit = _run_git(
        ["commit", "--only", "-m", commit_msg, "--", *sorted(committable)],
        project_root,
        logger,
    )
    if commit is None or commit.returncode != 0:
        err = (commit.stderr if commit else "") or "unknown error"
        out = (commit.stdout if commit else "") or ""
        msg = f"[HookCheck] git commit 失敗: {err}{out}"
        print(msg)
        logger.warning(msg)
        sys.stderr.write(msg + "\n")
        return False

    success_msg = (
        f"[HookCheck] 已自動 commit {len(committable)} 個權限修正檔案。"
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

    merge_violations = find_merge_declaration_violations(
        hooks_dir, settings_sources, project_root
    )
    if merge_violations:
        header = (
            "\n[WARNING] 合併版與被合併版並存（docstring 宣告已合併，"
            "但被合併版仍獨立註冊於同一事件，會重複執行）:"
        )
        print(header)
        logger.warning(header)
        sys.stderr.write(header + "\n")
        for event_type, merger_name, merged_name in merge_violations:
            line = f"  - {event_type}: {merger_name} 已宣告合併 {merged_name}，但兩者皆註冊"
            print(line)
            logger.warning(line)
            sys.stderr.write(line + "\n")
        advice = "建議: 從 settings.json 移除被合併版的註冊（保留檔案本身供回溯）"
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

    # --- opt-in prune（1.4.0-W2-013.4）：--fix 移除 settings.local.json 幽靈 hook ---
    # 偵測層（上方 WARNING）一律執行；移除動作僅在明示 --fix 時觸發（opt-in，不誤動）。
    if "--fix" in sys.argv:
        pruned = prune_phantom_local_registrations(
            settings_local_path, project_root, apply=True
        )
        if pruned:
            header = (
                f"\n[HookCheck --fix] 已從 settings.local.json 移除 "
                f"{len(pruned)} 個幽靈 hook 註冊（command 指向不存在檔）:"
            )
            print(header)
            logger.info(header)
            for event_type, path in pruned:
                line = f"  - [{event_type}] {path}"
                print(line)
                logger.info(line)
        else:
            msg = "\n[HookCheck --fix] settings.local.json 無幽靈 hook 註冊，無需修正"
            print(msg)
            logger.info(msg)

    log_output = "=" * 60

    print(log_output)

    logger.info(log_output)

    # Exit 0 to not block session start (warning only)
    return 0


if __name__ == '__main__':
    sys.exit(run_hook_safely(main, "hook-completeness-check"))
