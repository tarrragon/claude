"""0.4.1-W2-009: `ticket track phase` 同步寫入 tdd_phase + tdd_phase_source=manual。

Why: claim --as 的自動推導需要辨識「使用者已手動指定 phase」以避免覆蓋
（acceptance 2）。本測試驗證 execute_phase 的寫入端行為，
與 test_claim_auto_tdd_phase.py 的讀取端（claim 不覆蓋 manual）互補。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib import ticket_loader
from ticket_system.lib.parser import parse_frontmatter


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_ticket(path: Path, tid: str) -> None:
    lines = [
        "---",
        f"id: {tid}",
        "title: phase target",
        "type: IMP",
        "status: in_progress",
        "assigned: true",
        "started_at: null",
        "tdd_phase: phase1",
        "acceptance: []",
        "children: []",
        "blockedBy: []",
        "---",
        "",
        "body",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def patch_ticket_paths(tmp_ticket_dir: Path, monkeypatch):
    from ticket_system.commands import track_relations as tr_mod

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    monkeypatch.setattr(ticket_loader, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(tr_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(tr_mod, "load_ticket", _fake_load_ticket)


def test_execute_phase_writes_tdd_phase_as_manual(
    tmp_ticket_dir: Path, patch_ticket_paths
):
    from ticket_system.commands.track_relations import execute_phase

    tid = "0.0.0-W0-EXECPHASE1"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid)

    args = argparse.Namespace(ticket_id=tid, phase="phase3b", agent="fennel-go-developer")
    assert execute_phase(args, "0.0.0") == 0

    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm["current_phase"] == "Phase 3b"
    assert fm["tdd_phase"] == "phase3b"
    assert fm["tdd_phase_source"] == "manual"
