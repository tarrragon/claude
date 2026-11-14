"""ticket CLI 的 hook-logs 寫入在 linked worktree 內須落主 repo（3.3.0-W1-204.1.6.2）。"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

TICKET_DIR = Path(__file__).resolve().parents[1]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repos(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("x\n", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "feat")
    return main.resolve(), wt.resolve()


def _run_in(wt: Path, code: str) -> None:
    env = {k: v for k, v in os.environ.items()
           if k not in ("HOOK_TEST_ISOLATION", "CLAUDE_PROJECT_DIR")}
    env["PYTHONPATH"] = str(TICKET_DIR)
    subprocess.run([sys.executable, "-c", code], cwd=wt, env=env, check=True)


def test_parser_charset_log_in_main_repo(repos):
    main, wt = repos
    _run_in(wt, (
        "from pathlib import Path\n"
        "from ticket_system.lib.parser import _log_charset_violations as f\n"
        "f([('what', 'x', 0x78, 'k')], {'id': 'T-1'}, Path('T-1.md'))\n"
    ))
    assert (main / ".claude" / "hook-logs" / "charset-gate.log").is_file()
    assert not (wt / ".claude" / "hook-logs").exists()


def test_parser_enum_log_in_main_repo(repos):
    main, wt = repos
    _run_in(wt, (
        "from pathlib import Path\n"
        "from ticket_system.lib.parser import _log_enum_violations as f\n"
        "f([('status', 'a', 'b', 'c', 'k')], {'id': 'T-1'}, Path('T-1.md'), 'warn')\n"
    ))
    assert (main / ".claude" / "hook-logs" / "enum-gate.log").is_file()
    assert not (wt / ".claude" / "hook-logs").exists()


def test_claim_candidate_log_in_main_repo(repos):
    main, wt = repos
    _run_in(wt, (
        "from ticket_system.commands.lifecycle import _claim_candidate_logger as g\n"
        "lg = g(); lg.info('probe')\n"
        "[h.close() for h in lg.handlers]\n"
    ))
    logs = list((main / ".claude" / "hook-logs").glob("*.log"))
    assert logs
    assert not (wt / ".claude" / "hook-logs").exists()
