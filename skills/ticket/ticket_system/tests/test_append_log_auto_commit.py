"""W7-001 — append-log auto-commit 根因解 RED 測試（Phase 2）。

設計依據：1.0.0-W7-001 Solution「新設計：append-log auto-commit」+
「auto-commit 專屬設計考量」+「更新驗收標準」6 項。

核心問題（承接 W1-017 ANA）：
ticket body 經 append-log 寫入後停留於未 commit 的 working tree，被
`git checkout -- <file>` / `git reset --hard` / `git stash` 覆蓋回 create
commit 的 placeholder 版本。根因解：append-log 寫入後 auto-commit ticket md，
使 body 即時進 commit 歷史，三種 git 還原（checkout / reset --hard / stash）全失效。

新設計（取代舊 auto-stage + 方案 C hook 設計）：
- 修改點：track_acceptance.py `_execute_append_log_locked`，body 寫入（save_ticket）
  後新增 auto-commit。
- 薄封裝：`_auto_commit_ticket_md(path, ticket_id, section)` 於 lib/git_utils.py。
- commit 範圍：精確路徑（僅該 ticket md，無 ./、-A、--all）。
- commit message：`chore(<ticket_id>): append-log <section>`。

更新驗收標準（本檔 RED 測試 1:1 對應）：
1. append-log 寫入後產生 commit，git log 可見該 ticket md commit（body 進歷史）
2. auto-commit 後 `git reset --hard` 後 body 仍可從 commit 取回（根因解生效）
3. body 無變更時 append-log 不產生空 commit（graceful skip）
4. git 不可用 / index.lock 時 append-log 仍成功 exit 0 + stderr 警告
5. commit message 格式 `chore(<id>): append-log <section>`
6. 行為變更過 ticket-skill-sync-check（由 PM/hook 驗證，本檔不涵蓋自動化）

RED 預期：
- `lib/git_utils.py` 與 `_auto_commit_ticket_md` 尚未實作 → AC1/2/3/5 相關測試應失敗。
- append-log 目前未呼叫 auto-commit → commit 不會產生 → 對應斷言 RED。

還原行為（reset --hard / checkout / stash）使用真實 git repo fixture（非純 mock），
以驗證根因解在真實 git 語義下生效。
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter


# ============================================================
# 真實 git repo fixture
# ============================================================


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """在指定 repo 執行 git 命令並回傳結果。"""
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )


def _write_ticket_md(path: Path, tid: str) -> None:
    """寫入最小可解析 ticket md（含 placeholder body section）。"""
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        "type: IMP\n"
        "status: in_progress\n"
        "assigned: true\n"
        "tdd_phase: phase3b\n"
        "children: []\n"
        "blockedBy: []\n"
        "acceptance: []\n"
        "spawned_tickets: []\n"
        "---\n\n"
    )
    body = (
        "# Execution Log\n\n"
        "## Solution\n"
        "<!-- Schema[IMP/Solution]: 選填 -->\n\n"
        "<!-- To be filled by executing agent -->\n\n"
        "---\n\n"
        "## Test Results\n\n"
        "placeholder.\n"
    )
    path.write_text(fm + body, encoding="utf-8")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """建立真實 git repo，含已 commit（tracked）的 ticket md（placeholder body）。

    模擬 create commit：ticket md 進入 git 歷史的 placeholder 版本。
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@test.com")
    _run_git(repo, "config", "user.name", "test")

    tickets_dir = repo / "tickets"
    tickets_dir.mkdir()
    tid = "0.0.0-W0-AC"
    md_path = tickets_dir / f"{tid}.md"
    _write_ticket_md(md_path, tid)

    _run_git(repo, "add", str(md_path))
    _run_git(repo, "commit", "-m", "create ticket (placeholder)")
    return repo


@pytest.fixture
def patch_paths_to_repo(git_repo: Path, monkeypatch):
    """將 ticket loader/saver 路徑導向 git_repo 內的 tickets 目錄。"""
    tickets_dir = git_repo / "tickets"

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

    from ticket_system.commands import track_acceptance as ta_mod
    from ticket_system.lib import ticket_loader

    for mod in (ta_mod, ticket_loader):
        monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
        monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)

    return git_repo


def _call_append_log(ticket_id: str, section: str, content: str) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(ticket_id=ticket_id, section=section, content=content)
    return execute_append_log(ns, "0.0.0")


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


def _last_commit_message(repo: Path) -> str:
    result = _run_git(repo, "log", "-1", "--pretty=%s")
    return result.stdout.strip()


# ============================================================
# AC1: append-log 寫入後產生 commit，git log 可見 body 進歷史
# ============================================================


