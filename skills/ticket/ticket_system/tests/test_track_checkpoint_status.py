"""RED tests for ticket_system/commands/track_checkpoint_status.py (W10-017.1 Phase 3a).

對應 sage Phase 2 §4.3 (K1-K10) + §6 (F3) = 11 案例。

Phase 3b 實作後預期全部變綠。RED 原因：
- track_checkpoint_status.py 尚未存在
- register_checkpoint_status 尚未在 commands/track.py 註冊
"""

from __future__ import annotations

import argparse
import io
import sys
from typing import Any, List, Optional

import pytest

from ticket_system.lib.checkpoint_state import CheckpointState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    *,
    current_phase: str = "3",
    ready_for_clear: bool = True,
    active_agents: int = 0,
    uncommitted_files: Optional[int] = 0,
    unmerged_worktrees: Optional[List[str]] = None,
    active_handoff: Optional[str] = None,
    in_progress_tickets: Optional[List[str]] = None,
    data_sources: Optional[dict] = None,
    ticket_id: Optional[str] = None,
) -> CheckpointState:
    return CheckpointState(
        current_phase=current_phase,
        ready_for_clear=ready_for_clear,
        pending_checks=[],
        active_agents=active_agents,
        unmerged_worktrees=unmerged_worktrees or [],
        active_handoff=active_handoff,
        in_progress_tickets=in_progress_tickets or [],
        data_sources=data_sources or {
            "git-status": "ok", "dispatch-active": "ok",
            "handoff-pending": "ok", "ticket-query": "ok", "git-worktree": "ok",
        },
        computed_at="2026-04-19T12:00:00+00:00",
        uncommitted_files=uncommitted_files,
        _ticket_id=ticket_id,
    )


def _run_checkpoint_status(
    monkeypatch, state_or_exc, ticket_id: Optional[str] = None,
    spy_calls: Optional[list] = None,
) -> tuple[int, str, str]:
    from ticket_system.commands import track_checkpoint_status as mod
    from ticket_system.commands.track_checkpoint_status import (
        execute_checkpoint_status,
    )

    def fake_checkpoint_state(*args, **kwargs):
        if spy_calls is not None:
            spy_calls.append({"args": args, "kwargs": kwargs})
        if isinstance(state_or_exc, BaseException):
            raise state_or_exc
        return state_or_exc

    monkeypatch.setattr(mod, "checkpoint_state", fake_checkpoint_state)

    args = argparse.Namespace(ticket_id=ticket_id)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        rc = execute_checkpoint_status(args)
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


# ---------------------------------------------------------------------------
# K1-K6: 核心輸出與退出碼
# ---------------------------------------------------------------------------


def test_K1_outputs_phase_id_and_label(monkeypatch):
    state = _make_state(
        current_phase="1", uncommitted_files=3, ready_for_clear=False,
    )
    rc, out, _ = _run_checkpoint_status(monkeypatch, state)
    assert rc == 0
    assert "C1 未提交變更" in out
    assert "phase_id:" in out
    assert "1" in out


def test_K2_outputs_ready_for_clear_flag(monkeypatch):
    state = _make_state(
        current_phase="1", uncommitted_files=3, ready_for_clear=False,
    )
    rc, out, _ = _run_checkpoint_status(monkeypatch, state)
    assert "ready_for_clear:" in out
    assert "false" in out.lower()


def test_K3_outputs_data_source_status(monkeypatch):
    state = _make_state()
    rc, out, _ = _run_checkpoint_status(monkeypatch, state)
    assert "資料來源狀態:" in out
    # 5 個資料源行
    for src in ("git-status", "dispatch-active", "handoff-pending",
                "ticket-query", "git-worktree"):
        assert src in out, f"Missing data source line for {src}"


def test_K4_displays_data_source_failures(monkeypatch):
    state = _make_state(
        data_sources={
            "git-status": "FileNotFoundError: no such file",
            "dispatch-active": "ok", "handoff-pending": "ok",
            "ticket-query": "ok", "git-worktree": "ok",
        },
    )
    rc, out, _ = _run_checkpoint_status(monkeypatch, state)
    assert "git-status:" in out
    assert "FileNotFoundError" in out


def test_K5_outputs_next_action(monkeypatch):
    state = _make_state(
        current_phase="1", uncommitted_files=3, ready_for_clear=False,
    )
    rc, out, _ = _run_checkpoint_status(monkeypatch, state)
    assert "下一步:" in out
    assert "git add" in out and "git commit" in out
    assert "(3 檔)" in out


def test_K6_exit_always_zero(monkeypatch):
    """純報告型，任意 state 永遠 exit 0."""
    for state in [
        _make_state(current_phase="3", ready_for_clear=True),
        _make_state(current_phase="1", uncommitted_files=10, ready_for_clear=False),
        _make_state(current_phase="1.85", active_agents=5, ready_for_clear=False),
    ]:
        rc, _, _ = _run_checkpoint_status(monkeypatch, state)
        assert rc == 0


# ---------------------------------------------------------------------------
# K7: 內部錯誤
# ---------------------------------------------------------------------------


def test_K7_internal_error_exit_1(monkeypatch):
    rc, _, err = _run_checkpoint_status(monkeypatch, RuntimeError("boom"))
    assert rc == 1
    assert "internal error" in err.lower() or "boom" in err


# ---------------------------------------------------------------------------
# K8-K10: argparse / caller / 全域語意
# ---------------------------------------------------------------------------


def test_K8_argparse_ticket_id_flag():
    from ticket_system.commands.track_checkpoint_status import (
        register_checkpoint_status,
    )

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation")
    register_checkpoint_status(subparsers)
    ns = parser.parse_args(["checkpoint-status", "--ticket-id", "X"])
    assert ns.operation == "checkpoint-status"
    assert ns.ticket_id == "X"


def test_K9_calls_checkpoint_state_with_caller(monkeypatch):
    state = _make_state()
    spy_calls: list = []
    _run_checkpoint_status(monkeypatch, state, spy_calls=spy_calls)
    assert len(spy_calls) >= 1
    callers = [c["kwargs"].get("caller") for c in spy_calls]
    assert "checkpoint-status" in callers, (
        f"Expected caller='checkpoint-status', got {callers}"
    )


def test_K10_global_when_no_ticket_id(monkeypatch):
    state = _make_state()
    rc, out, _ = _run_checkpoint_status(monkeypatch, state, ticket_id=None)
    assert "Ticket:" in out
    # 全域語意：含 "全域" 字樣
    ticket_lines = [ln for ln in out.splitlines() if ln.startswith("Ticket:")]
    assert len(ticket_lines) >= 1
    assert "全域" in ticket_lines[0]


# ---------------------------------------------------------------------------
# F3: fail-open 路徑（部分資料源失敗）
# ---------------------------------------------------------------------------


def test_F3_fail_open_on_io_error_displays_partial(monkeypatch):
    """F3: 部分資料源 fallback (state.data_sources 含 error 字串) → exit 0 + 顯示錯誤訊息."""
    state = _make_state(
        data_sources={
            "git-status": "ok",
            "dispatch-active": "JSONDecodeError: Expecting value",
            "handoff-pending": "ok", "ticket-query": "ok", "git-worktree": "ok",
        },
    )
    rc, out, _ = _run_checkpoint_status(monkeypatch, state)
    assert rc == 0
    assert "dispatch-active:" in out
    assert "JSONDecodeError" in out
