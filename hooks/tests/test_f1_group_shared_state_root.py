"""F1 組（comment-qa、tripwire signals）讀共用狀態（SR）改走 get_shared_state_root（3.3.0-W1-204.1.2.13）。

fixture：真實 linked worktree，不設 HOOK_TEST_ISOLATION。
正向：WT 內讀到 MAIN 平面；E1 對照：同一輸入在 HOOK_TEST_ISOLATION=1 下讀 WT 平面而找不到。
"""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[2]
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

COMMENT_QA = (
    CLAUDE_DIR / "skills" / "dart-comment-traceability" / "hooks" / "comment-qa-hook.py"
)
TRIPWIRE_DIR = CLAUDE_DIR / "skills" / "wrap-decision" / "hooks"
TICKET_ID = "1.0.0-W1-001"


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
    # MAIN 平面的共用狀態；WT 平面刻意不放
    logs = main / "docs" / "work-logs"
    logs.mkdir(parents=True)
    (logs / "v1.0.0.md").write_text("log\n", encoding="utf-8")
    tickets = logs / "v1.0.0" / "tickets"
    tickets.mkdir(parents=True)
    (tickets / f"{TICKET_ID}.md").write_text(
        f"---\nid: {TICKET_ID}\ntype: ANA\n---\n\n# T\n\n## Solution\n\n", encoding="utf-8"
    )
    return main, wt


def _load_comment_qa():
    spec = importlib.util.spec_from_file_location("f1_comment_qa", COMMENT_QA)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["f1_comment_qa"] = mod
    spec.loader.exec_module(mod)
    return mod


def _detect_s3():
    if str(TRIPWIRE_DIR) not in sys.path:
        sys.path.insert(0, str(TRIPWIRE_DIR))
    from tripwire.signals import AnaClaimStrategy

    sd = SimpleNamespace(
        id="ana_claim", tool_matcher="Bash",
        command_pattern=r"ticket track claim", ticket_type_filter="ANA",
    )
    event = {"tool_name": "Bash", "tool_input": {"command": f"ticket track claim {TICKET_ID}"}}
    return AnaClaimStrategy().detect(event, {}, sd, None, logging.getLogger("t"))


def test_comment_qa_reads_main_work_logs(linked_worktree):
    main, wt = linked_worktree
    mod = _load_comment_qa()
    assert mod.PROJECT_ROOT == wt
    assert mod.find_related_work_log() == main / "docs" / "work-logs" / "v1.0.0.md"


def test_comment_qa_e1_isolation_reads_worktree_plane(linked_worktree, monkeypatch):
    mod = _load_comment_qa()
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    assert mod.find_related_work_log() is None  # WT 無 work-logs


def test_signals_s3_reads_main_ticket(linked_worktree):
    assert _detect_s3().hit is True


def test_comment_qa_e1_identity_old_code_misses_main(linked_worktree, monkeypatch):
    """E1：get_shared_state_root 換成恆等函式（等於舊碼）後讀不到 MAIN 的工作日誌。"""
    main, _ = linked_worktree
    mod = _load_comment_qa()
    assert mod.find_related_work_log() == main / "docs" / "work-logs" / "v1.0.0.md"
    monkeypatch.setattr(mod, "get_shared_state_root", lambda r=None: r)
    assert mod.find_related_work_log() is None


def test_signals_s3_e1_identity_old_code_misses_main_ticket(linked_worktree, monkeypatch):
    """E1：換成恆等函式後讀 WT 票，S3 不命中；換回新碼則命中。"""
    assert _detect_s3().hit is True
    import tripwire.signals as signals

    monkeypatch.setattr(signals, "get_shared_state_root", lambda r=None: r)
    assert _detect_s3().hit is False


def test_signals_s3_e1_isolation_reads_worktree_plane(linked_worktree, monkeypatch):
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    assert _detect_s3().hit is False
