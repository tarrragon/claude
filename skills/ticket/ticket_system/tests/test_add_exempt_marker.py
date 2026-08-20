"""add-exempt-marker CLI 子命令測試。

背景：自由撰寫章節（Solution / Test Results / NeedsContext 等）以
append-log 寫入後即無法修改。本檔驗證：

1. --match 命中恰好一行時，於該行前插入獨立 marker 行
2. 原文字逐字元不變（僅追加，不修改）
3. 0 命中 / 多重命中一律拒絕寫入
4. marker 格式驗證與 phase4-decision-enforcement-hook 同規則
5. 寫入後自動 commit（path-limited），與 append-log / resolve-spawn-request 同保護等級
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
Phase 5 再決定要不要快取。
另一行也提到 Phase 5 再決定的內容。
最後一行結尾。
"""


def _write_ticket_md(path: Path, tid: str, section: str = _SOLUTION_SECTION) -> None:
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
    tid = "0.0.0-W0-EXM"
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

    from ticket_system.commands import track_exempt_marker as tem_mod
    from ticket_system.lib import ticket_loader

    for mod in (tem_mod, ticket_loader):
        monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
        monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)

    return git_repo


def _call(
    ticket_id: str,
    section: str = "Solution",
    match_text: str = "第一行說明",
    category: str = "user-override",
    reason: str = "用戶明確裁示保留現狀",
    force: bool = False,
) -> int:
    from ticket_system.commands.track_exempt_marker import execute_add_exempt_marker

    ns = argparse.Namespace(
        ticket_id=ticket_id,
        section=section,
        match_text=match_text,
        category=category,
        reason=reason,
        force=force,
    )
    return execute_add_exempt_marker(ns, "0.0.0")


def _read_md(repo: Path, tid: str = "0.0.0-W0-EXM") -> str:
    return (repo / "tickets" / f"{tid}.md").read_text(encoding="utf-8")


def _commit_count(repo: Path) -> int:
    result = _run_git(repo, "rev-list", "--count", "HEAD")
    return int(result.stdout.strip())


# ============================================================
# AC1: 單一命中時插入 marker；0 命中 / 多重命中拒絕寫入
# ============================================================


class TestLocateAndInsert:
    def test_single_match_inserts_marker_before_line(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call("0.0.0-W0-EXM", match_text="第一行說明")
        assert rc == 0

        content = _read_md(repo)
        lines = content.splitlines()
        marker_idx = next(i for i, l in enumerate(lines) if "PC-093-exempt" in l)
        target_idx = next(i for i, l in enumerate(lines) if "第一行說明" in l)
        assert marker_idx == target_idx - 1
        assert "<!-- PC-093-exempt: user-override:用戶明確裁示保留現狀 -->" in lines[marker_idx]

    def test_zero_match_rejects_without_write(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", match_text="根本不存在的字串")
        assert rc == 1
        assert _read_md(repo) == before

    def test_multiple_match_rejects_and_lists_candidates(self, patch_paths_to_repo, capsys):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", match_text="Phase 5 再決定")
        assert rc == 1
        assert _read_md(repo) == before
        out = capsys.readouterr().out
        assert "定位不明確" in out
        assert out.count("Phase 5 再決定") >= 2

    def test_invalid_section_rejects(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", section="NotASection")
        assert rc == 1
        assert _read_md(repo) == before

    def test_section_not_found_rejects(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", section="Problem Analysis")
        assert rc == 1
        assert _read_md(repo) == before

    def test_match_text_with_curly_braces_does_not_crash(self, patch_paths_to_repo):
        # match_text 含字面 `{` 曾因誤經 str.format() 路徑拋 KeyError（回歸測試）
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", match_text="{not-a-format-field}")
        assert rc == 1
        assert _read_md(repo) == before


# ============================================================
# AC2: 僅追加，原文字逐字元不變
# ============================================================


class TestOriginalTextUnchanged:
    def test_original_lines_survive_byte_for_byte(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before_lines = set(_read_md(repo).splitlines())
        rc = _call("0.0.0-W0-EXM", match_text="最後一行結尾")
        assert rc == 0

        after_lines = _read_md(repo).splitlines()
        # 原本每一行都必須逐字元存在於新內容中（僅新增一行 marker，不改動既有行）
        for line in before_lines:
            assert line in after_lines

    def test_only_one_new_line_added(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before_count = len(_read_md(repo).splitlines())
        rc = _call("0.0.0-W0-EXM", match_text="最後一行結尾")
        assert rc == 0
        after_count = len(_read_md(repo).splitlines())
        assert after_count == before_count + 1


# ============================================================
# AC3: marker 格式驗證
# ============================================================


class TestMarkerValidation:
    def test_reason_too_short_rejects(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", category="user-override", reason="太短")
        assert rc == 1
        assert _read_md(repo) == before

    def test_baseline_gated_requires_number(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", category="baseline-gated", reason="沒有量化數字的理由說明")
        assert rc == 1
        assert _read_md(repo) == before

    def test_baseline_gated_with_number_passes(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call("0.0.0-W0-EXM", category="baseline-gated", reason="測量結果 84ms 低於門檻")
        assert rc == 0

    def test_ticket_tracked_requires_ticket_id(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", category="ticket-tracked", reason="沒有票號的延後理由說明")
        assert rc == 1
        assert _read_md(repo) == before

    def test_ticket_tracked_with_id_passes(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call("0.0.0-W0-EXM", category="ticket-tracked", reason="W17-085 hook 訊息改善")
        assert rc == 0

    def test_rule_quote_requires_path(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", category="rule-quote", reason="引用某規則但沒有給路徑喔")
        assert rc == 1
        assert _read_md(repo) == before

    def test_rule_quote_with_path_passes(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call(
            "0.0.0-W0-EXM",
            category="rule-quote",
            reason="引用 .claude/rules/core/decision-trigger-binding.md 規則 1.5",
        )
        assert rc == 0

    def test_history_requires_ticket_id(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _read_md(repo)
        rc = _call("0.0.0-W0-EXM", category="history", reason="這是一段歷史脈絡說明但沒有票號")
        assert rc == 1
        assert _read_md(repo) == before

    def test_history_with_ticket_id_passes(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        rc = _call("0.0.0-W0-EXM", category="history", reason="引用 W11-004 多視角審查發現作動機脈絡")
        assert rc == 0

    def test_invalid_category_rejected_by_argparse_layer(self):
        # CLI 層以 argparse choices 攔截，命令函式本身也應防禦（呼叫端繞過 argparse 時）
        from ticket_system.lib.exempt_marker import validate_exempt_fields, resolve_ticket_id_pattern

        ok, err = validate_exempt_fields(
            "not-a-real-category", "隨便一個超過十字元的理由文字",
            ticket_id_pattern=resolve_ticket_id_pattern(),
        )
        assert ok is False
        assert err == "category-whitelist"


# ============================================================
# 自動 commit（與 append-log / resolve-spawn-request 同保護等級）
# ============================================================


class TestAutoCommit:
    def test_write_creates_new_commit(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _commit_count(repo)
        rc = _call("0.0.0-W0-EXM", match_text="最後一行結尾")
        assert rc == 0
        assert _commit_count(repo) == before + 1

    def test_failed_write_creates_no_commit(self, patch_paths_to_repo):
        repo = patch_paths_to_repo
        before = _commit_count(repo)
        rc = _call("0.0.0-W0-EXM", match_text="根本不存在的字串")
        assert rc == 1
        assert _commit_count(repo) == before
