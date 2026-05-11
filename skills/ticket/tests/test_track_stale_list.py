"""
測試 ticket track stale-list 命令（W17-200）。

覆蓋核心行為：
- 僅列出 status=pending 的 ticket（in_progress / completed 不納入）
- 依 calculate_stale_level 分級為 info / warning / critical
- --threshold 篩選（預設 warning = warning + critical；info = 三級；
  all = 三級；critical = 僅 critical）
- 依 days 降序排序
- --wave 過濾
- --format ids / yaml / table
- 空集合 → rc=0 + 友好訊息
"""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout
from datetime import date, timedelta
from typing import Dict, List
from unittest.mock import patch


TODAY = date(2026, 5, 11)


def _make_ticket(
    ticket_id: str,
    *,
    age_days: int,
    status: str = "pending",
    wave: int = 17,
    title: str | None = None,
) -> Dict:
    created = (TODAY - timedelta(days=age_days)).isoformat()
    return {
        "id": ticket_id,
        "type": "IMP",
        "status": status,
        "wave": wave,
        "title": title or f"Ticket {ticket_id}",
        "created": created,
    }


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        operation="stale-list",
        threshold="warning",
        wave=None,
        all=False,
        version=None,
        format="table",
        _today=TODAY,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _run(args: argparse.Namespace, tickets: List[Dict]) -> tuple[int, str]:
    from ticket_system.commands.track_stale_list import execute_stale_list

    buf = io.StringIO()
    with patch(
        "ticket_system.commands.track_stale_list.list_tickets",
        return_value=tickets,
    ), patch(
        "ticket_system.commands.track_stale_list.get_active_versions",
        return_value=["v0.18.0"],
    ), redirect_stdout(buf):
        rc = execute_stale_list(args)
    return rc, buf.getvalue()


class TestStaleListThreshold:
    def test_default_warning_threshold_excludes_info(self):
        tickets = [
            _make_ticket("0.18.0-W17-INFO", age_days=7),     # info
            _make_ticket("0.18.0-W17-WARN", age_days=14),    # warning
            _make_ticket("0.18.0-W17-CRIT", age_days=30),    # critical
        ]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-INFO" not in out
        assert "0.18.0-W17-WARN" in out
        assert "0.18.0-W17-CRIT" in out

    def test_threshold_info_includes_all_three_levels(self):
        tickets = [
            _make_ticket("0.18.0-W17-INFO", age_days=7),
            _make_ticket("0.18.0-W17-WARN", age_days=14),
            _make_ticket("0.18.0-W17-CRIT", age_days=30),
        ]
        rc, out = _run(_args(threshold="info"), tickets)
        assert rc == 0
        assert "0.18.0-W17-INFO" in out
        assert "0.18.0-W17-WARN" in out
        assert "0.18.0-W17-CRIT" in out

    def test_threshold_all_same_as_info(self):
        tickets = [
            _make_ticket("0.18.0-W17-INFO", age_days=7),
            _make_ticket("0.18.0-W17-CRIT", age_days=30),
        ]
        rc, out = _run(_args(threshold="all"), tickets)
        assert rc == 0
        assert "0.18.0-W17-INFO" in out
        assert "0.18.0-W17-CRIT" in out

    def test_threshold_critical_only(self):
        tickets = [
            _make_ticket("0.18.0-W17-WARN", age_days=14),
            _make_ticket("0.18.0-W17-CRIT", age_days=30),
        ]
        rc, out = _run(_args(threshold="critical"), tickets)
        assert rc == 0
        assert "0.18.0-W17-WARN" not in out
        assert "0.18.0-W17-CRIT" in out


class TestStaleListStatusFilter:
    def test_only_pending_tickets_included(self):
        tickets = [
            _make_ticket("0.18.0-W17-P", age_days=20, status="pending"),
            _make_ticket("0.18.0-W17-I", age_days=20, status="in_progress"),
            _make_ticket("0.18.0-W17-C", age_days=20, status="completed"),
        ]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-P" in out
        assert "0.18.0-W17-I" not in out
        assert "0.18.0-W17-C" not in out

    def test_fresh_pending_not_listed(self):
        tickets = [_make_ticket("0.18.0-W17-FRESH", age_days=3)]
        rc, out = _run(_args(threshold="info"), tickets)
        assert rc == 0
        assert "0.18.0-W17-FRESH" not in out


class TestStaleListSorting:
    def test_rows_sorted_by_days_desc(self):
        tickets = [
            _make_ticket("0.18.0-W17-A", age_days=15, title="A"),
            _make_ticket("0.18.0-W17-B", age_days=40, title="B"),
            _make_ticket("0.18.0-W17-C", age_days=20, title="C"),
        ]
        rc, out = _run(_args(threshold="info"), tickets)
        assert rc == 0
        idx_a = out.index("0.18.0-W17-A")
        idx_b = out.index("0.18.0-W17-B")
        idx_c = out.index("0.18.0-W17-C")
        # B (40) > C (20) > A (15)
        assert idx_b < idx_c < idx_a


class TestStaleListWaveFilter:
    def test_wave_filter_excludes_others(self):
        tickets = [
            _make_ticket("0.18.0-W17-X", age_days=20, wave=17),
            _make_ticket("0.18.0-W18-Y", age_days=20, wave=18),
        ]
        rc, out = _run(_args(wave=17), tickets)
        assert rc == 0
        assert "0.18.0-W17-X" in out
        assert "0.18.0-W18-Y" not in out


class TestStaleListFormat:
    def test_format_ids_outputs_one_per_line(self):
        tickets = [
            _make_ticket("0.18.0-W17-A", age_days=20),
            _make_ticket("0.18.0-W17-B", age_days=30),
        ]
        rc, out = _run(_args(format="ids"), tickets)
        assert rc == 0
        lines = [ln for ln in out.strip().splitlines() if ln]
        assert lines == ["0.18.0-W17-B", "0.18.0-W17-A"]

    def test_format_yaml_contains_fields(self):
        tickets = [_make_ticket("0.18.0-W17-Y", age_days=30, title="hello")]
        rc, out = _run(_args(format="yaml"), tickets)
        assert rc == 0
        assert "id: 0.18.0-W17-Y" in out
        assert "level: critical" in out
        assert "days: 30" in out
        assert 'title: "hello"' in out

    def test_format_table_contains_pipe_layout(self):
        tickets = [_make_ticket("0.18.0-W17-T", age_days=30, title="hi")]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "0.18.0-W17-T | [critical] | 30 天 | hi" in out


class TestStaleListEmpty:
    def test_no_tickets_returns_zero_with_message(self):
        rc, out = _run(_args(), [])
        assert rc == 0
        assert "（無符合條件的 stale ticket）" in out

    def test_no_match_with_threshold_returns_message(self):
        tickets = [_make_ticket("0.18.0-W17-F", age_days=3)]
        rc, out = _run(_args(), tickets)
        assert rc == 0
        assert "（無符合條件的 stale ticket）" in out
