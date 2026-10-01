"""migrate 自動提交與結構欄位改寫（0.4.1-W1-010.2）。

E1 對照：同一 fixture（真實 git repo、真實票檔、真實 CLI 入口）下，
  - 無鎖：改名、引用改寫、topic 追加以「單一 commit」入庫（rc 0、工作區乾淨）
  - 殘留 ref 鎖：提交失敗，rc 75，stderr 的 [WARNING] 列出全部路徑，檔案仍在工作區
殘鎖是兩側唯一差異；只斷言失敗側時，提交退化為空操作仍會綠。
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
from ticket_system.lib.topic_assignments import list_assignments

_VER = "0.0.0"
_SRC = "0.0.0-W0-001"
_NEW = "0.0.0-W0-009"
_CHILD = "0.0.0-W0-001.1"
_REF = "0.0.0-W0-002"
_OTHER = "0.0.0-W0-003"
_OTHER_NEW = "0.0.0-W0-010"
_TOPIC = "框架修復"
_ASSIGN = "docs/work-logs/topic-assignments.txt"

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
blockedBy: {blocked}
relatedTo: []
spawned_tickets: []
source_ticket: null
acceptance:
- '[ ] a1'
assigned: false
tdd_stage: []
{extra}---

# Execution Log

## Solution

{body}
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout


def _seed(tid: str, children: str = "[]", blocked: str = "[]", extra: str = "",
          body: str = "history") -> Path:
    path = get_ticket_path(_VER, tid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _FM.format(tid=tid, children=children, blocked=blocked, extra=extra, body=body),
        encoding="utf-8",
    )
    return path


def _fm(path: Path) -> dict:
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
        yaml.dump({"versions": [{"version": _VER, "status": "active"}]}), encoding="utf-8"
    )
    _seed(_SRC, children=f"[{_CHILD}]",
          body=f"Context Bundle 提到 {_SRC}，歷史事實")
    _seed(_CHILD, extra=(
        f"parent_id: {_SRC}\nchain:\n  root: {_SRC}\n  parent: {_SRC}\n"
        "  depth: 1\n  sequence: [1, 1]\n"))
    _seed(_REF, blocked=f"[{_SRC}]", extra=(
        f"discovered_during: {_SRC}\nclosed_by: {_SRC}\n"), body=f"Solution 寫過 {_SRC}")
    _seed(_OTHER)
    assign = tmp_path / _ASSIGN
    assign.parent.mkdir(parents=True, exist_ok=True)
    assign.write_text(f"{_SRC}\t{_TOPIC}\n{_OTHER}\t{_TOPIC}\n", encoding="utf-8")
    (tmp_path / "docs" / "work-logs" / "topics-registry.txt").write_text(
        f"{_TOPIC}\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".claude/hook-logs/\n.claude/migration-backups/\n",
                                         encoding="utf-8")
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


def _dirty(repo: Path) -> str:
    return _git(repo, "status", "--porcelain")


def _commit_count(repo: Path) -> int:
    return int(_git(repo, "rev-list", "--count", "HEAD").strip())


def _plant_lock(repo: Path) -> Path:
    lock = repo / ".git" / "refs" / "heads" / "main.lock"
    lock.write_text("residue\n")
    return lock


def _head_name_status(repo: Path) -> dict:
    out = _git(repo, "diff-tree", "--no-renames", "--name-status", "-r", "--no-commit-id", "HEAD")
    pairs = (line.split("\t") for line in out.strip().splitlines())
    return {Path(path).name: code for code, path in pairs}


class TestSingleMigrateCommit:
    def test_one_commit_covers_rename_referrers_and_topic(self, repo, monkeypatch, capsys):
        before = _commit_count(repo)
        rc = _run(monkeypatch, _SRC, _NEW)
        assert rc == 0, capsys.readouterr()
        assert _dirty(repo) == ""
        assert _commit_count(repo) == before + 1
        by_name = _head_name_status(repo)
        assert by_name[f"{_SRC}.md"] == "D"
        assert by_name[f"{_NEW}.md"] == "A"
        assert by_name[f"{_REF}.md"] == "M"
        assert by_name[f"{_CHILD}.md"] == "M"
        assert by_name["topic-assignments.txt"] == "M"
        added = [ln for ln in _git(repo, "show", "HEAD", "--", _ASSIGN).splitlines()
                 if ln.startswith("+") and not ln.startswith("+++")]
        assert added == [f"+{_NEW}\t{_TOPIC}"]

    def test_locked_ref_exits_75_with_all_paths(self, repo, monkeypatch, capsys):
        _plant_lock(repo)
        before = _commit_count(repo)
        rc = _run(monkeypatch, _SRC, _NEW)
        err = capsys.readouterr().err
        assert rc == 75
        assert "[WARNING]" in err
        for tid in (_NEW, _SRC, _REF, _CHILD):
            assert f"{tid}.md" in err
        assert _commit_count(repo) == before
        assert get_ticket_path(_VER, _NEW).exists()
        assert _dirty(repo) != ""


class TestStructuralRewrite:
    def test_discovered_during_closed_by_and_chain_rewritten(self, repo, monkeypatch):
        assert _run(monkeypatch, _SRC, _NEW) == 0
        ref = _fm(get_ticket_path(_VER, _REF))
        assert ref["blockedBy"] == [_NEW]
        assert ref["discovered_during"] == _NEW
        assert ref["closed_by"] == _NEW
        child = _fm(get_ticket_path(_VER, _CHILD))
        assert child["chain"]["root"] == _NEW
        assert child["chain"]["parent"] == _NEW
        assert child["parent_id"] == _NEW

    def test_body_keeps_old_id_and_previous_ids_recorded(self, repo, monkeypatch):
        assert _run(monkeypatch, _SRC, _NEW) == 0
        new_text = get_ticket_path(_VER, _NEW).read_text(encoding="utf-8")
        assert f"Context Bundle 提到 {_SRC}" in new_text
        assert f"Solution 寫過 {_SRC}" in get_ticket_path(_VER, _REF).read_text(encoding="utf-8")
        assert _fm(get_ticket_path(_VER, _NEW))["previous_ids"] == [_SRC]


class TestTopicInheritance:
    def test_new_id_gets_topic_and_old_line_kept(self, repo, monkeypatch):
        assert _run(monkeypatch, _SRC, _NEW) == 0
        assert list_assignments()[_NEW] == _TOPIC
        lines = (repo / _ASSIGN).read_text(encoding="utf-8").splitlines()
        assert f"{_SRC}\t{_TOPIC}" in lines


class TestBatchConfig:
    def test_only_successes_in_single_commit(self, repo, monkeypatch, capsys):
        cfg = repo / "cfg.yaml"
        cfg.write_text(yaml.dump({"migrations": [
            {"from": _SRC, "to": _NEW},
            {"from": "0.0.0-W0-777", "to": "0.0.0-W0-778"},
            {"from": _OTHER, "to": _OTHER_NEW},
        ]}), encoding="utf-8")
        _git(repo, "add", "cfg.yaml")
        _git(repo, "commit", "-q", "-m", "cfg")
        before = _commit_count(repo)
        rc = _run(monkeypatch, "--config", str(cfg))
        assert rc == 0, capsys.readouterr()
        assert _dirty(repo) == ""
        assert _commit_count(repo) == before + 1
        names = set(_head_name_status(repo))
        assert {f"{_NEW}.md", f"{_OTHER_NEW}.md", f"{_SRC}.md", f"{_OTHER}.md"} <= names
        assert not any("778" in n for n in names)
        assert list_assignments()[_OTHER_NEW] == _TOPIC
