"""W3-044 S6 — complete CLI precondition 整合測試（B11-B15）。

complete 邏輯複雜（acceptance + body schema + spawned）；本檔聚焦驗證
precondition 行為（exit 2 拒絕 / force 旁路 / 與既有 short-circuit 互動），
不涵蓋完整 complete 流程（既有 lifecycle 測試已覆蓋）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest


def _call_complete(
    ticket_id: str,
    force: bool = False,
    yes_spawned: bool = True,
    skip_body_check: bool = True,
    no_stage: bool = True,
) -> int:
    from ticket_system.commands.lifecycle import execute_complete

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        yes_spawned=yes_spawned,
        skip_body_check=skip_body_check,
        force=force,
        no_stage=no_stage,
    )
    return execute_complete(ns, "0.0.0")


class TestCompletePrecondition:
    """B11-B15：complete × status × force 矩陣。"""

    def test_B11_pending_rejects_exit_2(
        self, pending_ticket, precondition_tmp_dir, capsys, monkeypatch
    ):
        """pending → exit 2（precondition 拒絕，區分於既有 blocked exit 1）。"""
        # Patch lifecycle ticket_loader to use precondition fixtures
        from ticket_system.commands import lifecycle as lifecycle_mod
        from ticket_system.lib.parser import parse_frontmatter

        def _fake_get_ticket_path(version, tid):
            return precondition_tmp_dir / f"{tid}.md"

        def _fake_load_and_validate_ticket(version, tid):
            path = precondition_tmp_dir / f"{tid}.md"
            if not path.exists():
                return None, "not found"
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            fm["_body"] = body
            fm["_path"] = str(path)
            return fm, None

        monkeypatch.setattr(lifecycle_mod, "get_ticket_path", _fake_get_ticket_path)
        monkeypatch.setattr(
            lifecycle_mod, "load_and_validate_ticket", _fake_load_and_validate_ticket
        )

        rc = _call_complete(pending_ticket)
        assert rc == 2
        captured = capsys.readouterr()
        assert "claim" in captured.err
        assert "status=pending" in captured.err

    def test_B13_already_complete_short_circuit(
        self, completed_ticket, precondition_tmp_dir, capsys, monkeypatch
    ):
        """B13: completed 走既有 is_already_complete short-circuit → exit 0（不被 precondition 攔截）。"""
        from ticket_system.commands import lifecycle as lifecycle_mod
        from ticket_system.lib.parser import parse_frontmatter

        def _fake_get_ticket_path(version, tid):
            return precondition_tmp_dir / f"{tid}.md"

        def _fake_load_and_validate_ticket(version, tid):
            path = precondition_tmp_dir / f"{tid}.md"
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            fm["_body"] = body
            fm["_path"] = str(path)
            # completed ticket 需 completed_at 才會 is_already_complete=True
            if not fm.get("completed_at"):
                fm["completed_at"] = "2026-05-25T00:00:00"
            return fm, None

        monkeypatch.setattr(lifecycle_mod, "get_ticket_path", _fake_get_ticket_path)
        monkeypatch.setattr(
            lifecycle_mod, "load_and_validate_ticket", _fake_load_and_validate_ticket
        )

        rc = _call_complete(completed_ticket)
        # is_already_complete 短路 → exit 0
        assert rc == 0

    def test_B15_pending_with_force_bypasses_precondition(
        self,
        pending_ticket,
        precondition_tmp_dir,
        precondition_hook_logs_dir,
        capsys,
        monkeypatch,
    ):
        """B15: --force 旁路 precondition；後續 validate_completable_status 仍可阻擋。

        本 case 只驗證 precondition 不擋（即不再 exit 2，可能進入後續流程）。
        force 同時用於 children-bypass 語義合併（W3-044 spec §R1）。
        """
        from ticket_system.commands import lifecycle as lifecycle_mod
        from ticket_system.lib.parser import parse_frontmatter

        def _fake_get_ticket_path(version, tid):
            return precondition_tmp_dir / f"{tid}.md"

        def _fake_load_and_validate_ticket(version, tid):
            path = precondition_tmp_dir / f"{tid}.md"
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            fm["_body"] = body
            fm["_path"] = str(path)
            return fm, None

        monkeypatch.setattr(lifecycle_mod, "get_ticket_path", _fake_get_ticket_path)
        monkeypatch.setattr(
            lifecycle_mod, "load_and_validate_ticket", _fake_load_and_validate_ticket
        )

        rc = _call_complete(pending_ticket, force=True)
        # precondition 不再 exit 2；後續流程可能因 validate_completable_status(pending)
        # 失敗回傳 1，但不是 precondition 的 exit 2
        assert rc != 2

        # hook-logs 記錄 force 使用
        log_file = precondition_hook_logs_dir / "cli-force-usage.jsonl"
        assert log_file.exists()
        record = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert record["operation"] == "complete"
        assert record["status_at_time"] == "pending"
