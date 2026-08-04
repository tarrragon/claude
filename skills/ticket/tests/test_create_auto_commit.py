"""0.2.1-W3-273 — worktree 內 ticket create 產出的追蹤與清理防護：auto-commit 測試

背景（框架 issue 46 症狀三）：worktree 內執行 `ticket create` 產出的 ticket md
若停留 untracked，`git diff` / `git diff --staged` 皆偵測不到（此時該檔案對
worktree-commit-before-dispatch-hook 的 PC-019 檢查完全不可見），分支合併
不會帶入（merge 只作用於已 commit 的物件），`git worktree remove --force`
會連同 worktree 目錄整個丟棄——consumer 曾實證一張 spawn 票差點遺失。

修法（與 append-log / set-acceptance 同 W7-001 家族）：`execute()` 落盤新
ticket md 後立即走 `_auto_commit_ticket_md`（`operation="create"`），path-limited
+ graceful degrade，與既有 auto-commit 家族一致。

本檔驗證（acceptance 對應）：
1. 主 repo 下 create 落盤後產生新 commit，訊息含 operation=create
2. 主 repo 下 commit 為 path-limited（僅新 ticket md 一個檔案）
3. 非 git repo（graceful degrade）：仍 exit 0 + stderr 警告，檔案已落 working tree
4. worktree 下 create 產生的 commit 落在 worktree 分支；`git worktree
   remove --force` 後新票內容仍可從分支歷史取回（根因解核心驗證，
   對應 acceptance 第一條「分支合併可帶入」）
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False,
    )


def _make_args(**overrides) -> argparse.Namespace:
    """建立完整的 create args Namespace（沿用 test_create_source_ticket.py 模式）。

    version 固定 "0.0.0"（測試沿用 test_set_acceptance_auto_commit.py 的隔離
    版本慣例，避免與真實專案版本目錄碰撞）；wave 用 1（非 0，`if not wave`
    guard 會把 0 當「未提供」拒絕）。
    """
    defaults = {
        "version": "0.0.0",
        "wave": 1,
        "seq": None,
        "type": "IMP",
        "priority": "P2",
        "action": "測試",
        "target": "create auto-commit 驗證",
        "title": "W3-273 auto-commit 測試票",
        "who": "thyme-python-developer",
        "what": "驗證 create 落盤後 auto-commit",
        "when": "v0.0.0",
        "where_layer": "Infrastructure",
        "where_files": "src/test.py",
        "why": "0.2.1-W3-273 測試",
        "how_type": None,
        "how_strategy": "測試策略",
        "parent": None,
        "source_ticket": None,
        "blocked_by": None,
        "related_to": None,
        "acceptance": ["驗收條件 A"],
        "decision_tree_entry": "第五層:TDD",
        "decision_tree_decision": "建立測試票",
        "decision_tree_rationale": "0.2.1-W3-273 auto-commit 測試",
        "force": False,
        "quiet": False,
        "verbose": False,
        "json_output": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _install_common_mocks(monkeypatch, tickets_dir: Path) -> None:
    """安裝 execute() 需要的外部邊界 mock，但不 stub `_build_and_save_ticket`
    ——本檔要驗證的正是落盤後的真實 auto-commit 副作用，需要真實檔案寫入
    真實 git repo（沿用 test_create_id_allocation_race.py 的「真實檔案系統」
    路線，而非 test_create_source_ticket.py 的「stub 掉持久化層」路線）。
    """
    monkeypatch.setattr(
        "ticket_system.commands.create.resolve_version", lambda v: "0.0.0"
    )
    monkeypatch.setattr(
        "ticket_system.lib.version.validate_version_registered",
        lambda v: (True, ""),
    )
    monkeypatch.setattr("ticket_system.commands.create.list_tickets", lambda v: [])
    monkeypatch.setattr(
        "ticket_system.commands.create.get_tickets_dir", lambda v: tickets_dir
    )
    monkeypatch.setattr(
        "ticket_system.commands.create.get_ticket_path",
        lambda v, tid: tickets_dir / f"{tid}.md",
    )
    monkeypatch.setattr("ticket_system.commands.create.get_next_seq", lambda v, w: 1)
    monkeypatch.setattr(
        "ticket_system.commands.create.get_next_child_seq", lambda pid: 1
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """建立真實 git repo（沿用 test_set_acceptance_auto_commit.py 的 fixture 模式）。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@test.com")
    _run_git(repo, "config", "user.name", "test")

    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-m", "seed commit")
    return repo


@pytest.fixture
def patch_paths_to_repo(git_repo: Path, monkeypatch):
    tickets_dir = git_repo / "tickets"
    tickets_dir.mkdir()
    _install_common_mocks(monkeypatch, tickets_dir)
    return git_repo


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


def _last_commit_message(repo: Path) -> str:
    result = _run_git(repo, "log", "-1", "--pretty=%s")
    return result.stdout.strip()


def _single_created_ticket_id(tickets_dir: Path) -> str:
    md_files = list(tickets_dir.glob("*.md"))
    assert len(md_files) == 1, f"預期恰好一個新 ticket md，實得 {md_files}"
    return md_files[0].stem


# ============================================================
# 主 repo 情境
# ============================================================


