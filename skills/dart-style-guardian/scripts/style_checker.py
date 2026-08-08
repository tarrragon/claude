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
    exempt_count: int = 0

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
# Project Calibration
# =============================================================================

CONFIG_RELATIVE_PATH = ".claude/config/dart-style-guardian.json"

# 中性預設：不指名任何 token 類別。指名等於斷言某套命名是對的，而各專案的
# design system 命名並不相同——把某一專案的命名寫成預設，讀者照建議動手就會
# 寫出不存在的類別。缺設定時退回描述性敘述，讀者仍知道該往哪找。
DEFAULT_TOKENS: dict[str, str | None] = {
    "color": None,
    "spacing": None,
    "font_size": None,
    "border_radius": None,
}
DEFAULT_I18N_ACCESSOR: str | None = None
DEFAULT_I18N_COMPLIANCE_PATTERN = r"AppLocalizations\.of\(|context\.l10n"
DEFAULT_EXEMPT_MARKERS = ["magic-exempt", "i18n-exempt"]


@dataclass
class StyleConfig:
    """Project-specific calibration for token naming, i18n access, and exemptions."""
    tokens: dict[str, str | None] = field(default_factory=lambda: dict(DEFAULT_TOKENS))
    i18n_accessor: str | None = DEFAULT_I18N_ACCESSOR
    i18n_compliance_pattern: str = DEFAULT_I18N_COMPLIANCE_PATTERN
    exempt_markers: list[str] = field(default_factory=lambda: list(DEFAULT_EXEMPT_MARKERS))
    loaded_from: Path | None = None

    def token(self, kind: str, fallback: str) -> str:
        """Return the configured token class name, or a descriptive fallback."""
        name = self.tokens.get(kind)
        return name if name else fallback


def find_project_root(start: Path) -> Path | None:
    """Walk upward looking for the directory that owns .claude/."""
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (candidate / ".claude").is_dir():
            return candidate
    return None


def load_config(start: Path | None = None) -> StyleConfig:
    """Load project calibration, falling back to neutral defaults with a notice.

    A missing config is not an error: the scanner still detects hardcoded values,
    it just cannot name the replacement token. Staying silent would be worse than
    the notice — the reader would take another project's naming as this project's
    answer, which is exactly the failure this configuration exists to prevent.
    """
    root = find_project_root(start or Path.cwd())
    if root is None:
        print(
            "[style-guardian] 找不到 .claude/ 目錄，使用中性預設（不指名 token 類別）。",
            file=sys.stderr,
        )
        return StyleConfig()

    config_path = root / CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        print(
            f"[style-guardian] 未找到 {CONFIG_RELATIVE_PATH}，使用中性預設。"
            " 建立該檔可讓修正建議指名本專案實際的 token 類別。",
            file=sys.stderr,
        )
        return StyleConfig()

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"[style-guardian] 讀取 {config_path} 失敗（{exc}），使用中性預設。",
            file=sys.stderr,
        )
        return StyleConfig()

    tokens = dict(DEFAULT_TOKENS)
    tokens.update({k: v for k, v in raw.get("tokens", {}).items() if k in tokens})
    i18n = raw.get("i18n", {})
    return StyleConfig(
        tokens=tokens,
        i18n_accessor=i18n.get("accessor") or DEFAULT_I18N_ACCESSOR,
        i18n_compliance_pattern=(
            i18n.get("compliance_pattern") or DEFAULT_I18N_COMPLIANCE_PATTERN
        ),
        exempt_markers=raw.get("exempt_markers") or list(DEFAULT_EXEMPT_MARKERS),
        loaded_from=config_path,
    )


# =============================================================================
# Detection Patterns
# =============================================================================


def build_pattern_groups(config: StyleConfig) -> dict[str, list[tuple[str, str]]]:
    """Build detection patterns whose suggestions speak this project's vocabulary."""
    color = config.token("color", "專案 design system 的 color token")
    spacing = config.token("spacing", "專案 design system 的 spacing token")
    font_size = config.token("font_size", "專案 design system 的 typography token")
    radius = config.token("border_radius", "專案 design system 的 border radius token")
    l10n = config.i18n_accessor or "ARB 產生的 localization 存取子（見專案 l10n.yaml）"

    return {
        "Color": [
            (r'Colors\.(blue|green|red|orange|amber|grey|white|black)(?:\[\d+\])?',
             f'改用 {color}'),
            (r'Color\(0x[Ff][Ff][0-9A-Fa-f]{6}\)',
             f'改用 {color}，勿寫死 hex'),
            (r'\.withOpacity\(',
             'withOpacity 已棄用，改用 .withValues(alpha:)'),
        ],
        "SizedBox": [
            (r'SizedBox\s*\(\s*(?:height|width)\s*:\s*(\d+(?:\.\d+)?)\s*[,\)]',
             f'改用 {spacing}'),
        ],
        "EdgeInsets": [
            (r'EdgeInsets\.(all|symmetric|only|fromLTRB)\s*\([^)]*\b(\d+(?:\.\d+)?)\b',
             f'改用 {spacing}'),
        ],
        "FontSize": [
            (r'fontSize\s*:\s*(\d+(?:\.\d+)?)\s*[,\)]',
             f'改用 {font_size}'),
        ],
        "BorderRadius": [
            (r'BorderRadius\.circular\s*\(\s*(\d+(?:\.\d+)?)\s*\)',
             f'改用 {radius}'),
        ],
        "i18n": [
            (r"Text\s*\(\s*['\"](?!http|[A-Z_]+|v\d)[^'\"]+['\"]",
             f'字串移入 ARB，改用 {l10n}'),
            (r"title\s*:\s*Text\s*\(\s*['\"][^'\"]+['\"]",
             f'AppBar 標題移入 ARB，改用 {l10n}'),
            (r"(?:labelText|hintText)\s*:\s*['\"][^'\"]+['\"]",
             f'label 與 hint 移入 ARB，改用 {l10n}'),
        ],
    }

