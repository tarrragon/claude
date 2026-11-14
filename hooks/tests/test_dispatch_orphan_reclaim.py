"""
Test: 擁有者 session 已結束（orphan_confirmed）的派發條目，各守衛的處理方向。

背景：/clear 也讓 session 以 graceful release 結束，但其子代理與背景命令仍會
寫檔（實測）。因此 orphan_confirmed 只能用在「誤判時多提醒、不放行寫入」的
判定，不能用來放行破壞性操作或刪除派發登記。

驗證項目：
1. process-skip-guard `has_active_dispatch`：只剩孤兒時為 False（提醒不靜音）；
   E2 正向對照：存活 session 的條目仍為 True；registry 不可用時孤兒仍計入
2. workspace-wipe-guard `_get_active_dispatch_count`：孤兒條目仍計入佔用
   （E2 正向對照：/clear 後仍執行的子代理不得被當孤兒而放行清空工作區）
3. 派發登記不提供依 orphan 判定刪除條目的入口（housekeeping 不回收）
"""

import importlib.util
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

from lib import dispatch_scope as scope_module  # noqa: E402


def _load(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wipe_hook = _load("workspace_wipe_guard_orphan", "workspace-wipe-guard-hook.py")
skip_hook = _load("process_skip_guard_orphan", "process-skip-guard-hook.py")
tracker_hook = _load("active_dispatch_tracker_orphan", "active-dispatch-tracker-hook.py")

_LOG = logging.getLogger("test_dispatch_orphan_reclaim")


def _fresh():
    return {"heartbeat_ts": datetime.now(timezone.utc).isoformat()}


def _entry(desc, session_id):
    return {
        "agent_description": desc,
        "session_id": session_id,
        "ticket_id": "",
        "files": [],
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
        "turn_ended_at": None,
    }


def _write_state(root: Path, entries):
    claude_dir = root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "dispatch-active.json").write_text(
        json.dumps({"dispatches": entries}), encoding="utf-8"
    )


def _registry(monkeypatch, sessions, available=True):
    monkeypatch.setattr(
        scope_module, "_read_registry_sessions", lambda r, lg: (sessions, available)
    )


# ---------------------------------------------------------------------------
# 1. process-skip-guard（誤判方向為多提醒，採用 orphan 排除）
# ---------------------------------------------------------------------------


def test_skip_only_orphan_is_inactive(tmp_path, monkeypatch):
    _write_state(tmp_path, [_entry("gone", "s-gone")])
    monkeypatch.setattr(skip_hook, "get_shared_state_root", lambda: tmp_path)
    _registry(monkeypatch, {"s-alive": _fresh()})

    assert skip_hook.has_active_dispatch("s-self", _LOG) is False


def test_skip_alive_owner_is_active(tmp_path, monkeypatch):
    # E2 正向對照
    _write_state(tmp_path, [_entry("gone", "s-gone"), _entry("alive", "s-alive")])
    monkeypatch.setattr(skip_hook, "get_shared_state_root", lambda: tmp_path)
    _registry(monkeypatch, {"s-alive": _fresh()})

    assert skip_hook.has_active_dispatch("s-self", _LOG) is True


def test_skip_registry_unavailable_keeps_orphan(tmp_path, monkeypatch):
    _write_state(tmp_path, [_entry("gone", "s-gone")])
    monkeypatch.setattr(skip_hook, "get_shared_state_root", lambda: tmp_path)
    _registry(monkeypatch, {}, available=False)

    assert skip_hook.has_active_dispatch("s-self", _LOG) is True


# ---------------------------------------------------------------------------
# 2. workspace-wipe-guard（誤判方向為放行破壞性操作，不採用 orphan 排除）
# ---------------------------------------------------------------------------


def test_wipe_count_keeps_orphan_of_cleared_session(monkeypatch):
    # E2 正向對照：擁有者 session 經 /clear 結束（registry 已無該 session，
    # 判定為 orphan_confirmed），其子代理仍可能寫檔，條目必須仍計入佔用
    monkeypatch.setattr(
        wipe_hook, "get_active_dispatches", lambda root: [_entry("cleared", "s-cleared")]
    )
    _registry(monkeypatch, {"s-alive": _fresh()})
    assert (
        scope_module.exclude_orphan_confirmed(
            [_entry("cleared", "s-cleared")], Path("/fake"), "s-self", _LOG
        )
        == []
    ), "前提：該條目在共用判定下確為 orphan_confirmed"

    assert wipe_hook._get_active_dispatch_count(Path("/fake"), _LOG) == 1


# ---------------------------------------------------------------------------
# 3. 派發登記不依 orphan 判定刪除條目
# ---------------------------------------------------------------------------


def test_no_orphan_prune_entry_point():
    assert not hasattr(scope_module, "prune_orphan_confirmed")
    assert not hasattr(tracker_hook, "prune_orphan_confirmed")
