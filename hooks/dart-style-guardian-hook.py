#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Dart Style Guardian PostEdit Hook

Automatically checks edited files for style violations.
Integrated with the dart-style-guardian SKILL.

Hook Type: PostToolUse (Edit, Write, MultiEdit)
Trigger: When editing files in lib/presentation/

Usage:
    This hook is called automatically by Claude Code.
    Configure in .claude/settings.local.json:

    {
      "hooks": {
        "postToolUse": [
          {
            "matcher": "Edit|Write|MultiEdit",
            "command": "uv run .claude/hooks/dart-style-guardian-hook.py \"$CLAUDE_FILE_PATHS\""
          }
        ]
      }
    }

Exit Codes:
    0 - Success (continue) - No violations or file not in scope
    0 - Success (continue) - Violations found but informational only

Output:
    JSON format for Claude Code hook system
"""

import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely
from lib.hook_messages import QualityMessages

# 偵測規則與專案校準一律取自 skill 的 style_checker，本 hook 不另維護第二套。
# 兩套規則各自演化的結果是 hook 說「改用 UIColors」而 skill 說「改用
# AppPalette」，讀者無從判斷哪個算數。
_SKILL_SCRIPTS = (
    Path(__file__).parent.parent / "skills" / "dart-style-guardian" / "scripts"
)
sys.path.insert(0, str(_SKILL_SCRIPTS))
try:
    from style_checker import (
        build_exempt_pattern,
        build_exception_patterns,
        build_pattern_groups,
        load_config,
        should_skip_line,
    )
    STYLE_CHECKER_AVAILABLE = True
except ImportError as exc:  # skill 目錄被移除或改名時降級為只檢查原生元件
    print(
        f"[dart-style-guardian-hook] 無法載入 style_checker（{exc}），"
        "本次僅執行原生元件檢查，樣式與 i18n 規則略過。",
        file=sys.stderr,
    )
    STYLE_CHECKER_AVAILABLE = False


def is_presentation_file(file_path: str) -> bool:
    """Check if file is in the presentation layer."""
    return '/lib/presentation/' in file_path or file_path.startswith('lib/presentation/')


def should_skip_file(file_path: str) -> bool:
    """Check if file should be skipped."""
    skip_patterns = [
        r'\.g\.dart$',
        r'\.freezed\.dart$',
        r'\.mocks\.dart$',
        r'/test/',
        r'/l10n/',
        r'/generated/',
        r'ui_config\.dart$',
        r'flat_design_config\.dart$',
        r'responsive_config\.dart$',
        r'theme\.dart$',
    ]
    for pattern in skip_patterns:
        if re.search(pattern, file_path):
            return True
    return False


def should_skip_line_safe(line: str, exception_patterns: list[str]) -> bool:
    """Delegate to style_checker when available; degrade to no-skip otherwise."""
    if not STYLE_CHECKER_AVAILABLE:
        return False
    return should_skip_line(line, exception_patterns)


def check_file_for_violations(file_path: Path) -> list[dict]:
    """Quick check for common violations."""
    violations = []

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception:
        return []

    lines = content.split('\n')

    # Native component direct-use patterns (spec §14.3 禁用對照表)
    # word-boundary anchored to avoid matching AppCard / _buildXxxChip etc.
    native_component_patterns = [
        (r'\bTextButton\(', 'NativeComponent', 'Use AppButton instead'),
        (r'\bElevatedButton\(', 'NativeComponent', 'Use AppButton instead'),
        (r'\bCard\(', 'NativeComponent', 'Use AppCard instead'),
        (r'\bAlertDialog\(', 'NativeComponent', 'Use AppDialog instead'),
        (r'\bshowDialog\(', 'NativeComponent', 'Use AppDialog helper instead'),
        (r'\bDivider\(', 'NativeComponent', 'Use AppDivider instead'),
        (r'\bChip\(', 'NativeComponent', 'Use AppBadge/AppChip instead'),
        (r'\bChoiceChip\(', 'NativeComponent', 'Use AppChip instead'),
    ]

    # Line-level exclusions for native component patterns (spec §14.3 注意事項)
    native_exclusion_patterns = [
        r'\bApp(Card|Button|Dialog|Divider|Badge|Chip)\b',  # already migrated
        r'ThemeData',
        r'^\s*(Widget\s+)?_build\w+.*\(',  # _build* method definitions
        r'^\s*import\s',
    ]

    if STYLE_CHECKER_AVAILABLE:
        config = load_config(file_path.parent)
        style_groups = build_pattern_groups(config)
        exception_patterns = build_exception_patterns(config)
        exempt_pattern = build_exempt_pattern(config)
    else:
        style_groups = {}
        exception_patterns = []
        exempt_pattern = None

    for line_num, line in enumerate(lines, 1):
        line_is_exempt = bool(exempt_pattern and re.search(exempt_pattern, line))

        if not line_is_exempt and not should_skip_line_safe(line, exception_patterns):
            for category, patterns in style_groups.items():
                matched = False
                for pattern, suggestion in patterns:
                    if re.search(pattern, line):
                        violations.append({
                            'line': line_num,
                            'category': category,
                            'suggestion': suggestion,
                        })
                        matched = True
                        break  # One violation per category per line is enough
                if matched:
                    break

        # Native component direct-use check (independent exclusion set, WARNING mode)
        if any(re.search(e, line) for e in native_exclusion_patterns):
            continue

        for pattern, category, suggestion in native_component_patterns:
            if re.search(pattern, line):
                violations.append({
                    'line': line_num,
                    'category': category,
                    'suggestion': suggestion,
                })
                break

    return violations


def main() -> int:
    """Main hook entry point."""
    logger = setup_hook_logging("dart-style-guardian-hook")
    # Get file paths from argument
    if len(sys.argv) < 2:
        # No files to check
        print(json.dumps({"continue": True}))
        logger.info("No files to check")
        return 0

    file_paths_str = sys.argv[1]

    # Parse file paths (comma-separated or newline-separated)
    file_paths = [
        p.strip()
        for p in re.split(r'[,\n]', file_paths_str)
        if p.strip()
    ]

    # Filter to presentation files only
    presentation_files = [
        p for p in file_paths
        if is_presentation_file(p) and not should_skip_file(p)
    ]

    if not presentation_files:
        # No presentation files to check
        print(json.dumps({"continue": True}))
        return 0

    # Check each file
    all_violations = {}
    for file_path in presentation_files:
        path = Path(file_path)
        if path.exists() and path.suffix == '.dart':
            violations = check_file_for_violations(path)
            if violations:
                all_violations[file_path] = violations

    if not all_violations:
        # No violations found
        print(json.dumps({"continue": True}))
        return 0

    # Format output message
    total = sum(len(v) for v in all_violations.values())
    message_lines = [
        QualityMessages.STYLE_CHECK_WARNING.format(issue=f"{total} potential violations detected"),
        "",
        "Consider using unified configuration:",
    ]

    for file_path, violations in all_violations.items():
        message_lines.append(f"\n{file_path}:")
        # Show first 5 violations per file
        for v in violations[:5]:
            message_lines.append(f"  Line {v['line']}: [{v['category']}] {v['suggestion']}")
        if len(violations) > 5:
            message_lines.append(f"  ... and {len(violations) - 5} more")

    message_lines.append("")
    message_lines.append("Run `/dart-style-guardian` for detailed guidance.")

    # Output informational message (don't block)
    output = {
        "continue": True,
        "message": "\n".join(message_lines),
    }

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "dart-style-guardian-hook"))
