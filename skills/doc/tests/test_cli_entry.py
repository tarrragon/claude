"""doc CLI 的三種直接執行入口：python3 -m doc_system、-m doc_system.cli、直接執行 cli.py。

三者都必須走到同一個 main：有子命令時執行該命令，無子命令時依 SKILL.md
〈無子命令時的預設行為〉執行 status。缺入口時的失效形態是 rc=0 且無輸出，
因此每個案例同時斷言 rc 與輸出內容。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
CLI_PATH = SKILL_DIR / "doc_system" / "cli.py"

ENTRY_FORMS = {
    "module_package": ["-m", "doc_system"],
    "module_cli": ["-m", "doc_system.cli"],
    "script_path": [str(CLI_PATH)],
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """含一筆提案的最小專案，供 status 產生可斷言的輸出。"""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "proposals-tracking.yaml").write_text(
        "proposals:\n  - id: PROP-001\n    status: draft\n", encoding="utf-8"
    )
    return tmp_path


def _run(form: str, args: list[str], project: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "SKILL_CLI_CALLER_CWD"}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    if form == "script_path":
        # 直接執行路徑不得依賴外部 PYTHONPATH，入口自身須能匯入套件
        env.pop("PYTHONPATH", None)
    else:
        env["PYTHONPATH"] = str(SKILL_DIR)
    return subprocess.run(
        [sys.executable, *ENTRY_FORMS[form], *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize("form", sorted(ENTRY_FORMS))
def test_entry_runs_subcommand(form, project):
    result = _run(form, ["status"], project)
    assert result.returncode == 0, result.stderr
    assert "提案總數: 1" in result.stdout


@pytest.mark.parametrize("form", sorted(ENTRY_FORMS))
def test_entry_without_args_runs_default_status(form, project):
    result = _run(form, [], project)
    assert result.returncode == 0, result.stderr
    assert "提案總數: 1" in result.stdout


@pytest.mark.parametrize("form", sorted(ENTRY_FORMS))
def test_entry_help_prints_usage(form, project):
    result = _run(form, ["--help"], project)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("usage: doc")


@pytest.mark.parametrize("form", sorted(ENTRY_FORMS))
def test_entry_propagates_nonzero_exit(form, project):
    """未知子命令由 argparse 拒絕，rc 非 0 且 stderr 有用法；入口不得吞掉結束碼。"""
    result = _run(form, ["no-such-command"], project)
    assert result.returncode == 2
    assert "usage: doc" in result.stderr
