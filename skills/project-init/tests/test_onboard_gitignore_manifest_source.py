"""onboard 的 .gitignore 必要規則與 SessionStart 檢查同源.

受檢專案帶有 .claude/lib/sync_exclude_manifest.py 時，onboard 以其
required_gitignore_entries() 為必要規則，涵蓋判定以 git check-ignore 探測。
缺 local-only 名稱（如 settings.local.json）的 .gitignore 必須被報缺。
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from project_init.lib.onboard_checker import check_gitignore_completeness

REAL_MANIFEST = Path(__file__).resolve().parents[3] / "lib" / "sync_exclude_manifest.py"


def _load_real_manifest():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_real_manifest", REAL_MANIFEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    lib_dir = tmp_path / ".claude" / "lib"
    lib_dir.mkdir(parents=True)
    shutil.copy(REAL_MANIFEST, lib_dir / "sync_exclude_manifest.py")
    return tmp_path


@pytest.fixture
def required() -> list[str]:
    return sorted(_load_real_manifest().required_gitignore_entries())


def _write_gitignore(project: Path, lines: list[str]) -> None:
    (project / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_complete_manifest_entries_pass(project: Path, required: list[str]) -> None:
    _write_gitignore(project, required)

    result = check_gitignore_completeness(project)

    assert result.missing_rules == []
    assert result.all_required_complete


def test_missing_local_only_entry_is_reported(project: Path, required: list[str]) -> None:
    """正向對照：少了 settings.local.json 的條目必須被報缺（舊的內建清單不含此項）."""
    target = ".claude/**/settings.local.json"
    assert target in required
    _write_gitignore(project, [e for e in required if e != target])

    result = check_gitignore_completeness(project)

    assert result.missing_rules == [target]
    assert not result.all_required_complete


def test_root_only_entry_does_not_cover_nested_name(project: Path, required: list[str]) -> None:
    """`.claude/settings.local.json` 只忽略根層，巢狀位置未涵蓋，仍報缺."""
    target = ".claude/**/settings.local.json"
    lines = [e for e in required if e != target] + [".claude/settings.local.json"]
    _write_gitignore(project, lines)

    result = check_gitignore_completeness(project)

    assert target in result.missing_rules


def test_missing_gitignore_lists_manifest_entries(project: Path, required: list[str]) -> None:
    result = check_gitignore_completeness(project)

    assert not result.exists
    assert result.missing_rules == required


def test_without_manifest_falls_back_with_stderr(tmp_path: Path, capsys) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _write_gitignore(tmp_path, ["coverage/"])

    result = check_gitignore_completeness(tmp_path)

    assert ".claude/worktrees/" in result.missing_rules
    assert "改用內建的退回清單" in capsys.readouterr().err
