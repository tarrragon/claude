"""Tests for subagent-stop-dispatch-cleanup-hook.py (0.19.1-W1-046).

歷史：
- W17-159（已過時）：當時 SubagentStop event schema 不允許
  hookSpecificOutput.additionalContext，被迫改用 top-level systemMessage。
- 0.19.1-W1-046：CC 2.1.163 #4 解除該限制，改回
  hookSpecificOutput.additionalContext（正確機制）；< 2.1.163 的 runtime
  透過 build_subagent_stop_output 自動 graceful fallback 回 systemMessage。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_output_format_additional_context | CC >= 2.1.163 有清理發生 | 輸出為 hookSpecificOutput.additionalContext（hookEventName=SubagentStop） |
| test_output_fallback_legacy_version | CC < 2.1.163 有清理發生 | 降級回 top-level systemMessage |
| test_no_active_dispatches_silent | 無 dispatch-active.json | return 0、stdout 無輸出 |
| test_remaining_dispatches_wait_message | 部分代理人未完成 | 內容含「[WAIT] 仍有 N 個代理人」 |
| test_all_cleared_ok_message | 所有代理人已完成 | 內容含「[OK] 所有代理人已完成」 |

策略：
- importlib 動態載入（檔名含 hyphen 無法 import）
- monkeypatch sys.stdin 注入 SubagentStop event JSON
- monkeypatch dispatch_tracker 函式取代真實檔案 IO
- monkeypatch supports_subagent_stop_additional_context 控制版本分支
- capsys 捕獲 stdout JSON
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

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


def _content_of(payload: dict) -> str:
    """從 additionalContext 或 systemMessage 取出注入文字（兩 shape 通用）。"""
    if "hookSpecificOutput" in payload:
        return payload["hookSpecificOutput"]["additionalContext"]
    return payload["systemMessage"]


class TestSubagentStopDispatchCleanupSchema:

    def _patch_cleared(self, hook_mod, monkeypatch, tmp_path, remaining):
        state_dir = tmp_path / ".claude" / "dispatch-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "clear_dispatch_by_id", lambda root, aid: True)
        monkeypatch.setattr(hook_mod, "clear_oldest_null_agent_id_entry", lambda root: False)
        monkeypatch.setattr(hook_mod, "get_active_dispatches", lambda root: remaining)
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-xyz"}))

    def test_output_format_additional_context(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """CC >= 2.1.163：有清理發生時輸出 hookSpecificOutput.additionalContext。"""
        self._patch_cleared(hook_mod, monkeypatch, tmp_path, remaining=[])
        # 強制走「支援」分支（避免 CI 無 claude binary 時走 fallback）
        monkeypatch.setattr(
            hook_mod, "build_subagent_stop_output",
            lambda context, logger=None: {
                "hookSpecificOutput": {
                    "hookEventName": "SubagentStop",
                    "additionalContext": context,
                }
            },
        )

        rc = hook_mod.main()
        assert rc == 0

        captured = capsys.readouterr()
        assert captured.out.strip(), "main() 應輸出 JSON"
        payload = json.loads(captured.out)

        assert "hookSpecificOutput" in payload, "CC >= 2.1.163 應使用 additionalContext"
        hso = payload["hookSpecificOutput"]
        assert hso["hookEventName"] == "SubagentStop"
        assert "additionalContext" in hso
        assert "[OK]" in hso["additionalContext"]

    def test_output_fallback_legacy_version(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """CC < 2.1.163：graceful fallback 回 top-level systemMessage。"""
        self._patch_cleared(hook_mod, monkeypatch, tmp_path, remaining=[])
        monkeypatch.setattr(
            hook_mod, "build_subagent_stop_output",
            lambda context, logger=None: {"systemMessage": context},
        )

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        assert "systemMessage" in payload, "< 2.1.163 應降級回 systemMessage"
        assert "hookSpecificOutput" not in payload
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
        """部分代理人仍在執行時，注入內容含 [WAIT] 訊息。"""
        self._patch_cleared(
            hook_mod, monkeypatch, tmp_path,
            remaining=[
                {"agent_description": "agent-A"},
                {"agent_description": "agent-B"},
            ],
        )

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        msg = _content_of(payload)
        assert "[WAIT]" in msg
        assert "仍有 2 個代理人" in msg
        assert "agent-A" in msg and "agent-B" in msg

    def test_all_cleared_ok_message(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """全部代理人完成且本次有 cleared 時注入內容含 [OK] 訊息。"""
        self._patch_cleared(hook_mod, monkeypatch, tmp_path, remaining=[])

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        msg = _content_of(payload)
        assert "[OK]" in msg
        assert "所有代理人已完成" in msg
