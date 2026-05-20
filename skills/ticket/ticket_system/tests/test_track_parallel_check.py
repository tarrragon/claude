"""Tests for ticket_system/commands/track_parallel_check.py (W17-203.1).

涵蓋 acceptance 4 要求的 5 案例：
1. 全互斥：3 children 檔案完全不重 → 一個可平行集合
2. 全衝突：3 children 全改同一檔 → 一個 conflict group
3. 混合：2 互斥 + 2 衝突
4. PC-137 觸發：5 children 全觸及 .claude/（互斥）→ warning 建議拆批
5. 空 children：parent 無 children → exit 1 + stderr
"""

from __future__ import annotations

import argparse
import io
import sys
from typing import List

import pytest

from ticket_system.commands import track_parallel_check as mod
from ticket_system.commands.track_parallel_check import execute_parallel_check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mk(ticket_id, files=None, status="pending", parent_id=None, children=None):
    return {
        "id": ticket_id,
        "status": status,
        "parent_id": parent_id,
        "children": children or [],
        "where": {"files": list(files or [])},
    }


def _run(monkeypatch, tickets: List[dict], target_id: str) -> tuple[int, str, str]:
    monkeypatch.setattr(mod, "list_tickets", lambda version: tickets)

    args = argparse.Namespace(ticket_id=target_id)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        rc = execute_parallel_check(args)
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return rc, out_buf.getvalue(), err_buf.getvalue()


# ---------------------------------------------------------------------------
# 1. 全互斥
# ---------------------------------------------------------------------------

def test_all_disjoint_yields_parallel_set(monkeypatch):
    parent = _mk(
        "0.18.0-W17-900",
        children=[
            "0.18.0-W17-900.1",
            "0.18.0-W17-900.2",
            "0.18.0-W17-900.3",
        ],
    )
    children = [
        _mk("0.18.0-W17-900.1", files=["docs/a.md"]),
        _mk("0.18.0-W17-900.2", files=["src/b.js"]),
        _mk("0.18.0-W17-900.3", files=["tests/c.py"]),
    ]
    rc, out, err = _run(monkeypatch, [parent] + children, "0.18.0-W17-900")
    assert rc == 0, err
    assert "[可平行派發] 3 ticket(s)" in out
    assert "[衝突任務] 0 group(s)" in out
    assert "PC-137 警告] 無" in out


# ---------------------------------------------------------------------------
# 2. 全衝突
# ---------------------------------------------------------------------------

def test_all_conflict_same_file(monkeypatch):
    parent = _mk(
        "0.18.0-W17-901",
        children=[
            "0.18.0-W17-901.1",
            "0.18.0-W17-901.2",
            "0.18.0-W17-901.3",
        ],
    )
    same = ".claude/skills/ticket/SKILL.md"
    children = [
        _mk("0.18.0-W17-901.1", files=[same]),
        _mk("0.18.0-W17-901.2", files=[same]),
        _mk("0.18.0-W17-901.3", files=[same]),
    ]
    rc, out, err = _run(monkeypatch, [parent] + children, "0.18.0-W17-901")
    assert rc == 0, err
    assert "[可平行派發] 0 ticket(s)" in out
    assert "[衝突任務] 1 group(s)" in out
    assert "0.18.0-W17-901.1" in out
    assert "0.18.0-W17-901.2" in out
    assert "0.18.0-W17-901.3" in out


# ---------------------------------------------------------------------------
# 3. 混合：2 互斥 + 2 衝突
# ---------------------------------------------------------------------------

def test_mixed_parallel_and_conflict(monkeypatch):
    parent = _mk(
        "0.18.0-W17-902",
        children=[
            "0.18.0-W17-902.1",
            "0.18.0-W17-902.2",
            "0.18.0-W17-902.3",
            "0.18.0-W17-902.4",
        ],
    )
    children = [
        _mk("0.18.0-W17-902.1", files=["docs/a.md"]),
        _mk("0.18.0-W17-902.2", files=["src/b.js"]),
        _mk("0.18.0-W17-902.3", files=["shared/x.py"]),
        _mk("0.18.0-W17-902.4", files=["shared/x.py"]),
    ]
    rc, out, err = _run(monkeypatch, [parent] + children, "0.18.0-W17-902")
    assert rc == 0, err
    assert "[可平行派發] 2 ticket(s)" in out
    assert "[衝突任務] 1 group(s)" in out
    # 衝突組應該含 .3 和 .4
    assert "0.18.0-W17-902.3" in out
    assert "0.18.0-W17-902.4" in out


# ---------------------------------------------------------------------------
# 4. PC-137 觸發
# ---------------------------------------------------------------------------

def test_pc137_warning_when_three_claude_edits_parallel(monkeypatch):
    parent = _mk(
        "0.18.0-W17-903",
        children=[f"0.18.0-W17-903.{i}" for i in range(1, 6)],
    )
    # 5 個 children 都改 .claude/ 但檔案互斥（不同子模組）
    children = [
        _mk("0.18.0-W17-903.1", files=[".claude/hooks/a.py"]),
        _mk("0.18.0-W17-903.2", files=[".claude/agents/b.md"]),
        _mk("0.18.0-W17-903.3", files=[".claude/pm-rules/c.md"]),
        _mk("0.18.0-W17-903.4", files=[".claude/error-patterns/d.md"]),
        _mk("0.18.0-W17-903.5", files=[".claude/methodologies/e.md"]),
    ]
    rc, out, err = _run(monkeypatch, [parent] + children, "0.18.0-W17-903")
    assert rc == 0, err
    assert "[可平行派發] 5 ticket(s)" in out
    assert "PC-137 警告" in out
    assert "建議拆批" in out
    assert ">= 3" in out


# ---------------------------------------------------------------------------
# 5. 空 children
# ---------------------------------------------------------------------------

def test_empty_children_returns_exit_1(monkeypatch):
    parent = _mk("0.18.0-W17-904", children=[])
    rc, out, err = _run(monkeypatch, [parent], "0.18.0-W17-904")
    assert rc == 1
    assert "無 pending children" in err


# ---------------------------------------------------------------------------
# 額外邊界：target 不存在
# ---------------------------------------------------------------------------

def test_missing_target_returns_exit_1(monkeypatch):
    rc, out, err = _run(monkeypatch, [], "0.18.0-W17-999")
    assert rc == 1
    assert "找不到 ticket" in err


# ---------------------------------------------------------------------------
# 額外邊界：invalid ID 格式
# ---------------------------------------------------------------------------

def test_invalid_ticket_id_returns_exit_2(monkeypatch):
    rc, out, err = _run(monkeypatch, [], "not-a-valid-id")
    assert rc == 2
    assert "無效的 ticket ID 格式" in err
