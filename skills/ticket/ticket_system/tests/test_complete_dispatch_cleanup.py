"""lifecycle._clear_dispatch_for_completed_ticket 測試套件（0.2.1-W3-1371）。

驗證 complete() 收尾流程新增的 dispatch-active 清除呼叫：
1. dispatch_tracker 模組可用時，以 ticket_id 呼叫 clear_dispatch_by_ticket_id。
2. 清除有命中時印出提示；無命中時不輸出。
3. dispatch_tracker 模組不可用（load_claude_lib 回傳 None）時 fail-open，寫 stderr。
4. clear_dispatch_by_ticket_id 拋例外時 fail-open，寫 stderr，不向外傳播例外。
5. 反事實測試（TestCounterfactualImmediateClearance）：真實 dispatch_tracker
   模組（非 mock），驗證條目消失確實由本函式觸發，非巧合經由 24 小時 TTL。
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ticket_system.commands import lifecycle

_TICKET_ID = "0.2.1-W3-1371"


class TestClearDispatchForCompletedTicket:
    def test_calls_clear_dispatch_by_ticket_id_with_ticket_id(self):
        mock_tracker = MagicMock()
        mock_tracker.clear_dispatch_by_ticket_id.return_value = 2
        with patch.object(
            lifecycle, "_load_dispatch_tracker", return_value=mock_tracker
        ), patch.object(
            lifecycle, "get_ticket_state_root", return_value="/fake/root"
        ):
            lifecycle._clear_dispatch_for_completed_ticket(_TICKET_ID)

        mock_tracker.clear_dispatch_by_ticket_id.assert_called_once_with(
            "/fake/root", _TICKET_ID
        )

    def test_prints_hint_when_entries_removed(self, capsys):
        mock_tracker = MagicMock()
        mock_tracker.clear_dispatch_by_ticket_id.return_value = 3
        with patch.object(
            lifecycle, "_load_dispatch_tracker", return_value=mock_tracker
        ), patch.object(lifecycle, "get_ticket_state_root", return_value="/fake/root"):
            lifecycle._clear_dispatch_for_completed_ticket(_TICKET_ID)

        out = capsys.readouterr().out
        assert "3" in out
        assert _TICKET_ID in out

    def test_no_output_when_nothing_removed(self, capsys):
        mock_tracker = MagicMock()
        mock_tracker.clear_dispatch_by_ticket_id.return_value = 0
        with patch.object(
            lifecycle, "_load_dispatch_tracker", return_value=mock_tracker
        ), patch.object(lifecycle, "get_ticket_state_root", return_value="/fake/root"):
            lifecycle._clear_dispatch_for_completed_ticket(_TICKET_ID)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_module_unavailable_fails_open_with_stderr(self, capsys):
        with patch.object(lifecycle, "_load_dispatch_tracker", return_value=None):
            lifecycle._clear_dispatch_for_completed_ticket(_TICKET_ID)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert "dispatch_tracker" in captured.err

    def test_exception_fails_open_does_not_propagate(self, capsys):
        mock_tracker = MagicMock()
        mock_tracker.clear_dispatch_by_ticket_id.side_effect = RuntimeError("boom")
        with patch.object(
            lifecycle, "_load_dispatch_tracker", return_value=mock_tracker
        ), patch.object(lifecycle, "get_ticket_state_root", return_value="/fake/root"):
            # 不應拋出例外
            lifecycle._clear_dispatch_for_completed_ticket(_TICKET_ID)

        captured = capsys.readouterr()
        assert "boom" in captured.err

    def test_empty_ticket_id_still_delegates_to_tracker(self):
        """本函式不重複做空字串守衛——`clear_dispatch_by_ticket_id` 自身
        已對空 ticket_id 回傳 0（見 dispatch_tracker 測試），此處僅驗證
        呼叫沒有被本層攔截。"""
        mock_tracker = MagicMock()
        mock_tracker.clear_dispatch_by_ticket_id.return_value = 0
        with patch.object(
            lifecycle, "_load_dispatch_tracker", return_value=mock_tracker
        ), patch.object(lifecycle, "get_ticket_state_root", return_value="/fake/root"):
            lifecycle._clear_dispatch_for_completed_ticket("")

        mock_tracker.clear_dispatch_by_ticket_id.assert_called_once_with(
            "/fake/root", ""
        )


class TestCounterfactualImmediateClearance:
    """反事實測試：真實 dispatch_tracker 模組（非 mock），全程不呼叫
    `cleanup_expired`，`turn_ended_at` 錨定為呼叫當下（距 24 小時 TTL
    邊界甚遠）——條目若消失，唯一可能原因是
    `_clear_dispatch_for_completed_ticket` 本身，非 TTL 逾時路徑。"""

    def test_ticket_bound_entry_disappears_immediately_on_complete(self, tmp_path):
        from ticket_system.lib.claude_lib_loader import load_claude_lib

        dispatch_tracker = load_claude_lib("dispatch_tracker")
        assert dispatch_tracker is not None, "真實 .claude/lib/dispatch_tracker 應可載入"

        ticket_id = "0.2.1-W3-9001"
        agent_id = "a-test-agent-9001"
        dispatch_tracker.record_dispatch(
            tmp_path,
            "test-agent",
            ticket_id=ticket_id,
            agent_id=agent_id,
        )
        # 模擬 SubagentStop 已標記回合結束：turn_ended_at 為呼叫當下，
        # 距 24 小時 TTL（TURN_ENDED_MAX_AGE_HOURS）邊界甚遠。
        dispatch_tracker.mark_turn_ended_by_id(tmp_path, agent_id)
        before = dispatch_tracker.get_active_dispatches(tmp_path)
        assert len(before) == 1
        turn_ended_at = datetime.fromisoformat(before[0]["turn_ended_at"])
        assert (datetime.now(timezone.utc) - turn_ended_at).total_seconds() < 60, (
            "turn_ended_at 須為剛剛，證明後續消失非 24 小時 TTL 所致"
        )

        with patch.object(lifecycle, "get_ticket_state_root", return_value=tmp_path):
            lifecycle._clear_dispatch_for_completed_ticket(ticket_id)

        remaining = dispatch_tracker.get_active_dispatches(tmp_path)
        assert remaining == []
