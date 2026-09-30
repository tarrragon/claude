"""
check 依前移清單切換建議、release 遇前移清單拒絕（E1 對照測試）

同一 fixture 版本分別造前移清單空／非空：
- check 結尾建議 finish（非空）／release（空）
- release rc=1 且不進入後續流程（非空）／照常進入後續流程（空）
- --force 不覆蓋前移拒絕
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402

VERSION = "0.1.0"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ticket_md(ticket_id: str, status: str) -> str:
    return "\n".join([
        "---",
        f"id: {ticket_id}",
        "title: 測試票",
        "type: IMP",
        f"status: {status}",
        "---",
        "",
        "# Body",
    ])


def _make_project(tmp_path: Path, with_overflow: bool) -> Path:
    tickets_dir = (
        tmp_path / "docs" / "work-logs" / "v0" / "v0.1" / f"v{VERSION}" / "tickets"
    )
    _write(tickets_dir / f"{VERSION}-W1-001.md", _ticket_md(f"{VERSION}-W1-001", "completed"))
    if with_overflow:
        _write(tickets_dir / f"{VERSION}-W3-010.md", _ticket_md(f"{VERSION}-W3-010", "pending"))
    _write(tmp_path / "docs" / "todolist.yaml", "versions:\n  - version: 0.1.0\n  - version: 0.1.1\n")
    return tmp_path


def _run(tmp_path: Path, argv: list, capsys):
    """執行 main()，回傳 (rc, stdout, 被呼叫的後續步驟名稱集合)。"""
    reached = set()

    def _mark(name, value):
        def _fn(*_a, **_k):
            reached.add(name)
            return value
        return _fn

    with patch.object(vr, "get_project_root", return_value=tmp_path), \
         patch.object(vr, "print_config_disclosure"), \
         patch.object(vr, "check_version_frozen", return_value=(True, [])), \
         patch.object(vr, "preflight_check", return_value=(True, {})), \
         patch.object(vr, "snapshot_git_status_paths", return_value=set()), \
         patch.object(vr, "check_residual_after_finish", return_value=[]), \
         patch.object(vr, "update_documents", side_effect=_mark("update_documents", True)), \
         patch.object(vr, "git_merge_and_push", side_effect=_mark("git", True)), \
         patch.object(vr, "mark_version_completed", return_value=True), \
         patch.object(vr, "activate_next_planned_version", return_value=True), \
         patch.object(vr, "commit_changes", return_value=True), \
         patch.object(sys, "argv", ["version_release.py"] + argv):
        rc = vr.main()
    out = capsys.readouterr()
    return rc, out.out + out.err, reached


class TestCheckSuggestionSwitch:
    def test_check_suggests_finish_when_overflow_nonempty(self, tmp_path, capsys):
        _make_project(tmp_path, with_overflow=True)
        rc, out, _ = _run(tmp_path, ["check", "--version", VERSION], capsys)
        assert rc == 0
        assert "version_release.py finish" in out
        assert "version_release.py release" not in out
        assert "前移 1 張" in out

    def test_check_suggests_release_when_overflow_empty(self, tmp_path, capsys):
        _make_project(tmp_path, with_overflow=False)
        rc, out, _ = _run(tmp_path, ["check", "--version", VERSION], capsys)
        assert rc == 0
        assert "version_release.py release" in out
        assert "version_release.py finish" not in out


class TestReleaseOverflowRefusal:
    def test_release_refuses_when_overflow_nonempty(self, tmp_path, capsys):
        _make_project(tmp_path, with_overflow=True)
        rc, out, reached = _run(tmp_path, ["release", "--version", VERSION], capsys)
        assert rc == 1
        assert "finish" in out
        assert f"{VERSION}-W3-010" in out
        assert reached == set()

    def test_release_proceeds_when_overflow_empty(self, tmp_path, capsys):
        _make_project(tmp_path, with_overflow=False)
        rc, _out, reached = _run(tmp_path, ["release", "--version", VERSION], capsys)
        assert rc == 0
        assert "update_documents" in reached

    def test_force_does_not_override_overflow_refusal(self, tmp_path, capsys):
        _make_project(tmp_path, with_overflow=True)
        rc, _out, reached = _run(
            tmp_path, ["release", "--version", VERSION, "--force"], capsys
        )
        assert rc == 1
        assert reached == set()

    def test_finish_unaffected_by_release_guard(self, tmp_path, capsys):
        _make_project(tmp_path, with_overflow=True)
        with patch.object(vr, "migrate_overflow_tickets", return_value=True) as migrate:
            rc, _out, reached = _run(tmp_path, ["finish", "--version", VERSION], capsys)
        assert migrate.called
        assert rc == 0
        assert "update_documents" in reached
