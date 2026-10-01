"""migrate 有子孫的票連帶遷移整個子樹（preflight 失敗整體拒絕）。

真實 tmp git repo、真實票檔、真實 CLI 入口。

E1 對照：同一批 fixture 下，遷移「有子孫的票」與「無子孫的票」兩條路徑產物不同
（前者子孫連帶改號、後者子票不受影響），才證明子樹邏輯真的在分辨有無子孫。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ticket_system.commands import migrate as migrate_mod
from ticket_system.lib import git_ops, git_utils
from ticket_system.lib.parser import parse_frontmatter
from ticket_system.lib.paths import get_ticket_path

_VER = "0.0.0"
_ASSIGN = "docs/work-logs/topic-assignments.txt"
_TOPIC = "topic-x"

_ROOT = "0.0.0-W0-010"
_C1 = "0.0.0-W0-010.1"
_C2 = "0.0.0-W0-010.2"
_G1 = "0.0.0-W0-010.1.1"
_NEW_ROOT = "0.0.0-W0-020"
_NEW_C1 = "0.0.0-W0-020.1"
_NEW_C2 = "0.0.0-W0-020.2"
_NEW_G1 = "0.0.0-W0-020.1.1"
_EXT = "0.0.0-W0-050"
_LEAF = "0.0.0-W0-060"
_LEAF_CHILDLESS = "0.0.0-W0-061"
_LEAF_NEW = "0.0.0-W0-062"

_FM = """---
id: {tid}
title: t
type: IMP
status: {status}
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
relatedTo: {related}
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


def _seed(tid, children="[]", blocked="[]", related="[]", status="pending", extra=""):
    path = get_ticket_path(_VER, tid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_FM.format(tid=tid, children=children, blocked=blocked,
                               related=related, status=status, extra=extra),
                    encoding="utf-8")


def _chain(tid, root, parent, depth, seq):
    return (f"parent_id: {parent}\nchain:\n  root: {root}\n  parent: {parent}\n"
            f"  depth: {depth}\n  sequence: {seq}\n")


def _fm(tid: str) -> dict:
    return parse_frontmatter(get_ticket_path(_VER, tid).read_text(encoding="utf-8"))[0]


def _exists(tid: str) -> bool:
    return get_ticket_path(_VER, tid).exists()


def _seed_tree() -> None:
    _seed(_ROOT, children=f"[{_C1}, {_C2}]")
    _seed(_C1, children=f"[{_G1}]", status="completed",
          extra=_chain(_C1, _ROOT, _ROOT, 1, "[10, 1]"))
    _seed(_C2, extra=_chain(_C2, _ROOT, _ROOT, 1, "[10, 2]"))
    _seed(_G1, status="completed", blocked=f"[{_C2}]",
          extra=_chain(_G1, _ROOT, _C1, 2, "[10, 1, 1]"))
    _seed(_EXT, blocked=f"[{_ROOT}, {_C1}]", related=f"[{_G1}]")
    _seed(_LEAF)
    _seed(_LEAF_CHILDLESS, children=f"[{_LEAF}]")  # 無前綴子孫，僅是無關引用


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
    _seed_tree()
    assign = tmp_path / _ASSIGN
    assign.parent.mkdir(parents=True, exist_ok=True)
    assign.write_text("".join(f"{t}\t{_TOPIC}\n" for t in (_ROOT, _C1, _C2, _G1)),
                      encoding="utf-8")
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


def _commits(repo: Path) -> int:
    return int(_git(repo, "rev-list", "--count", "HEAD").strip())


def _assert_untouched(repo: Path, head: str) -> None:
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "rev-parse", "HEAD") == head
    for tid in (_ROOT, _C1, _C2, _G1):
        assert _exists(tid)


