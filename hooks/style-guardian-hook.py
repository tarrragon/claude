#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Style Guardian PostEdit Hook

Automatically checks edited files for style violations.
Integrated with the style-guardian SKILL.

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
            "command": "uv run .claude/hooks/style-guardian-hook.py \"$CLAUDE_FILE_PATHS\""
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
from hook_utils import setup_hook_logging, run_hook_safely
from lib.hook_messages import QualityMessages


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


def check_file_for_violations(file_path: Path) -> list[dict]:
    """Quick check for common violations."""
    violations = []

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception:
        return []

    lines = content.split('\n')

    # Patterns to check (simplified for hook performance)
    patterns = [
        (r'Colors\.(blue|green|red|orange|amber)', 'Color', 'Use UIColors instead'),
        (r'Color\(0x[Ff][Ff][0-9A-Fa-f]{6}\)', 'Color', 'Use UIColors instead'),
        (r'SizedBox\s*\(\s*(?:height|width)\s*:\s*\d+\s*[,\)]', 'Spacing', 'Use UISpacing instead'),
        (r'EdgeInsets\.(all|symmetric)\s*\([^)]*\b\d+\b', 'Spacing', 'Use UISpacing instead'),
        (r'fontSize\s*:\s*\d+\s*[,\)]', 'Typography', 'Use UIFontSizes instead'),
        (r'BorderRadius\.circular\s*\(\s*\d+\s*\)', 'BorderRadius', 'Use UIBorderRadius instead'),
    ]

    # Exception patterns (already using config)
    exceptions = [
        r'UIColors\.',
        r'UISpacing\.',
        r'UIFontSizes\.',
        r'UIBorderRadius\.',
    ]

    for line_num, line in enumerate(lines, 1):
        # Skip lines that already use config
        if any(re.search(e, line) for e in exceptions):
            continue

        for pattern, category, suggestion in patterns:
            if re.search(pattern, line):
                violations.append({
                    'line': line_num,
                    'category': category,
                    'suggestion': suggestion,
                })
                break  # One violation per line is enough

    return violations


def main() -> int:
    """Main hook entry point."""
    logger = setup_hook_logging("style-guardian-hook")
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
    message_lines.append("Run `/style-guardian` for detailed guidance.")

    # Output informational message (don't block)
    output = {
        "continue": True,
        "message": "\n".join(message_lines),
    }

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "style-guardian-hook"))
