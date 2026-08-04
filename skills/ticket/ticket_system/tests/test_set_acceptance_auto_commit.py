"""0.2.1-W3-258 — set-acceptance auto-commit 測試（主 repo + worktree 兩情境）。

背景：0.2.1-W3-256 盤點發現 set-acceptance（與 set-priority / set-who 等）
無 auto-commit，落差在主 repo 下僅是保護等級較弱（working tree 變更仍在），
worktree 下升級為靜默遺失風險——`git worktree remove --force` 會直接丟棄
未 commit 的變更且無錯誤訊息。set-acceptance 是代理人收尾唯一必經的
frontmatter 寫入命令，risk 集中於此。

修法：`execute_set_acceptance` 寫入後走 `_auto_commit_ticket_md` 同一薄
封裝（`operation="set-acceptance"`），與 append-log 同保護等級（path-limited
+ graceful degrade）。

本檔驗證（acceptance 對應）：
1. 主 repo 下 set-acceptance 寫入後產生 commit，訊息格式含 operation
2. 主 repo 下 commit 為 path-limited（僅該 ticket md 一個檔案）
3. 非 git repo（graceful degrade）：仍 exit 0 + stderr 警告
4. worktree 下 set-acceptance 產生的 commit 落在 worktree 分支，且
   `git worktree remove --force` 後變更不遺失（根因解生效）
5. check-acceptance 排除說明另見 Solution（不同檔案、不同 save 路徑，未涵蓋）
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


def _write_ticket_md(path: Path, tid: str, acceptance: list[str] | None = None) -> None:
    """寫入最小可解析、狀態 in_progress、含 acceptance 清單的 ticket md。"""
    acceptance = acceptance or ["[ ] 條件一", "[ ] 條件二"]
    fm_lines = [
        "---",
        f"id: {tid}",
        "title: test",
        "type: IMP",
        "status: in_progress",
        "assigned: true",
        "tdd_phase: phase3b",
        "children: []",
        "blockedBy: []",
        "spawned_tickets: []",
        "acceptance:",
    ]
    fm_lines += [f"  - '{item}'" for item in acceptance]
    fm_lines.append("---\n")
    fm = "\n".join(fm_lines)
    body = (
        "# Execution Log\n\n"
        "## Solution\n\nplaceholder.\n\n"
        "## Test Results\n\nplaceholder.\n"
    )
    path.write_text(fm + "\n" + body, encoding="utf-8")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """建立真實 git repo，含已 commit（tracked）的 ticket md（沿用 append-log 測試模式）。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@test.com")
    _run_git(repo, "config", "user.name", "test")

    tickets_dir = repo / "tickets"
    tickets_dir.mkdir()
    tid = "0.0.0-W0-SA"
    md_path = tickets_dir / f"{tid}.md"
    _write_ticket_md(md_path, tid)

    _run_git(repo, "add", str(md_path))
    _run_git(repo, "commit", "-m", "create ticket (placeholder)")
    return repo


def _patch_loaders(monkeypatch, tickets_dir: Path) -> None:
    """將 set-acceptance 相關 loader/saver 路徑導向指定 tickets 目錄。"""

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

    from ticket_system.commands import track_set_acceptance as tsa_mod
    from ticket_system.lib import ticket_loader

    for mod in (tsa_mod, ticket_loader):
        monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
        monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)
    monkeypatch.setattr(
        tsa_mod, "load_and_validate_ticket", _fake_load_and_validate_ticket, raising=False
    )


@pytest.fixture
def patch_paths_to_repo(git_repo: Path, monkeypatch):
    _patch_loaders(monkeypatch, git_repo / "tickets")
    return git_repo


def _call_set_acceptance(ticket_id: str, check: list[str] | None = None) -> int:
    from ticket_system.commands.track_set_acceptance import execute_set_acceptance

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        check=check or ["1"],
        uncheck=None,
        all_check=False,
        all_uncheck=False,
        force=False,
    )
    return execute_set_acceptance(ns, "0.0.0")


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


def _last_commit_message(repo: Path) -> str:
    result = _run_git(repo, "log", "-1", "--pretty=%s")
    return result.stdout.strip()


# ============================================================
# 主 repo 情境
# ============================================================


