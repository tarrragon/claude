"""W3-044 S5 — set-acceptance CLI precondition 整合測試（B6-B10 + E2）。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest


def _call_set_acceptance(
    ticket_id: str,
    check: list[str] | None = None,
    force: bool = False,
) -> int:
    from ticket_system.commands.track_set_acceptance import execute_set_acceptance

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        check=check or ["1"],
        uncheck=None,
        all_check=False,
        all_uncheck=False,
        force=force,
    )
    return execute_set_acceptance(ns, "0.0.0")


class TestSetAcceptancePrecondition:
    """B6-B10 + E2：set-acceptance × status × force 矩陣。"""

    def test_B6_pending_rejects(self, pending_ticket, precondition_tmp_dir, capsys):
        before = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        rc = _call_set_acceptance(pending_ticket)
        assert rc == 2
        after = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        assert before == after
        captured = capsys.readouterr()
        assert "claim" in captured.err

    def test_B7_in_progress_passes(self, in_progress_ticket, precondition_tmp_dir):
        rc = _call_set_acceptance(in_progress_ticket)
        assert rc == 0

    def test_B8_completed_rejects_no_allow(
        self, completed_ticket, precondition_tmp_dir, capsys
    ):
        """set-acceptance 不允許 completed（allow_completed=False）。"""
        before = (precondition_tmp_dir / f"{completed_ticket}.md").read_text(encoding="utf-8")
        rc = _call_set_acceptance(completed_ticket)
        assert rc == 2
        after = (precondition_tmp_dir / f"{completed_ticket}.md").read_text(encoding="utf-8")
        assert before == after
        captured = capsys.readouterr()
        # E2: stderr 含 reopen 與 --force 提示
        assert "reopen" in captured.err
        assert "--force" in captured.err

    def test_B9_blocked_rejects(self, blocked_ticket, precondition_tmp_dir, capsys):
        rc = _call_set_acceptance(blocked_ticket)
        assert rc == 2
        captured = capsys.readouterr()
        assert "release" in captured.err

    def test_B10_completed_force_passes(
        self,
        completed_ticket,
        precondition_tmp_dir,
        precondition_hook_logs_dir,
        capsys,
    ):
        rc = _call_set_acceptance(completed_ticket, force=True)
        assert rc == 0
        log_file = precondition_hook_logs_dir / "cli-force-usage.jsonl"
        assert log_file.exists()
        record = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert record["operation"] == "set-acceptance"
        assert record["status_at_time"] == "completed"
