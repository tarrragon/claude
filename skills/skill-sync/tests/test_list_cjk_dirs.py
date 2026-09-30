"""skill-sync cmd_list 讀取發佈庫目錄清單的 CJK 名稱 E2（tarrragon/claude#111）。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill_sync.cli import cmd_list  # noqa: E402


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "core.quotepath=true", *args],
        cwd=cwd, capture_output=True, text=True, check=True,
    )


def _make_publish_repo(root: Path, names: list[str]) -> Path:
    repo = root / "publish"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "uploadpack.allowFilter", "true")
    for name in names:
        (repo / name).mkdir()
        (repo / name / "SKILL.md").write_text(f"# t\n\n{name} 說明\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def test_cmd_list_shows_cjk_and_ascii_skill_dirs(tmp_path, monkeypatch, capsys) -> None:
    repo = _make_publish_repo(tmp_path, ["plain-skill", "中文技能"])
    monkeypatch.setenv("SKILL_SYNC_REPO", f"file://{repo}")
    cmd_list(argparse.Namespace())
    out = capsys.readouterr().out
    assert "plain-skill" in out
    assert "中文技能" in out
    assert "中文技能 說明" not in out or "說明" in out
    assert "\\344" not in out  # 未出現八進位跳脫殘影
