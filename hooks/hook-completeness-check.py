#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook Completeness Check

Verifies that all hooks defined in hook-registry.json are properly
registered in settings.json. Runs on SessionStart to catch missing
configurations across different work environments.

Usage:
    python3 .claude/hooks/hook-completeness-check.py

Exit codes:
    0 - All hooks properly configured
    0 - Missing hooks detected (warning only, does not block)
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional


def load_json_file(file_path: Path) -> Optional[dict]:
    """Load and parse a JSON file."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[HookCheck] Error parsing {file_path}: {e}", file=sys.stderr)
        return None


def extract_commands_from_settings(settings: dict) -> Dict[str, Dict[str, Set[str]]]:
    """Extract all hook commands from settings.json grouped by event and matcher."""
    result = {}
    hooks_config = settings.get('hooks', {})

    for event_type, event_hooks in hooks_config.items():
        result[event_type] = {}
        for hook_group in event_hooks:
            matcher = hook_group.get('matcher', '__default__')
            commands = set()
            for hook in hook_group.get('hooks', []):
                cmd = hook.get('command', '')
                # Normalize: remove arguments like "$CLAUDE_FILE_PATH"
                base_cmd = cmd.split()[0] if cmd else ''
                if base_cmd:
                    commands.add(base_cmd)
            if matcher not in result[event_type]:
                result[event_type][matcher] = set()
            result[event_type][matcher].update(commands)

    return result


def extract_commands_from_registry(registry: dict) -> Dict[str, Dict[str, Set[str]]]:
    """Extract all hook commands from hook-registry.json grouped by event and matcher."""
    result = {}
    hooks_config = registry.get('hooks', {})

    for event_type, event_hooks in hooks_config.items():
        result[event_type] = {}
        for hook_group in event_hooks:
            matcher = hook_group.get('matcher') or '__default__'
            commands = set(hook_group.get('commands', []))
            if matcher not in result[event_type]:
                result[event_type][matcher] = set()
            result[event_type][matcher].update(commands)

    return result


def find_missing_hooks(registry_hooks: dict, settings_hooks: dict) -> List[Tuple[str, str, str]]:
    """Find hooks that are in registry but not in settings."""
    missing = []

    for event_type, matchers in registry_hooks.items():
        for matcher, required_commands in matchers.items():
            actual_commands = settings_hooks.get(event_type, {}).get(matcher, set())
            for cmd in required_commands:
                if cmd not in actual_commands:
                    display_matcher = matcher if matcher != '__default__' else '(default)'
                    missing.append((event_type, display_matcher, cmd))

    return missing


def find_extra_hooks(registry_hooks: dict, settings_hooks: dict) -> List[Tuple[str, str, str]]:
    """Find hooks that are in settings but not in registry."""
    extra = []

    for event_type, matchers in settings_hooks.items():
        for matcher, actual_commands in matchers.items():
            required_commands = registry_hooks.get(event_type, {}).get(matcher, set())
            for cmd in actual_commands:
                if cmd not in required_commands:
                    display_matcher = matcher if matcher != '__default__' else '(default)'
                    extra.append((event_type, display_matcher, cmd))

    return extra


def main():
    # Determine project root (where .claude directory is)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # .claude/hooks -> .claude -> project_root

    registry_path = project_root / '.claude' / 'hooks' / 'hook-registry.json'
    settings_path = project_root / '.claude' / 'settings.json'

    # Load files
    registry = load_json_file(registry_path)
    settings = load_json_file(settings_path)

    if registry is None:
        print("[HookCheck] Warning: hook-registry.json not found, skipping check", file=sys.stderr)
        sys.exit(0)

    if settings is None:
        print("[HookCheck] Warning: settings.json not found, skipping check", file=sys.stderr)
        sys.exit(0)

    # Extract and compare
    registry_hooks = extract_commands_from_registry(registry)
    settings_hooks = extract_commands_from_settings(settings)

    missing = find_missing_hooks(registry_hooks, settings_hooks)
    extra = find_extra_hooks(registry_hooks, settings_hooks)

    # Report results
    if not missing and not extra:
        print("[HookCheck] All hooks properly configured", file=sys.stderr)
        sys.exit(0)

    if missing:
        print("[HookCheck] Missing hooks detected:", file=sys.stderr)
        for event_type, matcher, cmd in missing:
            print(f"  - {event_type}/{matcher}: {cmd}", file=sys.stderr)

    if extra:
        print("[HookCheck] Extra hooks (not in registry):", file=sys.stderr)
        for event_type, matcher, cmd in extra:
            print(f"  - {event_type}/{matcher}: {cmd}", file=sys.stderr)
        print("[HookCheck] Consider adding them to hook-registry.json", file=sys.stderr)

    if missing:
        print("[HookCheck] Run: Edit .claude/settings.json to add missing hooks", file=sys.stderr)

    # Exit 0 to not block session start, just warn
    sys.exit(0)


if __name__ == '__main__':
    main()
