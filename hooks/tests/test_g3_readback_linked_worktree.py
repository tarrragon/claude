"""G3 讀回狀態三支 hook 在 linked worktree 內的讀寫落點測試（3.3.0-W1-204.1.6.8）。

不設 HOOK_TEST_ISOLATION：以真實 git linked worktree 驗證讀寫兩端都經
get_hook_log_dir，落在主 repo 的 .claude/hook-logs。
"""

import importlib.util
import io
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
if str(_HOOKS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR.parent))

_LOG = logging.getLogger("g3-readback-test")


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, _HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def checkouts(tmp_path, monkeypatch):
    """主 checkout 與 linked worktree；cwd 在 worktree，CLAUDE_PROJECT_DIR 指向 worktree。"""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("# t\n", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wt-branch")
    main, wt = main.resolve(), wt.resolve()
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    monkeypatch.chdir(wt)
    return main, wt


def _enter(monkeypatch, root: Path) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.chdir(root)


# ---------------------------------------------------------------------------
# parallel-claim-audit（寫入 audit log）
# ---------------------------------------------------------------------------

_TID = "0.19.0-W3-048"


def _seed_ticket(main: Path) -> None:
    tickets = main / "docs" / "work-logs" / "v0" / "v0.19" / "v0.19.0" / "tickets"
    tickets.mkdir(parents=True)
    (tickets / f"{_TID}.md").write_text(
        f"---\nid: {_TID}\nstatus: in_progress\nstarted_at: '{datetime.now().isoformat(timespec='seconds')}'\n"
        f"who:\n  current: pm\n---\n\n# {_TID}\n",
        encoding="utf-8",
    )


def _claim(hook, monkeypatch) -> int:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "ticket track claim " + _TID},
        "tool_result": {"stdout": "claimed", "stderr": ""},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return hook.main()


def _audit_file(root: Path) -> Path:
    return root / ".claude" / "hook-logs" / "parallel-claim-audit-hook" / "parallel-claim-audit.log"


def test_audit_entries_from_both_checkouts_land_in_main_hook_log_dir(checkouts, monkeypatch):
    main, wt = checkouts
    _seed_ticket(main)
    hook = _load("pca_under_test", "parallel-claim-audit-hook.py")

    assert _claim(hook, monkeypatch) == 0  # worktree 啟動
    _enter(monkeypatch, main)
    assert _claim(hook, monkeypatch) == 0  # 主 checkout 啟動

    assert _audit_file(main).exists()
    lines = _audit_file(main).read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["ticket_id"] for x in lines] == [_TID, _TID]
    assert not _audit_file(wt).exists()


# ---------------------------------------------------------------------------
# framework-rule-edit-skill-trigger（cache 讀寫）
# ---------------------------------------------------------------------------


def _cache_file(root: Path, session_id: str) -> Path:
    return (
        root / ".claude" / "hook-logs" / "framework-rule-edit-skill-trigger"
        / f"skill-trigger-cache-{session_id}.json"
    )


def test_skill_trigger_cache_written_and_read_in_main(checkouts, monkeypatch):
    main, wt = checkouts
    hook = _load("skill_trigger_under_test", "framework-rule-edit-skill-trigger-hook.py")

    hook._save_cache("sid-1", {"a.md"}, _LOG)

    assert _cache_file(main, "sid-1").exists()
    assert json.loads(_cache_file(main, "sid-1").read_text(encoding="utf-8"))["warned_paths"] == ["a.md"]
    assert not _cache_file(wt, "sid-1").exists()
    assert hook._load_cache("sid-1", _LOG) == {"a.md"}


def test_skill_trigger_cache_shared_across_checkouts_for_same_session(checkouts, monkeypatch):
    main, wt = checkouts
    hook = _load("skill_trigger_under_test2", "framework-rule-edit-skill-trigger-hook.py")

    hook._save_cache("sid-2", {"a.md"}, _LOG)  # worktree 啟動寫入
    _enter(monkeypatch, main)
    assert hook._load_cache("sid-2", _LOG) == {"a.md"}  # 主 checkout 啟動讀回同一份
    assert hook._load_cache("sid-other", _LOG) == set()  # 不同 session 仍隔離


# ---------------------------------------------------------------------------
# session-context-guard（讀 line-board 寫入的 context 用量檔）
# ---------------------------------------------------------------------------


def _usage_file(root: Path, session_id: str) -> Path:
    return root / ".claude" / "hook-logs" / "line-board" / "context" / f"{session_id}.json"


def test_context_usage_read_from_main_in_worktree(checkouts, monkeypatch):
    main, wt = checkouts
    hook = _load("scg_under_test", "session-context-guard-hook.py")
    record = {
        "sessionId": "sess-1", "phase": None, "tokens": 1, "window": 100, "percent": 50,
        "compactWindow": None, "compactPercent": None, "autoCompactThreshold": None, "measuredAt": 0,
    }
    path = _usage_file(main, "sess-1")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record), encoding="utf-8")

    assert hook.usage_file_path("sess-1") == path
    assert hook.read_usage_record({"session_id": "sess-1"}, _LOG)["percent"] == 50


def test_context_usage_path_is_derived_via_get_hook_log_dir(tmp_path, monkeypatch):
    """路徑必須經 get_hook_log_dir：替換它，用量檔路徑要跟著走（舊碼直接用 get_shared_state_root）。"""
    hook = _load("scg_under_test2", "session-context-guard-hook.py")
    seen = []

    def fake(name):
        seen.append(name)
        return tmp_path / name

    monkeypatch.setattr(hook, "get_hook_log_dir", fake, raising=False)

    assert hook.usage_file_path("s1") == tmp_path / "line-board" / "context" / "s1.json"
    assert seen == ["line-board"]
