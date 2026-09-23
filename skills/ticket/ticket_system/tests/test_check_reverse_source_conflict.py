"""Unit tests for ticket_ops.check_reverse_source_conflict.

裁定「寫入端是否加目標票血緣一致性檢查」落地的部分——本檢查只發
WARNING、不阻擋寫入（見函式 docstring 的理由）。呼叫端（add-spawned /
resolve-spawn-request）的整合行為另見各自測試檔。
"""

from __future__ import annotations

from unittest.mock import patch

# 匯入順序刻意固定：ticket_loader 先於 ticket_ops 匯入，避免觸發既有的
# ticket_ops <-> ticket_loader <-> ticket_chain_index 循環匯入（ticket_ops
# 若作為 process 內第一個被匯入的模組，ticket_chain_index 會在 ticket_ops
# 尚未初始化完成時嘗試取用 resolve_id_from_ref 而 ImportError；其他測試
# 檔案未撞到是因為先匯入了 commands.fields，順帶以正確順序解決了這條鏈）
import ticket_system.lib.ticket_loader  # noqa: F401
from ticket_system.lib import ticket_ops


def _patch_target_load(ticket_or_none):
    return patch.object(
        ticket_ops, "load_ticket", side_effect=lambda version, tid: ticket_or_none
    )


def _patch_version(version_or_none):
    return patch(
        "ticket_system.lib.ticket_validator.extract_version_from_ticket_id",
        return_value=version_or_none,
    )


def test_no_conflict_when_target_not_found():
    with _patch_version("0.31.0"), _patch_target_load(None):
        result = ticket_ops.check_reverse_source_conflict("0.31.0-W1-001", "T-1")
    assert result is None


def test_no_conflict_when_version_unresolvable():
    with _patch_version(None):
        result = ticket_ops.check_reverse_source_conflict("not-a-ticket-id", "T-1")
    assert result is None


def test_no_conflict_when_target_has_no_source_ticket():
    target = {"id": "0.31.0-W1-001", "source_ticket": None}
    with _patch_version("0.31.0"), _patch_target_load(target):
        result = ticket_ops.check_reverse_source_conflict("0.31.0-W1-001", "T-1")
    assert result is None


def test_no_conflict_when_source_ticket_matches_parent():
    target = {"id": "0.31.0-W1-001", "source_ticket": "T-1"}
    with _patch_version("0.31.0"), _patch_target_load(target):
        result = ticket_ops.check_reverse_source_conflict("0.31.0-W1-001", "T-1")
    assert result is None


def test_conflict_when_source_ticket_points_elsewhere():
    target = {"id": "0.31.0-W1-001", "source_ticket": "0.31.0-W9-999"}
    with _patch_version("0.31.0"), _patch_target_load(target):
        result = ticket_ops.check_reverse_source_conflict("0.31.0-W1-001", "T-1")
    assert result is not None
    assert "0.31.0-W1-001" in result
    assert "0.31.0-W9-999" in result
    assert "T-1" in result
