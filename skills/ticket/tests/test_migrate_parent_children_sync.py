"""migrate 父子雙向欄位同步（0.4.1-W1-020.1）。

遷移使新 ID 的階層對應到不同父票時：舊父 children 移除該票、新父 children 加入新 ID；
新 ID 為根票時 parent_id 清為 null。異動的父票檔案與遷移同屬單一隔離提交。

E1 對照：同一批 fixture（真實 tmp git repo、真實票檔、真實 CLI 入口）下，
  - 父票改變（改號到另一父之下）：舊父/新父 children 皆異動
  - 父票不變（同層改號）：舊父 children 僅原地改名、新父不異動
兩側產物不同，才證明同步邏輯真的在分辨「父票是否改變」。
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

_VER = "0.0.0"
_OLD_PARENT = "0.0.0-W0-001"
_NEW_PARENT = "0.0.0-W0-002"
_CHILD = "0.0.0-W0-001.1"
_SIBLING = "0.0.0-W0-001.2"
_UNDER_NEW = "0.0.0-W0-002.1"
_AS_ROOT = "0.0.0-W0-009"
_SAME_LEVEL = "0.0.0-W0-001.5"
_ORPHAN_TARGET = "0.0.0-W0-077.1"

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

_CHILD_EXTRA = (
    f"parent_id: {_OLD_PARENT}\nchain:\n  root: {_OLD_PARENT}\n  parent: {_OLD_PARENT}\n"
    "  depth: 1\n  sequence: [1, 1]\n"
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout


def _seed(tid: str, children: str = "[]", extra: str = "") -> None:
    path = get_ticket_path(_VER, tid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_FM.format(tid=tid, children=children, extra=extra), encoding="utf-8")


def _fm(tid: str) -> dict:
    path = get_ticket_path(_VER, tid)
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
    _seed(_OLD_PARENT, children=f"[{_CHILD}, {_SIBLING}]")
    _seed(_NEW_PARENT, children="[]")
    _seed(_CHILD, extra=_CHILD_EXTRA)
    _seed(_SIBLING, extra=_CHILD_EXTRA.replace("[1, 1]", "[1, 2]"))
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


def _head_files(repo: Path) -> dict:
    out = _git(repo, "show", "--no-renames", "--name-status", "--format=", "HEAD")
    pairs = (line.split("\t") for line in out.strip().splitlines())
    return {Path(path).name: code for code, path in pairs}


class TestParentChangedToOtherParent:
    def test_old_parent_drops_and_new_parent_gains(self, repo, monkeypatch):
        assert _run(monkeypatch, _CHILD, _UNDER_NEW) == 0
        assert _fm(_OLD_PARENT)["children"] == [_SIBLING]
        assert _fm(_NEW_PARENT)["children"] == [_UNDER_NEW]
        migrated = _fm(_UNDER_NEW)
        assert migrated["parent_id"] == _NEW_PARENT
        assert migrated["chain"]["parent"] == _NEW_PARENT

    def test_dict_form_children_handled(self, repo, monkeypatch):
        path = get_ticket_path(_VER, _OLD_PARENT)
        text = path.read_text(encoding="utf-8").replace(
            f"children: [{_CHILD}, {_SIBLING}]",
            f"children:\n- id: {_CHILD}\n  title: c\n- {_SIBLING}")
        path.write_text(text, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "dict children")
        assert _run(monkeypatch, _CHILD, _UNDER_NEW) == 0
        assert _fm(_OLD_PARENT)["children"] == [_SIBLING]
        assert _fm(_NEW_PARENT)["children"] == [_UNDER_NEW]

    def test_new_parent_already_listing_id_not_duplicated(self, repo, monkeypatch):
        path = get_ticket_path(_VER, _NEW_PARENT)
        path.write_text(path.read_text(encoding="utf-8").replace(
            "children: []", f"children: [{_UNDER_NEW}]"), encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "pre-listed")
        assert _run(monkeypatch, _CHILD, _UNDER_NEW) == 0
        assert _fm(_NEW_PARENT)["children"] == [_UNDER_NEW]


class TestNewIdIsRoot:
    def test_parent_id_cleared_and_old_parent_drops(self, repo, monkeypatch):
        assert _run(monkeypatch, _CHILD, _AS_ROOT) == 0
        migrated = _fm(_AS_ROOT)
        assert migrated["parent_id"] is None
        assert migrated["chain"]["parent"] is None
        assert _fm(_OLD_PARENT)["children"] == [_SIBLING]


class TestSameLevelRenumberNoRegression:
    def test_same_parent_renames_in_place(self, repo, monkeypatch):
        assert _run(monkeypatch, _CHILD, _SAME_LEVEL) == 0
        assert _fm(_OLD_PARENT)["children"] == [_SAME_LEVEL, _SIBLING]
        assert _fm(_NEW_PARENT)["children"] == []
        assert _fm(_SAME_LEVEL)["parent_id"] == _OLD_PARENT


class TestMissingNewParent:
    def test_warning_only_and_migration_completes(self, repo, monkeypatch, capsys):
        rc = _run(monkeypatch, _CHILD, _ORPHAN_TARGET)
        captured = capsys.readouterr()
        assert rc == 0, captured
        assert "[WARNING]" in captured.out + captured.err
        assert "0.0.0-W0-077" in captured.out + captured.err
        assert get_ticket_path(_VER, _ORPHAN_TARGET).exists()
        assert _fm(_OLD_PARENT)["children"] == [_SIBLING]


class TestDryRun:
    def test_dry_run_writes_nothing(self, repo, monkeypatch):
        before_head = _git(repo, "rev-parse", "HEAD")
        assert _run(monkeypatch, _CHILD, _UNDER_NEW, "--dry-run") == 0
        assert _git(repo, "status", "--porcelain") == ""
        assert _git(repo, "rev-parse", "HEAD") == before_head
        assert _fm(_OLD_PARENT)["children"] == [_CHILD, _SIBLING]
        assert _fm(_NEW_PARENT)["children"] == []


class TestSingleCommitContent:
    def test_parent_files_in_same_commit(self, repo, monkeypatch):
        before = int(_git(repo, "rev-list", "--count", "HEAD").strip())
        assert _run(monkeypatch, _CHILD, _UNDER_NEW) == 0
        assert int(_git(repo, "rev-list", "--count", "HEAD").strip()) == before + 1
        assert _git(repo, "status", "--porcelain") == ""
        files = _head_files(repo)
        assert files[f"{_CHILD}.md"] == "D"
        assert files[f"{_UNDER_NEW}.md"] == "A"
        assert files[f"{_OLD_PARENT}.md"] == "M"
        assert files[f"{_NEW_PARENT}.md"] == "M"
        old_in_commit = _git(repo, "show", f"HEAD:{_rel(repo, _OLD_PARENT)}")
        assert _CHILD not in parse_frontmatter(old_in_commit)[0]["children"]
        new_in_commit = _git(repo, "show", f"HEAD:{_rel(repo, _NEW_PARENT)}")
        assert parse_frontmatter(new_in_commit)[0]["children"] == [_UNDER_NEW]


def _rel(repo: Path, tid: str) -> str:
    return str(get_ticket_path(_VER, tid).relative_to(repo))


_PARENTLESS = "0.0.0-W0-050"
_FIRST = "0.0.0-W0-002.9"


class TestNewParentAlreadyListsNewId:
    """舊父 None（無 parent_id）、新父由新 ID 推導；新父已列 new_id 時保留原項（0.4.1-W1-037）。"""

    def _prepare(self, repo: Path, new_parent_children: str) -> None:
        _seed(_PARENTLESS)
        path = get_ticket_path(_VER, _NEW_PARENT)
        path.write_text(path.read_text(encoding="utf-8").replace(
            "children: []", f"children: {new_parent_children}"), encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "prepare new parent children")

    def test_listed_as_dict_keeps_form_and_position(self, repo, monkeypatch):
        self._prepare(repo, f"[{_FIRST}, {{id: {_PARENTLESS}, type: IMP}}, {_SIBLING}]")
        assert _run(monkeypatch, _PARENTLESS, _UNDER_NEW) == 0
        assert _fm(_NEW_PARENT)["children"] == [
            _FIRST, {"id": _UNDER_NEW, "type": "IMP"}, _SIBLING]

    def test_listed_as_string_keeps_position(self, repo, monkeypatch):
        self._prepare(repo, f"[{_FIRST}, {_PARENTLESS}, {_SIBLING}]")
        assert _run(monkeypatch, _PARENTLESS, _UNDER_NEW) == 0
        assert _fm(_NEW_PARENT)["children"] == [_FIRST, _UNDER_NEW, _SIBLING]

    def test_not_listed_appends_string_at_tail(self, repo, monkeypatch):
        self._prepare(repo, f"[{_FIRST}, {_SIBLING}]")
        assert _run(monkeypatch, _PARENTLESS, _UNDER_NEW) == 0
        assert _fm(_NEW_PARENT)["children"] == [_FIRST, _SIBLING, _UNDER_NEW]

    def test_e1_listed_and_unlisted_products_differ(self, repo, monkeypatch):
        self._prepare(repo, f"[{_FIRST}, {_PARENTLESS}, {_SIBLING}]")
        assert _run(monkeypatch, _PARENTLESS, _UNDER_NEW) == 0
        listed = _fm(_NEW_PARENT)["children"]
        _git(repo, "reset", "-q", "--hard", "HEAD~1")
        path = get_ticket_path(_VER, _NEW_PARENT)
        path.write_text(path.read_text(encoding="utf-8").replace(
            f"[{_FIRST}, {_PARENTLESS}, {_SIBLING}]", f"[{_FIRST}, {_SIBLING}]"),
            encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "unlisted")
        assert _run(monkeypatch, _PARENTLESS, _UNDER_NEW) == 0
        unlisted = _fm(_NEW_PARENT)["children"]
        assert listed != unlisted


class TestE1ParentChangedVsUnchanged:
    def test_products_differ_between_paths(self, repo, monkeypatch):
        assert _run(monkeypatch, _CHILD, _UNDER_NEW) == 0
        changed = (_fm(_OLD_PARENT)["children"], _fm(_NEW_PARENT)["children"])
        changed_files = set(_head_files(repo))

        _git(repo, "reset", "-q", "--hard", "HEAD~1")
        assert _run(monkeypatch, _CHILD, _SAME_LEVEL) == 0
        unchanged = (_fm(_OLD_PARENT)["children"], _fm(_NEW_PARENT)["children"])
        unchanged_files = set(_head_files(repo))

        assert changed != unchanged
        assert f"{_NEW_PARENT}.md" in changed_files
        assert f"{_NEW_PARENT}.md" not in unchanged_files
