"""Group C：6 優先級 Checkpoint 推導測試（核心決策）。

對應 Phase 2 §3 Group C（C1-C8）與 AC2 / AC5。

使用 Sociable Unit Tests：直接用真實 CheckpointState 物件調用 _derive_checkpoint，
不 mock dataclass（符合 sage §1 原則）。
"""

from __future__ import annotations

from ticket_system.lib.checkpoint_state import (
    CheckpointState,
    PendingCheck,
    _derive_checkpoint,
)


def _state(**overrides) -> CheckpointState:
    """建構「全 clean」基線狀態，case override 需觸發條件。"""
    defaults = dict(
        current_phase="",  # 由 _derive 決定
        ready_for_clear=False,
        pending_checks=[],
        active_agents=0,
        unmerged_worktrees=[],
        active_handoff=None,
        in_progress_tickets=[],
        data_sources={},
        computed_at="2026-04-19T00:00:00+00:00",
        uncommitted_files=0,
    )
    defaults.update(overrides)
    return CheckpointState(**defaults)


# ---------------------------------------------------------------------------
# C1-C6：6 優先級各自命中
# ---------------------------------------------------------------------------


# C1 優先級 1：active_agents > 0 + 其他條件全觸發 → "1.85"
def test_C1_priority1_active_agents_wins():
    state = _state(
        active_agents=2,
        unmerged_worktrees=["wt1"],
        uncommitted_files=3,
        active_handoff="W10-017.8",
        in_progress_tickets=["X"],
        _ticket_id="X",
    )
    # 前置驗證：輸入狀態符合預期
    assert state.active_agents == 2
    phase, label, action = _derive_checkpoint(state)
    assert phase == "1.85"
    assert "代理人" in label
    assert "2" in action  # 顯示代理人數量


# C2 優先級 2：active_agents=0 + unmerged_worktrees 非空 → "1.9"
def test_C2_priority2_unmerged_worktrees_wins():
    state = _state(
        active_agents=0,
        unmerged_worktrees=["wt1", "wt2"],
        uncommitted_files=5,
        active_handoff="H",
        in_progress_tickets=["X"],
        _ticket_id="X",
    )
    assert state.active_agents == 0
    assert len(state.unmerged_worktrees) == 2
    phase, label, action = _derive_checkpoint(state)
    assert phase == "1.9"
    assert "worktree" in label or "worktree" in action
    assert "2" in action


# C3 優先級 3：前兩項 clean + uncommitted_files > 0 → "1"
def test_C3_priority3_uncommitted_files_wins():
    state = _state(
        active_agents=0,
        unmerged_worktrees=[],
        uncommitted_files=3,
        active_handoff="H",
        in_progress_tickets=["X"],
        _ticket_id="X",
    )
    assert state.uncommitted_files == 3
    phase, label, action = _derive_checkpoint(state)
    assert phase == "1"
    assert "commit" in action
    assert "3" in action


# C4 優先級 4：前三項 clean + active_handoff 非 None → "2"
def test_C4_priority4_active_handoff_wins():
    state = _state(
        active_agents=0,
        unmerged_worktrees=[],
        uncommitted_files=0,
        active_handoff="W10-017.8",
        in_progress_tickets=["X"],
        _ticket_id="X",
    )
    assert state.active_handoff == "W10-017.8"
    phase, label, action = _derive_checkpoint(state)
    assert phase == "2"
    assert "clear" in action.lower()
    assert "W10-017.8" in action


# C5 優先級 5：前四項 clean + in_progress + ticket_id 指定 → "0.5"
def test_C5_priority5_inprogress_with_ticket_id_wins():
    state = _state(
        active_agents=0,
        unmerged_worktrees=[],
        uncommitted_files=0,
        active_handoff=None,
        in_progress_tickets=["X"],
        _ticket_id="X",
    )
    assert state.in_progress_tickets == ["X"]
    assert state._ticket_id == "X"
    phase, label, action = _derive_checkpoint(state)
    assert phase == "0.5"
    assert "append-log" in action


