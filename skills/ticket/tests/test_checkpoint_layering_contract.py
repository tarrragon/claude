"""W10-017.12 AC5：view / state / command 分層契約回歸測試。

目的：防止 Phase 4b P1 重構後的分層邊界回歸。本測試檔專注於
「誰在哪一層」的結構性契約，而非單純邏輯覆蓋（已由 test_checkpoint_state/
test_checkpoint_view.py 覆蓋）。

契約（三條）：
    C1. compute_blockers 必位於 lib/checkpoint_view.py，不在 commands 層。
        commands/track_handoff_ready.py 禁止定義業務判定函式（_compute_blockers
        / _Blocker），僅可 consume lib 結果。
    C2. PRIORITIES / FALLBACK 元素必為具名欄位結構（PriorityRule /
        FallbackRule NamedTuple），禁止匿名 5-tuple 退化。
    C3. _derive_checkpoint 與 get_suggested_commands 必共用 _resolve_rule 單次
        PRIORITIES loop，禁止兩個函式獨立掃描 PRIORITIES（DRY 回歸防護）。
"""

from __future__ import annotations

import inspect

from ticket_system.commands import track_handoff_ready
from ticket_system.lib import checkpoint_state, checkpoint_view


# ---------------------------------------------------------------------------
# C1：compute_blockers 分層契約
# ---------------------------------------------------------------------------


def test_C1_compute_blockers_defined_in_lib_view():
    """compute_blockers 與 Blocker 必位於 lib/checkpoint_view。"""
    assert hasattr(checkpoint_view, "compute_blockers")
    assert hasattr(checkpoint_view, "Blocker")
    assert callable(checkpoint_view.compute_blockers)


def test_C1_commands_layer_has_no_blocker_business_logic():
    """commands/track_handoff_ready 禁止定義 _compute_blockers / _Blocker。

    重構原則：業務判定（哪些狀態算阻擋）應集中 lib 層，commands 層僅消費並
    決定 exit code。若未來有人誤把邏輯下放回 commands 會被本測試攔截。
    """
    src = inspect.getsource(track_handoff_ready)
    assert "def _compute_blockers" not in src, (
        "_compute_blockers 應上移 lib/checkpoint_view.compute_blockers（AC1 契約）"
    )
    assert "class _Blocker" not in src, (
        "_Blocker 應上移 lib/checkpoint_view.Blocker（AC1 契約）"
    )


def test_C1_commands_layer_imports_from_lib():
    """commands/track_handoff_ready 必 import compute_blockers + Blocker from lib。"""
    src = inspect.getsource(track_handoff_ready)
    assert "compute_blockers" in src, "commands 層必須 import compute_blockers"
    assert "Blocker" in src, "commands 層必須 import Blocker"


# ---------------------------------------------------------------------------
# C2：PRIORITIES / FALLBACK 具名欄位契約
# ---------------------------------------------------------------------------


def test_C2_priorities_elements_are_named_tuples():
    """PRIORITIES 元素必為 PriorityRule NamedTuple 而非匿名 tuple。"""
    assert len(checkpoint_state.PRIORITIES) > 0
    for rule in checkpoint_state.PRIORITIES:
        assert isinstance(rule, checkpoint_state.PriorityRule), (
            f"PRIORITIES 元素必為 PriorityRule，實得 {type(rule).__name__}"
        )
        # 必備具名欄位（AC2 契約）
        assert hasattr(rule, "predicate")
        assert hasattr(rule, "phase")
        assert hasattr(rule, "label")
        assert hasattr(rule, "action_fn")
        assert hasattr(rule, "commands_fn")


def test_C2_fallback_is_named_tuple():
    """FALLBACK 必為 FallbackRule NamedTuple 而非匿名 tuple。"""
    assert isinstance(checkpoint_state.FALLBACK, checkpoint_state.FallbackRule)
    # 必備具名欄位
    fb = checkpoint_state.FALLBACK
    assert hasattr(fb, "phase")
    assert hasattr(fb, "label")
    assert hasattr(fb, "action_fn")
    assert hasattr(fb, "commands_fn")


# ---------------------------------------------------------------------------
# C3：_resolve_rule 單源契約（DRY 回歸防護）
# ---------------------------------------------------------------------------


def test_C3_resolve_rule_is_single_source():
    """_resolve_rule 必存在，且為 _derive_checkpoint / get_suggested_commands 共用源。

    重構目標：避免兩個函式各自掃描 PRIORITIES（原本 _derive_checkpoint 掃一次、
    get_suggested_commands 掃一次）。現在兩者都經 _resolve_rule 單次 loop。
    """
    assert hasattr(checkpoint_state, "_resolve_rule")
    assert callable(checkpoint_state._resolve_rule)

    derive_src = inspect.getsource(checkpoint_state._derive_checkpoint)
    cmds_src = inspect.getsource(checkpoint_view.get_suggested_commands)

    assert "_resolve_rule" in derive_src, (
        "_derive_checkpoint 必委派 _resolve_rule（AC3 契約）"
    )
    assert "_resolve_rule" in cmds_src, (
        "get_suggested_commands 必委派 _resolve_rule（AC3 契約）"
    )

    # 額外保險：兩者都不應再直接寫 `for ... in PRIORITIES`（獨立掃描）
    assert "in PRIORITIES" not in cmds_src, (
        "get_suggested_commands 不得再獨立掃描 PRIORITIES（應走 _resolve_rule）"
    )


def test_C3_resolve_rule_behavior_consistent_with_derive_and_commands():
    """_resolve_rule 回傳的 (phase, label, action, commands) 必與兩個舊 API 一致。

    行為契約：確保委派重構不改變對外觀察到的推導結果。
    """
    state = checkpoint_state.CheckpointState(
        current_phase="",
        ready_for_clear=False,
        pending_checks=[],
        active_agents=2,  # 命中 C1.85 代理人運行中
        unmerged_worktrees=[],
        active_handoff=None,
        in_progress_tickets=[],
        data_sources={},
        computed_at="2026-04-19T00:00:00+00:00",
        uncommitted_files=0,
    )

    phase, label, action, commands = checkpoint_state._resolve_rule(state)
    d_phase, d_label, d_action = checkpoint_state._derive_checkpoint(state)

    assert (phase, label, action) == (d_phase, d_label, d_action)

    # current_phase 需設成一致才能讓 get_suggested_commands 語意有效
    state.current_phase = phase
    assert checkpoint_view.get_suggested_commands(state) == commands
    assert commands == ["ticket track agent-status"]


def test_C3_resolve_rule_fallback_path():
    """PRIORITIES 全數未命中時必落入 FALLBACK 的 phase/label/action/commands。"""
    state = checkpoint_state.CheckpointState(
        current_phase="",
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

    phase, label, action, commands = checkpoint_state._resolve_rule(state)
    assert phase == checkpoint_state.FALLBACK.phase
    assert label == checkpoint_state.FALLBACK.label
    assert action == checkpoint_state.FALLBACK.action_fn(state)
    assert commands == checkpoint_state.FALLBACK.commands_fn(state)
