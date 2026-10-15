"""complete 收尾提交的鎖與 CAS 拒絕重試（0.5.0-W1-075.1）。

E1 對照：同一注入（首次提交遇 CAS 拒絕）下，不經重試的單次提交為失敗，
經 complete 路徑則自癒；對照組證明綠燈來自重試而非注入無效。
"""
import subprocess
from pathlib import Path

import pytest

from ticket_system.commands import lifecycle
from ticket_system.lib import git_ops, git_utils

_TID = "0.0.0-W0-001"
_CAS = (
    "fatal: update_ref failed for ref 'HEAD': cannot lock ref 'HEAD': "
    "is at aaaa but expected bbbb"
)


def _run(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _run(tmp_path, "init", "-q", "-b", "main")
    _run(tmp_path, "config", "user.email", "t@example.com")
    _run(tmp_path, "config", "user.name", "t")
    md = tmp_path / f"{_TID}.md"
    md.write_text("v1\n")
    _run(tmp_path, "add", md.name)
    _run(tmp_path, "commit", "-q", "-m", "init")
    md.write_text("v2\n")
    monkeypatch.setattr(git_utils, "_sleep", lambda _s: None)
    return tmp_path


def _flaky_commit(fail_times: int, error: str = _CAS):
    """前 fail_times 次回 failed(error)，之後走真實 commit_files_isolated。"""
    calls = {"n": 0}

    def fn(paths, message, **kwargs):
        calls["n"] += 1
        if calls["n"] <= fail_times:
            return {"status": "failed", "commit_sha": None, "error": error}
        return git_ops.commit_files_isolated(paths, message, **kwargs)

    fn.calls = calls
    return fn


def test_control_single_attempt_fails_on_cas(repo):
    """對照：不重試的單次提交在 CAS 拒絕下為失敗。"""
    result = _flaky_commit(1)([str(repo / f"{_TID}.md")], "m", cwd=str(repo))
    assert result["status"] == "failed"


def test_complete_commit_self_heals_after_cas_rejection(repo, monkeypatch, capsys):
    fake = _flaky_commit(1)
    monkeypatch.setattr(lifecycle, "commit_files_isolated", fake)
    assert lifecycle._auto_commit_completion_files(_TID, [str(repo / f"{_TID}.md")]) is False
    assert fake.calls["n"] == 2
    assert "[WARNING]" not in capsys.readouterr().err
    assert _run(repo, "status", "--porcelain").strip() == ""


def test_complete_commit_retries_lock_contention(repo, monkeypatch):
    lock_err = (
        "fatal: update_ref failed for ref 'HEAD': cannot lock ref 'HEAD': Unable to "
        f"create '{repo}/.git/refs/heads/main.lock': File exists."
    )
    fake = _flaky_commit(2, lock_err)
    monkeypatch.setattr(lifecycle, "commit_files_isolated", fake)
    assert lifecycle._auto_commit_completion_files(_TID, [str(repo / f"{_TID}.md")]) is False
    assert fake.calls["n"] == 3


def test_complete_commit_gives_up_with_actual_attempts(repo, monkeypatch, capsys):
    fake = _flaky_commit(99)
    monkeypatch.setattr(lifecycle, "commit_files_isolated", fake)
    assert lifecycle._auto_commit_completion_files(_TID, [str(repo / f"{_TID}.md")]) is True
    err = capsys.readouterr().err
    assert f"嘗試 {fake.calls['n']} 次" in err
    assert fake.calls["n"] > 1


def test_non_retryable_failure_not_retried(repo, monkeypatch):
    fake = _flaky_commit(99, "fatal: something else")
    monkeypatch.setattr(lifecycle, "commit_files_isolated", fake)
    assert lifecycle._auto_commit_completion_files(_TID, [str(repo / f"{_TID}.md")]) is True
    assert fake.calls["n"] == 1
