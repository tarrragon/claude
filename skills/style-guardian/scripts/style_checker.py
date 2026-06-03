#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Style Guardian - Unified Design System Checker

Detects hardcoded styles and i18n violations in Flutter/Dart code.

Usage:
    uv run style_checker.py scan <path>     # Scan directory or file
    uv run style_checker.py report          # Generate summary report
    uv run style_checker.py check <file>    # Check single file (for hooks)

Exit codes:
    0 - No violations found
    1 - Violations found
    2 - Error occurred
"""

import sys
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Generator
from collections import defaultdict


@dataclass
class Violation:
    """Represents a single style violation."""
    file: str
    line: int
    category: str
    pattern: str
    suggestion: str
    severity: str = "warning"  # warning, error


@dataclass
class ScanResult:
    """Results from scanning a file or directory."""
    violations: list[Violation] = field(default_factory=list)
    files_scanned: int = 0

    def add(self, violation: Violation) -> None:
        self.violations.append(violation)

    def has_violations(self) -> bool:
        return len(self.violations) > 0

    def by_category(self) -> dict[str, list[Violation]]:
        result = defaultdict(list)
        for v in self.violations:
            result[v.category].append(v)
        return dict(result)

    def by_file(self) -> dict[str, list[Violation]]:
        result = defaultdict(list)
        for v in self.violations:
            result[v.file].append(v)
        return dict(result)


# =============================================================================
# Detection Patterns
# =============================================================================

# Color violations
COLOR_PATTERNS = [
    # Material colors
    (r'Colors\.(blue|green|red|orange|amber|grey|white|black)(?:\[\d+\])?',
     'Use UIColors.primary/positive/negative instead'),
    # Hex colors
    (r'Color\(0x[Ff][Ff][0-9A-Fa-f]{6}\)',
     'Use UIColors constants instead of hex colors'),
    # withOpacity (deprecated)
    (r'\.withOpacity\(',
     'Use .withValues(alpha:) instead of withOpacity'),
]

# Spacing violations (SizedBox)
SIZEDBOX_PATTERNS = [
    (r'SizedBox\s*\(\s*(?:height|width)\s*:\s*(\d+(?:\.\d+)?)\s*[,\)]',
     'Use UISpacing.xs/sm/md/lg instead of hardcoded values'),
]

# EdgeInsets violations
EDGEINSETS_PATTERNS = [
    (r'EdgeInsets\.(all|symmetric|only|fromLTRB)\s*\([^)]*\b(\d+(?:\.\d+)?)\b',
     'Use UISpacing constants instead of hardcoded values'),
]

# Font size violations
FONTSIZE_PATTERNS = [
    (r'fontSize\s*:\s*(\d+(?:\.\d+)?)\s*[,\)]',
     'Use UIFontSizes.bodyMedium/titleLarge etc instead'),
]

# Border radius violations
BORDERRADIUS_PATTERNS = [
    (r'BorderRadius\.circular\s*\(\s*(\d+(?:\.\d+)?)\s*\)',
     'Use UIBorderRadius.xs/sm/md/lg instead'),
]

# i18n violations - hardcoded strings
I18N_PATTERNS = [
    # Text widget with literal string
    (r"Text\s*\(\s*['\"](?!http|[A-Z_]+|v\d)[^'\"]+['\"]",
     'Use context.l10n!.keyName instead of hardcoded text'),
    # Title in AppBar
    (r"title\s*:\s*Text\s*\(\s*['\"][^'\"]+['\"]",
     'Use context.l10n!.titleKey for AppBar titles'),
    # label/hint text
    (r"(?:labelText|hintText)\s*:\s*['\"][^'\"]+['\"]",
     'Use context.l10n!.key for input labels and hints'),
]

# Files/directories to exclude
EXCLUDE_PATTERNS = [
    r'\.g\.dart$',           # Generated files
    r'\.freezed\.dart$',     # Freezed generated
    r'\.mocks\.dart$',       # Mock files
    r'/test/',               # Test files (may have hardcoded test strings)
    r'/l10n/',               # Localization files
    r'/generated/',          # Generated code
    r'ui_config\.dart$',     # Configuration file itself
    r'flat_design_config\.dart$',  # Config file
    r'responsive_config\.dart$',   # Config file
    r'theme\.dart$',         # Theme configuration
]

# Exceptions - patterns that are OK
EXCEPTION_PATTERNS = [
    r'UIColors\.',           # Already using UIColors
    r'UISpacing\.',          # Already using UISpacing
    r'UIFontSizes\.',        # Already using UIFontSizes
    r'UIBorderRadius\.',     # Already using UIBorderRadius
    r'context\.l10n',        # Already using l10n
    r'//\s*OK:',             # Explicitly marked as OK
    r'//\s*ignore:',         # Explicitly ignored
]


def should_skip_file(file_path: str) -> bool:
    """Check if file should be skipped."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False


