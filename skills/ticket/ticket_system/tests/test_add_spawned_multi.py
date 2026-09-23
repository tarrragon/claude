"""Unit tests for execute_add_spawned multi-ID support (W17-008.1).

Verifies:
- nargs='+' multi-ID path: 一次新增多個 spawned IDs
- 單 ID 回歸：仍可單一 ID 呼叫
- 重複 ID 略過、計入 skipped
"""

from __future__ import annotations

import argparse
from typing import Any
from unittest.mock import patch

import pytest

from ticket_system.commands import fields as fields_mod


def _make_args(ticket_id: str, value: Any) -> argparse.Namespace:
    return argparse.Namespace(ticket_id=ticket_id, value=value)


@pytest.fixture
def fake_ticket():
    return {"id": "T-1", "spawned_tickets": []}


def _patch_io(ticket: dict):
    """Patch load/save/resolve to operate on in-memory ticket.

    亦 patch `git_utils._auto_commit_ticket_md`：`execute_add_spawned`
    對假路徑（`/tmp/fake-path.md`，非 git repo）呼叫真實版本會回傳
    `git_failed` 並寫 stderr WARNING，與本檔測試的目標行為（多 ID 新增/
    略過/血緣衝突提示）無關，會污染 `capsys` 斷言（auto-commit 本身的
    行為已由其他測試檔以真實 git repo fixture 覆蓋，見
    test_set_acceptance_auto_commit.py 同型案例）。
    """
    saved = {}

    def fake_load(version, tid):
        return ticket, None

    def fake_resolve(t, v, tid):
        return "/tmp/fake-path.md"

    def fake_save(t, path):
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


def test_add_spawned_multi_ids(fake_ticket, capsys):
    saved, patches = _patch_io(fake_ticket)
    for p in patches:
        p.start()
    try:
        rc = fields_mod.execute_add_spawned(
            _make_args("T-1", ["A", "B", "C"]), version="0.18.0"
        )
    finally:
        for p in patches:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == ["A", "B", "C"]
    out = capsys.readouterr().out
    assert "A, B, C" in out


def test_add_spawned_single_id_regression(fake_ticket, capsys):
    """單 ID 路徑仍 work（nargs='+' 仍會傳 list）."""
    saved, patches = _patch_io(fake_ticket)
    for p in patches:
        p.start()
    try:
        rc = fields_mod.execute_add_spawned(
            _make_args("T-1", ["A"]), version="0.18.0"
        )
    finally:
        for p in patches:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == ["A"]


def test_add_spawned_dedup_skipped(capsys):
    ticket = {"id": "T-1", "spawned_tickets": ["A"]}
    saved, patches = _patch_io(ticket)
    for p in patches:
        p.start()
    try:
        rc = fields_mod.execute_add_spawned(
            _make_args("T-1", ["A", "B"]), version="0.18.0"
        )
    finally:
        for p in patches:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == ["A", "B"]
    out = capsys.readouterr().out
    assert "新增: B" in out
    assert "已存在略過: A" in out


def test_add_spawned_backward_compat_string_value(fake_ticket):
    """防護：如有 caller 傳 str（理論上 argparse 已保證 list），仍能處理."""
    saved, patches = _patch_io(fake_ticket)
    for p in patches:
        p.start()
    try:
        rc = fields_mod.execute_add_spawned(
            _make_args("T-1", "X"), version="0.18.0"
        )
    finally:
        for p in patches:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == ["X"]


def test_add_spawned_warns_on_reverse_source_conflict(fake_ticket, capsys):
    """血緣一致性檢查（W3-644 acceptance 3 的裁定落地）：target 的
    source_ticket 指向他處時，寫入仍成功但發 stderr WARNING，不靜默。"""
    saved, patches = _patch_io(fake_ticket)
    conflict_patch = patch.object(
        fields_mod,
        "check_reverse_source_conflict",
        return_value="0.31.0-W1-001 的 source_ticket 已為 0.31.0-W9-999",
    )
    for p in patches + [conflict_patch]:
        p.start()
    try:
        rc = fields_mod.execute_add_spawned(
            _make_args("T-1", ["0.31.0-W1-001"]), version="0.18.0"
        )
    finally:
        for p in patches + [conflict_patch]:
            p.stop()

    assert rc == 0
    assert saved["ticket"]["spawned_tickets"] == ["0.31.0-W1-001"]
    err = capsys.readouterr().err
    assert "0.31.0-W1-001" in err
    assert "0.31.0-W9-999" in err


def test_add_spawned_no_warning_when_no_conflict(fake_ticket, capsys):
    saved, patches = _patch_io(fake_ticket)
    conflict_patch = patch.object(fields_mod, "check_reverse_source_conflict", return_value=None)
    for p in patches + [conflict_patch]:
        p.start()
    try:
        rc = fields_mod.execute_add_spawned(
            _make_args("T-1", ["A"]), version="0.18.0"
        )
    finally:
        for p in patches + [conflict_patch]:
            p.stop()

    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == ""
