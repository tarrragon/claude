"""migrate 同步改寫 handoff pending 內的舊 ticket ID。

E1 對照：同一 fixture 下，pending 內「指向被遷移票」與「指向無關票」兩類檔案，
前者被改寫與改名、後者位元組不變；無 pending 目錄時 migrate 行為不變。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ticket_system.lib import git_ops, git_utils
from ticket_system.lib.paths import get_ticket_path

_VER = "0.0.0"
_OLD = "0.0.0-W0-010"
_NEW = "0.0.0-W0-020"
_CHILD = "0.0.0-W0-010.1"
_NEW_CHILD = "0.0.0-W0-020.1"
_OTHER = "0.0.0-W0-050"

_FM = """---
id: {tid}
title: t
type: IMP
status: pending
version: 0.0.0
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


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout


def _seed(tid: str, children: str = "[]", extra: str = "") -> None:
    path = get_ticket_path(_VER, tid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_FM.format(tid=tid, children=children, extra=extra), encoding="utf-8")


def _pending(repo: Path) -> Path:
    return repo / ".claude" / "handoff" / "pending"


def _write_handoff(repo: Path, name: str, **fields) -> Path:
    d = _pending(repo)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.json"
    path.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("TICKET_SYSTEM_TEST_ISOLATION", "1")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "todolist.yaml").write_text(
        yaml.dump({"versions": [{"version": _VER, "status": "active"}]}), encoding="utf-8")
    _seed(_OLD)
    _seed(_OTHER)
    (tmp_path / ".gitignore").write_text(
        ".claude/hook-logs/\n.claude/migration-backups/\n.claude/handoff\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 0.0)
    monkeypatch.setattr(git_ops.time, "sleep", lambda _s: None)
    return tmp_path


def _run(monkeypatch, *argv: str) -> int:
    from ticket_system.scripts import ticket as cli

    monkeypatch.setattr(sys, "argv", ["ticket", "migrate", *argv, "--version", _VER,
                                      "--no-backup"])
    try:
        return cli.main() or 0
    except SystemExit as exc:
        return int(exc.code or 0)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestHandoffPendingRewrite:
    def test_old_id_replaced_and_file_renamed(self, repo, monkeypatch):
        _write_handoff(repo, _OLD, ticket_id=_OLD, from_ticket=_OLD,
                       direction="context-refresh", timestamp="t")
        assert _run(monkeypatch, _OLD, _NEW) == 0
        assert not (_pending(repo) / f"{_OLD}.json").exists()
        data = _load(_pending(repo) / f"{_NEW}.json")
        assert data["ticket_id"] == _NEW and data["from_ticket"] == _NEW
        assert _OLD not in json.dumps(data)

    def test_target_fields_and_direction_suffix_rewritten(self, repo, monkeypatch):
        path = _write_handoff(
            repo, _OTHER, ticket_id=_OTHER, direction=f"to-sibling:{_OLD}",
            target_ticket_id=_OLD, timestamp="t")
        assert _run(monkeypatch, _OLD, _NEW) == 0
        data = _load(path)  # 來源票未被遷移 -> 檔名不變，內容改寫
        assert data["target_ticket_id"] == _NEW
        assert data["direction"] == f"to-sibling:{_NEW}"
        assert data["ticket_id"] == _OTHER

    def test_unrelated_pending_untouched(self, repo, monkeypatch):
        """E1 對照：指向無關票的 pending 檔位元組不變"""
        path = _write_handoff(repo, _OTHER, ticket_id=_OTHER, direction="context-refresh",
                              timestamp="t")
        before = path.read_bytes()
        assert _run(monkeypatch, _OLD, _NEW) == 0
        assert path.read_bytes() == before

    def test_no_pending_dir_behaviour_unchanged(self, repo, monkeypatch):
        """對照：無 pending 目錄時 migrate 成功且不建立 handoff 目錄"""
        assert not (repo / ".claude" / "handoff").exists()
        assert _run(monkeypatch, _OLD, _NEW) == 0
        assert get_ticket_path(_VER, _NEW).exists()
        assert not (repo / ".claude" / "handoff").exists()

    def test_subtree_members_all_rewritten(self, repo, monkeypatch):
        _seed(_OLD, children=f"[{_CHILD}]")
        _seed(_CHILD, extra=(f"parent_id: {_OLD}\nchain:\n  root: {_OLD}\n"
                             f"  parent: {_OLD}\n  depth: 1\n  sequence: [10, 1]\n"))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "tree")
        _write_handoff(repo, _CHILD, ticket_id=_CHILD, direction="context-refresh",
                       timestamp="t")
        assert _run(monkeypatch, _OLD, _NEW) == 0
        data = _load(_pending(repo) / f"{_NEW_CHILD}.json")
        assert data["ticket_id"] == _NEW_CHILD
        assert not (_pending(repo) / f"{_CHILD}.json").exists()
