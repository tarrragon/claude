"""Shared Python project scanner module for pyproject.toml parsing and extraction.

This module provides unified functions for scanning .claude/skills/ directory
and extracting package information from pyproject.toml files.

It's designed to be used by both:
- Hook: .claude/hooks/package-version-sync-hook.py
- CLI: .claude/skills/project-init/project_init/lib/package_manager.py

API:
    load_pyproject_toml(path: Path) → Optional[dict]
    extract_version_from_pyproject(path: Path) → Optional[str]
    extract_package_name_from_pyproject(path: Path) → Optional[str]
    extract_cli_name_from_pyproject(path: Path) → Optional[str]
    scan_skills_directory(project_root: Path) → Dict[str, Dict[str, str]]
"""

from pathlib import Path
from typing import Dict, Optional

# TOML 解析：試圖使用 tomllib（Python 3.11+），否則 fallback 到 tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


# ============================================================================
# Constants
# ============================================================================

SKILLS_DIR_NAME = ".claude/skills"
PYPROJECT_FILENAME = "pyproject.toml"


# ============================================================================
# Public API
# ============================================================================


def load_pyproject_toml(pyproject_path: Path) -> Optional[Dict]:
    """Load and parse a pyproject.toml file.

    Attempts to use tomllib (Python 3.11+) or tomli fallback (Python 3.9-3.10).
    Returns None if the file cannot be parsed.

    Args:
        pyproject_path: Path to the pyproject.toml file.

    Returns:
        Parsed TOML dict, or None if parsing fails or tomllib unavailable.
    """
    if tomllib is None:
        return None

    try:
        with open(pyproject_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


def extract_version_from_pyproject(pyproject_path: Path) -> Optional[str]:
    """Extract version string from pyproject.toml.

    Retrieves the version from [project] table using structured TOML parsing.

    Args:
        pyproject_path: Path to the pyproject.toml file.

    Returns:
        Version string (e.g., "1.0.0"), or None if not found or parsing fails.
    """
    data = load_pyproject_toml(pyproject_path)
    if data is None:
        return None

    try:
        return data.get("project", {}).get("version")
    except Exception:
        return None


def extract_package_name_from_pyproject(pyproject_path: Path) -> Optional[str]:
    """Extract package name from pyproject.toml.

    Retrieves the name from [project] table. This is the name used by pip/uv.

    Args:
        pyproject_path: Path to the pyproject.toml file.

    Returns:
        Package name (e.g., "ticket-system"), or None if not found.
    """
    data = load_pyproject_toml(pyproject_path)
    if data is None:
        return None

    try:
        return data.get("project", {}).get("name")
    except Exception:
        return None


def extract_cli_name_from_pyproject(pyproject_path: Path) -> Optional[str]:
    """Extract CLI command name from pyproject.toml.

    Retrieves the first entry point name from [project.scripts] table.

    Args:
        pyproject_path: Path to the pyproject.toml file.

    Returns:
        CLI command name (e.g., "ticket"), or None if not found.
    """
    data = load_pyproject_toml(pyproject_path)
    if data is None:
        return None

    try:
        scripts = data.get("project", {}).get("scripts", {})
        if scripts:
            return next(iter(scripts.keys()))
    except Exception:
        return None

    return None


def scan_skills_directory(
    project_root: Path,
) -> Dict[str, Dict[str, str]]:
    """Scan .claude/skills/ directory and extract package information.

    Traverses the skills directory and parses each pyproject.toml to extract
    package name and version. Returns a dictionary mapping package names to
    their metadata in Hook-compatible format.

    Args:
        project_root: Root directory of the project.

    Returns:
        Dict mapping package name → {"path": relative_path, "version": version_str}.
        Returns empty dict if skills directory doesn't exist or no packages found.

    Example:
        {
            "ticket-system": {
                "path": ".claude/skills/ticket",
                "version": "1.0.0"
            },
            "mermaid-ascii": {
                "path": ".claude/skills/mermaid-ascii",
                "version": "0.5.0"
            }
        }
    """
    packages: Dict[str, Dict[str, str]] = {}
    skills_dir = project_root / SKILLS_DIR_NAME

    if not skills_dir.exists():
        return packages

    try:
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            pyproject_path = skill_dir / PYPROJECT_FILENAME
            if not pyproject_path.exists():
                continue

            try:
                pkg_name = extract_package_name_from_pyproject(pyproject_path)
                version = extract_version_from_pyproject(pyproject_path)

                if pkg_name and version:
                    packages[pkg_name] = {
                        "path": str(skill_dir.relative_to(project_root)),
                        "version": version,
                    }
            except Exception:
                # Skip packages that fail to parse
                continue
    except Exception:
        # If iterating skills_dir fails, return what we have
        pass

    return packages
