"""track commit 缺 Co-Authored-By 時自動補上。

E1：缺 trailer 的訊息修正前不補（紅）；已含且相鄰時逐字不變（對照）。
"""
import argparse
import json
import subprocess

import pytest

from ticket_system.commands import track_commit as tc

VERSION = "0.5.0"
TID = "0.5.0-W1-900"
SID = "sess-1111"
CO = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
SESSION = "Claude-Session: https://claude.ai/code/session_abc"


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, check=True)


def _write_transcript(path, model):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"type": "assistant", "message": {"model": "claude-haiku-4-5"}},
        {"type": "assistant", "message": {"model": model}},
        {"type": "user", "message": {"content": "x"}},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    (work / "a.py").write_text("base\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "base")
    (work / "a.py").write_text("changed\n")

    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("AI_AGENT", raising=False)
    _write_transcript(home / "projects" / "proj" / f"{SID}.jsonl", "claude-opus-5-5")

    monkeypatch.setattr(tc, "load_ticket", lambda v, t: {"id": t, "type": "IMP"})
    monkeypatch.setattr(tc, "write_files", lambda t: ["a.py"])
    monkeypatch.setattr(tc, "_resolve_repo_root", lambda w: str(work))
    monkeypatch.setattr(tc, "get_ticket_path", lambda v, t: work / "t.md")
    monkeypatch.setattr(tc, "get_ticket_state_root", lambda: work)
    monkeypatch.setattr(tc, "_build_worklog_path", lambda v: work / "w.md", raising=False)
    return work


def _commit(message):
    args = argparse.Namespace(ticket_id=TID, message=message, files=["a.py"], worktree=None)
    return tc.execute_commit(args, VERSION)


def _head_message(repo):
    return _git(repo, "log", "-1", "--format=%B").stdout


def _trailers(repo):
    out = subprocess.run(
        ["git", "-C", str(repo), "interpret-trailers", "--parse"],
        input=_head_message(repo), capture_output=True, text=True, check=True,
    ).stdout
    return out.strip().splitlines()


def test_missing_trailer_is_added(repo):
    assert _commit("feat: x\n\n內文") == 0
    assert CO in _trailers(repo)


def test_added_after_existing_trailer_paragraph(repo):
    assert _commit(f"feat: x\n\nSigned-off-by: a <a@b>") == 0
    assert _trailers(repo) == ["Signed-off-by: a <a@b>", CO]


def test_present_and_adjacent_is_verbatim(repo):
    msg = f"feat: x\n\n內文\n\n{CO}\n{SESSION}\n"
    assert _commit(msg) == 0
    assert _head_message(repo) == msg + "\n"


def test_non_adjacent_session_is_moved(repo):
    assert _commit(f"feat: x\n\n{SESSION}\n\n{CO}\n") == 0
    assert _trailers(repo) == [CO, SESSION]


def test_unreadable_model_warns_and_commits(repo, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "no-such")
    assert _commit("feat: x") == 0
    out = capsys.readouterr().out
    assert "[WARNING]" in out
    assert "Co-Authored-By" not in _head_message(repo)


def test_unknown_model_warns(repo, tmp_path, monkeypatch, capsys):
    _write_transcript(tmp_path / "claude" / "projects" / "proj" / f"{SID}.jsonl", "claude-zzz-9")
    assert _commit("feat: x") == 0
    assert "無法推導顯示名稱" in capsys.readouterr().out


def test_unlisted_but_wellformed_model_is_derived(repo, tmp_path):
    _write_transcript(
        tmp_path / "claude" / "projects" / "proj" / f"{SID}.jsonl", "claude-haiku-5-5"
    )
    assert _commit("feat: x") == 0
    assert "Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>" in _trailers(repo)


def test_subagent_uses_own_transcript_not_parent(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT", "claude-code_2-1-299_agent")
    agent_dir = tmp_path / "proj" / ".claude" / "worktrees" / "agent-abc123"
    agent_dir.mkdir(parents=True)
    monkeypatch.setattr(tc, "_resolve_repo_root", lambda w: str(repo))
    _write_transcript(
        tmp_path / "claude" / "projects" / "proj" / SID / "subagents" / "agent-abc123.jsonl",
        "claude-sonnet-5-5",
    )
    from ticket_system.lib import commit_attribution as ca
    line, _ = ca.resolve_co_author_line(str(agent_dir))
    assert line == "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"


def test_main_session_with_agent_suffixed_env_is_filled(repo, monkeypatch):
    # 主 session 的 AI_AGENT 同樣以 _agent 結尾，不可當子代理人訊號；cwd 不在 agent worktree
    monkeypatch.setenv("AI_AGENT", "claude-code_2-1-299_agent")
    assert _commit("feat: x\n\n內文") == 0
    assert CO in _trailers(repo)
