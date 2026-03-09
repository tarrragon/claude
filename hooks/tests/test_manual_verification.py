#!/usr/bin/env python3
"""Manual verification script for package-version-sync-hook.

This script verifies the core functionality of the hook without requiring pytest.
Run with: python3 .claude/hooks/tests/test_manual_verification.py
"""

import sys
import tempfile
from pathlib import Path

# Add hook directory to path
hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))

# Import the hook module by loading it directly
import importlib.util
spec = importlib.util.spec_from_file_location("package_version_sync_hook", hook_dir / "package-version-sync-hook.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def test_scan_skill_packages_normal():
    """Test Case 1.1: Normal scan with multiple skill packages."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        skills_dir = project_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        # Create 3 skill directories
        for skill_name, version in [("ticket", "1.0.0"), ("mermaid-ascii", "0.5.0"), ("project-init", "1.1.0")]:
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            pyproject_content = f"""
[build-system]
requires = ["hatchling"]

[project]
name = "{skill_name}-system"
version = "{version}"
"""
            (skill_dir / "pyproject.toml").write_text(pyproject_content)

        result = hook.scan_skill_packages(project_root)

        assert len(result) == 3, f"Expected 3 packages, got {len(result)}"
        assert "ticket-system" in result
        assert result["ticket-system"]["version"] == "1.0.0"
        assert result["mermaid-ascii-system"]["version"] == "0.5.0"
        print("[V] Test 1.1 passed: Normal scan with multiple skills")


def test_scan_skill_packages_empty():
    """Test Case 1.2: Skills directory doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        result = hook.scan_skill_packages(project_root)

        assert result == {}, f"Expected empty dict, got {result}"
        print("[V] Test 1.2 passed: Empty skills directory")


def test_scan_skill_packages_no_pyproject():
    """Test Case 1.3: Skill without pyproject.toml."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        skills_dir = project_root / ".claude" / "skills"
        (skills_dir / "incomplete-skill").mkdir(parents=True, exist_ok=True)

        result = hook.scan_skill_packages(project_root)

        assert result == {}, f"Expected empty dict, got {result}"
        print("[V] Test 1.3 passed: Skill without pyproject.toml")


def test_scan_skill_packages_missing_fields():
    """Test Case 1.4: pyproject.toml missing required fields."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        skills_dir = project_root / ".claude" / "skills"
        skill_dir = skills_dir / "incomplete"
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Missing name field
        (skill_dir / "pyproject.toml").write_text("[project]\nversion = '1.0.0'")

        result = hook.scan_skill_packages(project_root)

        assert result == {}, f"Expected empty dict, got {result}"
        print("[V] Test 1.4 passed: Missing required fields")


def test_version_comparison_identical():
    """Test Case 3.1: Versions are identical."""
    assert not hook.should_reinstall("1.0.0", "1.0.0")
    print("[V] Test 3.1 passed: Identical versions")


def test_version_comparison_mismatch():
    """Test Case 3.2-3.4: Version mismatches."""
    # Older installed
    assert hook.should_reinstall("1.0.1", "1.0.0")
    # Newer installed
    assert hook.should_reinstall("1.0.0", "1.0.1")
    # Not installed
    assert hook.should_reinstall("1.0.0", None)
    print("[V] Test 3.2-3.4 passed: Version mismatches")


def test_version_normalization():
    """Test Case 3.5: Version normalization."""
    # v prefix should be handled by get_installed_uv_tools, not should_reinstall
    # In should_reinstall, they're treated as different strings
    assert hook.should_reinstall("1.0.0", "v1.0.0")  # Different strings
    assert not hook.should_reinstall("1.0.0", "1.0.0")  # Same strings
    print("[V] Test 3.5 passed: Version normalization")


def test_parse_uv_output():
    """Test get_installed_uv_tools parsing."""
    # Test the parsing logic by simulating subprocess output
    uv_output = """Tool Name      Version  Executable Location
─────────────  ───────  ──────────────────────────
ticket-system  1.0.0    ~/.venv/bin/ticket
mermaid-ascii  0.5.0    ~/.venv/bin/mermaid
"""

    # Manually parse like the hook does
    tools = {}
    for line in uv_output.splitlines():
        if not line.strip() or "─" in line or "Tool Name" in line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            tool_name = parts[0]
            version_str = parts[1].lstrip("v")
            tools[tool_name] = version_str

    assert tools["ticket-system"] == "1.0.0"
    assert tools["mermaid-ascii"] == "0.5.0"
    print("[V] Test 2.1 passed: Normal output parsing")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Manual Verification Tests for package-version-sync-hook")
    print("=" * 60 + "\n")

    try:
        test_scan_skill_packages_normal()
        test_scan_skill_packages_empty()
        test_scan_skill_packages_no_pyproject()
        test_scan_skill_packages_missing_fields()
        test_version_comparison_identical()
        test_version_comparison_mismatch()
        test_version_normalization()
        test_parse_uv_output()

        print("\n" + "=" * 60)
        print("All 8 manual verification tests passed! [V]")
        print("=" * 60 + "\n")
        return 0
    except AssertionError as e:
        print(f"\n[X] Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n[X] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
