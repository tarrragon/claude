"""commit_files_isolated 範圍自檢子集比對（0.4.1-W1-034）。

列出但淨變更為零的路徑視為合法；清單外有變更仍 failed 且不 update-ref。
真實 tmp git repo；add-child 情境走真實 CLI 入口。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ticket_system.lib import git_ops, git_utils
from ticket_system.lib.parser import parse_frontmatter, save_ticket
from ticket_system.lib.paths import get_ticket_path

_VER = "0.0.0"
_PARENT = "0.0.0-W0-001"
_CHILD = "0.0.0-W0-002"
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
children: []
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
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("TICKET_SYSTEM_TEST_ISOLATION", "1")
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 0.0)
    monkeypatch.setattr(git_ops.time, "sleep", lambda _s: None)
    monkeypatch.setattr(git_ops, "_prevalidate_guard_env", lambda *a, **k: None, raising=False)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "todolist.yaml").write_text(
        yaml.dump({"versions": [{"version": _VER, "status": "active"}]}), encoding="utf-8")
    for name in ("a", "b", "c"):
        (tmp_path / f"{name}.txt").write_text(f"{name}\n", encoding="utf-8")
    linked = f"parent_id: {_PARENT}\nchain:\n  root: {_PARENT}\n  parent: {_PARENT}\n"
    for tid, extra in ((_PARENT, ""), (_CHILD, linked)):
        p = get_ticket_path(_VER, tid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_FM.format(tid=tid, extra=extra), encoding="utf-8")
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        save_ticket(fm, p)  # 正規化，使後續重存位元組相同
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").strip()


def _head_files(repo: Path) -> list[str]:
    return [Path(f).name for f in
            _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").split()]


def _sneak_stage_c(repo: Path):
    """在 write-tree 前把清單外的 c.txt 塞進臨時 index，模擬範圍外變更。"""
    real = git_ops._run_git_with_lock_retry

    def sneaky(args, **kw):
        if args[:2] == ["git", "write-tree"]:
            (repo / "c.txt").write_text("c2\n", encoding="utf-8")
            real(["git", "add", "--", "c.txt"], **kw)
        return real(args, **kw)

    return sneaky


class TestSubsetScope:
    def test_one_unchanged_path_committed_with_changed_only(self, repo):
        (repo / "a.txt").write_text("a2\n", encoding="utf-8")
        r = git_ops.commit_files_isolated(["a.txt", "b.txt"], "m", cwd=str(repo))
        assert r["status"] == "committed", r
        assert _head_files(repo) == ["a.txt"]
        assert _git(repo, "status", "--porcelain") == ""

    def test_out_of_scope_change_still_fails_without_update_ref(self, repo):
        head = _head(repo)
        (repo / "a.txt").write_text("a2\n", encoding="utf-8")
        with patch.object(git_ops, "_run_git_with_lock_retry", _sneak_stage_c(repo)):
            r = git_ops.commit_files_isolated(["a.txt", "b.txt"], "m", cwd=str(repo))
        assert r["status"] == "failed", r
        assert _head(repo) == head

    def test_all_paths_unchanged_is_noop(self, repo):
        head = _head(repo)
        r = git_ops.commit_files_isolated(["a.txt", "b.txt"], "m", cwd=str(repo))
        assert r["status"] == "empty", r
        assert _head(repo) == head
        assert _git(repo, "status", "--porcelain") == ""


def _cli(monkeypatch, *argv: str) -> int:
    from ticket_system.scripts import ticket as cli

    monkeypatch.setattr(sys, "argv", ["ticket", "track", *argv, "--version", _VER])
    try:
        return cli.main() or 0
    except SystemExit as exc:
        return int(exc.code or 0)


class TestAddChildRealCli:
    def test_child_already_linked_exit_0_and_commits_parent_only(self, repo, monkeypatch, capsys):
        before = _head(repo)
        rc = _cli(monkeypatch, "add-child", _PARENT, _CHILD)
        assert rc == 0, capsys.readouterr()
        assert _head(repo) != before
        assert _head_files(repo) == [f"{_PARENT}.md"]
        assert _git(repo, "status", "--porcelain") == ""

    def test_out_of_scope_exit_75_without_update_ref(self, repo, monkeypatch, capsys):
        before = _head(repo)
        with patch.object(git_ops, "_run_git_with_lock_retry", _sneak_stage_c(repo)):
            rc = _cli(monkeypatch, "add-child", _PARENT, _CHILD)
        assert rc == 75, capsys.readouterr()
        assert _head(repo) == before
