"""where.files 重疊提示（where_overlap）測試。

對照：同一份未完成票 fixture，新票 where.files 有重疊與無重疊各跑一次，
斷言輸出不同（test-assertion-design E1）。
"""
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from ticket_system.lib import where_overlap

SHARED = ".claude/skills/worktree/scripts/merge_gate.py"
OTHER = "docs/unrelated.md"

TICKETS = {
    "3.3.0": [
        {"id": "3.3.0-W1-001", "title": "重疊票", "status": "pending",
         "where": {"files": [SHARED, "a.py"]}},
        {"id": "3.3.0-W1-002", "title": "已完成票", "status": "completed",
         "where": {"files": [SHARED]}},
        {"id": "3.3.0-W1-099", "title": "自身", "status": "pending",
         "where": {"files": [SHARED]}},
    ],
    "3.4.0": [
        {"id": "3.4.0-W1-001", "title": "規劃版本進行中", "status": "in_progress",
         "where": {"files": [SHARED]}},
    ],
}


def _list(version):
    return TICKETS.get(version, [])


def _find(files):
    return where_overlap.find_overlapping_tickets(
        "3.3.0-W1-099", files, ["3.3.0", "3.4.0"], _list
    )


def test_overlap_vs_no_overlap_output_differs():
    with_overlap = where_overlap.format_overlap_hint(_find([SHARED]))
    without = where_overlap.format_overlap_hint(_find([OTHER]))

    assert with_overlap != without
    assert without == ""
    assert "3.3.0-W1-001" in with_overlap
    assert "重疊票" in with_overlap
    assert SHARED in with_overlap
    assert "3.4.0-W1-001" in with_overlap


def test_excludes_self_and_completed():
    ids = {t["id"] for t in _find([SHARED])}
    assert ids == {"3.3.0-W1-001", "3.4.0-W1-001"}


def test_failure_goes_to_stderr_without_raising(monkeypatch):
    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(where_overlap, "_scan_versions", boom)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        where_overlap.print_where_overlap_hint("3.3.0-W1-099", [SHARED])
    assert out.getvalue() == ""
    assert "boom" in err.getvalue()
