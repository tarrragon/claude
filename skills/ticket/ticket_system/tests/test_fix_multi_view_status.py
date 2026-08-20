"""fix-multi-view-status CLI 子命令測試。

背景：ANA Ticket Solution 區段的 multi_view_status 行一旦寫入非法值即無
合法途徑修正。本檔驗證：

1. 合法新值原地覆寫該行，reason 有效時通過
2. 非法新值拒絕寫入
3. 命中 0 行 / 多重命中一律拒絕寫入
4. 覆寫僅動 multi_view_status 該行，章節其他內容逐字元不變
5. 寫入後自動 commit（path-limited），與 add-exempt-marker 同保護等級
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )


_SOLUTION_SECTION = """## Solution
第一行說明。
multi_view_status: single-view-completed（非法值示範）
最後一行結尾。
"""

_SOLUTION_SECTION_NO_FIELD = """## Solution
第一行說明。
最後一行結尾，沒有 multi_view_status 行。
"""

_SOLUTION_SECTION_DUP_FIELD = """## Solution
multi_view_status: single-view-completed
第一行說明。
multi_view_status: another-bad-value
最後一行結尾。
"""


def _write_ticket_md(path: Path, tid: str, section: str = _SOLUTION_SECTION, status: str = "completed") -> None:
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        "type: ANA\n"
        f"status: {status}\n"
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
        f"{section}\n"
        "---\n\n"
        "## Test Results\n"
        "placeholder.\n\n"
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
    tid = "0.0.0-W0-MVS"
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

    from ticket_system.commands import track_multi_view_status as mvs_mod
    from ticket_system.lib import ticket_loader

    for mod in (mvs_mod, ticket_loader):
        monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
        monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)

    return git_repo


def _write_custom_section(repo: Path, section: str, status: str = "completed") -> None:
    tid = "0.0.0-W0-MVS"
    md_path = repo / "tickets" / f"{tid}.md"
    _write_ticket_md(md_path, tid, section=section, status=status)


def _call(
    ticket_id: str,
    section: str = "Solution",
    value: str = "skipped",
    reason: str = "修正為合法值並附上足夠長度的理由",
    force: bool = False,
    match_text: str | None = None,
) -> int:
    from ticket_system.commands.track_multi_view_status import execute_fix_multi_view_status

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        section=section,
        value=value,
        reason=reason,
        force=force,
        match_text=match_text,
    )
    return execute_fix_multi_view_status(ns, "0.0.0")


def _read_md(repo: Path, tid: str = "0.0.0-W0-MVS") -> str:
    return (repo / "tickets" / f"{tid}.md").read_text(encoding="utf-8")


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


# ============================================================
# AC1: 合法覆寫
# ============================================================


class TestOverwriteValidValue:
    def test_valid_value_overwrites_line_in_place(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call("0.0.0-W0-MVS", value="skipped")
        assert rc == 0

        content = _read_md(repo)
        assert "multi_view_status: skipped" in content
        assert "single-view-completed" not in content

    def test_overwrite_preserves_line_count(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before_count = len(_read_md(repo).splitlines())
        rc = _call("0.0.0-W0-MVS", value="n_a")
        assert rc == 0
        after_count = len(_read_md(repo).splitlines())
        assert after_count == before_count


# ============================================================
# AC2: 非法值拒絕
# ============================================================


class TestInvalidValueRejected:
    def test_invalid_value_rejects_without_write(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        # 繞過 argparse choices（模擬呼叫端直接呼叫函式），驗證函式本身防禦
        import argparse as _argparse
        from ticket_system.commands.track_multi_view_status import execute_fix_multi_view_status

        ns = _argparse.Namespace(
            ticket_id="0.0.0-W0-MVS",
            section="Solution",
            value="not-a-real-value",
            reason="修正為合法值並附上足夠長度的理由",
            force=False,
        )
        rc = execute_fix_multi_view_status(ns, "0.0.0")
        assert rc == 1
        assert _read_md(repo) == before

    def test_reason_required_and_too_short_rejects(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-MVS", value="skipped", reason="太短")
        assert rc == 1
        assert _read_md(repo) == before

    def test_reason_empty_rejects(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-MVS", value="skipped", reason="")
        assert rc == 1
        assert _read_md(repo) == before


# ============================================================
# AC3: 目標行不存在 / 多重命中
# ============================================================


class TestLocatePattern:
    def test_field_not_found_rejects(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _write_custom_section(repo, _SOLUTION_SECTION_NO_FIELD)
        before = _read_md(repo)
        rc = _call("0.0.0-W0-MVS")
        assert rc == 1
        assert _read_md(repo) == before

    def test_multiple_field_lines_rejects(self, patch_paths_to_repo, capsys):
        repo = patch_paths_to_repo
        _write_custom_section(repo, _SOLUTION_SECTION_DUP_FIELD)
        before = _read_md(repo)
        rc = _call("0.0.0-W0-MVS")
        assert rc == 1
        assert _read_md(repo) == before
        out = capsys.readouterr().out
        assert "定位不明確" in out

    def test_section_not_found_rejects(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-MVS", section="Test Results")
        assert rc == 1
        assert _read_md(repo) == before

    def test_match_narrows_multiple_hits_to_target_line(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _write_custom_section(repo, _SOLUTION_SECTION_DUP_FIELD)
        rc = _call("0.0.0-W0-MVS", value="skipped", match_text="single-view-completed")
        assert rc == 0
        content = _read_md(repo)
        assert "multi_view_status: another-bad-value" in content
        assert "single-view-completed" not in content

    def test_match_still_ambiguous_rejects(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _write_custom_section(repo, _SOLUTION_SECTION_DUP_FIELD)
        before = _read_md(repo)
        rc = _call("0.0.0-W0-MVS", value="skipped", match_text="multi_view_status")
        assert rc == 1
        assert _read_md(repo) == before


# ============================================================
# AC4: 僅覆寫該行，其他內容不變
# ============================================================


class TestOnlyTargetLineChanged:
    def test_other_lines_survive_byte_for_byte(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before_lines = _read_md(repo).splitlines()
        rc = _call("0.0.0-W0-MVS", value="reviewed", reason="改為已審查並附上足夠長度理由")
        assert rc == 0

        after_lines = _read_md(repo).splitlines()
        target_before = [l for l in before_lines if "multi_view_status" in l][0]
        for line in before_lines:
            if line == target_before:
                continue
            assert line in after_lines


# ============================================================
# 自動 commit（與 add-exempt-marker 同保護等級）
# ============================================================


class TestAutoCommit:
    def test_write_creates_new_commit(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _commit_count(repo)
        rc = _call("0.0.0-W0-MVS", value="skipped")
        assert rc == 0
        assert _commit_count(repo) == before + 1

    def test_failed_write_creates_no_commit(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _commit_count(repo)
        rc = _call("0.0.0-W0-MVS", value="skipped", reason="太短")
        assert rc == 1
        assert _commit_count(repo) == before


# ============================================================
# status precondition（completed 狀態預設允許，pending 需要 --force）
# ============================================================


class TestStatusPrecondition:
    def test_completed_status_allowed_without_force(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _write_custom_section(repo, _SOLUTION_SECTION, status="completed")
        rc = _call("0.0.0-W0-MVS", value="skipped")
        assert rc == 0

    def test_pending_status_rejected_without_force(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _write_custom_section(repo, _SOLUTION_SECTION, status="pending")
        before = _read_md(repo)
        rc = _call("0.0.0-W0-MVS", value="skipped")
        assert rc == 2
        assert _read_md(repo) == before

    def test_pending_status_allowed_with_force(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        _write_custom_section(repo, _SOLUTION_SECTION, status="pending")
        rc = _call("0.0.0-W0-MVS", value="skipped", force=True)
        assert rc == 0
