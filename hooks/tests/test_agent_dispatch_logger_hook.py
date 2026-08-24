"""Minimal gate-satisfying test for agent-dispatch-logger-hook.py（0.2.1-W3-945）。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_empty_stdin_fail_open | 空 stdin | SystemExit(0)，DEFAULT_OUTPUT 輸出 |
| test_malformed_json_fail_open | 畸形 JSON stdin | SystemExit(0)，DEFAULT_OUTPUT 輸出 |
| test_normal_input_logs_entry | 正常 Agent PostToolUse input | SystemExit(0)，JSONL 寫入一筆 |
| test_liveness_entry_written_via_run_hook_safely | 經 run_hook_safely 執行 | _liveness/<session>.jsonl 寫入 1 筆 |
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / "agent-dispatch-logger-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "agent_dispatch_logger_hook_gate", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def test_empty_stdin_fail_open(hook_mod, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == hook_mod.DEFAULT_OUTPUT


def test_malformed_json_fail_open(hook_mod, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))
    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == hook_mod.DEFAULT_OUTPUT


def test_normal_input_logs_entry(hook_mod, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(hook_mod, "get_project_root", lambda: str(tmp_path))
    input_data = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "0.2.1-W3-945 補測試",
            "description": "basil-hook-architect 執行",
            "subagent_type": "basil-hook-architect",
        },
        "tool_response": {"result": "done"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(input_data)))

    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0

    log_path = tmp_path / hook_mod.LOG_DIR / hook_mod.LOG_FILE
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["agent_type"] == "basil-hook-architect"
    assert "0.2.1-W3-945" in entry["ticket_id"]

    payload = json.loads(capsys.readouterr().out)
    assert payload == hook_mod.DEFAULT_OUTPUT


def test_liveness_entry_written_via_run_hook_safely(hook_mod, monkeypatch, tmp_path):
    import lib.hook_logging as hook_logging_mod

    monkeypatch.setattr(hook_logging_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-945")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    with pytest.raises(SystemExit) as exc:
        hook_logging_mod.run_hook_safely(hook_mod.main, hook_mod.HOOK_NAME)
    assert exc.value.code == 0

    liveness_file = tmp_path / ".claude" / "hook-logs" / "_liveness" / "test-session-945.jsonl"
    assert liveness_file.exists()
    lines = liveness_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["hook"] == hook_mod.HOOK_NAME
