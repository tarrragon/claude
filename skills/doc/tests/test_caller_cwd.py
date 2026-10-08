"""shim 以 uv --directory 啟動時，相對路徑引數須以呼叫者 cwd 解析。"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system import cli
from doc_system.core.file_locator import FileLocator
from tests.test_uc import _setup_project

SKILL_DIR = Path(cli.__file__).resolve().parent.parent


def _run_as_shim(monkeypatch, caller_dir: str, path_arg: str) -> int:
    """模擬 shim：行程 cwd 為 skill 目錄，呼叫者 cwd 由環境變數帶入。"""
    monkeypatch.chdir(SKILL_DIR)
    monkeypatch.setenv(cli.CALLER_CWD_ENV, caller_dir)
    monkeypatch.setattr(sys, "argv", ["doc", "uc", "verify", path_arg])
    with patch.object(FileLocator, "get_project_root", return_value=caller_dir):
        with pytest.raises(SystemExit) as exc_info:
            cli.main()
    return exc_info.value.code


@pytest.mark.parametrize("scenario", ["main_repo", "worktree"])
def test_relative_and_absolute_path_agree(tmp_path, monkeypatch, scenario):
    root = tmp_path / scenario
    root.mkdir()
    files = {"lib/good.dart": "// UC-01\n", "lib/bad.dart": "// UC-99\n"}
    project = _setup_project(root, files)

    rel = _run_as_shim(monkeypatch, project, "lib/good.dart")
    absolute = _run_as_shim(monkeypatch, project, f"{project}/lib/good.dart")
    rel_bad = _run_as_shim(monkeypatch, project, "lib/bad.dart")
    abs_bad = _run_as_shim(monkeypatch, project, f"{project}/lib/bad.dart")

    assert (rel, rel_bad) == (absolute, abs_bad) == (0, 1)


def test_nonexistent_relative_path_still_exits_2(tmp_path, monkeypatch, capsys):
    project = _setup_project(tmp_path)

    assert _run_as_shim(monkeypatch, project, "lib/nope.dart") == 2
    assert "不存在" in capsys.readouterr().err


def test_cwd_untouched_without_caller_env(tmp_path, monkeypatch):
    """未由 shim 啟動（無環境變數）時，不得改變 cwd 解析基準。"""
    project = _setup_project(tmp_path, {"lib/good.dart": "// UC-01\n"})
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(cli.CALLER_CWD_ENV, raising=False)
    monkeypatch.setattr(sys, "argv", ["doc", "uc", "verify", "lib/good.dart"])
    with patch.object(FileLocator, "get_project_root", return_value=project):
        with pytest.raises(SystemExit) as exc_info:
            cli.main()
    assert exc_info.value.code == 0
