#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pyyaml>=5.0",
# ]
# ///

"""
Python Package Version Sync Hook

Monitors installed Python packages and detects content changes.
Automatically reinstalls packages when their source code changes.

Hook Event: SessionStart

Purpose:
    When Python package source code (in .claude/skills/*) is modified,
    the package environment may become stale.
    This hook detects the mismatch and syncs via 'uv run' to keep them in sync.

How it works:
    1. Loads tracked packages from .claude/installed-packages.json
    2. Computes SHA256 hashes of all .py files in each package directory
    3. Compares with previously recorded hashes
    4. For changed packages: validates via 'uv run --directory {path}'
    5. Updates tracking file with new hashes and timestamp

Exit codes:
    0 - Sync successful or no action needed
    1 - Warnings (unable to process, but continue)
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


def get_project_root() -> Path:
    """Get project root from CLAUDE_PROJECT_DIR or infer from current location."""
    if "CLAUDE_PROJECT_DIR" in os.environ:
        return Path(os.environ["CLAUDE_PROJECT_DIR"])

    # Fallback: infer from hook location (.claude/hooks/xxx.py)
    hook_dir = Path(__file__).parent
    return hook_dir.parent.parent


def load_tracking_file(tracking_file: Path) -> Dict:
    """Load the installed packages tracking file."""
    if not tracking_file.exists():
        return {"packages": {}}

    try:
        with open(tracking_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"packages": {}}


def save_tracking_file(tracking_file: Path, data: Dict) -> bool:
    """Save the installed packages tracking file."""
    try:
        with open(tracking_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def compute_package_hash(package_dir: Path) -> str:
    """
    Compute SHA256 hash of all .py files in a package directory.

    Args:
        package_dir: Path to the package directory

    Returns:
        SHA256 hex digest of concatenated file hashes, or empty string if error
    """
    if not package_dir.exists():
        return ""

    file_hashes = []

    try:
        # Get all .py files, sorted for consistency
        py_files = sorted(package_dir.rglob("*.py"))

        for py_file in py_files:
            # Skip __pycache__, .venv, venv, .pytest_cache directories
            if any(
                skip_part in py_file.parts
                for skip_part in ["__pycache__", ".venv", "venv", ".pytest_cache", "test_env", "test_venv"]
            ):
                continue

            try:
                with open(py_file, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    file_hashes.append(file_hash)
            except Exception:
                # Skip files that can't be read
                continue

        if not file_hashes:
            return ""

        # Combine all file hashes and compute final hash
        combined = "".join(file_hashes).encode()
        return hashlib.sha256(combined).hexdigest()
    except Exception:
        return ""


def sync_package(project_root: Path, package_path: str) -> bool:
    """
    Sync a package via 'uv run --directory {path}' to ensure dependencies are resolved.

    Uses 'uv run' instead of 'uv pip install -e' so no project-level .venv is needed.
    Each package manages its own environment via its pyproject.toml.

    Args:
        project_root: Root directory of the project
        package_path: Relative path to the package (from project root)

    Returns:
        True if successful, False otherwise
    """
    package_full_path = project_root / package_path

    if not package_full_path.exists():
        return False

    try:
        result = subprocess.run(
            ["uv", "run", "--directory", str(package_full_path), "python", "-c", "pass"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        return False
    except Exception:
        return False


def format_time_iso8601() -> str:
    """Return current time in ISO 8601 format with UTC timezone."""
    return datetime.now(timezone.utc).isoformat()


def main():
    logger = setup_hook_logging("package-version-sync-hook")
    project_root = get_project_root()
    tracking_file = project_root / ".claude" / "installed-packages.json"

    # Load tracking file
    tracking_data = load_tracking_file(tracking_file)
    packages = tracking_data.get("packages", {})

    if not packages:
        # No packages to track
        print("Package Version Sync - No packages configured")
        return 0

    # Print header
    print("=" * 60)
    print("Package Version Sync - Session Startup Check")
    print("=" * 60)

    # Track if any package was updated
    any_updated = False

    # Check each package
    for package_name, package_info in packages.items():
        package_path = package_info.get("path", "")

        if not package_path:
            print(f"{package_name}: Invalid package path")
            continue

        package_full_path = project_root / package_path

        if not package_full_path.exists():
            print(f"{package_name}: Package directory not found")
            continue

        # Compute current hash
        current_hash = compute_package_hash(package_full_path)

        if not current_hash:
            print(f"{package_name}: Unable to compute hash")
            continue

        # Get previous hash
        previous_hash = package_info.get("content_hash", "")

        # Compare hashes
        if current_hash == previous_hash and previous_hash:
            # No change
            print(f"{package_name}: No changes (up to date)")
            continue

        # Changes detected
        print(f"{package_name}: Changes detected, reinstalling...")

        # Reinstall
        if sync_package(project_root, package_path):
            # Success - update tracking file
            package_info["content_hash"] = current_hash
            package_info["last_synced"] = format_time_iso8601()
            print(f"{package_name}: Sync successful")
            any_updated = True
        else:
            # Failed
            print(f"{package_name}: Sync failed (continuing with stale package)")

    # Save updated tracking file if any package changed
    if any_updated:
        save_tracking_file(tracking_file, tracking_data)

    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "package-version-sync-hook"))
