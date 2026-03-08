"""Tests for package-version-sync-hook.py

Tests cover:
- scan_skill_packages(): 6 test cases
- get_installed_uv_tools(): 5 test cases
- Version comparison logic: 5 test cases
- main() integration: 4 test cases
- sync-pull git diff: 3 test cases (Phase 3b-B)
- Boundary conditions: 4 test cases

Total: 27 test cases as designed in Phase 2
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest


# Import the hook module (filename contains hyphens, use importlib)
import importlib.util

_hook_path = str(Path(__file__).parent.parent / "package-version-sync-hook.py")
_spec = importlib.util.spec_from_file_location("package_version_sync_hook", _hook_path)
hook = importlib.util.module_from_spec(_spec)
sys.modules["package_version_sync_hook"] = hook
_spec.loader.exec_module(hook)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_project_root(tmp_path):
    """Create a temporary project root directory."""
    return tmp_path


@pytest.fixture
def skills_dir(temp_project_root):
    """Create a .claude/skills directory in the temp project."""
    skills_path = temp_project_root / ".claude" / "skills"
    skills_path.mkdir(parents=True, exist_ok=True)
    return skills_path


@pytest.fixture
def valid_pyproject_content():
    """Valid pyproject.toml content."""
    return """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-package"
version = "1.0.0"
description = "Test package"
"""


@pytest.fixture
def incomplete_pyproject_no_name():
    """pyproject.toml missing [project].name."""
    return """
[project]
version = "1.0.0"
"""


@pytest.fixture
def incomplete_pyproject_no_version():
    """pyproject.toml missing [project].version."""
    return """
