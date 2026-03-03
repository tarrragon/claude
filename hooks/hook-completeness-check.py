#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook Completeness Check

Verifies that all Python hook files in .claude/hooks/ directory are
properly registered in settings.json. Uses a directory scan + exclude
list mechanism instead of relying on hook-registry.json.

Runs on SessionStart to catch missing configurations and help maintain
comprehensive hook registration.

Usage:
    python3 .claude/hooks/hook-completeness-check.py

Exit codes:
    0 - All hooks properly configured (or warning only)
    0 - Missing/unregistered hooks detected (warning, does not block)
"""

import json
import os
import sys
import fnmatch
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


def load_json_file(file_path: Path, logger=None) -> Optional[dict]:
    """Load and parse a JSON file."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log_output = f"[HookCheck] Error parsing {file_path}: {e}"
        print(log_output)
        if logger:
            logger.info(log_output)
        return None


def get_exclude_patterns(exclude_list: Optional[dict]) -> Tuple[Set[str], Set[str]]:
    """Extract exact filenames and patterns to exclude from hook-exclude-list.json."""
    exact_excludes: Set[str] = set()
    patterns: Set[str] = set()

    if exclude_list is None:
        # Default excludes if file doesn't exist
        exact_excludes = {
            'common_functions.py',
            'frontmatter_parser.py',
            'markdown_formatter.py',
            'parse-test-json.py'
        }
        patterns = {'*-backup.py'}
        return exact_excludes, patterns

    # Load from configuration
    exact_excludes = set(exclude_list.get('exclude', []))
    patterns = set(exclude_list.get('exclude_patterns', []))

    return exact_excludes, patterns


def should_exclude_file(filename: str, exact_excludes: Set[str], patterns: Set[str]) -> bool:
    """Check if a file should be excluded from registration check."""
    # Check exact matches
    if filename in exact_excludes:
        return True

    # Check patterns
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True

    return False


def scan_hooks_directory(hooks_dir: Path, exact_excludes: Set[str], patterns: Set[str]) -> Set[str]:
    """Scan .claude/hooks directory for all .py files (excluding those in exclude list)."""
    hook_files: Set[str] = set()

    if not hooks_dir.exists():
        return hook_files

    for file_path in hooks_dir.glob('*.py'):
        filename = file_path.name

        # Skip excluded files
        if should_exclude_file(filename, exact_excludes, patterns):
            continue

        hook_files.add(filename)

    return hook_files


def extract_registered_hooks(settings: dict) -> Set[str]:
    """Extract all registered hook filenames from settings.json."""
    registered: Set[str] = set()
    hooks_config = settings.get('hooks', {})

    for event_type, event_hooks in hooks_config.items():
        if isinstance(event_hooks, list):
            for hook_group in event_hooks:
                if isinstance(hook_group, dict):
                    for hook in hook_group.get('hooks', []):
                        if isinstance(hook, dict):
                            command = hook.get('command', '')
                            # Extract filename from command path
                            # e.g., "$CLAUDE_PROJECT_DIR/.claude/hooks/hook-name.py" -> "hook-name.py"
                            if '.claude/hooks/' in command:
                                filename = command.split('.claude/hooks/')[-1]
                                # Remove any trailing arguments
                                filename = filename.split()[0] if filename else ''
                                if filename.endswith('.py'):
                                    registered.add(filename)

    return registered


def main():
    logger = setup_hook_logging("hook-completeness-check")
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    hooks_dir = script_dir
    settings_path = project_root / '.claude' / 'settings.json'
    exclude_list_path = script_dir / 'hook-exclude-list.json'

    # Load configuration files
    settings = load_json_file(settings_path, logger)
    if settings is None:
        log_output = "[HookCheck] Warning: settings.json not found, skipping check"
        print(log_output)
        logger.info(log_output)
        return 0

    exclude_list = load_json_file(exclude_list_path, logger)
    exact_excludes, patterns = get_exclude_patterns(exclude_list)

    # Scan hooks directory
    all_hooks = scan_hooks_directory(hooks_dir, exact_excludes, patterns)
    registered_hooks = extract_registered_hooks(settings)

    # Find unregistered hooks
    unregistered = all_hooks - registered_hooks
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

    log_output = "=" * 60

    print(log_output)

    logger.info(log_output)

    # Exit 0 to not block session start (warning only)
    return 0


if __name__ == '__main__':
    sys.exit(run_hook_safely(main, "hook-completeness-check"))
