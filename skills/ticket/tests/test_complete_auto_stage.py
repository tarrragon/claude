"""
ticket complete 自動隔離索引提交測試

沿革：W11-035 原採「自動 git add + stdout 建議裸 commit」（方案 D），留
staged 狀態於共用 index 等人工裸 commit；同儕 commit 8db456783 把共用
index 中過期 index 快照寫進 HEAD 的事故顯示，留 staged 狀態本身就是入口。
改為 CLI 自身以 commit_files_isolated（GIT_INDEX_FILE 隔離 + 提交前自檢）
直接完成提交，不留任何 staged 殘留於共用 index。

驗證情境：
1. 正常 complete：ticket md + worklog md 交由 commit_files_isolated 提交
2. cascade complete：unblocked children 落盤且 save 成功者進入提交清單
3. blockedBy 反向解鎖的 siblings 落盤且 save 成功者進入提交清單
4. --no-stage flag：跳過自動提交
5. stdout 含 commit SHA（成功時），不再印出「建議裸 commit」指令
6. 不誤觸提交範圍外的 WIP 檔案（僅提交已知 modified 路徑）
"""

from unittest.mock import patch

import pytest

TEMPLATE_BODY = """## Completion Info

**Completion Time**: (pending)
**Executing Agent**: thyme-python-developer
**Review Status**: pending
"""


def _build_ticket(ticket_id="0.18.0-W17-998", children=None):
    return {
        "id": ticket_id,
        "status": "in_progress",
        "title": "Test auto stage",
        "type": "IMP",
        "who": {"current": "thyme-python-developer"},
        "acceptance": [{"text": "x", "completed": True}],
        "children": children or [],
        "_body": TEMPLATE_BODY,
        "_path": f"/tmp/{ticket_id}.md",
    }


