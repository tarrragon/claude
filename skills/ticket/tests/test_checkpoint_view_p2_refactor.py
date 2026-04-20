"""W10-017.13 Phase 4b P2 refactor regression tests.

涵蓋範圍：
- AC1: handoff_status_for dict dispatch（_HANDOFF_STATUS_ROUTES 表）
  - 3 caller 各自路由到正確 builder
  - 新增 caller 只需擴充表（靜態檢驗：_VALID_CALLERS 與 routes key 同步）
- AC2: render_ready_check 未通過計數改用 CheckItem 結構化而非 "[ ]" 字串反推
  - CheckItem 匯出於公開 API
  - render_ready_check snapshot footer「X 項未通過」計數仍正確
  - 驗證計數邏輯不再依賴「把 '[ ]' 字面出現在 rendered 輸出裡」

Baseline: W10-017.12 之後 1296 綠。本 P2 重構後應保持全綠 + 新增本檔測試通過。
"""

from __future__ import annotations

from ticket_system.lib.checkpoint_state import CheckpointState
from ticket_system.lib.checkpoint_view import (
    CheckItem,
    _HANDOFF_STATUS_ROUTES,
    _VALID_CALLERS,
    handoff_status_for,
    render_ready_check,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> CheckpointState:
    defaults = dict(
        current_phase="3",
        ready_for_clear=True,
        pending_checks=[],
        active_agents=0,
        unmerged_worktrees=[],
        active_handoff=None,
        in_progress_tickets=[],
        data_sources={},
        computed_at="2026-04-19T12:00:00+00:00",
        uncommitted_files=0,
    )
    defaults.update(overrides)
    return CheckpointState(**defaults)


# ---------------------------------------------------------------------------
# AC1: handoff_status_for dict dispatch
# ---------------------------------------------------------------------------


def test_AC1_handoff_status_routes_table_covers_all_valid_callers():
    """_HANDOFF_STATUS_ROUTES 的 keys 必須與 _VALID_CALLERS 一致。

    防護：新增 CheckpointCaller 值（新 caller）時，若漏更新路由表會被此測抓到。
    """
    assert set(_HANDOFF_STATUS_ROUTES.keys()) == set(_VALID_CALLERS)


def test_AC1_dispatch_delegates_to_snapshot_builder():
    """snapshot caller 命中應回 (False, 含 handoff_id) 對 active_handoff not None."""
    state = _make_state(active_handoff="W10-017.13")
    is_ok, msg = handoff_status_for(state, caller="snapshot")
    assert is_ok is False
    assert "W10-017.13" in msg


def test_AC1_dispatch_delegates_to_handoff_ready_builder():
    """handoff-ready caller + handoff 存在 → (True, "handoff 已建立 ...")."""
    state = _make_state(active_handoff="W10-017.13")
    is_ok, msg = handoff_status_for(state, caller="handoff-ready")
    assert is_ok is True
    assert "handoff 已建立" in msg


def test_AC1_dispatch_delegates_to_checkpoint_status_builder():
    """checkpoint-status caller 永遠不阻擋。"""
    state = _make_state(active_handoff="W10-017.13")
    is_ok, msg = handoff_status_for(state, caller="checkpoint-status")
    assert is_ok is True
    assert "handoff pending" in msg


# ---------------------------------------------------------------------------
# AC2: render_ready_check uses structured CheckItem
# ---------------------------------------------------------------------------


def test_AC2_check_item_exported_in_public_api():
    """CheckItem 必須可從 lib.checkpoint_view 匯入（新公開契約）。"""
    from ticket_system.lib import checkpoint_view

    assert "CheckItem" in checkpoint_view.__all__
    assert hasattr(checkpoint_view, "CheckItem")


def test_AC2_check_item_render_pass_produces_x_mark():
    item = CheckItem(status="pass", text="無活躍代理人 (active_agents=0)")
    assert item.render() == "  [x] 無活躍代理人 (active_agents=0)"


def test_AC2_check_item_render_fail_with_hint():
    item = CheckItem(
        status="fail",
        text="無未提交變更 (uncommitted_files=3)",
        hint="git add + git commit",
    )
    assert item.render() == (
        "  [ ] 無未提交變更 (uncommitted_files=3) → git add + git commit"
    )


def test_AC2_check_item_render_unknown_marks_question():
    item = CheckItem(status="unknown", text="資料源不可用")
    assert item.render() == "  [?] 資料源不可用"


def test_AC2_snapshot_footer_counts_failures_structurally():
    """snapshot footer 「X 項未通過」必須等於 fail 狀態的 CheckItem 數。

    構造 3 個 fail 條件：active_agents=2 / uncommitted=5 / worktree=1；
    handoff=None 在 snapshot 下為 pass。預期 3 項未通過。
    """
    state = _make_state(
        active_agents=2,
        uncommitted_files=5,
        unmerged_worktrees=["/wt/a"],
        active_handoff=None,
    )
    out = render_ready_check(state, caller="snapshot")
    assert "3 項未通過" in out


def test_AC2_snapshot_footer_ignores_unknown_status_in_count():
    """uncommitted_files=None（[?] 狀態）不應被計入「未通過」。

    構造 active_agents=1 (fail) + uncommitted=None (unknown) + 其他 pass；
    預期「1 項未通過」，而非 2（舊 "[ ]" 字串反推會誤算成 1，但新結構把 [?]
    獨立為 status="unknown" 明確排除）。
    """
    state = _make_state(
        active_agents=1,
        uncommitted_files=None,
        unmerged_worktrees=[],
        active_handoff=None,
    )
    out = render_ready_check(state, caller="snapshot")
    assert "1 項未通過" in out
    # 且 [?] 確實出現在輸出中（AD-4 行為保留）
    assert "[?]" in out


def test_AC2_non_snapshot_caller_has_no_footer_count():
    """handoff-ready / checkpoint-status caller 不輸出「X 項未通過」footer。"""
    state = _make_state(active_agents=1, active_handoff="T1")
    out_hr = render_ready_check(state, caller="handoff-ready")
    out_cs = render_ready_check(state, caller="checkpoint-status")
    assert "項未通過" not in out_hr
    assert "項未通過" not in out_cs
