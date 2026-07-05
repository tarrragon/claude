"""1.5.0-W5-021 — set-exit-status / set-completion-info CLI 化測試。

依制式化內容生成方法論：Exit Status / Completion Info 有確定性 schema，
改由 CLI 生成結構，agent 只提供語意值。本檔驗證：
1. 內容組出符合 schema 的格式（fenced YAML / Markdown 欄位）
2. 透過 execute_append_log 委派機制正確寫入 ticket body（含 placeholder 替換）
3. 輸入驗證（枚舉值 / confidence 範圍）
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from ticket_system.lib.parser import parse_frontmatter


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=False
    )


def _write_ticket_md(path: Path, tid: str) -> None:
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
        "## Exit Status\n\n"
        "<!-- 代理人結束時以 YAML 格式回報 -->\n\n"
        "---\n\n"
        "## Completion Info\n\n"
        "**Completion Time**: (pending)\n"
        "**Executing Agent**: thyme-python-developer\n"
        "**Review Status**: pending\n"
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
    tid = "0.0.0-W0-SB"
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
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
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


def _md_text(repo: Path) -> str:
    return (repo / "tickets" / "0.0.0-W0-SB.md").read_text(encoding="utf-8")


# ============================================================
# set-exit-status
# ============================================================


class TestSetExitStatus:
    def test_writes_fenced_yaml_with_semantic_values(self, patch_paths_to_repo):
        from ticket_system.commands.track_structured_body import execute_set_exit_status

        args = argparse.Namespace(
            ticket_id="0.0.0-W0-SB",
            status="success",
            reason="全部測試通過",
            confidence="0.95",
            acceptance_met=["1", "2"],
            acceptance_unmet=None,
            artifacts=["path/to/file.py"],
            force=False,
        )
        rc = execute_set_exit_status(args, "0.0.0")
        assert rc == 0

        text = _md_text(patch_paths_to_repo)
        assert "```yaml" in text
        assert "exit_status: success" in text
        assert 'reason: "全部測試通過"' in text
        assert "confidence: 0.95" in text
        assert "acceptance_met: [1, 2]" in text
        assert "acceptance_unmet: []" in text
        assert 'artifacts: ["path/to/file.py"]' in text

    def test_rejects_invalid_status_enum(self, patch_paths_to_repo):
        from ticket_system.commands.track_structured_body import execute_set_exit_status

        args = argparse.Namespace(
            ticket_id="0.0.0-W0-SB",
            status="not_a_real_status",
            reason="",
            confidence="1.0",
            acceptance_met=None,
            acceptance_unmet=None,
            artifacts=None,
            force=False,
        )
        rc = execute_set_exit_status(args, "0.0.0")
        assert rc == 1

    def test_rejects_confidence_out_of_range(self, patch_paths_to_repo):
        from ticket_system.commands.track_structured_body import execute_set_exit_status

        args = argparse.Namespace(
            ticket_id="0.0.0-W0-SB",
            status="success",
            reason="",
            confidence="1.5",
            acceptance_met=None,
            acceptance_unmet=None,
            artifacts=None,
            force=False,
        )
        rc = execute_set_exit_status(args, "0.0.0")
        assert rc == 1

    def test_rejects_confidence_non_numeric(self, patch_paths_to_repo):
        from ticket_system.commands.track_structured_body import execute_set_exit_status

        args = argparse.Namespace(
            ticket_id="0.0.0-W0-SB",
            status="success",
            reason="",
            confidence="high",
            acceptance_met=None,
            acceptance_unmet=None,
            artifacts=None,
            force=False,
        )
        rc = execute_set_exit_status(args, "0.0.0")
        assert rc == 1


# ============================================================
# set-completion-info
# ============================================================


class TestSetCompletionInfo:
    def test_writes_completion_info_with_semantic_values(self, patch_paths_to_repo):
        from ticket_system.commands.track_structured_body import execute_set_completion_info

        args = argparse.Namespace(
            ticket_id="0.0.0-W0-SB",
            agent="thyme-python-developer",
            review_status="reviewed",
            summary="新增 set-exit-status / set-completion-info 子命令",
            force=False,
        )
        rc = execute_set_completion_info(args, "0.0.0")
        assert rc == 0

        text = _md_text(patch_paths_to_repo)
        assert "**Executing Agent**: thyme-python-developer" in text
        assert "**Review Status**: reviewed" in text
        assert "**Summary**: 新增 set-exit-status / set-completion-info 子命令" in text
        # placeholder 應被替換而非重複 append
        assert text.count("**Executing Agent**") == 1

    def test_rejects_invalid_review_status_enum(self, patch_paths_to_repo):
        from ticket_system.commands.track_structured_body import execute_set_completion_info

        args = argparse.Namespace(
            ticket_id="0.0.0-W0-SB",
            agent="thyme-python-developer",
            review_status="not_valid",
            summary="",
            force=False,
        )
        rc = execute_set_completion_info(args, "0.0.0")
        assert rc == 1

    def test_default_review_status_is_pending(self, patch_paths_to_repo):
        from ticket_system.commands.track_structured_body import execute_set_completion_info

        args = argparse.Namespace(
            ticket_id="0.0.0-W0-SB",
            agent="thyme-python-developer",
            summary="",
            force=False,
        )
        rc = execute_set_completion_info(args, "0.0.0")
        assert rc == 0
        text = _md_text(patch_paths_to_repo)
        assert "**Review Status**: pending" in text