class TestSubtreeCascade:
    def test_all_descendants_renamed_with_fields_rewritten(self, repo, monkeypatch):
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) == 0
        for old in (_ROOT, _C1, _C2, _G1):
            assert not _exists(old)
        root, c1, c2, g1 = (_fm(t) for t in (_NEW_ROOT, _NEW_C1, _NEW_C2, _NEW_G1))
        assert root["children"] == [_NEW_C1, _NEW_C2]
        assert c1["parent_id"] == _NEW_ROOT and c2["parent_id"] == _NEW_ROOT
        assert g1["parent_id"] == _NEW_C1
        assert c1["children"] == [_NEW_G1]
        assert g1["blockedBy"] == [_NEW_C2]
        assert g1["chain"]["root"] == _NEW_ROOT
        assert g1["chain"]["parent"] == _NEW_C1
        assert g1["chain"]["depth"] == 2
        assert g1["id"] == _NEW_G1 and g1["wave"] == 0

    def test_previous_ids_on_every_member_including_completed(self, repo, monkeypatch):
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) == 0
        expected = {_NEW_ROOT: _ROOT, _NEW_C1: _C1, _NEW_C2: _C2, _NEW_G1: _G1}
        for new, old in expected.items():
            assert _fm(new)["previous_ids"] == [old], new
        assert _fm(_NEW_C1)["status"] == "completed"
        assert _fm(_NEW_G1)["status"] == "completed"

    def test_topic_lines_appended_old_lines_kept(self, repo, monkeypatch):
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) == 0
        lines = (repo / _ASSIGN).read_text(encoding="utf-8").splitlines()
        for old, new in ((_ROOT, _NEW_ROOT), (_C1, _NEW_C1), (_C2, _NEW_C2), (_G1, _NEW_G1)):
            assert f"{old}\t{_TOPIC}" in lines
            assert f"{new}\t{_TOPIC}" in lines

    def test_external_references_rewritten(self, repo, monkeypatch):
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) == 0
        ext = _fm(_EXT)
        assert ext["blockedBy"] == [_NEW_ROOT, _NEW_C1]
        assert ext["relatedTo"] == [_NEW_G1]

    def test_single_isolated_commit_covers_whole_subtree(self, repo, monkeypatch):
        before = _commits(repo)
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) == 0
        assert _commits(repo) == before + 1
        assert _git(repo, "status", "--porcelain") == ""
        out = _git(repo, "show", "--no-renames", "--name-status", "--format=", "HEAD")
        status = {Path(p).name: c for c, p in (l.split("\t") for l in out.strip().splitlines())}
        for old in (_ROOT, _C1, _C2, _G1):
            assert status[f"{old}.md"] == "D"
        for new in (_NEW_ROOT, _NEW_C1, _NEW_C2, _NEW_G1):
            assert status[f"{new}.md"] == "A"
        assert status[f"{_EXT}.md"] == "M"
        assert status["topic-assignments.txt"] == "M"


class TestOverlappingMapping:
    """010 遷到 010.1 之下的位置：舊 010.1 同時映射到 010.1.1，新舊 ID 重疊。"""

    def test_references_remapped_in_single_pass(self, repo, monkeypatch):
        mapping = {_ROOT: _C1, _C1: _G1}
        ticket = {"blockedBy": [_ROOT, _C1], "children": [_C1, {"id": _ROOT}],
                  "parent_id": _C1, "chain": {"root": _ROOT, "parent": _C1},
                  "closed_by": [_ROOT], "discovered_during": _C1}
        assert migrate_mod._remap_ticket_refs(ticket, mapping) is True
        assert ticket["blockedBy"] == [_C1, _G1]
        assert ticket["children"] == [_G1, {"id": _C1}]
        assert ticket["parent_id"] == _G1
        assert ticket["chain"] == {"root": _C1, "parent": _G1}
        assert ticket["closed_by"] == [_C1]
        assert ticket["discovered_during"] == _G1

    def test_chained_mapping_does_not_cascade_twice(self):
        # 010.1->010.2，而 010.2 本身也在遷移（->010.3）：逐對替換會把 010.1 連跳成 010.3
        mapping = {_C1: _C2, _C2: "0.0.0-W0-010.3"}
        ticket = {"blockedBy": [_C1, _C2], "relatedTo": [_C2]}
        migrate_mod._remap_ticket_refs(ticket, mapping)
        assert ticket["blockedBy"] == [_C2, "0.0.0-W0-010.3"]
        assert ticket["relatedTo"] == ["0.0.0-W0-010.3"]

    def test_end_to_end_root_moves_under_own_first_child_slot(self, repo, monkeypatch):
        # 010 -> 010.1：舊 010.1 變 010.1.1、舊 010.1.1 變 010.1.1.1（深度 4 超限）。
        # 改用 010.2 子樹尚無孫的情形：C2 只有自身，先把孫移除以構造合法重疊。
        get_ticket_path(_VER, _G1).unlink()
        get_ticket_path(_VER, _C1).write_text(
            get_ticket_path(_VER, _C1).read_text(encoding="utf-8").replace(
                f"children: [{_G1}]", "children: []"), encoding="utf-8")
        _seed(_EXT, blocked=f"[{_ROOT}, {_C1}]")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "overlap seed")
        assert _run(monkeypatch, _ROOT, _C1) == 0
        # 舊 010.1 -> 010.1.1，舊 010 -> 010.1，舊 010.2 -> 010.1.2
        assert _fm(_C1)["previous_ids"] == [_ROOT]
        assert _fm(_G1)["previous_ids"] == [_C1]
        assert _fm("0.0.0-W0-010.1.2")["previous_ids"] == [_C2]
        assert _fm(_EXT)["blockedBy"] == [_C1, _G1]  # 單趟：010->010.1、010.1->010.1.1
        assert _fm(_C1)["children"] == [_G1, "0.0.0-W0-010.1.2"]


