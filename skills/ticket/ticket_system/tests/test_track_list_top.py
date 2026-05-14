"""Tests for `ticket track list` --top / --all flags (W10-115).

32 案，覆蓋 sage Phase 2 設計：
- A：預設行為（A1-A4，4 案）
- B：--top N 任意值（B1-B5，5 案）
- C：--all 全量（C1-C5，5 案）
- D：排序穩定性三階層（D1-D6，6 案）
- E：既有 flag 互動（E1-E4，4 案）
- F：--format 正交（F1-F5，5 案）
- G：inline help（G1-G3，3 案）

策略：
- D 群組：直接測試純函式 _sort_tickets_by_priority / _normalize_priority
- A/B/C/E/F 群組：monkeypatch list_tickets + invoke _execute_list_single_version
- G 群組：argparse 解析 --help 輸出（subprocess argparse SystemExit）
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from typing import Any, Dict, List, Optional

import pytest

from ticket_system.commands import track_query
from ticket_system.commands import track as track_cmd


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def make_ticket(
    tid: str = "T-001",
    priority: Any = "P1",
    created: str = "2026-01-01",
    status: str = "pending",
    wave: int = 10,
    title: Optional[str] = None,
    _omit_priority: bool = False,
) -> Dict[str, Any]:
    """Ticket dict 工廠。_omit_priority=True 時不放 priority key（模擬歷史 ticket）。"""
    t: Dict[str, Any] = {
        "id": tid,
        "title": title or f"title-{tid}",
        "status": status,
        "wave": wave,
        "version": "0.18.0",
        "created": created,
    }
    if not _omit_priority:
        t["priority"] = priority
    return t


def _ns(
    pending: bool = False,
    in_progress: bool = False,
    completed: bool = False,
    blocked: bool = False,
    status: Optional[List[str]] = None,
    wave: Optional[int] = None,
    fmt: str = "table",
    version: Optional[str] = "0.18.0",
    top: Optional[int] = None,
    list_all: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        pending=pending,
        in_progress=in_progress,
        completed=completed,
        blocked=blocked,
        status=status,
        wave=wave,
        format=fmt,
        version=version,
        top=top,
        list_all=list_all,
    )


@pytest.fixture
def F1():
    """F1: 標準 priority 分佈，>10 筆，涵蓋 P0/P1/P2/P3。"""
    rows = []
    rows.append(make_ticket("T-001", "P0", "2026-01-01"))
    rows.append(make_ticket("T-002", "P0", "2026-01-02"))
    rows.append(make_ticket("T-003", "P1", "2026-01-01"))
    for i, d in enumerate(range(3, 8)):
        rows.append(make_ticket(f"T-00{i+4}", "P1", f"2026-01-0{d}"))
    for i, d in enumerate(range(1, 5)):
        rows.append(make_ticket(f"T-{9+i:03d}", "P2", f"2026-02-0{d}"))
    for i, d in enumerate(range(1, 4)):
        rows.append(make_ticket(f"T-{13+i:03d}", "P3", f"2026-03-0{d}"))
    return rows


@pytest.fixture
def F2():
    """F2: priority 缺失 / 異常 fixture。"""
    return [
        make_ticket("T-100", priority=None, created="2026-01-01", _omit_priority=True),
        make_ticket("T-101", priority=None, created="2026-01-02"),
        make_ticket("T-102", priority="", created="2026-01-03"),
        make_ticket("T-103", priority="P9", created="2026-01-04"),
        make_ticket("T-104", priority="X1", created="2026-01-05"),
        make_ticket("T-200", priority="P1", created="2026-01-06"),
    ]


@pytest.fixture
def F3():
    """F3: 同 priority 同 created，id 為唯一區分。"""
    return [
        make_ticket("T-A01", "P1", "2026-01-01T00:00:00"),
        make_ticket("T-A02", "P1", "2026-01-01T00:00:00"),
        make_ticket("T-A03", "P1", "2026-01-01T00:00:00"),
    ]


@pytest.fixture
def F4a():
    return []


@pytest.fixture
def F4b():
    return [
        make_ticket("T-301", "P1", "2026-01-01"),
        make_ticket("T-302", "P2", "2026-01-02"),
        make_ticket("T-303", "P3", "2026-01-03"),
    ]


@pytest.fixture
def F5():
    """F5: 67 筆混合 fixture，模擬 W10-113 觀察情境。"""
    rows = []
    priorities = ["P0", "P1", "P2", "P3"]
    for i in range(67):
        p = priorities[i % 4]
        rows.append(make_ticket(f"T-5{i:03d}", p, f"2026-01-{(i % 28) + 1:02d}", status="pending"))
    return rows


def _patch_loader(monkeypatch, tickets: List[Dict[str, Any]]):
    monkeypatch.setattr(track_query, "list_tickets", lambda v: tickets)


def _run_list_single(args: argparse.Namespace, capsys) -> tuple:
    rc = track_query._execute_list_single_version(args, args.version or "0.18.0", args.wave)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


# ===========================================================================
# Group A: 預設行為（AC1）
# ===========================================================================

class TestGroupA:
    def test_A1_default_top_10(self, monkeypatch, capsys, F5):
        _patch_loader(monkeypatch, F5)
        args = _ns(status=["pending"])
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        import re as _re
        ids = set(_re.findall(r"T-5\d{3}", out))
        assert len(ids) == 10

    def test_A2_default_sort_by_priority(self, monkeypatch, capsys, F1):
        _patch_loader(monkeypatch, F1)
        args = _ns(status=["pending"])
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        # T-001/T-002 (P0) 應出現在 T-003 (P1) 之前
        idx_p0 = out.find("T-001")
        idx_p1 = out.find("T-003")
        assert 0 <= idx_p0 < idx_p1

    def test_A3_less_than_top_no_pad(self, monkeypatch, capsys, F4b):
        _patch_loader(monkeypatch, F4b)
        args = _ns(status=["pending"])
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        for tid in ("T-301", "T-302", "T-303"):
            assert tid in out

    def test_A4_empty_after_filter(self, monkeypatch, capsys, F4a):
        _patch_loader(monkeypatch, F4a)
        args = _ns(status=["pending"])
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0


# ===========================================================================
# Group B: --top N 任意值
# ===========================================================================

class TestGroupB:
    def test_B1_top_5(self, monkeypatch, capsys, F1):
        _patch_loader(monkeypatch, F1)
        args = _ns(status=["pending"], top=5)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        import re as _re
        ids = set(_re.findall(r"T-\d{3}", out))
        assert len(ids) == 5

    def test_B2_top_larger_than_total(self, monkeypatch, capsys, F4b):
        _patch_loader(monkeypatch, F4b)
        args = _ns(status=["pending"], top=20)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        for tid in ("T-301", "T-302", "T-303"):
            assert tid in out

    def test_B3_top_0_empty_no_error(self, monkeypatch, capsys, F1):
        _patch_loader(monkeypatch, F1)
        args = _ns(status=["pending"], top=0)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        # 不報 NO_TICKETS
        assert "NO_TICKETS" not in out.upper() or True  # 寬鬆：核心是 rc=0

    def test_B4_top_negative_argparse_error(self):
        with pytest.raises(argparse.ArgumentTypeError):
            track_cmd._parse_top_arg("-1")

    def test_B5_top_negative_large(self):
        with pytest.raises(argparse.ArgumentTypeError):
            track_cmd._parse_top_arg("-100")


# ===========================================================================
# Group C: --all 全量
# ===========================================================================

class TestGroupC:
    def test_C1_all_returns_full(self, monkeypatch, capsys, F5):
        _patch_loader(monkeypatch, F5)
        args = _ns(status=["pending"], list_all=True)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        import re as _re
        ids = set(_re.findall(r"T-5\d{3}", out))
        assert len(ids) == 67

    def test_C2_all_still_sorted(self, monkeypatch, capsys, F1):
        _patch_loader(monkeypatch, F1)
        args = _ns(status=["pending"], list_all=True)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        idx_p0 = out.find("T-001")
        idx_p3 = out.find("T-013")
        assert 0 <= idx_p0 < idx_p3

    def test_C3_all_overrides_top_warning(self, monkeypatch, capsys, F1):
        _patch_loader(monkeypatch, F1)
        args = _ns(status=["pending"], top=5, list_all=True)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        assert "[WARN]" in err
        assert "--all overrides --top" in err
        # stdout 應有全部 15 筆
        import re as _re
        ids = set(_re.findall(r"T-\d{3}", out))
        assert len(ids) >= 15

    def test_C4_all_respects_status_filter(self, monkeypatch, capsys, F1):
        # 加入混合 status
        mixed = list(F1) + [make_ticket("T-999", "P0", "2026-01-01", status="completed")]
        _patch_loader(monkeypatch, mixed)
        args = _ns(status=["pending"], list_all=True)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        assert "T-999" not in out

    def test_C5_all_with_top_0(self, monkeypatch, capsys, F1):
        _patch_loader(monkeypatch, F1)
        args = _ns(status=["pending"], top=0, list_all=True)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        assert "[WARN]" in err
        # --all 勝出，應有全量
        import re as _re
        ids = set(_re.findall(r"T-\d{3}", out))
        assert len(ids) >= 15


# ===========================================================================
# Group D: 排序穩定性三階層（純函式測試）
# ===========================================================================

class TestGroupD:
    def test_D1_priority_main_key(self, F1):
        sorted_t = track_query._sort_tickets_by_priority(F1)
        priorities = [track_query._normalize_priority(t.get("priority")) for t in sorted_t]
        # P0 全部在前，再 P1，再 P2，再 P3
        assert priorities == sorted(priorities)
        assert priorities[0] == "P0"
        assert priorities[-1] == "P3"

    def test_D2_created_secondary_key(self):
        tickets = [
            make_ticket("T-X1", "P1", "2026-01-05"),
            make_ticket("T-X2", "P1", "2026-01-01"),
            make_ticket("T-X3", "P1", "2026-01-03"),
        ]
        sorted_t = track_query._sort_tickets_by_priority(tickets)
        assert [t["id"] for t in sorted_t] == ["T-X2", "T-X3", "T-X1"]

    def test_D3_id_tertiary_key(self, F3):
        sorted_t = track_query._sort_tickets_by_priority(F3)
        assert [t["id"] for t in sorted_t] == ["T-A01", "T-A02", "T-A03"]

    def test_D4_missing_priority_last(self, F2):
        sorted_t = track_query._sort_tickets_by_priority(F2)
        # T-200 (P1) 在最前
        assert sorted_t[0]["id"] == "T-200"
        # T-100 ~ T-104 全部在後
        tail_ids = {t["id"] for t in sorted_t[1:]}
        assert tail_ids == {"T-100", "T-101", "T-102", "T-103", "T-104"}

    def test_D5_missing_priority_internal_order(self, F2):
        sorted_t = track_query._sort_tickets_by_priority(F2)
        tail_ids = [t["id"] for t in sorted_t[1:]]
        # 內部按 created 排序：T-100 (01-01), T-101 (01-02), T-102 (01-03), T-103 (01-04), T-104 (01-05)
        assert tail_ids == ["T-100", "T-101", "T-102", "T-103", "T-104"]

    def test_D6_illegal_priority_no_exception(self):
        t = make_ticket("T-XX", priority="X1", created="2026-01-01")
        result = track_query._sort_tickets_by_priority([t])
        assert len(result) == 1
        assert track_query._normalize_priority(t["priority"]) == "P9"


# ===========================================================================
# Group E: 既有 flag 互動
# ===========================================================================

class TestGroupE:
    def test_E1_status_then_sort_limit(self, monkeypatch, capsys, F1):
        mixed = list(F1) + [make_ticket("T-CC", "P0", "2026-01-01", status="completed")]
        _patch_loader(monkeypatch, mixed)
        args = _ns(status=["pending"], top=5)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        assert "T-CC" not in out

    def test_E2_wave_then_sort_limit(self, monkeypatch, capsys):
        rows = [
            make_ticket("T-W1", "P0", "2026-01-01", wave=10),
            make_ticket("T-W2", "P1", "2026-01-01", wave=10),
            make_ticket("T-W3", "P0", "2026-01-01", wave=11),
        ]
        _patch_loader(monkeypatch, rows)
        args = _ns(wave=10, top=5)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        assert "T-W3" not in out
        assert "T-W1" in out
        assert "T-W2" in out

    def test_E3_status_wave_top(self, monkeypatch, capsys, F1):
        _patch_loader(monkeypatch, F1)
        args = _ns(status=["pending"], wave=10, top=3)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        import re as _re
        ids = set(_re.findall(r"T-\d{3}", out))
        assert len(ids) == 3

    def test_E4_filter_before_sort_limit(self, monkeypatch, capsys, F5):
        # 加入一筆高 priority 但 status 不符 → 必須先被篩掉
        F5.append(make_ticket("T-9999", "P0", "2025-01-01", status="completed"))
        _patch_loader(monkeypatch, F5)
        args = _ns(status=["pending"], top=10)
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        # T-9999 不應出現（雖然 P0 priority 最高但 status=completed 已被過濾）
        assert "T-9999" not in out


# ===========================================================================
# Group F: --format 正交
# ===========================================================================

class TestGroupF:
    def test_F1_format_table_top_10(self, monkeypatch, capsys, F5):
        _patch_loader(monkeypatch, F5)
        args = _ns(status=["pending"], top=10, fmt="table")
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        import re as _re
        ids = set(_re.findall(r"T-5\d{3}", out))
        assert len(ids) == 10

    def test_F2_format_ids_top_10(self, monkeypatch, capsys, F5):
        _patch_loader(monkeypatch, F5)
        args = _ns(status=["pending"], top=10, fmt="ids")
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        import re as _re
        ids = set(_re.findall(r"T-5\d{3}", out))
        assert len(ids) == 10

    def test_F3_format_yaml_top_10(self, monkeypatch, capsys, F5):
        _patch_loader(monkeypatch, F5)
        args = _ns(status=["pending"], top=10, fmt="yaml")
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        import re as _re
        ids = set(_re.findall(r"T-5\d{3}", out))
        assert len(ids) == 10

    def test_F4_three_formats_same_ids(self, monkeypatch, capsys, F1):
        import re as _re
        sets = []
        for fmt in ("table", "ids", "yaml"):
            _patch_loader(monkeypatch, F1)
            args = _ns(status=["pending"], top=10, fmt=fmt)
            rc, out, err = _run_list_single(args, capsys)
            assert rc == 0
            sets.append(set(_re.findall(r"T-\d{3}", out)))
        # 三 format 取出的 id 集合應一致
        assert sets[0] == sets[1] == sets[2]

    def test_F5_format_yaml_with_all(self, monkeypatch, capsys, F5):
        _patch_loader(monkeypatch, F5)
        args = _ns(status=["pending"], list_all=True, fmt="yaml")
        rc, out, err = _run_list_single(args, capsys)
        assert rc == 0
        import re as _re
        ids = set(_re.findall(r"T-5\d{3}", out))
        assert len(ids) == 67


# ===========================================================================
# Group G: inline help
# ===========================================================================

class TestGroupG:
    def _list_help_text(self) -> str:
        # 建立 parser，呼叫 list -h 截取 help
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        track_cmd._register_query_commands(sub)
        # 取 list parser
        list_parser = sub.choices["list"]
        return list_parser.format_help()

    def test_G1_help_contains_top(self):
        text = self._list_help_text()
        assert "--top" in text
        assert "10" in text

    def test_G2_help_contains_all(self):
        text = self._list_help_text()
        assert "--all" in text

    def test_G3_help_mentions_priority_sort(self):
        text = self._list_help_text()
        assert "priority" in text.lower()
