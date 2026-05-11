"""Tests for subagent-stop-dispatch-cleanup-hook.py (W17-159).

W17-159 修復 SubagentStop event schema 違反：
- 修復前：輸出 hookSpecificOutput.additionalContext（schema 不允許）
- 修復後：輸出 top-level systemMessage（同 W17-158 處置）

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_output_format_top_level_systemMessage | 有清理發生 | 輸出 JSON 為 {"systemMessage": "..."} 結構，無 hookSpecificOutput 包裝 |
| test_no_active_dispatches_silent | 無 dispatch-active.json | return 0、stdout 無輸出 |
| test_remaining_dispatches_wait_message | 部分代理人未完成 | systemMessage 含「[WAIT] 仍有 N 個代理人」 |
| test_all_cleared_ok_message | 所有代理人已完成 | systemMessage 含「[OK] 所有代理人已完成」 |

策略：
- importlib 動態載入（檔名含 hyphen 無法 import）
- monkeypatch sys.stdin 注入 SubagentStop event JSON
- monkeypatch dispatch_tracker 函式取代真實檔案 IO
- capsys 捕獲 stdout JSON
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


HOOK_PATH = Path(__file__).parent.parent / "subagent-stop-dispatch-cleanup-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "subagent_stop_dispatch_cleanup_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def _stdin(payload: dict) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


class TestSubagentStopDispatchCleanupSchema:

    def test_output_format_top_level_systemMessage(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """有清理發生時輸出 JSON 必須是 top-level systemMessage，禁止 hookSpecificOutput.additionalContext。"""
        # 建立 fake state file 讓 not state_file.exists() 不為真
        state_dir = tmp_path / ".claude" / "dispatch-state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "clear_dispatch_by_id", lambda root, aid: True)
        monkeypatch.setattr(hook_mod, "clear_oldest_null_agent_id_entry", lambda root: False)
        monkeypatch.setattr(hook_mod, "get_active_dispatches", lambda root: [])
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-xyz"}))

        rc = hook_mod.main()
        assert rc == 0

        captured = capsys.readouterr()
        assert captured.out.strip(), "main() 應輸出 JSON"
        payload = json.loads(captured.out)

        assert "systemMessage" in payload, "SubagentStop event 必須使用 top-level systemMessage"
        assert "hookSpecificOutput" not in payload, (
            "SubagentStop schema 不允許 hookSpecificOutput.additionalContext（W17-159）"
        )
        # 應包含 [OK] 訊息（remaining=空、cleared=True）
        assert "[OK]" in payload["systemMessage"]

    def test_no_active_dispatches_silent(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """state_file 不存在時 return 0 且 stdout 無輸出。"""
        non_existent = tmp_path / "nope.json"
        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: non_existent)
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-xyz"}))

        rc = hook_mod.main()
        assert rc == 0

        captured = capsys.readouterr()
        assert captured.out == "", "state_file 不存在時不應輸出"

    def test_remaining_dispatches_wait_message(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """部分代理人仍在執行時，systemMessage 含 [WAIT] 訊息。"""
        state_file = tmp_path / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "clear_dispatch_by_id", lambda root, aid: True)
        monkeypatch.setattr(hook_mod, "clear_oldest_null_agent_id_entry", lambda root: False)
        monkeypatch.setattr(
            hook_mod,
            "get_active_dispatches",
            lambda root: [
                {"agent_description": "agent-A"},
                {"agent_description": "agent-B"},
            ],
        )
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-xyz"}))

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        assert "systemMessage" in payload
        assert "hookSpecificOutput" not in payload
        msg = payload["systemMessage"]
        assert "[WAIT]" in msg
        assert "仍有 2 個代理人" in msg
        assert "agent-A" in msg and "agent-B" in msg

    def test_all_cleared_ok_message(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """全部代理人完成且本次有 cleared 時 systemMessage 含 [OK] 訊息。"""
        state_file = tmp_path / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "clear_dispatch_by_id", lambda root, aid: True)
        monkeypatch.setattr(hook_mod, "clear_oldest_null_agent_id_entry", lambda root: False)
        monkeypatch.setattr(hook_mod, "get_active_dispatches", lambda root: [])
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-xyz"}))

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        assert "systemMessage" in payload
        assert "hookSpecificOutput" not in payload
        msg = payload["systemMessage"]
        assert "[OK]" in msg
        assert "所有代理人已完成" in msg
