"""Minimal gate-satisfying test for task-dispatch-readiness-check.py（0.2.1-W3-945）。

背景：test_agent_dispatch_check.py 已對本檔（HOOK_NAME 內部值為
"agent-dispatch-check"）的分派邏輯有大量覆蓋，但檔名不符
hooks-test-gate-hook.py 的 `_candidate_tests` 慣例（依「檔案名」stem 推導，
非內部 HOOK_NAME），故本檔補齊 gate 可辨識的最小測試骨架。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_empty_stdin_fail_open | 空 stdin | SystemExit(0)，不崩潰 |
| test_malformed_json_fail_open | 畸形 JSON stdin | SystemExit(0)，不崩潰（read_hook_input 解析失敗回傳 {}） |
| test_normal_input_non_agent_tool_exit_zero | 非 Agent/Task 工具 input | SystemExit(0) |
| test_liveness_entry_written_via_run_hook_safely | 經 run_hook_safely 執行 | _liveness/<session>.jsonl 寫入 1 筆 |
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / "task-dispatch-readiness-check.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "task_dispatch_readiness_check_gate", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def test_empty_stdin_fail_open(hook_mod, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0


def test_malformed_json_fail_open(hook_mod, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))
    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0


def test_normal_input_non_agent_tool_exit_zero(hook_mod, monkeypatch):
    input_data = {"tool_name": "Read", "tool_input": {"file_path": "foo.py"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(input_data)))
    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0


def test_liveness_entry_written_via_run_hook_safely(hook_mod, monkeypatch, tmp_path):
    import lib.hook_logging as hook_logging_mod

    monkeypatch.setattr(hook_logging_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-945")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    with pytest.raises(SystemExit) as exc:
        hook_logging_mod.run_hook_safely(hook_mod.main, "agent-dispatch-check")
    assert exc.value.code == 0

    liveness_file = tmp_path / ".claude" / "hook-logs" / "_liveness" / "test-session-945.jsonl"
    assert liveness_file.exists()
    lines = liveness_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["hook"] == "agent-dispatch-check"
