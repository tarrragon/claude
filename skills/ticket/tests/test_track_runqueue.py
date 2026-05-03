"""
測試 ticket track runqueue 命令（W17-011.1 / W17-009 落地）。

覆蓋 runqueue 統一 scheduler CLI 的核心行為：
- --format=list：blockedBy=[] 且 status=pending 的可執行清單，priority 排序
- --format=dag：拓撲層級分組（完整 DAG，含 blocked）
- --format=critical-path：僅關鍵路徑節點（slack=0）
- --top N：list / critical-path 生效，dag 忽略
- --context=resume：與 .claude/handoff/pending/ 交集
- --wave N：wave 過濾
- 復用 CriticalPathAnalyzer / CycleDetector（禁止重寫拓撲/CPM/環檢測）
- 禁止 --nice 參數
- register 走 track.py _create_command_handlers()

Note: 實作應復用 ticket_system.lib.critical_path 與 cycle_detector；測試以
      Monkeypatch ticket loader 與 handoff scanner 的方式驗證行為。
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ticket(
    ticket_id: str,
    *,
    status: str = "pending",
    blocked_by: List[str] | None = None,
    priority: str = "P1",
    wave: int = 17,
) -> Dict:
    return {
        "id": ticket_id,
        "status": status,
        "blockedBy": blocked_by or [],
        "priority": priority,
        "wave": wave,
        "title": f"Title for {ticket_id}",
        "type": "IMP",
    }


def _run(args: argparse.Namespace) -> tuple[int, str]:
    """Invoke execute_runqueue and capture stdout."""
    from ticket_system.commands.track_runqueue import execute_runqueue

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_runqueue(args, "0.18.0")
    return rc, buf.getvalue()


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        operation="runqueue",
        format="list",
        top=None,
        context=None,
        wave=None,
        status="pending",
        version=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunqueueList:
    """--format=list：blockedBy=[] 且 status=pending 的可執行清單"""

    def test_list_returns_unblocked_pending_only(self):
        tickets = [
            _make_ticket("0.18.0-W17-001", blocked_by=[]),
            _make_ticket("0.18.0-W17-002", blocked_by=["0.18.0-W17-001"]),
            _make_ticket("0.18.0-W17-003", blocked_by=[], status="completed"),
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "0.18.0-W17-001" in out
        assert "0.18.0-W17-002" not in out  # blocked
        assert "0.18.0-W17-003" not in out  # completed

    def test_list_sorted_by_priority_p0_first(self):
        tickets = [
            _make_ticket("TIX-ALPHA", priority="P2", blocked_by=[]),
            _make_ticket("TIX-BETA", priority="P0", blocked_by=[]),
            _make_ticket("TIX-GAMMA", priority="P1", blocked_by=[]),
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        idx_beta = out.find("TIX-BETA")
        idx_gamma = out.find("TIX-GAMMA")
        idx_alpha = out.find("TIX-ALPHA")
        assert idx_beta < idx_gamma < idx_alpha, (
            f"P0→P1→P2 ordering violated: {out}"
        )

    def test_list_empty_returns_zero_with_notice(self):
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=[],
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        # Non-empty message so user sees feedback
        assert len(out) > 0

    def test_list_filter_by_wave(self):
        tickets = [
            _make_ticket("WAVE17-A", wave=17, blocked_by=[]),
            _make_ticket("WAVE18-B", wave=18, blocked_by=[]),
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list", wave=17))
        assert rc == 0
        assert "WAVE17-A" in out
        assert "WAVE18-B" not in out


class TestRunqueueTop:
    """--top N 在 list / critical-path 生效"""

    def test_top_limits_list_count(self):
        tickets = [
            _make_ticket(f"T{i}", priority="P1", blocked_by=[]) for i in range(5)
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list", top=2))
        assert rc == 0
        # At least 3 of 5 must be absent (only top-2 shown)
        absent = sum(1 for i in range(5) if f"T{i}" not in out)
        assert absent >= 3, f"--top=2 should hide >=3 items, got out={out}"

    def test_top_ignored_in_dag(self):
        """dag 格式忽略 --top（展示完整 DAG）"""
        tickets = [
            _make_ticket(f"T{i}", priority="P1", blocked_by=[]) for i in range(4)
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="dag", top=1))
        assert rc == 0
        for i in range(4):
            assert f"T{i}" in out, f"dag --top=1 should not hide T{i}: {out}"


class TestRunqueueDag:
    """--format=dag：拓撲層級分組，呈現 blockedBy 鏈"""

    def test_dag_shows_all_levels(self):
        tickets = [
            _make_ticket("NODE-ALPHA", blocked_by=[]),
            _make_ticket("NODE-BETA", blocked_by=["NODE-ALPHA"]),
            _make_ticket("NODE-GAMMA", blocked_by=["NODE-BETA"]),
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="dag"))
        assert rc == 0
        assert "NODE-ALPHA" in out
        assert "NODE-BETA" in out
        assert "NODE-GAMMA" in out

    def test_dag_includes_blocked_tickets(self):
        """dag 視圖含 blockedBy 非空的 ticket（與 list 不同）"""
        tickets = [
            _make_ticket("ROOT", blocked_by=[]),
            _make_ticket("CHILD", blocked_by=["ROOT"]),
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="dag"))
        assert rc == 0
        assert "CHILD" in out


class TestRunqueueCriticalPath:
    """--format=critical-path：僅 slack=0 節點"""

    def test_critical_path_linear_chain(self):
        tickets = [
            _make_ticket("CPN-ALPHA", blocked_by=[]),
            _make_ticket("CPN-BETA", blocked_by=["CPN-ALPHA"]),
            _make_ticket("CPN-GAMMA", blocked_by=["CPN-BETA"]),
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="critical-path"))
        assert rc == 0
        assert "CPN-ALPHA" in out
        assert "CPN-BETA" in out
        assert "CPN-GAMMA" in out

    def test_critical_path_reuses_analyzer(self):
        """驗證呼叫 CriticalPathAnalyzer.analyze（非重寫演算法）"""
        tickets = [_make_ticket("A", blocked_by=[])]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ), patch(
            "ticket_system.commands.track_runqueue.CriticalPathAnalyzer.analyze",
            wraps=__import__(
                "ticket_system.lib.critical_path",
                fromlist=["CriticalPathAnalyzer"],
            ).CriticalPathAnalyzer.analyze,
        ) as spy:
            rc, _ = _run(_args(format="critical-path"))
        assert rc == 0
        assert spy.called, "execute_runqueue 必須呼叫 CriticalPathAnalyzer.analyze"


class TestRunqueueContextResume:
    """--context=resume：與 .claude/handoff/pending/ 交集"""

    def test_context_resume_intersects_handoff(self, tmp_path, monkeypatch):
        pending_dir = tmp_path / ".claude" / "handoff" / "pending"
        pending_dir.mkdir(parents=True)
        (pending_dir / "0.18.0-W17-001.json").write_text(
            json.dumps({
                "ticket_id": "0.18.0-W17-001",
                "direction": "to-child:0.18.0-W17-002",
                "from_status": "in_progress",
            }),
            encoding="utf-8",
        )

        tickets = [
            _make_ticket("0.18.0-W17-001", blocked_by=[]),
            _make_ticket("0.18.0-W17-042", blocked_by=[]),
        ]

        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ), patch(
            "ticket_system.commands.track_runqueue._get_pending_handoff_ticket_ids",
            return_value={"0.18.0-W17-001"},
        ):
            rc, out = _run(_args(format="list", context="resume"))
        assert rc == 0
        assert "0.18.0-W17-001" in out
        assert "0.18.0-W17-042" not in out, "resume 模式應只保留 handoff 交集"


class TestRunqueueExitStatusTag:
    """W17-031.1: --context=resume 讀 handoff JSON exit_status 並顯示 tag。

    四類顯示為 tag 取代 runnable 標記（blockedBy=[]）：
    needs_context / blocked / failed / partial_success；
    success / 缺欄位 → 不顯示 tag（fail-open）。
    """

    def _make_handoff(self, ticket_id: str, status: str | None) -> Dict:
        data = {
            "ticket_id": ticket_id,
            "direction": "to-self",
            "from_status": "in_progress",
        }
        if status is not None:
            data["exit_status"] = {"status": status, "reason": ""}
        return data

    def _run_resume_with_handoff(
        self, tickets: List[Dict], handoff_info: Dict[str, Dict]
    ) -> tuple[int, str]:
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ), patch(
            "ticket_system.commands.track_runqueue._get_pending_handoff_info",
            return_value=handoff_info,
        ), patch(
            "ticket_system.commands.track_runqueue._get_pending_handoff_ticket_ids",
            return_value=set(handoff_info.keys()),
        ):
            return _run(_args(format="list", context="resume"))

    def test_needs_context_shows_tag_and_drops_runnable(self):
        tickets = [_make_ticket("0.18.0-W17-100", blocked_by=[])]
        info = {"0.18.0-W17-100": self._make_handoff(
            "0.18.0-W17-100", "needs_context"
        )}
        rc, out = self._run_resume_with_handoff(tickets, info)
        assert rc == 0
        assert "0.18.0-W17-100" in out
        assert "[needs_context]" in out
        # 不顯示 runnable 標記
        assert "blockedBy=[]" not in out

    def test_blocked_status_shows_tag(self):
        tickets = [_make_ticket("0.18.0-W17-101", blocked_by=[])]
        info = {"0.18.0-W17-101": self._make_handoff(
            "0.18.0-W17-101", "blocked"
        )}
        rc, out = self._run_resume_with_handoff(tickets, info)
        assert rc == 0
        assert "[blocked]" in out
        assert "blockedBy=[]" not in out

    def test_failed_status_shows_tag(self):
        tickets = [_make_ticket("0.18.0-W17-102", blocked_by=[])]
        info = {"0.18.0-W17-102": self._make_handoff(
            "0.18.0-W17-102", "failed"
        )}
        rc, out = self._run_resume_with_handoff(tickets, info)
        assert rc == 0
        assert "[failed]" in out
        assert "blockedBy=[]" not in out

    def test_partial_success_shows_tag(self):
        tickets = [_make_ticket("0.18.0-W17-103", blocked_by=[])]
        info = {"0.18.0-W17-103": self._make_handoff(
            "0.18.0-W17-103", "partial_success"
        )}
        rc, out = self._run_resume_with_handoff(tickets, info)
        assert rc == 0
        assert "[partial_success]" in out
        assert "blockedBy=[]" not in out

    def test_missing_exit_status_field_fail_open(self):
        """缺 exit_status 欄位 → 不標籤（fail-open，相容舊 handoff JSON）"""
        tickets = [_make_ticket("0.18.0-W17-104", blocked_by=[])]
        info = {"0.18.0-W17-104": self._make_handoff(
            "0.18.0-W17-104", None  # 無 exit_status
        )}
        rc, out = self._run_resume_with_handoff(tickets, info)
        assert rc == 0
        assert "0.18.0-W17-104" in out
        # 無 tag，保留 runnable 標記
        assert "blockedBy=[]" in out
        for tag in ("[needs_context]", "[blocked]", "[failed]", "[partial_success]"):
            assert tag not in out

    def test_success_status_does_not_tag(self):
        """status=success 不標籤（成功 ticket 應為 runnable，無需提醒）"""
        tickets = [_make_ticket("0.18.0-W17-105", blocked_by=[])]
        info = {"0.18.0-W17-105": self._make_handoff(
            "0.18.0-W17-105", "success"
        )}
        rc, out = self._run_resume_with_handoff(tickets, info)
        assert rc == 0
        assert "blockedBy=[]" in out

    def test_unknown_status_value_fail_open(self):
        """未知 status 值（schema 演進防護）→ 不標籤"""
        tickets = [_make_ticket("0.18.0-W17-106", blocked_by=[])]
        info = {"0.18.0-W17-106": self._make_handoff(
            "0.18.0-W17-106", "future_unknown_state"
        )}
        rc, out = self._run_resume_with_handoff(tickets, info)
        assert rc == 0
        assert "blockedBy=[]" in out
        assert "[future_unknown_state]" not in out

    def test_existing_list_tests_unaffected_no_resume(self):
        """非 resume 模式不讀 handoff，標記維持 blockedBy=[]"""
        tickets = [_make_ticket("0.18.0-W17-107", blocked_by=[])]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))  # 無 context=resume
        assert rc == 0
        assert "blockedBy=[]" in out


class TestRunqueueReadinessTag:
    """W17-031.3: runqueue list 輸出 readiness tag。

    判定規則（ticket md 表）：
    - exit_status=needs_context → [NEEDS-CTX]
    - exit_status=blocked → [BLOCKED]
    - exit_status=failed → [FAILED]
    - exit_status=success 或 Context Bundle 段落非空 → [READY]
    - 無 exit_status 且無 Context Bundle → [NO-CB]
    """

    def _make_handoff(self, ticket_id: str, status: str) -> Dict:
        return {
            "ticket_id": ticket_id,
            "direction": "to-self",
            "from_status": "in_progress",
            "exit_status": {"status": status, "reason": ""},
        }

    def test_ready_when_exit_status_success(self):
        tickets = [_make_ticket("TIX-RDY-1", blocked_by=[])]
        info = {"TIX-RDY-1": self._make_handoff("TIX-RDY-1", "success")}
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ), patch(
            "ticket_system.commands.track_runqueue._get_pending_handoff_info",
            return_value=info,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "[READY]" in out
        assert "TIX-RDY-1" in out

    def test_ready_when_context_bundle_present(self):
        ticket = _make_ticket("TIX-CB-1", blocked_by=[])
        ticket["_body"] = (
            "# Execution Log\n\n"
            "## Context Bundle\n\n"
            "Some real context content here.\n\n"
            "## Solution\n"
        )
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=[ticket],
        ), patch(
            "ticket_system.commands.track_runqueue._get_pending_handoff_info",
            return_value={},
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "[READY]" in out

    def test_no_cb_when_no_exit_status_and_no_context_bundle(self):
        tickets = [_make_ticket("TIX-NOCB-1", blocked_by=[])]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "[NO-CB]" in out

    def test_needs_ctx_readiness_tag(self):
        tickets = [_make_ticket("TIX-NC-1", blocked_by=[])]
        info = {"TIX-NC-1": self._make_handoff("TIX-NC-1", "needs_context")}
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ), patch(
            "ticket_system.commands.track_runqueue._get_pending_handoff_info",
            return_value=info,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "[NEEDS-CTX]" in out
        assert "[READY]" not in out

    def test_context_bundle_with_only_html_comment_is_empty(self):
        """空 Context Bundle 段落（僅 HTML 註解）→ NO-CB 而非 READY"""
        ticket = _make_ticket("TIX-EMPTY-CB", blocked_by=[])
        ticket["_body"] = (
            "# Execution Log\n\n"
            "## Context Bundle\n\n"
            "<!-- placeholder for context -->\n\n"
            "## Solution\n"
        )
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=[ticket],
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "[NO-CB]" in out
        assert "[READY]" not in out

    def test_readiness_does_not_change_priority_order(self):
        """readiness 標註不影響 priority 排序（AC 3）"""
        tickets = [
            _make_ticket("TIX-LOW", priority="P3", blocked_by=[]),
            _make_ticket("TIX-HI", priority="P0", blocked_by=[]),
        ]
        # 高優先級 NO-CB；低優先級 READY（success），確保 readiness 不影響排序
        ticket_hi_body = tickets[1]
        info = {"TIX-LOW": self._make_handoff("TIX-LOW", "success")}
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ), patch(
            "ticket_system.commands.track_runqueue._get_pending_handoff_info",
            return_value=info,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        # P0 仍排第一，即使是 NO-CB
        assert out.find("TIX-HI") < out.find("TIX-LOW"), (
            f"priority 排序被 readiness 影響: {out}"
        )

    def test_blocked_pending_excluded_from_list(self):
        """blockedBy 非空仍被排除（readiness 不放寬 list 過濾條件）"""
        tickets = [
            _make_ticket("TIX-OPEN", blocked_by=[]),
            _make_ticket("TIX-BLOCKED", blocked_by=["TIX-OPEN"]),
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "TIX-OPEN" in out
        assert "TIX-BLOCKED" not in out


class TestRunqueueStaleInProgress:
    """W17-031.4: runqueue list 標註 stale in_progress。

    判定規則：
    - status=in_progress 且 completed_at=None 且 started_at 距今 >= 24h → [STALE]
    - status=in_progress 但 started_at < 24h → 不標
    - status=completed → 不標（且不出現在 list）
    """

    def _stale_ticket(
        self, ticket_id: str, hours_ago: float, **overrides
    ) -> Dict:
        from datetime import datetime, timedelta
        started = (datetime.now() - timedelta(hours=hours_ago)).isoformat(
            timespec="seconds"
        )
        ticket = _make_ticket(ticket_id, **overrides)
        ticket["status"] = "in_progress"
        ticket["started_at"] = started
        ticket["completed_at"] = None
        return ticket

    def test_in_progress_over_24h_marked_stale(self):
        tickets = [self._stale_ticket("TIX-STALE-1", hours_ago=30)]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "TIX-STALE-1" in out
        assert "[STALE]" in out

    def test_in_progress_under_24h_not_marked(self):
        tickets = [self._stale_ticket("TIX-FRESH-1", hours_ago=2)]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        # 24h 內的 in_progress 不在 listable 範圍，也不標 STALE
        assert "[STALE]" not in out

    def test_completed_ticket_not_in_list_and_no_stale_tag(self):
        ticket = _make_ticket("TIX-DONE-1", blocked_by=[])
        ticket["status"] = "completed"
        ticket["started_at"] = "2026-01-01T00:00:00"
        ticket["completed_at"] = "2026-01-02T00:00:00"
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=[ticket],
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "TIX-DONE-1" not in out
        assert "[STALE]" not in out

    def test_pending_ticket_not_marked_stale(self):
        """pending（非 in_progress）即使 started_at 很久也不標 STALE"""
        tickets = [_make_ticket("TIX-PEND-1", blocked_by=[])]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "TIX-PEND-1" in out
        assert "[STALE]" not in out

    def test_stale_does_not_break_readiness_tag(self):
        """STALE 與 readiness tag 並列（可疊加）"""
        tickets = [self._stale_ticket("TIX-STALE-RDY", hours_ago=48)]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="list"))
        assert rc == 0
        assert "[STALE]" in out
        # 既有 readiness tag 仍應存在（NO-CB 因無 Context Bundle 也無 handoff）
        assert "[NO-CB]" in out


class TestRunqueueCycleDetection:
    """復用 CycleDetector：有環時給出錯誤訊息"""

    def test_cycle_is_reported_not_crashed(self):
        tickets = [
            _make_ticket("A", blocked_by=["B"]),
            _make_ticket("B", blocked_by=["A"]),
        ]
        with patch(
            "ticket_system.commands.track_runqueue.list_tickets",
            return_value=tickets,
        ):
            rc, out = _run(_args(format="critical-path"))
        # 不 crash；可回 0（報 warning）或非 0（錯誤碼），但須有輸出
        assert rc in (0, 1, 2)
        assert len(out) > 0


class TestRunqueueRegistration:
    """註冊走 _create_command_handlers() 字典（不走 snapshot/dispatch-check 雙軌）"""

    def test_runqueue_in_command_handlers(self):
        from ticket_system.commands.track import _create_command_handlers

        handlers = _create_command_handlers()
        assert "runqueue" in handlers, (
            "runqueue 必須註冊於 _create_command_handlers() 字典，"
            "不走 snapshot/dispatch-check 雙軌"
        )
        from ticket_system.commands.track_runqueue import execute_runqueue
        assert handlers["runqueue"] is execute_runqueue

    def test_runqueue_not_in_execute_special_branches(self):
        """runqueue 不應是 execute() 裡的 snapshot-style 特殊分支"""
        from pathlib import Path
        track_py = Path(
            __import__("ticket_system.commands.track", fromlist=["__file__"]).__file__
        )
        src = track_py.read_text(encoding="utf-8")
        # 特殊分支 pattern：operation == "<name>"
        assert 'operation == "runqueue"' not in src, (
            "runqueue 不得加入 execute() 的 operation == '...' 特殊分支"
        )


class TestRunqueueNiceRejected:
    """禁止 --nice 參數（linux 審查結論）"""

    def test_nice_flag_not_registered(self):
        """track.py 的 register 不得含 --nice 參數"""
        from pathlib import Path
        from ticket_system.commands import track_runqueue

        # Check runqueue source does not reference --nice
        src_paths = [
            Path(track_runqueue.__file__).read_text(encoding="utf-8"),
        ]
        # Also check track.py register additions
        from ticket_system.commands import track as track_mod
        src_paths.append(Path(track_mod.__file__).read_text(encoding="utf-8"))

        for src in src_paths:
            assert "--nice" not in src, "禁止 --nice 參數（W17-009 linux 審查結論）"


class TestRunqueueReusesLib:
    """禁止重寫拓撲/CPM/環檢測"""

    def test_no_local_kahn_or_topological_impl(self):
        """track_runqueue 不應自行實作 Kahn/topological sort"""
        from pathlib import Path
        from ticket_system.commands import track_runqueue

        src = Path(track_runqueue.__file__).read_text(encoding="utf-8")
        # 禁止出現獨立拓撲實作關鍵字（Kahn 算法常見詞）
        forbidden = ["in_degree", "kahn", "Kahn"]
        for word in forbidden:
            assert word not in src, (
                f"禁止重寫拓撲演算法（發現 '{word}'）；"
                f"應復用 CriticalPathAnalyzer / CycleDetector"
            )

    def test_imports_critical_path_analyzer(self):
        """明確 import CriticalPathAnalyzer"""
        from ticket_system.commands import track_runqueue
        assert hasattr(track_runqueue, "CriticalPathAnalyzer")
