#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
CLI Dependency Check Hook

Checks required CLI tools (rg) at session start.

Hook Event: SessionStart

Purpose:
    Ensures CLI search tools are available before the session begins.

Checked tools:
    - rg (ripgrep): Text search engine, used by built-in Grep

Exit codes:
    0 - All tools available or auto-install succeeded
    1 - Critical failure (should not block session)
"""

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


# ---------------------------------------------------------------------------
# Claude Code bundled tool checks
# ---------------------------------------------------------------------------

def _check_claude_bundled_rg():
    """Check if Claude Code's bundled ripgrep is available.

    Claude Code aliases `rg` to `<claude_binary> --ripgrep` at runtime.
    This alias is invisible to Python subprocesses, so we check the binary
    directly using the known installation path pattern.

    Returns:
        version string if found, None otherwise
    """
    import glob as globmod
    from pathlib import Path

    claude_dir = Path.home() / ".local" / "share" / "claude" / "versions"
    if not claude_dir.exists():
        return None

    # Find the latest version directory
    versions = sorted(claude_dir.iterdir(), reverse=True)
    for ver_path in versions:
        if ver_path.is_file():
            try:
                result = subprocess.run(
                    [str(ver_path), "--ripgrep", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return result.stdout.strip().split("\n")[0]
            except (subprocess.TimeoutExpired, OSError):
                continue
    return None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "rg",
        "display": "ripgrep",
        "check_version": ["rg", "--version"],
        "auto_install": None,  # Too many platform variants, just advise
        "install_hint": {
            "darwin": "brew install ripgrep",
            "linux": "sudo apt-get install ripgrep",
            "default": "cargo install ripgrep",
        },
        "required": False,  # Built-in Grep is a fallback
        # Claude Code bundles rg as `claude_binary --ripgrep`.
        # The alias is only visible inside the interactive shell,
        # so we also check this fallback path.
        "bundled_check": _check_claude_bundled_rg,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_platform_key():
    """Return a platform key for install hints."""
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    return "default"


def check_tool(name):
    """Check if a CLI tool is available on PATH or as a shell alias."""
    if shutil.which(name) is not None:
        return True

    # Fallback: try running via shell (catches aliases like rg -> claude --ripgrep)
    try:
        result = subprocess.run(
            f"command -v {name}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def get_version(cmd):
    """Run a version command and return the first line of output."""
    # Try direct execution first
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Fallback: try via shell (for aliases)
    try:
        cmd_str = " ".join(cmd)
        result = subprocess.run(
            cmd_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except (subprocess.TimeoutExpired, OSError):
        pass

    return None


def auto_install(cmd):
    """Attempt to install a tool. Returns (success, message)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, "auto-install succeeded"
        return False, result.stderr.strip()[:200] if result.stderr else "unknown error"
    except subprocess.TimeoutExpired:
        return False, "install timed out"
    except FileNotFoundError:
        installer = cmd[0] if cmd else "unknown"
        return False, f"{installer} not found"
    except OSError as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger = setup_hook_logging("cli-dependency-check")
    plat = get_platform_key()
    results = []
    any_missing = False

    for tool in TOOLS:
        name = tool["name"]
        display = tool["display"]

        if check_tool(name):
            version = get_version(tool["check_version"])
            version_str = version if version else "version unknown"
            results.append(f"  [OK] {display}: {version_str}")
            continue

        # Check bundled version (e.g. Claude Code's built-in rg)
        bundled_check = tool.get("bundled_check")
        if bundled_check:
            bundled_version = bundled_check()
            if bundled_version:
                results.append(f"  [OK] {display}: {bundled_version} (bundled)")
                continue

        # Tool is missing
        any_missing = True

        # Try auto-install if available
        if tool["auto_install"]:
            install_cmd = tool["auto_install"]
            results.append(f"  [MISSING] {display}: attempting auto-install...")
            success, msg = auto_install(install_cmd)

            if success:
                # Verify it's now available
                if check_tool(name):
                    version = get_version(tool["check_version"])
                    version_str = version if version else "installed"
                    results.append(f"  [INSTALLED] {display}: {version_str}")
                    continue
                else:
                    results.append(f"  [WARNING] {display}: installed but not on PATH")
            else:
                results.append(f"  [FAILED] {display}: {msg}")

        # Show install hint
        hints = tool["install_hint"]
        hint = hints.get(plat, hints.get("default", "see documentation"))
        results.append(f"  [HINT] Install manually: {hint}")

    # Output
    if any_missing:
        output = "=" * 60 + "\nCLI Dependency Check\n" + "=" * 60 + "\n"
        output += "\n".join(results) + "\n" + "=" * 60
        print(output)
        logger.info("CLI dependency check completed with missing tools:\n" + output)
    else:
        # Compact output when everything is OK
        status_parts = []
        for tool in TOOLS:
            version = get_version(tool["check_version"])
            if not version:
                bundled_fn = tool.get("bundled_check")
                version = bundled_fn() if bundled_fn else None
            short = version.split()[0] if version else tool["name"]
            status_parts.append(short)
        output = f"[CLI Check] OK: {', '.join(status_parts)}"
        print(output)
        logger.info(output)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "cli-dependency-check"))
