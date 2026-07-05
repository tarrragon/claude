"""1.5.0-W5-005.7: stale-list 的 stale in-progress 章節與 release hint。

驗證重點：
1. stale in_progress 票（started_at 超過閾值）在 table 輸出附 release 指令提示
2. 未超閾值的 in_progress 票不出現
3. ids / yaml 格式維持 pending-only（pipe 消費者向後相容）
4. --wave 過濾同樣作用於 in_progress 章節
5. 單平面設計：判定僅依 frontmatter started_at，不讀 dispatch-active.json
"""

from argparse import Namespace
from datetime import date, datetime
from unittest.mock import patch

import pytest

from ticket_system.commands import track_stale_list
from ticket_system.lib.staleness import STALE_IN_PROGRESS_HOURS

NOW = datetime(2026, 7, 5, 12, 0, 0)
TODAY = date(2026, 7, 5)
STALE_HOURS = STALE_IN_PROGRESS_HOURS + 2  # 超閾值
FRESH_HOURS = 1  # 未超閾值


def _ticket(tid, status, *, started_hours_ago=None, wave=5, agent="thyme-python-developer"):
    ticket = {
        "id": tid,
        "title": f"title-{tid}",
        "status": status,
        "wave": wave,
        "created": "2026-07-04",
        "who": {"current": agent},
    }
    if started_hours_ago is not None:
        ticket["started_at"] = (
            datetime.fromtimestamp(NOW.timestamp() - started_hours_ago * 3600)
            .isoformat(timespec="seconds")
        )
    return ticket


def _run(tickets, capsys, **overrides):
    args = Namespace(
        threshold="warning",
        wave=overrides.pop("wave", None),
        all=False,
        version="9.9.9",
        format=overrides.pop("format", "table"),
        _today=TODAY,
        _now=NOW,
    )
    with patch.object(track_stale_list, "list_tickets", return_value=tickets), \
         patch.object(track_stale_list, "get_active_versions", return_value=["9.9.9"]):
        rc = track_stale_list.execute_stale_list(args)
    assert rc == 0
    return capsys.readouterr().out


class TestInProgressSection:
    def test_stale_in_progress_shown_with_release_hint(self, capsys):
        out = _run(
            [_ticket("9.9.9-W5-001", "in_progress", started_hours_ago=STALE_HOURS)],
            capsys,
        )
        assert "Stale in-progress tickets" in out
        assert "9.9.9-W5-001" in out
        assert "agent=thyme-python-developer" in out
        assert "ticket track release <id>" in out

    def test_fresh_in_progress_not_shown(self, capsys):
        out = _run(
            [_ticket("9.9.9-W5-002", "in_progress", started_hours_ago=FRESH_HOURS)],
            capsys,
        )
        assert "Stale in-progress tickets" not in out
        assert "9.9.9-W5-002" not in out

    def test_missing_started_at_not_shown(self, capsys):
        """缺 started_at 的 in_progress 票 fail-open 不誤標（單平面：無其他資料源）"""
        out = _run([_ticket("9.9.9-W5-003", "in_progress")], capsys)
        assert "Stale in-progress tickets" not in out

    def test_wave_filter_applies(self, capsys):
        tickets = [
            _ticket("9.9.9-W5-004", "in_progress", started_hours_ago=STALE_HOURS, wave=5),
            _ticket("9.9.9-W6-001", "in_progress", started_hours_ago=STALE_HOURS, wave=6),
        ]
        out = _run(tickets, capsys, wave=5)
        assert "9.9.9-W5-004" in out
        assert "9.9.9-W6-001" not in out

    def test_elapsed_hours_rendered(self, capsys):
        out = _run(
            [_ticket("9.9.9-W5-005", "in_progress", started_hours_ago=STALE_HOURS)],
            capsys,
        )
        assert f"in_progress {STALE_HOURS}h" in out


class TestPipeFormatsBackwardCompat:
    """ids / yaml 維持 pending-only：既有 pipe 消費者不得混入 in_progress"""

    def test_ids_format_excludes_in_progress(self, capsys):
        tickets = [
            _ticket("9.9.9-W5-006", "in_progress", started_hours_ago=STALE_HOURS),
        ]
        out = _run(tickets, capsys, format="ids")
        assert "9.9.9-W5-006" not in out

    def test_yaml_format_excludes_in_progress(self, capsys):
        tickets = [
            _ticket("9.9.9-W5-007", "in_progress", started_hours_ago=STALE_HOURS),
        ]
        out = _run(tickets, capsys, format="yaml")
        assert "9.9.9-W5-007" not in out


class TestPendingSectionRegression:
    """既有 pending stale 表格行為不受擴充影響"""

    def test_stale_pending_still_listed(self, capsys):
        stale_pending = {
            "id": "9.9.9-W5-008",
            "title": "old pending",
            "status": "pending",
            "wave": 5,
            "created": "2026-06-01",  # 34 天前 → critical
        }
        out = _run([stale_pending], capsys)
        assert "9.9.9-W5-008" in out
        assert "[critical]" in out

    def test_both_sections_coexist(self, capsys):
        tickets = [
            {
                "id": "9.9.9-W5-009",
                "title": "old pending",
                "status": "pending",
                "wave": 5,
                "created": "2026-06-01",
            },
            _ticket("9.9.9-W5-010", "in_progress", started_hours_ago=STALE_HOURS),
        ]
        out = _run(tickets, capsys)
        assert "9.9.9-W5-009" in out
        assert "9.9.9-W5-010" in out
        assert out.index("9.9.9-W5-009") < out.index("Stale in-progress")
