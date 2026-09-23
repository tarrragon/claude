"""Unit tests for execute_remove_spawned（補齊 add-spawned 對稱移除介面）.

Verifies:
- 按 ID 移除（單一 / 多個），介面比照 add-spawned 的 nargs='+'
- 不存在的條目回報而非靜默（rc 與 stderr 皆可觀察）
- 部分成功時：已移除項目照常寫入、找不到項目照常回報
- 反向欄位清理：目標票 source_ticket 回指本票時同步清除
- 反向欄位不清理：目標票 source_ticket 指向他處時保持不動
"""

from __future__ import annotations

import argparse
from typing import Any
from unittest.mock import patch

from ticket_system.commands import fields as fields_mod


def _make_args(ticket_id: str, value: Any) -> argparse.Namespace:
    return argparse.Namespace(ticket_id=ticket_id, value=value)


def _patch_io(ticket: dict):
    """Patch load/save/resolve to operate on in-memory ticket（比照 add-spawned 測試模式）。

    ``fake_save`` 額外把每次呼叫記錄進 ``saved["calls"]``（依 id 索引）：
    反向欄位清理測試需要區分「本票的 save」與「目標票的 save」兩次獨立呼叫
    ——兩者共用同一個被 patch 的 save_ticket，若只覆寫單一 "ticket" key
    後到的呼叫會覆蓋先到的斷言目標。

    亦 patch `git_utils._auto_commit_ticket_md`：對假路徑呼叫真實版本會
    回傳 `git_failed` 並寫 stderr WARNING，與本檔測試目標無關，見
    test_add_spawned_multi.py 同型註解。
    """
    saved: dict = {"calls": []}

    def fake_load(version, tid):
        return ticket, None

    def fake_resolve(t, v, tid):
        return "/tmp/fake-path.md"

    def fake_save(t, path):
        saved["calls"].append({"ticket": t, "path": path})
        saved["ticket"] = t
        saved["path"] = path

    return saved, [
        patch.object(fields_mod, "load_and_validate_ticket", side_effect=fake_load),
        patch.object(fields_mod, "resolve_ticket_path", side_effect=fake_resolve),
        patch.object(fields_mod.ticket_loader, "save_ticket", side_effect=fake_save),
        patch(
            "ticket_system.lib.git_utils._auto_commit_ticket_md",
            return_value="committed",
        ),
    ]


def _find_saved_by_id(saved: dict, ticket_id: str) -> dict:
    for call in saved["calls"]:
        if call["ticket"].get("id") == ticket_id:
            return call["ticket"]
    raise AssertionError(f"no save_ticket call recorded for id={ticket_id!r}")


def test_remove_spawned_single_id(capsys):
    ticket = {"id": "T-1", "spawned_tickets": ["A", "B"]}
    saved, patches = _patch_io(ticket)
    for p in patches:
        p.start()
    try:
        rc = fields_mod.execute_remove_spawned(
            _make_args("T-1", ["A"]), version="0.31.0"
        )
    finally:
        for p in patches:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == ["B"]
    out = capsys.readouterr().out
    assert "移除: A" in out


def test_remove_spawned_multi_ids(capsys):
    ticket = {"id": "T-1", "spawned_tickets": ["A", "B", "C"]}
    saved, patches = _patch_io(ticket)
    for p in patches:
        p.start()
    try:
        rc = fields_mod.execute_remove_spawned(
            _make_args("T-1", ["A", "B"]), version="0.31.0"
        )
    finally:
        for p in patches:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == ["C"]
    out = capsys.readouterr().out
    assert "移除: A, B" in out


