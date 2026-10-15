"""0.5.0-W1-237：track commit 將 CLI 管理的檔案視為隱含可寫。

補救文案會同時帶票檔、版本工作日誌、topic-assignments.txt；這三項不在
where.files，原範圍檢查會拒絕。E2：他票票檔與一般 docs 檔仍須被拒。
"""
import argparse
import subprocess

import pytest

from ticket_system.commands import track_commit as tc

VERSION = "0.5.0"
TID = "0.5.0-W1-900"
WORKLOG = f"docs/work-logs/v0/v0.5/v{VERSION}/v{VERSION}-main.md"
TICKET = f"docs/work-logs/v0/v0.5/v{VERSION}/tickets/{TID}.md"
OTHER_TICKET = f"docs/work-logs/v0/v0.5/v{VERSION}/tickets/0.5.0-W1-901.md"
TOPICS = "docs/work-logs/topic-assignments.txt"
ALL = (WORKLOG, TICKET, OTHER_TICKET, TOPICS, "docs/other.md")


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    for rel in ALL:
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("base\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    for rel in ALL:
        (tmp_path / rel).write_text("changed\n")

    monkeypatch.setattr(tc, "load_ticket", lambda v, t: {"id": t, "type": "IMP"})
    monkeypatch.setattr(tc, "write_files", lambda t: ["src/a.py"])
    monkeypatch.setattr(tc, "_resolve_repo_root", lambda w: str(tmp_path))
    monkeypatch.setattr(tc, "get_ticket_path", lambda v, t: tmp_path / TICKET)
    monkeypatch.setattr(tc, "get_ticket_state_root", lambda: tmp_path)
    monkeypatch.setattr(tc, "_build_worklog_path", lambda v: tmp_path / WORKLOG, raising=False)
    return tmp_path


def _run(files):
    args = argparse.Namespace(ticket_id=TID, message="chore: remedy", files=files, worktree=None)
    return tc.execute_commit(args, VERSION)


def test_remedy_with_worklog_and_topics_commits(repo):
    # 0.5.0-W1-259：共用檔只提交本票的行，故兩檔需含本票的新增行
    (repo / WORKLOG).write_text(f"base\n- {TID} done\n")
    (repo / TOPICS).write_text(f"base\n{TID}\ttopic\n")
    assert _run([TICKET, WORKLOG, TOPICS]) == 0
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert sorted(committed) == sorted([TICKET, WORKLOG, TOPICS])


@pytest.mark.parametrize("bad", [OTHER_TICKET, "docs/other.md"])
def test_other_docs_still_rejected(repo, bad, capsys):
    assert _run([TICKET, bad]) == 1
    assert bad in capsys.readouterr().out


def test_ticket_only_unchanged(repo):
    assert _run([TICKET]) == 0
