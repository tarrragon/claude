"""set-acceptance --add / --edit / --remove 迴歸測試。

背景：現行 set-acceptance 僅支援 --check / --uncheck / --all-check /
--all-uncheck，建票後範圍變化時無法修訂 acceptance 條目本身（只能新增/移除
既有條目的勾選狀態，無法改文字、加新條目、刪舊條目）。本檔驗證三個新增
子操作與既有 check/uncheck 系列正交共存、索引對位正確、已勾選條目移除防護。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter


def _call_set_acceptance(
    ticket_id: str,
    *,
    check: list[str] | None = None,
    uncheck: list[str] | None = None,
    all_check: bool = False,
    all_uncheck: bool = False,
    add: list[str] | None = None,
    edit: list[list[str]] | None = None,
    remove: list[str] | None = None,
    force: bool = False,
) -> int:
    from ticket_system.commands.track_set_acceptance import execute_set_acceptance

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        check=check,
        uncheck=uncheck,
        all_check=all_check,
        all_uncheck=all_uncheck,
        add=add,
        edit=edit,
        remove=remove,
        force=force,
    )
    return execute_set_acceptance(ns, "0.0.0")


def _read_acceptance(precondition_tmp_dir: Path, ticket_id: str) -> list[str]:
    path = precondition_tmp_dir / f"{ticket_id}.md"
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm["acceptance"]


class TestAdd:
    def test_add_appends_unchecked_item(self, tmp_ticket_factory, precondition_tmp_dir):
        tid = tmp_ticket_factory(
            status="in_progress", acceptance=["[x] 條件一"]
        )
        rc = _call_set_acceptance(tid, add=["新條件"])
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[x] 條件一", "[ ] 新條件"]

    def test_add_multiple_items_in_one_call(self, tmp_ticket_factory, precondition_tmp_dir):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[ ] 條件一"])
        rc = _call_set_acceptance(tid, add=["條件二", "條件三"])
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[ ] 條件一", "[ ] 條件二", "[ ] 條件三"]

class TestEdit:
    def test_edit_overwrites_text_preserves_checked_state(
        self, tmp_ticket_factory, precondition_tmp_dir
    ):
        tid = tmp_ticket_factory(
            status="in_progress", acceptance=["[x] 舊文字一", "[ ] 舊文字二"]
        )
        rc = _call_set_acceptance(tid, edit=[["1", "新文字一"]])
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[x] 新文字一", "[ ] 舊文字二"], (
            "edit 覆寫文字後，原勾選狀態（[x]）必須保留"
        )

    def test_edit_preserves_unchecked_state(self, tmp_ticket_factory, precondition_tmp_dir):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[ ] 舊文字"])
        rc = _call_set_acceptance(tid, edit=[["1", "新文字"]])
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[ ] 新文字"]

    def test_edit_multiple_pairs_in_one_call(self, tmp_ticket_factory, precondition_tmp_dir):
        tid = tmp_ticket_factory(
            status="in_progress", acceptance=["[ ] 一", "[x] 二", "[ ] 三"]
        )
        rc = _call_set_acceptance(tid, edit=[["1", "改一"], ["3", "改三"]])
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[ ] 改一", "[x] 二", "[ ] 改三"]

    def test_edit_invalid_index_rejected(self, tmp_ticket_factory, precondition_tmp_dir, capsys):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[ ] 條件一"])
        rc = _call_set_acceptance(tid, edit=[["9", "文字"]])
        assert rc == 1
        assert "超出範圍" in capsys.readouterr().out
        # 失敗時不應寫入任何變更
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[ ] 條件一"]

    def test_edit_duplicate_index_rejected(self, tmp_ticket_factory, precondition_tmp_dir, capsys):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[ ] 一", "[ ] 二"])
        rc = _call_set_acceptance(tid, edit=[["1", "改甲"], ["1", "改乙"]])
        assert rc == 1
        assert "重複指定" in capsys.readouterr().out


class TestRemove:
    def test_remove_unchecked_item(self, tmp_ticket_factory, precondition_tmp_dir):
        tid = tmp_ticket_factory(
            status="in_progress", acceptance=["[x] 一", "[ ] 二", "[x] 三"]
        )
        rc = _call_set_acceptance(tid, remove=["2"])
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[x] 一", "[x] 三"]

    def test_remove_checked_item_without_force_blocked(
        self, tmp_ticket_factory, precondition_tmp_dir, capsys
    ):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[x] 一", "[ ] 二"])
        rc = _call_set_acceptance(tid, remove=["1"])
        assert rc == 1
        assert "--force" in capsys.readouterr().out
        # 拒絕時內容不變（防抹驗收證據的核心保證）
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[x] 一", "[ ] 二"]

    def test_remove_checked_item_with_force_allowed(
        self, tmp_ticket_factory, precondition_tmp_dir
    ):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[x] 一", "[ ] 二"])
        rc = _call_set_acceptance(tid, remove=["1"], force=True)
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[ ] 二"]

    def test_remove_multiple_indices_realigns_without_drift(
        self, tmp_ticket_factory, precondition_tmp_dir
    ):
        """移除多個 index 後，剩餘條目依原內容正確對位，不因刪除順序漂移。"""
        tid = tmp_ticket_factory(
            status="in_progress",
            acceptance=["[ ] 一", "[x] 二", "[ ] 三", "[x] 四", "[ ] 五"],
        )
        # 移除 index 2 與 4（皆已勾選，需 force）；若不由大到小刪除，
        # 刪除 index 2 後原 index 4 的內容會位移到 index 3，導致誤刪「三」
        rc = _call_set_acceptance(tid, remove=["2", "4"], force=True)
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, tid)
        assert acceptance == ["[ ] 一", "[ ] 三", "[ ] 五"]

    def test_remove_index_out_of_range_rejected(
        self, tmp_ticket_factory, precondition_tmp_dir, capsys
    ):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[ ] 一"])
        rc = _call_set_acceptance(tid, remove=["5"])
        assert rc == 1
        assert "超出範圍" in capsys.readouterr().out


class TestCompletedTicketProtection:
    """已 completed 票的 add/edit/remove 修訂需明確防護（沿用既有
    require_in_progress 前置檢查，check/uncheck 系列同款保護）。"""

    def test_add_on_completed_ticket_rejected_without_force(
        self, completed_ticket, precondition_tmp_dir, capsys
    ):
        before = (precondition_tmp_dir / f"{completed_ticket}.md").read_text(encoding="utf-8")
        rc = _call_set_acceptance(completed_ticket, add=["新條件"])
        assert rc == 2
        after = (precondition_tmp_dir / f"{completed_ticket}.md").read_text(encoding="utf-8")
        assert before == after
        assert "--force" in capsys.readouterr().err

    def test_add_on_completed_ticket_allowed_with_force(
        self, completed_ticket, precondition_tmp_dir, precondition_hook_logs_dir
    ):
        rc = _call_set_acceptance(completed_ticket, add=["新條件"], force=True)
        assert rc == 0
        acceptance = _read_acceptance(precondition_tmp_dir, completed_ticket)
        assert "[ ] 新條件" in acceptance

    def test_remove_on_completed_ticket_rejected_without_force(
        self, completed_ticket, precondition_tmp_dir
    ):
        rc = _call_set_acceptance(completed_ticket, remove=["1"])
        assert rc == 2


class TestModeExclusivity:
    def test_add_and_check_mutually_exclusive(self, tmp_ticket_factory, precondition_tmp_dir, capsys):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[ ] 一"])
        rc = _call_set_acceptance(tid, add=["新條件"], check=["1"])
        assert rc == 1
        assert "互斥" in capsys.readouterr().out

    def test_no_mode_specified_errors(self, tmp_ticket_factory, precondition_tmp_dir, capsys):
        tid = tmp_ticket_factory(status="in_progress", acceptance=["[ ] 一"])
        rc = _call_set_acceptance(tid)
        assert rc == 1
