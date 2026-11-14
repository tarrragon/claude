"""handoff_utils 未傳根時票面讀取 fallback 走 get_ticket_state_root（3.3.0-W1-204.1.2.12）。

真實 linked worktree：cwd 在 WT，票只存在 MAIN；未傳根時須讀到 MAIN 的票。
"""

import subprocess
from pathlib import Path

import pytest

from ticket_system.lib import handoff_utils
from ticket_system.lib.paths import (
    get_project_root,
    reset_project_root_cache,
    reset_ticket_state_root_cache,
)

TICKET_ID = "0.1.0-W1-901"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def wt_with_main_ticket(tmp_path, monkeypatch):
    main, wt = tmp_path / "main", tmp_path / "wt"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "checkout", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "T")
    (main / "README.md").write_text("init\n", encoding="utf-8")
    _git(main, "add", ".")
    _git(main, "commit", "-q", "-m", "init")
    _git(main, "worktree", "add", "-q", "-b", "feat/x", str(wt), "HEAD")
    # 票只存在 MAIN（未追蹤檔，WT 看不到）
    tdir = main / ".claude" / "tickets"
    tdir.mkdir(parents=True)
    (tdir / f"{TICKET_ID}.md").write_text(
        f"---\nid: {TICKET_ID}\nstatus: completed\n---\nbody\n", encoding="utf-8"
    )

    monkeypatch.delenv("TICKET_SYSTEM_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    reset_project_root_cache()
    reset_ticket_state_root_cache()
    monkeypatch.chdir(wt)
    yield main, wt
    reset_project_root_cache()
    reset_ticket_state_root_cache()


def test_load_status_without_root_reads_main(wt_with_main_ticket):
    assert handoff_utils._load_ticket_status(TICKET_ID) == "completed"


def test_is_ticket_missing_without_root_reads_main(wt_with_main_ticket):
    assert handoff_utils.is_ticket_missing(TICKET_ID) is False


def test_explicit_root_unchanged(wt_with_main_ticket):
    _, wt = wt_with_main_ticket
    assert handoff_utils._load_ticket_status(TICKET_ID, project_root=wt) is None


def test_e1_contrast_project_root_fallback_fails(wt_with_main_ticket, monkeypatch):
    """E1：fallback 換回 get_project_root（落到 WT）時，讀不到 MAIN 的票。"""
    monkeypatch.setattr(handoff_utils, "get_ticket_state_root", get_project_root)
    assert handoff_utils._load_ticket_status(TICKET_ID) is None
    assert handoff_utils.is_ticket_missing(TICKET_ID) is True
