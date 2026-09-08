"""`ticket track list` In Progress 列 lease 標記測試（三態 + 向後相容）。

背景：`SKILL.md` fallback 步驟假設 `ticket track list --status pending
in_progress` 的輸出對 in_progress 票帶 `[LIVE]`／`[RECLAIMABLE]` 標記
（同 `ticket track dashboard`），但實作先前僅 dashboard/runqueue 有渲染，
list 完全不帶標記。本檔驗證 list 的 table 格式輸出補齊同一套標記。

策略：monkeypatch `track_query.list_tickets` 提供 fixture 票，
monkeypatch `track_query.lease.load_registry_snapshot` 控制 registry
快照，呼叫 `_execute_list_single_version` 並以 `capsys` 擷取 stdout（同
`test_track_list_top.py` 既有模式）。
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

import pytest

from ticket_system.commands import track_query


def _mk_ticket(
    tid: str,
    status: str = "in_progress",
    title: str = "impl",
    agent: str = "thyme",
) -> Dict[str, Any]:
    return {
        "id": tid,
        "title": title,
        "status": status,
        "wave": 3,
        "version": "0.18.0",
        "created": "2026-01-01",
        "priority": "P1",
        "who": {"current": agent},
        "what": title,
    }


def _ns(status: Optional[List[str]] = None) -> argparse.Namespace:
    return argparse.Namespace(
        pending=False,
        in_progress=False,
        completed=False,
        blocked=False,
        status=status,
        wave=None,
        format="table",
        version="0.18.0",
        top=None,
        list_all=False,
    )


def _run_list(monkeypatch, tickets, registry_snapshot, capsys) -> str:
    monkeypatch.setattr(track_query, "list_tickets", lambda v: tickets)
    monkeypatch.setattr(
        track_query.lease, "load_registry_snapshot", lambda: registry_snapshot
    )
    args = _ns(status=["in_progress"])
    track_query._execute_list_single_version(args, "0.18.0", None)
    return capsys.readouterr().out


class _FakePmRegistry:
    """最小假物件：`is_fresh(heartbeat_ts, now)` 僅比對字面 "FRESH"，
    同 `test_track_dashboard.py` Group J 既有 fixture 設計。"""

    def is_fresh(self, heartbeat_ts: Any, now: Any) -> bool:
        return heartbeat_ts == "FRESH"


def _mk_registry(ticket_id: str, session_id: str, heartbeat_ts: str) -> Dict[str, Any]:
    return {
        "sessions": {
            session_id: {"tickets": [ticket_id], "heartbeat_ts": heartbeat_ts},
        },
    }


# ---------------------------------------------------------------------------
# 三態
# ---------------------------------------------------------------------------


def test_live_tag_for_fresh_session_owner(monkeypatch, capsys):
    """FRESH session 持有 → in_progress 列附 [LIVE]。"""
    tickets = [_mk_ticket("0.18.0-W3-801")]
    registry = _mk_registry("0.18.0-W3-801", "sess-a", "FRESH")
    out = _run_list(monkeypatch, tickets, (registry, _FakePmRegistry()), capsys)
    target_line = next(ln for ln in out.splitlines() if "0.18.0-W3-801" in ln)
    assert "[LIVE]" in target_line
    assert "[RECLAIMABLE]" not in target_line


def test_reclaimable_tag_for_stale_session_owner(monkeypatch, capsys):
    """STALE session 持有 → in_progress 列附 [RECLAIMABLE]。"""
    tickets = [_mk_ticket("0.18.0-W3-802")]
    registry = _mk_registry("0.18.0-W3-802", "sess-b", "STALE")
    out = _run_list(monkeypatch, tickets, (registry, _FakePmRegistry()), capsys)
    target_line = next(ln for ln in out.splitlines() if "0.18.0-W3-802" in ln)
    assert "[RECLAIMABLE]" in target_line
    assert "[LIVE]" not in target_line


def test_reclaimable_tag_when_registry_untracked(monkeypatch, capsys):
    """registry 已載入但未追蹤該票 lease（無 owner）→ 視為 RECLAIMABLE，
    與 dashboard 同判準（owner=None 不降級為 untracked）。"""
    tickets = [_mk_ticket("0.18.0-W3-803")]
    registry = {"sessions": {}}
    out = _run_list(monkeypatch, tickets, (registry, _FakePmRegistry()), capsys)
    target_line = next(ln for ln in out.splitlines() if "0.18.0-W3-803" in ln)
    assert "[RECLAIMABLE]" in target_line
    assert "[LIVE]" not in target_line


def test_registry_unavailable_degrades_to_no_tag(monkeypatch, capsys):
    """registry 不可用（pm_registry=None）→ 無標記，既有輸出格式不受影響
    （Never break userspace）。"""
    tickets = [_mk_ticket("0.18.0-W3-804")]
    out = _run_list(monkeypatch, tickets, ({}, None), capsys)
    target_line = next(ln for ln in out.splitlines() if "0.18.0-W3-804" in ln)
    assert "[LIVE]" not in target_line
    assert "[RECLAIMABLE]" not in target_line


def test_pending_ticket_never_tagged_even_with_registry_entry(monkeypatch, capsys):
    """非 in_progress 票（如 pending）即使巧合出現在 registry 中，也不附
    標記——本命令僅對 in_progress 列渲染 lease 標記。"""
    tickets = [_mk_ticket("0.18.0-W3-805", status="pending")]
    registry = _mk_registry("0.18.0-W3-805", "sess-c", "FRESH")
    args = _ns(status=["pending"])
    monkeypatch.setattr(track_query, "list_tickets", lambda v: tickets)
    monkeypatch.setattr(
        track_query.lease, "load_registry_snapshot",
        lambda: (registry, _FakePmRegistry()),
    )
    track_query._execute_list_single_version(args, "0.18.0", None)
    out = capsys.readouterr().out
    target_line = next(ln for ln in out.splitlines() if "0.18.0-W3-805" in ln)
    assert "[LIVE]" not in target_line
    assert "[RECLAIMABLE]" not in target_line