[project]
name = "test-package"
"""


@pytest.fixture
def malformed_toml():
    """Malformed TOML content."""
    return "[project\nversion = 1.0.0"  # Missing closing bracket


# ============================================================================
# Tests for scan_skill_packages()
# ============================================================================


class TestScanSkillPackages:
    """Test cases for scan_skill_packages() function."""

    def test_normal_scan_multiple_skills(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 1.1: Normal scan with multiple valid Skill packages."""
        # Setup: Create 3 skill directories with valid pyproject.toml
        for skill_name in ["ticket", "mermaid-ascii", "project-init"]:
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Create pyproject.toml with different versions
            pyproject_path = skill_dir / "pyproject.toml"
            content = valid_pyproject_content.replace("test-package", f"{skill_name}-system")
            if skill_name == "mermaid-ascii":
                content = content.replace("1.0.0", "0.5.0")
            elif skill_name == "project-init":
                content = content.replace("1.0.0", "1.1.0")
            pyproject_path.write_text(content)

        # Execute
        result = hook.scan_skill_packages(temp_project_root)

        # Verify
        assert len(result) == 3
        assert "ticket-system" in result
        assert "mermaid-ascii-system" in result
        assert "project-init-system" in result
        assert result["ticket-system"]["version"] == "1.0.0"
        assert result["mermaid-ascii-system"]["version"] == "0.5.0"
        assert result["project-init-system"]["version"] == "1.1.0"

    def test_skills_dir_not_exist(self, temp_project_root):
        """Test Case 1.2: Skills directory doesn't exist."""
        # Execute
        result = hook.scan_skill_packages(temp_project_root)

        # Verify
        assert result == {}

    def test_skill_without_pyproject(self, temp_project_root, skills_dir):
        """Test Case 1.3: Skill directory exists but has no pyproject.toml."""
        # Setup: Create skill directory without pyproject.toml
        (skills_dir / "incomplete-skill").mkdir(parents=True, exist_ok=True)

        # Execute
        result = hook.scan_skill_packages(temp_project_root)

        # Verify: Should skip skill without pyproject.toml
        assert result == {}

    def test_missing_required_fields(self, temp_project_root, skills_dir, incomplete_pyproject_no_name):
        """Test Case 1.4: pyproject.toml missing required [project].name or version."""
        # Setup: Create skill with incomplete pyproject.toml
        skill_dir = skills_dir / "incomplete"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(incomplete_pyproject_no_name)

        # Execute
        result = hook.scan_skill_packages(temp_project_root)

        # Verify: Should skip incomplete package
        assert result == {}

    def test_tomllib_fallback(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 1.5: Python < 3.11 fallback to tomli."""
        # Setup: Create valid skill
        skill_dir = skills_dir / "test-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        # Execute: Should work regardless of tomllib availability
        with patch.object(hook, "tomllib", None):
            # Verify tomllib is None
            original_tomllib = hook.tomllib
            hook.tomllib = None
            try:
                result = hook.scan_skill_packages(temp_project_root)
                # Should return empty because _load_pyproject_toml will return None
                assert result == {}
            finally:
                hook.tomllib = original_tomllib

    def test_malformed_toml(self, temp_project_root, skills_dir, malformed_toml):
        """Test Case 1.6: Malformed TOML file is skipped gracefully."""
        # Setup: Create skill with malformed TOML
        skill_dir = skills_dir / "broken-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(malformed_toml)

        # Execute
        result = hook.scan_skill_packages(temp_project_root)

        # Verify: Should skip broken package without raising exception
        assert result == {}


# ============================================================================
# Tests for get_installed_uv_tools()
# ============================================================================


class TestGetInstalledUvTools:
    """Test cases for get_installed_uv_tools() function."""

    def test_normal_output_parsing(self):
        """Test Case 2.1: Parse normal 'uv tool list' output."""
        # Setup
        uv_output = (
            "Tool Name      Version  Executable Location\n"
            "─────────────  ───────  ──────────────────────────\n"
            "ticket-system  1.0.0    ~/.venv/bin/ticket\n"
            "mermaid-ascii  0.5.0    ~/.venv/bin/mermaid\n"
        )

        # Mock subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=uv_output,
                stderr=""
            )

            # Execute
            result = hook.get_installed_uv_tools()

        # Verify
        assert result == {"ticket-system": "1.0.0", "mermaid-ascii": "0.5.0"}

    def test_empty_installed_tools(self):
        """Test Case 2.2: No installed tools."""
        # Setup
        uv_output = (
            "Tool Name  Version  Executable Location\n"
            "─────────  ───────  ──────────────────────"
        )

        # Mock subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=uv_output,
                stderr=""
            )

            # Execute
            result = hook.get_installed_uv_tools()

        # Verify
        assert result == {}

    def test_version_variants(self):
        """Test Case 2.3: Version format variants (v prefix, prerelease)."""
        # Setup
        uv_output = (
            "Tool Name  Version     Executable Location\n"
            "─────────  ──────────  ──────────────────────\n"
            "tool1      1.0.0       ~/.venv/bin/tool1\n"
            "tool2      v1.0.0      ~/.venv/bin/tool2\n"
            "tool3      1.0.0-rc1   ~/.venv/bin/tool3\n"
            "tool4      1.0.0.0     ~/.venv/bin/tool4\n"
        )

        # Mock subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=uv_output,
                stderr=""
            )

            # Execute
            result = hook.get_installed_uv_tools()

        # Verify: v prefix should be stripped
        assert result["tool1"] == "1.0.0"
        assert result["tool2"] == "1.0.0"  # v prefix removed
        assert result["tool3"] == "1.0.0-rc1"  # prerelease preserved
        assert result["tool4"] == "1.0.0.0"

    def test_uv_command_failure(self):
        """Test Case 2.4: 'uv tool list' command fails."""
        # Mock subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: command not found"
            )

            # Execute
            result = hook.get_installed_uv_tools()

        # Verify: Should return empty dict gracefully
        assert result == {}

    def test_special_characters_in_tool_names(self):
        """Test Case 2.5: Tool names with special characters."""
        # Setup
        uv_output = (
            "Tool Name              Version  Executable Location\n"
            "─────────────────────  ───────  ──────────────────────\n"
            "my-tool-123            1.0.0    ~/.venv/bin/my-tool\n"
            "CamelCaseTool          2.0.0    ~/.venv/bin/camel\n"
            "tool_with_underscore   1.5.0    ~/.venv/bin/tool_under\n"
        )

        # Mock subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=uv_output,
                stderr=""
            )

            # Execute
            result = hook.get_installed_uv_tools()

        # Verify
        assert result["my-tool-123"] == "1.0.0"
        assert result["CamelCaseTool"] == "2.0.0"
        assert result["tool_with_underscore"] == "1.5.0"


# ============================================================================
# Tests for version comparison logic
# ============================================================================


class TestVersionComparison:
    """Test cases for should_reinstall() function."""

    def test_versions_identical(self):
        """Test Case 3.1: Versions are identical."""
        # Execute & Verify
        assert not hook.should_reinstall("1.0.0", "1.0.0")
        assert not hook.should_reinstall("0.5.0", "0.5.0")

    def test_version_mismatch_older(self):
        """Test Case 3.2: Installed version is older than desired."""
        # Execute & Verify
        assert hook.should_reinstall("1.0.1", "1.0.0")
        assert hook.should_reinstall("1.1.0", "1.0.0")

    def test_version_mismatch_newer(self):
        """Test Case 3.3: Installed version is newer than desired."""
        # Execute & Verify
        assert hook.should_reinstall("1.0.0", "1.0.1")
        assert hook.should_reinstall("1.0.0", "1.1.0")

    def test_tool_not_installed(self):
        """Test Case 3.4: Tool is not installed (None)."""
        # Execute & Verify
        assert hook.should_reinstall("1.0.0", None)
        assert hook.should_reinstall("0.5.0", None)

    def test_version_normalization(self):
        """Test Case 3.5: Version string variations."""
        # Note: In the current implementation, we use simple string comparison
        # v prefix is removed by get_installed_uv_tools(), so desired version
        # should already be without 'v' prefix
        assert hook.should_reinstall("1.0.0", "v1.0.0")  # String mismatch
        assert not hook.should_reinstall("1.0.0", "1.0.0")


# ============================================================================
# Tests for main() integration
# ============================================================================


class TestMainIntegration:
    """Test cases for main() function integration."""

    def test_normal_flow_no_reinstall_needed(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 4.1: Normal flow - all packages up to date."""
        # Setup: Create skill and mock installed tools
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        with patch("subprocess.run") as mock_run:
            # Mock uv tool list response
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=(
                    "Tool Name      Version  Executable Location\n"
                    "─────────────  ───────  ──────────────────────\n"
                    "test-package   1.0.0    ~/.venv/bin/test\n"
                ),
                stderr=""
            )

            with patch("package_version_sync_hook._get_project_root", return_value=temp_project_root):
                with patch("package_version_sync_hook.setup_hook_logging"):
                    # Execute
                    result = hook.main()

        # Verify
        assert result == 0

    def test_reinstall_multiple_packages(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 4.2: Need to reinstall multiple packages."""
        # Setup: Create multiple skills
        for skill_name, version in [("ticket", "1.0.1"), ("mermaid", "0.5.0")]:
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            content = valid_pyproject_content.replace("test-package", f"{skill_name}-system")
            content = content.replace("1.0.0", version)
            (skill_dir / "pyproject.toml").write_text(content)

        with patch("subprocess.run") as mock_run:
            # Mock uv tool list with old versions
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=(
                    "Tool Name     Version  Executable Location\n"
                    "─────────────  ───────  ──────────────────────\n"
                    "ticket-system  1.0.0    ~/.venv/bin/ticket\n"
                    "mermaid-system 0.4.0    ~/.venv/bin/mermaid\n"
                ),
                stderr=""
            )

            with patch("package_version_sync_hook._get_project_root", return_value=temp_project_root):
                with patch("package_version_sync_hook.setup_hook_logging"):
                    with patch("package_version_sync_hook.reinstall_uv_tool", return_value=True):
                        # Execute
                        result = hook.main()

        # Verify
        assert result == 0

    def test_no_skills_directory(self, temp_project_root):
        """Test Case 4.3: No .claude/skills directory."""
        with patch("package_version_sync_hook._get_project_root", return_value=temp_project_root):
            with patch("package_version_sync_hook.setup_hook_logging"):
                # Execute
                result = hook.main()

        # Verify
        assert result == 0

    def test_error_handling(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 4.4: Error handling during scanning."""
        # Setup: Create skill with valid pyproject
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        with patch("subprocess.run") as mock_run:
            # Mock uv tool list failure
            mock_run.side_effect = Exception("uv not found")

            with patch("package_version_sync_hook._get_project_root", return_value=temp_project_root):
                with patch("package_version_sync_hook.setup_hook_logging"):
                    # Execute - should handle exception gracefully
                    result = hook.main()

        # Verify - main should still return 0 (no action needed)
        assert result == 0


# ============================================================================
# Boundary condition tests
# ============================================================================


class TestCacheMechanism:
    """Test cases for cache mechanism."""

    def test_cache_hit_no_changes(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 5.1: Cache hit when pyproject.toml files are unchanged."""
        # Setup: Create skill directory with pyproject.toml
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        # First scan - create initial packages
        packages = hook.scan_skill_packages(temp_project_root)
        assert len(packages) == 1

        # Create cache
        hook._update_sync_cache(temp_project_root, packages, {"test-package": "1.0.0"})

        # Second scan - same packages, should hit cache
        cache_hit = hook._should_skip_sync_due_to_cache(temp_project_root, packages)
        assert cache_hit is True

    def test_cache_miss_pyproject_modified(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 5.2: Cache miss when pyproject.toml is modified."""
        # Setup: Create initial skill
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        pyproject_path = skill_dir / "pyproject.toml"
        pyproject_path.write_text(valid_pyproject_content)

        # First scan and cache
        packages = hook.scan_skill_packages(temp_project_root)
        hook._update_sync_cache(temp_project_root, packages, {"test-package": "1.0.0"})

        # Modify pyproject.toml
        modified_content = valid_pyproject_content.replace("1.0.0", "1.0.1")
        pyproject_path.write_text(modified_content)

        # Re-scan - should miss cache due to hash change
        packages = hook.scan_skill_packages(temp_project_root)
        cache_hit = hook._should_skip_sync_due_to_cache(temp_project_root, packages)
        assert cache_hit is False

    def test_cache_miss_new_package_added(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 5.3: Cache miss when a new package is added."""
        # Setup: Create initial skill
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        # First scan and cache
        packages = hook.scan_skill_packages(temp_project_root)
        assert len(packages) == 1
        hook._update_sync_cache(temp_project_root, packages, {"test-package": "1.0.0"})

        # Add new package
        new_skill_dir = skills_dir / "mermaid-ascii"
        new_skill_dir.mkdir(parents=True, exist_ok=True)
        content = valid_pyproject_content.replace("test-package", "mermaid-ascii-system").replace("1.0.0", "0.5.0")
        (new_skill_dir / "pyproject.toml").write_text(content)

        # Re-scan - should miss cache due to new package
        packages = hook.scan_skill_packages(temp_project_root)
        assert len(packages) == 2
        cache_hit = hook._should_skip_sync_due_to_cache(temp_project_root, packages)
        assert cache_hit is False

    def test_cache_miss_package_removed(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 5.4: Cache miss when a package is removed."""
        # Setup: Create two skills
        for skill_name in ["ticket", "mermaid-ascii"]:
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            content = valid_pyproject_content.replace("test-package", f"{skill_name}-system")
            (skill_dir / "pyproject.toml").write_text(content)

        # First scan and cache
        packages = hook.scan_skill_packages(temp_project_root)
        assert len(packages) == 2
        hook._update_sync_cache(temp_project_root, packages, {
            "ticket-system": "1.0.0",
            "mermaid-ascii-system": "0.5.0"
        })

        # Remove one package directory
        import shutil
        shutil.rmtree(skills_dir / "mermaid-ascii")

        # Re-scan - should miss cache due to removed package
        packages = hook.scan_skill_packages(temp_project_root)
        assert len(packages) == 1
        cache_hit = hook._should_skip_sync_due_to_cache(temp_project_root, packages)
        assert cache_hit is False

    def test_cache_format_error_fallback_to_sync(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 5.5: Cache format error causes fallback to full sync."""
        # Setup: Create skill
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        # Create corrupted cache
        cache_dir = hook._get_cache_dir(temp_project_root)
        cache_file = cache_dir / hook.SYNC_CACHE_FILENAME
        cache_file.write_text("{invalid json")

        # Scan - should treat corrupted cache as miss
        packages = hook.scan_skill_packages(temp_project_root)
        cache_hit = hook._should_skip_sync_due_to_cache(temp_project_root, packages)
        assert cache_hit is False

    def test_cache_not_exist_triggers_sync(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 5.6: Non-existent cache triggers full sync."""
        # Setup: Create skill
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        # First scan without cache
        packages = hook.scan_skill_packages(temp_project_root)
        cache_hit = hook._should_skip_sync_due_to_cache(temp_project_root, packages)
        assert cache_hit is False

        # After cache creation, should hit
        hook._update_sync_cache(temp_project_root, packages, {"test-package": "1.0.0"})
        cache_hit = hook._should_skip_sync_due_to_cache(temp_project_root, packages)
        assert cache_hit is True


class TestBoundaryConditions:
    """Test cases for boundary conditions."""

    def test_paths_with_spaces(self, tmp_path):
        """Test Case 6.2: Project path contains spaces."""
        # Setup: Create project with spaces in path
        project_root = tmp_path / "my projects" / "test project"
        skills_dir = project_root / ".claude" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)

        pyproject_content = """
[project]
name = "test-package"
version = "1.0.0"
"""
        (skill_dir / "pyproject.toml").write_text(pyproject_content)

        # Execute
        result = hook.scan_skill_packages(project_root)

        # Verify
        assert "test-package" in result
        assert ".claude/skills/ticket" in result["test-package"]["path"]

    def test_permission_denied(self, temp_project_root, skills_dir):
        """Test Case 6.3: Permission denied when reading pyproject.toml."""
        # Setup: Create skill directory with restricted file
        skill_dir = skills_dir / "restricted"
        skill_dir.mkdir(parents=True, exist_ok=True)
        pyproject_path = skill_dir / "pyproject.toml"
        pyproject_path.write_text("[project]\nname = 'test'\nversion = '1.0.0'")

        # Make file unreadable (if possible on this platform)
        try:
            pyproject_path.chmod(0o000)

            # Execute
            result = hook.scan_skill_packages(temp_project_root)

            # Verify: Should skip unreadable file
            assert result == {}
        finally:
            # Restore permissions for cleanup
            try:
                pyproject_path.chmod(0o644)
            except Exception:
                pass

    def test_reinstall_failure(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 6.4: Reinstall fails gracefully."""
        # Setup
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        with patch("subprocess.run") as mock_run:
            # Mock uv tool list
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr=""
            )

            with patch("package_version_sync_hook._get_project_root", return_value=temp_project_root):
                with patch("package_version_sync_hook.setup_hook_logging"):
                    with patch("package_version_sync_hook.reinstall_uv_tool", return_value=False):
                        # Execute
                        result = hook.main()

        # Verify: Should return 0 even if reinstall fails
        assert result == 0


# ============================================================================
# Tests for cache mechanism integration with main()
# ============================================================================


class TestCacheIntegrationWithMain:
    """Test cases for cache mechanism integrated with main()."""

    def test_main_cache_hit_skips_uv_list(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 7.1: main() skips 'uv tool list' when cache hits."""
        # Setup: Create skill
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        # Pre-populate cache
        packages = hook.scan_skill_packages(temp_project_root)
        hook._update_sync_cache(temp_project_root, packages, {"test-package": "1.0.0"})

        with patch("subprocess.run") as mock_run:
            # Should NOT call subprocess (uv tool list)
            mock_run.side_effect = Exception("Should not be called")

            with patch("package_version_sync_hook._get_project_root", return_value=temp_project_root):
                with patch("package_version_sync_hook.setup_hook_logging"):
                    # Execute
                    result = hook.main()

        # Verify: Should skip uv tool list call
        assert result == 0
        assert not mock_run.called

    def test_main_cache_miss_executes_full_sync(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 7.2: main() executes full sync on cache miss."""
        # Setup: Create skill (no cache)
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "pyproject.toml").write_text(valid_pyproject_content)

        with patch("subprocess.run") as mock_run:
            # Mock uv tool list response
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=(
                    "Tool Name      Version  Executable Location\n"
                    "─────────────  ───────  ──────────────────────\n"
                    "test-package   1.0.0    ~/.venv/bin/test\n"
                ),
                stderr=""
            )

            with patch("package_version_sync_hook._get_project_root", return_value=temp_project_root):
                with patch("package_version_sync_hook.setup_hook_logging"):
                    # Execute
                    result = hook.main()

        # Verify: Should call subprocess (uv tool list)
        assert result == 0
        assert mock_run.called

        # Verify cache was created
        cache_hit = hook._should_skip_sync_due_to_cache(
            temp_project_root,
            hook.scan_skill_packages(temp_project_root)
        )
        assert cache_hit is True

    def test_main_cache_updated_after_pyproject_change(self, temp_project_root, skills_dir, valid_pyproject_content):
        """Test Case 7.3: Cache is updated after pyproject.toml change triggers sync."""
        # Setup: Create initial skill and cache
        skill_dir = skills_dir / "ticket"
        skill_dir.mkdir(parents=True, exist_ok=True)
        pyproject_path = skill_dir / "pyproject.toml"
        pyproject_path.write_text(valid_pyproject_content)

        packages = hook.scan_skill_packages(temp_project_root)
        hook._update_sync_cache(temp_project_root, packages, {"test-package": "1.0.0"})

        # Verify initial cache hit
        assert hook._should_skip_sync_due_to_cache(temp_project_root, packages) is True

        # Modify pyproject.toml (version change)
        modified_content = valid_pyproject_content.replace("1.0.0", "1.0.1")
        pyproject_path.write_text(modified_content)

        with patch("subprocess.run") as mock_run:
            # Mock uv tool list (old version)
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=(
                    "Tool Name      Version  Executable Location\n"
                    "─────────────  ───────  ──────────────────────\n"
                    "test-package   1.0.0    ~/.venv/bin/test\n"
                ),
                stderr=""
            )

            with patch("package_version_sync_hook._get_project_root", return_value=temp_project_root):
                with patch("package_version_sync_hook.setup_hook_logging"):
                    with patch("package_version_sync_hook.reinstall_uv_tool", return_value=True):
                        # Execute - should miss cache and perform sync
                        result = hook.main()

        # Verify: result is 0
        assert result == 0

        # Verify cache is updated with new hash
        new_packages = hook.scan_skill_packages(temp_project_root)
        # Next call should hit cache
        assert hook._should_skip_sync_due_to_cache(temp_project_root, new_packages) is True
