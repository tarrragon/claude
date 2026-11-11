"""ticket track resolve：以舊票號查出現行票號（依 previous_ids）。"""
import argparse
from pathlib import Path

import pytest

from ticket_system.commands import track_query
from ticket_system.lib import paths


def _ticket(root: Path, rel_dir: str, ticket_id: str, status: str, previous=None) -> None:
    d = root / "docs" / "work-logs" / rel_dir / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    prev = ""
    if previous:
        prev = "previous_ids:\n" + "".join(f"- {p}\n" for p in previous)
    (d / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\nstatus: {status}\n{prev}---\n\n# body\n", encoding="utf-8"
    )


@pytest.fixture
def state_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "get_ticket_state_root", lambda: tmp_path)
    # 連續改號：0.3.1-W1-005 → 0.4.0-W1-002 → 1.0.0-W1-009
    _ticket(tmp_path, "v1/v1.0/v1.0.0", "1.0.0-W1-009", "pending",
            previous=["0.3.1-W1-005", "0.4.0-W1-002"])
    _ticket(tmp_path, "v0/v0.3/v0.3.1", "0.3.1-W1-001", "completed")
    return tmp_path


def _run(ticket_id: str) -> int:
    return track_query.execute_resolve(argparse.Namespace(ticket_id=ticket_id), "0.0.0")


def test_oldest_id_resolves_to_current(state_root, capsys):
    assert _run("0.3.1-W1-005") == 0
    out = capsys.readouterr().out
    assert "0.3.1-W1-005 → 1.0.0-W1-009" in out
    assert "pending" in out


def test_intermediate_id_resolves_to_current(state_root, capsys):
    assert _run("0.4.0-W1-002") == 0
    assert "→ 1.0.0-W1-009" in capsys.readouterr().out


def test_current_id_reported_as_current(state_root, capsys):
    assert _run("0.3.1-W1-001") == 0
    assert "仍是現行票號" in capsys.readouterr().out


def test_unknown_id_fails_with_message(state_root, capsys):
    assert _run("0.3.1-W1-999") == 1
    out = capsys.readouterr().out
    assert "找不到 0.3.1-W1-999" in out
    assert "git log --follow" in out