# Files/directories to exclude
EXCLUDE_PATTERNS = [
    r'\.g\.dart$',           # Generated files
    r'\.freezed\.dart$',     # Freezed generated
    r'\.mocks\.dart$',       # Mock files
    r'/test/',               # Test files (may have hardcoded test strings)
    r'/l10n/',               # Localization files
    r'/generated/',          # Generated code
    r'/design_system/',      # Design system token SSOT directory (any project)
    r'_config\.dart$',       # Config files (e.g. ui_config.dart, flat_design_config.dart)
    r'theme\.dart$',         # Theme configuration (idiomatic Flutter naming)
]

# Line-level exceptions that hold regardless of project calibration.
# Project-specific ones (token classes, i18n accessor, exempt markers) are
# derived from StyleConfig in build_exception_patterns.
BASE_EXCEPTION_PATTERNS = [
    r'//\s*OK:',             # Explicitly marked as OK
    r'//\s*ignore:',         # Explicitly ignored
]


def build_exception_patterns(config: StyleConfig) -> list[str]:
    """Patterns marking a line as already compliant for this project."""
    patterns = list(BASE_EXCEPTION_PATTERNS)
    patterns.append(config.i18n_compliance_pattern)
    for name in config.tokens.values():
        if name:
            patterns.append(rf'{re.escape(name)}\.')
    return patterns


def build_exempt_pattern(config: StyleConfig) -> str | None:
    """Regex matching any configured exemption marker, or None when unset."""
    markers = [re.escape(m) for m in config.exempt_markers if m]
    return "|".join(markers) if markers else None


def should_skip_file(file_path: str) -> bool:
    """Check if file should be skipped."""
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, file_path):
            return True
    return False


def should_skip_line(line: str, exception_patterns: list[str]) -> bool:
    """Check if line already complies and needs no further checking."""
    for pattern in exception_patterns:
        if re.search(pattern, line):
            return True
    return False


def check_patterns(
    content: str,
    patterns: list[tuple[str, str]],
    category: str,
    file_path: str,
    exception_patterns: list[str],
    exempt_pattern: str | None,
) -> Generator[Violation | str, None, None]:
    """Yield violations, or the sentinel 'EXEMPT' for each suppressed match.

    Exempt matches are surfaced as a count rather than dropped: a silently
    skipped line is indistinguishable from a line the scanner cannot see, and
    the reader has no way to tell whether the marker is doing its job or the
    detection is broken.
    """
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        if should_skip_line(line, exception_patterns):
            continue

        is_exempt = bool(exempt_pattern and re.search(exempt_pattern, line))

        for pattern, suggestion in patterns:
            for match in re.finditer(pattern, line):
                if is_exempt:
                    yield "EXEMPT"
                    continue
                yield Violation(
                    file=file_path,
                    line=line_num,
                    category=category,
                    pattern=match.group(0)[:50],  # Truncate for readability
                    suggestion=suggestion,
                )


def scan_file(file_path: Path, config: StyleConfig | None = None) -> ScanResult:
    """Scan a single Dart file for violations."""
    config = config or load_config(file_path.parent)
    result = ScanResult(files_scanned=1)

    if should_skip_file(str(file_path)):
        return result

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return result

    exception_patterns = build_exception_patterns(config)
    exempt_pattern = build_exempt_pattern(config)

    for category, patterns in build_pattern_groups(config).items():
        for item in check_patterns(
            content, patterns, category, str(file_path),
            exception_patterns, exempt_pattern,
        ):
            if item == "EXEMPT":
                result.exempt_count += 1
            else:
                result.add(item)

    return result


def scan_directory(dir_path: Path, config: StyleConfig | None = None) -> ScanResult:
    """Scan a directory recursively for Dart files."""
    config = config or load_config(dir_path)
    result = ScanResult()

    for file_path in dir_path.rglob("*.dart"):
        file_result = scan_file(file_path, config)
        result.files_scanned += file_result.files_scanned
        result.exempt_count += file_result.exempt_count
        result.violations.extend(file_result.violations)

    return result


def format_violation(v: Violation) -> str:
    """Format a violation for display."""
    return f"  {v.file}:{v.line}: [{v.category}] {v.pattern}\n    -> {v.suggestion}"


def format_exempt_line(result: ScanResult) -> str:
    return f"Exempt (marked in source): {result.exempt_count}"


def print_report(result: ScanResult) -> None:
    """Print a formatted report of scan results."""
    if not result.has_violations():
        print(f"No style violations found in {result.files_scanned} files.")
        if result.exempt_count:
            print(format_exempt_line(result))
        return

    print(f"\nStyle Guardian Report")
    print(f"=" * 60)
    print(f"Files scanned: {result.files_scanned}")
    print(f"Total violations: {len(result.violations)}")
    if result.exempt_count:
        print(format_exempt_line(result))
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
        "exempt_count": result.exempt_count,
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
