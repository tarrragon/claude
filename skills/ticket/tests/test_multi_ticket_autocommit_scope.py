"""一次寫多張票的命令 auto-commit 範圍與失敗可見性（0.4.0-W1-074）。

E1 對照：同一 fixture（真實 git repo、真實票檔、真實 CLI 入口）下，
  - 無鎖：所有被寫的票檔以「單一 commit」提交（rc 0、無 WARNING、工作區乾淨）
  - 殘留 ref 鎖：提交失敗，stderr 出現 [WARNING]，rc 75，票檔仍留在工作區
殘鎖是兩側唯一差異；只斷言失敗側時，reporting 退化為空操作仍會綠。

另含 ``commit_ticket_mds_reporting`` 多路徑單元測試。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ticket_system.commands import generate as generate_cmd
from ticket_system.lib import git_ops, git_utils
from ticket_system.lib.paths import get_ticket_path
from ticket_system.lib.plan_parser import PlanParseResult, PlanTask

_VER = "0.0.0"
_TID = "0.0.0-W0-001"
_OTHER = "0.0.0-W0-002"
_OLD_PARENT = "0.0.0-W0-003"
_PEND = "0.0.0-W0-005"
_DONE1 = "0.0.0-W0-006"
_DONE2 = "0.0.0-W0-007"
_CHILD = "0.0.0-W0-008"

_UNCHECKED = "- '[ ] a1'\n- '[ ] a2'"
_CHECKED = "- '[x] a1'\n- '[x] a2'"

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
blockedBy: []
relatedTo: []
spawned_tickets: []
source_ticket: null
acceptance:
{acc}
assigned: true
tdd_stage: []
{extra}---

# Execution Log

## Problem Analysis

pa

## Solution

sol

## Test Results

tr

## Spawn Requests

"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout


def _seed(tid: str, status: str, children: str = "[]", acc: str = _UNCHECKED,
          extra: str = "") -> None:
    path = get_ticket_path(_VER, tid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _FM.format(tid=tid, status=status, children=children, acc=acc, extra=extra),
        encoding="utf-8",
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("TICKET_SYSTEM_TEST_ISOLATION", "1")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _seed(_TID, "in_progress")
    _seed(_OTHER, "pending")
    _seed(_OLD_PARENT, "in_progress", children=f"[{_CHILD}]")
    _seed(_PEND, "pending")
    _seed(_DONE1, "in_progress", acc=_CHECKED)
    _seed(_DONE2, "in_progress", acc=_CHECKED)
    _seed(_CHILD, "pending", extra=f"parent_id: {_OLD_PARENT}\n")
    # 比照真實 consumer repo：hook-logs 已被 gitignore。identity_guard 會呼叫
    # mark_hook_entry 寫入 .claude/hook-logs/_liveness/<session>.jsonl；缺這行時
    # 「工作區乾淨」斷言依是否在 Claude session 內執行而定。
    (tmp_path / ".gitignore").write_text(".claude/hook-logs/\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 0.0)
    monkeypatch.setattr(git_ops.time, "sleep", lambda _s: None)
    return tmp_path


def _run(monkeypatch, *argv: str, track: bool = True) -> int:
    from ticket_system.scripts import ticket as cli

    head = ["ticket", "track"] if track else ["ticket"]
    monkeypatch.setattr(sys, "argv", [*head, *argv, "--version", _VER])
    try:
        return cli.main() or 0
    except SystemExit as exc:
        return int(exc.code or 0)


def _plant_lock(repo: Path) -> Path:
    lock = repo / ".git" / "refs" / "heads" / "main.lock"
    lock.write_text("residue\n")
    return lock


def _dirty(repo: Path) -> str:
    return _git(repo, "status", "--porcelain")


def _commit_count(repo: Path) -> int:
    return int(_git(repo, "rev-list", "--count", "HEAD").strip())


def _head_files(repo: Path) -> set:
    out = _git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
    return {Path(line).name for line in out.splitlines() if line.strip()}


def _md(tid: str) -> str:
    return f"{tid}.md"


# 命令 -> (argv, track 子命令?, 預期同一 commit 內的票 id 集合)
_COMMANDS = {
    "add-child": (["add-child", _TID, _OTHER], True, {_TID, _OTHER}),
    "set-parent-3-paths": (["set-parent", _CHILD, _TID], True, {_OLD_PARENT, _TID, _CHILD}),
    "batch-claim": (["batch-claim", f"{_OTHER},{_PEND}"], True, {_OTHER, _PEND}),
    "batch-complete": (["batch-complete", f"{_DONE1},{_DONE2}"], True, {_DONE1, _DONE2}),
    "dispatch": (["dispatch", _TID, "--note", "n"], True, {_TID}),
    "claim": (["claim", _OTHER], True, {_OTHER}),
    "release": (["release", _TID], True, {_TID}),
    "close": (
        ["close", _OTHER, "--resolved-by", "none", "--reason", "cancelled_by_user",
         "--reason-note", "not needed"],
        True, {_OTHER},
    ),
    "batch-create": (
        ["batch-create", "--template", "impl-parsley", "--targets", "aa,bb", "--wave", "1"],
        False, {"0.0.0-W1-001", "0.0.0-W1-002"},
    ),
    "generate": (["generate", "PLAN.md", "--wave", "1"], False, None),
}


@pytest.fixture
def stub_plan(repo, monkeypatch):
    """generate 的 plan 解析換成固定兩個任務，聚焦驗證提交範圍。"""
    (repo / "PLAN.md").write_text("plan\n", encoding="utf-8")
    _git(repo, "add", "PLAN.md")
    _git(repo, "commit", "-q", "-m", "plan")
    tasks = [
        PlanTask(title=f"task {i}", description="d", action="實作", target=f"T{i}",
                 files=["lib/a.dart"], layer="Application", task_type="IMP",
                 complexity=3, order=i)
        for i in (1, 2)
    ]
    result = PlanParseResult(plan_title="p", plan_description="d", tasks=tasks,
                             total_tasks=2, success=True)
    monkeypatch.setattr(generate_cmd, "parse_plan", lambda _p: result)


def _invoke(name, repo, monkeypatch):
    argv, track, _ = _COMMANDS[name]
    if name == "generate":
        argv = ["generate", str(repo / "PLAN.md"), "--wave", "1"]
    return _run(monkeypatch, *argv, track=track)


@pytest.mark.parametrize("name", sorted(_COMMANDS))
def test_control_no_lock_single_commit_covers_all_written_tickets(
    name, repo, stub_plan, monkeypatch, capsys
):
    before = _commit_count(repo)
    rc = _invoke(name, repo, monkeypatch)
    cap = capsys.readouterr()
    assert rc == 0, cap.out + cap.err
    assert "[WARNING]" not in cap.err
    assert _dirty(repo) == "", "寫入後工作區不得留未提交的票檔"
    assert _commit_count(repo) == before + 1, "多張票應合為單一 commit"
    expected = _COMMANDS[name][2]
    if expected is not None:
        assert {_md(t) for t in expected} <= _head_files(repo)


@pytest.mark.parametrize("name", sorted(_COMMANDS))
def test_residual_lock_fails_visibly_with_75(name, repo, stub_plan, monkeypatch, capsys):
    _plant_lock(repo)
    rc = _invoke(name, repo, monkeypatch)
    cap = capsys.readouterr()
    assert rc == git_utils.EXIT_AUTO_COMMIT_FAILED, cap.out + cap.err
    assert "[WARNING]" in cap.err
    assert "exit code 75" in cap.err
    assert _dirty(repo) != "", "提交失敗時票檔應仍在工作區（寫入已發生）"


# --- commit_ticket_mds_reporting 單元測試 -------------------------------------


def _touch(repo: Path, tid: str) -> str:
    path = get_ticket_path(_VER, tid)
    path.write_text(path.read_text(encoding="utf-8") + "\nedit\n", encoding="utf-8")
    return str(path)


def test_mds_reporting_commits_all_paths_in_one_commit(repo):
    paths = [_touch(repo, _TID), _touch(repo, _OTHER), _touch(repo, _PEND)]
    before = _commit_count(repo)
    failed = git_utils.commit_ticket_mds_reporting("t", paths, _TID, "multi", operation="op")
    assert failed is False
    assert _commit_count(repo) == before + 1
    assert {_md(_TID), _md(_OTHER), _md(_PEND)} <= _head_files(repo)
    assert _dirty(repo) == ""


def test_mds_reporting_dedupes_and_ignores_empty(repo):
    p = _touch(repo, _TID)
    before = _commit_count(repo)
    assert git_utils.commit_ticket_mds_reporting("t", [p, p, ""], _TID, "s") is False
    assert _commit_count(repo) == before + 1
    assert git_utils.commit_ticket_mds_reporting("t", [], _TID, "s") is False
    assert _commit_count(repo) == before + 1


def test_mds_reporting_lock_returns_true_and_warning_lists_every_path(repo, capsys):
    paths = [_touch(repo, _TID), _touch(repo, _OTHER)]
    _plant_lock(repo)
    failed = git_utils.commit_ticket_mds_reporting("t", paths, _TID, "multi", operation="op")
    err = capsys.readouterr().err
    assert failed is True
    assert "[WARNING]" in err and "exit code 75" in err
    remedy = [ln for ln in err.splitlines() if ln.startswith("補救指令")][0]
    assert all(p in remedy for p in paths), "補救指令必須列出每一個未入庫的票檔"


def test_single_path_api_unchanged(repo):
    p = _touch(repo, _TID)
    assert git_utils.commit_ticket_md_reporting("t", p, _TID, "s") is False
    assert _dirty(repo) == ""


# --- worklog 進度行以行層級提交（batch-complete） -----------------------------

_WORKLOG_BASE = (
    "# w\n\n### 2026-01-01\n\n- x\n\n---\n\n## Footer\n\nfooter\n"
)


def _worklog_file(repo: Path) -> Path:
    return repo / "docs/work-logs/v0/v0.0/v0.0.0/v0.0.0-main.md"


def _reset_worklog(repo: Path, text: str) -> Path:
    path = _worklog_file(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(repo, "add", str(path))
    _git(repo, "commit", "-q", "-m", "worklog seed")
    return path


def _head_worklog(repo: Path) -> list:
    return _git(repo, "show", "HEAD:docs/work-logs/v0/v0.0/v0.0.0/v0.0.0-main.md").splitlines()


def _batch_complete(monkeypatch) -> int:
    return _run(monkeypatch, "batch-complete", f"{_DONE1},{_DONE2}")


def test_batch_complete_worklog_lines_in_same_commit_and_clean(repo, monkeypatch, capsys):
    _reset_worklog(repo, _WORKLOG_BASE)
    before = _commit_count(repo)
    rc = _batch_complete(monkeypatch)
    cap = capsys.readouterr()
    assert rc == 0, cap.out + cap.err
    assert _commit_count(repo) == before + 1
    assert "v0.0.0-main.md" in _head_files(repo)
    assert _dirty(repo) == "", "進度行應與票檔同一 commit，工作區不留 M"
    head = _head_worklog(repo)
    assert sum(1 for ln in head if f"{_DONE1} 完成" in ln or f"{_DONE2} 完成" in ln) == 2


def test_batch_complete_does_not_commit_others_worklog_edit(repo, monkeypatch, capsys):
    path = _reset_worklog(repo, _WORKLOG_BASE)
    path.write_text(
        _WORKLOG_BASE.replace("- x\n", "- x\n- other uncommitted\n"), encoding="utf-8"
    )
    rc = _batch_complete(monkeypatch)
    assert rc == 0, capsys.readouterr().err
    head = _head_worklog(repo)
    assert "- other uncommitted" not in head
    assert any(f"{_DONE1} 完成" in ln for ln in head)
    assert "- other uncommitted" in path.read_text(encoding="utf-8").splitlines()


def test_batch_complete_replays_into_date_section_when_others_edit_existing_line(
    repo, monkeypatch, capsys
):
    path = _reset_worklog(repo, _WORKLOG_BASE)
    path.write_text(_WORKLOG_BASE.replace("- x\n", "- x edited\n"), encoding="utf-8")
    rc = _batch_complete(monkeypatch)
    assert rc == 0, capsys.readouterr().err
    head = _head_worklog(repo)
    assert "- x edited" not in head
    idx_sep = head.index("---")
    idx_x = head.index("- x")
    progress = [i for i, ln in enumerate(head) if "完成" in ln]
    assert len(progress) == 2
    assert all(idx_x < i < idx_sep for i in progress), head
