"""寫入票面的 track 子命令 auto-commit 範圍與失敗可見性（0.4.0-W1-071）。

E1 對照：同一 fixture（真實 git repo、真實票檔、真實 CLI 入口）下，
  - 無鎖：靜默提交成功（rc 0、無 WARNING、工作區不留未提交的票檔）
  - 殘留 ref 鎖：提交失敗，stderr 出現 [WARNING]，rc 75
殘鎖是兩側唯一差異；只斷言失敗側時，reporting 退化為空操作仍會綠。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ticket_system.lib import git_ops, git_utils
from ticket_system.lib.paths import get_ticket_path

_VER = "0.0.0"
_TID = "0.0.0-W0-001"
_OTHER = "0.0.0-W0-002"
_HAS_SPAWNED = "0.0.0-W0-003"
_CLOSED = "0.0.0-W0-004"

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
children: []
blockedBy: []
relatedTo: []
spawned_tickets: {spawned}
source_ticket: null
acceptance:
- '[ ] a1'
- '[ ] a2'
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


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("TICKET_SYSTEM_TEST_ISOLATION", "1")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    seeds = (
        (_TID, "in_progress", "[]", ""),
        (_OTHER, "pending", "[]", ""),
        (_HAS_SPAWNED, "in_progress", f"[{_OTHER}]", ""),
        (_CLOSED, "closed", "[]",
         "closed_at: '2026-01-01T00:00:00'\\nclosed_by: someone\\nclose_reason: goal_achieved\\n"),
    )
    for tid, status, spawned, extra in seeds:
        path = get_ticket_path(_VER, tid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _FM.format(tid=tid, status=status, spawned=spawned, extra=extra.replace("\\n", "\n")),
            encoding="utf-8",
        )
    # 比照真實 consumer repo：hook-logs 已被 gitignore。identity_guard 會呼叫
    # mark_hook_entry 寫入 .claude/hook-logs/_liveness/<session>.jsonl；若測試行程
    # 帶有 Claude session 環境變數，該檔會出現在 fixture repo，使「工作區乾淨」
    # 斷言依執行環境而定（在 session 內跑紅、在 session 外跑綠）。
    (tmp_path / ".gitignore").write_text(".claude/hook-logs/\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 0.0)
    monkeypatch.setattr(git_ops.time, "sleep", lambda _s: None)
    return tmp_path


def _run(monkeypatch, *argv: str) -> int:
    from ticket_system.scripts import ticket as cli

    monkeypatch.setattr(sys, "argv", ["ticket", "track", *argv, "--version", _VER])
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


# 命令 -> (目標票, argv)；目標票以 {t} 佔位於 argv。
_COMMANDS = {
    "set-how": (_TID, ["set-how", "{t}", "--strategy", "new strategy"]),
    "set-what": (_TID, ["set-what", "{t}", "new what"]),
    "set-who": (_TID, ["set-who", "{t}", "someone-else"]),
    "set-why": (_TID, ["set-why", "{t}", "new why"]),
    "set-priority": (_TID, ["set-priority", "{t}", "P1"]),
    "set-where": (_TID, ["set-where", "{t}", "--files", "a/b.py"]),
    "set-scope-blocker": (_TID, ["set-scope-blocker", "{t}", "--reason", "blocked by x"]),
    "set-decision-tree": (_TID, ["set-decision-tree", "{t}", "--entry", "e"]),
    "add-acceptance": (_TID, ["add-acceptance", "{t}", "a3"]),
    "remove-acceptance": (_TID, ["remove-acceptance", "{t}", "1"]),
    "set-acceptance": (_TID, ["set-acceptance", "{t}", "--check", "1"]),
    "add-spawned": (_TID, ["add-spawned", "{t}", _OTHER]),
    "remove-spawned": (_HAS_SPAWNED, ["remove-spawned", "{t}", _OTHER]),
    "set-blocked-by": (_TID, ["set-blocked-by", "{t}", _OTHER]),
    "set-related-to": (_TID, ["set-related-to", "{t}", _OTHER]),
    "phase": (_TID, ["phase", "{t}", "phase1", "some-agent"]),
    "add-spawn-request": (_TID, [
        "add-spawn-request", "{t}", "--what", "w", "--why", "y",
        "--type", "IMP", "--priority", "P2",
    ]),
    "register-artifact": (_TID, [
        "register-artifact", "{t}", "--path", "x.txt", "--purpose", "p", "--expiry", "e",
    ]),
    "add-exempt-marker": (_TID, [
        "add-exempt-marker", "{t}", "--section", "Solution", "--match", "sol",
        "--category", "history", "--reason", "W0-001 historical reference",
    ]),
    "set-closed-by": (_CLOSED, ["set-closed-by", "{t}", "--value", _OTHER]),
    "restore": (_CLOSED, ["restore", "{t}", "--reason", "restore for test"]),
}


def _argv(name: str) -> list:
    target, argv = _COMMANDS[name]
    return [a.replace("{t}", target) for a in argv]


@pytest.mark.parametrize("name", sorted(_COMMANDS))
def test_control_no_lock_commits_silently(name, repo, monkeypatch, capsys):
    rc = _run(monkeypatch, *_argv(name))
    cap = capsys.readouterr()
    assert rc == 0, cap.out + cap.err
    assert "[WARNING]" not in cap.err
    assert _dirty(repo) == "", "寫入後工作區不得留未提交的票檔"


@pytest.mark.parametrize("name", sorted(_COMMANDS))
def test_residual_lock_fails_visibly_with_75(name, repo, monkeypatch, capsys):
    _plant_lock(repo)
    rc = _run(monkeypatch, *_argv(name))
    cap = capsys.readouterr()
    assert rc == git_utils.EXIT_AUTO_COMMIT_FAILED, cap.out + cap.err
    assert "[WARNING]" in cap.err
    assert "exit code 75" in cap.err
