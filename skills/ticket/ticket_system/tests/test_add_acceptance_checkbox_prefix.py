"""add-acceptance 剝除誤帶入文字的核取方塊前綴，迴歸測試。

背景：add-acceptance 的 value 語意是「條目文字」，CLI 自行補正規前綴；但
help 原未說明此行為，呼叫者複製票面既有字面（帶 [ ]/[x] 開頭）貼入會得到
雙重前綴。剝除邏輯沿用 set-acceptance --add/--edit 已落地的
`_strip_checkbox_prefix`，僅剝除字串開頭一次出現，文字中段的 [ ] 不受影響。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter


@pytest.fixture(autouse=True)
def _patch_fields_ticket_paths(precondition_tmp_dir, monkeypatch):
    """execute_add_acceptance 所在的 fields 模組各自 import 了自己的
    get_ticket_path / load_and_validate_ticket 名稱，tmp_ticket_factory 的
    monkeypatch 未涵蓋此模組（僅涵蓋 track_acceptance / track_set_acceptance /
    ticket_loader / ticket_ops），需另外在此檔案內對 fields 模組命名空間補 patch
    （對齊 test_commands_race.py 既有做法）。
    """
    from ticket_system.commands import fields as fields_mod

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return precondition_tmp_dir / f"{ticket_id}.md"

    def _fake_load_and_validate_ticket(version: str, ticket_id: str):
        from ticket_system.lib.parser import parse_frontmatter as _parse

        path = precondition_tmp_dir / f"{ticket_id}.md"
        if not path.exists():
            return None, f"ticket not found: {ticket_id}"
        fm, body = _parse(path.read_text(encoding="utf-8"))
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm, None

    monkeypatch.setattr(fields_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(fields_mod, "load_and_validate_ticket", _fake_load_and_validate_ticket)


def _call_add_acceptance(
    ticket_id: str,
    value: str,
    *,
    force: bool = False,
    as_agent: str | None = None,
) -> int:
    from ticket_system.commands.fields import execute_add_acceptance

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        value=value,
        force=force,
        as_agent=as_agent,
    )
    return execute_add_acceptance(ns, "0.0.0")


def _read_acceptance(precondition_tmp_dir: Path, ticket_id: str) -> list[str]:
    path = precondition_tmp_dir / f"{ticket_id}.md"
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm["acceptance"]


def test_add_acceptance_plain_text_gets_single_prefix(
    tmp_ticket_factory, precondition_tmp_dir
):
    tid = tmp_ticket_factory(status="in_progress", acceptance=["[x] 條件一"])
    rc = _call_add_acceptance(tid, "新條件")
    assert rc == 0
    assert _read_acceptance(precondition_tmp_dir, tid) == ["[x] 條件一", "[ ] 新條件"]


def test_add_acceptance_with_unchecked_prefix_normalized_to_single(
    tmp_ticket_factory, precondition_tmp_dir
):
    tid = tmp_ticket_factory(status="in_progress", acceptance=["[x] 條件一"])
    rc = _call_add_acceptance(tid, "[ ] 新條件")
    assert rc == 0
    assert _read_acceptance(precondition_tmp_dir, tid) == ["[x] 條件一", "[ ] 新條件"], (
        "帶入的 [ ] 前綴應被剝除，不應與既有邏輯補的前綴疊加成雙重前綴"
    )


def test_add_acceptance_with_checked_prefix_normalized_to_unchecked(
    tmp_ticket_factory, precondition_tmp_dir
):
    tid = tmp_ticket_factory(status="in_progress", acceptance=["[x] 條件一"])
    rc = _call_add_acceptance(tid, "[x] 新條件")
    assert rc == 0
    assert _read_acceptance(precondition_tmp_dir, tid) == ["[x] 條件一", "[ ] 新條件"], (
        "add-acceptance 新增條目一律未勾選，帶入的 [x] 視為誤帶字面而非勾選意圖"
    )


def test_add_acceptance_midtext_bracket_not_stripped(
    tmp_ticket_factory, precondition_tmp_dir
):
    """文字中段的 [ ] 是內容不是前綴，不應被剝除（僅剝除開頭一次出現）。"""
    tid = tmp_ticket_factory(status="in_progress", acceptance=["[x] 條件一"])
    rc = _call_add_acceptance(tid, "欄位格式為 [ ] 開頭")
    assert rc == 0
    assert _read_acceptance(precondition_tmp_dir, tid) == [
        "[x] 條件一",
        "[ ] 欄位格式為 [ ] 開頭",
    ]
