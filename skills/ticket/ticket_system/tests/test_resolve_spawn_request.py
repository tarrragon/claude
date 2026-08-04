"""resolve-spawn-request CLI 子命令測試。

背景：add-spawn-request 有 CLI 寫入端，但 PM 處理後的狀態標記（pending 改
processed 或 dismissed）過去無對應 CLI，只能直接編輯 ticket md——繞道即失
去 append-log 的 auto-commit 保護。本檔驗證：

1. CLI 可將指定 SR 標記 processed 並同時回填 spawned_tickets，或標記
   dismissed 附 reason
2. 寫入後自動 commit（path-limited），與 append-log 同保護等級
3. 對既有手改格式的 SR 條目（含全形括號說明文字）不誤判不破壞
4. 找不到 SR / status 行時報錯且不修改 body
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter


# ============================================================
# 真實 git repo fixture（沿用 test_append_log_auto_commit.py 模式）
# ============================================================


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )


_SPAWN_REQUESTS_SECTION = """## Spawn Requests
- **SR-1** (2026-08-04 10:00)
  - what: 第一個建議
  - why: 原因一
  - suggested_type: IMP
  - suggested_priority: P1
  - related_files:
  - context:
  - status: pending


- **SR-2** (2026-08-04 10:05)
  - what: 第二個建議
  - why: 原因二
  - suggested_type: ANA
  - suggested_priority: P2
  - related_files:
  - context:
  - status: pending
"""

_HAND_EDITED_SECTION = """## Spawn Requests
- **SR-1** (2026-08-04 10:00)
  - what: 第一個建議
  - why: 原因一
  - suggested_type: IMP
  - suggested_priority: P1
  - related_files:
  - context:
  - status: processed（已建 0.0.0-W0-FAKE（P1，巢狀括號說明））
