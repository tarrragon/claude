"""0.4.1-W2-009: infer_next_tdd_phase 單元測試（純邏輯，不觸碰 registry.yaml I/O）。

測試覆蓋:
1. agent 無 tdd_phases 對應 -> None
2. 單一 phase agent + 無 tdd_stage -> 直接採用該 phase
3. 多 phase agent + 無 tdd_stage -> 無法判斷順序 -> None
4. 有 tdd_stage：從序列開頭找 agent 對應的最早 phase
5. 有 tdd_stage 且 ticket 目前 tdd_phase 已推進：從該位置（含）起找最早未完成 phase
6. 目前 tdd_phase 不在 tdd_stage 中（資料異常）：從頭開始找
7. agent 對應的 phase 都在目前位置之前（已無未完成對應）-> None
"""
from __future__ import annotations

import pytest

from ticket_system.lib import tdd_phase_inference


@pytest.fixture
def patch_agent_phases(monkeypatch):
    """以 dict 取代 registry I/O，測試只關心 phase 選擇邏輯。"""

    def _apply(mapping: dict) -> None:
        monkeypatch.setattr(
            tdd_phase_inference,
            "_load_agent_tdd_phases",
            lambda agent: list(mapping.get(agent, [])),
        )

    return _apply


def test_agent_without_mapping_returns_none(patch_agent_phases):
    patch_agent_phases({})
    ticket = {"tdd_stage": ["phase1", "phase2"], "tdd_phase": "phase1"}
    assert tdd_phase_inference.infer_next_tdd_phase(ticket, "unknown-agent") is None


def test_single_phase_agent_without_tdd_stage_adopts_directly(patch_agent_phases):
    patch_agent_phases({"fennel-go-developer": ["phase3b"]})
    ticket = {}
    result = tdd_phase_inference.infer_next_tdd_phase(ticket, "fennel-go-developer")
    assert result == "phase3b"


def test_multi_phase_agent_without_tdd_stage_gives_up(patch_agent_phases):
    patch_agent_phases({"multi-phase-agent": ["phase3a", "phase3b"]})
    ticket = {}
    result = tdd_phase_inference.infer_next_tdd_phase(ticket, "multi-phase-agent")
    assert result is None


def test_earliest_matching_phase_from_start_of_stage(patch_agent_phases):
    patch_agent_phases({"fennel-go-developer": ["phase3b"]})
    ticket = {
        "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b", "phase4"],
        "tdd_phase": "phase1",
    }
    result = tdd_phase_inference.infer_next_tdd_phase(ticket, "fennel-go-developer")
    assert result == "phase3b"


def test_earliest_unfinished_phase_from_current_position(patch_agent_phases):
    """多 phase agent：從目前 tdd_phase 位置（含）起找最早對應 phase。"""
    patch_agent_phases({"multi-phase-agent": ["phase1", "phase3b"]})
    ticket = {
        "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b", "phase4"],
        "tdd_phase": "phase2",
    }
    result = tdd_phase_inference.infer_next_tdd_phase(ticket, "multi-phase-agent")
    # phase1 在 phase2 之前，已略過；下一個對應為 phase3b
    assert result == "phase3b"


def test_current_phase_not_in_stage_starts_from_beginning(patch_agent_phases):
    patch_agent_phases({"fennel-go-developer": ["phase3b"]})
    ticket = {
        "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b", "phase4"],
        "tdd_phase": "unrecognized-phase",
    }
    result = tdd_phase_inference.infer_next_tdd_phase(ticket, "fennel-go-developer")
    assert result == "phase3b"


def test_no_remaining_matching_phase_returns_none(patch_agent_phases):
    patch_agent_phases({"lavender-interface-designer": ["phase1"]})
    ticket = {
        "tdd_stage": ["phase1", "phase2", "phase3a", "phase3b", "phase4"],
        "tdd_phase": "phase3b",
    }
    result = tdd_phase_inference.infer_next_tdd_phase(
        ticket, "lavender-interface-designer"
    )
    assert result is None