class TestAutoCommitProducesCommit:
    """AC1: append-log 寫入後 auto-commit，body 進 git 歷史。"""

    def test_append_log_produces_new_commit(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _commit_count(repo)

        rc = _call_append_log("0.0.0-W0-AC", "Solution", "實際實作內容 ALPHA")
        assert rc == 0

        after = _commit_count(repo)
        assert after == before + 1, (
            "append-log 應 auto-commit 產生一個新 commit（RED：尚未實作 auto-commit）"
        )

    def test_body_content_present_in_committed_version(self, patch_paths_to_repo):
        repo = patch_paths_to_repo

        rc = _call_append_log("0.0.0-W0-AC", "Solution", "實際實作內容 BETA")
        assert rc == 0

        # HEAD commit 的 ticket md 內容應含新寫入的 body（已進歷史）
        result = _run_git(repo, "show", "HEAD:tickets/0.0.0-W0-AC.md")
        assert "實際實作內容 BETA" in result.stdout, (
            "新寫入 body 應出現在 HEAD commit（RED：未 auto-commit 時 HEAD 仍為 placeholder）"
        )


# ============================================================
# AC2: auto-commit 後 reset --hard / checkout 還原仍可從 commit 取回 body
# ============================================================


class TestRestoreOperationsCannotEraseCommittedBody:
    """AC2: 三種 git 還原在 body 進 commit 後全失效（根因解生效）。

    用真實 git repo（非純 mock）驗證還原語義。
    """

    def test_reset_hard_preserves_committed_body(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        md = repo / "tickets" / "0.0.0-W0-AC.md"

        rc = _call_append_log("0.0.0-W0-AC", "Solution", "RESET_HARD_SURVIVOR")
        assert rc == 0

        # 模擬還原：reset --hard 清 working tree + index
        _run_git(repo, "reset", "--hard", "HEAD")

        # body 已進 commit，reset --hard 還原到 HEAD（含新內容）→ 不丟
        assert "RESET_HARD_SURVIVOR" in md.read_text(encoding="utf-8"), (
            "auto-commit 後 reset --hard 應保留 body（RED：未 commit 時會被還原回 placeholder）"
        )

    def test_checkout_file_preserves_committed_body(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        md = repo / "tickets" / "0.0.0-W0-AC.md"

        rc = _call_append_log("0.0.0-W0-AC", "Solution", "CHECKOUT_SURVIVOR")
        assert rc == 0

        # 模擬還原：checkout -- <file> 用 HEAD/index 覆蓋 working tree
        _run_git(repo, "checkout", "--", "tickets/0.0.0-W0-AC.md")

        assert "CHECKOUT_SURVIVOR" in md.read_text(encoding="utf-8"), (
            "auto-commit 後 checkout -- <file> 應保留 body（RED：未 commit 時會被還原）"
        )

    def test_stash_preserves_committed_body(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        md = repo / "tickets" / "0.0.0-W0-AC.md"

        rc = _call_append_log("0.0.0-W0-AC", "Solution", "STASH_SURVIVOR")
        assert rc == 0

        # body 已 commit → 無 dirty 變更，stash 不會清掉已 commit 的內容
        _run_git(repo, "stash")

        assert "STASH_SURVIVOR" in md.read_text(encoding="utf-8"), (
            "auto-commit 後 git stash 應保留 body（RED：未 commit 時 body 留 working tree 被 stash 移除）"
        )


# ============================================================
# AC3: body 無變更時 append-log 不產生空 commit（graceful skip）
# ============================================================


class TestNoEmptyCommitOnNoChange:
    """AC3: body 內容無實際變更時不產生空 commit。"""

    def test_no_commit_when_body_unchanged(self, patch_paths_to_repo, monkeypatch):
        repo = patch_paths_to_repo

        # patch save_ticket 為 no-op：模擬 body 無實際變更（檔案內容與 HEAD 相同）
        from ticket_system.commands import track_acceptance as ta_mod

        monkeypatch.setattr(ta_mod, "save_ticket", lambda *a, **k: None, raising=False)

        before = _commit_count(repo)
        rc = _call_append_log("0.0.0-W0-AC", "Solution", "內容（不寫入磁碟）")
        assert rc == 0

        after = _commit_count(repo)
        assert after == before, (
            "body 無實際變更時不應產生空 commit（RED：auto-commit graceful skip 尚未實作）"
        )


# ============================================================
# AC4: git 不可用 / index.lock 時 append-log 仍成功 + stderr 警告
# ============================================================


class TestGracefulDegrade:
    """AC4: auto-commit 失敗時 append-log 仍 exit 0 + stderr 警告，body 保留 working tree。"""

    def test_append_log_succeeds_when_not_git_repo(self, tmp_path: Path, monkeypatch, capsys):
        # 非 git repo 的 tickets 目錄
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        tid = "0.0.0-W0-NOGIT"
        md = tickets_dir / f"{tid}.md"
        _write_ticket_md(md, tid)

        def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
            return tickets_dir / f"{ticket_id}.md"

        def _fake_load_ticket(version: str, ticket_id: str):
            fm, body = parse_frontmatter(md.read_text(encoding="utf-8"))
            fm["_body"] = body
            fm["_path"] = str(md)
            return fm

        from ticket_system.commands import track_acceptance as ta_mod
        from ticket_system.lib import ticket_loader

        for mod in (ta_mod, ticket_loader):
            monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
            monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)

        rc = _call_append_log(tid, "Solution", "NOGIT_BODY")
        # graceful degrade：非 git repo commit 失敗，append-log 仍成功
        assert rc == 0, "非 git repo 時 append-log 應 graceful degrade 仍 exit 0"

        # body 保留 working tree（commit 失敗但寫入未丟）
        assert "NOGIT_BODY" in md.read_text(encoding="utf-8"), (
            "auto-commit 失敗時 body 應保留 working tree"
        )

        # stderr 應有警告（commit 失敗可觀測，quality-baseline 規則 4）
        captured = capsys.readouterr()
        assert "commit" in captured.err.lower() or "git" in captured.err.lower(), (
            "auto-commit 失敗應在 stderr 警告（RED：警告訊息尚未實作）"
        )

    def test_append_log_succeeds_when_git_commit_fails(self, patch_paths_to_repo, monkeypatch, capsys):
        # patch _auto_commit_ticket_md 拋例外，模擬 index.lock 競爭等失敗
        from ticket_system.lib import git_utils  # RED：模組尚未存在 → 觸發 ImportError

        def _raise(*a, **k):
            raise RuntimeError("simulated index.lock contention")

        monkeypatch.setattr(git_utils, "_auto_commit_ticket_md", _raise, raising=False)

        rc = _call_append_log("0.0.0-W0-AC", "Solution", "LOCK_CONTENTION_BODY")
        assert rc == 0, "auto-commit 失敗（index.lock）時 append-log 仍應 exit 0"

        captured = capsys.readouterr()
        assert "commit" in captured.err.lower() or "git" in captured.err.lower(), (
            "auto-commit 失敗應在 stderr 警告"
        )


# ============================================================
# AC5: commit message 格式 `chore(<id>): append-log <section>`
# ============================================================


class TestCommitMessageFormat:
    """AC5: auto-commit message 格式為 chore(<id>): append-log <section>。"""

    def test_commit_message_format(self, patch_paths_to_repo):
        repo = patch_paths_to_repo

        rc = _call_append_log("0.0.0-W0-AC", "Solution", "MSG_FORMAT_BODY")
        assert rc == 0

        msg = _last_commit_message(repo)
        assert msg == "chore(0.0.0-W0-AC): append-log Solution", (
            f"commit message 應為 'chore(<id>): append-log <section>'，實得 '{msg}'"
            "（RED：尚未實作 auto-commit）"
        )

    def test_commit_message_reflects_section(self, patch_paths_to_repo):
        repo = patch_paths_to_repo

        rc = _call_append_log("0.0.0-W0-AC", "Test Results", "TEST_RESULTS_BODY")
        assert rc == 0

        msg = _last_commit_message(repo)
        assert "append-log Test Results" in msg, (
            f"commit message 應反映 section 名稱，實得 '{msg}'"
        )


# ============================================================
# git_utils 薄封裝模組存在性（RED：模組尚未建立）
# ============================================================


class TestGitUtilsModuleExists:
    """新設計要求 lib/git_utils.py 提供 _auto_commit_ticket_md 薄封裝。"""

    def test_git_utils_module_importable(self):
        from ticket_system.lib import git_utils  # RED：模組尚未建立

        assert hasattr(git_utils, "_auto_commit_ticket_md"), (
            "lib/git_utils.py 應提供 _auto_commit_ticket_md（RED：尚未實作）"
        )

    def test_auto_commit_ticket_md_signature(self):
        import inspect

        from ticket_system.lib import git_utils

        sig = inspect.signature(git_utils._auto_commit_ticket_md)
        params = list(sig.parameters)
        # 設計簽章：_auto_commit_ticket_md(path, ticket_id, section)
        assert params[:3] == ["path", "ticket_id", "section"], (
            f"_auto_commit_ticket_md 簽章應為 (path, ticket_id, section)，實得 {params}"
        )
