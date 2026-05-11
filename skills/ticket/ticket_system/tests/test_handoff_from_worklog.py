"""Tests for ticket handoff --from-worklog (W17-083.2 S2).

對應 W17-083 Phase 2 sage §S2 8 測試案例（S2-T01 ~ S2-T08）。

測試 _execute_from_worklog() CLI 邏輯：
- worklog 解析 + handoff 關鍵字偵測 + ticket ID 提取
- 對每個 ID 處理 dry-run / 已 pending / completed / 不存在 / 實際建檔

策略：
- 用 monkeypatch 攔截 _execute_handoff（避免實際建檔污染環境，與 _execute_handoff 自身單元測試解耦）
- 用 monkeypatch 攔截 load_ticket 模擬 ticket 狀態
- worklog 用 tmp_path 建真實檔案
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_from_worklog(
    monkeypatch,
    *,
    worklog_path: Optional[Path] = None,
    dry_run: bool = False,
    pending_ids: Optional[set[str]] = None,
    ticket_status_map: Optional[dict] = None,
    handoff_calls: Optional[list] = None,
    active_version: Optional[str] = "0.18.0",
) -> tuple[int, str, str]:
    """執行 _execute_from_worklog，回傳 (rc, stdout, stderr).

    Args:
        worklog_path: --worklog-path 引數值；None 走 auto-detect
        pending_ids: 模擬已存在的 pending handoff 的 ticket ID 集合
        ticket_status_map: {ticket_id: status} 模擬 load_ticket 回傳
        handoff_calls: 收集 _execute_handoff 呼叫記錄的 list
    """
    from ticket_system.commands import handoff as handoff_mod

    pending_ids = pending_ids or set()
    ticket_status_map = ticket_status_map or {}
    handoff_calls = handoff_calls if handoff_calls is not None else []

    # Mock load_ticket：回傳 dict 含 status
    def fake_load_ticket(version, tid):
        if tid in ticket_status_map:
            return {"id": tid, "status": ticket_status_map[tid]}
        return None

    monkeypatch.setattr(handoff_mod, "load_ticket", fake_load_ticket)

    # Mock get_current_version
    monkeypatch.setattr(
        "ticket_system.lib.version.get_current_version",
        lambda: active_version,
    )

    # Mock get_project_root + pending dir 檢查
    # 直接 mock pending_dir 路徑檢查邏輯：用 monkeypatch 替換 Path.exists
    from ticket_system.lib import constants

    fake_root = Path("/tmp/_fake_root_test")
    monkeypatch.setattr(handoff_mod, "get_project_root", lambda: fake_root)

    real_exists = Path.exists

    def fake_path_exists(self):
        # pending dir json 檔案：檢查 pending_ids
        try:
            rel = self.relative_to(
                fake_root / constants.HANDOFF_DIR / constants.HANDOFF_PENDING_SUBDIR
            )
            stem = rel.name[:-5] if rel.name.endswith(".json") else rel.name
            return stem in pending_ids
        except ValueError:
            pass
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", fake_path_exists)

    # Mock _execute_handoff
    def fake_execute_handoff(args):
        handoff_calls.append(args.ticket_id)
        return 0

    monkeypatch.setattr(handoff_mod, "_execute_handoff", fake_execute_handoff)

    args = argparse.Namespace(
        worklog_path=worklog_path,
        dry_run=dry_run,
    )

    out_buf, err_buf = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        rc = handoff_mod._execute_from_worklog(args)
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


# ---------------------------------------------------------------------------
# S2-T01 ~ S2-T08
# ---------------------------------------------------------------------------


class TestHandoffFromWorklog:

    def test_t01_dry_run_lists_suggestions(self, tmp_path, monkeypatch):
        """S2-T01：dry-run 列出建議命令，不實際建檔"""
        worklog = tmp_path / "v0.18.0-main.md"
        worklog.write_text(
            "## 下個 Session 接手 Context\n\nW17-079 與 W17-080 待處理\n",
            encoding="utf-8",
        )

        calls = []
        rc, out, err = _run_from_worklog(
            monkeypatch,
            worklog_path=worklog,
            dry_run=True,
            ticket_status_map={
                "0.18.0-W17-079": "in_progress",
                "0.18.0-W17-080": "pending",
            },
            handoff_calls=calls,
        )

        assert rc == 0
        assert "[DRY-RUN]" in out
        assert "0.18.0-W17-079" in out
        assert "0.18.0-W17-080" in out
        assert calls == []  # dry-run 不呼叫 _execute_handoff

    def test_t02_actual_execution_creates_pending(self, tmp_path, monkeypatch):
        """S2-T02：實際執行呼叫 _execute_handoff 建檔"""
        worklog = tmp_path / "v0.18.0-main.md"
        worklog.write_text(
            "## Handoff Context\n\nW17-079 待處理\n",
            encoding="utf-8",
        )

        calls = []
        rc, out, err = _run_from_worklog(
            monkeypatch,
            worklog_path=worklog,
            ticket_status_map={"0.18.0-W17-079": "in_progress"},
            handoff_calls=calls,
        )

        assert rc == 0
        assert calls == ["0.18.0-W17-079"]
        assert "[OK] 0.18.0-W17-079" in out

    def test_t03_skip_existing_pending(self, tmp_path, monkeypatch):
        """S2-T03：已存在 pending handoff 跳過"""
        worklog = tmp_path / "v0.18.0-main.md"
        worklog.write_text(
            "## Session Handoff\n\nW17-079 待處理\n",
            encoding="utf-8",
        )

        calls = []
        rc, out, err = _run_from_worklog(
            monkeypatch,
            worklog_path=worklog,
            pending_ids={"0.18.0-W17-079"},
            ticket_status_map={"0.18.0-W17-079": "in_progress"},
            handoff_calls=calls,
        )

        assert rc == 0
        assert "[SKIP]" in out
        assert "0.18.0-W17-079" in out
        assert "已存在 pending handoff" in out
        assert calls == []

    def test_t04_auto_detect_worklog(self, tmp_path, monkeypatch):
        """S2-T04：未傳 --worklog-path 時自動偵測 active version worklog"""
        worklog = tmp_path / "v0.18.0-main.md"
        worklog.write_text(
            "## Handoff Context\n\nW17-079 待處理\n",
            encoding="utf-8",
        )

        # Mock find_worklog_path 回傳 tmp 路徑
        from ticket_system.commands import handoff as handoff_mod

        monkeypatch.setattr(
            "ticket_system.lib.worklog_parser.find_worklog_path",
            lambda v: worklog,
        )

        calls = []
        rc, out, err = _run_from_worklog(
            monkeypatch,
            worklog_path=None,  # auto-detect
            ticket_status_map={"0.18.0-W17-079": "in_progress"},
            handoff_calls=calls,
        )

        assert rc == 0
        assert calls == ["0.18.0-W17-079"]

    def test_t05_worklog_not_exist(self, tmp_path, monkeypatch):
        """S2-T05：--worklog-path 指向不存在路徑 → exit != 0 + stderr 錯誤"""
        missing = tmp_path / "nonexistent.md"

        calls = []
        rc, out, err = _run_from_worklog(
            monkeypatch,
            worklog_path=missing,
            handoff_calls=calls,
        )

        assert rc != 0
        assert "不存在" in err or "不存在" in out
        assert calls == []

    def test_t06_no_handoff_keyword(self, tmp_path, monkeypatch):
        """S2-T06：worklog 無 handoff 關鍵字 → exit 0 + 提示訊息"""
        worklog = tmp_path / "v0.18.0-main.md"
        worklog.write_text(
            "## 一般工作日誌\n\n今天修了一個 bug\n",
            encoding="utf-8",
        )

        calls = []
        rc, out, err = _run_from_worklog(
            monkeypatch,
            worklog_path=worklog,
            handoff_calls=calls,
        )

        assert rc == 0
        assert "未偵測到 handoff" in out
        assert calls == []

    def test_t07_skip_completed_ticket(self, tmp_path, monkeypatch):
        """S2-T07：ticket 狀態為 completed → 跳過"""
        worklog = tmp_path / "v0.18.0-main.md"
        worklog.write_text(
            "## Handoff Context\n\nW17-079 已完成\n",
            encoding="utf-8",
        )

        calls = []
        rc, out, err = _run_from_worklog(
            monkeypatch,
            worklog_path=worklog,
            ticket_status_map={"0.18.0-W17-079": "completed"},
            handoff_calls=calls,
        )

        assert rc == 0
        assert "[SKIP]" in out
        assert "已 completed" in out
        assert calls == []

    def test_t08_ticket_not_found_no_block(self, tmp_path, monkeypatch):
        """S2-T08：ticket 不存在 → 列 [FAIL] 但不阻塞其他 ticket"""
        worklog = tmp_path / "v0.18.0-main.md"
        worklog.write_text(
            "## Handoff Context\n\nW99-999 與 W17-080 待處理\n",
            encoding="utf-8",
        )

        calls = []
        rc, out, err = _run_from_worklog(
            monkeypatch,
            worklog_path=worklog,
            ticket_status_map={"0.18.0-W17-080": "in_progress"},  # W99-999 未模擬
            handoff_calls=calls,
        )

        assert rc == 0
        assert "[FAIL]" in out
        assert "0.18.0-W99-999" in out
        # W17-080 仍應被處理（不被 W99-999 失敗阻塞）
        assert calls == ["0.18.0-W17-080"]