class TestPreflightRejectsWholeSubtree:
    def test_collision_rejects_and_names_the_colliding_id(self, repo, monkeypatch, capsys):
        _seed(_NEW_C2)  # 020.2 已被佔用
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "occupy")
        head = _git(repo, "rev-parse", "HEAD")
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) != 0
        out = capsys.readouterr()
        assert _NEW_C2 in out.out + out.err
        assert not _exists(_NEW_ROOT) and not _exists(_NEW_C1)
        _assert_untouched(repo, head)

    def test_depth_overflow_lists_ticket_id_and_depth(self, repo, monkeypatch, capsys):
        # 010.1（含孫 010.1.1）遷到 030.1.1：根深度 3，孫會成為 030.1.1.1 深度 4 > 3
        _seed("0.0.0-W0-030")
        _seed("0.0.0-W0-030.1", extra=_chain("", "0.0.0-W0-030", "0.0.0-W0-030", 1, "[30, 1]"))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "new parent")
        head = _git(repo, "rev-parse", "HEAD")
        assert _run(monkeypatch, _C1, "0.0.0-W0-030.1.1") != 0
        out = capsys.readouterr()
        text = out.out + out.err
        assert "0.0.0-W0-030.1.1.1" in text
        assert "4" in text
        assert not _exists("0.0.0-W0-030.1.1")
        _assert_untouched(repo, head)

    def test_unregistered_target_version_rejects_without_writes(self, repo, monkeypatch):
        head = _git(repo, "rev-parse", "HEAD")
        assert _run(monkeypatch, _ROOT, "9.9.9-W0-001") != 0
        _assert_untouched(repo, head)
        assert not (repo / ".claude" / "migration-backups").exists()

    def test_any_failure_blocks_even_when_other_items_pass(self, repo, monkeypatch):
        _seed(_NEW_G1)  # 只有孫輩碰撞，根與其餘子孫本身可遷
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "occupy grandchild")
        head = _git(repo, "rev-parse", "HEAD")
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) != 0
        assert not _exists(_NEW_ROOT)
        _assert_untouched(repo, head)


class TestDryRunAndMidFailure:
    def test_dry_run_prints_full_mapping_and_writes_nothing(self, repo, monkeypatch, capsys):
        head = _git(repo, "rev-parse", "HEAD")
        assert _run(monkeypatch, _ROOT, _NEW_ROOT, "--dry-run") == 0
        text = capsys.readouterr().out
        for old, new in ((_ROOT, _NEW_ROOT), (_C1, _NEW_C1), (_C2, _NEW_C2), (_G1, _NEW_G1)):
            assert old in text and new in text
        _assert_untouched(repo, head)
        assert not _exists(_NEW_ROOT)

    def test_mid_write_failure_reports_written_set(self, repo, monkeypatch, capsys):
        real_save = migrate_mod.save_ticket
        calls = {"n": 0}

        def flaky(ticket, path):
            calls["n"] += 1
            if calls["n"] == 3:
                raise OSError("disk full")
            return real_save(ticket, path)

        monkeypatch.setattr(migrate_mod, "save_ticket", flaky)
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) != 0
        out = capsys.readouterr()
        text = out.out + out.err
        assert "disk full" in text
        written = [t for t in (_NEW_ROOT, _NEW_C1, _NEW_C2, _NEW_G1) if _exists(t)]
        assert len(written) == 2
        for tid in written:
            assert f"{tid}.md" in text


class TestE1ContrastWithAndWithoutDescendants:
    def test_descendant_path_vs_childless_path_differ(self, repo, monkeypatch):
        # 無子孫：只改自身，既有行為不回歸
        assert _run(monkeypatch, _LEAF, _LEAF_NEW) == 0
        assert _exists(_LEAF_NEW) and not _exists(_LEAF)
        assert _fm(_LEAF_NEW)["previous_ids"] == [_LEAF]
        assert _fm(_LEAF_CHILDLESS)["children"] == [_LEAF_NEW]
        assert _exists(_ROOT) and _exists(_G1)  # 他人子樹不受影響
        leaf_files = {p.name for p in get_ticket_path(_VER, _LEAF).parent.glob("*.md")}
        # 有子孫：整個子樹改號
        assert _run(monkeypatch, _ROOT, _NEW_ROOT) == 0
        tree_files = {p.name for p in get_ticket_path(_VER, _LEAF).parent.glob("*.md")}
        assert f"{_NEW_G1}.md" in tree_files and f"{_NEW_G1}.md" not in leaf_files
        assert f"{_G1}.md" in leaf_files and f"{_G1}.md" not in tree_files
