"""linked worktree 內讀共用狀態一律讀主倉庫（0.5.0-W1-264.4）。

每個案例建主倉庫加 linked worktree，兩邊狀態內容刻意不同，cwd 為 worktree，
斷言讀到的是主倉庫那份。變異確認：把讀取點改回 get_project_root 時翻紅。
"""

import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import hook_base
from lib.hook_base import has_parallel_dispatch
from lib.hook_ticket import extract_where_files, find_ticket_file

HOOKS = Path(__file__).parent.parent
TICKET_ID = "0.5.0-W1-900"


def _load(filename, name):
    spec = importlib.util.spec_from_file_location(name, HOOKS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _ticket(root, status, files):
    d = root / "docs" / "work-logs" / "v0.5.0" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    body = "\n".join("  - " + f for f in files)
    (d / (TICKET_ID + ".md")).write_text(
        "---\nid: %s\nstatus: %s\nwhere:\n  files:\n%s\n---\n\n# t\n"
        % (TICKET_ID, status, body),
        encoding="utf-8",
    )


def _dispatch(root, entries):
    p = root / ".claude" / "dispatch-active.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"dispatches": entries}), encoding="utf-8")


@pytest.fixture
def repos(tmp_path, monkeypatch):
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
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(wt)
    hook_base.clear_project_root_cache()
    yield main, wt
    hook_base.clear_project_root_cache()


ENTRY = {
    "agent_id": "a1",
    "agent_description": "d",
    "ticket_id": TICKET_ID,
    "session_id": "s1",
    "dispatched_at": "2026-10-14T00:00:00+00:00",
    "turn_ended_at": "2026-10-14T00:01:00+00:00",
    "files": [],
}


def test_has_parallel_dispatch_reads_main_repo(repos):
    main, wt = repos
    _dispatch(main, [ENTRY])
    _dispatch(wt, [])
    assert has_parallel_dispatch() is True
    assert has_parallel_dispatch(wt) is True


def test_has_parallel_dispatch_main_empty_wt_nonempty(repos):
    main, wt = repos
    _dispatch(main, [])
    _dispatch(wt, [ENTRY])
    assert has_parallel_dispatch(wt) is False


def test_has_parallel_dispatch_failure_is_non_parallel(repos):
    main, wt = repos
    p = main / ".claude" / "dispatch-active.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    assert has_parallel_dispatch(wt) is False


def test_process_skip_guard_reads_main_dispatch(repos):
    main, wt = repos
    _dispatch(main, [ENTRY])
    _dispatch(wt, [])
    mod = _load("process-skip-guard-hook.py", "psg_wt")
    assert mod.has_active_dispatch() is True


def test_process_skip_guard_main_empty_wt_nonempty(repos):
    main, wt = repos
    _dispatch(main, [])
    _dispatch(wt, [ENTRY])
    mod = _load("process-skip-guard-hook.py", "psg_wt2")
    assert mod.has_active_dispatch() is False


def test_session_registry_main_scan_reads_main_state(repos, tmp_path, capsys):
    main, wt = repos
    _dispatch(main, [ENTRY])
    _ticket(main, "completed", ["a.py"])
    _dispatch(wt, [])
    _ticket(wt, "in_progress", ["a.py"])
    mod = _load("session-registry-start-hook.py", "srs_wt")
    with patch.object(mod, "read_json_from_stdin", return_value={"session_id": "self"}), \
         patch.object(mod, "is_subagent_environment", return_value=False), \
         patch.object(mod, "get_registry_paths",
                      return_value=(tmp_path / "reg.json", tmp_path / "reg.lock")), \
         patch.object(mod, "register_session"):
        assert mod.main() == 0
    out = capsys.readouterr().out
    assert "現況：completed" in out


def test_find_ticket_file_default_root_reads_main(repos):
    main, wt = repos
    _ticket(main, "completed", ["a.py"])
    _ticket(wt, "in_progress", ["b.py"])
    found = find_ticket_file(TICKET_ID)
    assert found is not None
    assert Path(found).resolve() == (
        main / "docs" / "work-logs" / "v0.5.0" / "tickets" / (TICKET_ID + ".md")
    ).resolve()


def test_extract_where_files_default_root_reads_main(repos):
    main, wt = repos
    _ticket(main, "completed", ["main_only.py"])
    _ticket(wt, "in_progress", ["wt_only.py"])
    assert extract_where_files(TICKET_ID) == ["main_only.py"]
