"""version_release 讀取 git status 路徑的 CJK 檔名 E2（tarrragon/claude#111）。"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _init(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "seed.txt").write_text("s", encoding="utf-8")
    _git(tmp_path, "add", "seed.txt")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def test_snapshot_paths_returns_raw_cjk_and_ascii(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    (repo / "中文.md").write_text("x", encoding="utf-8")
    (repo / "plain.md").write_text("x", encoding="utf-8")
    paths = vr.snapshot_git_status_paths(repo)
    assert "中文.md" in paths
    assert "plain.md" in paths


def test_snapshot_paths_rename_both_sides(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    (repo / "舊.md").write_text("content body", encoding="utf-8")
    _git(repo, "add", "舊.md")
    _git(repo, "commit", "-q", "-m", "old")
    _git(repo, "mv", "舊.md", "新.md")
    paths = vr.snapshot_git_status_paths(repo)
    assert {"舊.md", "新.md"} <= paths


def test_commit_changes_includes_cjk_docs(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    # docs/ 內先有已追蹤檔，新檔才會以逐檔而非整目錄形式出現在 status
    (repo / "docs").mkdir()
    (repo / "docs" / "seed.md").write_text("s", encoding="utf-8")
    _git(repo, "add", "docs/seed.md")
    _git(repo, "commit", "-q", "-m", "docs seed")
    baseline = vr.snapshot_git_status_paths(repo)
    (repo / "docs" / "中文.md").write_text("x", encoding="utf-8")
    with patch.object(vr, "get_project_root", return_value=repo):
        assert vr.commit_changes("0.1.0", baseline=baseline) is True
    assert "docs/中文.md" in _git(repo, "-c", "core.quotepath=false", "ls-files")
    assert _git(repo, "status", "--porcelain").strip() == ""


def test_commit_changes_warns_when_git_add_fails(tmp_path: Path, capsys) -> None:
    repo = _init(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "seed.md").write_text("s", encoding="utf-8")
    _git(repo, "add", "docs/seed.md")
    _git(repo, "commit", "-q", "-m", "docs seed")
    (repo / "docs" / "a.md").write_text("x", encoding="utf-8")
    real_run = subprocess.run

    def fake_run(cmd, *a, **kw):
        if cmd[:2] == ["git", "add"]:
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        return real_run(cmd, *a, **kw)

    with patch.object(vr, "get_project_root", return_value=repo), patch.object(
        vr.subprocess, "run", side_effect=fake_run
    ):
        vr.commit_changes("0.1.0", baseline=set())
    out = capsys.readouterr()
    assert "docs/a.md" in (out.out + out.err)
    assert "git add" in (out.out + out.err)
