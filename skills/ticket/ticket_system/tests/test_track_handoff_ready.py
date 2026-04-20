"""RED tests for ticket_system/commands/track_handoff_ready.py (W10-017.1 Phase 3a).

對應 sage Phase 2 §2 真值表 #1-#10 + §4.2 H11-H15 = 15 案例。

Phase 3b 實作後預期全部變綠。RED 原因：
- track_handoff_ready.py 尚未存在
- register_handoff_ready 尚未在 commands/track.py 註冊
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
        data_sources={
            "git-status": "ok", "dispatch-active": "ok",
            "handoff-pending": "ok", "ticket-query": "ok", "git-worktree": "ok",
        },
        computed_at="2026-04-19T12:00:00+00:00",
        uncommitted_files=uncommitted_files,
        _ticket_id=ticket_id,
    )


def _run_handoff_ready(
    monkeypatch, state_or_exc, ticket_id: Optional[str] = None,
    spy_calls: Optional[list] = None,
) -> tuple[int, str, str]:
    """執行 execute_handoff_ready，回傳 (rc, stdout, stderr)."""
    from ticket_system.commands import track_handoff_ready as mod
    from ticket_system.commands.track_handoff_ready import execute_handoff_ready

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
        rc = execute_handoff_ready(args)
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


# ---------------------------------------------------------------------------
# §2 真值表 #1-#10 (5 phase × ticket-id 2 維)
# ---------------------------------------------------------------------------


def test_handoff_ready_c3_clean_returns_go(monkeypatch):
    """#1 C3 全乾淨 + ticket-id unspecified → GO (exit 0)."""
    state = _make_state(current_phase="3", ready_for_clear=True)
    rc, out, _ = _run_handoff_ready(monkeypatch, state)
    assert rc == 0
    assert "結論: GO" in out
    assert "ready for /clear" in out


def test_handoff_ready_c2_active_handoff_returns_go(monkeypatch):
    """#2 C2 handoff 已建立 + 其他全 0 → GO (exit 0)."""
    state = _make_state(
        current_phase="2", active_handoff="W10-017.1", ready_for_clear=True,
    )
    rc, out, _ = _run_handoff_ready(monkeypatch, state, ticket_id="W10-017.1")
    assert rc == 0
    assert "handoff 已建立" in out


def test_handoff_ready_c1_uncommitted_unspecified_returns_no_go(monkeypatch):
    """#3 C1 uncommitted=3 + unspecified → NO-GO (exit 2)."""
    state = _make_state(
        current_phase="1", uncommitted_files=3, ready_for_clear=False,
    )
    rc, out, _ = _run_handoff_ready(monkeypatch, state)
    assert rc == 2
    assert "未提交變更" in out or "uncommitted" in out.lower()
    assert "3" in out  # 3 檔


def test_handoff_ready_c1_uncommitted_specified_still_no_go(monkeypatch):
    """#4 C1 uncommitted=3 + specified ticket-id → NO-GO (全域判定不過濾)."""
    state = _make_state(
        current_phase="1", uncommitted_files=3, ready_for_clear=False,
        ticket_id="W10-017.1",
    )
    rc, out, _ = _run_handoff_ready(monkeypatch, state, ticket_id="W10-017.1")
    assert rc == 2


def test_handoff_ready_c185_active_agents_unspecified_no_go(monkeypatch):
    """#5 C1.85 active_agents=2 + unspecified → NO-GO."""
    state = _make_state(
        current_phase="1.85", active_agents=2, ready_for_clear=False,
    )
    rc, out, _ = _run_handoff_ready(monkeypatch, state)
    assert rc == 2
    assert "活躍代理人" in out or "active_agents" in out
    assert "2" in out


def test_handoff_ready_c185_active_agents_specified_still_no_go(monkeypatch):
    """#6 C1.85 active_agents=2 + specified → NO-GO (全域判定)."""
    state = _make_state(
        current_phase="1.85", active_agents=2, ready_for_clear=False,
        ticket_id="W10-017.1",
    )
    rc, _, _ = _run_handoff_ready(monkeypatch, state, ticket_id="W10-017.1")
    assert rc == 2


def test_handoff_ready_c19_unmerged_worktree_unspecified_no_go(monkeypatch):
    """#7 C1.9 unmerged_worktree + unspecified → NO-GO."""
    state = _make_state(
        current_phase="1.9", unmerged_worktrees=["wt-a"], ready_for_clear=False,
    )
    rc, out, _ = _run_handoff_ready(monkeypatch, state)
    assert rc == 2
    assert "worktree" in out.lower() or "未合併" in out


