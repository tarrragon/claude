"""0.4.0-W1-069 — 不接受 ticket_id 位置參數名的 track 子命令，版本解析須從 ID 取得。

重現：todolist 有 active 版本 0.2.0 與 planned 版本 0.3.0，票建在 0.3.0。
set-parent / add-child 的位置參數是 child_id / parent_id（非 ticket_id），
execute() 只從 args.ticket_id 取版本，落到自動偵測（只看 active）而找不到票。
E1 對照：同一票給 --version 0.3.0 時成功。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.commands import track
from ticket_system.lib.parser import parse_frontmatter


def _ticket_text(tid: str, parent: str | None = None, children: str = "[]") -> str:
    parent_line = f"parent_id: {parent}" if parent else "parent_id: null"
    return "\n".join([
        "---", f"id: {tid}", "title: t", "type: IMP", "status: pending",
        "version: 0.3.0", "wave: 1", parent_line, f"children: {children}",
        "blockedBy: []", "relatedTo: []", "acceptance: []",
        "spawned_tickets: []", "assigned: false", "started_at: null",
        "tdd_phase: phase1", "---", "", "body", "",
    ])


@pytest.fixture
def planned_project(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "todolist.yaml").parent.mkdir(parents=True)
    (docs / "todolist.yaml").write_text(
        "versions:\n"
        "  - version: 0.2.0\n    status: active\n"
        "  - version: 0.3.0\n    status: planned\n",
        encoding="utf-8",
    )
    tdir = docs / "work-logs" / "v0" / "v0.3" / "v0.3.0" / "tickets"
    tdir.mkdir(parents=True)
    (docs / "work-logs" / "v0" / "v0.2" / "v0.2.0" / "tickets").mkdir(parents=True)
    (tdir / "0.3.0-W1-001.md").write_text(_ticket_text("0.3.0-W1-001", children="[0.3.0-W1-012]"), encoding="utf-8")
    (tdir / "0.3.0-W1-012.md").write_text(_ticket_text("0.3.0-W1-012", parent="0.3.0-W1-001"), encoding="utf-8")
    (tdir / "0.3.0-W1-013.md").write_text(_ticket_text("0.3.0-W1-013"), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tdir


def _run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    track.register(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["track", *argv])
    return track.execute(args)


def _fm(tdir: Path, tid: str) -> dict:
    fm, _ = parse_frontmatter((tdir / f"{tid}.md").read_text(encoding="utf-8"))
    return fm


def test_set_parent_clear_with_explicit_version_succeeds(planned_project):
    """E1 對照組：給 --version 成功。"""
    rc = _run(["set-parent", "0.3.0-W1-012", "--clear", "--version", "0.3.0"])
    assert rc == 0
    assert not _fm(planned_project, "0.3.0-W1-012").get("parent_id")


def test_set_parent_clear_without_version_resolves_from_id(planned_project):
    rc = _run(["set-parent", "0.3.0-W1-012", "--clear"])
    assert rc == 0
    assert not _fm(planned_project, "0.3.0-W1-012").get("parent_id")


def test_add_child_without_version_resolves_from_parent_id(planned_project):
    rc = _run(["add-child", "0.3.0-W1-013", "0.3.0-W1-012"])
    assert rc == 0
    assert "0.3.0-W1-012" in (_fm(planned_project, "0.3.0-W1-013").get("children") or [])


def test_explicit_version_still_wins_over_id(planned_project):
    """--version 顯式值優先，不被 ID 覆蓋（票在 0.3.0，指到 0.2.0 應找不到）。"""
    rc = _run(["set-parent", "0.3.0-W1-012", "--clear", "--version", "0.2.0"])
    assert rc != 0


def test_ticket_ids_first_id_version_used(planned_project):
    ns = argparse.Namespace(ticket_ids="0.3.0-W1-012,0.3.0-W1-013", version=None)
    assert track._ticket_id_arg_version(ns) == "0.3.0"