def test_remove_spawned_not_found_reports_not_silent(capsys):
    """核心 acceptance：對不存在的條目回報而非靜默（非 0 rc + stderr 可見）。"""
    ticket = {"id": "T-1", "spawned_tickets": ["A"]}
    saved, patches = _patch_io(ticket)
    for p in patches:
        p.start()
    try:
        rc = fields_mod.execute_remove_spawned(
            _make_args("T-1", ["X"]), version="0.31.0"
        )
    finally:
        for p in patches:
            p.stop()

    # 全數找不到：無變更可寫，rc 非 0（與 remove-acceptance 索引超出範圍時
    # 回傳 1 同語意：呼叫者要求的操作未達成）
    assert rc == 1
    assert saved["ticket"]["spawned_tickets"] == ["A"]
    captured = capsys.readouterr()
    assert "X" in captured.err
    assert "找不到" in captured.err


def test_remove_spawned_partial_not_found_still_removes_found(capsys):
    """部分成功：找得到的照常移除並寫入，找不到的照常回報，不因夾帶無效 ID 而整批拒絕。"""
    ticket = {"id": "T-1", "spawned_tickets": ["A"]}
    saved, patches = _patch_io(ticket)
    for p in patches:
        p.start()
    try:
        rc = fields_mod.execute_remove_spawned(
            _make_args("T-1", ["A", "X"]), version="0.31.0"
        )
    finally:
        for p in patches:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == []
    captured = capsys.readouterr()
    assert "移除: A" in captured.out
    assert "X" in captured.err
    assert "找不到" in captured.err


def test_remove_spawned_clears_matching_reverse_source_ticket(capsys):
    """反向欄位清理：目標票 source_ticket 回指本票時，移除後應同步清除。"""
    ticket = {"id": "T-1", "spawned_tickets": ["0.31.0-W1-001"]}
    saved, patches = _patch_io(ticket)

    target_ticket = {"id": "0.31.0-W1-001", "source_ticket": "T-1"}

    def fake_target_load(version, tid):
        return dict(target_ticket)

    extra_patches = [
        patch.object(fields_mod.ticket_loader, "load_ticket", side_effect=fake_target_load),
        patch(
            "ticket_system.lib.ticket_validator.extract_version_from_ticket_id",
            return_value="0.31.0",
        ),
    ]

    for p in patches + extra_patches:
        p.start()
    try:
        rc = fields_mod.execute_remove_spawned(
            _make_args("T-1", ["0.31.0-W1-001"]), version="0.31.0"
        )
    finally:
        for p in patches + extra_patches:
            p.stop()

    assert rc == 0
    assert _find_saved_by_id(saved, "T-1")["spawned_tickets"] == []
    assert _find_saved_by_id(saved, "0.31.0-W1-001")["source_ticket"] is None
    out = capsys.readouterr().out
    assert "已同步清除反向欄位" in out
    assert "0.31.0-W1-001" in out


def test_remove_spawned_does_not_clear_mismatched_reverse_source_ticket(capsys):
    """反向欄位保護：目標票 source_ticket 指向他處時不動它——這正是本命令要
    修復的動機案例（誤植的 spawned 條目移除時，不可誤清無關票的血緣）。"""
    ticket = {"id": "T-1", "spawned_tickets": ["0.31.0-W1-001"]}
    saved, patches = _patch_io(ticket)

    target_ticket = {"id": "0.31.0-W1-001", "source_ticket": "0.31.0-W9-999"}

    def fake_target_load(version, tid):
        return dict(target_ticket)

    extra_patches = [
        patch.object(fields_mod.ticket_loader, "load_ticket", side_effect=fake_target_load),
        patch(
            "ticket_system.lib.ticket_validator.extract_version_from_ticket_id",
            return_value="0.31.0",
        ),
    ]

    for p in patches + extra_patches:
        p.start()
    try:
        rc = fields_mod.execute_remove_spawned(
            _make_args("T-1", ["0.31.0-W1-001"]), version="0.31.0"
        )
    finally:
        for p in patches + extra_patches:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == []
    # 只有本票（T-1）的 save 被呼叫；目標票 source_ticket 指向他處，
    # 不應觸發第二次 save_ticket 呼叫
    assert len(saved["calls"]) == 1
    out = capsys.readouterr().out
    assert "已同步清除反向欄位" not in out