def test_handoff_ready_c19_unmerged_worktree_specified_still_no_go(monkeypatch):
    """#8 C1.9 unmerged_worktree + specified → NO-GO (全域判定)."""
    state = _make_state(
        current_phase="1.9", unmerged_worktrees=["wt-a"], ready_for_clear=False,
        ticket_id="W10-017.1",
    )
    rc, _, _ = _run_handoff_ready(monkeypatch, state, ticket_id="W10-017.1")
    assert rc == 2


def test_handoff_ready_c05_other_in_progress_no_go(monkeypatch):
    """#9 C0.5 in_progress=["W10-099"] + unspecified → NO-GO (其他 ticket 未完成)."""
    state = _make_state(
        current_phase="0.5", in_progress_tickets=["W10-099"], ready_for_clear=False,
    )
    rc, _, _ = _run_handoff_ready(monkeypatch, state)
    assert rc == 2


def test_handoff_ready_c05_self_in_progress_returns_go(monkeypatch):
    """#10 C0.5 in_progress=["W10-017.1"] + specified self → GO (自身視為正常推進)."""
    state = _make_state(
        current_phase="0.5",
        in_progress_tickets=["W10-017.1"],
        ready_for_clear=True,
        ticket_id="W10-017.1",
    )
    rc, out, _ = _run_handoff_ready(monkeypatch, state, ticket_id="W10-017.1")
    assert rc == 0


# ---------------------------------------------------------------------------
# H11-H15: 補強測試（exit code 1 / fail-open / argparse / caller）
# ---------------------------------------------------------------------------


def test_H11_handoff_ready_internal_error_returns_exit_1(monkeypatch):
    """H11: 非 IO_ERRORS (RuntimeError) → exit 1 + stderr."""
    rc, _, err = _run_handoff_ready(monkeypatch, RuntimeError("boom"))
    assert rc == 1
    assert "internal error" in err.lower() or "boom" in err


def test_H12_handoff_ready_io_error_fail_open_displays_degraded(monkeypatch):
    """H12: IO_ERRORS (OSError) → fail-open（v2.1 §3.5）.

    AD-2: 本 Phase 3a 暫定 exit 2 (保守)；待 PM 答覆 Q5 確認.
    """
    rc, out, err = _run_handoff_ready(monkeypatch, OSError("disk fail"))
    # 接受 exit 2 (保守 NO-GO)；不接受 exit 1（IO_ERRORS 非 internal error）
    assert rc in (0, 2), f"Expected 0 or 2 (fail-open), got {rc}"
    # stderr 或 stdout 應提示「資料源異常」
    combined = out + err
    assert "資料源" in combined or "data source" in combined.lower()


def test_H13_handoff_ready_argparse_uses_ticket_id_flag():
    """H13: argparse `handoff-ready --ticket-id W10-017.1` → namespace.ticket_id 正確."""
    from ticket_system.commands.track_handoff_ready import register_handoff_ready

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation")
    register_handoff_ready(subparsers)
    ns = parser.parse_args(["handoff-ready", "--ticket-id", "W10-017.1"])
    assert ns.operation == "handoff-ready"
    assert ns.ticket_id == "W10-017.1"


def test_H14_handoff_ready_argparse_no_ticket_id_optional():
    """H14: argparse `handoff-ready`（無 ticket-id）→ namespace.ticket_id is None."""
    from ticket_system.commands.track_handoff_ready import register_handoff_ready

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation")
    register_handoff_ready(subparsers)
    ns = parser.parse_args(["handoff-ready"])
    assert ns.ticket_id is None


def test_H15_handoff_ready_calls_checkpoint_state_with_caller_handoff_ready(
    monkeypatch,
):
    """H15: execute_handoff_ready 呼叫 checkpoint_state 時 caller="handoff-ready"."""
    state = _make_state()
    spy_calls: list = []
    _run_handoff_ready(monkeypatch, state, spy_calls=spy_calls)
    assert len(spy_calls) >= 1
    # 驗證 caller 參數
    callers = [c["kwargs"].get("caller") for c in spy_calls]
    assert "handoff-ready" in callers, f"Expected caller='handoff-ready', got {callers}"
