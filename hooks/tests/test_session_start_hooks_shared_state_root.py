"""SessionStart 六處讀共用狀態的根改用 get_shared_state_root（3.3.0-W1-204.1.2.3）。

以真實 git 建立主 repo（MAIN）與 linked worktree（WT），不 mock git。
共用狀態（todolist、work-logs、registry、票面）只存在於 MAIN 且不入 WT 的
checkout，cwd 在 WT 時新版必須讀到 MAIN，舊版（get_project_root）讀到 WT。

情境：
- B：cwd 與 CLAUDE_PROJECT_DIR 都在 WT
- C：CLAUDE_PROJECT_DIR=MAIN、cwd=WT（cd 進 WT 後 compact／resume）

隔離：fixture 全程只在 tmp_path 內操作；HOOK_TEST_ISOLATION 僅在 fixture
內解除以走真實解析，測試結束由 monkeypatch 還原。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lib import hook_base

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
SCRIPTS_DIR = CLAUDE_DIR / "skills" / "framework-issue" / "scripts"
AUDIT_HOOK = CLAUDE_DIR / "skills" / "worktree" / "hooks" / "session-start-merged-worktree-audit-hook.py"

TICKET_REL = "docs/work-logs/v3/v3.3/v3.3.0/tickets/3.3.0-W1-001.md"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _load(name: str, path: Path):
    for p in (str(HOOKS_DIR), str(CLAUDE_DIR), str(path.parent)):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["B", "C"])
def scenario(request, tmp_path, monkeypatch):
    """回傳 (main, wt)；cwd 已切到 WT，env 依情境設定。"""
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("x", encoding="utf-8")
    ticket = main / TICKET_REL
    ticket.parent.mkdir(parents=True)
    ticket.write_text("---\nid: 3.3.0-W1-001\nstatus: pending\n---\n", encoding="utf-8")
    _git(main, "add", "CLAUDE.md", TICKET_REL)
    _git(main, "commit", "-q", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))

    # 共用狀態：只存在 MAIN（未提交，不進 WT checkout）
    (main / "docs").mkdir(exist_ok=True)
    (main / "docs" / "todolist.yaml").write_text(
        "versions:\n- version: 3.3.0\n  status: active\ntickets:\n- id: a\n  status: pending\n",
        encoding="utf-8",
    )
    (main / "docs" / "error-patterns").mkdir()
    state = main / ".claude" / "state"
    state.mkdir(parents=True)
    ticket.write_text("---\nid: 3.3.0-W1-001\nstatus: completed\n---\n", encoding="utf-8")

    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt if request.param == "B" else main))
    monkeypatch.chdir(wt)
    hook_base.clear_project_root_cache()
    yield main, wt
    hook_base.clear_project_root_cache()


# ---------- doc-sync-check ----------

def test_doc_sync_reads_main_state(scenario):
    main, wt = scenario
    hook = _load("doc_sync_check_hook", HOOKS_DIR / "doc-sync-check-hook.py")
    assert not (wt / "docs" / "todolist.yaml").exists()  # 對照：WT 沒有
    assert hook.check_todolist() == {"exists": True, "has_pending_items": True, "pending_count": 1}
    assert hook.check_error_patterns()["exists"] is True
    assert hook.get_latest_version() == "3.3.0"


# ---------- tech-debt-reminder ----------

def test_tech_debt_reminder_uses_main_root(scenario, monkeypatch):
    main, _ = scenario
    hook = _load("tech_debt_reminder", HOOKS_DIR / "tech-debt-reminder.py")
    seen = []
    monkeypatch.setattr(hook, "setup_hook_logging", lambda n: MagicMock())
    monkeypatch.setattr(hook, "read_json_from_stdin", lambda logger: {"k": 1})
    monkeypatch.setattr(
        hook, "get_current_version_from_todolist", lambda root, logger: seen.append(root)
    )
    hook.main()
    assert seen == [main]


# ---------- version-consistency-guard ----------

def test_version_consistency_guard_uses_main_root(scenario, monkeypatch):
    main, _ = scenario
    hook = _load("version_consistency_guard_hook", HOOKS_DIR / "version-consistency-guard-hook.py")
    seen = []

    class _Stop(Exception):
        pass

    def _record(root, logger):
        seen.append(root)
        raise _Stop

    monkeypatch.setattr(hook, "setup_hook_logging", lambda n: MagicMock())
    monkeypatch.setattr(hook, "get_registered_versions", _record)
    with pytest.raises(_Stop):
        hook.main()
    assert seen == [main]


# ---------- session-start-scheduler-hint ----------

def test_scheduler_hint_spawned_and_needs_context_use_main_root(scenario, monkeypatch):
    main, _ = scenario
    hook = _load("session_start_scheduler_hint_hook", HOOKS_DIR / "session-start-scheduler-hint-hook.py")
    spawned, needs = [], []
    monkeypatch.setattr(
        hook, "scan_spawned_pending", lambda root, v, logger: spawned.append((root, v)) or []
    )
    monkeypatch.setattr(
        hook, "scan_needs_context_handoffs", lambda root, logger: needs.append(root) or []
    )
    hook.fetch_spawned_pending_context(MagicMock())
    hook.fetch_needs_context_section(MagicMock())
    # 真實 _detect_active_version 讀 MAIN todolist -> 取得 3.3.0（WT 無 todolist 會是 None）
    assert spawned == [(main, "3.3.0")]
    assert needs == [main]


# ---------- todo_pending_registry（todo-delta 走此路） ----------

def test_registry_path_wraps_shared_root_when_root_passed(scenario):
    main, wt = scenario
    sys.path.insert(0, str(SCRIPTS_DIR))
    import todo_pending_registry as registry

    reg = main / ".claude" / "state" / "framework-issue-todo-pending.json"
    reg.write_text(
        json.dumps({"schema_version": registry.SCHEMA_VERSION, "pending": [{"issue": 1}]}),
        encoding="utf-8",
    )
    # registry_path 傳入根優先（不再包共用根）；共用根由呼叫端（hook／section_comment）傳入
    assert registry.registry_path(wt) == wt / ".claude" / "state" / reg.name
    assert registry.pending_entries(project_root=wt) is None
    shared = hook_base.get_shared_state_root(wt)
    assert registry.registry_path(shared) == reg
    assert registry.pending_entries(project_root=shared) == [{"issue": 1}]
    # 未傳入根：回推主 repo
    assert registry.pending_entries() == [{"issue": 1}]


# ---------- session-start-merged-worktree-audit ----------

def test_merged_worktree_audit_reads_main_ticket_state(scenario, monkeypatch, capsys):
    main, _ = scenario
    hook = _load("session_start_merged_worktree_audit_hook", AUDIT_HOOK)
    monkeypatch.setattr(hook, "setup_hook_logging", lambda n: MagicMock())
    monkeypatch.setattr(hook, "read_json_from_stdin", lambda logger: {})
    monkeypatch.setattr(hook, "collect_merged_user_worktrees", lambda logger: [])
    monkeypatch.setattr(hook, "collect_orphan_agent_branches", lambda logger, reason_out=None: [])
    assert hook.main() == 0
    # MAIN 有「completed 但未提交」的票；WT 乾淨。新版應列出該票
    assert "3.3.0-W1-001" in capsys.readouterr().out
