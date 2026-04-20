"""Regression tests for CheckpointCaller / _VALID_CALLERS 單源一致性（W10-017.11 AC 5）。

目的：防護 checkpoint_state.CheckpointCaller Literal 與 checkpoint_view._VALID_CALLERS
之間的雙源漂移（W10-017.11 Phase 4b P0 重構結論）。
"""

from __future__ import annotations

from typing import get_args

import pytest

from ticket_system.lib.checkpoint_state import CheckpointCaller
from ticket_system.lib.checkpoint_view import _VALID_CALLERS, handoff_status_for


# 三命令實際傳入 caller 值（snapshot/handoff-ready/checkpoint-status 命令原始碼）
EXPECTED_CLI_CALLERS = {"snapshot", "handoff-ready", "checkpoint-status"}


class TestCallerLiteralConsistency:
    """CheckpointCaller Literal 與 CLI 實際 caller 的一致性。"""

    def test_literal_contains_all_cli_callers(self) -> None:
        """Literal 必須包含所有 CLI 實際傳入的 caller 值。"""
        literal_values = set(get_args(CheckpointCaller))
        missing = EXPECTED_CLI_CALLERS - literal_values
        assert not missing, f"Literal 缺少 CLI caller: {missing}"

    def test_literal_has_no_unused_cli_callers(self) -> None:
        """Literal 除了 'unknown'（log fallback）外，不應含未使用的 CLI caller。

        尤其 'dispatch-check' 曾預留但從未落地，應已移除。
        """
        literal_values = set(get_args(CheckpointCaller))
        # 排除 log fallback 值
        cli_literal = literal_values - {"unknown"}
        extra = cli_literal - EXPECTED_CLI_CALLERS
        assert not extra, f"Literal 含未使用的 caller: {extra}"

    def test_dispatch_check_removed(self) -> None:
        """明確防護：'dispatch-check' 不應再出現在 Literal。"""
        assert "dispatch-check" not in get_args(CheckpointCaller)


class TestValidCallersDerivedFromLiteral:
    """_VALID_CALLERS 從 CheckpointCaller 派生（避免雙源定義）。"""

    def test_valid_callers_matches_cli_literal(self) -> None:
        """_VALID_CALLERS 應等於 Literal 去掉 'unknown' 後的集合。"""
        expected = set(get_args(CheckpointCaller)) - {"unknown"}
        assert set(_VALID_CALLERS) == expected

    def test_valid_callers_matches_expected_cli_set(self) -> None:
        """_VALID_CALLERS 應恰好等於三 CLI 命令 caller。"""
        assert set(_VALID_CALLERS) == EXPECTED_CLI_CALLERS

    def test_handoff_status_for_accepts_all_valid_callers(self) -> None:
        """handoff_status_for 必須接受 _VALID_CALLERS 所有成員（不 raise）。"""
        from ticket_system.lib.checkpoint_state import CheckpointState

        state = CheckpointState(
            current_phase="3",
            ready_for_clear=True,
            pending_checks=[],
            active_agents=0,
            unmerged_worktrees=[],
            active_handoff=None,
            in_progress_tickets=[],
            data_sources={},
            computed_at="2026-04-19T00:00:00+00:00",
            uncommitted_files=0,
        )
        for caller in _VALID_CALLERS:
            # 不 raise 即視為通過
            is_ok, msg = handoff_status_for(state, caller)
            assert isinstance(is_ok, bool)
            assert isinstance(msg, str)

    def test_handoff_status_for_rejects_unknown_caller(self) -> None:
        """handoff_status_for 對非 _VALID_CALLERS 成員 raise ValueError。"""
        from ticket_system.lib.checkpoint_state import CheckpointState

        state = CheckpointState(
            current_phase="3",
            ready_for_clear=True,
            pending_checks=[],
            active_agents=0,
            unmerged_worktrees=[],
            active_handoff=None,
            in_progress_tickets=[],
            data_sources={},
            computed_at="2026-04-19T00:00:00+00:00",
            uncommitted_files=0,
        )
        with pytest.raises(ValueError):
            handoff_status_for(state, "dispatch-check")
        with pytest.raises(ValueError):
            handoff_status_for(state, "unknown")
