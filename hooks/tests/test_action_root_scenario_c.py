"""
Test: get_action_root 與四支守衛的情境 C（env=MAIN、payload.cwd=WT）

情境 C：CLAUDE_PROJECT_DIR / get_project_root 指向主 repo，payload.cwd 在
linked worktree。作用面（staged 檔、git status、pubspec/CHANGELOG）須以 WT 判定。
每支守衛含正向對照（WT 上應擋的輸入被擋）與反向對照（MAIN 有、WT 沒有的
狀態不影響判定）；用真實 git repo / worktree，不 mock 偵測函式。

Source: ticket 3.3.0-W1-204.1.3.1（判定表 AR 列，3.3.0-W1-204.1）
"""

import importlib.util
import io
import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))

from lib.git_utils import get_action_root  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True, capture_output=True,
    )


@pytest.fixture
def main_and_wt(tmp_path):
    main_repo = tmp_path / "main"
    main_repo.mkdir()
    _git(main_repo, "init", "-q", "-b", "main")
    (main_repo / "a.txt").write_text("a\n")
    (main_repo / "pubspec.yaml").write_text("version: 1.0.0\n")
    (main_repo / "CHANGELOG.md").write_text("## [1.0.0]\n")
    _git(main_repo, "add", ".")
    _git(main_repo, "commit", "-q", "-m", "base")
    wt = tmp_path / "wt"
    _git(main_repo, "worktree", "add", "-q", "-b", "wtbr", str(wt), "main")
    return main_repo, wt


# ============================================================================
# get_action_root：四種 cwd
# ============================================================================


class TestGetActionRoot:
    def test_cwd_in_main_repo(self, main_and_wt, monkeypatch):
        main_repo, wt = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        sub = main_repo / "sub"
        sub.mkdir()
        assert get_action_root({"cwd": str(sub)}) == main_repo

    def test_cwd_in_linked_worktree_ignores_env(self, main_and_wt, monkeypatch):
        main_repo, wt = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        assert get_action_root({"cwd": str(wt)}) == wt

    def test_cwd_outside_repo_falls_back(self, tmp_path, main_and_wt, monkeypatch, capsys):
        main_repo, _ = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        outside = tmp_path / "outside"
        outside.mkdir()
        assert get_action_root({"cwd": str(outside)}) == main_repo
        assert "get_action_root" in capsys.readouterr().err

    def test_missing_cwd_falls_back(self, main_and_wt, monkeypatch, capsys):
        main_repo, _ = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        assert get_action_root({}) == main_repo
        assert get_action_root(None) == main_repo
        assert "缺 cwd" in capsys.readouterr().err


# ============================================================================
# bare-commit-guard：staged 檔（AR）
# ============================================================================

_bare = _load("bare_commit_guard_hook_c", HOOKS_DIR / "bare-commit-guard-hook.py")


def _run_bare(monkeypatch, main_repo: Path, wt: Path) -> int:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m x"},
        "cwd": str(wt),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(_bare, "get_project_root", lambda: main_repo)
    dispatches = [{"files": ["ok.txt"]}, {"files": ["other.txt"]}]
    monkeypatch.setattr(_bare, "_get_active_dispatches_safe", lambda r: dispatches)
    monkeypatch.setattr(_bare, "_exclude_orphan_confirmed", lambda d, *a, **k: d)
    monkeypatch.setattr(_bare, "_with_live_declared_files", lambda d, *a, **k: d)
    return _bare.main()


def _stage(repo: Path, *names: str) -> None:
    for n in names:
        (repo / n).write_text(n)
    _git(repo, "add", *names)


class TestBareCommitGuardScenarioC:
    def test_wt_staged_cross_dispatch_blocked(self, monkeypatch, main_and_wt):
        """正向對照：WT 夾帶兩個派發的檔案 → 擋（舊碼讀 MAIN index 為空而放行）。"""
        main_repo, wt = main_and_wt
        _stage(wt, "ok.txt", "other.txt")
        assert _run_bare(monkeypatch, main_repo, wt) == 2

    def test_main_staged_does_not_affect_wt_judgement(self, monkeypatch, main_and_wt):
        """反向對照：MAIN 夾帶、WT 只有單一派發範圍 → 放行。"""
        main_repo, wt = main_and_wt
        _stage(main_repo, "ok.txt", "other.txt")
        _stage(wt, "ok.txt")
        assert _run_bare(monkeypatch, main_repo, wt) == 0


