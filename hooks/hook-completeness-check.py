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
import logging
import os
import re
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
from lib.hook_command_resolver import resolve_hook_script_path
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


def extract_registered_commands(
    settings: dict, logger: Optional[logging.Logger] = None
) -> List[Tuple[str, str, str]]:
    """從 settings dict 提取所有 (event_type, matcher, command) 三元組。

    保留 matcher：同一 hook 在同事件下以不同 matcher（如 Edit / Write）註冊
    屬合法多工具覆蓋，非重複；重複偵測須以 (event, matcher, 路徑) 為鍵。

    settings 結構不符預期（`hooks` 非 dict、事件區塊非 list 等）時記錄
    WARNING 並略過該段（回傳結果不含該段），不靜默吞掉——結構異常代表
    本次掃描結果不完整，須讓使用者知道「守衛這次沒真的檢查到」，而非讓
    不完整的結果被誤讀為「確實沒有問題」。
    """
    triples: List[Tuple[str, str, str]] = []
    hooks_config = settings.get("hooks", {})
    if not isinstance(hooks_config, dict):
        msg = (
            f"[HookCheck] settings.json 的 'hooks' 區塊非預期結構"
            f"（型別={type(hooks_config).__name__}，應為 dict），本次掃描略過"
        )
        print(msg)
        if logger:
            logger.warning(msg)
        return triples

    for event_type, event_hooks in hooks_config.items():
        if not isinstance(event_hooks, list):
            msg = (
                f"[HookCheck] settings.json 的 '{event_type}' 事件區塊非預期"
                f"結構（型別={type(event_hooks).__name__}，應為 list），略過此事件"
            )
            print(msg)
            if logger:
                logger.warning(msg)
            continue
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
    settings_sources: List[Tuple[str, Optional[dict]]],
    project_root: Path,
    logger: Optional[logging.Logger] = None,
) -> List[Tuple[str, str, str]]:
    """找出「已註冊但 command 指向不存在的 .py 檔」的幽靈註冊。

    Args:
        settings_sources: [(來源標籤, settings dict 或 None), ...]。
        project_root: 專案根目錄（解析 $CLAUDE_PROJECT_DIR）。
        logger: 選填，傳入時使 extract_registered_commands 的結構異常
            WARNING 寫入日誌檔（非僅 print stdout）。

    Returns:
        [(來源標籤, event_type, 解析後不存在的路徑字串), ...]。
    """
    phantoms: List[Tuple[str, str, str]] = []
    for label, settings in settings_sources:
        if not settings:
            continue
        for event_type, _matcher, command in extract_registered_commands(settings, logger):
            path = resolve_hook_script_path(command, project_root)
            if path is None:
                continue  # 非 .py/.sh 檔 hook（inline shell 等）不檢查
            if not path.exists():
                phantoms.append((label, event_type, str(path)))
    return phantoms