def _run_complete(
    *,
    ticket,
    no_stage=False,
    cascade_unblocked=None,
    reverse_unblock_tickets=None,
    captured_saves=None,
    commit_result=None,
    worklog_written=True,
):
    """共用 patch 結構，回傳 (result, captured_commit_calls)。

    commit_result: 若傳入，覆寫 commit_files_isolated 的回傳值（預設為
        committed + 固定 SHA）。
    reverse_unblock_tickets: 額外併入 list_tickets 回傳值的 ticket dict
        清單，供真實 _reverse_unblock_blockedby（未 mock）掃描 blockedBy
        反向解鎖（siblings 測試用）。
    captured_saves: 若傳入 list，save_ticket 每次呼叫的 {id, status}
        會被記錄進去，供驗證「落盤仍發生」。
    """
    from ticket_system.commands.lifecycle import TicketLifecycle

    lifecycle = TicketLifecycle("0.18.0")

    captured_calls = []

    default_commit_result = {
        "status": "committed",
        "commit_sha": "abc123def4567890",
        "error": None,
    }

    def fake_commit_files_isolated(paths, message, cwd=None):
        captured_calls.append(
            {"paths": list(paths), "message": message, "cwd": cwd}
        )
        return commit_result or default_commit_result

    # cascade fake：模擬 _post_complete_cascade 解鎖 children
    def fake_cascade(parent_ticket, version, ticket_map, saved_paths=None):
        unblocked = []
        if cascade_unblocked:
            for child_id in cascade_unblocked:
                if child_id in ticket_map:
                    ticket_map[child_id]["status"] = "pending"
                if saved_paths is not None:
                    saved_paths.append(f"/tmp/{child_id}.md")
                unblocked.append({"id": child_id, "title": ""})
        return unblocked

    def fake_resolve_path(t, version, tid):
        return f"/tmp/{tid}.md"

    def fake_save(t, path):
        if captured_saves is not None:
            captured_saves.append({"id": t.get("id"), "status": t.get("status")})

    # 模擬 worklog appender 寫入後路徑可推導
    fake_worklog_path = "/tmp/worklog-0.18.0.md"

    with patch(
        "ticket_system.commands.lifecycle.load_and_validate_ticket",
        return_value=(ticket, None),
    ), patch(
        "ticket_system.commands.lifecycle.validate_completable_status",
        return_value=(True, "", False),
    ), patch(
        "ticket_system.commands.lifecycle.validate_acceptance_criteria",
        return_value=(True, []),
    ), patch(
        "ticket_system.commands.lifecycle.validate_execution_log",
        return_value=(True, []),
    ), patch(
        "ticket_system.commands.lifecycle.validate_execution_log_by_type",
        return_value=(True, []),
    ), patch(
        "ticket_system.commands.lifecycle.validate_self_check_subsection",
        return_value=(True, None),
    ), patch(
        "ticket_system.commands.lifecycle.save_ticket",
        side_effect=fake_save,
    ), patch(
        "ticket_system.commands.lifecycle.resolve_ticket_path",
        side_effect=fake_resolve_path,
    ), patch(
        "ticket_system.commands.lifecycle.append_worklog_progress",
        return_value=worklog_written,
    ), patch(
        "ticket_system.commands.lifecycle._build_worklog_path_for_stage",
        return_value=fake_worklog_path,
    ), patch(
        "ticket_system.commands.lifecycle.list_tickets",
        return_value=(
            [{"id": cid} for cid in (cascade_unblocked or [])]
            + (reverse_unblock_tickets or [])
        ),
    ), patch(
        "ticket_system.commands.lifecycle._analyze_next_steps",
        return_value={},
    ), patch(
        "ticket_system.commands.lifecycle._print_next_steps"
    ), patch(
        "ticket_system.commands.lifecycle._auto_handoff_if_needed"
    ), patch(
        "ticket_system.commands.lifecycle._handle_ana_spawned_confirmation",
        return_value=None,
    ), patch(
        "ticket_system.commands.lifecycle._handle_pending_children_block",
        return_value=None,
    ), patch(
        "ticket_system.commands.lifecycle._post_complete_cascade",
        side_effect=fake_cascade,
    ), patch(
        "ticket_system.commands.lifecycle.commit_files_isolated",
        side_effect=fake_commit_files_isolated,
    ):
        result = lifecycle.complete(ticket["id"], no_stage=no_stage)

    return result, captured_calls


