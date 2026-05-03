"""
Unit tests for worktree-zombie-cleanup-hook.

Source: 0.18.0-W17-119.1
"""

import importlib.util
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# 動態載入帶連字號的 hook 檔
HOOK_PATH = Path(__file__).resolve().parent.parent / "worktree-zombie-cleanup-hook.py"


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
         patch.object(hook_module, "remove_worktree", return_value=True) as mock_rm:
        result = hook_module.process_worktree(tmp_path, wt, time.time(), logger)
    assert result["action"] == "clean"
    assert result["success"] is True
    mock_rm.assert_called_once()


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
