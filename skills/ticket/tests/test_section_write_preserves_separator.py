"""章節寫入保留章節尾的 --- 分隔線（#33）。

三條寫入路徑：append-log 附加、append-log --replace、add-spawn-request。
每條以寫入前後 `---` 行數相同作斷言；各附「無分隔線」對照，確認未憑空補線。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib import ticket_loader
from ticket_system.lib.parser import parse_frontmatter


@pytest.fixture
def tickets(tmp_path: Path, monkeypatch):
    def _path(version: str, ticket_id: str) -> Path:
        return tmp_path / f"{ticket_id}.md"

    def _load(version: str, ticket_id: str):
        path = _path(version, ticket_id)
        if not path.exists():
            return None
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    from ticket_system.commands import track_acceptance as ta_mod
    from ticket_system.lib import git_utils

    monkeypatch.setattr(ticket_loader, "get_ticket_path", _path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _load)
    monkeypatch.setattr(ta_mod, "get_ticket_path", _path)
    monkeypatch.setattr(ta_mod, "load_ticket", _load)
    monkeypatch.setattr(git_utils, "commit_ticket_md_reporting", lambda *a, **k: False)
    return _path


def _write(path: Path, body: str) -> None:
    fm = (
        "---\nid: T-1\ntitle: t\ntype: IMP\nstatus: in_progress\nassigned: true\n"
        "children: []\nblockedBy: []\nacceptance: []\nspawned_tickets: []\n---\n\n"
    )
    path.write_text(fm + body, encoding="utf-8")


def _sep_count(path: Path) -> int:
    _, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return sum(1 for line in body.split("\n") if line.strip() == "---")


def _append(section: str, content: str, replace: bool = False) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(ticket_id="T-1", section=section, content=content, replace=replace)
    return execute_append_log(ns, "0.0.0")


BODY_WITH_SEP = (
    "## Problem Analysis\n\n### 問題根因\n\n舊內容\n\n---\n\n"
    "## Solution\n\nx\n\n---\n\n"
    "## Spawn Requests\n\n（無）\n\n---\n\n"
    "## Completion Info\n\ny\n"
)
BODY_NO_SEP = BODY_WITH_SEP.replace("\n---\n", "\n")


def test_append_keeps_separator(tickets):
    path = tickets("0.0.0", "T-1")
    _write(path, BODY_WITH_SEP)
    before = _sep_count(path)
    assert _append("Problem Analysis", "新內容") == 0
    assert _sep_count(path) == before
    text = path.read_text(encoding="utf-8")
    assert "新內容\n\n---\n\n## Solution" in text


def test_replace_keeps_separator(tickets):
    path = tickets("0.0.0", "T-1")
    _write(path, BODY_WITH_SEP)
    before = _sep_count(path)
    assert _append("Problem Analysis", "取代內容", replace=True) == 0
    assert _sep_count(path) == before
    assert "取代內容\n\n---\n\n## Solution" in path.read_text(encoding="utf-8")


def test_spawn_request_keeps_separator(tickets):
    from ticket_system.commands.track_acceptance import execute_add_spawn_request

    path = tickets("0.0.0", "T-1")
    _write(path, BODY_WITH_SEP)
    before = _sep_count(path)
    ns = argparse.Namespace(
        ticket_id="T-1", what="w", why="y", type="IMP", priority="P2", files=[], context=""
    )
    assert execute_add_spawn_request(ns, "0.0.0") == 0
    assert _sep_count(path) == before
    assert "\n\n---\n\n## Completion Info" in path.read_text(encoding="utf-8")


def test_no_separator_stays_without_separator(tickets):
    """對照：原本無分隔線的章節寫入後不憑空出現分隔線。"""
    path = tickets("0.0.0", "T-1")
    _write(path, BODY_NO_SEP)
    assert _sep_count(path) == 0
    assert _append("Problem Analysis", "新內容") == 0
    assert _sep_count(path) == 0
