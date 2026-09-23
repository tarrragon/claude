"""restore 子命令測試（closed 票唯一合法出邊：closed -> pending 還原路徑）。

背景：closed 為 STATUS_TRANSITIONS 定義的終態，release 與 claim 皆被
enum-gate 擋下，ticket md 直接 Edit 被 hook 阻擋——誤關票原本無法還原。
本檔驗證新增的 restore 子命令補上此缺口，並驗證該轉移只能由 restore
觸發（release / claim 對 closed 票仍被擋，各一個該紅輸入）。

驗證範圍：
1. 合法還原路徑：closed 票 + --reason → 成功還原為 pending，四個
   close 相關欄位清除，票面寫入 restored_at/restored_by/restore_reason
2. 必填驗證：--reason 缺失或空字串 → 拒絕，不寫入
3. 前置條件：非 closed 狀態的票 → 拒絕
4. 該紅輸入：release 對 closed 票仍拒絕（enum-gate 之外的 app-level guard）
5. 該紅輸入：claim 對 closed 票仍被 enum-gate 擋下（deny 模式拋錯）
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.parser import (
    ENUM_SNAPSHOT_FIELD,
    _snapshot_enum_fields,
    parse_frontmatter,
)


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False,
    )


def _write_ticket_md(path: Path, tid: str, status: str = "closed") -> None:
    fm_lines = [
        "---",
        f"id: {tid}",
        "title: test",
        "type: IMP",
        f"status: {status}",
        "assigned: true",
        "children: []",
        "blockedBy: []",
        "spawned_tickets: []",
        "acceptance: []",
    ]
    if status == "closed":
        fm_lines += [
            "completed_at: null",
            "closed_at: '2026-01-01T00:00:00'",
            "closed_by: some-issue",
            "close_reason: not_executable_knowledge_captured",
            "close_reason_note: 'mistaken close'",
        ]
    fm_lines.append("---\n")
    fm = "\n".join(fm_lines)
    body = "# Execution Log\n\n## Solution\n\nplaceholder.\n"
    path.write_text(fm + "\n" + body, encoding="utf-8")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@test.com")
    _run_git(repo, "config", "user.name", "test")

    tickets_dir = repo / "tickets"
    tickets_dir.mkdir()

    closed_id = "0.0.0-W0-200"
    _write_ticket_md(tickets_dir / f"{closed_id}.md", closed_id, status="closed")

    open_id = "0.0.0-W0-201"
    _write_ticket_md(tickets_dir / f"{open_id}.md", open_id, status="in_progress")

    for fname in (f"{closed_id}.md", f"{open_id}.md"):
        _run_git(repo, "add", f"tickets/{fname}")
    _run_git(repo, "commit", "-m", "create tickets (placeholder)")
    return repo


def _patch_loaders(monkeypatch, tickets_dir: Path) -> None:
    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tickets_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tickets_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        try:
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        fm[ENUM_SNAPSHOT_FIELD] = _snapshot_enum_fields(fm)
        return fm

    def _fake_load_and_validate_ticket(version: str, ticket_id: str):
        ticket = _fake_load_ticket(version, ticket_id)
        if ticket is None:
            return None, f"ticket not found: {ticket_id}"
        return ticket, None

    from ticket_system.commands import track_restore as restore_mod
    from ticket_system.commands import lifecycle as lifecycle_mod
    from ticket_system.lib import ticket_loader

    for mod in (restore_mod, lifecycle_mod, ticket_loader):
        monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
        monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)
    monkeypatch.setattr(
        restore_mod, "load_and_validate_ticket", _fake_load_and_validate_ticket, raising=False
    )
    monkeypatch.setattr(
        lifecycle_mod, "load_and_validate_ticket", _fake_load_and_validate_ticket, raising=False
    )


@pytest.fixture
def patch_paths_to_repo(git_repo: Path, monkeypatch):
    _patch_loaders(monkeypatch, git_repo / "tickets")
    return git_repo


def _call_restore(ticket_id: str, reason: str, as_agent: str = "") -> int:
    from ticket_system.commands.track_restore import execute_restore

    ns = argparse.Namespace(ticket_id=ticket_id, reason=reason, as_agent=as_agent)
    return execute_restore(ns, "0.0.0")


def _read_ticket(repo: Path, ticket_id: str) -> dict:
    path = repo / "tickets" / f"{ticket_id}.md"
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


class TestRestoreHappyPath:
    def test_restores_closed_to_pending_and_clears_fields(self, patch_paths_to_repo, capsys):
        repo = patch_paths_to_repo
        before = _commit_count(repo)

        rc = _call_restore("0.0.0-W0-200", "誤關票還原", as_agent="thyme-python-developer")

        assert rc == 0
        fm = _read_ticket(repo, "0.0.0-W0-200")
        assert fm["status"] == "pending"
        assert "close_reason" not in fm
        assert "close_reason_note" not in fm
        assert "closed_by" not in fm
        assert "closed_at" not in fm
        assert "completed_at" not in fm
        assert fm["restore_reason"] == "誤關票還原"
        assert fm["restored_by"] == "thyme-python-developer"
        assert "restored_at" in fm
        assert _commit_count(repo) == before + 1


class TestRestoreInvalidInput:
    def test_rejects_missing_reason(self, patch_paths_to_repo, capsys):
        rc = _call_restore("0.0.0-W0-200", "")

        assert rc == 1
        assert "--reason 必填" in capsys.readouterr().out
        fm = _read_ticket(patch_paths_to_repo, "0.0.0-W0-200")
        assert fm["status"] == "closed"

    def test_rejects_non_closed_ticket(self, patch_paths_to_repo, capsys):
        rc = _call_restore("0.0.0-W0-201", "reason")

        assert rc == 1
        assert "僅適用 status=closed" in capsys.readouterr().out


class TestClosedTerminalStillEnforced:
    """acceptance 第 2 項：closed -> pending 只能由 restore 觸發，
    release / claim 各給一個該紅輸入驗證。"""

    def test_release_rejects_closed_ticket(self, patch_paths_to_repo, capsys):
        from ticket_system.commands.lifecycle import TicketLifecycle

        lifecycle = TicketLifecycle("0.0.0")
        rc = lifecycle.release("0.0.0-W0-200")

        assert rc == 1
        assert "已關閉，無法釋放" in capsys.readouterr().out
        fm = _read_ticket(patch_paths_to_repo, "0.0.0-W0-200")
        assert fm["status"] == "closed"

    def test_claim_rejected_by_enum_gate(self, patch_paths_to_repo, capsys):
        from ticket_system.commands.lifecycle import TicketLifecycle
        from ticket_system.lib.parser import EnumGateViolation

        lifecycle = TicketLifecycle("0.0.0")
        with pytest.raises(EnumGateViolation):
            lifecycle.claim("0.0.0-W0-200")

        fm = _read_ticket(patch_paths_to_repo, "0.0.0-W0-200")
        assert fm["status"] == "closed"
