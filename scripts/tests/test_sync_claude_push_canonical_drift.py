#!/usr/bin/env python3
"""sync-claude-push 接線：base 讀自工作區 sync-base.json，與 clone 的 HEAD 比對後印出。

判斷邏輯本身的四種情況在 lib/tests/test_canonical_drift.py；本檔只驗接線：
讀到的 base 是 sync-base.json 記錄的值，canonical 前進時印警告，一致時不印。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_drift", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_drift"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _canonical(tmp_path: Path, commits: int) -> tuple[Path, list[str]]:
    repo = tmp_path / "clone"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    shas = []
    for i in range(commits):
        (repo / f"f{i}").write_text(str(i), encoding="utf-8")
        _git(repo, "add", f"f{i}")
        _git(repo, "commit", "-q", "-m", f"c{i}")
        shas.append(_git(repo, "rev-parse", "HEAD"))
    return repo, shas


def _project(tmp_path: Path, base_sha: str) -> Path:
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    sync_mod.write_base_sha(project / ".claude", base_sha)
    return project


def test_push_reports_canonical_advanced(tmp_path, capsys):
    clone, shas = _canonical(tmp_path, 3)
    project = _project(tmp_path, shas[0])

    sync_mod._report_canonical_drift(project, clone)

    out = capsys.readouterr().out
    assert "[WARNING]" in out
    assert "2 個 commit" in out


def test_push_silent_when_base_matches_head(tmp_path, capsys):
    clone, shas = _canonical(tmp_path, 2)
    project = _project(tmp_path, shas[-1])

    sync_mod._report_canonical_drift(project, clone)

    assert "[WARNING]" not in capsys.readouterr().out


def test_push_reports_reason_when_base_missing(tmp_path, capsys):
    clone, _ = _canonical(tmp_path, 1)
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)

    sync_mod._report_canonical_drift(project, clone)

    out = capsys.readouterr().out
    assert "[INFO]" in out
    assert "[WARNING]" not in out
