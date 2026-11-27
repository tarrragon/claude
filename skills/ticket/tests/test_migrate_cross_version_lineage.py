"""migrate 跨版本遷移子票時保留 parent_id 與父票 children 血緣。

跨版本遷移只換版本、父子關係不變：新票 parent_id 保留指向原父票，
原父票 children 把舊號改寫為新號。同版本改號為根票是刻意重排階層，仍清為 null。

E1 對照：同一組父子 fixture，跨版本目標與同版本目標兩側產物不同。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ticket_system.lib import git_ops, git_utils
from ticket_system.lib.parser import parse_frontmatter
from ticket_system.lib.paths import get_ticket_path

_VX = "0.0.0"
_VY = "0.0.1"
_PARENT = "0.0.0-W0-001"
_CHILD = "0.0.0-W0-001.1"
_SIBLING = "0.0.0-W0-001.2"
_GRANDCHILD = "0.0.0-W0-001.1.1"
_CROSS_ROOT = "0.0.1-W0-005"
_CROSS_GRANDCHILD = "0.0.1-W0-005.1"
_SAME_ROOT = "0.0.0-W0-009"

_FM = """---
id: {tid}
title: t
type: IMP
status: pending
version: {ver}
wave: 0
priority: P2
who:
  current: tester
  history: {{}}
what: w
when: n
where:
  layer: Infrastructure
  files: []
why: y
how:
  task_type: Implementation
  strategy: s
children: {children}
blockedBy: []
relatedTo: []
spawned_tickets: []
source_ticket: null
acceptance:
- '[ ] a1'
assigned: false
tdd_stage: []
{extra}---

# Execution Log
"""


def _chain(parent: str, depth: int, seq: str) -> str:
    return (f"parent_id: {parent}\nchain:\n  root: {_PARENT}\n  parent: {parent}\n"
            f"  depth: {depth}\n  sequence: {seq}\n")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True, text=True).stdout


def _seed(tid: str, children: str = "[]", extra: str = "") -> None:
    ver = tid.split("-")[0]
    path = get_ticket_path(ver, tid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_FM.format(tid=tid, ver=ver, children=children, extra=extra),
                    encoding="utf-8")


def _fm(tid: str) -> dict:
    path = get_ticket_path(tid.split("-")[0], tid)
    return parse_frontmatter(path.read_text(encoding="utf-8"))[0]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("TICKET_SYSTEM_TEST_ISOLATION", "1")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "todolist.yaml").write_text(
        yaml.dump({"versions": [{"version": _VX, "status": "active"},
                                {"version": _VY, "status": "active"}]}),
        encoding="utf-8")
    _seed(_PARENT, children=f"[{_CHILD}, {_SIBLING}]")
    _seed(_CHILD, children=f"[{_GRANDCHILD}]", extra=_chain(_PARENT, 1, "[1, 1]"))
    _seed(_SIBLING, extra=_chain(_PARENT, 1, "[1, 2]"))
    _seed(_GRANDCHILD, extra=_chain(_CHILD, 2, "[1, 1, 1]"))
    (tmp_path / ".gitignore").write_text(".claude/hook-logs/\n.claude/migration-backups/\n",
                                         encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 0.0)
    monkeypatch.setattr(git_utils, "_sleep", lambda _s: None)
    monkeypatch.setattr(git_ops.time, "sleep", lambda _s: None)
    return tmp_path


def _run(monkeypatch, *argv: str) -> int:
    from ticket_system.scripts import ticket as cli

    monkeypatch.setattr(sys, "argv", ["ticket", "migrate", *argv, "--version", _VX,
                                      "--no-backup"])
    try:
        return cli.main() or 0
    except SystemExit as exc:
        return int(exc.code or 0)


def _child_ids(tid: str) -> list:
    return [c.get("id") if isinstance(c, dict) else c for c in _fm(tid)["children"]]


class TestCrossVersionKeepsLineage:
    def test_single_leaf_keeps_parent_and_rewrites_children(self, repo, monkeypatch):
        assert _run(monkeypatch, _SIBLING, _CROSS_ROOT) == 0
        migrated = _fm(_CROSS_ROOT)
        assert migrated["parent_id"] == _PARENT
        assert _CROSS_ROOT in _child_ids(_PARENT)
        assert _SIBLING not in _child_ids(_PARENT)
        assert _child_ids(_PARENT).count(_CROSS_ROOT) == 1

    def test_subtree_keeps_parent_and_rewrites_children(self, repo, monkeypatch):
        assert _run(monkeypatch, _CHILD, _CROSS_ROOT) == 0
        assert _fm(_CROSS_ROOT)["parent_id"] == _PARENT
        assert _fm(_CROSS_GRANDCHILD)["parent_id"] == _CROSS_ROOT
        assert _child_ids(_PARENT) == [_CROSS_ROOT, _SIBLING]


class TestSameVersionStillClears:
    """E1 對照：同批 fixture、同版本改號為根票，parent_id 清為 null、舊父移除。"""

    def test_single_leaf_cleared(self, repo, monkeypatch):
        assert _run(monkeypatch, _SIBLING, _SAME_ROOT) == 0
        assert _fm(_SAME_ROOT)["parent_id"] is None
        assert _SIBLING not in _child_ids(_PARENT)
        assert _SAME_ROOT not in _child_ids(_PARENT)

    def test_e1_cross_and_same_version_products_differ(self, repo, monkeypatch):
        assert _run(monkeypatch, _SIBLING, _CROSS_ROOT) == 0
        cross = _fm(_CROSS_ROOT)["parent_id"]
        _git(repo, "reset", "-q", "--hard", "HEAD~1")
        assert _run(monkeypatch, _SIBLING, _SAME_ROOT) == 0
        assert cross != _fm(_SAME_ROOT)["parent_id"]
