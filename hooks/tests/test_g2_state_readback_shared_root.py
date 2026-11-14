"""G2 讀回狀態的兩支 hook 改經 get_hook_log_dir（3.3.0-W1-204.1.6.7）。

涵蓋 context-depth-warning（state、log）與 memory-dir-audit（marker）。
不設 HOOK_TEST_ISOLATION；建主 checkout 與 linked worktree，斷言讀寫都落在
主 repo 的 .claude/hook-logs/<hook 名>/，並驗證兩個 checkout 並行寫入時的合流行為。
變異確認：換回舊版（以 __file__ 推根寫 .claude/hooks/hook-logs）時，本檔斷言失敗。
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent
CDW_PATH = HOOKS / "context-depth-warning-hook.py"
AUDIT_PATH = HOOKS / "memory-dir-audit-hook.py"
CDW_STATE = "context-depth-warning/context-depth-warning-state.json"
CDW_LOG = "context-depth-warning/context-depth-warning.log"
MARKER = "memory-dir-audit/memory-dir-audit-marker.json"
DEEP = 450_000  # >= THRESHOLD 400K
SHALLOW = 10_000


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repos(tmp_path, monkeypatch):
    from lib import hook_base

    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("x", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    for name in (
        "HOOK_TEST_ISOLATION",
        "CLAUDE_PROJECT_DIR",
        "CONTEXT_DEPTH_WARNING_STATE",
        "MEMORY_DIR_AUDIT_MARKER_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(wt)
    hook_base.clear_project_root_cache()
    yield main, wt
    hook_base.clear_project_root_cache()


def _transcript(tmp_path, tokens, name="t.jsonl"):
    p = tmp_path / name
    entry = {
        "message": {
            "role": "assistant",
            "usage": {
                "input_tokens": tokens,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }
    }
    p.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return p


def _run_cdw(cwd, tmp_path, session, tokens):
    """以 subprocess 在 cwd 跑 context-depth-warning，回傳 (rc, stdout)。"""
    t = _transcript(tmp_path, tokens, name=f"{session}-{tokens}.jsonl")
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("HOOK_TEST_ISOLATION", "CLAUDE_PROJECT_DIR")
    }
    proc = subprocess.run(
        [sys.executable, str(CDW_PATH)],
        input=json.dumps({"session_id": session, "transcript_path": str(t)}),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=env,
    )
    return proc.returncode, proc.stdout


def _hook_logs(root):
    return root / ".claude" / "hook-logs"


def _state(root):
    p = _hook_logs(root) / CDW_STATE
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def test_cdw_main_checkout_writes_main_hook_logs(repos, tmp_path):
    main, wt = repos
    rc, out = _run_cdw(main, tmp_path, "s1", DEEP)
    assert rc == 0
    assert "context-depth-warning" in out
    assert _state(main) == {"s1": DEEP // 50_000}
    assert (_hook_logs(main) / CDW_LOG).is_file()


def test_cdw_linked_worktree_state_and_log_land_in_main(repos, tmp_path):
    main, wt = repos
    rc, out = _run_cdw(wt, tmp_path, "s1", DEEP)
    assert rc == 0
    assert "context-depth-warning" in out
    assert _state(main) == {"s1": DEEP // 50_000}
    assert (_hook_logs(main) / CDW_LOG).is_file()
    assert not (_hook_logs(wt) / CDW_STATE).exists()
    assert not list(wt.rglob("context-depth-warning-state.json"))


def test_cdw_same_session_dedup_merges_across_checkouts(repos, tmp_path):
    """同 session、同 tier 先後在兩個 checkout 觸發：第二次因共用 state 不再提醒。"""
    main, wt = repos
    _, first = _run_cdw(main, tmp_path, "s1", DEEP)
    rc, second = _run_cdw(wt, tmp_path, "s1", DEEP)
    assert "context-depth-warning" in first
    assert rc == 0
    assert second.strip() == ""


def test_cdw_different_sessions_do_not_overwrite_each_other(repos, tmp_path):
    """兩個 session 各在一個 checkout 寫 state：以 session_id 分鍵，不互蓋。"""
    main, wt = repos
    _run_cdw(main, tmp_path, "sA", DEEP)
    _run_cdw(wt, tmp_path, "sB", DEEP + 100_000)
    state = _state(main)
    assert state == {"sA": DEEP // 50_000, "sB": (DEEP + 100_000) // 50_000}


def test_cdw_below_threshold_clears_only_own_session(repos, tmp_path):
    main, wt = repos
    _run_cdw(main, tmp_path, "sA", DEEP)
    _run_cdw(main, tmp_path, "sB", DEEP)
    _run_cdw(wt, tmp_path, "sA", SHALLOW)
    assert _state(main) == {"sB": DEEP // 50_000}


def _load_audit():
    spec = importlib.util.spec_from_file_location("audit_g2", AUDIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_audit_marker_default_path_is_main_hook_logs(repos):
    main, wt = repos
    mod = _load_audit()
    assert mod._marker_file() == _hook_logs(main) / MARKER


def test_audit_marker_written_to_main_from_worktree(repos, tmp_path):
    main, wt = repos
    mem = tmp_path / "memdir"
    mem.mkdir()
    (mem / "a.md").write_text("x", encoding="utf-8")
    mod = _load_audit()
    mod.resolve_candidate_memory_dirs = lambda: [str(mem)]
    calls = []
    mod.emit_model_reminder = lambda *a, **k: calls.append(a)
    inp = {"hook_event_name": "Stop", "session_id": "s"}
    logger = mod.setup_hook_logging("memory-dir-audit")
    assert mod._run_audit(logger, mod._marker_file(), inp) == 0
    marker = _hook_logs(main) / MARKER
    assert json.loads(marker.read_text(encoding="utf-8")) == {str(mem): ["a.md"]}
    assert not list(wt.rglob("memory-dir-audit-marker.json"))
    assert len(calls) == 1


def test_audit_marker_dedup_merges_across_checkouts(repos, tmp_path, monkeypatch):
    """主 checkout 先記錄過同一快照，worktree 啟動後不再重複提醒。"""
    main, wt = repos
    mem = tmp_path / "memdir"
    mem.mkdir()
    (mem / "a.md").write_text("x", encoding="utf-8")
    marker = _hook_logs(main) / MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({str(mem): ["a.md"]}), encoding="utf-8")
    mod = _load_audit()
    mod.resolve_candidate_memory_dirs = lambda: [str(mem)]
    calls = []
    mod.emit_model_reminder = lambda *a, **k: calls.append(a)
    logger = mod.setup_hook_logging("memory-dir-audit")
    inp = {"hook_event_name": "Stop", "session_id": "s"}
    assert mod._run_audit(logger, mod._marker_file(), inp) == 0
    assert calls == []
