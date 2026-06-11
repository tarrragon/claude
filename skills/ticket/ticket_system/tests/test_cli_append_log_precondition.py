"""W3-044 S3 — append-log CLI precondition 整合測試（B1-B5 + E1）。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest


def _call_append_log(
    ticket_id: str,
    section: str = "Solution",
    content: str = "test content",
    force: bool = False,
) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(
        ticket_id=ticket_id, section=section, content=content, force=force
    )
    return execute_append_log(ns, "0.0.0")


class TestAppendLogPrecondition:
    """B1-B5 + E1：append-log entry × status × force 矩陣。"""

    def test_B1_pending_rejects(self, pending_ticket, precondition_tmp_dir, capsys):
        before = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        rc = _call_append_log(pending_ticket)
        assert rc == 2
        # ticket md 不變
        after = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        assert before == after
        # stderr 含建議
        captured = capsys.readouterr()
        assert "claim" in captured.err
        # E1：訊息含 status=pending 與 in_progress 提示
        assert "status=pending" in captured.err
        assert "in_progress" in captured.err

    def test_B2_in_progress_passes(self, in_progress_ticket, precondition_tmp_dir):
        rc = _call_append_log(in_progress_ticket, content="實際內容 B2")
        assert rc == 0
        body = (precondition_tmp_dir / f"{in_progress_ticket}.md").read_text(encoding="utf-8")
        assert "實際內容 B2" in body

    def test_B3_completed_passes_with_allow_completed(
        self, completed_ticket, precondition_tmp_dir
    ):
        """completed 路徑允許 append-log 補 review。"""
        rc = _call_append_log(completed_ticket, content="補 review 評論")
        assert rc == 0
        body = (precondition_tmp_dir / f"{completed_ticket}.md").read_text(encoding="utf-8")
        assert "補 review 評論" in body

    def test_B4_blocked_rejects(self, blocked_ticket, precondition_tmp_dir, capsys):
        before = (precondition_tmp_dir / f"{blocked_ticket}.md").read_text(encoding="utf-8")
        rc = _call_append_log(blocked_ticket)
        assert rc == 2
        after = (precondition_tmp_dir / f"{blocked_ticket}.md").read_text(encoding="utf-8")
        assert before == after
        captured = capsys.readouterr()
        assert "release" in captured.err

    def test_B5_pending_with_force_passes_logs_warning(
        self,
        pending_ticket,
        precondition_tmp_dir,
        precondition_hook_logs_dir,
        capsys,
    ):
        rc = _call_append_log(pending_ticket, content="force 寫入", force=True)
        assert rc == 0
        # ticket md 變更生效
        body = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        assert "force 寫入" in body

        # stderr warning + hook-logs
        captured = capsys.readouterr()
        assert "--force" in captured.err

        log_file = precondition_hook_logs_dir / "cli-force-usage.jsonl"
        assert log_file.exists()
        record = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert record["ticket_id"] == pending_ticket
        assert record["operation"] == "append-log"
        assert record["status_at_time"] == "pending"


class TestAppendLogPreDispatchSections:
    """W1-058：派發前章節（Problem Analysis / Context Bundle）pending 直寫。"""

    def test_pending_problem_analysis_passes_without_force(
        self, pending_ticket, precondition_tmp_dir, precondition_hook_logs_dir, capsys
    ):
        """pending + Problem Analysis → 不需 --force 即可寫入（既有章節 append）。"""
        rc = _call_append_log(
            pending_ticket, section="Problem Analysis", content="派發前根因分析"
        )
        assert rc == 0
        body = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        assert "派發前根因分析" in body

        # 不發 status 阻擋訊息、不記 force log（合法 bookkeeping 路徑）
        captured = capsys.readouterr()
        assert "status=pending" not in captured.err
        assert "--force" not in captured.err
        assert not (precondition_hook_logs_dir / "cli-force-usage.jsonl").exists()

    def test_pending_context_bundle_passes_with_autocreate(
        self, pending_ticket, precondition_tmp_dir, precondition_hook_logs_dir, capsys
    ):
        """pending + Context Bundle → 通過且觸發 W1-025 缺失章節自動補建。"""
        rc = _call_append_log(
            pending_ticket, section="Context Bundle", content="### 派發前置資訊"
        )
        assert rc == 0
        body = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        assert "## Context Bundle" in body
        assert "### 派發前置資訊" in body
        assert not (precondition_hook_logs_dir / "cli-force-usage.jsonl").exists()

    def test_pending_solution_still_rejects(
        self, pending_ticket, precondition_tmp_dir, capsys
    ):
        """執行產出章節（Solution）維持 in_progress 限制（W3-044 不變）。"""
        rc = _call_append_log(pending_ticket, section="Solution", content="不應寫入")
        assert rc == 2
        body = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        assert "不應寫入" not in body
        captured = capsys.readouterr()
        assert "claim" in captured.err

    def test_pending_test_results_still_rejects(self, pending_ticket, capsys):
        """執行產出章節（Test Results）維持 in_progress 限制。"""
        rc = _call_append_log(pending_ticket, section="Test Results", content="x")
        assert rc == 2
        captured = capsys.readouterr()
        assert "status=pending" in captured.err

    def test_pending_pre_dispatch_with_force_still_logs(
        self, pending_ticket, precondition_hook_logs_dir, capsys
    ):
        """既有 --force 行為不變：即使章節屬派發前章節，帶 --force 仍記 audit。"""
        rc = _call_append_log(
            pending_ticket,
            section="Problem Analysis",
            content="force 路徑",
            force=True,
        )
        assert rc == 0
        log_file = precondition_hook_logs_dir / "cli-force-usage.jsonl"
        assert log_file.exists()
        record = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert record["operation"] == "append-log"
        assert record["status_at_time"] == "pending"
        captured = capsys.readouterr()
        assert "--force" in captured.err

    def test_in_progress_pre_dispatch_passes(
        self, in_progress_ticket, precondition_tmp_dir
    ):
        """in_progress + 派發前章節 → 照常通過（回歸防護）。"""
        rc = _call_append_log(
            in_progress_ticket, section="Problem Analysis", content="執行中補充分析"
        )
        assert rc == 0
        body = (precondition_tmp_dir / f"{in_progress_ticket}.md").read_text(
            encoding="utf-8"
        )
        assert "執行中補充分析" in body

    def test_blocked_pre_dispatch_still_rejects(self, blocked_ticket, capsys):
        """blocked + 派發前章節 → 仍被擋（allow_pending 僅放行 pending）。"""
        rc = _call_append_log(blocked_ticket, section="Context Bundle", content="x")
        assert rc == 2
        captured = capsys.readouterr()
        assert "release" in captured.err
