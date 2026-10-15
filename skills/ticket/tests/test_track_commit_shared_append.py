"""0.5.0-W1-259：track commit 對 append-only 共用檔只提交本票的行。

E2：工作區有他票未提交的行時，提交內容不含該行（修正前紅）。
"""
import argparse
import subprocess

import pytest

from ticket_system.commands import track_commit as tc

VERSION = "0.5.0"
TID = "0.5.0-W1-900"
OTHER = "0.5.0-W1-901"
WORKLOG = f"docs/work-logs/v0/v0.5/v{VERSION}/v{VERSION}-main.md"
TICKET = f"docs/work-logs/v0/v0.5/v{VERSION}/tickets/{TID}.md"
TOPICS = "docs/work-logs/topic-assignments.txt"
OLD_TOPIC = "0.5.0-W1-800\told\n"


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    for rel, text in ((TICKET, "t\n"), (WORKLOG, "log0\n"), (TOPICS, OLD_TOPIC)):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    monkeypatch.setattr(tc, "load_ticket", lambda v, t: {"id": t, "type": "IMP"})
    monkeypatch.setattr(tc, "write_files", lambda t: ["src/a.py"])
    monkeypatch.setattr(tc, "_resolve_repo_root", lambda w: str(tmp_path))
    monkeypatch.setattr(tc, "get_ticket_path", lambda v, t: tmp_path / TICKET)
    monkeypatch.setattr(tc, "get_ticket_state_root", lambda: tmp_path)
    monkeypatch.setattr(tc, "_build_worklog_path", lambda v: tmp_path / WORKLOG, raising=False)
    return tmp_path


def _run(files):
    args = argparse.Namespace(ticket_id=TID, message="chore: x", files=files, worktree=None)
    return tc.execute_commit(args, VERSION)


def _show(repo, rel):
    return _git(repo, "show", f"HEAD:{rel}").stdout


def test_other_ticket_topic_line_not_committed(repo):
    (repo / TOPICS).write_text(f"{OLD_TOPIC}{OTHER}\tx\n{TID}\tmine\n")
    assert _run([TOPICS]) == 0
    committed = _show(repo, TOPICS)
    assert f"{TID}\tmine" in committed
    assert OTHER not in committed
    assert OTHER in (repo / TOPICS).read_text()  # 他票行留在工作區


def test_other_ticket_worklog_line_not_committed(repo):
    (repo / WORKLOG).write_text(f"log0\n- {OTHER} wip\n- {TID} done\n")
    (repo / TICKET).write_text("t2\n")
    assert _run([TICKET, WORKLOG]) == 0
    committed = _show(repo, WORKLOG)
    assert f"{TID} done" in committed
    assert OTHER not in committed


def test_only_own_lines_same_as_whole_file(repo):
    (repo / TOPICS).write_text(f"{OLD_TOPIC}{TID}\tmine\n")
    assert _run([TOPICS]) == 0
    assert _show(repo, TOPICS) == (repo / TOPICS).read_text()


def test_no_own_line_not_committed(repo, capsys):
    head = _git(repo, "rev-parse", "HEAD").stdout
    (repo / TOPICS).write_text(f"{OLD_TOPIC}{OTHER}\tx\n")
    assert _run([TOPICS]) == 0
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert "無本票" in capsys.readouterr().out


def test_worktree_mode_refuses_ticket_md_as_primary_path(repo):
    """worktree 內票面是舊副本，只有共用檔本票行時不得借票面作主路徑（E2 正向對照）。"""
    head = _git(repo, "rev-parse", "HEAD").stdout
    (repo / TICKET).write_text("stale worktree copy\n")
    (repo / TOPICS).write_text(f"{OLD_TOPIC}{TID}\tmine\n")
    args = argparse.Namespace(
        ticket_id=TID, message="chore: x", files=[TOPICS], worktree=str(repo)
    )
    assert tc.execute_commit(args, VERSION) == 1
    assert _git(repo, "rev-parse", "HEAD").stdout == head
