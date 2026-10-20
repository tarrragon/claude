"""
worktree merge 新入口測試（0.5.0-W1-266）：--branch、合併前驗收、落後 base 提示。

以 tmp repo 實跑 cmd_merge，不 mock merge_branch_cas。
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import worktree_manager as wm  # noqa: E402
import merge_cas as mc  # noqa: E402

AGENT_BRANCH = "worktree-agent-abc123"
A_LINES = [f"line{i}\n" for i in range(1, 11)]


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def commit_file(repo, name, text, msg):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-m", msg)


def line_edit(lineno, text):
    lines = list(A_LINES)
    lines[lineno - 1] = text + "\n"
    return "".join(lines)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_sleep", lambda _s: None)
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    commit_file(r, "a.txt", "".join(A_LINES), "base a")
    monkeypatch.chdir(r)
    monkeypatch.setattr(wm, "get_project_root", lambda: str(r))
    monkeypatch.setattr(wm, "get_worktree_list", lambda: [])
    return r


def make_branch(repo, name, text):
    git(repo, "checkout", "-b", name)
    commit_file(repo, "a.txt", text, "agent edit")
    git(repo, "checkout", "main")


class TestBranchEntry:
    def test_merge_agent_branch_by_name(self, repo):
        make_branch(repo, AGENT_BRANCH, line_edit(9, "agent9"))

        assert wm.cmd_merge(None, branch=AGENT_BRANCH) == 0
        assert (repo / "a.txt").read_text().splitlines()[8] == "agent9"

    def test_unknown_branch_blocked(self, repo):
        before = git(repo, "rev-parse", "HEAD")

        assert wm.cmd_merge(None, branch="worktree-agent-nope") == 1
        assert git(repo, "rev-parse", "HEAD") == before


class TestPreAcceptance:
    @pytest.fixture
    def ticket_wt(self, repo, monkeypatch):
        make_branch(repo, "feat/0.1.1-W9-002", line_edit(9, "t9"))
        monkeypatch.setattr(
            wm, "get_worktree_list",
            lambda: [{"path": str(repo), "branch": "feat/0.1.1-W9-002"}],
        )
        monkeypatch.setattr(wm, "_query_ticket_status", lambda _t: "in_progress")

    def test_incomplete_ticket_blocked_without_flag(self, repo, ticket_wt):
        before = git(repo, "rev-parse", "HEAD")

        assert wm.cmd_merge("0.1.1-W9-002") == 1
        assert git(repo, "rev-parse", "HEAD") == before

    def test_incomplete_ticket_merges_with_flag_and_logs(self, repo, ticket_wt):
        assert wm.cmd_merge("0.1.1-W9-002", pre_acceptance_reason="hook 須合併後驗收") == 0
        log = (repo / ".claude" / "logs" / "worktree-merge.log").read_text()
        assert "hook 須合併後驗收" in log and "0.1.1-W9-002" in log


class TestBehindBase:
    def test_behind_without_conflict_merges(self, repo, capsys):
        make_branch(repo, AGENT_BRANCH, line_edit(9, "agent9"))
        commit_file(repo, "a.txt", line_edit(1, "main1"), "main moves on")

        assert wm.cmd_merge(None, branch=AGENT_BRANCH) == 0
        assert "落後" in capsys.readouterr().out
        merged = (repo / "a.txt").read_text().splitlines()
        assert merged[0] == "main1" and merged[8] == "agent9"

    def test_behind_with_conflict_aborts_ref_unchanged(self, repo):
        make_branch(repo, AGENT_BRANCH, line_edit(5, "agent5"))
        commit_file(repo, "a.txt", line_edit(5, "main5"), "main conflicting")
        before = git(repo, "rev-parse", "HEAD")

        assert wm.cmd_merge(None, branch=AGENT_BRANCH) == 1
        assert git(repo, "rev-parse", "HEAD") == before
        assert not (repo / ".git" / "MERGE_HEAD").exists()


class TestMergeMessage:
    """合併 commit 訊息可指定；指定與不指定的訊息必須不同（對照），多行與 trailer 完整保留。"""

    def _body(self, repo):
        return git(repo, "log", "-1", "--format=%B", "main")

    def test_default_message_unchanged(self, repo):
        make_branch(repo, AGENT_BRANCH, line_edit(9, "agent9"))

        assert wm.cmd_merge(None, branch=AGENT_BRANCH) == 0
        assert self._body(repo) == f"Merge branch '{AGENT_BRANCH}'"

    def test_message_overrides_default(self, repo):
        make_branch(repo, AGENT_BRANCH, line_edit(9, "agent9"))

        assert wm.cmd_merge(None, branch=AGENT_BRANCH, message="merge(0.1.1-W9-002): 補測試") == 0
        assert self._body(repo) == "merge(0.1.1-W9-002): 補測試"

    def test_ticket_composes_default_message_with_branch(self, repo):
        make_branch(repo, AGENT_BRANCH, line_edit(9, "agent9"))

        assert wm.cmd_merge(None, branch=AGENT_BRANCH, ticket="0.1.1-W9-002") == 0
        assert self._body(repo) == f"Merge branch '{AGENT_BRANCH}' (0.1.1-W9-002)"

    def test_ticket_id_target_default_message_carries_id(self, repo, monkeypatch):
        make_branch(repo, "feat/0.1.1-W9-002", line_edit(9, "t9"))
        monkeypatch.setattr(
            wm, "get_worktree_list",
            lambda: [{"path": str(repo), "branch": "feat/0.1.1-W9-002"}],
        )
        monkeypatch.setattr(wm, "_query_ticket_status", lambda _t: "completed")

        assert wm.cmd_merge("0.1.1-W9-002") == 0
        assert self._body(repo) == "Merge branch 'feat/0.1.1-W9-002' (0.1.1-W9-002)"

    def test_message_wins_over_ticket(self, repo):
        make_branch(repo, AGENT_BRANCH, line_edit(9, "agent9"))

        assert wm.cmd_merge(None, branch=AGENT_BRANCH, ticket="0.1.1-W9-002", message="custom") == 0
        assert self._body(repo) == "custom"

    def test_multiline_message_with_trailer_preserved(self, repo):
        make_branch(repo, AGENT_BRANCH, line_edit(9, "agent9"))
        msg = (
            "merge(0.1.1-W9-002): 標題\n\n第二段說明\n第三行\n\n"
            "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_x"
        )

        assert wm.cmd_merge(None, branch=AGENT_BRANCH, message=msg) == 0
        assert self._body(repo) == msg

    def test_cli_parses_message_and_ticket(self, repo, monkeypatch):
        make_branch(repo, AGENT_BRANCH, line_edit(9, "agent9"))
        monkeypatch.setattr(
            sys, "argv",
            ["wm", "merge", "--branch", AGENT_BRANCH, "--ticket", "0.1.1-W9-002", "--message", "m1\n\nbody"],
        )

        assert wm.main() == 0
        assert self._body(repo) == "m1\n\nbody"