class TestMainRepoAutoCommit:
    def test_create_produces_new_commit(self, patch_paths_to_repo):
        from ticket_system.commands.create import execute

        repo = patch_paths_to_repo
        before = _commit_count(repo)

        rc = execute(_make_args())
        assert rc == 0

        after = _commit_count(repo)
        assert after == before + 1, "create 應 auto-commit 產生一個新 commit"

    def test_commit_message_format_uses_create_operation(self, patch_paths_to_repo):
        from ticket_system.commands.create import execute

        repo = patch_paths_to_repo
        tickets_dir = repo / "tickets"

        rc = execute(_make_args())
        assert rc == 0

        ticket_id = _single_created_ticket_id(tickets_dir)
        msg = _last_commit_message(repo)
        assert msg == f"chore({ticket_id}): create Task Summary", (
            f"commit message 應含 operation=create，實得 '{msg}'"
        )

    def test_commit_only_touches_new_ticket_md(self, patch_paths_to_repo):
        from ticket_system.commands.create import execute

        repo = patch_paths_to_repo
        rc = execute(_make_args())
        assert rc == 0

        result = _run_git(repo, "show", "--stat", "--pretty=format:", "HEAD")
        assert "1 file changed" in result.stdout, (
            f"path-limited commit 應只涉及單一檔案，實得: {result.stdout!r}"
        )


class TestMainRepoGracefulDegrade:
    def test_not_git_repo_graceful_degrade(self, tmp_path: Path, monkeypatch, capsys):
        from ticket_system.commands.create import execute

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        _install_common_mocks(monkeypatch, tickets_dir)

        rc = execute(_make_args())
        assert rc == 0, "非 git repo 時 create 應 graceful degrade 仍 exit 0"

        ticket_id = _single_created_ticket_id(tickets_dir)
        assert (tickets_dir / f"{ticket_id}.md").exists(), (
            "auto-commit 失敗時 ticket md 應保留 working tree"
        )

        captured = capsys.readouterr()
        assert "commit" in captured.err.lower() or "git" in captured.err.lower(), (
            "auto-commit 失敗應在 stderr 警告（與 append-log/set-acceptance 一致）"
        )


# ============================================================
# worktree 情境（本票存在的理由：issue 46 症狀三——untracked ticket md
# 在 `git worktree remove --force` 下靜默丟棄）
# ============================================================


class TestWorktreeAutoCommit:
    @pytest.fixture
    def worktree(self, git_repo: Path):
        worktree_dir = git_repo.parent / "worktree"
        result = _run_git(
            git_repo, "worktree", "add", "-b", "feat/w3-273-test", str(worktree_dir)
        )
        assert result.returncode == 0, f"worktree add 失敗: {result.stderr}"
        return git_repo, worktree_dir

    def test_commit_lands_on_worktree_branch_not_main(self, worktree, monkeypatch):
        main_repo, worktree_dir = worktree
        tickets_dir = worktree_dir / "tickets"
        tickets_dir.mkdir(exist_ok=True)
        _install_common_mocks(monkeypatch, tickets_dir)

        from ticket_system.commands.create import execute

        main_head_before = _run_git(main_repo, "rev-parse", "HEAD").stdout.strip()

        rc = execute(_make_args())
        assert rc == 0

        wt_log = _run_git(worktree_dir, "log", "-1", "--pretty=%s")
        assert "create" in wt_log.stdout

        main_head_after = _run_git(main_repo, "rev-parse", "HEAD").stdout.strip()
        assert main_head_after == main_head_before, (
            "worktree 內的 commit 不應變更主 repo 分支的 HEAD"
        )

    def test_worktree_remove_force_no_longer_loses_new_ticket(self, worktree, monkeypatch):
        """根因解核心驗證：auto-commit 後 `worktree remove --force` 不再丟棄
        create 產出的新 ticket（未修復前為 untracked，此步驟會靜默消失）。"""
        main_repo, worktree_dir = worktree
        tickets_dir = worktree_dir / "tickets"
        tickets_dir.mkdir(exist_ok=True)
        _install_common_mocks(monkeypatch, tickets_dir)

        from ticket_system.commands.create import execute

        rc = execute(_make_args())
        assert rc == 0

        ticket_id = _single_created_ticket_id(tickets_dir)

        # 變更已進 worktree 分支的 commit 歷史後，才移除 worktree
        remove_result = _run_git(
            main_repo, "worktree", "remove", "--force", str(worktree_dir)
        )
        assert remove_result.returncode == 0

        # 從主 repo 檢視該分支的最新 commit，新票內容仍可取回（未隨 worktree
        # 目錄消失；對應 acceptance「分支合併可帶入」——分支歷史本身即已含入，
        # 後續 `git merge feat/w3-273-test` 會正常帶入）
        show_result = _run_git(
            main_repo, "show", f"feat/w3-273-test:tickets/{ticket_id}.md"
        )
        assert show_result.returncode == 0, (
            f"應可從分支歷史取回新票內容，git show 失敗: {show_result.stderr}"
        )
        assert ticket_id in show_result.stdout

    def test_merge_brings_in_new_ticket(self, worktree, monkeypatch):
        """acceptance 第一條字面驗證：分支合併確實帶入新票（而非僅倖存於分支歷史）。"""
        main_repo, worktree_dir = worktree
        tickets_dir = worktree_dir / "tickets"
        tickets_dir.mkdir(exist_ok=True)
        _install_common_mocks(monkeypatch, tickets_dir)

        from ticket_system.commands.create import execute

        rc = execute(_make_args())
        assert rc == 0
        ticket_id = _single_created_ticket_id(tickets_dir)

        merge_result = _run_git(
            main_repo, "merge", "feat/w3-273-test", "--no-edit"
        )
        assert merge_result.returncode == 0, f"merge 失敗: {merge_result.stderr}"

        merged_path = main_repo / "tickets" / f"{ticket_id}.md"
        assert merged_path.exists(), "merge 後新票應存在於主 repo 工作目錄"
