"""Minimal gate-satisfying test for agent-commit-verification-hook.py（0.2.1-W3-945）。

背景：既有 test_agent_commit_verification_hook_{dedup,porcelain,scan_errors,
schema,worktree_uncommitted}.py 已覆蓋大量細節行為，但命名不符
hooks-test-gate-hook.py 的 `_candidate_tests` 慣例（stem 或 stem 去
`_hook` 後綴），故本檔補齊 gate 可辨識的最小測試骨架，不重複既有覆蓋。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_empty_stdin_fail_open | 空 stdin | SystemExit(0)，不崩潰 |
| test_malformed_json_fail_open | 畸形 JSON stdin | SystemExit(0)，不崩潰 |
| test_normal_input_clean_state_exit_zero | 正常 SubagentStop input，乾淨狀態 | SystemExit(0)，stdout 無輸出 |
| test_liveness_entry_written_via_run_hook_safely | 經 run_hook_safely 執行 | _liveness/<session>.jsonl 寫入 1 筆，hook 名稱正確 |
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / "agent-commit-verification-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "agent_commit_verification_hook_gate", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def _patch_clean(hook_mod, monkeypatch):
    monkeypatch.setattr(hook_mod, "_lookup_agent_info", lambda *a, **kw: ("agent-X", False))
    monkeypatch.setattr(hook_mod, "get_uncommitted_files", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_unmerged_worktrees", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_unmerged_feature_branches", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "scan_hook_errors", lambda *a, **kw: [])
    monkeypatch.setattr(hook_mod, "get_project_root", lambda: Path("/tmp"))


def test_empty_stdin_fail_open(hook_mod, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


def test_malformed_json_fail_open(hook_mod, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))
    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


def test_normal_input_clean_state_exit_zero(hook_mod, monkeypatch, capsys):
    _patch_clean(hook_mod, monkeypatch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"agent_id": "agent-xyz"})))
    with pytest.raises(SystemExit) as exc:
        hook_mod.main()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


def test_liveness_entry_written_via_run_hook_safely(hook_mod, monkeypatch, tmp_path):
    """經 run_hook_safely 呼叫 main() 時，_liveness 索引檔應寫入一筆進入訊號。"""
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
