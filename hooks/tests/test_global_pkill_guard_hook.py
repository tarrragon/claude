"""Test: global-pkill-guard-hook（0.5.0-W1-187.5）"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "global_pkill_guard_hook", HOOKS_DIR / "global-pkill-guard-hook.py"
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def run(monkeypatch, capsys, command, tool="Bash"):
    payload = json.dumps({"tool_name": tool, "tool_input": {"command": command}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    rc = hook.main()
    return rc, capsys.readouterr().err


@pytest.mark.parametrize("cmd", [
    "pkill -f flutter_tester",
    "pkill flutter_tester",
    "killall flutter_tester",
    "sudo killall -9 dart",
    "echo hi && pkill -9 -f dart",
    "FOO=1 pkill dart",
    "/usr/bin/pkill dart",
    "bash -c 'pkill -f dart'",
    # B+view 正向對照：任意位置
    "timeout 5 pkill -f dart",
    "nice -n 5 killall dart",
    "ssh host pkill dart",
    "docker exec c pkill dart",
    "/usr/bin/killall -9 dart",
    "timeout 10 bash -c 'pkill -f dart'",
    "sh -c \"echo x; /usr/bin/pkill dart\"",
    "python3 .claude/scripts/orphan-test-procs.py --kill --root /tmp/x",
    "python3 .claude/scripts/orphan-test-procs.py --root=/x --kill",
    # 閱讀類命令的執行類選項（正向對照）
    "rg --pre pkill x .",
    "rg --pre=pkill x .",
    "man -P 'pkill dart' ls",
    "man --pager='pkill dart' ls",
    "less '+!pkill dart' f",
    "man -Hpkill ls",
    "man -Ppkill ls",
    "man --html=pkill ls",
    "timeout 5 rg --pre pkill x .",
    # command 之後的 -v/-V 屬被執行命令的參數，不得豁免
    "command pkill -v dart",
    "command killall -V dart",
    "command -p pkill -v dart",
])
def test_denied_with_alternative(monkeypatch, capsys, cmd):
    rc, err = run(monkeypatch, capsys, cmd)
    assert rc == 2
    assert "orphan-test-procs.py" in err
    assert "kill -- -<PGID>" in err


@pytest.mark.parametrize("cmd", [
    "kill 1234",
    "kill -9 -- -4321",
    "echo pkill -f foo",
    "grep -rn 'pkill' .claude",
    "git commit -m 'document killall ban'",
    "rg pkill .claude",
    "timeout 5 grep -r pkill .",
    "nice -n 5 rg pkill .",
    "env FOO=1 grep pkill f",
    "man pkill",
    "which pkill",
    "command -v pkill",
    "command -V killall",
    "type killall",
    "cat x | grep -n killall",
    "python3 .claude/scripts/orphan-test-procs.py",
    "python3 .claude/scripts/orphan-test-procs.py --kill",
    "python3 .claude/scripts/orphan-test-procs.py --root /tmp/x",
    "echo 'unclosed",
    "ls",
    "rg -n pkill src",
    "man -k pkill",
    "less pkill.log",
    "man -H ls",
    "man --html ls",
])
def test_allowed(monkeypatch, capsys, cmd):
    rc, err = run(monkeypatch, capsys, cmd)
    assert rc == 0
    assert err == ""


def test_non_bash_ignored(monkeypatch, capsys):
    rc, _ = run(monkeypatch, capsys, "pkill x", tool="Edit")
    assert rc == 0
