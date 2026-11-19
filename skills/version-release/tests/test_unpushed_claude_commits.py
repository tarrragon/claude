"""version-release check 列出未推送的 .claude/ commit 數（資訊，不阻擋）。

判準與框架 lib 的 unpushed_claude_commits 相同：錨點為最後一次寫入
.claude/sync-base.json 的 commit，計數為其後動到 .claude/ 的非 merge commit。
0 與非 0 互為對照；另驗證不影響 preflight 的通過判定。
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


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


def test_counts_commits_after_sync_base(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/sync-base.json", "{}")
    _commit(repo, ".claude/a.md", "a")
    _commit(repo, "docs/x.md", "x")
    _commit(repo, ".claude/b.md", "b")

    line = vr.describe_unpushed_claude_commits(repo)

    assert "2 個" in line
    assert "consumer 尚未取得" in line


def test_zero_right_after_sync_base(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/a.md", "a")
    _commit(repo, ".claude/sync-base.json", "{}")

    assert "0 個" in vr.describe_unpushed_claude_commits(repo)


def test_missing_sync_base_reports_reason(tmp_path):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/a.md", "a")

    assert "無法計算" in vr.describe_unpushed_claude_commits(repo)


def test_preflight_prints_line_and_does_not_gate(tmp_path, capsys):
    repo = _repo(tmp_path)
    _commit(repo, ".claude/sync-base.json", "{}")
    _commit(repo, ".claude/a.md", "a")
    ok = (True, [])
    with patch.object(vr, "get_project_root", return_value=repo), \
         patch.object(vr, "check_worklog_completed", return_value=ok), \
         patch.object(vr, "check_technical_debt_status",
                      return_value={"passed": True, "message": "ok", "pending_tds": []}), \
         patch.object(vr, "check_technical_debt", return_value=ok), \
         patch.object(vr, "check_previous_versions_completed", return_value=ok), \
         patch.object(vr, "check_stale_active_versions", return_value=ok), \
         patch.object(vr, "check_version_sync", return_value=ok), \
         patch.object(vr, "check_placeholder_implementations", return_value=ok):
        all_ok, _ = vr.preflight_check("9.9.9")

    assert all_ok is True
    assert "1 個" in capsys.readouterr().out
