"""set-closed-by 子命令測試（closed 票 closed_by 欄位修正路徑）。

背景：close 對已 closed 票拒絕覆寫，CLI 無 reopen 子命令，ticket md 直接
Edit 被 hook 阻擋——修正 closed_by 三條既有路徑皆封閉。本檔驗證新增的
set-closed-by 子命令補上此缺口。

驗證範圍：
1. 合法修正路徑：closed 票 + 合法且存在的新 Ticket ID → 成功修正並 auto-commit
2. 非法輸入：--value 非合法 Ticket ID 格式 → 拒絕，不寫入
3. 非法輸入：--value 指向不存在的 Ticket → 拒絕，不寫入
4. 前置條件：非 closed 狀態的票 → 拒絕
5. 冪等：新值與舊值相同 → 不產生變更、不 commit
6. 值域依 close_reason 限定（3.1.0-W1-057）：預設 reason 收 none、
   transferred_to_issue 只收 issue 參照、superseded_by 只收 Ticket ID
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False,
    )


def _write_ticket_md(
    path: Path,
    tid: str,
    status: str = "closed",
    closed_by: str = "some-agent",
    close_reason: str = "goal_achieved",
) -> None:
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
            "closed_at: '2026-01-01T00:00:00'",
            f"closed_by: {closed_by}",
            f"close_reason: {close_reason}",
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

    # 目標票：closed 狀態，closed_by 填錯
    target_id = "0.0.0-W0-100"
    _write_ticket_md(tickets_dir / f"{target_id}.md", target_id, status="closed")

    # 解決者票：存在的合法 Ticket ID，供 --value 指向
    resolver_id = "0.0.0-W0-101"
    _write_ticket_md(
        tickets_dir / f"{resolver_id}.md", resolver_id, status="in_progress"
    )

    # 未關閉票：驗證前置條件
    open_id = "0.0.0-W0-102"
    _write_ticket_md(tickets_dir / f"{open_id}.md", open_id, status="in_progress")

    # 依 close_reason 限定值域的目標票（3.1.0-W1-057）
    superseded_id = "0.0.0-W0-103"
    _write_ticket_md(
        tickets_dir / f"{superseded_id}.md", superseded_id,
        closed_by="0.0.0-W0-101", close_reason="superseded_by",
    )
    transferred_id = "0.0.0-W0-104"
    _write_ticket_md(
        tickets_dir / f"{transferred_id}.md", transferred_id,
        closed_by="none", close_reason="transferred_to_issue",
    )

    for fname in (
        f"{target_id}.md", f"{resolver_id}.md", f"{open_id}.md",
        f"{superseded_id}.md", f"{transferred_id}.md",
    ):
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
        return fm

    def _fake_load_and_validate_ticket(version: str, ticket_id: str):
        ticket = _fake_load_ticket(version, ticket_id)
        if ticket is None:
            return None, f"ticket not found: {ticket_id}"
        return ticket, None

    from ticket_system.commands import track_set_closed_by as scb_mod
    from ticket_system.lib import ticket_loader

    for mod in (scb_mod, ticket_loader):
        monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
        monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)
    monkeypatch.setattr(
        scb_mod, "load_and_validate_ticket", _fake_load_and_validate_ticket, raising=False
    )


@pytest.fixture
def patch_paths_to_repo(git_repo: Path, monkeypatch):
    _patch_loaders(monkeypatch, git_repo / "tickets")
    return git_repo


def _call(ticket_id: str, value: str) -> int:
    from ticket_system.commands.track_set_closed_by import execute_set_closed_by

    ns = argparse.Namespace(ticket_id=ticket_id, value=value)
    return execute_set_closed_by(ns, "0.0.0")


def _read_closed_by(repo: Path, ticket_id: str) -> str:
    path = repo / "tickets" / f"{ticket_id}.md"
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm.get("closed_by", "")


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


class TestSetClosedByHappyPath:
    def test_corrects_closed_by_and_commits(self, patch_paths_to_repo, capsys):
        repo = patch_paths_to_repo
        before = _commit_count(repo)

        rc = _call("0.0.0-W0-100", "0.0.0-W0-101")

        assert rc == 0
        assert _read_closed_by(repo, "0.0.0-W0-100") == "0.0.0-W0-101"
        assert _commit_count(repo) == before + 1

        out = capsys.readouterr().out
        assert "舊值" in out
        assert "新值" in out
        assert "some-agent" in out
        assert "0.0.0-W0-101" in out

    def test_idempotent_when_value_unchanged(self, patch_paths_to_repo, capsys):
        repo = patch_paths_to_repo
        _call("0.0.0-W0-100", "0.0.0-W0-101")
        before = _commit_count(repo)

        rc = _call("0.0.0-W0-100", "0.0.0-W0-101")

        assert rc == 0
        assert _commit_count(repo) == before  # 無變更，不 commit


class TestSetClosedByInvalidInput:
    def test_rejects_non_ticket_id_format(self, patch_paths_to_repo, capsys):
        rc = _call("0.0.0-W0-100", "thyme-python-developer")

        assert rc == 1
        assert "closed_by 須為" in capsys.readouterr().out
        assert _read_closed_by(patch_paths_to_repo, "0.0.0-W0-100") == "some-agent"

    def test_rejects_nonexistent_ticket_id(self, patch_paths_to_repo, capsys):
        rc = _call("0.0.0-W0-100", "0.0.0-W0-999")

        assert rc == 1
        assert "不存在" in capsys.readouterr().out
        assert _read_closed_by(patch_paths_to_repo, "0.0.0-W0-100") == "some-agent"

    def test_rejects_non_closed_ticket(self, patch_paths_to_repo, capsys):
        rc = _call("0.0.0-W0-102", "0.0.0-W0-101")

        assert rc == 1
        assert "僅適用 status=closed" in capsys.readouterr().out


class TestSetClosedByReasonDomain:
    """值域依 close_reason 限定，與 close、hook 共用驗證函式（3.1.0-W1-057）。"""

    def test_accepts_none_for_default_reason(self, patch_paths_to_repo):
        rc = _call("0.0.0-W0-100", "none")

        assert rc == 0
        assert _read_closed_by(patch_paths_to_repo, "0.0.0-W0-100") == "none"

    def test_rejects_issue_ref_for_default_reason(self, patch_paths_to_repo, capsys):
        rc = _call("0.0.0-W0-100", "tarrragon/claude#60")

        assert rc == 1
        assert "closed_by 須為" in capsys.readouterr().out
        assert _read_closed_by(patch_paths_to_repo, "0.0.0-W0-100") == "some-agent"

    def test_accepts_issue_ref_for_transferred(self, patch_paths_to_repo):
        rc = _call("0.0.0-W0-104", "tarrragon/claude#60")

        assert rc == 0
        assert _read_closed_by(patch_paths_to_repo, "0.0.0-W0-104") == "tarrragon/claude#60"

    @pytest.mark.parametrize("value", ["none", "0.0.0-W0-101"])
    def test_rejects_non_issue_ref_for_transferred(self, patch_paths_to_repo, capsys, value):
        rc = _call("0.0.0-W0-104", value)

        assert rc == 1
        assert "issue 參照" in capsys.readouterr().out
        assert _read_closed_by(patch_paths_to_repo, "0.0.0-W0-104") == "none"

    @pytest.mark.parametrize("value", ["none", "tarrragon/claude#60"])
    def test_rejects_non_ticket_id_for_superseded(self, patch_paths_to_repo, capsys, value):
        rc = _call("0.0.0-W0-103", value)

        assert rc == 1
        assert "closed_by 須為 Ticket ID" in capsys.readouterr().out
        assert _read_closed_by(patch_paths_to_repo, "0.0.0-W0-103") == "0.0.0-W0-101"