class TestCompleteAutoStage:
    def test_complete_commits_ticket_and_worklog(self, capsys):
        ticket = _build_ticket()
        result, calls = _run_complete(ticket=ticket)

        assert result == 0
        assert len(calls) == 1, f"expected 1 commit_files_isolated call, got {calls}"
        committed = calls[0]["paths"]
        assert any("0.18.0-W17-998.md" in p for p in committed), committed
        assert any("worklog" in p for p in committed), committed
        # W4-026：cwd 錨定為 modified_paths[0]（票面 md）所在目錄
        assert calls[0]["cwd"] == "/tmp", calls[0]

    def test_worklog_written_vs_skipped_changes_commit_scope(self, capsys):
        """E1 對照：追加回傳 True／False 兩案，提交範圍的工作日誌成員不同。"""
        _, calls_written = _run_complete(
            ticket=_build_ticket(), worklog_written=True
        )
        _, calls_skipped = _run_complete(
            ticket=_build_ticket(), worklog_written=False
        )

        written = calls_written[0]["paths"]
        skipped = calls_skipped[0]["paths"]
        assert any("worklog" in p for p in written), written
        assert not any("worklog" in p for p in skipped), skipped
        assert any("0.18.0-W17-998.md" in p for p in skipped), skipped

    def test_complete_cascade_commits_children(self, capsys):
        """children 解鎖且 save 成功者進入提交清單，commit body 列出其 ID。"""
        captured_saves = []
        ticket = _build_ticket(children=["0.18.0-W17-998.1"])
        result, calls = _run_complete(
            ticket=ticket,
            cascade_unblocked=["0.18.0-W17-998.1"],
            captured_saves=captured_saves,
        )

        assert result == 0
        assert len(calls) == 1
        committed = calls[0]["paths"]
        assert any("0.18.0-W17-998.1.md" in p for p in committed), committed
        assert "0.18.0-W17-998.1" in calls[0]["message"], calls[0]

    def test_complete_reverse_unblock_commits_siblings(self, capsys):
        """blockedBy 反向解鎖的兄弟 Ticket 落盤且進入提交清單。"""
        parent_id = "0.18.0-W17-994"
        sibling_id = "0.18.0-W17-993"
        ticket = _build_ticket(ticket_id=parent_id)
        # ticket_map 需含已完成的 parent 自身，供 is_fully_unblocked 判定通過
        completed_parent_snapshot = {"id": parent_id, "status": "completed"}
        sibling = {
            "id": sibling_id,
            "status": "blocked",
            "blockedBy": [parent_id],
            "title": "sibling blocked by parent",
        }
        captured_saves = []

        result, calls = _run_complete(
            ticket=ticket,
            reverse_unblock_tickets=[completed_parent_snapshot, sibling],
            captured_saves=captured_saves,
        )

        assert result == 0
        # 落盤仍發生：save_ticket 被呼叫且 sibling 狀態已改為 pending
        sibling_saves = [s for s in captured_saves if s["id"] == sibling_id]
        assert len(sibling_saves) == 1, captured_saves
        assert sibling_saves[0]["status"] == "pending", captured_saves
        # 且進入提交清單
        assert len(calls) == 1
        committed = calls[0]["paths"]
        assert any(sibling_id in p for p in committed), committed
        assert sibling_id in calls[0]["message"], calls[0]

    def test_no_stage_flag_skips_commit(self, capsys):
        ticket = _build_ticket()
        result, calls = _run_complete(ticket=ticket, no_stage=True)

        assert result == 0
        assert len(calls) == 0, f"--no-stage should skip commit, got {calls}"

    def test_stdout_prints_commit_sha_on_success(self, capsys):
        ticket = _build_ticket(ticket_id="0.18.0-W17-997")
        result, calls = _run_complete(ticket=ticket)
        captured = capsys.readouterr()

        assert result == 0
        assert "abc123de" in captured.out

    def test_stdout_silent_on_empty_status(self, capsys):
        """工作區內容與 HEAD 相同（empty 短路）時不印出提交相關訊息。"""
        ticket = _build_ticket(ticket_id="0.18.0-W17-995")
        result, calls = _run_complete(
            ticket=ticket,
            commit_result={"status": "empty", "commit_sha": None, "error": None},
        )
        captured = capsys.readouterr()

        assert result == 0
        assert len(calls) == 1
        assert "Auto-commit" not in captured.out
        assert "chore(" not in captured.out

    def test_stderr_warns_on_failed_status_not_stdout(self, capsys):
        """提交失敗時警告寫 stderr，不寫 stdout；complete 不中斷但 exit 75（0.4.0-W1-067）。
        對照：提交成功的其他測項維持 exit 0。"""
        ticket = _build_ticket(ticket_id="0.18.0-W17-991")
        result, calls = _run_complete(
            ticket=ticket,
            commit_result={
                "status": "failed",
                "commit_sha": None,
                "error": "提交範圍自我驗證失敗",
            },
        )
        captured = capsys.readouterr()

        assert result == 75
        assert len(calls) == 1
        assert "[WARNING]" in captured.err
        assert "git add" in captured.err and "補救指令" in captured.err
        assert "提交範圍自我驗證失敗" in captured.err
        assert "提交範圍自我驗證失敗" not in captured.out

    def test_no_pathspec_bare_commit_suggestion_printed(self, capsys):
        """改造後不再印出「建議裸 commit」指令——提交已由 CLI 自身完成，
        不留 staged 狀態給人工操作。"""
        ticket = _build_ticket(ticket_id="0.18.0-W17-996")
        result, calls = _run_complete(ticket=ticket)
        captured = capsys.readouterr()

        assert result == 0
        assert "git commit -m" not in captured.out
        assert "git diff --cached --name-only" not in captured.out

    def test_commit_message_contains_ticket_id(self, capsys):
        ticket = _build_ticket(ticket_id="0.18.0-W17-990")
        result, calls = _run_complete(ticket=ticket)

        assert result == 0
        assert len(calls) == 1
        assert "0.18.0-W17-990" in calls[0]["message"]

    def test_auto_commit_only_passes_known_paths(self, capsys):
        """commit_files_isolated 參數須為精確路徑，不包含 './' 或 '-A'"""
        ticket = _build_ticket()
        _, calls = _run_complete(ticket=ticket)

        assert calls
        committed = calls[0]["paths"]
        # 禁止寬範圍參數
        for arg in committed:
            assert arg not in (".", "./", "-A", "--all"), (
                f"auto-commit must use precise paths, got {committed}"
            )
        # 所有提交路徑都應是 .md 結尾
        for arg in committed:
            assert arg.endswith(".md"), f"unexpected committed path: {arg}"