class TestMainRepoAutoCommit:
    def test_set_acceptance_produces_new_commit(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _commit_count(repo)

        rc = _call_set_acceptance("0.0.0-W0-SA")
        assert rc == 0

        after = _commit_count(repo)
        assert after == before + 1, "set-acceptance 應 auto-commit 產生一個新 commit"

    def test_commit_message_format_uses_set_acceptance_operation(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_set_acceptance("0.0.0-W0-SA")
        assert rc == 0

        msg = _last_commit_message(repo)
        assert msg == "chore(0.0.0-W0-SA): set-acceptance Acceptance Criteria", (
            f"commit message 應含 operation=set-acceptance，實得 '{msg}'"
        )

    def test_commit_only_touches_ticket_md(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_set_acceptance("0.0.0-W0-SA")
        assert rc == 0

        result = _run_git(repo, "show", "--stat", "--pretty=format:", "HEAD")
        assert "0.0.0-W0-SA.md" in result.stdout
        assert "1 file changed" in result.stdout, (
            f"path-limited commit 應只涉及單一檔案，實得: {result.stdout!r}"
        )

    def test_reset_hard_preserves_committed_acceptance(self, patch_paths_to_repo):
        """根因解驗證：auto-commit 後 reset --hard 仍保留勾選狀態。"""
        repo = patch_paths_to_repo
        md = repo / "tickets" / "0.0.0-W0-SA.md"

        rc = _call_set_acceptance("0.0.0-W0-SA")
        assert rc == 0

        _run_git(repo, "reset", "--hard", "HEAD")
        assert "[x] 條件一" in md.read_text(encoding="utf-8")


class TestMainRepoGracefulDegrade:
    def test_not_git_repo_graceful_degrade(self, tmp_path: Path, monkeypatch, capsys):
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        tid = "0.0.0-W0-NOGIT"
        md = tickets_dir / f"{tid}.md"
        _write_ticket_md(md, tid)

        _patch_loaders(monkeypatch, tickets_dir)

        rc = _call_set_acceptance(tid)
        assert rc == 0, "非 git repo 時 set-acceptance 應 graceful degrade 仍 exit 0"
        assert "[x] 條件一" in md.read_text(encoding="utf-8"), (
            "auto-commit 失敗時 body 應保留 working tree"
        )

        captured = capsys.readouterr()
        assert "commit" in captured.err.lower() or "git" in captured.err.lower(), (
            "auto-commit 失敗應在 stderr 警告（與 append-log 一致）"
        )


# ============================================================
# worktree 情境（本票存在的理由：0.2.1-W3-256 實驗證實
# worktree remove --force 靜默丟棄未 commit 變更）
# ============================================================


class TestWorktreeAutoCommit:
    @pytest.fixture
    def worktree(self, git_repo: Path):
        """在 git_repo 上建立一個獨立分支的 worktree，回傳 (main_repo, worktree_dir)。"""
        worktree_dir = git_repo.parent / "worktree"
        result = _run_git(
            git_repo, "worktree", "add", "-b", "feat/w3-258-test", str(worktree_dir)
        )
        assert result.returncode == 0, f"worktree add 失敗: {result.stderr}"
        return git_repo, worktree_dir

    def test_commit_lands_on_worktree_branch_not_main(self, worktree, monkeypatch):
        """set-acceptance 在 worktree 內執行時，commit 應落在 worktree 分支，
        不影響主 repo 分支的 HEAD。"""
        main_repo, worktree_dir = worktree
        tickets_dir = worktree_dir / "tickets"
        # worktree add 已從分支內容 checkout tickets/（git_repo fixture 已 commit
        # 過該目錄），故此處目錄已存在，用 exist_ok 避免 FileExistsError
        tickets_dir.mkdir(exist_ok=True)
        tid = "0.0.0-W0-WT"
        _write_ticket_md(tickets_dir / f"{tid}.md", tid)

        _patch_loaders(monkeypatch, tickets_dir)

        main_head_before = _run_git(main_repo, "rev-parse", "HEAD").stdout.strip()

        rc = _call_set_acceptance(tid)
        assert rc == 0

        # worktree 分支應有新 commit（ticket md 進歷史）
        wt_log = _run_git(worktree_dir, "log", "-1", "--pretty=%s")
        assert "set-acceptance" in wt_log.stdout

        # 主 repo 分支 HEAD 不受影響（獨立 index/HEAD）
        main_head_after = _run_git(main_repo, "rev-parse", "HEAD").stdout.strip()
        assert main_head_after == main_head_before, (
            "worktree 內的 commit 不應變更主 repo 分支的 HEAD"
        )

    def test_worktree_remove_force_no_longer_loses_change(self, worktree, monkeypatch):
        """根因解核心驗證：auto-commit 後 `worktree remove --force` 不再丟棄
        set-acceptance 的變更（0.2.1-W3-256 實驗證實未 commit 時會靜默丟棄）。"""
        main_repo, worktree_dir = worktree
        tickets_dir = worktree_dir / "tickets"
        # worktree add 已從分支內容 checkout tickets/（git_repo fixture 已 commit
        # 過該目錄），故此處目錄已存在，用 exist_ok 避免 FileExistsError
        tickets_dir.mkdir(exist_ok=True)
        tid = "0.0.0-W0-WT2"
        _write_ticket_md(tickets_dir / f"{tid}.md", tid)

        _patch_loaders(monkeypatch, tickets_dir)

        rc = _call_set_acceptance(tid)
        assert rc == 0

        # 變更已進 worktree 分支的 commit 歷史後，才移除 worktree
        remove_result = _run_git(main_repo, "worktree", "remove", "--force", str(worktree_dir))
        assert remove_result.returncode == 0

        # 從主 repo 檢視該分支的最新 commit，勾選內容仍可取回（未隨 worktree 目錄消失）
        show_result = _run_git(
            main_repo, "show", f"feat/w3-258-test:tickets/{tid}.md"
        )
        assert "[x] 條件一" in show_result.stdout, (
            "auto-commit 後變更應留在分支歷史中，worktree remove --force 不應丟失"
        )
