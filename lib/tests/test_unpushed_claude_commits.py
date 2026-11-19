#!/usr/bin/env python3
"""未推送的 .claude/ commit 數：以最後一次修改 sync-base.json 的 commit 為錨點計數。

錨點是本地 git 中最後一次寫入 `.claude/sync-base.json` 的 commit（push 或 pull
後都會 commit 這個檔），計數是錨點之後、動到 `.claude/` 的非 merge commit，不含
sync-base.json 本身。fixture 用真實 git repo；0 與非 0 互為對照。
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.unpushed_claude_commits import (  # noqa: E402
    count_unpushed_claude_commits,
    format_unpushed_line,
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "proj"
    (repo / ".claude").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _commit(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", rel)


def test_zero_when_nothing_after_anchor(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/rules.md", "a")
    _commit(repo, ".claude/sync-base.json", '{"last_synced_base_sha": "x"}')

    result = count_unpushed_claude_commits(repo)

    assert result.count == 0
    assert result.anchor is not None


def test_counts_claude_commits_after_anchor_only(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/rules.md", "a")
    _commit(repo, ".claude/sync-base.json", '{"last_synced_base_sha": "x"}')
    _commit(repo, ".claude/rules.md", "b")
    _commit(repo, "docs/notes.md", "outside .claude")
    _commit(repo, ".claude/hooks/h.py", "c")

    result = count_unpushed_claude_commits(repo)

    assert result.count == 2


def test_sync_base_rewrite_moves_anchor(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/sync-base.json", '{"last_synced_base_sha": "x"}')
    _commit(repo, ".claude/rules.md", "b")
    _commit(repo, ".claude/sync-base.json", '{"last_synced_base_sha": "y"}')

    assert count_unpushed_claude_commits(repo).count == 0


def test_missing_anchor_reports_reason(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/rules.md", "a")

    result = count_unpushed_claude_commits(repo)

    assert result.count is None
    assert "sync-base.json" in result.reason


def test_not_a_repo_reports_reason(tmp_path):
    result = count_unpushed_claude_commits(tmp_path)

    assert result.count is None
    assert result.reason


def test_format_line_nonzero_and_zero_and_unknown(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/sync-base.json", "{}")
    _commit(repo, ".claude/rules.md", "b")
    nonzero = format_unpushed_line(count_unpushed_claude_commits(repo))
    assert "1 個" in nonzero and "consumer 尚未取得" in nonzero

    _commit(repo, ".claude/sync-base.json", "{ }")
    zero = format_unpushed_line(count_unpushed_claude_commits(repo))
    assert "0 個" in zero

    unknown = format_unpushed_line(count_unpushed_claude_commits(tmp_path / "nope"))
    assert "無法計算" in unknown
