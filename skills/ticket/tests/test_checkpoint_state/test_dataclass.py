"""Group A：CheckpointState / PendingCheck dataclass 建構測試。

對應 Phase 2 §3 Group A（A1-A5）與 AC1。
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from ticket_system.lib.checkpoint_state import (
    CheckpointState,
    PendingCheck,
    format_phase_label,
)


def _make_state(**overrides) -> CheckpointState:
    """建構最小合法 CheckpointState，測試可 override 欄位。"""
    defaults = dict(
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
    defaults.update(overrides)
    return CheckpointState(**defaults)


# A1 正常：合法欄位 + 空 pending_checks → 可讀 + computed_at ISO 格式
def test_A1_normal_construction_all_fields_readable():
    state = _make_state()
    # 所有欄位皆可讀
    assert state.current_phase == "3"
    # phase_label 改由 view function 產生（L10 重構）
    assert format_phase_label(state).startswith("C3")
    assert state.pending_checks == []
    # computed_at 為 ISO 8601 格式（至少含 'T' 與日期-時間）
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", state.computed_at)


# A2 正常：3 個 PendingCheck（auto_detectable 混合）→ frozen
def test_A2_pending_checks_frozen_and_mixed():
    checks = [
        PendingCheck(check_id="c1", reason="r1", blocker=True, auto_detectable=True),
        PendingCheck(check_id="c2", reason="r2", blocker=False, auto_detectable=False),
        PendingCheck(check_id="c3", reason="r3", blocker=False, auto_detectable=True),
    ]
    state = _make_state(pending_checks=checks)
    assert len(state.pending_checks) == 3
    # PendingCheck 為 frozen，寫入應拋 FrozenInstanceError
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.pending_checks[0].check_id = "mutated"  # type: ignore[misc]


# A3 邊界：全空 list 欄位 → 仍可建構，ready_for_clear 可讀
def test_A3_all_empty_lists_constructible():
    state = _make_state(
        pending_checks=[],
        unmerged_worktrees=[],
        in_progress_tickets=[],
        data_sources={},
    )
    # ready_for_clear 已是 bool，可直接讀
    assert isinstance(state.ready_for_clear, bool)


# A4 邊界：dataclasses.fields() 計數 >= 12（AC1 判定）
def test_A4_dataclass_fields_count_meets_AC1():
    public_fields = [
        f for f in dataclasses.fields(CheckpointState) if not f.name.startswith("_")
    ]
    # L10 重構後 phase_label / next_action 改為 view function，
    # 公開欄位由 12 降為 10（純 state，不含 view 字串）。
    assert len(public_fields) >= 10, (
        f"公開欄位 >= 10，實際 {len(public_fields)}："
        f"{[f.name for f in public_fields]}"
    )


# A5 異常：必填欄位缺失 → TypeError
def test_A5_missing_required_field_raises_typeerror():
    with pytest.raises(TypeError):
        # 刻意少傳必填欄位（pending_checks / data_sources 等）
        CheckpointState(  # type: ignore[call-arg]
            current_phase="3",
            ready_for_clear=True,
        )


# 補充：PendingCheck frozen 性獨立驗證
def test_pending_check_is_frozen():
    c = PendingCheck(check_id="x", reason="y", blocker=False, auto_detectable=False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.check_id = "z"  # type: ignore[misc]
