#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Version Consistency Guard Hook

Detects version inconsistencies and alerts on incomplete tasks in older versions
and version mismatches between current_version and work-logs directories.

Hook Event: SessionStart (non-blocking warning)

Purpose:
    1. Prevents version number from advancing (current_version in todolist.yaml)
       while older versions still have pending/in_progress/blocked Tickets.
    2. Alerts when current_version is lower than the highest version directory
       in docs/work-logs/ (indicates todolist.yaml is out of sync).

Logic:
    1. Read current_version from docs/todolist.yaml
    2. Scan all version directories in docs/work-logs/
    3. Check for incomplete Tickets in versions older than current_version
    4. Check for version mismatch (current_version vs highest worklog version)
    5. Print clear warning message(s) (non-blocking)

Exit code:
    0 - Always (non-blocking warning, never prevents session start)
"""

import re
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    get_project_root,
    parse_ticket_frontmatter,
    scan_ticket_files_by_version,
)


# ============================================================================
# Constants
# ============================================================================

INCOMPLETE_STATUSES = {"pending", "in_progress", "blocked"}


# ============================================================================
# Version parsing
# ============================================================================

def parse_version_string(version_str: str) -> Tuple[int, ...]:
    """Parse version string (e.g. '0.1.0') to tuple (0, 1, 0).

    Args:
        version_str: Version string like '0.1.0'

    Returns:
        Tuple of integers, or empty tuple if parsing fails
    """
    try:
        parts = version_str.strip().split(".")
        return tuple(int(p) for p in parts if p.isdigit())
    except (ValueError, AttributeError):
        return ()


def version_is_older(version_a: Tuple[int, ...], version_b: Tuple[int, ...]) -> bool:
    """Check if version_a is older than version_b.

    Args:
        version_a: Tuple like (0, 1, 0)
        version_b: Tuple like (0, 1, 1)

    Returns:
        True if version_a < version_b
    """
    # Pad shorter version with zeros
    max_len = max(len(version_a), len(version_b))
    a_padded = version_a + (0,) * (max_len - len(version_a))
    b_padded = version_b + (0,) * (max_len - len(version_b))
    return a_padded < b_padded


# ============================================================================
# Ticket discovery
# ============================================================================

def get_incomplete_tickets(version_dir: Path, logger, project_root: Path = None) -> List[Dict[str, str]]:
    """Find all incomplete Tickets in a version directory.

    Args:
        version_dir: Path to version directory like v0.1.0
        logger: Logger instance
        project_root: Project root (optional, used for scan_ticket_files_by_version)

    Returns:
        List of dicts with keys: id, status
    """
    tickets_dir = version_dir / "tickets"

    if not tickets_dir.exists():
        return []

    incomplete = []

    try:
        # 提取版本號（例如 v0.1.0 -> 0.1.0）
        version_name = version_dir.name
        version = version_name[1:] if version_name.startswith('v') else version_name

        # 使用共用函式掃描 Ticket 檔案
        if project_root:
            ticket_files = scan_ticket_files_by_version(project_root, version, logger)
        else:
            ticket_files = sorted(tickets_dir.glob("*.md"))

        for ticket_file in sorted(ticket_files) if project_root else ticket_files:
            # Extract ticket ID from filename (e.g. "0.1.0-W1-001.md" -> "0.1.0-W1-001")
            ticket_id = ticket_file.stem

            frontmatter = parse_ticket_frontmatter(ticket_file, logger)
            status = frontmatter.get('status') if frontmatter else None

            if status in INCOMPLETE_STATUSES:
                incomplete.append({
                    "id": ticket_id,
                    "status": status
                })
    except Exception as e:
        logger.warning(f"Error scanning tickets in {tickets_dir}: {e}")

    return incomplete


def find_older_versions_with_incomplete_tickets(
    project_root: Path,
    current_version: str,
    logger
) -> Dict[str, List[Dict[str, str]]]:
    """Find all older versions with incomplete Tickets.

    Args:
        project_root: Project root path
        current_version: Current version string (e.g. '0.1.0')
        logger: Logger instance

    Returns:
        Dict mapping version string to list of incomplete Tickets
    """
    work_logs_dir = project_root / "docs" / "work-logs"

    if not work_logs_dir.exists():
        return {}

    current_ver_tuple = parse_version_string(current_version)
    if not current_ver_tuple:
        logger.warning(f"Failed to parse current_version: {current_version}")
        return {}

    result = {}

    try:
        for version_dir in sorted(work_logs_dir.iterdir()):
            # Only process directories like v0.1.0
            if not version_dir.is_dir():
                continue

            dir_name = version_dir.name
            if not dir_name.startswith('v'):
                continue

            # Extract version from directory name
            version_str = dir_name[1:]  # Remove 'v' prefix

            version_tuple = parse_version_string(version_str)

            if not version_tuple:
                continue

            # Check if this version is older than current_version
            if version_is_older(version_tuple, current_ver_tuple):
                incomplete = get_incomplete_tickets(version_dir, logger, project_root)
                if incomplete:
                    result[version_str] = incomplete

    except Exception as e:
        logger.warning(f"Error scanning work-logs: {e}")

    return result


# ============================================================================
# Output formatting
# ============================================================================

ACTIVE_STATUSES = {"in_progress", "blocked"}


def find_higher_active_versions(
    project_root: Path, current_version: str, logger
) -> List[str]:
    """Find version directories higher than current_version with active Tickets.

    Only versions containing in_progress or blocked Tickets are considered
    a real mismatch signal. Versions with only pending Tickets are normal
    future planning and should not trigger a warning.

    Args:
        project_root: Project root path
        current_version: Current version string from todolist.yaml
        logger: Logger instance

    Returns:
        List of version strings higher than current_version with active Tickets
    """
    work_logs_dir = project_root / "docs" / "work-logs"

    if not work_logs_dir.exists():
        return []

    current_ver_tuple = parse_version_string(current_version)
    if not current_ver_tuple:
        return []

    active_higher = []

    try:
        for version_dir in work_logs_dir.iterdir():
            if not version_dir.is_dir():
                continue

            dir_name = version_dir.name
            if not dir_name.startswith('v'):
                continue

            version_str = dir_name[1:]  # Remove 'v' prefix

            version_tuple = parse_version_string(version_str)
            if not version_tuple:
                continue

            # Only check versions higher than current_version
            if not version_is_older(current_ver_tuple, version_tuple):
                continue

            # Check if this higher version has active (in_progress/blocked) Tickets
            tickets_dir = version_dir / "tickets"
            if not tickets_dir.exists():
                continue

            for ticket_file in tickets_dir.glob("*.md"):
                frontmatter = parse_ticket_frontmatter(ticket_file, logger)
                status = frontmatter.get('status') if frontmatter else None
                if status in ACTIVE_STATUSES:
                    active_higher.append(version_str)
                    break  # One active ticket is enough to flag this version

    except Exception as e:
        logger.warning(f"Error scanning work-logs for higher active versions: {e}")

    return sorted(active_higher, key=lambda v: parse_version_string(v))


def print_warning(current_version: str, older_versions_info: Dict[str, List[Dict[str, str]]]) -> None:
    """Print warning message about incomplete tickets in older versions.

    Args:
        current_version: Current version string
        older_versions_info: Dict mapping version to incomplete Tickets
    """
    separator = "=" * 60

    print()
    print(separator)
    print("[Version Consistency Guard] 發現舊版本未完成的 Ticket")
    print(separator)
    print()
    print(f"current_version: {current_version}（來自 docs/todolist.yaml）")
    print()
    print("以下版本有未完成的 Ticket，請先完成舊版本任務再推進版本號：")
    print()

    # Sort versions (using tuple comparison)
    sorted_versions = sorted(
        older_versions_info.keys(),
        key=lambda v: parse_version_string(v)
    )

    for version in sorted_versions:
        tickets = older_versions_info[version]
        count = len(tickets)
        print(f"  v{version}: {count} 個未完成")

        # Show first few tickets
        for ticket in tickets[:3]:
            ticket_id = ticket['id']
            status = ticket['status']
            print(f"    - {ticket_id} [{status}]")

        if len(tickets) > 3:
            print(f"    ... 還有 {len(tickets) - 3} 個")

    print()
    print("建議：使用 ticket track list --version {version} --status pending in_progress")
    print("      查看完整任務列表")
    print()
    print(separator)
    print()


def print_version_mismatch_warning(current_version: str, active_version: str) -> None:
    """Print warning about active development in a version higher than current_version.

    Args:
        current_version: Current version from todolist.yaml
        active_version: Higher version with in_progress/blocked Tickets
    """
    separator = "=" * 60

    print()
    print(separator)
    print("[Version Consistency Guard] 版本配置可能過期")
    print(separator)
    print()
    print(f"current_version (todolist.yaml): {current_version}")
    print(f"活躍開發版本 (docs/work-logs/):  {active_version}")
    print()
    print(f"v{active_version} 中有 in_progress 或 blocked 的 Ticket，")
    print(f"但 todolist.yaml 的 current_version 仍為 {current_version}。")
    print()
    print("建議：")
    print(f"  修改 docs/todolist.yaml current_version 為 {active_version}")
    print()
    print(separator)
    print()


# ============================================================================
# Main
# ============================================================================

def read_current_version_from_todolist(project_root: Path, logger) -> Optional[str]:
    """Read current_version from docs/todolist.yaml.

    Args:
        project_root: Project root path
        logger: Logger instance

    Returns:
        Version string like '0.1.0', or None if not found or parse error
    """
    todolist_path = project_root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        return None

    try:
        content = todolist_path.read_text(encoding='utf-8')

        # Simple regex search for "current_version: X.Y.Z"
        match = re.search(r'^\s*current_version:\s*(\S+)\s*$', content, re.MULTILINE)
        if match:
            return match.group(1).strip().strip("'\"")

        return None

    except Exception as e:
        logger.warning(f"Failed to read or parse todolist.yaml: {e}")
        return None


def main() -> int:
    """Main hook function."""
    logger = setup_hook_logging("version-consistency-guard-hook")

    # Find project root using hook_utils
    project_root = get_project_root()

    # Read current_version from todolist.yaml
    current_version = read_current_version_from_todolist(project_root, logger)

    if not current_version:
        # No version file or can't parse - silently exit
        logger.debug("Could not read current_version from todolist.yaml")
        return 0

    logger.debug(f"Current version: {current_version}")

    # Find older versions with incomplete tickets
    older_versions_info = find_older_versions_with_incomplete_tickets(
        project_root,
        current_version,
        logger
    )

    if older_versions_info:
        # Print warning (non-blocking)
        print_warning(current_version, older_versions_info)
        logger.info(
            f"Version consistency warning: {len(older_versions_info)} "
            f"older version(s) with incomplete Tickets"
        )
    else:
        logger.debug("No incomplete tickets in older versions")

    # Check for version mismatch: higher versions with active (in_progress/blocked) Tickets
    higher_active = find_higher_active_versions(project_root, current_version, logger)

    if higher_active:
        for version in higher_active:
            print_version_mismatch_warning(current_version, version)
        logger.info(
            f"Version mismatch warning: {len(higher_active)} higher version(s) "
            f"with active Tickets: {', '.join(higher_active)}"
        )
    else:
        logger.debug("No higher versions with active Tickets")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "version-consistency-guard"))
