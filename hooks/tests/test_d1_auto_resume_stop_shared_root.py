"""D1：handoff-auto-resume-stop 的 pending 掃描、票面讀取、archive 寫入同用共用狀態根
（3.3.0-W1-204.1.2.10）。

fixture：真實 tmp 主 repo + linked worktree，cwd 與 CLAUDE_PROJECT_DIR 設為 worktree，
不設 HOOK_TEST_ISOLATION。.stop-blocked flag 仍落 session 根（WT）。
"""

import importlib.util
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills" / "ticket" / "hooks" / "handoff-auto-resume-stop-hook.py"
)
TICKET_ID = "9.9.9-W1-001"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True,
    )


@pytest.fixture
def linked_worktree(tmp_path, monkeypatch):
    main = (tmp_path / "main").resolve()
    main.mkdir()
    (main / "CLAUDE.md").write_text("# t\n", encoding="utf-8")
    _git(main, "init", "-q", "-b", "main")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wt-branch")
    monkeypatch.chdir(wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    return main, wt


def _load_hook(monkeypatch, *, stale: bool = False):
    spec = importlib.util.spec_from_file_location("d1_stop_hook", HOOK_PATH)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    # 票面判定與根無關，固定為「有效 pending」，只驗證掃描落在哪個根
    monkeypatch.setattr(hook, "_lib_orphan_reason", lambda r, t, project_root=None: "")
    monkeypatch.setattr(hook, "is_handoff_stale",
                        lambda r, project_root=None: (stale, "stale" if stale else ""))
    monkeypatch.setattr(hook, "is_ticket_completed", lambda root, tid, log: False)
    monkeypatch.setattr(hook, "is_ticket_recently_started",
                        lambda root, tid, log, cache=None: False)
    monkeypatch.setattr(hook, "read_session_state", lambda logger, input_data=None: None)
    return hook


def _write_pending(root: Path) -> Path:
    pending = root / ".claude" / "handoff" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    path = pending / f"{TICKET_ID}.json"
    path.write_text(json.dumps({
        "ticket_id": TICKET_ID,
        "direction": "context_refresh",
        "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
        "title": "d1",
        "resumed_at": None,
    }), encoding="utf-8")
    return path


def _flag(root: Path) -> Path:
    return root / ".claude" / "handoff" / ".stop-blocked"


def test_wt_session_blocks_on_main_pending_and_flag_stays_in_wt(
    linked_worktree, monkeypatch
):
    """正向對照：MAIN 有會擋的 pending，WT session 停止 → block；flag 落 WT 根。"""
    main, wt = linked_worktree
    _write_pending(main)
    hook = _load_hook(monkeypatch)

    out = hook.generate_hook_output(logging.getLogger("d1"), input_data={})

    assert out.get("decision") == "block"
    assert _flag(wt).exists(), "flag 應落在 session（WT）根"
    assert not _flag(main).exists(), "flag 不得落到 MAIN 根"


def test_wt_session_archives_stale_main_pending_into_main_archive(
    linked_worktree, monkeypatch
):
    """stale pending 歸檔到 MAIN 的 archive，WT 內不產生 archive。"""
    main, wt = linked_worktree
    src = _write_pending(main)
    hook = _load_hook(monkeypatch, stale=True)

    hook.generate_hook_output(logging.getLogger("d1"), input_data={})

    assert not src.exists()
    assert list((main / ".claude" / "handoff" / "archive").rglob("*.json"))
    assert not (wt / ".claude" / "handoff" / "archive").exists()


def test_e1_identity_state_root_reverts_to_allow(linked_worktree, monkeypatch):
    """E1 對照：get_shared_state_root 換成恆等函式 → WT 掃空目錄，變回放行。"""
    main, wt = linked_worktree
    _write_pending(main)
    hook = _load_hook(monkeypatch)
    monkeypatch.setattr(hook, "get_shared_state_root", lambda default_root=None: default_root)

    out = hook.generate_hook_output(logging.getLogger("d1"), input_data={})

    assert out.get("decision") != "block"
    assert out == {"suppressOutput": True}
