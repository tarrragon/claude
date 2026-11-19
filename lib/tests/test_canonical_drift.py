#!/usr/bin/env python3
"""推送前比對 base 與 canonical HEAD：落後或 base 不在歷史中時警告，一律不阻擋。

四種情況：base == HEAD 不輸出；base 是祖先但 HEAD 已前進，警告並列出前進的
commit 數；base 不在 canonical 歷史中，警告；讀不到 base，印出原因。fixture 用
真實 git repo，「canonical 已前進」為正向對照，base == HEAD 為反向對照。
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.canonical_drift import describe_canonical_drift  # noqa: E402


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "canonical"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def test_base_equals_head_is_silent(tmp_path):
    repo = _repo(tmp_path)
    head = _commit(repo, "a")

    assert describe_canonical_drift(repo, head) == []


def test_canonical_advanced_warns_with_commit_count(tmp_path):
    repo = _repo(tmp_path)
    base = _commit(repo, "a")
    _commit(repo, "b")
    _commit(repo, "c")

    lines = describe_canonical_drift(repo, base)

    text = "\n".join(lines)
    assert lines and lines[0].startswith("[WARNING]")
    assert "2 個 commit" in text
    assert "sync-pull" in text


def test_base_not_in_canonical_history_warns(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, "a")
    unknown = "0123456789abcdef0123456789abcdef01234567"

    lines = describe_canonical_drift(repo, unknown)

    assert lines and lines[0].startswith("[WARNING]")
    assert "不在 canonical 歷史中" in "\n".join(lines)


def test_base_diverged_from_canonical_warns_not_in_history(tmp_path):
    repo = _repo(tmp_path)
    root = _commit(repo, "a")
    _git(repo, "checkout", "-q", "-b", "side")
    side = _commit(repo, "side")
    _git(repo, "checkout", "-q", "-")
    _git(repo, "reset", "-q", "--hard", root)
    _commit(repo, "b")

    lines = describe_canonical_drift(repo, side)

    assert lines and lines[0].startswith("[WARNING]")
    assert "不在 canonical 歷史中" in "\n".join(lines)


def test_missing_base_reports_reason_without_warning(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, "a")

    lines = describe_canonical_drift(repo, None)

    assert lines and lines[0].startswith("[INFO]")
    assert "last_synced_base_sha" in lines[0]


def test_unreadable_clone_reports_reason(tmp_path):
    not_a_repo = tmp_path / "empty"
    not_a_repo.mkdir()

    lines = describe_canonical_drift(not_a_repo, "0123456789abcdef0123456789abcdef01234567")

    assert lines and lines[0].startswith("[INFO]")
