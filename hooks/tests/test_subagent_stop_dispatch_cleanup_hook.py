"""Tests for subagent-stop-dispatch-cleanup-hook.py (1.0.0-W1-055.1).

歷史：
- W17-159（已過時）：當時 SubagentStop event schema 不允許
  hookSpecificOutput.additionalContext，被迫改用 top-level systemMessage。
- 0.19.1-W1-046（已回退）：CC 2.1.163 #4 解禁後改用 additionalContext。
- 1.0.0-W1-055.1：W1-055 ANA 活體確證 additionalContext 投遞對象是「停止中的
  subagent」（注入並令其繼續 → 自激迴圈，H1 confidence 0.95），回退
  systemMessage 純顯示通道；新增 stop_hook_active 斷路器與 [WAIT] 廣播 dedup。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_output_format_system_message | 有清理發生 | 輸出為 top-level systemMessage（無 hookSpecificOutput） |
| test_no_active_dispatches_silent | 無 dispatch-active.json | return 0、stdout 無輸出 |
| test_remaining_dispatches_wait_message | 部分代理人未完成 | 內容含「[WAIT] 仍有 N 個代理人」 |
| test_all_cleared_ok_message | 所有代理人已完成 | 內容含「[OK] 所有代理人已完成」 |
| test_stop_hook_active_silent | stop_hook_active=true | 靜默 exit 0，不清理、不輸出 |
| test_wait_dedup_* | [WAIT] 重播場景 | 同 key TTL 內去重、TTL 過期重播、內容變化重播 |

策略：
- importlib 動態載入（檔名含 hyphen 無法 import）
- monkeypatch sys.stdin 注入 SubagentStop event JSON
- monkeypatch dispatch_tracker 函式取代真實檔案 IO
- monkeypatch _get_wait_dedup_state_file 指向 tmp_path（避免污染真實 repo）
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


class TestSubagentStopDispatchCleanupSchema:

    def _patch_cleared(
        self, hook_mod, monkeypatch, tmp_path, remaining,
        agent_id="agent-xyz", cleared=True,
    ):
        state_dir = tmp_path / ".claude" / "dispatch-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")

        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "clear_dispatch_by_id", lambda root, aid: cleared)
        monkeypatch.setattr(hook_mod, "clear_oldest_null_agent_id_entry", lambda root: False)
        monkeypatch.setattr(hook_mod, "get_active_dispatches", lambda root: remaining)
        # dedup state 寫到 tmp_path，避免測試污染真實 repo 的 hook-logs
        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": agent_id}))

    def test_output_format_system_message(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """1.0.0-W1-055.1：有清理發生時輸出 top-level systemMessage（純顯示通道）。"""
        self._patch_cleared(hook_mod, monkeypatch, tmp_path, remaining=[])

        rc = hook_mod.main()
        assert rc == 0

        captured = capsys.readouterr()
        assert captured.out.strip(), "main() 應輸出 JSON"
        payload = json.loads(captured.out)

        assert "systemMessage" in payload, "應使用 systemMessage 純顯示通道"
        assert "hookSpecificOutput" not in payload, (
            "additionalContext 會注入停止中的 subagent 引發自激迴圈（W1-055 H1），"
            "已回退 systemMessage"
        )
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
        """部分代理人仍在執行時，輸出內容含 [WAIT] 訊息。"""
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
        msg = payload["systemMessage"]
        assert "[WAIT]" in msg
        assert "仍有 2 個代理人" in msg
        assert "agent-A" in msg and "agent-B" in msg

    def test_all_cleared_ok_message(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """全部代理人完成且本次有 cleared 時輸出內容含 [OK] 訊息。"""
        self._patch_cleared(hook_mod, monkeypatch, tmp_path, remaining=[])

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        assert "[OK]" in payload["systemMessage"]
        assert "所有代理人已完成" in payload["systemMessage"]


class TestStopHookActiveCircuitBreaker:
    """1.0.0-W1-055.1 修復 1：stop_hook_active=true 靜默退出（自激迴圈斷路器）。"""

    def test_stop_hook_active_silent(self, hook_mod, monkeypatch, capsys, tmp_path):
        """stop_hook_active=true 時靜默 exit 0，不執行清理、不輸出任何 JSON。"""
        calls = {"clear": 0}

        def _record_clear(root, aid):
            calls["clear"] += 1
            return True

        state_file = tmp_path / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "clear_dispatch_by_id", _record_clear)
        monkeypatch.setattr(
            sys, "stdin",
            _stdin({"agent_id": "agent-xyz", "stop_hook_active": True}),
        )

        rc = hook_mod.main()
        assert rc == 0

        captured = capsys.readouterr()
        assert captured.out == "", "stop_hook_active=true 不應輸出（避免再注入）"
        assert calls["clear"] == 0, "stop_hook_active=true 不應執行清理（首次事件已清）"

    def test_stop_hook_active_false_normal_flow(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """stop_hook_active=false 時照常執行（不誤傷正常事件）。"""
        state_dir = tmp_path / ".claude"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "clear_dispatch_by_id", lambda root, aid: True)
        monkeypatch.setattr(hook_mod, "clear_oldest_null_agent_id_entry", lambda root: False)
        monkeypatch.setattr(hook_mod, "get_active_dispatches", lambda root: [])
        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        monkeypatch.setattr(
            sys, "stdin",
            _stdin({"agent_id": "agent-xyz", "stop_hook_active": False}),
        )

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        assert "[OK]" in payload["systemMessage"]


class TestWaitBroadcastDedup:
    """1.0.0-W1-055.1 修復 2：[WAIT] 廣播以 agent_id + remaining hash 做 TTL 去重。"""

    REMAINING = [{"agent_description": "agent-B"}]

    def _run_event(
        self, hook_mod, monkeypatch, tmp_path, capsys,
        agent_id="agent-xyz", remaining=None, cleared=False,
    ):
        """模擬一次 SubagentStop 事件，回傳 stdout 原文。"""
        if remaining is None:
            remaining = self.REMAINING
        state_file = tmp_path / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "clear_dispatch_by_id", lambda root, aid: cleared)
        monkeypatch.setattr(
            hook_mod, "clear_oldest_null_agent_id_entry", lambda root: cleared
        )
        monkeypatch.setattr(hook_mod, "get_active_dispatches", lambda root: remaining)
        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": agent_id}))

        rc = hook_mod.main()
        assert rc == 0
        return capsys.readouterr().out

    def test_wait_dedup_second_event_silent(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """同 agent_id + 相同 remaining 的第二次事件：[WAIT] 被去重，stdout 靜默。

        重現 W1-052 場景：首次事件清理成功 + 播報 [WAIT]；自激迴圈的後續事件
        清理失敗（記錄已清）且 remaining 不變 → 無任何輸出。
        """
        first = self._run_event(
            hook_mod, monkeypatch, tmp_path, capsys, cleared=True
        )
        assert "[WAIT]" in json.loads(first)["systemMessage"]

        second = self._run_event(
            hook_mod, monkeypatch, tmp_path, capsys, cleared=False
        )
        assert second == "", "TTL 內同 key 的 [WAIT] 應被去重（無其他訊息時靜默）"

    def test_wait_dedup_different_remaining_rebroadcast(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """remaining 內容變化（agent 增減）視為新狀態，重新播報。"""
        self._run_event(hook_mod, monkeypatch, tmp_path, capsys, cleared=True)

        changed = [
            {"agent_description": "agent-B"},
            {"agent_description": "agent-C"},
        ]
        out = self._run_event(
            hook_mod, monkeypatch, tmp_path, capsys,
            remaining=changed, cleared=False,
        )
        msg = json.loads(out)["systemMessage"]
        assert "仍有 2 個代理人" in msg

    def test_wait_dedup_different_agent_rebroadcast(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """不同 agent_id 的真實 SubagentStop 各自播報一次（key 含 agent_id）。"""
        self._run_event(
            hook_mod, monkeypatch, tmp_path, capsys,
            agent_id="agent-first", cleared=True,
        )
        out = self._run_event(
            hook_mod, monkeypatch, tmp_path, capsys,
            agent_id="agent-second", cleared=True,
        )
        assert "[WAIT]" in json.loads(out)["systemMessage"]

    def test_check_and_record_broadcast_ttl_expiry(self, hook_mod, tmp_path):
        """TTL 過期後同 key 重新播報（避免長任務的真實 [WAIT] 永久靜默）。"""
        import logging

        logger = logging.getLogger("test-dedup-ttl")
        state_file = tmp_path / "dedup.json"
        ttl = hook_mod.WAIT_BROADCAST_DEDUP_TTL_SECONDS

        t0 = 1_000_000.0
        assert hook_mod.check_and_record_broadcast(
            state_file, "key-a", ttl, logger, now=t0
        ) is False, "首次播報不應被去重"
        assert hook_mod.check_and_record_broadcast(
            state_file, "key-a", ttl, logger, now=t0 + ttl - 1
        ) is True, "TTL 內同 key 應被去重"
        assert hook_mod.check_and_record_broadcast(
            state_file, "key-a", ttl, logger, now=t0 + ttl + 1
        ) is False, "TTL 過期後應重新播報"

    def test_check_and_record_broadcast_corrupt_state_fail_open(
        self, hook_mod, tmp_path
    ):
        """state 檔損毀時 fail-open（照常播報），不吞掉真實通知。"""
        import logging

        logger = logging.getLogger("test-dedup-corrupt")
        state_file = tmp_path / "dedup.json"
        state_file.write_text("not-json{{{", encoding="utf-8")

        assert hook_mod.check_and_record_broadcast(
            state_file, "key-a", 600, logger, now=1_000_000.0
        ) is False, "損毀 state 應 fail-open 照常播報"
        # 寫回後 state 檔恢復為合法 JSON
        recovered = json.loads(state_file.read_text(encoding="utf-8"))
        assert "key-a" in recovered
