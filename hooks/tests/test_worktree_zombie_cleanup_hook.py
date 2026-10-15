"""
Unit tests for worktree-zombie-cleanup-hook.

Source: 0.18.0-W17-119.1
"""

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# 動態載入帶連字號的 hook 檔
HOOK_PATH = Path(__file__).resolve().parents[2] / "skills" / "worktree" / "hooks" / "worktree-zombie-cleanup-hook.py"


@pytest.fixture(scope="module")
def hook_module():
    sys.path.insert(0, str(HOOK_PATH.parent))
    spec = importlib.util.spec_from_file_location("worktree_zombie_cleanup_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------- parse_pid_from_locked_content ----------

def test_parse_pid_from_locked_content_typical(hook_module):
    content = "claude agent agent-a04636c2 (pid 45136)\n"
    assert hook_module.parse_pid_from_locked_content(content) == 45136


def test_parse_pid_from_locked_content_missing(hook_module):
    assert hook_module.parse_pid_from_locked_content("no pid here") is None
    assert hook_module.parse_pid_from_locked_content("") is None


def test_parse_pid_from_locked_content_malformed(hook_module):
    assert hook_module.parse_pid_from_locked_content("(pid abc)") is None


# ---------- is_recent ----------

def test_is_recent_true(tmp_path, hook_module):
    d = tmp_path / "agent-x"
    d.mkdir()
    assert hook_module.is_recent(d, time.time()) is True


def test_is_recent_false(tmp_path, hook_module):
    d = tmp_path / "agent-x"
    d.mkdir()
    old = time.time() - 60 * 60  # 1 小時前
    os.utime(d, (old, old))
    assert hook_module.is_recent(d, time.time()) is False


def test_is_recent_missing_returns_false(tmp_path, hook_module):
    assert hook_module.is_recent(tmp_path / "missing", time.time()) is False


# ---------- decide_action ----------

def test_decide_action_recent(hook_module):
    action, _ = hook_module.decide_action(123, False, "", False, recent=True)
    assert action == "skip-recent"


def test_decide_action_no_pid(hook_module):
    action, _ = hook_module.decide_action(None, False, "", False, recent=False)
    assert action == "skip-no-pid"


def test_decide_action_alive(hook_module):
    action, _ = hook_module.decide_action(123, True, "claude", False, recent=False)
    assert action == "skip-alive"


def test_decide_action_alive_pid_reused_other_process(hook_module):
    # PID 重用為其他進程 → 視為 dead，clean
    action, _ = hook_module.decide_action(123, True, "bash", False, recent=False)
    assert action == "clean"


def test_decide_action_dead_clean(hook_module):
    action, _ = hook_module.decide_action(123, False, "", False, recent=False)
    assert action == "clean"


def test_decide_action_dead_dirty(hook_module):
    action, _ = hook_module.decide_action(123, False, "", True, recent=False)
    assert action == "warn-dirty"


# ---------- is_disabled ----------

def test_is_disabled_off(hook_module, monkeypatch):
    monkeypatch.delenv(hook_module.DISABLE_ENV_VAR, raising=False)
    assert hook_module.is_disabled() is False


def test_is_disabled_on(hook_module, monkeypatch):
    monkeypatch.setenv(hook_module.DISABLE_ENV_VAR, "1")
    assert hook_module.is_disabled() is True


def test_is_disabled_empty_string(hook_module, monkeypatch):
    monkeypatch.setenv(hook_module.DISABLE_ENV_VAR, "  ")
    assert hook_module.is_disabled() is False


# ---------- list_agent_worktrees ----------

def test_list_agent_worktrees(tmp_path, hook_module):
    base = tmp_path / ".claude" / "worktrees"
    base.mkdir(parents=True)
    (base / "agent-aaaa").mkdir()
    (base / "agent-bbbb").mkdir()
    (base / "not-agent").mkdir()
    (base / "agent-cccc-file").touch()  # 檔案非目錄
    result = hook_module.list_agent_worktrees(tmp_path)
    names = sorted(p.name for p in result)
    assert names == ["agent-aaaa", "agent-bbbb"]


def test_list_agent_worktrees_missing(tmp_path, hook_module):
    assert hook_module.list_agent_worktrees(tmp_path) == []


# ---------- read_locked_pid ----------

def test_read_locked_pid(tmp_path, hook_module):
    name = "agent-zzz"
    locked_dir = tmp_path / ".git" / "worktrees" / name
    locked_dir.mkdir(parents=True)
    (locked_dir / "locked").write_text("claude agent agent-zzz (pid 99999)\n")
    assert hook_module.read_locked_pid(tmp_path, name) == 99999


def test_read_locked_pid_missing_file(tmp_path, hook_module):
    assert hook_module.read_locked_pid(tmp_path, "agent-none") is None


# ---------- process_worktree (整合純邏輯 + mocked subprocess) ----------

def _make_worktree(tmp_path: Path, name: str, pid: int, *, recent: bool = False):
    wt = tmp_path / ".claude" / "worktrees" / name
    wt.mkdir(parents=True)
    locked_dir = tmp_path / ".git" / "worktrees" / name
    locked_dir.mkdir(parents=True)
    (locked_dir / "locked").write_text(f"claude agent {name} (pid {pid})\n")
    if not recent:
        old = time.time() - 60 * 60
        os.utime(wt, (old, old))
    return wt


def test_process_worktree_dead_clean_triggers_remove(tmp_path, hook_module):
    wt = _make_worktree(tmp_path, "agent-d1", 11111)
    logger = MagicMock()
    with patch.object(hook_module, "check_pid_alive", return_value=(False, "")), \
         patch.object(hook_module, "is_worktree_dirty", return_value=False), \
         patch.object(hook_module, "get_worktree_branch", return_value="worktree-agent-d1"), \
         patch.object(hook_module, "delete_branch_if_merged", return_value=True), \
         patch.object(hook_module, "remove_worktree", return_value=True) as mock_rm, \
         patch.object(hook_module.subprocess, "run") as mock_git:
        result = hook_module.process_worktree(tmp_path, wt, time.time(), logger)
    assert result["action"] == "clean"
    assert result["success"] is True
    mock_rm.assert_called_once()
    mock_git.assert_not_called()  # 測試期間不得啟動真實 git


def test_process_worktree_dead_dirty_warns_no_remove(tmp_path, hook_module):
    wt = _make_worktree(tmp_path, "agent-d2", 22222)
    logger = MagicMock()
    with patch.object(hook_module, "check_pid_alive", return_value=(False, "")), \
         patch.object(hook_module, "is_worktree_dirty", return_value=True), \
         patch.object(hook_module, "remove_worktree") as mock_rm:
        result = hook_module.process_worktree(tmp_path, wt, time.time(), logger)
    assert result["action"] == "warn-dirty"
    mock_rm.assert_not_called()


def test_process_worktree_alive_skips(tmp_path, hook_module):
    wt = _make_worktree(tmp_path, "agent-a1", 33333)
    logger = MagicMock()
    with patch.object(hook_module, "check_pid_alive", return_value=(True, "claude")), \
         patch.object(hook_module, "remove_worktree") as mock_rm:
        result = hook_module.process_worktree(tmp_path, wt, time.time(), logger)
    assert result["action"] == "skip-alive"
    mock_rm.assert_not_called()


def test_process_worktree_recent_skips(tmp_path, hook_module):
    wt = _make_worktree(tmp_path, "agent-r1", 44444, recent=True)
    logger = MagicMock()
    with patch.object(hook_module, "check_pid_alive") as mock_ps, \
         patch.object(hook_module, "remove_worktree") as mock_rm:
        result = hook_module.process_worktree(tmp_path, wt, time.time(), logger)
    assert result["action"] == "skip-recent"
    mock_ps.assert_not_called()
    mock_rm.assert_not_called()


# ---------- main 整體（含 disable 開關）----------

def test_main_disabled_short_circuit(tmp_path, hook_module, monkeypatch, capsys):
    monkeypatch.setenv(hook_module.DISABLE_ENV_VAR, "1")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc = hook_module.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert '"suppressOutput": true' in out


def test_main_no_worktrees(tmp_path, hook_module, monkeypatch, capsys):
    monkeypatch.delenv(hook_module.DISABLE_ENV_VAR, raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc = hook_module.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert '"suppressOutput": true' in out


# ---------- summarize ----------

def test_summarize_empty(hook_module):
    assert hook_module.summarize([]) == ""
    assert hook_module.summarize([{"action": "skip-alive"}]) == ""


def test_summarize_mixed(hook_module):
    results = [
        {"name": "a", "action": "clean", "success": True, "reason": "dead"},
        {"name": "b", "action": "warn-dirty", "reason": "dead+dirty"},
        {"name": "c", "action": "clean", "success": False, "reason": "dead"},
    ]
    msg = hook_module.summarize(results)
    assert "已清理: 1" in msg
    assert "dirty 保留: 1" in msg
    assert "清理失敗: 1" in msg
    assert "* b" in msg


# ---------- 0.5.0-W1-164.6.1：唯讀 git 旗標 ----------

def test_is_worktree_dirty_status_has_no_optional_locks_before_subcommand(hook_module):
    fake = MagicMock(returncode=0, stdout="", stderr="")
    with patch.object(hook_module.subprocess, "run", return_value=fake) as run:
        hook_module.is_worktree_dirty(Path("/tmp"))
    argv = run.call_args.args[0]
    assert "--no-optional-locks" in argv
    assert argv.index("--no-optional-locks") < argv.index("status")


def _make_stat_dirty_repo(tmp_path):
    """臨時 repo：檔案內容未變但 mtime 改動（stat-dirty），不帶旗標的 status 會重寫 index。"""
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    target = tmp_path / "f.txt"
    target.write_text("x\n")
    git("add", "f.txt")
    git("commit", "-q", "-m", "init")
    os.utime(target, (1_000_000_000, 1_000_000_000))
    return tmp_path / ".git" / "index"


def test_plain_status_rewrites_index_control(tmp_path):
    """對照：不帶旗標的 status 會改寫 index（旗標測試的鑑別力前提）。"""
    index = _make_stat_dirty_repo(tmp_path)
    before = index.read_bytes()
    subprocess.run(["git", "-C", str(tmp_path), "status", "--porcelain"], check=True, capture_output=True)
    assert index.read_bytes() != before


def test_is_worktree_dirty_does_not_rewrite_index(hook_module, tmp_path):
    index = _make_stat_dirty_repo(tmp_path)
    before = index.read_bytes()
    assert hook_module.is_worktree_dirty(tmp_path) is False
    assert index.read_bytes() == before


# ---------- 0.5.0-W1-164.6.2：寫入類 git 經溫和終止函式、靜默逾時日誌 ----------

import logging
import signal
import subprocess


class _FakeTimeoutPopen:
    """communicate 逾時、terminate 後 wait 立即返回；記錄收到的終止方式。"""

    instances = []

    def __init__(self, args, **kwargs):
        self.args = args
        self.pid = 4242
        self.calls = []
        self.returncode = None
        _FakeTimeoutPopen.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def communicate(self, input_text=None, timeout=None):
        raise subprocess.TimeoutExpired(self.args, timeout)

    def terminate(self):
        self.calls.append("terminate")

    def wait(self, timeout=None):
        self.calls.append("wait")
        return 0

    def kill(self):
        self.calls.append("kill")


@pytest.fixture
def fake_timeout_popen(monkeypatch):
    import lib.git_utils as git_utils
    _FakeTimeoutPopen.instances = []
    monkeypatch.setattr(git_utils.subprocess, "Popen", _FakeTimeoutPopen)
    monkeypatch.setattr(
        git_utils.os, "killpg",
        lambda pid, sig: _FakeTimeoutPopen.instances[0].calls.append(("killpg", pid, sig)),
    )
    return _FakeTimeoutPopen


def _ok_completed(stdout=""):
    return subprocess.CompletedProcess([], 0, stdout, "")


def _no_subprocess_run(*a, **k):
    raise AssertionError("寫入類呼叫不得直接經 subprocess.run（SIGKILL 逾時）")


def test_remove_worktree_uses_graceful_runner_for_unlock_and_remove(hook_module, monkeypatch):
    seen = []

    def fake(args, timeout, **kw):
        seen.append(args)
        return _ok_completed()

    monkeypatch.setattr(hook_module, "run_with_graceful_timeout", fake)
    monkeypatch.setattr(hook_module.subprocess, "run", _no_subprocess_run)
    ok = hook_module.remove_worktree(Path("/r"), Path("/r/w"), "agent-x", logging.getLogger("t"))
    assert ok is True
    assert [a[3:5] for a in seen] == [["worktree", "unlock"], ["worktree", "remove"]]


def test_delete_branch_uses_graceful_runner(hook_module, monkeypatch):
    seen = []

    def fake(args, timeout, **kw):
        seen.append(args)
        return _ok_completed()

    monkeypatch.setattr(hook_module, "run_with_graceful_timeout", fake)
    monkeypatch.setattr(hook_module, "is_branch_merged", lambda *a, **k: True)
    ok = hook_module.delete_branch_if_merged(Path("/r"), "b", "agent-x", logging.getLogger("t"))
    assert ok is True
    assert seen and seen[0][3:5] == ["branch", "-d"]


def test_remove_worktree_timeout_sends_sigterm_not_sigkill(hook_module, fake_timeout_popen, caplog):
    with caplog.at_level(logging.ERROR):
        ok = hook_module.remove_worktree(Path("/r"), Path("/r/w"), "agent-x", logging.getLogger("t"))
    assert ok is False
    assert fake_timeout_popen.instances[0].calls == [("killpg", 4242, signal.SIGTERM), "wait"]
    assert any("執行失敗" in r.getMessage() for r in caplog.records)


def test_delete_branch_timeout_sends_sigterm_not_sigkill(hook_module, fake_timeout_popen, monkeypatch, caplog):
    monkeypatch.setattr(hook_module, "is_branch_merged", lambda *a, **k: True)
    with caplog.at_level(logging.ERROR):
        ok = hook_module.delete_branch_if_merged(Path("/r"), "b", "agent-x", logging.getLogger("t"))
    assert ok is False
    assert fake_timeout_popen.instances[0].calls == [("killpg", 4242, signal.SIGTERM), "wait"]
    assert any("執行失敗" in r.getMessage() for r in caplog.records)


def _raise_timeout(*a, **k):
    raise subprocess.TimeoutExpired(["git"], 10)


@pytest.mark.parametrize("fn,args,expected,name", [
    ("is_worktree_dirty", (Path("/tmp"),), True, "is_worktree_dirty"),
    ("is_branch_merged", (Path("/tmp"), "b"), False, "is_branch_merged"),
])
def test_silent_helpers_log_timeout_distinct_from_other_failure(
    hook_module, monkeypatch, caplog, fn, args, expected, name
):
    monkeypatch.setattr(hook_module.subprocess, "run", _raise_timeout)
    with caplog.at_level(logging.INFO):
        assert getattr(hook_module, fn)(*args) is expected
    timeout_msgs = [r.getMessage() for r in caplog.records if "逾時" in r.getMessage()]
    assert len(timeout_msgs) == 1
    assert name in timeout_msgs[0]

    caplog.clear()

    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(hook_module.subprocess, "run", boom)
    with caplog.at_level(logging.INFO):
        assert getattr(hook_module, fn)(*args) is expected
    msgs = [r.getMessage() for r in caplog.records]
    assert any(name in m and "執行失敗" in m for m in msgs)
    assert not any("逾時" in m for m in msgs)


@pytest.mark.parametrize("fn,args,stdout,expected", [
    ("is_worktree_dirty", (Path("/tmp"),), "", False),
    ("is_branch_merged", (Path("/tmp"), "b"), "", True),
])
def test_silent_helpers_no_log_on_normal_completion(hook_module, monkeypatch, caplog, fn, args, stdout, expected):
    fake = MagicMock(returncode=0, stdout=stdout, stderr="")
    monkeypatch.setattr(hook_module.subprocess, "run", lambda *a, **k: fake)
    with caplog.at_level(logging.DEBUG):
        assert getattr(hook_module, fn)(*args) is expected
    assert not [r for r in caplog.records if getattr(hook_module, "HOOK_NAME") in r.name]


@pytest.mark.parametrize("fn,args,expected,name", [
    ("is_worktree_dirty", (Path("/tmp"),), True, "is_worktree_dirty"),
    ("is_branch_merged", (Path("/tmp"), "b"), False, "is_branch_merged"),
])
def test_silent_helpers_log_nonzero_returncode_as_failure(
    hook_module, monkeypatch, caplog, fn, args, expected, name
):
    fake = MagicMock(returncode=128, stdout="", stderr="fatal")
    monkeypatch.setattr(hook_module.subprocess, "run", lambda *a, **k: fake)
    with caplog.at_level(logging.INFO):
        assert getattr(hook_module, fn)(*args) is expected
    msgs = [r.getMessage() for r in caplog.records]
    assert any(name in m and "執行失敗" in m and "returncode=128" in m for m in msgs)
    assert not any("逾時" in m for m in msgs)


# ---------- 整體期限扣減（0.5.0-W1-164.6.17） ----------

import json
import types


def _registered_outer_timeout():
    settings = Path(__file__).resolve().parents[2] / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    for group in data["hooks"]["SessionStart"]:
        for hook in group["hooks"]:
            if "worktree-zombie-cleanup-hook.py" in hook["command"]:
                return hook["timeout"]
    raise AssertionError("settings.json 未註冊 worktree-zombie-cleanup hook")


def _simulate_all_hung(hook_module, monkeypatch, tmp_path, deduct):
    """5 個殭屍 worktree、每個 git 呼叫皆卡到逾時並耗盡寬限；回傳模擬耗時秒數。"""
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        hook_module, "time",
        types.SimpleNamespace(monotonic=lambda: clock["now"], time=lambda: 0.0),
    )
    grace = hook_module.TERMINATE_GRACE_SECONDS

    def hung_runner(args, timeout, **kw):
        clock["now"] += timeout + grace
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr(hook_module, "run_with_graceful_timeout", hung_runner)
    monkeypatch.setattr(hook_module, "is_worktree_dirty", lambda p: False)
    monkeypatch.setattr(hook_module, "check_pid_alive", lambda pid: (False, ""))
    monkeypatch.setattr(hook_module, "get_worktree_branch", lambda r, w: None)
    monkeypatch.setattr(hook_module, "is_recent", lambda d, n, t=0: False)
    monkeypatch.setattr(hook_module, "read_locked_pid", lambda r, n: 1)
    if not deduct:
        monkeypatch.setattr(hook_module, "budgeted_timeout", lambda base: base)

    worktrees = [tmp_path / f"agent-{i}" for i in range(5)]
    logger = logging.getLogger("test-budget")
    start = clock["now"]
    hook_module.start_overall_deadline()
    try:
        for wt in worktrees:
            if hook_module.budget_exhausted() and deduct:
                break
            hook_module.process_worktree(tmp_path, wt, 0.0, logger)
    finally:
        hook_module._deadline = None
    return clock["now"] - start


def test_overall_budget_is_below_registered_outer_timeout(hook_module):
    assert hook_module.OUTER_TIMEOUT_SECONDS == _registered_outer_timeout()
    assert hook_module.OVERALL_BUDGET_SECONDS < hook_module.OUTER_TIMEOUT_SECONDS


def test_all_hung_calls_finish_before_outer_timeout(hook_module, monkeypatch, tmp_path):
    elapsed = _simulate_all_hung(hook_module, monkeypatch, tmp_path, deduct=True)
    assert elapsed < _registered_outer_timeout()


def test_without_deduction_all_hung_calls_exceed_outer_timeout(hook_module, monkeypatch, tmp_path):
    """正向對照：移除扣減後整體耗時超過外層，證明上一則斷言有鑑別力。"""
    elapsed = _simulate_all_hung(hook_module, monkeypatch, tmp_path, deduct=False)
    assert elapsed >= _registered_outer_timeout()


def test_budgeted_timeout_none_when_remaining_not_above_grace(hook_module, monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr(hook_module, "time", types.SimpleNamespace(monotonic=lambda: clock["now"]))
    hook_module.start_overall_deadline(budget=hook_module.TERMINATE_GRACE_SECONDS)
    try:
        assert hook_module.budgeted_timeout(10) is None
    finally:
        hook_module._deadline = None


def test_budgeted_timeout_passthrough_without_deadline(hook_module):
    hook_module._deadline = None
    assert hook_module.budgeted_timeout(10) == 10
