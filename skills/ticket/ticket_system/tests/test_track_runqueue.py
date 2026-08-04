"""Tests for ticket_system/commands/track_runqueue.py (W17-020).

聚焦 _render_list 在 context=resume 過濾為空時的訊息分支。
"""

from __future__ import annotations

from typing import Dict, List

import pytest

from ticket_system.commands import track_runqueue


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
    monkeypatch.setattr(track_runqueue, "get_project_root", lambda: tmp_path)

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
    monkeypatch.setattr(track_runqueue, "get_project_root", lambda: tmp_path)

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
    monkeypatch.setattr(track_runqueue, "get_project_root", lambda: tmp_path)

    info = track_runqueue._get_pending_handoff_info()

    # 0.2.1-W3-002 既是 b.json 的 source key，也是 a.json 的 target_ticket_id；
    # source key（b.json 自身資料）不得被 a.json 的 target 補登錄覆蓋
    assert info["0.2.1-W3-002"]["ticket_id"] == "0.2.1-W3-002"


def test_get_pending_handoff_info_no_target_ticket_id_field(tmp_path, monkeypatch):
    """無 target_ticket_id 欄位的 handoff（向後相容）不受影響，僅登錄 source key。"""
    pending_dir = tmp_path / ".claude" / "handoff" / "pending"
    pending_dir.mkdir(parents=True)
    _write_handoff(pending_dir, "a.json", {"ticket_id": "0.2.1-W3-100"})
    monkeypatch.setattr(track_runqueue, "get_project_root", lambda: tmp_path)

    info = track_runqueue._get_pending_handoff_info()

    assert list(info.keys()) == ["0.2.1-W3-100"]
