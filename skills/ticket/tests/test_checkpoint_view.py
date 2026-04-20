"""RED tests for ticket_system/lib/checkpoint_view.py (W10-017.1 Phase 3a).

對應 sage Phase 2 §3 (V1-V7) + §6 (F4)。

測試範圍：
- handoff_status_for(state, caller) 三 caller × (None / not None) = 6 路徑
- handoff_status_for(caller="bogus") raise ValueError (v2.2 Q1)
- F4 靜態檢查 CLI except 子句使用 lib IO_ERRORS

Phase 3b 實作後預期全部變綠。RED 原因：lib/checkpoint_view.py 尚未存在。
"""

from __future__ import annotations

import inspect

import pytest

from ticket_system.lib.checkpoint_state import CheckpointState


def _make_state(active_handoff=None, **overrides) -> CheckpointState:
    """構造 CheckpointState helper（lib dataclass 不 Mock，符合 Sociable Unit Tests）。"""
    defaults = dict(
        current_phase="3",
        ready_for_clear=True,
        pending_checks=[],
        active_agents=0,
        unmerged_worktrees=[],
        active_handoff=active_handoff,
        in_progress_tickets=[],
        data_sources={},
        computed_at="2026-04-19T12:00:00+00:00",
        uncommitted_files=0,
    )
    defaults.update(overrides)
    return CheckpointState(**defaults)


# ---------------------------------------------------------------------------
# V1-V6: handoff_status_for 三 caller × (None / not None)
# ---------------------------------------------------------------------------


def test_view_snapshot_handoff_present_returns_blocking():
    """V1: snapshot caller + active_handoff not None → (False, "先處理 pending handoff" + ticket_id)."""
    from ticket_system.lib.checkpoint_view import handoff_status_for

    state = _make_state(active_handoff="W10-017.1")
    is_ok, msg = handoff_status_for(state, caller="snapshot")
    assert is_ok is False
    assert "先處理 pending handoff" in msg
    assert "W10-017.1" in msg


def test_view_snapshot_handoff_absent_returns_pass():
    """V2: snapshot caller + active_handoff None → (True, "無 pending handoff")."""
    from ticket_system.lib.checkpoint_view import handoff_status_for

    state = _make_state(active_handoff=None)
    is_ok, msg = handoff_status_for(state, caller="snapshot")
    assert is_ok is True
    assert "無 pending handoff" in msg


def test_view_handoff_ready_present_returns_go_signal():
    """V3: handoff-ready caller + active_handoff not None → (True, "handoff 已建立" + ticket_id)."""
    from ticket_system.lib.checkpoint_view import handoff_status_for

    state = _make_state(active_handoff="W10-017.1")
    is_ok, msg = handoff_status_for(state, caller="handoff-ready")
    assert is_ok is True
    assert "handoff 已建立" in msg
    assert "W10-017.1" in msg


def test_view_handoff_ready_absent_defers_to_other_blockers():
    """V4: handoff-ready caller + active_handoff None → (True, ...)；不阻擋 GO."""
    from ticket_system.lib.checkpoint_view import handoff_status_for

    state = _make_state(active_handoff=None)
    is_ok, msg = handoff_status_for(state, caller="handoff-ready")
    assert is_ok is True
    # 訊息描述「無 handoff，看其他阻擋」（不阻擋 GO 結論）
    assert "handoff" in msg


def test_view_checkpoint_status_present_reports_only():
    """V5: checkpoint-status caller + active_handoff not None → (True, "handoff pending" + id)."""
    from ticket_system.lib.checkpoint_view import handoff_status_for

    state = _make_state(active_handoff="W10-017.1")
    is_ok, msg = handoff_status_for(state, caller="checkpoint-status")
    assert is_ok is True
    assert "handoff pending" in msg
    assert "W10-017.1" in msg


def test_view_checkpoint_status_absent_reports_only():
    """V6: checkpoint-status caller + active_handoff None → (True, "無 pending handoff")."""
    from ticket_system.lib.checkpoint_view import handoff_status_for

    state = _make_state(active_handoff=None)
    is_ok, msg = handoff_status_for(state, caller="checkpoint-status")
    assert is_ok is True
    assert "無 pending handoff" in msg


# ---------------------------------------------------------------------------
# V7: unknown caller (v2.2 Q1 PM 決策：raise ValueError)
# ---------------------------------------------------------------------------


def test_view_unknown_caller_raises_value_error():
    """V7: caller="bogus" → raise ValueError("unknown caller: bogus") (v2.2 Q1)."""
    from ticket_system.lib.checkpoint_view import handoff_status_for

    state = _make_state(active_handoff=None)
    with pytest.raises(ValueError) as exc_info:
        handoff_status_for(state, caller="bogus")
    assert "unknown caller" in str(exc_info.value)
    assert "bogus" in str(exc_info.value)


# ---------------------------------------------------------------------------
# format_local_time helper (v2.2 Q4：系統時區)
# ---------------------------------------------------------------------------


def test_format_local_time_uses_state_computed_at():
    """format_local_time 從 state.computed_at 取值並轉本地時區字串."""
    from ticket_system.lib.checkpoint_view import format_local_time

    state = _make_state()
    result = format_local_time(state)
    assert isinstance(result, str)
    # 含 "(local)" 標記（v2.2 Q4 規格）
    assert "local" in result.lower()
    # 預期格式 "YYYY-MM-DD HH:MM (local)"
    assert "2026" in result  # 從 state.computed_at 解析出年份


# ---------------------------------------------------------------------------
# F4: CLI except 子句靜態檢查（驗證 import IO_ERRORS from lib 而非重複定義）
# ---------------------------------------------------------------------------


def test_F4_cli_except_clause_imports_io_errors_from_lib():
    """F4: 三命令 except 子句使用 IO_ERRORS from lib（避免重複定義）."""
    from ticket_system.commands import (
        track_snapshot,
        track_handoff_ready,
        track_checkpoint_status,
    )

    # 三個 module 都應 import IO_ERRORS
    for mod in (track_snapshot, track_handoff_ready, track_checkpoint_status):
        src = inspect.getsource(mod)
        # 驗證 import 形式：from ticket_system.lib.checkpoint_state import ... IO_ERRORS ...
        assert "IO_ERRORS" in src, f"{mod.__name__} missing IO_ERRORS import"
        # 確認不是另外定義 IO_ERRORS = (...)，而是 import
        assert (
            "from ticket_system.lib.checkpoint_state import" in src
            and "IO_ERRORS" in src
        ), f"{mod.__name__} should import IO_ERRORS from lib.checkpoint_state"
