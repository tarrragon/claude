"""set-coordination 子命令與 create --coordination 旗標測試（E1 對照）。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter
from ticket_system.lib.ticket_builder import create_ticket_frontmatter

TID = "0.0.0-W0-200"


def _write(path: Path, coordination: bool = False) -> None:
    lines = ["---", f"id: {TID}", "title: t", "type: IMP", "status: pending",
             "children: []", "blockedBy: []", "spawned_tickets: []", "acceptance: []"]
    if coordination:
        lines.append("coordination: true")
    path.write_text("\n".join(lines) + "\n---\n\n# Execution Log\n", encoding="utf-8")


def _fm(path: Path) -> dict:
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm


@pytest.fixture
def ticket_path(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / f"{TID}.md"
    _write(path)

    def _load(version, ticket_id):
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        fm["_body"], fm["_path"] = body, str(path)
        return fm, None

    from ticket_system.commands import track_set_coordination as mod
    monkeypatch.setattr(mod, "get_ticket_path", lambda v, t: path)
    monkeypatch.setattr(mod, "load_and_validate_ticket", _load)
    monkeypatch.setattr(mod, "resolve_ticket_path", lambda t, v, i: path)
    from ticket_system.lib import git_utils
    monkeypatch.setattr(git_utils, "commit_ticket_md_reporting", lambda *a, **k: False)
    return path


def _call(clear: bool = False) -> int:
    from ticket_system.commands.track_set_coordination import execute_set_coordination
    return execute_set_coordination(argparse.Namespace(ticket_id=TID, clear=clear), "0.0.0")


def test_set_then_clear_changes_frontmatter(ticket_path):
    assert "coordination" not in _fm(ticket_path)
    assert _call() == 0
    assert _fm(ticket_path).get("coordination") is True
    assert _call() == 0  # 冪等
    assert _fm(ticket_path).get("coordination") is True
    assert _call(clear=True) == 0
    assert "coordination" not in _fm(ticket_path)


def _config(coordination: bool) -> dict:
    return {
        "ticket_id": TID, "version": "0.0.0", "wave": 0, "title": "t",
        "ticket_type": "IMP", "priority": "P2", "who": "x", "what": "w",
        "when": "w", "where_layer": "Domain", "why": "y",
        "how_task_type": "Implementation", "how_strategy": "s",
        "coordination": coordination,
    }


def test_create_with_and_without_flag_differ():
    with_flag = create_ticket_frontmatter(_config(True))
    without = create_ticket_frontmatter(_config(False))
    assert with_flag.get("coordination") is True
    assert "coordination" not in without
