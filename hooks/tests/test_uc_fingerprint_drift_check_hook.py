"""Minimal gate-satisfying test for uc-fingerprint-drift-check-hook.py（0.2.1-W3-945）。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_empty_stdin_fail_open | 空 stdin | main() 回傳 0，不崩潰 |
| test_malformed_json_fail_open | 畸形 JSON stdin | main() 回傳 0，不崩潰 |
| test_normal_input_non_target_file_returns_zero | Write 非 app-use-cases.md | main() 回傳 0 |
| test_liveness_entry_written_via_run_hook_safely | 經 run_hook_safely 執行 | _liveness/<session>.jsonl 寫入 1 筆 |
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / "uc-fingerprint-drift-check-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "uc_fingerprint_drift_check_hook_gate", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def test_empty_stdin_fail_open(hook_mod, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert hook_mod.main() == 0


def test_malformed_json_fail_open(hook_mod, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))
    assert hook_mod.main() == 0


def test_normal_input_non_target_file_returns_zero(hook_mod, monkeypatch):
    input_data = {
        "tool_name": "Write",
        "tool_input": {"file_path": "docs/other-file.md"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(input_data)))
    assert hook_mod.main() == 0


def test_liveness_entry_written_via_run_hook_safely(hook_mod, monkeypatch, tmp_path):
    import lib.hook_logging as hook_logging_mod

    monkeypatch.setattr(hook_logging_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-945")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = hook_logging_mod.run_hook_safely(hook_mod.main, hook_mod.HOOK_NAME)
    assert exit_code == 0

    liveness_file = tmp_path / ".claude" / "hook-logs" / "_liveness" / "test-session-945.jsonl"
    assert liveness_file.exists()
    lines = liveness_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["hook"] == hook_mod.HOOK_NAME
