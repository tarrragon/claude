#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
5W1H Content Validator

Validates 5W1H decision framework content for:
1. Completeness - All 6 sections present (Who, What, When, Where, Why, How)
2. Format compliance - Executor/Dispatcher format, Task Type format
3. Agile refactor compliance - Task Type matches executor
4. Avoidance language detection - No escape phrases

Usage:
    uv run .claude/skills/5w1h-decision/scripts/validate_5w1h.py "content"
    uv run .claude/skills/5w1h-decision/scripts/validate_5w1h.py --file path/to/file.md
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Avoidance language patterns
AVOIDANCE_PATTERNS = [
    # Quality compromise
    r"\b(too complex|workaround|hack|temporary fix|quick fix)\b",
    r"\b(bypass|ignore for now|will fix later|avoid dealing with|skip for now)\b",
    # Simplification
    r"\b(simpler approach|simpler way|easier approach|simpler method|simplify)\b",
    # Problem ignoring
    r"\b(ignore the issue|architecture debt later|code smell ignore)\b",
    r"\b(just add todo|too many issues skip|technical debt later)\b",
    # Test compromise
    r"\b(simplify test|simplified test|lower test standard|test too strict)\b",
    r"\b(relax test requirement|basic test only|minimal test|reduce test complexity)\b",
    # Code escape
    r"\b(comment out|disable|temporarily disable)\b",
    # Chinese patterns
    r"(太複雜|先將就|暫時性修正|症狀緩解|先這樣處理|臨時解決方案)",
    r"(更簡單的方法|採用更簡單的方法|簡化處理)",
    r"(發現問題但不處理|架構問題先不管|程式異味先忽略)",
    r"(簡化測試|降低測試標準|測試要求太嚴格|放寬測試條件)",
    r"(註解掉|停用功能|暫時關閉)",
]

# Required sections
REQUIRED_SECTIONS = ["Who", "What", "When", "Where", "Why", "How"]

# Task types and their valid executors
TASK_TYPE_EXECUTORS = {
    "Implementation": ["parsley", "sage", "pepper", "basil", "cinnamon", "mint"],
    "Dispatch": ["rosemary"],
    "Review": ["rosemary"],
    "Documentation": ["thyme", "rosemary", "memory-network-builder"],
    "Analysis": ["lavender", "rosemary", "bay", "coriander"],
    "Planning": ["rosemary", "lavender"],
}

# Main thread identifier
MAIN_THREAD = "rosemary"


@dataclass
class ValidationResult:
    """Validation result container."""

    valid: bool
    errors: list[str]
    warnings: list[str]


def check_section_present(content: str, section: str) -> bool:
    """Check if a section is present in content."""
    pattern = rf"(?:^|\n)\s*{section}\s*:"
    return bool(re.search(pattern, content, re.IGNORECASE))


def extract_section(content: str, section: str) -> Optional[str]:
    """Extract section content."""
    pattern = rf"(?:^|\n)\s*{section}\s*:\s*(.+?)(?=\n\s*(?:Who|What|When|Where|Why|How)\s*:|$)"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def check_executor_dispatcher_format(who_content: str) -> tuple[bool, str]:
    """Check Who section for executor/dispatcher format."""
    # Pattern: {agent} (executor) | {dispatcher} (dispatcher)
    # Or: {agent} (self-execute - dispatch/review)
    executor_pattern = r"\(executor\)\s*\|\s*.*\(dispatcher\)"
    self_execute_pattern = r"\(self-execute"

    if re.search(executor_pattern, who_content, re.IGNORECASE):
        return True, ""
    if re.search(self_execute_pattern, who_content, re.IGNORECASE):
        return True, ""

    return False, "Who section must have (executor) | (dispatcher) format"


def check_task_type_format(how_content: str) -> tuple[bool, str, Optional[str]]:
    """Check How section for Task Type format."""
    pattern = r"\[Task Type:\s*(\w+)\]"
    match = re.search(pattern, how_content, re.IGNORECASE)

    if not match:
        return False, "How section must have [Task Type: XXX] prefix", None

    task_type = match.group(1)
    valid_types = list(TASK_TYPE_EXECUTORS.keys())

    if task_type not in valid_types:
        return False, f"Invalid Task Type: {task_type}. Valid: {valid_types}", None

    return True, "", task_type


def extract_executor(who_content: str) -> Optional[str]:
    """Extract executor from Who section."""
    # Try to find agent name before (executor)
    pattern = r"(\w+(?:-\w+)*)\s*\(executor\)"
    match = re.search(pattern, who_content, re.IGNORECASE)
    if match:
        return match.group(1)

    # Check for self-execute pattern
    pattern = r"(\w+(?:-\w+)*)\s*\(self-execute"
    match = re.search(pattern, who_content, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def check_agile_compliance(executor: str, task_type: str) -> tuple[bool, str]:
    """Check if executor matches task type (agile refactor compliance)."""
    valid_executors = TASK_TYPE_EXECUTORS.get(task_type, [])

    # Check if executor matches any valid executor pattern
    executor_lower = executor.lower()

    for valid in valid_executors:
        if valid.lower() in executor_lower:
            return True, ""

    # Special check: main thread doing Implementation
    if task_type == "Implementation" and MAIN_THREAD in executor_lower:
        return False, f"Agile Refactor Violation: Main thread ({executor}) cannot execute Implementation tasks"

    # Special check: agent doing Dispatch
    if task_type == "Dispatch" and MAIN_THREAD not in executor_lower:
        return False, f"Agile Refactor Violation: Agent ({executor}) cannot execute Dispatch tasks"

    return True, ""


def check_avoidance_language(content: str) -> list[str]:
    """Check for avoidance language patterns."""
    found = []

    for pattern in AVOIDANCE_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        found.extend(matches)

    return found


def validate(content: str) -> ValidationResult:
    """Validate 5W1H content."""
    errors = []
    warnings = []

    # 1. Check all sections present
    for section in REQUIRED_SECTIONS:
        if not check_section_present(content, section):
            errors.append(f"Missing required section: {section}")

    # If missing sections, skip format checks
    if errors:
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # 2. Extract sections
    who_content = extract_section(content, "Who") or ""
    how_content = extract_section(content, "How") or ""

    # 3. Check Who format
    valid, msg = check_executor_dispatcher_format(who_content)
    if not valid:
        errors.append(msg)

    # 4. Check How Task Type format
    valid, msg, task_type = check_task_type_format(how_content)
    if not valid:
        errors.append(msg)

    # 5. Check agile compliance (only if we have both executor and task type)
    if task_type:
        executor = extract_executor(who_content)
        if executor:
            valid, msg = check_agile_compliance(executor, task_type)
            if not valid:
                errors.append(msg)
        else:
            warnings.append("Could not extract executor from Who section")

    # 6. Check avoidance language
    avoidance_found = check_avoidance_language(content)
    if avoidance_found:
        errors.append(f"Avoidance language detected: {', '.join(set(avoidance_found))}")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: validate_5w1h.py <content> or --file <path>")
        return 1

    # Check for file mode
    if sys.argv[1] == "--file":
        if len(sys.argv) < 3:
            print("Error: --file requires a path argument")
            return 1
        file_path = Path(sys.argv[2])
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            return 1
        content = file_path.read_text()
    else:
        content = sys.argv[1]

    result = validate(content)

    if result.valid:
        print("5W1H Validation: PASSED")
        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")
        return 0
    else:
        print("5W1H Validation: FAILED")
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")
        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