def should_skip_line(line: str) -> bool:
    """Check if line should be skipped."""
    for pattern in EXCEPTION_PATTERNS:
        if re.search(pattern, line):
            return True
    return False


def check_patterns(
    content: str,
    patterns: list[tuple[str, str]],
    category: str,
    file_path: str
) -> Generator[Violation, None, None]:
    """Check content against patterns and yield violations."""
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        if should_skip_line(line):
            continue

        for pattern, suggestion in patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                # Double-check this line doesn't have exceptions
                if not should_skip_line(line):
                    yield Violation(
                        file=file_path,
                        line=line_num,
                        category=category,
                        pattern=match.group(0)[:50],  # Truncate for readability
                        suggestion=suggestion,
                    )


def scan_file(file_path: Path) -> ScanResult:
    """Scan a single Dart file for violations."""
    result = ScanResult(files_scanned=1)

    if should_skip_file(str(file_path)):
        return result

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return result

    # Check all pattern categories
    for v in check_patterns(content, COLOR_PATTERNS, "Color", str(file_path)):
        result.add(v)

    for v in check_patterns(content, SIZEDBOX_PATTERNS, "SizedBox", str(file_path)):
        result.add(v)

    for v in check_patterns(content, EDGEINSETS_PATTERNS, "EdgeInsets", str(file_path)):
        result.add(v)

    for v in check_patterns(content, FONTSIZE_PATTERNS, "FontSize", str(file_path)):
        result.add(v)

    for v in check_patterns(content, BORDERRADIUS_PATTERNS, "BorderRadius", str(file_path)):
        result.add(v)

    for v in check_patterns(content, I18N_PATTERNS, "i18n", str(file_path)):
        result.add(v)

    return result


def scan_directory(dir_path: Path) -> ScanResult:
    """Scan a directory recursively for Dart files."""
    result = ScanResult()

    for file_path in dir_path.rglob("*.dart"):
        file_result = scan_file(file_path)
        result.files_scanned += file_result.files_scanned
        result.violations.extend(file_result.violations)

    return result


def format_violation(v: Violation) -> str:
    """Format a violation for display."""
    return f"  {v.file}:{v.line}: [{v.category}] {v.pattern}\n    -> {v.suggestion}"


def print_report(result: ScanResult) -> None:
    """Print a formatted report of scan results."""
    if not result.has_violations():
        print(f"No style violations found in {result.files_scanned} files.")
        return

    print(f"\nStyle Guardian Report")
    print(f"=" * 60)
    print(f"Files scanned: {result.files_scanned}")
    print(f"Total violations: {len(result.violations)}")
    print()

    # Summary by category
    by_category = result.by_category()
    print("Violations by category:")
    for category, violations in sorted(by_category.items()):
        print(f"  {category}: {len(violations)}")
    print()

    # Details by file
    print("Details:")
    print("-" * 60)
    by_file = result.by_file()
    for file_path, violations in sorted(by_file.items()):
        print(f"\n{file_path} ({len(violations)} violations):")
        for v in violations[:10]:  # Limit to first 10 per file
            print(format_violation(v))
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more")


def print_json_report(result: ScanResult) -> None:
    """Print a JSON report for hook integration."""
    output = {
        "files_scanned": result.files_scanned,
        "total_violations": len(result.violations),
        "violations": [
            {
                "file": v.file,
                "line": v.line,
                "category": v.category,
                "pattern": v.pattern,
                "suggestion": v.suggestion,
            }
            for v in result.violations
        ]
    }
    print(json.dumps(output, indent=2))


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    command = sys.argv[1]

    if command == "scan":
        if len(sys.argv) < 3:
            print("Usage: style_checker.py scan <path>")
            return 2

        path = Path(sys.argv[2])
        if path.is_file():
            result = scan_file(path)
        elif path.is_dir():
            result = scan_directory(path)
        else:
            print(f"Error: {path} not found")
            return 2

        print_report(result)
        return 1 if result.has_violations() else 0

    elif command == "check":
        # For hook integration - JSON output
        if len(sys.argv) < 3:
            print("Usage: style_checker.py check <file>")
            return 2

        path = Path(sys.argv[2])
        if not path.is_file():
            print(f"Error: {path} not found")
            return 2

        result = scan_file(path)
        print_json_report(result)
        return 1 if result.has_violations() else 0

    elif command == "report":
        # Scan lib/ directory and generate report
        lib_path = Path("lib")
        if not lib_path.exists():
            # Try relative to script location
            script_dir = Path(__file__).parent.parent.parent.parent.parent
            lib_path = script_dir / "lib"

        if not lib_path.exists():
            print("Error: lib/ directory not found")
            return 2

        result = scan_directory(lib_path)
        print_report(result)
        return 1 if result.has_violations() else 0

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        return 2


if __name__ == "__main__":
    sys.exit(main())
