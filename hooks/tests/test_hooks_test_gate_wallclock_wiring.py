"""
Test: hooks-test-gate 的 wallclock 執行點接線

背景：wallclock 標記測試被 pyproject addopts `-m 'not wallclock'` 預設排除，
需有固定執行點。選定 hooks-test-gate：commit 觸及 gate 本體或計時外掛（conftest.py）
時，額外以 `-m wallclock` 跑 gate 的測試檔；紅燈或逾時一律 deny，不 skip。

E1 對照：同一組 fixture 下「計時外掛健康」放行、「計時外掛的 atexit 註冊被弄壞」deny。
E1 兩個測試需真實 uv + pytest 子程序，負載敏感，歸 wallclock 標記（與接線對象同族）。
"""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "hooks_test_gate_hook_wiring", HOOKS_DIR / "hooks-test-gate-hook.py"
)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

_GATE_TEST = "test_hooks_test_gate_hook.py"


class TestWallclockTriggers:
    def test_gate_and_timing_plugin_trigger_gate_test_file(self):
        triggers = gate.WALLCLOCK_TRIGGERS
        assert triggers["hooks-test-gate-hook.py"] == _GATE_TEST
        assert triggers["conftest.py"] == _GATE_TEST

    def test_unrelated_hook_has_no_wallclock_trigger(self):
        assert "bash-edit-guard-hook.py" not in gate.WALLCLOCK_TRIGGERS

    def test_wallclock_command_selects_marker(self, monkeypatch, tmp_path):
        seen = []

        def _run(cmd, **kw):
            seen.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="1 passed in 0.01s\n", stderr="")

        monkeypatch.setattr(gate.subprocess, "run", _run)
        lg = _NullLogger()
        gate._run_pytest([tmp_path / _GATE_TEST], tmp_path, lg, extra_args=["-m", "wallclock"])
        assert seen and seen[0][-3:-1] == ["-m", "wallclock"]

    def test_wallclock_timeout_is_timeout_status_not_skip(self, monkeypatch, tmp_path):
        def _run(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, 1)

        monkeypatch.setattr(gate.subprocess, "run", _run)
        status, _ = gate._run_pytest(
            [tmp_path / _GATE_TEST], tmp_path, _NullLogger(), extra_args=["-m", "wallclock"]
        )
        assert status == gate._STATUS_TIMEOUT


class _NullLogger:
    def __getattr__(self, name):
        return lambda *a, **k: None


def _build_fixture(root: Path, break_atexit: bool) -> None:
    """複製 gate、計時外掛、gate 測試檔與 lib 到 tmp 專案；可選擇弄壞 atexit 註冊。"""
    hooks = root / ".claude" / "hooks"
    (hooks / "tests").mkdir(parents=True)
    for name in ("hooks-test-gate-hook.py", "conftest.py", "testpaths_coverage_warning.py",
                 "pyproject.toml"):
        shutil.copy(HOOKS_DIR / name, hooks / name)
    shutil.copy(HOOKS_DIR / "tests" / _GATE_TEST, hooks / "tests" / _GATE_TEST)
    shutil.copytree(
        HOOKS_DIR.parent / "lib", root / ".claude" / "lib",
        ignore=shutil.ignore_patterns("__pycache__", "tests", ".pytest_cache"),
    )
    if break_atexit:
        conftest = hooks / "conftest.py"
        text = conftest.read_text(encoding="utf-8")
        assert "atexit.register(_atexit_mark)" in text
        conftest.write_text(text.replace("atexit.register(_atexit_mark)", "pass"), encoding="utf-8")


def _commit_touching_conftest(monkeypatch, root: Path):
    monkeypatch.setattr(gate, "get_project_root", lambda: root)
    monkeypatch.setattr(
        gate, "run_git_command",
        lambda *a, **k: (True, "M\0.claude/hooks/conftest.py\0"),
    )
    payload = {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "x"'}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    captured = []
    with patch("builtins.print", side_effect=lambda *a, **k: captured.append(a[0] if a else "")):
        code = gate.main()
    return code, captured


@pytest.mark.wallclock
class TestE1TimingPluginBreakage:
    def test_healthy_timing_plugin_is_not_denied(self, monkeypatch, tmp_path):
        _build_fixture(tmp_path, break_atexit=False)
        code, captured = _commit_touching_conftest(monkeypatch, tmp_path)
        assert code == 0
        for out in captured:
            decision = json.loads(out)["hookSpecificOutput"].get("permissionDecision")
            assert decision != "deny", out

    def test_broken_timing_plugin_is_denied_by_wallclock_run(self, monkeypatch, tmp_path):
        _build_fixture(tmp_path, break_atexit=True)
        code, captured = _commit_touching_conftest(monkeypatch, tmp_path)
        assert code == 0
        decisions = [json.loads(o)["hookSpecificOutput"].get("permissionDecision") for o in captured]
        assert "deny" in decisions, captured
        assert "wallclock" in captured[0]
