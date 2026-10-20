"""agent-dispatch-validation-hook「外部 .claude 路徑」判定：佔位字樣與同 repo worktree。

E1：佔位字樣、同 repo 同層 worktree 放行（修正前紅）。
E2：repo 外 worktree、判定失敗（解析不出 common dir / 所屬 checkout）維持阻擋。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
_TICKET_HOOKS_DIR = _HOOKS_DIR.parent / "skills" / "ticket" / "hooks"
sys.path.insert(0, str(_TICKET_HOOKS_DIR))
_spec = importlib.util.spec_from_file_location(
    "agent_dispatch_validation_hook_ext",
    _TICKET_HOOKS_DIR / "agent-dispatch-validation-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)
_classify = _hook._classify_prompt_paths


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    main = tmp_path / "proj"
    main.mkdir()
    _git(main, "init", "-q")
    (main / "a.txt").write_text("x")
    _git(main, "add", "a.txt")
    _git(main, "commit", "-q", "-m", "init")
    monkeypatch.setattr(_hook, "get_project_root", lambda: main)
    return main


def _worktree(main, dest):
    _git(main, "worktree", "add", "-q", "-b", "wt-branch", str(dest))
    (dest / ".claude" / "hooks").mkdir(parents=True)
    return dest


@pytest.mark.parametrize("sample", [
    "範例 ~/.../.claude/x 說明",
    "範例 /home/u/…/.claude/x 說明",
    "範例 /<worktree>/.claude/hooks/x.py 說明",
    "範例 /abs/<path>/sub/.claude/x 說明",
])
def test_placeholder_paths_not_external(repo, sample):
    main_repo, external, _ = _classify(sample)
    assert external is False


def test_sibling_worktree_same_repo_not_external(repo, tmp_path):
    wt = _worktree(repo, tmp_path / "proj-sibling")
    main_repo, external, _ = _classify(f"修改 {wt}/.claude/hooks/x.py")
    assert external is False


def test_worktree_outside_repo_still_external(repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    wt = _worktree(repo, outside / "wt")
    main_repo, external, _ = _classify(f"修改 {wt}/.claude/hooks/x.py")
    # E2：同 repo 但位於 repo 外（非同層）的 worktree，runtime 仍拒絕，照擋
    assert external is True


def test_unrelated_repo_claude_still_external(repo, tmp_path_factory):
    other = tmp_path_factory.mktemp("other")
    _git(other, "init", "-q")
    (other / ".claude").mkdir()
    main_repo, external, _ = _classify(f"修改 {other}/.claude/hooks/x.py")
    assert external is True


def test_nonexistent_path_stays_external(repo):
    _, external, _ = _classify("修改 /nonexistent-zz/wt/.claude/hooks/x.py")
    assert external is True


def test_unresolvable_common_dir_stays_external(repo, tmp_path_factory):
    broken = tmp_path_factory.mktemp("broken")
    (broken / ".git").write_text("gitdir: /nonexistent-zz/gitdir\n")
    (broken / ".claude").mkdir()
    _, external, _ = _classify(f"修改 {broken}/.claude/hooks/x.py")
    assert external is True


def test_project_root_unresolvable_stays_external(repo, tmp_path, monkeypatch):
    wt = _worktree(repo, tmp_path / "proj-sibling")
    monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path / "no-such-root")
    _, external, _ = _classify(f"修改 {wt}/.claude/hooks/x.py")
    assert external is True
