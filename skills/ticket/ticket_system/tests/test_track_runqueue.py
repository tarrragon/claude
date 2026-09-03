"""Tests for ticket_system/commands/track_runqueue.py (W17-020).

聚焦 _render_list 在 context=resume 過濾為空時的訊息分支。
"""

from __future__ import annotations

import re
from typing import Dict, List

import pytest

from ticket_system.commands import track_runqueue
from ticket_system.lib.paths import get_project_root


def _read_hook_empty_marker() -> str:
    """讀取 session-start-scheduler-hint-hook.py 的 EMPTY_MARKER 常數值。

    hook 為 PEP 723 單檔腳本無法被 import，故以讀檔 + 正規表示式解析取其
    常數值，不在測試中硬編複本——hook 端若改變該常數，本函式回傳值同步
    改變，任一處單獨修改即使比對測試紅燈。
    """
    hook_path = (
        get_project_root()
        / ".claude"
        / "hooks"
        / "session-start-scheduler-hint-hook.py"
    )
    source = hook_path.read_text(encoding="utf-8")
    match = re.search(r'^EMPTY_MARKER = "([^"]+)"', source, re.MULTILINE)
    assert match, "session-start-scheduler-hint-hook.py 未找到 EMPTY_MARKER 常數定義"
    return match.group(1)


def _mk(tid: str, status: str = "pending", blocked=None, priority: str = "P2",
        wave: int = 17) -> Dict:
    return {
        "id": tid,
        "status": status,
        "blockedBy": blocked or [],
        "priority": priority,
        "wave": wave,
        "title": f"title-{tid}",
    }


# ---------------------------------------------------------------------------
# _render_list context 分支
# ---------------------------------------------------------------------------

def test_render_list_empty_default_context_shows_blocked_message():
    out = track_runqueue._render_list([], top=None, wave=None, context=None)
    assert "blockedBy 全非空或 status 非 pending" in out
    assert "無 resume 候選" not in out


def test_render_list_empty_resume_context_shows_handoff_message():
    out = track_runqueue._render_list(
        [], top=None, wave=None, context="resume"
    )
    assert "無 resume 候選" in out
    assert "handoff pending" in out
    assert "blockedBy 全非空" not in out


def test_render_list_empty_resume_with_filtered_tickets_shows_resume_message():
    """有 ticket 但全被 resume 過濾掉（實務上 _apply_context_resume 已回傳 []）。"""
    out = track_runqueue._render_list(
        [], top=None, wave=None, context="resume"
    )
    assert "無 resume 候選" in out


def test_render_list_non_empty_ignores_context():
    tickets = [_mk("0.18.0-W17-001", priority="P1")]
    out = track_runqueue._render_list(
        tickets, top=None, wave=None, context="resume"
    )
    assert "0.18.0-W17-001" in out
    assert "無 resume 候選" not in out


# ---------------------------------------------------------------------------
# execute_runqueue 端對端：context=resume 無 handoff pending
# ---------------------------------------------------------------------------

def test_execute_runqueue_resume_no_handoff_pending(monkeypatch, capsys):
    import argparse

    tickets = [_mk("0.18.0-W17-001"), _mk("0.18.0-W17-002")]
    monkeypatch.setattr(
        track_runqueue, "list_tickets", lambda version: tickets
    )
    monkeypatch.setattr(
        track_runqueue, "_get_pending_handoff_info", lambda: {}
    )

    ns = argparse.Namespace(
        format="list", top=None, context="resume", wave=None,
    )
    rc = track_runqueue.execute_runqueue(ns, "0.18.0")
    assert rc == 0
    out = capsys.readouterr().out
    assert "無 resume 候選" in out
    assert "handoff pending" in out


def test_execute_runqueue_no_context_empty_uses_default_message(
    monkeypatch, capsys
):
    import argparse

    # 所有 ticket 都 blocked
    tickets = [_mk("0.18.0-W17-001", blocked=["x"])]
    monkeypatch.setattr(
        track_runqueue, "list_tickets", lambda version: tickets
    )

    ns = argparse.Namespace(
        format="list", top=None, context=None, wave=None,
    )
    rc = track_runqueue.execute_runqueue(ns, "0.18.0")
    assert rc == 0
    out = capsys.readouterr().out
    assert "blockedBy 全非空或 status 非 pending" in out
    assert "無 resume 候選" not in out


# ---------------------------------------------------------------------------
# W17-146: _apply_context_resume 解析 direction 取出 target
# ---------------------------------------------------------------------------

def _apply_with_handoff(monkeypatch, tickets, handoff_info):
    monkeypatch.setattr(
        track_runqueue, "_get_pending_handoff_info", lambda: handoff_info
    )
    return track_runqueue._apply_context_resume(tickets, "resume")


