"""format_write_command_commit_failure 依失敗分支的補救文案（0.5.0-W1-075.2，E2 逐分支）。"""
import pytest

from ticket_system.lib.git_utils import (
    classify_commit_failure,
    format_write_command_commit_failure,
)

_TID = "0.0.0-W0-001"
_CAS = "fatal: update_ref failed for ref 'HEAD': cannot lock ref 'HEAD': is at A but expected B"
_LOCK = (
    "fatal: update_ref failed for ref 'HEAD': cannot lock ref 'HEAD': Unable to "
    "create '/r/.git/refs/heads/main.lock': File exists."
)
_HOOK = "[git-ref-transaction-content-guard] DENY: x\nfatal: ref updates aborted by hook"
_OTHER = "git rev-parse 逾時"


def _fmt(error, attempts=1, extra=()):
    return format_write_command_commit_failure(
        "complete", "/r/t.md", _TID, "post-completion", "metadata sync",
        error, attempts, extra,
    )


@pytest.mark.parametrize(
    "error,expected",
    [(_CAS, "cas"), (_LOCK, "lock"), (_HOOK, "hook"), (_OTHER, "other")],
)
def test_classify(error, expected):
    assert classify_commit_failure(error) == expected


@pytest.mark.parametrize("error", [_CAS, _HOOK])
def test_cas_and_hook_recommend_track_commit_not_bare_commit(error):
    out = _fmt(error, extra=["/r/w.md"])
    assert "補救指令：ticket track commit" in out
    assert "/r/t.md /r/w.md" in out
    assert "git add" not in out
    assert "git commit -m" not in out
    assert "鎖排除後" not in out


@pytest.mark.parametrize("error", [_LOCK, _OTHER])
def test_lock_and_other_keep_git_add_remedy(error):
    out = _fmt(error)
    assert "補救指令（鎖排除後）：git add /r/t.md" in out
    assert "ticket track commit" in out


def test_lock_branch_lists_lock_path():
    assert "鎖檔路徑：/r/.git/refs/heads/main.lock" in _fmt(_LOCK)


@pytest.mark.parametrize("attempts", [1, 2, 4])
def test_attempts_is_actual_value(attempts):
    assert f"嘗試 {attempts} 次" in _fmt(_CAS, attempts)
