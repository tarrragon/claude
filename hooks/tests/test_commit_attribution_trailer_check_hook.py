"""commit-attribution-trailer-check-hook 單元測試（E2 正向對照 + 豁免對照）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "commit-attribution-trailer-check-hook.py"


@pytest.fixture(scope="module")
def hook():
    spec = importlib.util.spec_from_file_location("attribution_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CO = "Co-Authored-By: Claude <noreply@anthropic.com>"
SES = "Claude-Session: https://claude.ai/code/session_abc"


def test_missing_co_author_prompts(hook):
    assert "Co-Authored-By" in hook.evaluate_trailers("feat: x\n\nbody\n", 1)


def test_only_session_line_prompts(hook):
    assert hook.evaluate_trailers(f"feat: x\n\nbody\n\n{SES}\n", 1) is not None


def test_co_author_only_ok(hook):
    assert hook.evaluate_trailers(f"feat: x\n\nbody\n\n{CO}\n", 1) is None


def test_adjacent_both_ok(hook):
    assert hook.evaluate_trailers(f"feat: x\n\nbody\n\n{CO}\n{SES}\n", 1) is None


def test_blank_line_between_prompts(hook):
    assert "Claude-Session" in hook.evaluate_trailers(f"feat: x\n\n{CO}\n\n{SES}\n", 1)


def test_session_not_last_paragraph_prompts(hook):
    assert hook.evaluate_trailers(f"feat: x\n\n{CO}\n{SES}\n\ntail text\n", 1) is not None


def test_ticket_cli_commit_exempt(hook):
    assert hook.evaluate_trailers("chore(1.0.0-W1-001): claim\n\nSession: 1234-uuid\n", 1) is None


def test_merge_exempt(hook):
    assert hook.evaluate_trailers("Merge branch 'x'\n", 2) is None
    assert hook.evaluate_trailers("feat: merged\n", 2) is None


def test_revert_exempt(hook):
    assert hook.evaluate_trailers('Revert "feat: x"\n\nThis reverts commit abc.\n', 1) is None


# --- check_commit：以 stdout 的提交 SHA 定位，不讀 HEAD（0.5.0-W1-265） ---

import logging
import subprocess

STDOUT_TPL = "[main {sha}] {subj}\n 1 file changed, 1 insertion(+)\n"
LOG = logging.getLogger("t")


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def _commit(repo, subject, body=""):
    (repo / "f.txt").write_text(subject)
    _git(repo, "add", "f.txt")
    msg = subject + ("\n\n" + body if body else "")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "--short", "HEAD")


@pytest.fixture
def repo(tmp_path, hook, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    monkeypatch.setattr(hook, "get_project_root", lambda: str(tmp_path))
    return tmp_path


def _input(sha, subj, command="git commit -m x"):
    stdout = STDOUT_TPL.format(sha=sha, subj=subj) if sha else " 1 file changed, 1 insertion(+)\n"
    return {"tool_input": {"command": command}, "tool_response": {"stdout": stdout, "stderr": ""}}


def test_uses_stdout_sha_not_head(hook, repo):
    old = _commit(repo, "old bad")  # 缺 trailer
    _commit(repo, "newer good", CO)  # HEAD 已被推進，且合規
    assert hook.check_commit(_input(old, "old bad"), LOG) is not None


def test_no_sha_falls_back_to_head(hook, repo):
    _commit(repo, "head bad")
    assert hook.check_commit(_input(None, "x"), LOG) is not None
    _commit(repo, "head good", CO)
    assert hook.check_commit(_input(None, "x"), LOG) is None


def test_unresolvable_sha_skipped_not_head(hook, repo):
    _commit(repo, "head bad")  # 若退回 HEAD 會誤報
    assert hook.check_commit(_input("deadbee", "other"), LOG) is None


def test_git_dash_C_uses_target_repo(hook, repo, tmp_path_factory):
    other = tmp_path_factory.mktemp("other")
    _git(other, "init", "-q", "-b", "main")
    sha = _commit(other, "other bad")
    _commit(repo, "proj good", CO)
    cmd = f"git -C {other} commit -m x"
    assert hook.check_commit(_input(sha, "other bad", cmd), LOG) is not None


def test_git_dash_C_variable_skipped(hook, repo):
    _commit(repo, "head bad")
    assert hook.check_commit(_input("deadbee", "x", 'git -C "$D" commit -m x'), LOG) is None