def test_apply_context_resume_to_sibling_with_target(monkeypatch):
    """T1: to-sibling:T → 候選含 T（target），不含 source。"""
    tickets = [
        _mk("0.18.0-W17-110.1", status="completed"),
        _mk("0.18.0-W17-110.3", status="pending"),
    ]
    handoff = {
        "0.18.0-W17-110.1": {
            "ticket_id": "0.18.0-W17-110.1",
            "direction": "to-sibling:0.18.0-W17-110.3",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    ids = {t["id"] for t in out}
    assert "0.18.0-W17-110.3" in ids


def test_apply_context_resume_to_parent_with_target(monkeypatch):
    """T2: to-parent:T → 候選含 T。"""
    tickets = [
        _mk("0.18.0-W17-200", status="pending"),
    ]
    handoff = {
        "0.18.0-W17-200.1": {
            "ticket_id": "0.18.0-W17-200.1",
            "direction": "to-parent:0.18.0-W17-200",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-200"}


def test_apply_context_resume_to_child_with_target(monkeypatch):
    """T3: to-child:T → 候選含 T。"""
    tickets = [
        _mk("0.18.0-W17-300.1", status="pending"),
    ]
    handoff = {
        "0.18.0-W17-300": {
            "ticket_id": "0.18.0-W17-300",
            "direction": "to-child:0.18.0-W17-300.1",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-300.1"}


def test_apply_context_resume_context_refresh_uses_source(monkeypatch):
    """T4: context-refresh → 候選為 source ticket_id。"""
    tickets = [
        _mk("0.18.0-W17-400", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-400": {
            "ticket_id": "0.18.0-W17-400",
            "direction": "context-refresh",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-400"}


def test_apply_context_resume_next_wave_uses_source(monkeypatch):
    """T5: next-wave → 候選為 source ticket_id。"""
    tickets = [
        _mk("0.18.0-W17-500", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-500": {
            "ticket_id": "0.18.0-W17-500",
            "direction": "next-wave",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-500"}


def test_apply_context_resume_empty_direction_falls_back_to_source(monkeypatch):
    """T6 邊界: direction 空字串 → fallback 到 source ticket_id，不 crash。"""
    tickets = [
        _mk("0.18.0-W17-600", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-600": {
            "ticket_id": "0.18.0-W17-600",
            "direction": "",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-600"}


def test_apply_context_resume_unknown_direction_falls_back_to_source(monkeypatch):
    """T7 邊界: direction 格式錯誤 → fallback 到 source ticket_id。"""
    tickets = [
        _mk("0.18.0-W17-700", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-700": {
            "ticket_id": "0.18.0-W17-700",
            "direction": "foobar",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-700"}


def test_apply_context_resume_task_chain_no_target_falls_back(monkeypatch):
    """to-sibling 無 :target → fallback source ticket_id。"""
    tickets = [
        _mk("0.18.0-W17-800", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-800": {
            "ticket_id": "0.18.0-W17-800",
            "direction": "to-sibling",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-800"}


# ---------------------------------------------------------------------------
# W6-022: _apply_context_resume 優先讀 target_ticket_id（W17-164 絕對指向）
# ---------------------------------------------------------------------------

def test_apply_context_resume_context_refresh_with_target_ticket_id(monkeypatch):
    """W6-022 regression: direction=context-refresh + target_ticket_id 存在
    → 候選為 target，而非 source（避免 completed source 被 _is_listable 濾掉）。
    """
    tickets = [
        _mk("0.18.0-W6-012", status="completed"),
        _mk("0.18.0-W13-001", status="pending"),
    ]
    handoff = {
        "0.18.0-W6-012": {
            "ticket_id": "0.18.0-W6-012",
            "direction": "context-refresh",
            "target_ticket_id": "0.18.0-W13-001",
            "from_status": "completed",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W13-001"}


def test_apply_context_resume_target_ticket_id_overrides_direction(monkeypatch):
    """W6-022: target_ticket_id 優先於 direction 解析（即使 direction 為任務鏈格式）。"""
    tickets = [
        _mk("0.18.0-W17-901", status="pending"),
        _mk("0.18.0-W17-902", status="pending"),
    ]
    handoff = {
        "0.18.0-W17-900": {
            "ticket_id": "0.18.0-W17-900",
            "direction": "to-sibling:0.18.0-W17-901",
            "target_ticket_id": "0.18.0-W17-902",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-902"}


def test_apply_context_resume_empty_target_ticket_id_falls_back(monkeypatch):
    """W6-022 邊界: target_ticket_id 為空字串 → fallback 既有 direction 邏輯。"""
    tickets = [
        _mk("0.18.0-W17-910", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-910": {
            "ticket_id": "0.18.0-W17-910",
            "direction": "context-refresh",
            "target_ticket_id": "",
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-910"}


def test_apply_context_resume_non_string_target_ticket_id_falls_back(monkeypatch):
    """W6-022 邊界: target_ticket_id 非字串 → fallback 既有 direction 邏輯。"""
    tickets = [
        _mk("0.18.0-W17-920", status="in_progress"),
    ]
    handoff = {
        "0.18.0-W17-920": {
            "ticket_id": "0.18.0-W17-920",
            "direction": "context-refresh",
            "target_ticket_id": None,
        }
    }
    out = _apply_with_handoff(monkeypatch, tickets, handoff)
    assert {t["id"] for t in out} == {"0.18.0-W17-920"}


# ---------------------------------------------------------------------------
# W6-022: cross-command 一致性（runqueue --context=resume vs resume --list）
# ---------------------------------------------------------------------------

def test_cross_command_consistency_context_refresh_target_ticket_id(monkeypatch):
    """W6-022: runqueue --context=resume 應呈現 resume --list 同樣的 target ticket。

    建構 fixture：source=completed + target=pending + direction=context-refresh
    + target_ticket_id 存在。
    - resume --list 直接列舉 handoff JSON，回傳 target_ticket_id 集合。
    - runqueue --context=resume 過 _apply_context_resume → 應回傳同樣的 target。
    兩者結果集必須相等（修復前不相等：runqueue 落 source 被 _is_listable 濾掉）。
    """
    tickets = [
        _mk("0.18.0-W6-012", status="completed"),
        _mk("0.18.0-W13-001", status="pending"),
    ]
    handoff = {
        "0.18.0-W6-012": {
            "ticket_id": "0.18.0-W6-012",
            "direction": "context-refresh",
            "target_ticket_id": "0.18.0-W13-001",
        }
    }

    # runqueue --context=resume 結果集
    runqueue_out = _apply_with_handoff(monkeypatch, tickets, handoff)
    runqueue_ids = {t["id"] for t in runqueue_out}

    # resume --list 等價結果集：handoff JSON 之 target_ticket_id（W17-164 語意）
    resume_list_ids = {
        info["target_ticket_id"]
        for info in handoff.values()
        if info.get("target_ticket_id")
    }

    assert runqueue_ids == resume_list_ids
    assert "0.18.0-W13-001" in runqueue_ids


# ---------------------------------------------------------------------------
# W1-020: 共用 is_fully_unblocked predicate（blocker completed 但 blockedBy 未清）
# ---------------------------------------------------------------------------

def test_is_unblocked_pending_blocker_completed_but_blockedby_not_cleared():
    """blocker 已 completed 但 blockedBy 欄位未清理 → 應視為 ready（W8-042 缺陷修復）。"""
    blocker = _mk("0.18.0-W1-001", status="completed")
    target = _mk("0.18.0-W1-002", status="pending", blocked=["0.18.0-W1-001"])
    ticket_map = {t["id"]: t for t in (blocker, target)}
    assert track_runqueue._is_unblocked_pending(target, ticket_map) is True


def test_is_unblocked_pending_blocker_closed_treated_as_resolved():
    """blocker closed 在 scheduler 場景（include_closed_as_resolved=True）視為已解除。"""
    blocker = _mk("0.18.0-W1-001", status="closed")
    target = _mk("0.18.0-W1-002", status="pending", blocked=["0.18.0-W1-001"])
    ticket_map = {t["id"]: t for t in (blocker, target)}
    assert track_runqueue._is_unblocked_pending(target, ticket_map) is True


def test_is_unblocked_pending_blocker_still_in_progress_stays_blocked():
    """blocker 仍 in_progress → 仍視為 blocked。"""
    blocker = _mk("0.18.0-W1-001", status="in_progress")
    target = _mk("0.18.0-W1-002", status="pending", blocked=["0.18.0-W1-001"])
    ticket_map = {t["id"]: t for t in (blocker, target)}
    assert track_runqueue._is_unblocked_pending(target, ticket_map) is False


def test_is_unblocked_pending_empty_blockedby_is_ready():
    target = _mk("0.18.0-W1-002", status="pending", blocked=[])
    ticket_map = {target["id"]: target}
    assert track_runqueue._is_unblocked_pending(target, ticket_map) is True


def test_is_unblocked_pending_non_pending_status_false():
    target = _mk("0.18.0-W1-002", status="in_progress", blocked=[])
    ticket_map = {target["id"]: target}
    assert track_runqueue._is_unblocked_pending(target, ticket_map) is False


def test_render_list_surfaces_ticket_with_completed_blocker_uncleared():
    """端到端：blocker completed + blockedBy 未清 → runqueue list 應列出 target。"""
    blocker = _mk("0.18.0-W1-001", status="completed", priority="P1")
    target = _mk("0.18.0-W1-002", status="pending", blocked=["0.18.0-W1-001"], priority="P1")
    out = track_runqueue._render_list(
        [blocker, target], top=None, wave=None, context=None
    )
    assert "0.18.0-W1-002" in out


# ---------------------------------------------------------------------------
# 0.2.1-W3-142: _unresolved_blockers + list 視圖後綴改由實查推導
# ---------------------------------------------------------------------------

_STALE_STARTED_AT = "2020-01-01T00:00:00"  # 遠早於 STALE_IN_PROGRESS_HOURS 門檻


def _mk_stale_in_progress(tid: str, blocked=None, priority: str = "P2") -> Dict:
    ticket = _mk(tid, status="in_progress", blocked=blocked, priority=priority)
    ticket["started_at"] = _STALE_STARTED_AT
    return ticket


def test_unresolved_blockers_empty_blockedby_returns_empty():
    target = _mk("0.18.0-W1-010", blocked=[])
    assert track_runqueue._unresolved_blockers(target, {target["id"]: target}) == []


def test_unresolved_blockers_all_resolved_returns_empty():
    """blocker 皆 completed/closed → 未解除清單為空（AND 語義同 is_fully_unblocked）。"""
    b1 = _mk("0.18.0-W1-011", status="completed")
    b2 = _mk("0.18.0-W1-012", status="closed")
    target = _mk("0.18.0-W1-013", blocked=["0.18.0-W1-011", "0.18.0-W1-012"])
    ticket_map = {t["id"]: t for t in (b1, b2, target)}
    assert track_runqueue._unresolved_blockers(target, ticket_map) == []


def test_unresolved_blockers_pending_blocker_included():
    """blocker 仍 pending → 出現在未解除清單中。"""
    blocker = _mk("0.18.0-W1-014", status="pending")
    target = _mk("0.18.0-W1-015", blocked=["0.18.0-W1-014"])
    ticket_map = {t["id"]: t for t in (blocker, target)}
    assert track_runqueue._unresolved_blockers(target, ticket_map) == ["0.18.0-W1-014"]


def test_unresolved_blockers_mixed_resolved_and_unresolved():
    """混合已解除與未解除 → 僅回傳未解除者，保留 blockedBy 原序。"""
    resolved = _mk("0.18.0-W1-016", status="completed")
    unresolved = _mk("0.18.0-W1-017", status="in_progress")
    target = _mk("0.18.0-W1-018", blocked=["0.18.0-W1-016", "0.18.0-W1-017"])
    ticket_map = {t["id"]: t for t in (resolved, unresolved, target)}
    assert track_runqueue._unresolved_blockers(target, ticket_map) == ["0.18.0-W1-017"]


def test_unresolved_blockers_missing_blocker_treated_as_unresolved():
    """blocker 在 ticket_map 中找不到（資料不一致）→ 保守視為未解除。"""
    target = _mk("0.18.0-W1-019", blocked=["0.18.0-W1-ghost"])
    ticket_map = {target["id"]: target}
    assert track_runqueue._unresolved_blockers(target, ticket_map) == ["0.18.0-W1-ghost"]


def test_unresolved_blockers_ticket_map_none_returns_literal_blockedby():
    """ticket_map 為 None 時無法查詢狀態，保守回傳字面 blockedBy。"""
    target = _mk("0.18.0-W1-020", blocked=["0.18.0-W1-021"])
    assert track_runqueue._unresolved_blockers(target, None) == ["0.18.0-W1-021"]


def test_render_list_stale_in_progress_with_unresolved_blocker_shows_real_ids():
    """acceptance #1：stale in_progress 且 blockedBy 未解除 → 顯示實際未解除 blocker，
    而非字面 blockedBy=[]。"""
    blocker = _mk("0.18.0-W1-030", status="pending")
    stale = _mk_stale_in_progress("0.18.0-W1-031", blocked=["0.18.0-W1-030"])
    out = track_runqueue._render_list(
        [blocker, stale], top=None, wave=None, context=None
    )
    assert "0.18.0-W1-031" in out
    assert "blockedBy=[0.18.0-W1-030]" in out
    # 該筆不得再顯示假造的「無阻擋」字面
    stale_line = next(line for line in out.splitlines() if "0.18.0-W1-031" in line)
    assert "blockedBy=[]" not in stale_line


def test_render_list_stale_in_progress_with_resolved_blocker_shows_empty():
    """stale in_progress 但 blocker 已解除 → 仍正確顯示 blockedBy=[]（非誤報）。"""
    blocker = _mk("0.18.0-W1-032", status="completed")
    stale = _mk_stale_in_progress("0.18.0-W1-033", blocked=["0.18.0-W1-032"])
    out = track_runqueue._render_list(
        [blocker, stale], top=None, wave=None, context=None
    )
    stale_line = next(line for line in out.splitlines() if "0.18.0-W1-033" in line)
    assert "blockedBy=[]" in stale_line


def test_render_list_unblocked_pending_unchanged_shows_empty():
    """acceptance #2：unblocked pending 顯示維持現狀（向後相容），不受本票變更影響。"""
    target = _mk("0.18.0-W1-034", status="pending", blocked=[])
    out = track_runqueue._render_list(
        [target], top=None, wave=None, context=None
    )
    stale_line = next(line for line in out.splitlines() if "0.18.0-W1-034" in line)
    assert "blockedBy=[]" in stale_line


def test_render_list_regression_case_w3_124_pattern():
    """acceptance #3 回歸案例：blockedBy=[<blocker>] 且 blocker 仍 pending 的 stale
    in_progress ticket（比照 0.2.1-W3-124 / 0.2.1-W3-130 樣態），list 視圖須顯示
    實際未解除 blocker 而非誤導性的 blockedBy=[]。"""
    blocker = _mk("0.2.1-W3-130", status="pending")
    stale_target = _mk_stale_in_progress("0.2.1-W3-124", blocked=["0.2.1-W3-130"])
    out = track_runqueue._render_list(
        [blocker, stale_target], top=None, wave=None, context=None
    )
    target_line = next(line for line in out.splitlines() if "0.2.1-W3-124" in line)
    assert "blockedBy=[0.2.1-W3-130]" in target_line
    assert "blockedBy=[]" not in target_line


# ---------------------------------------------------------------------------
# multi-PM 協調層 Phase 3：registry STALE session 持票 RECLAIMABLE_TAG
# ---------------------------------------------------------------------------


def test_render_list_marks_reclaimable_when_lease_reclaimable(monkeypatch):
    """is_lease_reclaimable 回傳 True 的票 → list 視圖顯示 [RECLAIMABLE] tag。"""
    stale = _mk_stale_in_progress("0.2.1-W3-500")
    monkeypatch.setattr(
        track_runqueue.lease, "load_registry_snapshot", lambda: ({}, object())
    )
    monkeypatch.setattr(
        track_runqueue.lease, "is_lease_reclaimable",
        lambda registry, ticket, pm_registry, now: ticket.get("id") == "0.2.1-W3-500",
    )

    out = track_runqueue._render_list([stale], top=None, wave=None, context=None)

    target_line = next(line for line in out.splitlines() if "0.2.1-W3-500" in line)
    assert f"[{track_runqueue.RECLAIMABLE_TAG}]" in target_line


def test_render_list_omits_reclaimable_tag_when_not_reclaimable(monkeypatch):
    """is_lease_reclaimable 回傳 False（如 registry 未追蹤 / session 仍 FRESH）
    → 不顯示 [RECLAIMABLE] tag。"""
    stale = _mk_stale_in_progress("0.2.1-W3-501")
    monkeypatch.setattr(
        track_runqueue.lease, "load_registry_snapshot", lambda: ({}, None)
    )
    monkeypatch.setattr(
        track_runqueue.lease, "is_lease_reclaimable",
        lambda registry, ticket, pm_registry, now: False,
    )

    out = track_runqueue._render_list([stale], top=None, wave=None, context=None)

    target_line = next(line for line in out.splitlines() if "0.2.1-W3-501" in line)
    assert f"[{track_runqueue.RECLAIMABLE_TAG}]" not in target_line


def test_render_list_reclaimable_and_stale_tags_coexist(monkeypatch):
    """STALE_TAG（票面自身時間戳）與 RECLAIMABLE_TAG（registry heartbeat）
    判準不同，可同時出現於同一列。"""
    stale = _mk_stale_in_progress("0.2.1-W3-502")
    monkeypatch.setattr(
        track_runqueue.lease, "load_registry_snapshot", lambda: ({}, object())
    )
    monkeypatch.setattr(
        track_runqueue.lease, "is_lease_reclaimable",
        lambda registry, ticket, pm_registry, now: True,
    )

    out = track_runqueue._render_list([stale], top=None, wave=None, context=None)

    target_line = next(line for line in out.splitlines() if "0.2.1-W3-502" in line)
    assert f"[{track_runqueue.STALE_TAG}]" in target_line
    assert f"[{track_runqueue.RECLAIMABLE_TAG}]" in target_line


def test_render_list_reclaimable_check_degrades_when_registry_unavailable(monkeypatch):
    """registry 不可用（非 git 環境等）時 load_registry_snapshot 回傳
    pm_registry=None，is_lease_reclaimable 對任何票一律回傳 False，不阻擋
    list 視圖輸出（降級路徑不拋例外）。"""
    stale = _mk_stale_in_progress("0.2.1-W3-503")
    monkeypatch.setattr(
        track_runqueue.lease, "load_registry_snapshot",
        lambda: ({"schema_version": 0, "sessions": {}}, None),
    )

    out = track_runqueue._render_list([stale], top=None, wave=None, context=None)

    assert "0.2.1-W3-503" in out
    target_line = next(line for line in out.splitlines() if "0.2.1-W3-503" in line)
    assert f"[{track_runqueue.RECLAIMABLE_TAG}]" not in target_line


def test_render_list_untracked_owner_in_progress_now_marks_reclaimable(monkeypatch):
    """0.2.1-W3-867 回歸案例：graceful SessionEnd 刪除 registry entry 後，
    `is_lease_reclaimable` 對 owner=None 一律回傳 True——stale in_progress
    票即使 registry 未追蹤仍應顯示 [RECLAIMABLE]（不再永久失去可接手標記，
    僅剩 24 小時 STALE_TAG 兜底）。"""
    stale = _mk_stale_in_progress("0.2.1-W3-504")
    monkeypatch.setattr(
        track_runqueue.lease, "load_registry_snapshot", lambda: ({}, object())
    )
    monkeypatch.setattr(
        track_runqueue.lease, "is_lease_reclaimable",
        lambda registry, ticket, pm_registry, now: True,  # owner=None 修復後語意
    )

    out = track_runqueue._render_list([stale], top=None, wave=None, context=None)

    target_line = next(line for line in out.splitlines() if "0.2.1-W3-504" in line)
    assert f"[{track_runqueue.RECLAIMABLE_TAG}]" in target_line


def test_render_list_pending_ticket_never_tagged_reclaimable_even_if_owner_none(
    monkeypatch,
):
    """守衛回歸案例（0.2.1-W3-873 收斂後）：status 守衛已收回
    `is_lease_reclaimable` 函式內，`_render_list` 不再自行判斷
    `status == "in_progress"`，改為信任函式的真實契約——pending 票（非
    in_progress）呼叫本函式一律回傳 False，不誤標 [RECLAIMABLE]。此處以
    貼近真實契約的 mock（依 ticket status 判斷）驗證，而非直接令 mock
    恆真（恆真會繞過本測試意在驗證的性質）。"""
    pending = _mk("0.2.1-W3-505", status="pending")
    monkeypatch.setattr(
        track_runqueue.lease, "load_registry_snapshot", lambda: ({}, object())
    )
    monkeypatch.setattr(
        track_runqueue.lease, "is_lease_reclaimable",
        lambda registry, ticket, pm_registry, now: ticket.get("status") == "in_progress",
    )

    out = track_runqueue._render_list([pending], top=None, wave=None, context=None)

    target_line = next(line for line in out.splitlines() if "0.2.1-W3-505" in line)
    assert f"[{track_runqueue.RECLAIMABLE_TAG}]" not in target_line


# ---------------------------------------------------------------------------
# multi-PM 協調層 Phase 3：runqueue --groups（父票設計要點 5）
# ---------------------------------------------------------------------------


def _mk_with_files(tid: str, files, priority: str = "P2", status: str = "pending",
                    blocked=None) -> Dict:
    ticket = _mk(tid, status=status, blocked=blocked, priority=priority)
    ticket["where"] = {"files": files}
    return ticket


class TestRenderGroups:
    def test_readiness_filter_matches_list_view(self):
        """`parallel_group` / `not_selected` 的候選節點集合仍與 list 視圖同
        （blockedBy=[] 且 pending）：仍有未解除 blocker 的票不進入群組判定。
        in_progress 票（無 `started_at`，`is_stale_in_progress` fail-open
        判為非 stale）改為以 seed 身份參與——因與任何 ready 票無 where.files
        交集，未排除任何節點，`occupied` 因此為空、不出現於輸出（見
        `test_in_progress_seed_excludes_conflicting_neighbor` 驗證有衝突時
        seed 會出現於 occupied 區塊）。"""
        ready = _mk_with_files("0.2.1-W3-600", ["lib/a.dart"])
        in_progress = _mk_with_files(
            "0.2.1-W3-601", ["lib/b.dart"], status="in_progress"
        )
        still_blocked = _mk_with_files(
            "0.2.1-W3-602", ["lib/c.dart"], blocked=["0.2.1-W3-999"]
        )

        out = track_runqueue._render_groups([ready, in_progress, still_blocked])

        assert "0.2.1-W3-600" in out
        assert "0.2.1-W3-601" not in out
        assert "0.2.1-W3-602" not in out

    def test_in_progress_seed_excludes_conflicting_neighbor(self):
        """live in_progress 票與某 ready 票有 where.files 交集時：該 ready
        票被排除出 `parallel_group`（併入 `not_selected`），in_progress 票
        本身不出現於 `parallel_group` 亦不出現於 `not_selected`，但因其
        衝突對出現於第三段，`occupied` 區塊須列出其 id 供讀者辨識排除來源
        （acceptance: 落選來源可解釋）。"""
        occupying = _mk_with_files(
            "0.2.1-W3-603", ["lib/shared.dart"], status="in_progress"
        )
        neighbor = _mk_with_files("0.2.1-W3-604", ["lib/shared.dart"])

        out = track_runqueue._render_groups([occupying, neighbor])

        assert "可並行群組（0 票" in out
        assert "0.2.1-W3-603" not in out.split("施工中佔用節點")[0]
        assert "- 0.2.1-W3-604" in out  # not_selected 段
        assert "施工中佔用節點" in out
        assert "- 0.2.1-W3-603" in out

    def test_stale_in_progress_not_seeded_neighbor_still_selectable(self):
        """stale in_progress 票（`started_at` 逾 24 小時前，
        `is_stale_in_progress` 判 True）不納入 seed：其鄰居票不因此被排除，
        與 `_is_listable` 對 stale in_progress「仍可列示接手」的判準一致，
        避免 list 視圖與 groups 視圖給出相反指引。"""
        stale = _mk_with_files(
            "0.2.1-W3-605", ["lib/shared.dart"], status="in_progress"
        )
        stale["started_at"] = "2000-01-01T00:00:00"
        neighbor = _mk_with_files("0.2.1-W3-606", ["lib/shared.dart"])

        out = track_runqueue._render_groups([stale, neighbor])

        assert "0.2.1-W3-606" in out
        assert "本輪未選入可並行集合（0 票" in out
        assert "施工中佔用節點" not in out

    def test_no_conflicts_all_in_parallel_group(self):
        a = _mk_with_files("0.2.1-W3-610", ["lib/a.dart"])
        b = _mk_with_files("0.2.1-W3-611", ["lib/b.dart"])

        out = track_runqueue._render_groups([a, b])

        assert "可並行群組" in out
        assert "0.2.1-W3-610" in out
        assert "0.2.1-W3-611" in out
        assert "本輪未選入可並行集合（0 票" in out

    def test_conflicting_pair_one_selected_one_deferred_with_conflict_pair_shown(self):
        """直接衝突的一對票：貪婪獨立集依輸入序選第一票入可並行群組，
        第二票落在本輪未選入清單；衝突對仍完整顯示供人工判讀。"""
        a = _mk_with_files("0.2.1-W3-620", ["lib/shared.dart"])
        b = _mk_with_files("0.2.1-W3-621", ["lib/shared.dart"])

        out = track_runqueue._render_groups([a, b])

        assert "- 0.2.1-W3-621" in out
        assert "0.2.1-W3-620 <-> 0.2.1-W3-621" in out
        assert "lib/shared.dart" in out

    def test_priority_ordering_preserved_into_parallel_group(self):
        """`_render_groups` 依 priority/type/id 排序後傳入
        `compute_parallel_groups`，parallel_group 應反映此排序（P0 優先）。"""
        low = _mk_with_files("0.2.1-W3-630", ["lib/x.dart"], priority="P3")
        high = _mk_with_files("0.2.1-W3-631", ["lib/y.dart"], priority="P0")

        out = track_runqueue._render_groups([low, high])

        idx_high = out.index("0.2.1-W3-631")
        idx_low = out.index("0.2.1-W3-630")
        assert idx_high < idx_low

    def test_empty_ready_set_shows_message(self):
        blocked = _mk_with_files(
            "0.2.1-W3-640", ["lib/x.dart"], blocked=["0.2.1-W3-999"]
        )

        out = track_runqueue._render_groups([blocked])

        assert "無可執行 Ticket" in out


class TestRenderRunqueueGroupsDispatch:
    def test_groups_flag_takes_precedence_over_format(self, monkeypatch):
        """`--groups` 優先於 `--format`（互斥，本函式不落入 list/dag 分支）。"""
        import argparse

        a = _mk_with_files("0.2.1-W3-650", ["lib/a.dart"])
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda version: [a])

        ns = argparse.Namespace(
            format="dag", top=None, context=None, wave=None, groups=True,
        )
        out = track_runqueue.render_runqueue(ns, "0.2.1")

        assert "=== Parallel Groups ===" in out

    def test_groups_false_falls_through_to_format_list(self, monkeypatch):
        """`groups` 屬性缺失（既有呼叫端未傳）時預設 False，維持原 list 行為。"""
        import argparse

        a = _mk("0.2.1-W3-660")
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda version: [a])

        ns = argparse.Namespace(format="list", top=None, context=None, wave=None)
        out = track_runqueue.render_runqueue(ns, "0.2.1")

        assert "=== Parallel Groups ===" not in out
        assert "可執行清單" in out

    def test_execute_runqueue_groups_end_to_end(self, monkeypatch, capsys):
        import argparse

        a = _mk_with_files("0.2.1-W3-670", ["lib/shared.dart"])
        b = _mk_with_files("0.2.1-W3-671", ["lib/shared.dart"])
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda version: [a, b])

        ns = argparse.Namespace(
            format="list", top=None, context=None, wave=None, groups=True,
        )
        rc = track_runqueue.execute_runqueue(ns, "0.2.1")

        assert rc == 0
        out = capsys.readouterr().out
        assert "本輪未選入可並行集合（1 票" in out
        assert "0.2.1-W3-670 <-> 0.2.1-W3-671" in out


class TestRegisterRunqueueGroupsFlag:
    def test_groups_flag_registered_and_defaults_false(self):
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        track_runqueue.register_runqueue(subparsers)

        ns = parser.parse_args(["runqueue"])
        assert ns.groups is False

    def test_groups_flag_can_be_set(self):
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        track_runqueue.register_runqueue(subparsers)

        ns = parser.parse_args(["runqueue", "--groups"])
        assert ns.groups is True


# ---------------------------------------------------------------------------
# 0.2.1-W3-220: _get_pending_handoff_info key 語意修復
# （target_ticket_id 同時建索引，不破壞既有以 source ticket_id 為 key 的呼叫端）
# ---------------------------------------------------------------------------

def _write_handoff(pending_dir, filename: str, data: Dict) -> None:
    import json
    (pending_dir / filename).write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


def test_get_pending_handoff_info_indexes_by_target_ticket_id(tmp_path, monkeypatch):
    """target 票應能以自身 id 查到 handoff（實例參照 0.2.1-W3-159.json 樣態）。"""
    pending_dir = tmp_path / ".claude" / "handoff" / "pending"
    pending_dir.mkdir(parents=True)
    _write_handoff(pending_dir, "a.json", {
        "ticket_id": "0.2.1-W3-159",
        "target_ticket_id": "0.2.1-W3-174",
    })
    monkeypatch.setattr(track_runqueue, "get_ticket_state_root", lambda: tmp_path)

    info = track_runqueue._get_pending_handoff_info()

    assert "0.2.1-W3-174" in info
    assert info["0.2.1-W3-174"]["ticket_id"] == "0.2.1-W3-159"


def test_get_pending_handoff_info_source_key_unaffected(tmp_path, monkeypatch):
    """既有以 source ticket_id 為 key 的呼叫端行為不變（不被 target key 覆蓋）。"""
    pending_dir = tmp_path / ".claude" / "handoff" / "pending"
    pending_dir.mkdir(parents=True)
    _write_handoff(pending_dir, "a.json", {
        "ticket_id": "0.2.1-W3-159",
        "target_ticket_id": "0.2.1-W3-174",
    })
    monkeypatch.setattr(track_runqueue, "get_ticket_state_root", lambda: tmp_path)

    info = track_runqueue._get_pending_handoff_info()

    assert "0.2.1-W3-159" in info
    assert info["0.2.1-W3-159"]["target_ticket_id"] == "0.2.1-W3-174"


def test_get_pending_handoff_info_source_key_not_overwritten_by_target(
    tmp_path, monkeypatch
):
    """target_ticket_id 若恰巧撞到另一張票的 source ticket_id，不覆蓋既有項目。"""
    pending_dir = tmp_path / ".claude" / "handoff" / "pending"
    pending_dir.mkdir(parents=True)
    _write_handoff(pending_dir, "a.json", {
        "ticket_id": "0.2.1-W3-001",
        "target_ticket_id": "0.2.1-W3-002",
    })
    _write_handoff(pending_dir, "b.json", {
        "ticket_id": "0.2.1-W3-002",
        "target_ticket_id": "0.2.1-W3-003",
    })
    monkeypatch.setattr(track_runqueue, "get_ticket_state_root", lambda: tmp_path)

    info = track_runqueue._get_pending_handoff_info()

    # 0.2.1-W3-002 既是 b.json 的 source key，也是 a.json 的 target_ticket_id；
    # source key（b.json 自身資料）不得被 a.json 的 target 補登錄覆蓋
    assert info["0.2.1-W3-002"]["ticket_id"] == "0.2.1-W3-002"


def test_get_pending_handoff_info_no_target_ticket_id_field(tmp_path, monkeypatch):
    """無 target_ticket_id 欄位的 handoff（向後相容）不受影響，僅登錄 source key。"""
    pending_dir = tmp_path / ".claude" / "handoff" / "pending"
    pending_dir.mkdir(parents=True)
    _write_handoff(pending_dir, "a.json", {"ticket_id": "0.2.1-W3-100"})
    monkeypatch.setattr(track_runqueue, "get_ticket_state_root", lambda: tmp_path)

    info = track_runqueue._get_pending_handoff_info()

    assert list(info.keys()) == ["0.2.1-W3-100"]


# ---------------------------------------------------------------------------
# 0.2.1-W3-765: --topic 過濾 + list 視圖主題前綴
# ---------------------------------------------------------------------------

class TestFilterByTopic:
    def test_topic_none_returns_all_tickets(self):
        tickets = [_mk("0.2.1-W3-001"), _mk("0.2.1-W3-002")]
        out = track_runqueue._filter_by_topic(tickets, None, {})
        assert out == tickets

    def test_topic_filters_to_matching_assignment_only(self):
        tickets = [_mk("0.2.1-W3-001"), _mk("0.2.1-W3-002"), _mk("0.2.1-W3-003")]
        assignments = {
            "0.2.1-W3-001": "排程主題",
            "0.2.1-W3-002": "其他主題",
        }
        out = track_runqueue._filter_by_topic(tickets, "排程主題", assignments)
        assert [t["id"] for t in out] == ["0.2.1-W3-001"]

    def test_topic_filters_out_unassigned_tickets(self):
        tickets = [_mk("0.2.1-W3-001")]
        out = track_runqueue._filter_by_topic(tickets, "排程主題", {})
        assert out == []


class TestRenderListTopicPrefix:
    def test_list_line_prefixed_with_assigned_topic(self):
        tickets = [_mk("0.2.1-W3-001", priority="P1")]
        assignments = {"0.2.1-W3-001": "排程主題"}
        out = track_runqueue._render_list(
            tickets, top=None, wave=None, context=None,
            topic_assignments_map=assignments,
        )
        assert "[排程主題]" in out

    def test_list_line_unassigned_shows_explicit_marker_not_blank(self):
        tickets = [_mk("0.2.1-W3-001", priority="P1")]
        out = track_runqueue._render_list(
            tickets, top=None, wave=None, context=None,
            topic_assignments_map={},
        )
        assert f"[{track_runqueue.UNASSIGNED_TOPIC_LABEL}]" in out

    def test_list_default_no_assignments_arg_uses_unassigned_marker(self):
        """topic_assignments_map 省略（呼叫端未提供）時仍以明確標記顯示，不留空。"""
        tickets = [_mk("0.2.1-W3-001", priority="P1")]
        out = track_runqueue._render_list(tickets, top=None, wave=None, context=None)
        assert f"[{track_runqueue.UNASSIGNED_TOPIC_LABEL}]" in out


class TestRegisterRunqueueTopicFlag:
    def test_topic_flag_registered_and_defaults_none(self):
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        track_runqueue.register_runqueue(subparsers)

        ns = parser.parse_args(["runqueue"])
        assert ns.topic is None

    def test_topic_flag_can_be_set(self):
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="operation")
        track_runqueue.register_runqueue(subparsers)

        ns = parser.parse_args(["runqueue", "--topic", "排程主題"])
        assert ns.topic == "排程主題"


class TestRenderRunqueueTopicFilterEndToEnd:
    def test_render_runqueue_topic_filters_list_output(self, monkeypatch):
        import argparse

        tickets = [_mk("0.2.1-W3-001"), _mk("0.2.1-W3-002")]
        assignments = {"0.2.1-W3-001": "排程主題"}
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda v: tickets)
        monkeypatch.setattr(
            track_runqueue.topic_assignments, "list_assignments", lambda: assignments
        )
        monkeypatch.setattr(
            track_runqueue, "_get_pending_handoff_info", lambda: {}
        )

        args = argparse.Namespace(
            format="list", top=None, context=None, wave=None,
            groups=False, topic="排程主題",
        )
        out = track_runqueue.render_runqueue(args, "0.2.1")

        assert "0.2.1-W3-001" in out
        assert "0.2.1-W3-002" not in out
        assert "[排程主題]" in out

    def test_render_runqueue_no_topic_arg_shows_all(self, monkeypatch):
        """--topic 未指定（args 缺 topic 屬性，走 getattr 預設 None）不過濾。"""
        import argparse

        tickets = [_mk("0.2.1-W3-001"), _mk("0.2.1-W3-002")]
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda v: tickets)
        monkeypatch.setattr(
            track_runqueue.topic_assignments, "list_assignments", lambda: {}
        )
        monkeypatch.setattr(
            track_runqueue, "_get_pending_handoff_info", lambda: {}
        )

        args = argparse.Namespace(
            format="list", top=None, context=None, wave=None, groups=False,
        )
        out = track_runqueue.render_runqueue(args, "0.2.1")

        assert "0.2.1-W3-001" in out
        assert "0.2.1-W3-002" in out


# ---------------------------------------------------------------------------
# 0.2.1-W3-765 acceptance #4: session-start-scheduler-hint-hook 對 runqueue
# stdout 的字串比對在新前綴下仍正確。hook 唯一的比對邏輯是
# EMPTY_MARKER = "無可執行 Ticket" 子字串檢查（見該 hook _has_content），
# 不解析逐行格式，故主題前綴不影響其判定。本測試直接複製該判定邏輯，
# 驗證含主題前綴的 list 輸出仍被判定為「有內容」。
# ---------------------------------------------------------------------------

def test_topic_prefixed_list_output_still_detected_as_non_empty_by_hook_logic(
    real_repo_root,
):
    empty_marker = _read_hook_empty_marker()
    tickets = [_mk("0.2.1-W3-001", priority="P1")]
    out = track_runqueue._render_list(
        tickets, top=None, wave=None, context=None,
        topic_assignments_map={"0.2.1-W3-001": "排程主題"},
    )
    has_content = bool(out and out.strip()) and empty_marker not in out
    assert has_content is True


# ---------------------------------------------------------------------------
# 空清單訊息在過濾情境下的歸因（過濾排空的原因不可固定歸因 blockedBy/status，
# 訊息須反映實際排空所在的階段：wave 過濾 / topic 過濾 / blockedBy+status）
# ---------------------------------------------------------------------------

class TestEmptyReasonAttribution:
    def test_topic_filter_no_match_reports_topic_not_blocked_by(
        self, monkeypatch, real_repo_root
    ):
        """--topic 無命中時訊息指出主題過濾為排空原因，不歸因 blockedBy 或 status。"""
        import argparse

        tickets = [_mk("0.2.1-W3-001", wave=3)]
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda v: tickets)
        monkeypatch.setattr(
            track_runqueue.topic_assignments, "list_assignments", lambda: {}
        )
        monkeypatch.setattr(
            track_runqueue, "_get_pending_handoff_info", lambda: {}
        )

        args = argparse.Namespace(
            format="list", top=None, context=None, wave=3,
            topic="不存在的主題", groups=False,
        )
        out = track_runqueue.render_runqueue(args, "0.2.1")

        assert "不存在的主題" in out
        assert "無符合票" in out
        assert "blockedBy 全非空或 status 非 pending" not in out

    def test_wave_filter_no_match_reports_wave_not_blocked_by(self, monkeypatch):
        """--wave 無命中時訊息指出 wave 過濾為排空原因，不歸因 blockedBy 或 status。"""
        import argparse

        tickets = [_mk("0.2.1-W3-001", wave=1)]
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda v: tickets)
        monkeypatch.setattr(
            track_runqueue.topic_assignments, "list_assignments", lambda: {}
        )
        monkeypatch.setattr(
            track_runqueue, "_get_pending_handoff_info", lambda: {}
        )

        args = argparse.Namespace(
            format="list", top=None, context=None, wave=99,
            topic=None, groups=False,
        )
        out = track_runqueue.render_runqueue(args, "0.2.1")

        assert "wave 99" in out
        assert "無符合票" in out
        assert "blockedBy 全非空或 status 非 pending" not in out

    def test_wave_and_topic_both_matched_but_blocked_reports_original_message(
        self, monkeypatch
    ):
        """wave / topic 過濾皆有命中票，僅因 blockedBy/status 排空時維持原訊息。"""
        import argparse

        tickets = [_mk("0.2.1-W3-001", wave=3, status="completed")]
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda v: tickets)
        monkeypatch.setattr(
            track_runqueue.topic_assignments,
            "list_assignments",
            lambda: {"0.2.1-W3-001": "排程主題"},
        )
        monkeypatch.setattr(
            track_runqueue, "_get_pending_handoff_info", lambda: {}
        )

        args = argparse.Namespace(
            format="list", top=None, context=None, wave=3,
            topic="排程主題", groups=False,
        )
        out = track_runqueue.render_runqueue(args, "0.2.1")

        assert "blockedBy 全非空或 status 非 pending" in out

    def test_groups_view_topic_filter_no_match_reports_topic(self, monkeypatch):
        """--groups 視圖下 --topic 無命中同樣歸因主題，不共用 list 視圖固定文字。"""
        import argparse

        tickets = [_mk("0.2.1-W3-001")]
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda v: tickets)
        monkeypatch.setattr(
            track_runqueue.topic_assignments, "list_assignments", lambda: {}
        )

        args = argparse.Namespace(
            format="list", top=None, context=None, wave=None,
            topic="不存在的主題", groups=True,
        )
        out = track_runqueue.render_runqueue(args, "0.2.1")

        assert "不存在的主題" in out
        assert "無符合票" in out

    def test_all_empty_reason_messages_contain_empty_marker(
        self, monkeypatch, real_repo_root
    ):
        """所有空清單訊息維持含 EMPTY_MARKER 子字串（機械化比對 hook 常數值）。"""
        import argparse

        empty_marker = _read_hook_empty_marker()
        monkeypatch.setattr(track_runqueue, "list_tickets", lambda v: [])
        monkeypatch.setattr(
            track_runqueue.topic_assignments, "list_assignments", lambda: {}
        )
        monkeypatch.setattr(
            track_runqueue, "_get_pending_handoff_info", lambda: {}
        )

        for wave, topic in [(None, None), (3, None), (None, "某主題"), (3, "某主題")]:
            args = argparse.Namespace(
                format="list", top=None, context=None, wave=wave,
                topic=topic, groups=False,
            )
            out = track_runqueue.render_runqueue(args, "0.2.1")
            assert empty_marker in out

        args_groups = argparse.Namespace(
            format="list", top=None, context=None, wave=None,
            topic=None, groups=True,
        )
        out_groups = track_runqueue.render_runqueue(args_groups, "0.2.1")
        assert empty_marker in out_groups