# ---------------------------------------------------------------------------
# 真實 repo、真實 CLI 入口：complete 連帶解鎖的票併入同一筆 commit
# ---------------------------------------------------------------------------

import subprocess
import sys
from pathlib import Path

from ticket_system.lib import git_ops, git_utils
from ticket_system.lib.paths import get_ticket_path

_REAL_VER = "0.0.0"
_OTHER_VER = "0.0.1"
_PARENT = "0.0.0-W0-001"
_CHILD = "0.0.0-W0-002"
_CROSS = "0.0.1-W0-001"

_REAL_FM = """---
id: {tid}
title: t-{tid}
type: IMP
status: {status}
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
blockedBy: {blocked_by}
relatedTo: []
spawned_tickets: []
source_ticket: null
acceptance:
- '[x] a1'
assigned: true
tdd_stage: []
{extra}---

# Execution Log

## Problem Analysis

pa

## Solution

sol

### 自檢結果

- [x] 已自檢

## Test Results

tr

## Spawn Requests

"""


def _real_git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout


def _seed_real(ver, tid, status, children="[]", blocked_by="[]", extra=""):
    path = get_ticket_path(ver, tid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _REAL_FM.format(
            tid=tid, ver=ver, status=status, children=children,
            blocked_by=blocked_by, extra=extra,
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def real_repo(tmp_path, monkeypatch):
    """父票 in_progress；同版本 child 與跨版本引用者皆 blocked 於父票。"""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setenv("TICKET_SYSTEM_TEST_ISOLATION", "1")
    _real_git(tmp_path, "init", "-q", "-b", "main")
    _real_git(tmp_path, "config", "user.email", "t@example.com")
    _real_git(tmp_path, "config", "user.name", "t")
    _seed_real(_REAL_VER, _PARENT, "in_progress", children=f"[{_CHILD}]")
    _seed_real(
        _REAL_VER, _CHILD, "blocked", blocked_by=f"[{_PARENT}]",
        extra=f"parent_id: {_PARENT}\n",
    )
    _seed_real(_OTHER_VER, _CROSS, "blocked", blocked_by=f"[{_PARENT}]")
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "todolist.yaml").write_text(
        "versions:\n- version: 0.0.0\n  status: active\n"
        "- version: 0.0.1\n  status: planned\n",
        encoding="utf-8",
    )
    worklog = tmp_path / "docs/work-logs/v0/v0.0/v0.0.0/v0.0.0-main.md"
    worklog.parent.mkdir(parents=True, exist_ok=True)
    worklog.write_text("# w\n\n### 2026-01-01\n\n- x\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".claude/hook-logs/\n", encoding="utf-8")
    _real_git(tmp_path, "add", "-A")
    _real_git(tmp_path, "commit", "-q", "-m", "seed")
    monkeypatch.setattr(git_utils, "_COMMIT_RETRY_BUDGET_SECONDS", 0.0)
    monkeypatch.setattr(git_ops.time, "sleep", lambda _s: None)
    return tmp_path


def _cli_complete(monkeypatch, tid, ver=_REAL_VER) -> int:
    from ticket_system.scripts import ticket as cli

    monkeypatch.setattr(
        sys, "argv", ["ticket", "track", "complete", tid, "--version", ver, "--as", "tester",
         "--force"]  # 有未完成 children 時 complete 預設阻擋；cascade 路徑須 --force
    )
    try:
        return cli.main() or 0
    except SystemExit as exc:
        return int(exc.code or 0)


def _head_names(repo: Path) -> set:
    out = _real_git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
    return {Path(line).name for line in out.splitlines() if line.strip()}


class TestCompleteCommitsUnblockedTickets:
    def test_unblocked_child_and_cross_version_in_same_commit(
        self, real_repo, monkeypatch, capsys
    ):
        before = int(_real_git(real_repo, "rev-list", "--count", "HEAD"))
        rc = _cli_complete(monkeypatch, _PARENT)
        captured = capsys.readouterr()

        assert rc == 0, captured.out + captured.err
        assert _real_git(real_repo, "status", "--porcelain", "--untracked-files=no") == "", captured.out
        assert int(_real_git(real_repo, "rev-list", "--count", "HEAD")) == before + 1
        assert _head_names(real_repo) == {
            f"{_PARENT}.md", f"{_CHILD}.md", f"{_CROSS}.md", "v0.0.0-main.md",
        }
        body = _real_git(real_repo, "log", "-1", "--pretty=%B")
        assert _CHILD in body and _CROSS in body

    def test_no_unblock_targets_commit_scope_is_ticket_plus_worklog(
        self, real_repo, monkeypatch, capsys
    ):
        """E1 對照：同 fixture 但無人 blocked 於本票，範圍僅本票加 worklog。"""
        _seed_real(_REAL_VER, _CHILD, "pending")
        _seed_real(_OTHER_VER, _CROSS, "pending")
        _real_git(real_repo, "add", "-A")
        _real_git(real_repo, "commit", "-q", "-m", "no-blockers")

        rc = _cli_complete(monkeypatch, _PARENT)
        captured = capsys.readouterr()

        assert rc == 0, captured.out + captured.err
        assert _real_git(real_repo, "status", "--porcelain", "--untracked-files=no") == ""
        assert _head_names(real_repo) == {f"{_PARENT}.md", "v0.0.0-main.md"}
        assert "解鎖" not in _real_git(real_repo, "log", "-1", "--pretty=%B")

    def test_residual_ref_lock_exit_75_lists_all_paths(
        self, real_repo, monkeypatch, capsys
    ):
        (real_repo / ".git" / "refs" / "heads" / "main.lock").write_text("residue\n")
        rc = _cli_complete(monkeypatch, _PARENT)
        captured = capsys.readouterr()

        assert rc == 75, captured.err
        assert "[WARNING]" in captured.err
        for name in (_PARENT, _CHILD, _CROSS):
            assert f"{name}.md" in captured.err, captured.err

    def test_failed_save_unblocked_ticket_not_in_commit(
        self, real_repo, monkeypatch, capsys
    ):
        """被解鎖票 save 失敗：不列入提交範圍，原 WARNING 照常。"""
        from ticket_system.commands import lifecycle

        real_save = lifecycle.save_ticket

        def flaky_save(ticket, path):
            if ticket.get("id") == _CHILD and ticket.get("status") == "pending":
                raise OSError("disk full")
            return real_save(ticket, path)

        monkeypatch.setattr(lifecycle, "save_ticket", flaky_save)
        rc = _cli_complete(monkeypatch, _PARENT)
        captured = capsys.readouterr()

        assert rc == 0, captured.out + captured.err
        names = _head_names(real_repo)
        assert f"{_CHILD}.md" not in names
        assert {f"{_PARENT}.md", f"{_CROSS}.md"} <= names
        assert "disk full" in captured.out + captured.err