def find_duplicate_registrations(
    settings_sources: List[Tuple[str, Optional[dict]]],
    project_root: Path,
    logger: Optional[logging.Logger] = None,
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
        for event_type, matcher, command in extract_registered_commands(settings, logger):
            path = resolve_hook_script_path(command, project_root)
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
    logger: Optional[logging.Logger] = None,
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
        for event_type, _matcher, command in extract_registered_commands(settings, logger):
            path = resolve_hook_script_path(command, project_root)
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
    settings_local: Optional[dict],
    project_root: Path,
    logger: Optional[logging.Logger] = None,
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
    for event_type, _matcher, command in extract_registered_commands(settings_local, logger):
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
                path = resolve_hook_script_path(command, project_root)
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


_SKILL_HOOK_SKIP_DIRS = frozenset({"__pycache__", ".venv", "node_modules", ".git"})


def _iter_skill_hook_files(skills_dir: Path):
    """走訪 .claude/skills/<skill>/hooks/ 下所有 .py 檔案（遞迴），略過快取/
    虛擬環境目錄。

    與 project_init.lib.hook_checker.scan_skill_hooks 使用相同的目錄結構與
    跳過清單，但回傳 Path 物件供權限操作使用（scan_skill_hooks 回傳相對路徑
    字串集合，供註冊比對使用，兩者用途不同故不合併）。
    """
    if not skills_dir.exists():
        return
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        hooks_subdir = skill_dir / "hooks"
        if not hooks_subdir.is_dir():
            continue
        for file_path in sorted(hooks_subdir.rglob("*.py")):
            rel_parts = file_path.relative_to(skills_dir).parts
            if any(part in _SKILL_HOOK_SKIP_DIRS for part in rel_parts):
                continue
            if not file_path.is_file():
                continue
            yield file_path


def _detect_missing_exec_bit(hooks_dir, logger):
    """掃描 hooks_dir 頂層與 .claude/skills/<skill>/hooks/ 下缺可執行位的
    hook 檔案（偵測版，2026-08-22 降級：不再 chmod）。

    降級理由：settings.json 全部 hook 註冊已改為顯式解譯器形式（`uv run
    --quiet <path>` 或 `python3 <path>`），Claude Code 以直譯器讀檔執行，
    不依賴檔案本身的 exec bit——「已註冊但本輪尚未 chmod 就被執行」的競態
    在此前提下不再成立。舊版的自動 chmod + 自動 commit 因此改為純偵測：
    仍回報缺可執行位的檔案供稽核（如跨平台 mode 遺失），但不再變更檔案、
    不再產生 git mode-only commit。

    hooks_dir 頂層刻意不遞迴：`tests/`、`acceptance_checkers/`、`archived/`
    下的 .py 由 pytest 或 import 載入，從不被直譯器直接執行，掃描範圍維持
    與舊版一致，避免回報無意義的雜訊。skills_dir 由 `hooks_dir.parent /
    "skills"` 推導（即 project_root/.claude/skills/）。skill hooks 下遞迴
    掃描，僅略過快取/虛擬環境目錄（`_iter_skill_hook_files`），因該子樹不
    存在 tests/ 等非執行用途的子目錄。

    Returns:
        (missing_relative_paths, already_ok_count)
        missing_relative_paths 為相對於 project_root（= hooks_dir.parent.
        parent）的路徑字串（如 ".claude/hooks/foo.py"、".claude/skills/bar/
        hooks/baz.py"）。
    """
    project_root = hooks_dir.parent.parent
    skills_dir = hooks_dir.parent / "skills"

    missing = []
    already_ok = 0

    candidates = list(sorted(hooks_dir.glob("*.py"))) + list(
        _iter_skill_hook_files(skills_dir)
    )

    for py_file in candidates:
        if not py_file.is_file():
            continue

        if os.access(py_file, os.X_OK):
            already_ok += 1
        else:
            rel = str(py_file.resolve().relative_to(project_root.resolve()))
            missing.append(rel)
            logger.info(f"缺可執行位（不自動修復）: {rel}")

    return missing, already_ok


def _format_permission_report(ok_count: int, missing_files: List[str]) -> List[str]:
    """組合「權限」區塊的回報行，主計數與本次偵測數分行呈現。

    降級版（2026-08-22）：settings.json 全部 hook 註冊已改為顯式解譯器形式，
    可執行位不再是 hook 被 runtime 呼叫的前提，本函式不再描述「已修復」或
    任何生效時點，只陳述「已確認可執行」與「本次偵測到缺可執行位」兩個
    事實計數，不自動修復、不觸發 git commit。
    """
    lines = [f"權限: {ok_count} 個已確認可執行"]
    if missing_files:
        lines.append(
            f"權限: 本次偵測到缺可執行位 {len(missing_files)} 個"
            "（不自動修復，可執行位非執行前提）"
        )
    return lines


def main():
    logger = setup_hook_logging("hook-completeness-check")
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    hooks_dir = script_dir
    settings_path = project_root / '.claude' / 'settings.json'
    exclude_list_path = script_dir / 'hook-exclude-list.json'

    # --- Permission check（偵測版，2026-08-22 降級：不再 chmod、不再 auto-commit）---
    missing_exec_bit_files, ok_count = _detect_missing_exec_bit(hooks_dir, logger)

    if missing_exec_bit_files:
        log_output = (
            f"[HookCheck] 偵測: {len(missing_exec_bit_files)} 個檔案缺可執行位"
            "（不自動修復，settings.json 皆以顯式解譯器呼叫，可執行位非執行前提）"
        )
        print(log_output)
        logger.info(log_output)
        for name in missing_exec_bit_files[:10]:
            detail = f"  缺可執行位: {name}"
            print(detail)
            logger.info(detail)
        if len(missing_exec_bit_files) > 10:
            more = f"  ... 還有 {len(missing_exec_bit_files) - 10} 個"
            print(more)
            logger.info(more)

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
    for log_output in _format_permission_report(ok_count, missing_exec_bit_files):
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
    phantoms = find_phantom_registrations(settings_sources, project_root, logger)
    duplicates = find_duplicate_registrations(settings_sources, project_root, logger)

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
        hooks_dir, settings_sources, project_root, logger
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
    local_hook_regs = find_local_hook_registrations(settings_local, project_root, logger)
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
