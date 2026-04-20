"""Regression tests for _render_degraded_snapshot DRY 複用（W10-017.11 AC 4/5）。

目的：防護 _render_degraded_snapshot 再次退回獨立字串實作，與 render_current_suggestion
+ render_ready_check 兩 view function 漂移。
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from ticket_system.commands.track_snapshot import (
    _build_degraded_state,
    _render_degraded_snapshot,
)
from ticket_system.lib.checkpoint_view import (
    render_current_suggestion,
    render_ready_check,
)


class TestDegradedStateBuilder:
    """_build_degraded_state 提供可被 view function 消費的 CheckpointState。"""

    def test_degraded_state_fields_fallback(self) -> None:
        state = _build_degraded_state("simulated IOError")
        assert state.active_agents == 0
        assert state.unmerged_worktrees == []
        assert state.active_handoff is None
        assert state.in_progress_tickets == []
        assert state.uncommitted_files is None  # 觸發 Ready Check [?] 分支
        assert state.current_phase == "3"

    def test_degraded_state_records_error_in_pending(self) -> None:
        state = _build_degraded_state("simulated IOError")
        assert any("simulated IOError" in c.reason for c in state.pending_checks)


class TestDegradedSnapshotReusesRenderFunctions:
    """AC 4：_render_degraded_snapshot 產出必須由 render_* 函式組成。"""

    def test_output_contains_render_current_suggestion(self) -> None:
        error = "boom"
        state = _build_degraded_state(error)
        expected_block = render_current_suggestion(state)

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = _render_degraded_snapshot(error)
        output = buf.getvalue()

        assert rc == 0
        assert expected_block in output

    def test_output_contains_render_ready_check(self) -> None:
        error = "boom"
        state = _build_degraded_state(error)
        expected_block = render_ready_check(state, caller="snapshot")

        buf = io.StringIO()
        with redirect_stdout(buf):
            _render_degraded_snapshot(error)
        output = buf.getvalue()

        assert expected_block in output

    def test_output_still_reports_data_source_unavailable(self) -> None:
        """降級路徑必須清楚標示資料源不可用（與 error 一起）。"""
        buf = io.StringIO()
        with redirect_stdout(buf):
            _render_degraded_snapshot("disk gone")
        output = buf.getvalue()
        assert "資料源不可用" in output
        assert "disk gone" in output
