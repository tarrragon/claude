"""0.5.0-W1-297.1：track commit 拒絕訊息依類型給出下一步指示。

判準性拒絕不得改走 fallback；環境性失敗先重跑、持續失敗才 fallback。
E1：兩類指示常數與分類結果必須不同，且各自出現在對應拒絕的輸出。
"""
import argparse

import pytest

from ticket_system.commands import track_commit as tc

TID = "0.5.0-W1-900"
VERSION = "0.5.0"


def test_guidance_constants_differ():
    assert tc.CRITERIA_REJECTION_GUIDANCE != tc.ENVIRONMENT_FAILURE_GUIDANCE


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("self_verification", tc.FAILURE_CRITERIA),
        ("git_step", tc.FAILURE_ENVIRONMENT),
        ("cas", tc.FAILURE_ENVIRONMENT),
        (None, tc.FAILURE_CRITERIA),  # fail-closed
        ("unknown_kind", tc.FAILURE_CRITERIA),  # fail-closed
    ],
)
def test_classify_failure(kind, expected):
    assert tc.classify_failure(kind) == expected


def _run(files, tmp_path, monkeypatch, result=None, declared=("src/a.py",)):
    monkeypatch.setattr(tc, "load_ticket", lambda v, t: {"id": t, "type": "IMP"})
    monkeypatch.setattr(tc, "write_files", lambda t: list(declared))
    monkeypatch.setattr(tc, "_resolve_repo_root", lambda w: str(tmp_path))
    monkeypatch.setattr(tc, "_cli_managed_paths", lambda *a: set())
    monkeypatch.setattr(tc, "_expand_directories", lambda f, *a: list(f))
    monkeypatch.setattr(tc, "_split_shared_append_files", lambda n, *a: (n, {}))
    if result is not None:
        monkeypatch.setattr(tc, "commit_files_isolated", lambda *a, **k: result)
    args = argparse.Namespace(ticket_id=TID, message="m", files=files, worktree=None)
    return tc.execute_commit(args, VERSION)


def test_out_of_scope_carries_criteria_guidance(tmp_path, monkeypatch, capsys):
    assert _run(["src/other.py"], tmp_path, monkeypatch) == 1
    out = capsys.readouterr().out
    assert tc.CRITERIA_REJECTION_GUIDANCE in out
    assert tc.ENVIRONMENT_FAILURE_GUIDANCE not in out


def test_undeclared_carries_criteria_guidance(tmp_path, monkeypatch, capsys):
    assert _run(["src/a.py"], tmp_path, monkeypatch, declared=()) == 1
    assert tc.CRITERIA_REJECTION_GUIDANCE in capsys.readouterr().out


def test_environment_failure_carries_retry_guidance(tmp_path, monkeypatch, capsys):
    result = {"status": "failed", "commit_sha": None, "error": "git read-tree 失敗",
              "failure_kind": "git_step"}
    assert _run(["src/a.py"], tmp_path, monkeypatch, result) == 1
    out = capsys.readouterr().out
    assert tc.ENVIRONMENT_FAILURE_GUIDANCE in out
    assert tc.CRITERIA_REJECTION_GUIDANCE not in out


def test_self_verification_failure_carries_criteria_guidance(tmp_path, monkeypatch, capsys):
    result = {"status": "failed", "commit_sha": None, "error": "任意字面",
              "failure_kind": "self_verification"}
    assert _run(["src/a.py"], tmp_path, monkeypatch, result) == 1
    out = capsys.readouterr().out
    assert tc.CRITERIA_REJECTION_GUIDANCE in out
    assert tc.ENVIRONMENT_FAILURE_GUIDANCE not in out
