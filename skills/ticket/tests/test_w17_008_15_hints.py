"""
測試 W17-008.15 方案 D 的兩個提示行：

1. lifecycle._print_source_ana_complete_hint
   - IMP complete 後若 source ANA 的 spawned 全 completed → 印出建議

2. create._print_in_progress_group_hint
   - ticket create 不帶 --parent 時偵測 in_progress group → 印出提示

測試以 monkeypatch ticket loader 為主，避免依賴實體檔案。
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Dict
from unittest.mock import patch


# ---------------------------------------------------------------------------
# _print_source_ana_complete_hint
# ---------------------------------------------------------------------------

def _imp(ticket_id: str, source: str | None = None) -> Dict:
    return {
        "id": ticket_id,
        "type": "IMP",
        "status": "completed",
        "source_ticket": source,
    }


def _ana(ticket_id: str, *, status: str = "in_progress", spawned=None) -> Dict:
    return {
        "id": ticket_id,
        "type": "ANA",
        "status": status,
        "spawned_tickets": spawned or [],
    }


def _capture_source_hint(ticket: Dict, loader_map: Dict[str, Dict]) -> str:
    from ticket_system.commands.lifecycle import _print_source_ana_complete_hint

    def fake_load(version: str, tid: str):
        return loader_map.get(tid)

    buf = io.StringIO()
    with patch(
        "ticket_system.commands.lifecycle.load_ticket", side_effect=fake_load
    ), redirect_stdout(buf):
        _print_source_ana_complete_hint(ticket, "0.18.0")
    return buf.getvalue()


class TestSourceAnaCompleteHint:
    def test_hint_printed_when_all_spawned_completed(self):
        ana = _ana("ANA-1", spawned=["IMP-A", "IMP-B"])
        loader = {
            "ANA-1": ana,
            "IMP-A": {"id": "IMP-A", "status": "completed"},
            "IMP-B": {"id": "IMP-B", "status": "completed"},
        }
        ticket = _imp("IMP-A", source="ANA-1")
        out = _capture_source_hint(ticket, loader)
        assert "Source ANA ANA-1 spawned 全 completed" in out
        assert "ticket track complete ANA-1" in out

    def test_no_hint_when_partial_spawned_completed(self):
        ana = _ana("ANA-2", spawned=["IMP-A", "IMP-B"])
        loader = {
            "ANA-2": ana,
            "IMP-A": {"id": "IMP-A", "status": "completed"},
            "IMP-B": {"id": "IMP-B", "status": "in_progress"},
        }
        ticket = _imp("IMP-A", source="ANA-2")
        out = _capture_source_hint(ticket, loader)
        assert out == ""

    def test_no_hint_when_no_source(self):
        ticket = _imp("IMP-X", source=None)
        out = _capture_source_hint(ticket, {})
        assert out == ""

    def test_no_hint_when_source_already_completed(self):
        ana = _ana("ANA-3", status="completed", spawned=["IMP-A"])
        loader = {
            "ANA-3": ana,
            "IMP-A": {"id": "IMP-A", "status": "completed"},
        }
        ticket = _imp("IMP-A", source="ANA-3")
        out = _capture_source_hint(ticket, loader)
        assert out == ""

    def test_no_hint_when_completed_ticket_is_not_imp(self):
        ana = _ana("ANA-4", spawned=["IMP-A"])
        loader = {
            "ANA-4": ana,
            "IMP-A": {"id": "IMP-A", "status": "completed"},
        }
        ticket = {
            "id": "DOC-1",
            "type": "DOC",
            "status": "completed",
            "source_ticket": "ANA-4",
        }
        out = _capture_source_hint(ticket, loader)
        assert out == ""

    def test_no_hint_when_source_has_no_spawned(self):
        ana = _ana("ANA-5", spawned=[])
        loader = {"ANA-5": ana}
        ticket = _imp("IMP-A", source="ANA-5")
        out = _capture_source_hint(ticket, loader)
        assert out == ""


# ---------------------------------------------------------------------------
# _print_in_progress_group_hint
# ---------------------------------------------------------------------------

def _capture_group_hint(
    version: str, wave: int | None, new_id: str, tickets
) -> str:
    from ticket_system.commands.create import _print_in_progress_group_hint

    buf = io.StringIO()
    with patch(
        "ticket_system.commands.create.list_tickets", return_value=tickets
    ), redirect_stdout(buf):
        _print_in_progress_group_hint(version, wave, new_id)
    return buf.getvalue()


def _group(ticket_id: str, *, children, wave: int = 17, status: str = "in_progress") -> Dict:
    return {
        "id": ticket_id,
        "status": status,
        "children": children,
        "wave": wave,
    }


class TestInProgressGroupHint:
    def test_hint_printed_for_in_progress_group_with_children(self):
        tickets = [_group("0.18.0-W17-008", children=["A", "B"])]
        out = _capture_group_hint(
            "0.18.0", 17, "0.18.0-W17-099", tickets
        )
        assert "0.18.0-W17-008" in out
        assert "(2 children)" in out
        assert "--parent 0.18.0-W17-008" in out

    def test_no_hint_when_group_has_no_children(self):
        tickets = [_group("0.18.0-W17-008", children=[])]
        out = _capture_group_hint(
            "0.18.0", 17, "0.18.0-W17-099", tickets
        )
        assert out == ""

    def test_no_hint_when_group_not_in_progress(self):
        tickets = [
            _group("0.18.0-W17-008", children=["A"], status="completed")
        ]
        out = _capture_group_hint(
            "0.18.0", 17, "0.18.0-W17-099", tickets
        )
        assert out == ""

    def test_skip_when_new_ticket_already_in_group(self):
        # 新 ticket ID 是 0.18.0-W17-008.99，本身就掛在 group 0.18.0-W17-008 下
        # 應跳過提示避免噪音
        tickets = [_group("0.18.0-W17-008", children=["A"])]
        out = _capture_group_hint(
            "0.18.0", 17, "0.18.0-W17-008.99", tickets
        )
        assert out == ""

    def test_wave_filter_excludes_other_waves(self):
        tickets = [
            _group("0.18.0-W17-008", children=["A"], wave=17),
            _group("0.18.0-W18-001", children=["B"], wave=18),
        ]
        out = _capture_group_hint(
            "0.18.0", 17, "0.18.0-W17-099", tickets
        )
        assert "0.18.0-W17-008" in out
        assert "0.18.0-W18-001" not in out
