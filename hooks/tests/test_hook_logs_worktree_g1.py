"""G1 hooks 的 hook-logs 寫入路徑在 linked worktree 下須落主 checkout（3.3.0-W1-204.1.6.1）。

fixture：tmp 主 repo + linked worktree，cwd 與 CLAUDE_PROJECT_DIR 設為 worktree，
不設 HOOK_TEST_ISOLATION。舊寫法經 get_project_root() 拼接，日誌落 worktree 根；
新寫法經 get_hook_log_dir，落主 repo。
"""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[2]
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

PARALLEL = CLAUDE_DIR / "hooks" / "parallel-suggestion-hook.py"
POST_TEST = CLAUDE_DIR / "hooks" / "post-test-hook.py"
HANDOFF = CLAUDE_DIR / "skills" / "ticket" / "hooks" / "handoff-cleanup-hook.py"
COMMENT_QA = (
    CLAUDE_DIR / "skills" / "dart-comment-traceability" / "hooks" / "comment-qa-hook.py"
)


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


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _assert_only_main(main: Path, wt: Path, pattern: str) -> None:
    assert list((main / ".claude" / "hook-logs").rglob(pattern)), "主 repo 無日誌"
    assert not list((wt / ".claude" / "hook-logs").rglob(pattern)), "日誌誤落 worktree"


def test_parallel_suggestion_log_in_main(linked_worktree):
    main, wt = linked_worktree
    mod = _load(PARALLEL, "g1_parallel")
    mod.save_analysis_log(False, None, 2, logging.getLogger("t"))
    _assert_only_main(main, wt, "analysis-*.log")


def test_post_test_evaluation_in_main(linked_worktree):
    main, wt = linked_worktree
    mod = _load(POST_TEST, "g1_post_test")
    mod._log_evaluation(next(iter(mod.ErrorType)), [], logging.getLogger("t"))
    _assert_only_main(main, wt, "pre-fix-evaluation-*.json")


def test_handoff_cleanup_report_in_main(linked_worktree):
    main, wt = linked_worktree
    mod = _load(HANDOFF, "g1_handoff")
    (main / ".claude" / "hook-logs" / "handoff-cleanup").mkdir(parents=True)
    mod.generate_summary_log(wt, [], logging.getLogger("t"))
    _assert_only_main(main, wt, "cleanup-report-*.json")


def test_comment_qa_report_dir_in_main(linked_worktree):
    main, wt = linked_worktree
    mod = _load(COMMENT_QA, "g1_comment_qa")
    assert main / ".claude" / "hook-logs" in mod.REPORT_DIR.parents
    assert wt not in mod.REPORT_DIR.parents