# ============================================================================
# workspace-wipe-guard：未提交檔（AR）
# ============================================================================

_wipe = _load("workspace_wipe_guard_hook_c", HOOKS_DIR / "workspace-wipe-guard-hook.py")


def _run_wipe(monkeypatch, main_repo: Path, wt: Path) -> int:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git reset --hard"},
        "cwd": str(wt),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(_wipe, "get_project_root", lambda: main_repo)
    monkeypatch.setattr(_wipe, "_get_active_dispatch_count", lambda r, lg: 0)
    return _wipe.main()


class TestWorkspaceWipeGuardScenarioC:
    def test_wt_dirty_blocked(self, monkeypatch, main_and_wt):
        """正向對照：WT 有未提交 tracked 變更 → 擋（舊碼讀 MAIN 乾淨而僅 WARN）。"""
        main_repo, wt = main_and_wt
        (wt / "a.txt").write_text("changed in wt\n")
        assert _run_wipe(monkeypatch, main_repo, wt) == 2

    def test_main_dirty_does_not_affect_wt_judgement(self, monkeypatch, main_and_wt):
        """反向對照：MAIN 髒、WT 乾淨 → 不擋（非並行期 WARN）。"""
        main_repo, wt = main_and_wt
        (main_repo / "a.txt").write_text("changed in main\n")
        assert _run_wipe(monkeypatch, main_repo, wt) == 0


# ============================================================================
# version-release-guard：pubspec / CHANGELOG（AR）
# ============================================================================

_release = _load(
    "version_release_guard_hook_c",
    CLAUDE_DIR / "skills" / "version-release" / "hooks" / "version-release-guard-hook.py",
)
_LOGGER = logging.getLogger("test-version-release-c")


class TestVersionReleaseGuardScenarioC:
    def test_wt_mismatch_detected(self, monkeypatch, main_and_wt):
        """正向對照：WT 版本不一致 → False（舊碼讀 MAIN 一致而通過）。"""
        main_repo, wt = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        (wt / "CHANGELOG.md").write_text("## [2.0.0]\n")
        ok, _ = _release.check_pubspec_version(_LOGGER, {"cwd": str(wt)})
        assert ok is False

    def test_main_mismatch_does_not_affect_wt(self, monkeypatch, main_and_wt):
        """反向對照：MAIN 不一致、WT 一致 → True。"""
        main_repo, wt = main_and_wt
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(main_repo))
        (main_repo / "CHANGELOG.md").write_text("## [2.0.0]\n")
        ok, _ = _release.check_pubspec_version(_LOGGER, {"cwd": str(wt)})
        assert ok is True


# ============================================================================
# agent-commit-verification：git status（AR）
# ============================================================================

_agent = _load(
    "agent_commit_verification_hook_c", HOOKS_DIR / "agent-commit-verification-hook.py"
)


def _run_agent(monkeypatch, main_repo: Path, wt: Path, capsys) -> str:
    payload = {"agent_id": "a1", "cwd": str(wt)}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(_agent, "get_project_root", lambda: main_repo)
    monkeypatch.setattr(_agent, "_lookup_agent_info", lambda r, a, lg: ("desc", False))
    try:
        _agent.main()
    except SystemExit:
        pass
    return capsys.readouterr().err


class TestAgentCommitVerificationScenarioC:
    def test_wt_dirty_detected(self, monkeypatch, main_and_wt, capsys):
        """正向對照：WT 有未提交檔 → 偵測到（舊碼讀 MAIN 乾淨而漏報）。"""
        main_repo, wt = main_and_wt
        (wt / "a.txt").write_text("changed in wt\n")
        err = _run_agent(monkeypatch, main_repo, wt, capsys)
        assert _agent.MSG_UNCOMMITTED_DETECTED in err

    def test_main_dirty_does_not_affect_wt_judgement(self, monkeypatch, main_and_wt, capsys):
        """反向對照：MAIN 髒、WT 乾淨 → 不報未提交。"""
        main_repo, wt = main_and_wt
        (main_repo / "a.txt").write_text("changed in main\n")
        err = _run_agent(monkeypatch, main_repo, wt, capsys)
        assert _agent.MSG_UNCOMMITTED_DETECTED not in err
