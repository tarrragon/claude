#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ticket Manager CLI Version Sync Hook

Verifies that the installed ticket CLI matches the source code.
If differences are detected, automatically reinstalls the CLI.

Hook Event: SessionStart

Purpose:
    When ticket source code is modified, the installed CLI
    (which is a snapshot installed via 'uv tool install') becomes stale.
    This hook detects the mismatch and auto-reinstalls to keep them in sync.

How it works:
    1. Finds the installed ticket CLI via 'which ticket'
    2. Locates source code in .claude/skills/ticket/ticket_system/
    3. Computes SHA256 hashes of all .py files in both locations
    4. Compares hash sets and file presence
    5. If differences: reinstalls via 'uv tool install . --force'
    6. If identical: quick pass (< 1 second)

Exit codes:
    0 - Sync successful or no action needed
    1 - Warnings (uv/ticket not found, reinstall warnings)

重構紀錄 (v0.31.0-W22-001.3):
- 遷移至統一日誌系統 (hook_utils)
"""

import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Set, Dict, Tuple

# 導入 hook_utils
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


def get_project_root(logger: logging.Logger) -> Path:
    """Get project root from CLAUDE_PROJECT_DIR or infer from current location."""
    if "CLAUDE_PROJECT_DIR" in os.environ:
        return Path(os.environ["CLAUDE_PROJECT_DIR"])

    # Fallback: infer from hook location (.claude/hooks/xxx.py)
    hook_dir = Path(__file__).parent
    return hook_dir.parent.parent


def find_ticket_cli_path(logger: logging.Logger) -> Optional[Path]:
    """
    Locate the installed ticket CLI.

    Returns:
        Path to ticket CLI binary, or None if not found
    """
    try:
        result = subprocess.run(
            ["which", "ticket"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.debug(f"Found ticket CLI at {result.stdout.strip()}")
            return Path(result.stdout.strip())
    except Exception as e:
        logger.debug(f"Error finding ticket CLI: {e}")

    return None


def find_ticket_module_path(ticket_binary: Path, logger: logging.Logger) -> Optional[Path]:
    """
    Find the installed ticket module from the CLI binary.

    Strategy:
        1. Read shebang from ticket binary to get Python path
        2. Use that Python to find site-packages
        3. Look for ticket_system module

    Args:
        ticket_binary: Path to the ticket CLI executable
        logger: Logger instance

    Returns:
        Path to ticket_system module, or None if not found
    """
    try:
        with open(ticket_binary, "r", encoding="utf-8", errors="ignore") as f:
            shebang = f.readline()
            if not shebang.startswith("#!"):
                logger.debug("Invalid shebang in ticket binary")
                return None

            python_path = shebang[2:].strip()
            if not python_path:
                logger.debug("Empty Python path in shebang")
                return None

            # Find site-packages from Python executable
            result = subprocess.run(
                [python_path, "-c", "import site; print(site.getsitepackages()[0])"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                site_packages = Path(result.stdout.strip())
                ticket_module = site_packages / "ticket_system"
                if ticket_module.exists():
                    logger.debug(f"Found ticket module at {ticket_module}")
                    return ticket_module
    except Exception as e:
        logger.debug(f"Error finding ticket module: {e}")

    return None


def compute_file_hashes(directory: Path) -> Dict[str, str]:
    """
    Compute SHA256 hashes of all .py files in a directory (recursive).

    Returns:
        Dict mapping relative file paths to their SHA256 hashes
    """
    hashes = {}

    if not directory.exists():
        return hashes

    try:
        for py_file in sorted(directory.rglob("*.py")):
            # Skip __pycache__ and .venv directories
            if "__pycache__" in py_file.parts or ".venv" in py_file.parts:
                continue

            try:
                with open(py_file, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    rel_path = py_file.relative_to(directory)
                    hashes[str(rel_path)] = file_hash
            except Exception:
                # Skip files that can't be read
                pass
    except Exception:
        pass

    return hashes


def compare_source_and_installed(
    source_hashes: Dict[str, str],
    installed_hashes: Dict[str, str]
) -> Tuple[bool, Dict[str, any]]:
    """
    Compare source code hashes with installed version.

    Returns:
        (is_identical: bool, differences: dict with 'added', 'removed', 'modified')
    """
    source_files = set(source_hashes.keys())
    installed_files = set(installed_hashes.keys())

    differences = {
        "added": source_files - installed_files,
        "removed": installed_files - source_files,
        "modified": []
    }

    # Check for modified files
    for file_path in source_files & installed_files:
        if source_hashes[file_path] != installed_hashes[file_path]:
            differences["modified"].append(file_path)

    is_identical = not (
        differences["added"] or
        differences["removed"] or
        differences["modified"]
    )

    return is_identical, differences


def reinstall_ticket_cli(project_root: Path, logger: logging.Logger) -> bool:
    """
    Reinstall ticket CLI via 'uv tool install . --force'

    Args:
        project_root: Project root path
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    ticket_manager_dir = project_root / ".claude" / "skills" / "ticket"

    if not ticket_manager_dir.exists():
        logger.warning("ticket directory not found")
        print("[TicketSync] Warning: ticket directory not found", file=sys.stdout)
        return False

    try:
        result = subprocess.run(
            ["uv", "tool", "install", ".", "--force"],
            cwd=ticket_manager_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.warning("uv tool install failed")
            print("[TicketSync] Warning: uv tool install failed", file=sys.stdout)
            if result.stderr:
                logger.debug(f"uv stderr: {result.stderr[:200]}")
                print(f"  Error: {result.stderr[:200]}", file=sys.stdout)
            return False

        logger.info("ticket CLI reinstalled successfully")
        return True
    except subprocess.TimeoutExpired:
        logger.warning("uv tool install timed out")
        print("[TicketSync] Warning: uv tool install timed out", file=sys.stdout)
        return False
    except FileNotFoundError:
        logger.warning("uv command not found")
        print("[TicketSync] Warning: uv command not found", file=sys.stdout)
        return False
    except Exception as e:
        logger.warning(f"uv tool install failed: {e}")
        print(f"[TicketSync] Warning: uv tool install failed ({e})", file=sys.stdout)
        return False


def format_difference_summary(differences: Dict[str, any]) -> str:
    """Format the differences into a readable summary."""
    parts = []

    if differences["added"]:
        parts.append(f"+ {len(differences['added'])} file(s)")
    if differences["removed"]:
        parts.append(f"- {len(differences['removed'])} file(s)")
    if differences["modified"]:
        parts.append(f"~ {len(differences['modified'])} file(s)")

    return ", ".join(parts)


def main() -> int:
    logger = setup_hook_logging("ticket-reinstall")

    project_root = get_project_root(logger)
    logger.debug(f"Project root: {project_root}")

    # Find source code
    source_dir = project_root / ".claude" / "skills" / "ticket" / "ticket_system"
    if not source_dir.exists():
        logger.warning("ticket source not found")
        print("[TicketSync] Warning: ticket source not found", file=sys.stdout)
        return 0

    # Find installed ticket CLI
    ticket_binary = find_ticket_cli_path(logger)
    if not ticket_binary:
        logger.warning("ticket CLI not installed")
        print("[TicketSync] Warning: ticket CLI not installed", file=sys.stdout)
        return 0

    # Find installed module
    installed_module = find_ticket_module_path(ticket_binary, logger)
    if not installed_module:
        logger.warning("could not locate installed ticket module")
        print("[TicketSync] Warning: could not locate installed ticket module", file=sys.stdout)
        return 0

    # Compute hashes
    source_hashes = compute_file_hashes(source_dir)
    installed_hashes = compute_file_hashes(installed_module)

    if not source_hashes:
        logger.warning("no Python files found in source")
        print("[TicketSync] Warning: no Python files found in source", file=sys.stdout)
        return 0

    # Compare
    is_identical, differences = compare_source_and_installed(
        source_hashes, installed_hashes
    )

    if is_identical:
        # Fast path: everything matches
        logger.info("ticket CLI synchronized")
        print("[TicketSync] ticket CLI synchronized")
        return 0

    # Differences detected - show summary
    summary = format_difference_summary(differences)
    logger.info(f"Differences detected ({summary})")
    print(f"[TicketSync] Differences detected ({summary})", file=sys.stdout)

    # Attempt reinstall
    logger.info("Reinstalling ticket CLI...")
    print("[TicketSync] Reinstalling ticket CLI...", file=sys.stdout)
    success = reinstall_ticket_cli(project_root, logger)

    if success:
        logger.info("ticket CLI reinstalled successfully")
        print("[TicketSync] ticket CLI reinstalled successfully", file=sys.stdout)
        return 0
    else:
        logger.warning("Failed to reinstall, continuing with stale CLI")
        print("[TicketSync] Failed to reinstall, continuing with stale CLI", file=sys.stdout)
        return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "ticket-reinstall")
    sys.exit(exit_code)
