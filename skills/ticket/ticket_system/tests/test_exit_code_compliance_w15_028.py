"""Tests for W15-028.2 — CLI exit code 三值分層合規（PC-096 防護）。

對照 .claude/references/cli-exit-code-rules.md：
- 0 = GO / SUCCESS
- 1 = INTERNAL_ERROR（exception / 程式 bug）
- 2 = BUSINESS_REJECT / NO-GO（業務拒絕 / 用戶輸入錯誤 / 查無資料）

覆蓋 4 個修復檔的關鍵分支（最低 acceptance：
audit ≥ 1×rc=2、acceptance ≥ 2×rc=2、batch ≥ 1×rc=2、dashboard ≥ 1×rc=2，本檔合計 7 個）。
"""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from ticket_system.commands import track_acceptance, track_audit, track_batch, track_dashboard


# ---------------------------------------------------------------------------
# track_audit.execute_audit
# ---------------------------------------------------------------------------

class _FakeAuditReport:
    def __init__(self, passed: bool):
        self.overall_passed = passed
        self.steps = []
        self.summary = ""


def test_audit_business_reject_returns_2(monkeypatch, capsys):
    """W15-028.2: audit 未通過屬業務拒絕（NO-GO），exit code 2。"""
    monkeypatch.setattr(track_audit, "run_audit", lambda tid, ver: _FakeAuditReport(False))
    # _format_audit_report 仰賴完整 report；patch 為簡單字串避免額外依賴
    monkeypatch.setattr(track_audit, "_format_audit_report", lambda report: "audit failed")

    args = argparse.Namespace(ticket_id="0.18.0-W15-028.2")
    rc = track_audit.execute_audit(args, "0.18.0")
    assert rc == 2
    out = capsys.readouterr().out
    assert "audit failed" in out


def test_audit_success_returns_0(monkeypatch, capsys):
    """audit 通過 → exit code 0（GO / SUCCESS）對照基線。"""
    monkeypatch.setattr(track_audit, "run_audit", lambda tid, ver: _FakeAuditReport(True))
    monkeypatch.setattr(track_audit, "_format_audit_report", lambda report: "audit passed")

    args = argparse.Namespace(ticket_id="0.18.0-W15-028.2")
    rc = track_audit.execute_audit(args, "0.18.0")
    assert rc == 0


def test_audit_internal_error_returns_1(monkeypatch, capsys):
    """audit 拋出非預期 exception → exit code 1（INTERNAL_ERROR）。"""
    def _raise(tid, ver):
        raise RuntimeError("simulated internal failure")

    monkeypatch.setattr(track_audit, "run_audit", _raise)

    args = argparse.Namespace(ticket_id="0.18.0-W15-028.2")
    rc = track_audit.execute_audit(args, "0.18.0")
    assert rc == 1


# ---------------------------------------------------------------------------
# track_acceptance.execute_check_acceptance
# ---------------------------------------------------------------------------

def test_acceptance_mutually_exclusive_flags_returns_2(capsys):
    """--all 與 index 同時提供 → 用戶輸入錯誤，exit code 2。"""
    args = argparse.Namespace(ticket_id="dummy", all=True, index="1", uncheck=False)
    rc = track_acceptance.execute_check_acceptance(args, "0.18.0")
    assert rc == 2


def test_acceptance_missing_index_returns_2(capsys):
    """既無 --all 也無 index → 用戶輸入錯誤，exit code 2。"""
    args = argparse.Namespace(ticket_id="dummy", all=False, index=None, uncheck=False)
    rc = track_acceptance.execute_check_acceptance(args, "0.18.0")
    assert rc == 2


def test_acceptance_ticket_not_found_returns_2(monkeypatch, capsys):
    """指定 ticket 不存在 → 用戶輸入錯誤，exit code 2。"""
    monkeypatch.setattr(
        track_acceptance,
        "load_and_validate_ticket",
        lambda version, tid: (None, "not found"),
    )
    args = argparse.Namespace(ticket_id="nonexistent", all=True, index=None, uncheck=False)
    rc = track_acceptance.execute_check_acceptance(args, "0.18.0")
    assert rc == 2


def test_acceptance_empty_acceptance_list_returns_2(monkeypatch, capsys):
    """ticket 存在但 acceptance 為空 → 業務拒絕（無條件可勾選），exit code 2。"""
    fake_ticket = {"acceptance": []}
    monkeypatch.setattr(
        track_acceptance,
        "load_and_validate_ticket",
        lambda version, tid: (fake_ticket, None),
    )
    args = argparse.Namespace(ticket_id="dummy", all=True, index=None, uncheck=False)
    rc = track_acceptance.execute_check_acceptance(args, "0.18.0")
    assert rc == 2


# ---------------------------------------------------------------------------
# track_batch._execute_batch_operation
# ---------------------------------------------------------------------------

def test_batch_no_valid_tickets_returns_2(monkeypatch, capsys):
    """批量操作收到空 ticket_ids → 用戶輸入錯誤，exit code 2。"""
    monkeypatch.setattr(track_batch, "_parse_ticket_ids", lambda x: [])

    args = argparse.Namespace(ticket_ids="", dry_run=False)
    rc = track_batch._execute_batch_operation(
        args=args,
        version="0.18.0",
        operation="claim",
        operation_name="Claim",
        result_message_key="dummy",
        processor=lambda t, tid: (True, "ok"),
    )
    assert rc == 2


def test_batch_complete_resolve_failure_returns_2(monkeypatch, capsys):
    """execute_batch_complete: _resolve_ticket_ids_for_complete 回 None → exit 2。"""
    monkeypatch.setattr(
        track_batch, "_resolve_ticket_ids_for_complete", lambda args, version: None
    )

    args = argparse.Namespace(ticket_ids=None, wave=None, parent=None, dry_run=False)
    rc = track_batch.execute_batch_complete(args, "0.18.0")
    assert rc == 2


# ---------------------------------------------------------------------------
# track_dashboard.dashboard_main
# ---------------------------------------------------------------------------

def _dashboard_ns(**overrides):
    defaults = dict(wave=None, top=None, stale_threshold=None, no_stale=False, format="text")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_dashboard_no_active_version_returns_2(capsys):
    """version is None → 查無資料屬業務拒絕，exit code 2。"""
    rc = track_dashboard.dashboard_main(_dashboard_ns(), None)
    err = capsys.readouterr().err
    assert rc == 2
    assert "No active version detected" in err


def test_dashboard_internal_load_failure_returns_1(monkeypatch, capsys):
    """list_tickets 拋 exception → INTERNAL_ERROR，exit code 1。"""
    def _raise(v):
        raise RuntimeError("simulated index load failure")

    monkeypatch.setattr(track_dashboard, "list_tickets", _raise)
    rc = track_dashboard.dashboard_main(_dashboard_ns(), "0.18.0")
    err = capsys.readouterr().err
    assert rc == 1
    assert "simulated index load failure" in err
