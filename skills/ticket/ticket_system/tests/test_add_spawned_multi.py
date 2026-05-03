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
    """Patch load/save/resolve to operate on in-memory ticket."""
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
