"""
測試 ticket track stuck-anas 命令（W17-008.15 方案 D 第 1 項）。

覆蓋核心行為：
- 過濾 type=ANA + status=in_progress + spawned 全 completed
- spawned 為空 → 不視為卡住（避免誤報）
- spawned 任一未 completed → 不視為卡住
- spawned ticket 不存在 → 不視為卡住（保守）
- --wave 過濾
- 空集合 → rc=0 + 友好訊息
"""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout
from typing import Dict, List
from unittest.mock import patch


def _make_ana(
    ticket_id: str,
    *,
    status: str = "in_progress",
    spawned: List[str] | None = None,
    wave: int = 17,
) -> Dict:
    return {
        "id": ticket_id,
        "type": "ANA",
        "status": status,
        "spawned_tickets": spawned or [],
        "wave": wave,
        "title": f"ANA {ticket_id}",
    }


def _make_imp(
    ticket_id: str, *, status: str = "completed", wave: int = 17
) -> Dict:
    return {
        "id": ticket_id,
        "type": "IMP",
        "status": status,
        "wave": wave,
        "title": f"IMP {ticket_id}",
    }


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        operation="stuck-anas",
        wave=None,
        all=False,
        version=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _run(args: argparse.Namespace, tickets: List[Dict]) -> tuple[int, str]:
    from ticket_system.commands.track_stuck_anas import execute_stuck_anas

    buf = io.StringIO()
    with patch(
        "ticket_system.commands.track_stuck_anas.list_tickets",
        return_value=tickets,
    ), patch(
        "ticket_system.commands.track_stuck_anas.get_active_versions",
        return_value=["v0.18.0"],
    ), redirect_stdout(buf):
        rc = execute_stuck_anas(args)
    return rc, buf.getvalue()


class TestStuckAnasFiltering:
    def test_ana_with_all_spawned_completed_is_listed(self):
        tickets = [
            _make_ana("0.18.0-W17-100", spawned=["0.18.0-W17-101"]),
            _make_imp("0.18.0-W17-101", status="completed"),
        ]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-100" in out
        assert "可考慮 ticket track complete 0.18.0-W17-100" in out

    def test_ana_with_no_spawned_is_not_stuck(self):
        tickets = [_make_ana("0.18.0-W17-200", spawned=[])]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-200" not in out
        assert "（無卡住的 ANA）" in out

    def test_ana_with_partial_spawned_completed_is_not_stuck(self):
        tickets = [
            _make_ana(
                "0.18.0-W17-300",
                spawned=["0.18.0-W17-301", "0.18.0-W17-302"],
            ),
            _make_imp("0.18.0-W17-301", status="completed"),
            _make_imp("0.18.0-W17-302", status="in_progress"),
        ]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-300" not in out

    def test_ana_with_missing_spawned_is_not_stuck(self):
        tickets = [
            _make_ana("0.18.0-W17-400", spawned=["0.18.0-W17-NOTEXIST"]),
        ]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-400" not in out

    def test_completed_ana_is_not_listed(self):
        tickets = [
            _make_ana(
                "0.18.0-W17-500",
                status="completed",
                spawned=["0.18.0-W17-501"],
            ),
            _make_imp("0.18.0-W17-501", status="completed"),
        ]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-500" not in out

    def test_imp_type_is_not_listed_even_with_spawned(self):
        tickets = [
            {
                "id": "0.18.0-W17-600",
                "type": "IMP",
                "status": "in_progress",
                "spawned_tickets": ["0.18.0-W17-601"],
                "wave": 17,
                "title": "fake",
            },
            _make_imp("0.18.0-W17-601", status="completed"),
        ]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-600" not in out


class TestStuckAnasWaveFilter:
    def test_wave_filter_excludes_other_waves(self):
        tickets = [
            _make_ana(
                "0.18.0-W17-001", wave=17, spawned=["0.18.0-W17-002"]
            ),
            _make_imp("0.18.0-W17-002", status="completed", wave=17),
            _make_ana(
                "0.18.0-W18-001", wave=18, spawned=["0.18.0-W18-002"]
            ),
            _make_imp("0.18.0-W18-002", status="completed", wave=18),
        ]
        rc, out = _run(_args(wave=17), tickets)
        assert rc == 0
        assert "0.18.0-W17-001" in out
        assert "0.18.0-W18-001" not in out


class TestStuckAnasEmpty:
    def test_no_tickets_returns_zero_with_message(self):
        rc, out = _run(_args(), [])
        assert rc == 0
        assert "（無卡住的 ANA）" in out