"""


def _write_ticket_md(path: Path, tid: str, section: str = _SPAWN_REQUESTS_SECTION) -> None:
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
        "placeholder.\n\n"
        "---\n\n"
        f"{section}\n"
        "---\n\n"
        "## Completion Info\n"
        "placeholder.\n"
    )
    path.write_text(fm + body, encoding="utf-8")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@test.com")
    _run_git(repo, "config", "user.name", "test")

    tickets_dir = repo / "tickets"
    tickets_dir.mkdir()
    tid = "0.0.0-W0-SR"
    md_path = tickets_dir / f"{tid}.md"
    _write_ticket_md(md_path, tid)

    _run_git(repo, "add", str(md_path))
    _run_git(repo, "commit", "-m", "create ticket (placeholder)")
    return repo


@pytest.fixture
def patch_paths_to_repo(git_repo: Path, monkeypatch):
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


def _call_resolve(
    ticket_id: str,
    sr_label: str,
    status: str,
    spawned_ticket=None,
    reason=None,
    force=False,
) -> int:
    from ticket_system.commands.track_acceptance import execute_resolve_spawn_request

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        sr_label=sr_label,
        status=status,
        spawned_ticket=spawned_ticket,
        reason=reason,
        force=force,
    )
    return execute_resolve_spawn_request(ns, "0.0.0")


def _read_md(repo: Path, tid: str = "0.0.0-W0-SR") -> str:
    return (repo / "tickets" / f"{tid}.md").read_text(encoding="utf-8")


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


def _last_commit_message(repo: Path) -> str:
    result = _run_git(repo, "log", "-1", "--pretty=%s")
    return result.stdout.strip()


# ============================================================
# AC1: processed 帶 spawned ticket，回填 spawned_tickets + 狀態行更新
# ============================================================


class TestResolveProcessed:
    def test_mark_processed_updates_status_line(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_resolve("0.0.0-W0-SR", "SR-1", "processed", spawned_ticket=["0.0.0-W0-100"])
        assert rc == 0

        content = _read_md(repo)
        assert "- status: processed（已建 0.0.0-W0-100）" in content
        # 未修改的 SR-2 應維持 pending
        assert "- status: pending" in content

    def test_mark_processed_backfills_spawned_tickets_field(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_resolve("0.0.0-W0-SR", "SR-1", "processed", spawned_ticket=["0.0.0-W0-100"])
        assert rc == 0

        fm, _ = parse_frontmatter(_read_md(repo))
        assert fm["spawned_tickets"] == ["0.0.0-W0-100"]

    def test_mark_processed_multi_spawned_tickets(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_resolve(
            "0.0.0-W0-SR", "SR-2", "processed",
            spawned_ticket=["0.0.0-W0-101", "0.0.0-W0-102"],
        )
        assert rc == 0

        content = _read_md(repo)
        assert "0.0.0-W0-101" in content and "0.0.0-W0-102" in content
        fm, _ = parse_frontmatter(content)
        assert fm["spawned_tickets"] == ["0.0.0-W0-101", "0.0.0-W0-102"]

    def test_mark_processed_dedupes_existing_spawned_tickets(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc1 = _call_resolve("0.0.0-W0-SR", "SR-1", "processed", spawned_ticket=["0.0.0-W0-100"])
        assert rc1 == 0
        rc2 = _call_resolve("0.0.0-W0-SR", "SR-2", "processed", spawned_ticket=["0.0.0-W0-100"])
        assert rc2 == 0

        fm, _ = parse_frontmatter(_read_md(repo))
        # 同一 ID 重複標記不應在 spawned_tickets 出現兩次
        assert fm["spawned_tickets"] == ["0.0.0-W0-100"]

    def test_mark_processed_without_spawned_ticket_bare_value(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_resolve("0.0.0-W0-SR", "SR-1", "processed")
        assert rc == 0

        content = _read_md(repo)
        assert "- status: processed" in content
        # 無 spawned ticket 時不應出現括號說明
        assert "processed（" not in content.split("SR-1")[1].split("SR-2")[0]


# ============================================================
# AC2: dismissed 帶 reason
# ============================================================


class TestResolveDismissed:
    def test_mark_dismissed_with_reason(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_resolve("0.0.0-W0-SR", "SR-2", "dismissed", reason="重複建議，併入 SR-1")
        assert rc == 0

        content = _read_md(repo)
        assert "- status: dismissed（重複建議，併入 SR-1）" in content

    def test_mark_dismissed_does_not_touch_spawned_tickets(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_resolve("0.0.0-W0-SR", "SR-1", "dismissed", reason="評估後不建")
        assert rc == 0

        fm, _ = parse_frontmatter(_read_md(repo))
        assert fm.get("spawned_tickets") == []


# ============================================================
# AC3: 既有手改格式（含全形括號、巢狀括號）不誤判不破壞
# ============================================================


class TestToleratesHandEditedFormat:
    def test_updates_hand_edited_nested_parens_entry(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo2"
        repo.mkdir()
        _run_git(repo, "init")
        _run_git(repo, "config", "user.email", "test@test.com")
        _run_git(repo, "config", "user.name", "test")
        tickets_dir = repo / "tickets"
        tickets_dir.mkdir()
        tid = "0.0.0-W0-HAND"
        md_path = tickets_dir / f"{tid}.md"
        _write_ticket_md(md_path, tid, section=_HAND_EDITED_SECTION)
        _run_git(repo, "add", str(md_path))
        _run_git(repo, "commit", "-m", "create")

        def _fake_get_ticket_path(version, ticket_id):
            return tickets_dir / f"{ticket_id}.md"

        def _fake_load_ticket(version, ticket_id):
            path = tickets_dir / f"{ticket_id}.md"
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            fm["_body"] = body
            fm["_path"] = str(path)
            return fm

        from ticket_system.commands import track_acceptance as ta_mod
        from ticket_system.lib import ticket_loader

        for mod in (ta_mod, ticket_loader):
            monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
            monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)

        # 既有條目已是 processed（含巢狀全形括號），重新標記為 dismissed 應整行覆蓋成功
        rc = _call_resolve(tid, "SR-1", "dismissed", reason="重新評估後撤銷")
        assert rc == 0, "應能覆蓋既有含巢狀括號的手改格式，不因解析失敗而報錯"

        content = md_path.read_text(encoding="utf-8")
        assert "- status: dismissed（重新評估後撤銷）" in content
        # 舊的巢狀括號內容應已被整行覆蓋，不殘留
        assert "0.0.0-W0-FAKE" not in content
        # what/why 等其他欄位不應被破壞
        assert "第一個建議" in content
        assert "原因一" in content


# ============================================================
# AC4: 找不到 SR / status 行缺失時報錯，不修改 body
# ============================================================


class TestNotFoundGuards:
    def test_unknown_sr_label_returns_error(self, patch_paths_to_repo, capsys):
        repo = patch_paths_to_repo
        before = _read_md(repo)

        rc = _call_resolve("0.0.0-W0-SR", "SR-99", "processed", spawned_ticket=["0.0.0-W0-1"])
        assert rc == 1

        after = _read_md(repo)
        assert before == after, "找不到 SR 時不應修改 body"

        captured = capsys.readouterr()
        assert "SR-99" in captured.out

    def test_unknown_ticket_returns_error(self, patch_paths_to_repo):
        rc = _call_resolve("0.0.0-W0-NOTEXIST", "SR-1", "processed")
        assert rc == 1


# ============================================================
# AC5: 寫入後自動 commit，path-limited，commit message 含 section
# ============================================================


class TestAutoCommit:
    def test_resolve_produces_new_commit(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _commit_count(repo)

        rc = _call_resolve("0.0.0-W0-SR", "SR-1", "processed", spawned_ticket=["0.0.0-W0-100"])
        assert rc == 0

        after = _commit_count(repo)
        assert after == before + 1, "resolve-spawn-request 應 auto-commit 產生一個新 commit"

    def test_commit_only_touches_ticket_md(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call_resolve("0.0.0-W0-SR", "SR-1", "processed", spawned_ticket=["0.0.0-W0-100"])
        assert rc == 0

        result = _run_git(repo, "show", "--stat", "--pretty=format:", "HEAD")
        assert "0.0.0-W0-SR.md" in result.stdout
        # path-limited commit 只應涉及該 ticket md 一個檔案（git show --stat
        # 摘要行固定格式 "1 file changed, ..."，非本次改動檔案數才會 > 1）
        assert "1 file changed" in result.stdout, (
            f"應只 commit 單一檔案，實得 stat 輸出: {result.stdout!r}"
        )

    def test_commit_message_reflects_spawn_requests_section(self, patch_paths_to_repo):
        """0.2.1-W3-257：commit 訊息應標示實際操作名 resolve-spawn-request，
        不再誤標為 append-log（同一 auto-commit 薄封裝，僅 operation 參數不同）。"""
        repo = patch_paths_to_repo
        rc = _call_resolve("0.0.0-W0-SR", "SR-1", "processed", spawned_ticket=["0.0.0-W0-100"])
        assert rc == 0

        msg = _last_commit_message(repo)
        assert msg == "chore(0.0.0-W0-SR): resolve-spawn-request Spawn Requests", (
            f"commit message 應反映實際操作名 resolve-spawn-request，實得 '{msg}'"
        )

    def test_reset_hard_preserves_committed_status(self, patch_paths_to_repo):
        """auto-commit 後 reset --hard 仍保留狀態更新（與 append-log 同保護等級）。"""
        repo = patch_paths_to_repo
        md = repo / "tickets" / "0.0.0-W0-SR.md"

        rc = _call_resolve("0.0.0-W0-SR", "SR-1", "processed", spawned_ticket=["0.0.0-W0-100"])
        assert rc == 0

        _run_git(repo, "reset", "--hard", "HEAD")

        assert "processed（已建 0.0.0-W0-100）" in md.read_text(encoding="utf-8")
