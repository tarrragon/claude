"""gitignore-entries 子命令：輸出與 SessionStart gitignore 檢查的缺項集合同源."""

import importlib.util
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from project_init.commands.gitignore_entries import run_gitignore_entries

REPO_CLAUDE = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_CLAUDE / "hooks" / "session-start-gitignore-check-hook.py"
LIB_FILES = ("sync_exclude_manifest.py", "ticket_lock_gitignore.py")


def _load_hook():
    sys.path.insert(0, str(REPO_CLAUDE))
    sys.path.insert(0, str(HOOK_PATH.parent))
    spec = importlib.util.spec_from_file_location("_gitignore_hook_under_test", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_project(tmp_path: Path, lib_files=LIB_FILES) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    lib_dir = tmp_path / ".claude" / "lib"
    lib_dir.mkdir(parents=True)
    for name in lib_files:
        shutil.copy(REPO_CLAUDE / "lib" / name, lib_dir / name)
    return tmp_path


def test_output_equals_hook_missing_set_on_empty_gitignore(tmp_path, capsys):
    project = _make_project(tmp_path)
    hook = _load_hook()
    expected, _tracked, _exists = hook.run_checks(
        project, logging.getLogger("t"), code_root=project
    )

    rc = run_gitignore_entries(project)

    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert set(out) == set(expected)
    assert len(out) == len(expected) > 1


def test_missing_manifest_prints_no_list_and_fails(tmp_path, capsys):
    project = _make_project(tmp_path, lib_files=())

    rc = run_gitignore_entries(project)

    captured = capsys.readouterr()
    assert rc != 0
    assert captured.out == ""
    assert "sync_exclude_manifest" in captured.err


def test_missing_lock_module_prints_manifest_entries_and_fails(tmp_path, capsys):
    project = _make_project(tmp_path, lib_files=("sync_exclude_manifest.py",))

    rc = run_gitignore_entries(project)

    captured = capsys.readouterr()
    assert rc != 0
    assert captured.out.strip() != ""
    assert "**/*.md.lock" not in captured.out
    assert "lock" in captured.err


@pytest.mark.parametrize("flag", [None])
def test_cli_registers_subcommand(flag):
    from project_init.scripts.main import _create_parser

    args = _create_parser().parse_args(["gitignore-entries"])
    assert args.command == "gitignore-entries"
