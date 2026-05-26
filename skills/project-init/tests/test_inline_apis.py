"""Test inlined pyproject_scanner API in package_manager.

Verifies W3-051 inline 5 APIs behave equivalently to .claude/lib/pyproject_scanner.py.
"""

from pathlib import Path

import pytest

from project_init.lib.package_manager import (
    extract_cli_name_from_pyproject,
    extract_package_name_from_pyproject,
    extract_version_from_pyproject,
    load_pyproject_toml,
    scan_skills_directory,
)


@pytest.fixture
def sample_pyproject(tmp_path: Path) -> Path:
    """Create a sample pyproject.toml."""
    content = """
[project]
name = "sample-pkg"
version = "1.2.3"

[project.scripts]
sample-cli = "sample.main:run"
secondary-cli = "sample.other:run"
"""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(content)
    return pyproject


@pytest.fixture
def minimal_pyproject(tmp_path: Path) -> Path:
    """Create a minimal pyproject.toml without scripts."""
    content = """
[project]
name = "minimal-pkg"
version = "0.1.0"
"""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(content)
    return pyproject


def test_load_pyproject_toml_success(sample_pyproject: Path):
    data = load_pyproject_toml(sample_pyproject)
    assert data is not None
    assert data["project"]["name"] == "sample-pkg"


def test_load_pyproject_toml_missing_file(tmp_path: Path):
    result = load_pyproject_toml(tmp_path / "nonexistent.toml")
    assert result is None


def test_load_pyproject_toml_invalid_content(tmp_path: Path):
    bad = tmp_path / "bad.toml"
    bad.write_text("not valid [[[ toml")
    assert load_pyproject_toml(bad) is None


def test_extract_version(sample_pyproject: Path):
    assert extract_version_from_pyproject(sample_pyproject) == "1.2.3"


def test_extract_version_missing(tmp_path: Path):
    p = tmp_path / "pyproject.toml"
    p.write_text("[project]\nname = \"x\"\n")
    assert extract_version_from_pyproject(p) is None


def test_extract_package_name(sample_pyproject: Path):
    assert extract_package_name_from_pyproject(sample_pyproject) == "sample-pkg"


def test_extract_package_name_missing(tmp_path: Path):
    p = tmp_path / "pyproject.toml"
    p.write_text("[project]\nversion = \"1.0\"\n")
    assert extract_package_name_from_pyproject(p) is None


def test_extract_cli_name_returns_first(sample_pyproject: Path):
    # 應該回傳 [project.scripts] 第一個 key
    assert extract_cli_name_from_pyproject(sample_pyproject) == "sample-cli"


def test_extract_cli_name_no_scripts(minimal_pyproject: Path):
    assert extract_cli_name_from_pyproject(minimal_pyproject) is None


def test_scan_skills_directory_empty(tmp_path: Path):
    # 無 .claude/skills/ 目錄
    result = scan_skills_directory(tmp_path)
    assert result == {}


def test_scan_skills_directory_with_packages(tmp_path: Path):
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)

    # Package A：含 scripts → 應被收錄
    pkg_a = skills / "pkg-a"
    pkg_a.mkdir()
    (pkg_a / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nversion = "1.0.0"\n'
        '[project.scripts]\npkg-a-cli = "pkg_a.main:run"\n'
    )

    # Package B：無 scripts → 應被略過
    pkg_b = skills / "pkg-b"
    pkg_b.mkdir()
    (pkg_b / "pyproject.toml").write_text(
        '[project]\nname = "pkg-b"\nversion = "2.0.0"\n'
    )

    # Package C：含 scripts → 應被收錄
    pkg_c = skills / "pkg-c"
    pkg_c.mkdir()
    (pkg_c / "pyproject.toml").write_text(
        '[project]\nname = "pkg-c"\nversion = "3.1.0"\n'
        '[project.scripts]\npkg-c = "pkg_c.x:run"\n'
    )

    result = scan_skills_directory(tmp_path)
    assert set(result.keys()) == {"pkg-a", "pkg-c"}
    assert result["pkg-a"]["version"] == "1.0.0"
    assert result["pkg-a"]["path"] == ".claude/skills/pkg-a"
    assert result["pkg-c"]["version"] == "3.1.0"


def test_scan_skills_directory_skips_non_dirs(tmp_path: Path):
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    # 放一個檔案（非目錄）
    (skills / "stray-file.txt").write_text("hi")

    # 正常 package
    pkg = skills / "real-pkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "real-pkg"\nversion = "0.1.0"\n'
        '[project.scripts]\nreal = "x.y:z"\n'
    )

    result = scan_skills_directory(tmp_path)
    assert list(result.keys()) == ["real-pkg"]


def test_inline_api_equivalent_to_lib_module(sample_pyproject: Path):
    """驗證 inline API 與 .claude/lib/pyproject_scanner.py 行為等價。"""
    # 動態載入 .claude/lib/pyproject_scanner（hook side SSOT）
    import importlib.util
    import sys as _sys

    repo_root = Path(__file__).resolve().parents[4]
    lib_path = repo_root / ".claude" / "lib" / "pyproject_scanner.py"
    if not lib_path.exists():
        pytest.skip(f"hook side lib not found: {lib_path}")

    spec = importlib.util.spec_from_file_location("_hook_pyproject_scanner", lib_path)
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["_hook_pyproject_scanner"] = mod
    spec.loader.exec_module(mod)

    # 四個 single-file API 行為對齊
    assert load_pyproject_toml(sample_pyproject) == mod.load_pyproject_toml(sample_pyproject)
    assert extract_version_from_pyproject(sample_pyproject) == mod.extract_version_from_pyproject(sample_pyproject)
    assert extract_package_name_from_pyproject(sample_pyproject) == mod.extract_package_name_from_pyproject(sample_pyproject)
    assert extract_cli_name_from_pyproject(sample_pyproject) == mod.extract_cli_name_from_pyproject(sample_pyproject)
