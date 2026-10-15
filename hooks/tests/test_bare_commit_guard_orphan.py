"""
Test: bare-commit-guard-hook 排除擁有者 session 已結束的派發條目
（0.5.0-W1-227.1，源自 ANA 0.5.0-W1-227 候選 C）。

驗證項目：
1. E2 正向對照：orphan_confirmed 條目不計入佔用（修正前 DENY、修正後放行）
2. 對照：擁有者存活／heartbeat 逾時／registry 不可用／無 session_id
   仍維持佔用（DENY）
3. 排除時寫 warning 日誌（ticket_id、session_id）
"""

import importlib.util
import io
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "bare_commit_guard_hook_orphan", HOOKS_DIR / "bare-commit-guard-hook.py"
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)


def _dispatch(ticket_id, files, session_id):
    return {"ticket_id": ticket_id, "files": list(files), "session_id": session_id}


def _fresh():
    return {"heartbeat_ts": datetime.now(timezone.utc).isoformat()}


def _two(owner_a, owner_b="s-alive"):
    return [_dispatch("T-1", ["a.py"], owner_a), _dispatch("T-2", ["b.py"], owner_b)]


def _run(monkeypatch, sessions, available, dispatches):
    """T-1／T-2 宣告互不相交，staged 跨兩者：兩筆皆佔用 → DENY；
    佔用判定決定結果。"""
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(hook_module, "get_project_root", lambda: Path("/fake"))
    monkeypatch.setattr(hook_module, "_merge_in_progress", lambda *a, **k: False)
    monkeypatch.setattr(hook_module, "_get_active_dispatches_safe", lambda r: dispatches)
    monkeypatch.setattr(hook_module, "_get_staged_files", lambda r: ["a.py", "b.py"])
    monkeypatch.setattr(hook_module, "_with_live_declared_files", lambda d, r, lg: d)
    monkeypatch.setattr(
        hook_module, "_read_registry_sessions", lambda r, lg: (sessions, available),
        raising=False,  # 修正前守衛無此函式；容許以原版暫換驗證紅燈
    )
    monkeypatch.setattr(
        hook_module, "resolve_session_id", lambda data: "s-self", raising=False
    )
    return hook_module.main()


def test_orphan_confirmed_does_not_block(monkeypatch):
    # T-1 被排除後無活躍派發 → 非並行期 WARN 放行；修正前 DENY（紅）
    one = [_dispatch("T-1", ["a.py"], "s-gone")]
    assert _run(monkeypatch, {"s-alive": _fresh()}, True, one) == 0


def test_alive_owner_still_blocks(monkeypatch):
    sessions = {"s-a": _fresh(), "s-alive": _fresh()}
    assert _run(monkeypatch, sessions, True, _two("s-a")) == 2


def test_heartbeat_stale_owner_still_blocks(monkeypatch):
    stale = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()
    sessions = {"s-a": {"heartbeat_ts": stale}, "s-alive": _fresh()}
    assert _run(monkeypatch, sessions, True, _two("s-a")) == 2


def test_registry_unavailable_still_blocks(monkeypatch):
    assert _run(monkeypatch, {}, False, _two("s-gone")) == 2


def test_unknown_owner_still_blocks(monkeypatch):
    assert _run(monkeypatch, {"s-alive": _fresh()}, True, _two("")) == 2


def test_exclusion_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(
        hook_module, "_read_registry_sessions",
        lambda r, lg: ({"s-alive": _fresh()}, True),
    )
    logger = logging.getLogger("t-exclude")
    with caplog.at_level(logging.WARNING, logger="t-exclude"):
        out = hook_module._exclude_orphan_confirmed(
            _two("s-gone"), Path("/fake"), "s-self", logger
        )
    assert [d["ticket_id"] for d in out] == ["T-2"]
    assert "T-1" in caplog.text and "s-gone" in caplog.text
