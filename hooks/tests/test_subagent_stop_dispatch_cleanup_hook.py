"""Tests for subagent-stop-dispatch-cleanup-hook.py (1.0.0-W1-055.1)。

歷史：
- W17-159（已過時）：當時 SubagentStop event schema 不允許
  hookSpecificOutput.additionalContext，被迫改用 top-level systemMessage。
- 0.19.1-W1-046（已回退）：CC 2.1.163 #4 解禁後改用 additionalContext。
- 1.0.0-W1-055.1：W1-055 ANA 活體確證 additionalContext 投遞對象是「停止中的
  subagent」（注入並令其繼續 → 自激迴圈，H1 confidence 0.95），回退
  systemMessage 純顯示通道；新增 stop_hook_active 斷路器與 [WAIT] 廣播 dedup。
- SubagentStop 刪除記錄前提失準修復票：SubagentStop 不保證代理人真正終止，
  `clear_dispatch_by_id` / `clear_oldest_null_agent_id_entry`（刪除式）改為
  `mark_turn_ended_by_id` / `mark_oldest_active_null_agent_id_entry_turn_
  ended`（標記式，entry 保留）。[WAIT]/[OK] 判斷改依 `turn_ended_at` 篩出
  的 `still_running` 子集，不再用「entry 是否還在陣列中」（entry 保留後
  恆為真）；[OK] 措辭改為「目前無代理人在執行回合中」，不再宣稱「已完成，
  可開始驗收」。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_output_format_system_message | 有標記發生 | 輸出為 top-level systemMessage（無 hookSpecificOutput） |
| test_no_active_dispatches_silent | 無 dispatch-active.json | return 0、stdout 無輸出 |
| test_remaining_dispatches_wait_message | 部分代理人仍在執行回合中 | 內容含「[WAIT] 仍有 N 個代理人」 |
| test_all_cleared_ok_message | 無代理人在執行回合中 | 內容含「[OK] 目前無代理人在執行回合中」 |
| test_marked_entry_not_counted_as_still_running | 已標記回合結束的 entry 存在但不計入 still_running | 不觸發 [WAIT]，改觸發 [OK] |
| test_stop_hook_active_silent | stop_hook_active=true | 靜默 exit 0，不標記、不輸出 |
| test_wait_dedup_* | [WAIT] 重播場景 | 同 key TTL 內去重、TTL 過期重播、內容變化重播 |
| test_declines_mark_when_multiple_null_candidates | null 候選 > 1 筆 | 不呼叫 FIFO 標記（呼叫即失敗），僅供 [WAIT] 訊息 |
| test_single_null_candidate_still_uses_fifo | null 候選 = 1 筆 | 照常呼叫 FIFO 標記（向後相容） |

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
def hook_mod(monkeypatch, tmp_path):
    """載入 hook 模組，並改寫 __file__ 使其 __file__ 導向 project_root 落在
    測試專屬 tmp_path。

    Why：main() 以 `Path(__file__).resolve().parent.parent.parent` 解析
    project_root，並自 0.2.1-W3-1092 起將此值顯式傳給
    setup_hook_logging(project_root=...)。顯式傳入會繞過 conftest
    isolate_hook_logs 對 get_project_root() 的隔離（該 fixture 只攔截
    「未傳 project_root、內部自行呼叫 get_project_root()」的路徑），若不
    改寫 __file__，測試會將真實日誌寫入 production .claude/hook-logs/。
    """
    module = _load_hook_module()
    fake_hooks_dir = tmp_path / "fake_repo" / ".claude" / "hooks"
    fake_hooks_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        module,
        "__file__",
        str(fake_hooks_dir / "subagent-stop-dispatch-cleanup-hook.py"),
    )
    return module


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
        monkeypatch.setattr(hook_mod, "mark_turn_ended_by_id", lambda root, aid: cleared)
        monkeypatch.setattr(
            hook_mod, "mark_oldest_active_null_agent_id_entry_turn_ended",
            lambda root: False,
        )
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
        """1.0.0-W1-055.1：有標記發生時輸出 top-level systemMessage（純顯示通道）。"""
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
        """無代理人在執行回合中且本次有標記時輸出內容含 [OK] 訊息（措辭不宣稱
        「已完成」——標記式設計下無法確認代理人已真正終止）。"""
        self._patch_cleared(hook_mod, monkeypatch, tmp_path, remaining=[])

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        assert "[OK]" in payload["systemMessage"]
        assert "目前無代理人在執行回合中" in payload["systemMessage"]
        assert "已完成" not in payload["systemMessage"]

    def test_marked_entry_not_counted_as_still_running(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """已標記回合結束（turn_ended_at 非 None）的 entry 雖仍保留在陣列中，
        不應被計入 still_running，觸發 [OK] 而非 [WAIT]（SubagentStop 刪除
        記錄前提失準修復票：entry 保留後「陣列非空」不再等於「仍在執行」）。
        """
        self._patch_cleared(
            hook_mod, monkeypatch, tmp_path,
            remaining=[
                {
                    "agent_description": "agent-已回合結束",
                    "turn_ended_at": "2026-09-03T00:00:00+00:00",
                },
            ],
        )

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        msg = payload["systemMessage"]
        assert "[OK]" in msg
        assert "[WAIT]" not in msg


class TestHandleFirstPrecedence:
    """agent_handle 精準比對先於 agent_id 精準比對呼叫（識別碼命名空間
    修復票）。"""

    def _patch(
        self, hook_mod, monkeypatch, tmp_path,
        handle_result, id_result, remaining=None,
    ):
        state_dir = tmp_path / ".claude" / "dispatch-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")

        calls = {"handle": 0, "id": 0}

        def _mock_handle(root, aid):
            calls["handle"] += 1
            return handle_result

        def _mock_id(root, aid):
            calls["id"] += 1
            return id_result

        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "mark_turn_ended_by_handle", _mock_handle)
        monkeypatch.setattr(hook_mod, "mark_turn_ended_by_id", _mock_id)
        monkeypatch.setattr(
            hook_mod, "mark_oldest_active_null_agent_id_entry_turn_ended",
            lambda root: False,
        )
        monkeypatch.setattr(
            hook_mod, "get_active_dispatches", lambda root: remaining or []
        )
        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "afix-abc-hex123"}))
        return calls

    def test_handle_match_skips_id_call(self, hook_mod, monkeypatch, tmp_path):
        """agent_handle 比對成功時，不再呼叫 agent_id 精準比對——避免對
        已標記的 entry 做不必要的二次查找。"""
        calls = self._patch(
            hook_mod, monkeypatch, tmp_path, handle_result=True, id_result=True
        )

        rc = hook_mod.main()

        assert rc == 0
        assert calls["handle"] == 1
        assert calls["id"] == 0, "handle 比對成功後不應再呼叫 agent_id 比對"

    def test_handle_miss_falls_back_to_id(self, hook_mod, monkeypatch, tmp_path):
        """agent_handle 比對失敗（無 handle 可比對或無匹配）時，fallback
        到既有的 agent_id 精準比對——未命名派發的既有行為不變。"""
        calls = self._patch(
            hook_mod, monkeypatch, tmp_path, handle_result=False, id_result=True
        )

        rc = hook_mod.main()

        assert rc == 0
        assert calls["handle"] == 1
        assert calls["id"] == 1, "handle 比對失敗後應 fallback 到 agent_id 比對"


class TestRealDispatchTrackerIntegration:
    """端對端整合測試：真實 dispatch_tracker 函式 + 真實 dispatch-active.json
    檔案 I/O（不 mock mark_turn_ended_by_id / get_active_dispatches），驗證
    SubagentStop 事件後 entry 保留且含 name / ticket_id。

    實際 Task 工具派發無法在單元測試環境重現，本測試以「真實函式鏈路端對端
    執行」取代 mock，作為票面 acceptance「以實際派發驗證」的自動化替代
    佐證；完整的真實 Task 派發觀察仍需 PM 於實際 session 執行 SubagentStop
    後另行確認（見本票 Solution 說明）。
    """

    def test_entry_persists_with_name_and_ticket_id_after_subagent_stop(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        from lib.dispatch_tracker import get_active_dispatches, record_dispatch

        # hook_mod fixture 已將 __file__ 導向 tmp_path/fake_repo/.claude/hooks，
        # _get_project_root() 因此解析到 tmp_path/fake_repo，與下方 record_dispatch
        # 的 project_root 對齊，確保寫入與 main() 內部讀取是同一份檔案。
        project_root = hook_mod._get_project_root()
        record_dispatch(
            project_root,
            agent_description="修復 dart_parser",
            ticket_id="W7-9999",
            agent_id="agent-real-001",
            name="thyme-python-developer",
        )

        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-real-001"}))

        rc = hook_mod.main()
        assert rc == 0

        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1, "entry 應保留，不應被刪除"
        entry = dispatches[0]
        assert entry["turn_ended_at"] is not None
        assert entry["name"] == "thyme-python-developer"
        assert entry["ticket_id"] == "W7-9999"

        payload = json.loads(capsys.readouterr().out)
        assert "[OK]" in payload["systemMessage"]

    def test_named_dispatch_marked_via_agent_handle_when_agent_id_never_recorded(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """核心回歸案例：named 派發的 tool_response.agentId 從未補齊
        （record_dispatch 的 agent_id 參數為 None，重現識別碼命名空間
        修復票的實測現況），僅靠 agent_handle 仍能在 SubagentStop 時精準
        標記——這是本票要修的主要情境。"""
        from lib.dispatch_tracker import get_active_dispatches, record_dispatch

        project_root = hook_mod._get_project_root()
        record_dispatch(
            project_root,
            agent_description="修復某功能",
            ticket_id="W7-9998",
            agent_id=None,  # 實測現況：named 派發的 tool_response.agentId 缺席
            name="thyme-python-developer",
            agent_handle="fix-abc123",
        )

        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        # SubagentStop 回報的 agent_id：CC runtime 保證存在，格式
        # a<handle>-<hex>，與上方 record_dispatch 的 agent_id=None 無關
        monkeypatch.setattr(
            sys, "stdin", _stdin({"agent_id": "afix-abc123-73070ca5c1d3f849"})
        )

        rc = hook_mod.main()
        assert rc == 0

        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 1, "entry 應保留，不應被刪除"
        entry = dispatches[0]
        assert entry["turn_ended_at"] is not None, (
            "修復前此案例的 turn_ended_at 恆為 None（agent_id 精準比對與 "
            "FIFO 皆失敗）；修復後應透過 agent_handle 成功標記"
        )
        assert entry["agent_id"] is None, "agent_id 欄位本身不變，仍為 None"

    def test_parallel_dispatch_with_multiple_null_agent_id_candidates(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """AC2：平行派發情境（>1 個 agent_id=None 候選，FIFO 依設計停用）
        下，named 派發仍可透過 agent_handle 精準標記；同批其他未被
        SubagentStop 觸發的候選不受影響（不誤標）。"""
        from lib.dispatch_tracker import get_active_dispatches, record_dispatch

        project_root = hook_mod._get_project_root()
        # 模擬同批次平行派發 4 個代理人，agent_id 皆缺席（tool_response.
        # agentId 缺席為實測現況），其中 3 個為 named（各有 agent_handle）
        record_dispatch(
            project_root, "task A", agent_id=None,
            name="thyme-python-developer", agent_handle="fix-taskA",
        )
        record_dispatch(
            project_root, "task B", agent_id=None,
            name="thyme-documentation-integrator", agent_handle="fix-taskB",
        )
        record_dispatch(
            project_root, "task C", agent_id=None,
            name="basil-hook-architect", agent_handle="fix-taskC",
        )
        record_dispatch(project_root, "task D (unnamed)", agent_id=None)

        # 候選數 4（> 1）：修復前這會使 FIFO fallback 依設計停用，
        # agent_id 精準比對也因命名空間不符必然失敗，taskB 的
        # turn_ended_at 會恆為 None。修復後應透過 agent_handle 精準比對
        # 成功，不受候選數 > 1 影響（handle 比對本就不經過 FIFO 路徑）。
        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        monkeypatch.setattr(
            sys, "stdin", _stdin({"agent_id": "afix-taskB-7c3ab68f2489cc2b"})
        )

        rc = hook_mod.main()
        assert rc == 0

        dispatches = get_active_dispatches(project_root)
        assert len(dispatches) == 4, "entry 皆應保留，不應被刪除"
        by_handle = {d.get("agent_handle") or d["agent_description"]: d for d in dispatches}

        assert by_handle["fix-taskB"]["turn_ended_at"] is not None, (
            "平行情境（候選 > 1）下，named 派發應仍能透過 agent_handle "
            "精準標記，不落入 FIFO 停用分支"
        )
        # 未被本次 SubagentStop 觸發的其他候選不應被誤標
        assert by_handle["fix-taskA"]["turn_ended_at"] is None
        assert by_handle["fix-taskC"]["turn_ended_at"] is None
        assert by_handle["task D (unnamed)"]["turn_ended_at"] is None


class TestStopHookActiveCircuitBreaker:
    """1.0.0-W1-055.1 修復 1：stop_hook_active=true 靜默退出（自激迴圈斷路器）。"""

    def test_stop_hook_active_silent(self, hook_mod, monkeypatch, capsys, tmp_path):
        """stop_hook_active=true 時靜默 exit 0，不執行標記、不輸出任何 JSON。"""
        calls = {"mark": 0}

        def _record_mark(root, aid):
            calls["mark"] += 1
            return True

        state_file = tmp_path / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "mark_turn_ended_by_id", _record_mark)
        monkeypatch.setattr(
            sys, "stdin",
            _stdin({"agent_id": "agent-xyz", "stop_hook_active": True}),
        )

        rc = hook_mod.main()
        assert rc == 0

        captured = capsys.readouterr()
        assert captured.out == "", "stop_hook_active=true 不應輸出（避免再注入）"
        assert calls["mark"] == 0, "stop_hook_active=true 不應執行標記（首次事件已標記）"

    def test_stop_hook_active_false_normal_flow(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """stop_hook_active=false 時照常執行（不誤傷正常事件）。"""
        state_dir = tmp_path / ".claude"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "mark_turn_ended_by_id", lambda root, aid: True)
        monkeypatch.setattr(
            hook_mod, "mark_oldest_active_null_agent_id_entry_turn_ended",
            lambda root: False,
        )
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


class TestFifoFallbackMultipleNullCandidates:
    """FIFO 後援於 null 候選數 > 1 時停用，避免誤將仍在執行中的記錄標記為
    已結束回合。

    背景：isolation=none 派發的 agent_id 全記為 null，FIFO 若在多筆並存時
    仍標記「最早」的一筆，不保證是本次真正結束的那一筆。
    """

    def test_declines_mark_when_multiple_null_candidates(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """null 候選 2 筆：不呼叫 mark_oldest_active_null_agent_id_entry_turn_ended，
        僅供 [WAIT] 訊息。"""
        state_file = tmp_path / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")

        def _fail_if_called(root):
            raise AssertionError(
                "候選數 > 1 時不應呼叫 mark_oldest_active_null_agent_id_entry_turn_ended"
            )

        null_candidates = [
            {
                "agent_id": None,
                "agent_description": "agent-A",
                "ticket_id": "T-A",
                "dispatched_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "agent_id": None,
                "agent_description": "agent-B",
                "ticket_id": "T-B",
                "dispatched_at": "2026-01-01T00:01:00+00:00",
            },
        ]

        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "mark_turn_ended_by_id", lambda root, aid: False)
        monkeypatch.setattr(
            hook_mod, "mark_oldest_active_null_agent_id_entry_turn_ended",
            _fail_if_called,
        )
        monkeypatch.setattr(hook_mod, "get_active_dispatches", lambda root: null_candidates)
        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-no-match"}))

        rc = hook_mod.main()
        assert rc == 0

        payload = json.loads(capsys.readouterr().out)
        msg = payload["systemMessage"]
        assert "[WAIT]" in msg, "未標記任一記錄，候選仍在 still_running 中觸發 [WAIT]"
        assert "仍有 2 個代理人" in msg
        assert "已標記回合結束" not in msg, "候選數 > 1 時不應宣稱已標記"

    def test_single_null_candidate_still_uses_fifo(
        self, hook_mod, monkeypatch, capsys, tmp_path
    ):
        """null 候選 = 1 筆：維持原 FIFO 行為（向後相容，非本次修改範圍）。"""
        state_file = tmp_path / "dispatch-active.json"
        state_file.write_text("{}", encoding="utf-8")

        calls = {"count": 0}

        def _record_fifo(root):
            calls["count"] += 1
            return True

        one_candidate = [
            {
                "agent_id": None,
                "agent_description": "agent-A",
                "ticket_id": "T-A",
                "dispatched_at": "2026-01-01T00:00:00+00:00",
            },
        ]

        monkeypatch.setattr(hook_mod, "get_state_file_path", lambda root: state_file)
        monkeypatch.setattr(hook_mod, "mark_turn_ended_by_id", lambda root, aid: False)
        monkeypatch.setattr(
            hook_mod, "mark_oldest_active_null_agent_id_entry_turn_ended", _record_fifo
        )
        monkeypatch.setattr(hook_mod, "get_active_dispatches", lambda root: one_candidate)
        monkeypatch.setattr(
            hook_mod, "_get_wait_dedup_state_file",
            lambda root: tmp_path / "wait-broadcast-dedup.json",
        )
        monkeypatch.setattr(sys, "stdin", _stdin({"agent_id": "agent-no-match"}))

        rc = hook_mod.main()
        assert rc == 0
        assert calls["count"] == 1, "候選數 <= 1 時應照常呼叫 FIFO 清理"


class TestWaitBroadcastDedup:
    """1.0.0-W1-055.1 修復 2：[WAIT] 廣播以 agent_id + still_running hash 做 TTL 去重。"""

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
        monkeypatch.setattr(hook_mod, "mark_turn_ended_by_id", lambda root, aid: cleared)
        monkeypatch.setattr(
            hook_mod, "mark_oldest_active_null_agent_id_entry_turn_ended",
            lambda root: cleared,
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
