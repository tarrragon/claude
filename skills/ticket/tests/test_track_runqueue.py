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