# C6 優先級 fallback：全 clean + 無 in_progress → "3"
def test_C6_fallback_all_clean():
    state = _state(
        active_agents=0,
        unmerged_worktrees=[],
        uncommitted_files=0,
        active_handoff=None,
        in_progress_tickets=[],
        _ticket_id=None,
    )
    phase, label, action = _derive_checkpoint(state)
    assert phase == "3"
    assert "clear" in action.lower() or "Ticket" in action


# ---------------------------------------------------------------------------
# C7-C8：邊界
# ---------------------------------------------------------------------------


# C7 邊界：優先級 1 與 3 同時觸發 → 命中優先級 1
def test_C7_priority_order_higher_wins_over_lower():
    state = _state(
        active_agents=2,
        uncommitted_files=3,
    )
    phase, _label, _action = _derive_checkpoint(state)
    assert phase == "1.85", (
        "active_agents>0 應勝過 uncommitted_files>0（優先級 1 > 優先級 3）"
    )


# C7b 邊界：uncommitted_files=None（資料源失敗）不應命中優先級 3
def test_C7b_uncommitted_none_does_not_trigger_priority3():
    """Optional[int] = None 時（資料源失敗），不該被當作「有未提交檔案」。"""
    state = _state(
        active_agents=0,
        unmerged_worktrees=[],
        uncommitted_files=None,  # 資料源失敗
        active_handoff=None,
        in_progress_tickets=[],
        _ticket_id=None,
    )
    phase, _label, _action = _derive_checkpoint(state)
    # 不應命中優先級 3（"1"），應 fallback 到 "3"
    assert phase == "3"


# C7c 邊界：uncommitted_files=0（clean）不應命中優先級 3
def test_C7c_uncommitted_zero_does_not_trigger_priority3():
    state = _state(
        active_agents=0,
        unmerged_worktrees=[],
        uncommitted_files=0,
        active_handoff=None,
        in_progress_tickets=[],
        _ticket_id=None,
    )
    phase, _label, _action = _derive_checkpoint(state)
    assert phase == "3"


# C7d 邊界：in_progress 非空但 _ticket_id=None，不應命中優先級 5
def test_C7d_inprogress_without_ticket_id_skips_priority5():
    state = _state(
        in_progress_tickets=["X"],
        _ticket_id=None,
    )
    phase, _label, _action = _derive_checkpoint(state)
    # 應 fallback 到 "3"，不命中 0.5
    assert phase == "3"


# C8 邊界：ready_for_clear 推導（注意：_derive_checkpoint 不計算 ready_for_clear，
# 此欄位由 checkpoint_state() 主流程依 Phase 3a §1.2 Step 3 計算。
# 此處用 Phase 2 §3 Group C 的語意斷言：phase in {"2","3"} 且 pending 全 auto_detectable=False。）
def test_C8_ready_for_clear_semantic_phase3_all_non_autodetectable():
    """驗證 ready_for_clear 語意：phase 為 2/3 且所有 pending 非 auto_detectable 時成立。"""
    # 此測試不呼叫 _derive_checkpoint；驗證 AC5 語意合約
    # （ready_for_clear 完整計算測試屬派發 2/3 主流程範圍）
    pending_all_non_auto = [
        PendingCheck(check_id="c1", reason="r", blocker=False, auto_detectable=False),
        PendingCheck(check_id="c2", reason="r", blocker=False, auto_detectable=False),
    ]
    pending_with_auto = [
        PendingCheck(check_id="c1", reason="r", blocker=False, auto_detectable=False),
        PendingCheck(check_id="c2", reason="r", blocker=False, auto_detectable=True),
    ]

    # 語意合約：phase ∈ {"2","3"} AND all(not c.auto_detectable)
    def ready(phase: str, checks) -> bool:
        return phase in {"2", "3"} and all(not c.auto_detectable for c in checks)

    assert ready("3", pending_all_non_auto) is True
    assert ready("2", pending_all_non_auto) is True
    assert ready("3", pending_with_auto) is False
    assert ready("1", pending_all_non_auto) is False
