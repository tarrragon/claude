"""W3-044 S7 — precondition × file_lock 互動測試（D1-D2）。

驗證：
- D1：require_in_progress 拒絕時 fcntl 鎖正確釋放（後續操作可成功）
- D2：--force 旁路後 mutation 正常執行 + lock 釋放

注意：file_lock 設計上保留 .lock sentinel file（不刪除），但 fcntl 鎖會釋放；
驗收方式為「後續操作可成功完成」而非「sentinel file 不存在」。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest


def _call_append_log(ticket_id: str, force: bool = False) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        section="Solution",
        content="lock test",
        force=force,
    )
    return execute_append_log(ns, "0.0.0")


class TestPreconditionLockSafety:
    """D1-D2：file_lock 在 precondition 路徑下的釋放契約。"""

    def test_D1_lock_released_after_rejection(
        self, pending_ticket, precondition_tmp_dir
    ):
        """D1: 拒絕後 fcntl 鎖已釋放，後續操作可立即取得 lock 完成。"""
        rc = _call_append_log(pending_ticket)
        assert rc == 2

        # 將 status 改為 in_progress 後第二次 append-log 應成功
        # （若 fcntl lock 未釋放會 block 或失敗）
        ticket_path = precondition_tmp_dir / f"{pending_ticket}.md"
        content = ticket_path.read_text(encoding="utf-8")
        content = content.replace("status: pending", "status: in_progress")
        ticket_path.write_text(content, encoding="utf-8")

        rc2 = _call_append_log(pending_ticket)
        assert rc2 == 0

    def test_D2_force_bypass_mutation_persists_and_lock_released(
        self, pending_ticket, precondition_tmp_dir, precondition_hook_logs_dir
    ):
        """D2: --force 旁路後 mutation 生效 + lock 釋放（後續 force 仍可成功）。"""
        rc = _call_append_log(pending_ticket, force=True)
        assert rc == 0

        body = (precondition_tmp_dir / f"{pending_ticket}.md").read_text(encoding="utf-8")
        assert "lock test" in body

        # 第二次 force append-log 仍可成功
        rc2 = _call_append_log(pending_ticket, force=True)
        assert rc2 == 0
