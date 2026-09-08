"""Tests for handoff --gc / --from-worklog stale 判定漏認 closed 狀態的修復
（0.2.1-W3-1312 item 2）。

Bug：`handoff_utils.is_handoff_stale()` 的 target 檢查只呼叫
`is_ticket_in_progress_or_completed`（僅 in_progress / completed 兩態），
未涵蓋 closed；`handoff._execute_from_worklog` 的 skip 判定也只比對
`STATUS_COMPLETED`。target/來源 ticket 被 closed 的 pending handoff 檔因此
永遠不會被判定為 stale，`--gc` 與 `--from-worklog` 都無法清理。

`is_handoff_stale` 是 --gc（`handoff_gc._collect_stale_handoffs`）與
`resume --list`（`resume.list_pending_handoffs`）共用的單一 stale 判定來源
（W17-163 L1-A），故本檔同時覆蓋兩個消費端，避免只修好一邊又漂移。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

from ticket_system.commands.handoff_gc import execute_gc, _collect_stale_handoffs
from ticket_system.lib.handoff_utils import is_handoff_stale


# ---------------------------------------------------------------------------
# Group A：is_handoff_stale 單元測試（--gc 與 resume --list 共用的判定來源）
# ---------------------------------------------------------------------------

class TestIsHandoffStaleClosedTarget:

    @patch("ticket_system.lib.handoff_utils._load_ticket_status")
    def test_target_closed_is_stale(self, mock_status):
        """任務鏈 handoff，target 已 closed → 應判定 stale（現行行為僅認
        in_progress/completed，closed 會被誤判為非 stale）。"""
        mock_status.return_value = "closed"
        record = {
            "ticket_id": "0.18.0-W6-001",
            "direction": "to-sibling:0.18.0-W6-002",
            "from_status": "completed",
        }
        is_stale, reason = is_handoff_stale(record)
        assert is_stale is True
        assert "0.18.0-W6-002" in reason
        assert "closed" in reason

    @patch("ticket_system.lib.handoff_utils._load_ticket_status")
    def test_target_pending_not_stale(self, mock_status):
        """target 仍 pending（未 closed/completed/in_progress）→ 非 stale，
        修復不可過度放寬既有規則。"""
        mock_status.return_value = "pending"
        record = {
            "ticket_id": "0.18.0-W6-003",
            "direction": "to-sibling:0.18.0-W6-004",
            "from_status": "completed",
        }
        is_stale, _reason = is_handoff_stale(record)
        assert is_stale is False


# ---------------------------------------------------------------------------
# Group B：--gc --dry-run 對 target closed 的 pending 檔列為 stale（acceptance）
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_gc_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        handoff_pending = project_root / ".claude" / "handoff" / "pending"
        handoff_archive = project_root / ".claude" / "handoff" / "archive"
        handoff_pending.mkdir(parents=True, exist_ok=True)
        (project_root / "pubspec.yaml").touch()

        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)

        try:
            yield project_root, handoff_pending, handoff_archive
        finally:
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


def _write_handoff(pending_dir: Path, ticket_id: str, direction: str, from_status: str = "in_progress") -> Path:
    data = {
        "ticket_id": ticket_id,
        "direction": direction,
        "timestamp": "2026-09-08T12:00:00",
        "from_status": from_status,
        "title": "Test",
    }
    path = pending_dir / f"{ticket_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


class TestGcDryRunClosedTarget:

    @patch("ticket_system.lib.handoff_utils._load_ticket_status")
    def test_gc_dry_run_lists_closed_target_as_stale(self, mock_status, temp_gc_env, capsys):
        _project_root, pending, _archive = temp_gc_env
        mock_status.return_value = "closed"
        _write_handoff(pending, "0.18.0-W6-005", "to-sibling:0.18.0-W6-006")

        rc = execute_gc(dry_run=True)
        out = capsys.readouterr().out

        assert rc == 0
        assert "0.18.0-W6-005" in out
        assert "1 個 stale handoff" in out

    @patch("ticket_system.lib.handoff_utils._load_ticket_status")
    def test_collect_stale_handoffs_closed_target(self, mock_status, temp_gc_env):
        _project_root, pending, _archive = temp_gc_env
        mock_status.return_value = "closed"
        _write_handoff(pending, "0.18.0-W6-007", "to-child:0.18.0-W6-008")

        result = _collect_stale_handoffs()
        assert len(result) == 1
        assert result[0][1] == "0.18.0-W6-007"


# ---------------------------------------------------------------------------
# Group C：--from-worklog 對來源 ticket 已 closed 應 SKIP（現行只認 completed）
# ---------------------------------------------------------------------------

def _run_from_worklog(
    monkeypatch,
    *,
    worklog_path: Path,
    ticket_status_map: Optional[dict] = None,
    active_version: Optional[str] = "0.18.0",
) -> tuple[int, str, str]:
    from ticket_system.commands import handoff as handoff_mod

    ticket_status_map = ticket_status_map or {}

    def fake_load_ticket(version, tid):
        if tid in ticket_status_map:
            return {"id": tid, "status": ticket_status_map[tid]}
        return None

    monkeypatch.setattr(handoff_mod, "load_ticket", fake_load_ticket)
    monkeypatch.setattr(
        "ticket_system.lib.version.get_current_version",
        lambda: active_version,
    )

    from ticket_system.lib import constants

    fake_root = Path("/tmp/_fake_root_test_1312")
    monkeypatch.setattr(handoff_mod, "get_ticket_state_root", lambda: fake_root)

    real_exists = Path.exists

    def fake_path_exists(self):
        try:
            self.relative_to(
                fake_root / constants.HANDOFF_DIR / constants.HANDOFF_PENDING_SUBDIR
            )
            return False  # 無既有 pending handoff
        except ValueError:
            pass
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", fake_path_exists)

    calls: list = []

    def fake_execute_handoff(args):
        calls.append(args.ticket_id)
        return 0

    monkeypatch.setattr(handoff_mod, "_execute_handoff", fake_execute_handoff)

    args = argparse.Namespace(worklog_path=worklog_path, dry_run=False)

    out_buf, err_buf = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        rc = handoff_mod._execute_from_worklog(args)
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


class TestFromWorklogSkipClosed:

    def test_skip_closed_ticket(self, tmp_path, monkeypatch):
        """來源 ticket 已 closed（非 completed）→ 現行行為不 SKIP，會誤嘗試對
        已關閉票建立 handoff；修復後應與 completed 同樣被 SKIP。"""
        worklog = tmp_path / "v0.18.0-main.md"
        worklog.write_text(
            "## Handoff Context\n\nW17-079 已關閉\n",
            encoding="utf-8",
        )

        rc, out, _err = _run_from_worklog(
            monkeypatch,
            worklog_path=worklog,
            ticket_status_map={"0.18.0-W17-079": "closed"},
        )

        assert rc == 0
        assert "[SKIP]" in out
        assert "closed" in out
