"""
Test: merge-staged-index-guard-hook（0.4.0-W1-060）

主工作區 index 有 staged 變更時擋下 git merge（此狀態下 merge 必然失敗，
失敗路徑以 read-tree 把 index 與工作區重設為開始時的 HEAD）。

E2 正向對照：staged 狀態下 `git merge x` 與 `git -C <repo> merge x` 被 deny。
E1 對照：同一命令 index 乾淨時放行；worktree 目錄內（cwd 或 -C）放行。
另測：--abort / --continue 放行、非 merge 放行、守衛自身例外 fail-open。
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "merge_staged_index_guard_hook",
    HOOKS_DIR / "merge-staged-index-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    (path / "a.txt").write_text("a\n")
    _git(path, "add", "a.txt")
    _git(path, "-c", "user.email=t@example.com", "-c", "user.name=t",
         "commit", "-q", "-m", "init")
    return path


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path / "main")


def _stage(repo: Path, name: str = "staged.txt") -> None:
    (repo / name).write_text("x\n")
    _git(repo, "add", name)


def _run(monkeypatch, command: str, cwd: Path, tool_name: str = "Bash") -> int:
    payload = {
        "tool_name": tool_name,
        "tool_input": {"command": command},
        "cwd": str(cwd),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hook_module.main()


# ---- E2：staged 狀態必須 deny ----

def test_e2_plain_merge_denied_when_staged(monkeypatch, repo, capsys):
    _stage(repo)
    assert _run(monkeypatch, "git merge feature", repo) == 2
    err = capsys.readouterr().err
    assert "staged.txt" in err
    assert "restore --staged" in err
    assert "read-tree" in err


def test_e2_dash_c_merge_denied_when_staged(monkeypatch, repo, tmp_path):
    # 全套件負載下逾時會 fail-open 翻掉 deny，放寬逾時以降低負載敏感度
    monkeypatch.setattr(hook_module, "_GIT_TIMEOUT_SECONDS", 60)
    _stage(repo)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert _run(monkeypatch, f"git -C {repo} merge feature", elsewhere) == 2


# ---- E1：對照放行 ----

def test_e1_clean_index_allowed(monkeypatch, repo):
    assert _run(monkeypatch, "git merge feature", repo) == 0


def test_e1_clean_index_dash_c_allowed(monkeypatch, repo, tmp_path):
    assert _run(monkeypatch, f"git -C {repo} merge feature", tmp_path) == 0


def test_e1_worktree_cwd_allowed_even_if_staged(monkeypatch, tmp_path):
    wt = _init_repo(tmp_path / "proj" / ".claude" / "worktrees" / "agent-x")
    _stage(wt)
    assert _run(monkeypatch, "git merge feature", wt) == 0


def test_e1_worktree_dash_c_allowed_even_if_staged(monkeypatch, tmp_path):
    wt = _init_repo(tmp_path / "proj" / ".claude" / "worktrees" / "agent-y")
    _stage(wt)
    assert _run(monkeypatch, f"git -C {wt} merge feature", tmp_path) == 0


# ---- 收拾中斷合併的路徑必須放行 ----

@pytest.mark.parametrize("flag", ["--abort", "--continue"])
def test_abort_continue_allowed_when_staged(monkeypatch, repo, flag):
    _stage(repo)
    assert _run(monkeypatch, f"git merge {flag}", repo) == 0


# ---- 其他 ----

def test_non_merge_command_allowed(monkeypatch, repo):
    _stage(repo)
    assert _run(monkeypatch, "git status", repo) == 0


def test_non_bash_tool_allowed(monkeypatch, repo):
    _stage(repo)
    assert _run(monkeypatch, "git merge x", repo, tool_name="Read") == 0


def test_fail_open_on_internal_exception(monkeypatch, repo, capsys):
    _stage(repo)

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(hook_module, "_staged_files", boom)
    assert _run(monkeypatch, "git merge x", repo) == 0
    assert "boom" in capsys.readouterr().err


# ---- 快轉 merge：不走 merge commit 路徑，staged 不相干檔時放行 ----

_COMMIT = ["-c", "user.email=t@example.com", "-c", "user.name=t"]


def _branch_with_commit(repo: Path, name: str) -> None:
    """從目前 HEAD 建分支並在其上加一個 commit，切回原分支。"""
    _git(repo, "checkout", "-q", "-b", name)
    (repo / f"{name}.txt").write_text(name + "\n")
    _git(repo, "add", f"{name}.txt")
    _git(repo, *_COMMIT, "commit", "-q", "-m", name)
    _git(repo, "checkout", "-q", "-")


def test_e1_fast_forward_merge_allowed_when_staged(monkeypatch, repo):
    _branch_with_commit(repo, "ffbranch")
    _stage(repo)
    assert _run(monkeypatch, "git merge ffbranch", repo) == 0


def test_e2_diverged_merge_denied_when_staged(monkeypatch, repo, capsys):
    _branch_with_commit(repo, "side")
    (repo / "main-only.txt").write_text("m\n")
    _git(repo, "add", "main-only.txt")
    _git(repo, *_COMMIT, "commit", "-q", "-m", "main-advance")
    _stage(repo)
    assert _run(monkeypatch, "git merge side", repo) == 2
    assert "merge commit" in capsys.readouterr().err


def test_e2_fast_forward_with_no_ff_denied_when_staged(monkeypatch, repo):
    _branch_with_commit(repo, "ffbranch")
    _stage(repo)
    assert _run(monkeypatch, "git merge --no-ff ffbranch", repo) == 2


def test_unresolvable_ref_treated_as_staged_denied(monkeypatch, repo):
    _stage(repo)
    assert _run(monkeypatch, "git merge no-such-ref", repo) == 2


# ---- 未決路徑：git 逾時 / 非零 returncode 維持 fail-open，但必須留下可見訊號 ----
# 與上方 E2 deny 測試構成 E1 對照：同一組 staged fixture，正常 git 為 deny（rc=2），
# 注入 git 故障後為放行（rc=0）且 stderr 有訊息。

def test_e1_git_timeout_allowed_with_visible_message(monkeypatch, repo, capsys):
    _stage(repo)
    real_run_git = hook_module._run_git

    def timeout_on_diff(target, args):
        if "diff" in args:
            raise subprocess.TimeoutExpired(cmd="git", timeout=1)
        return real_run_git(target, args)

    monkeypatch.setattr(hook_module, "_run_git", timeout_on_diff)
    assert _run(monkeypatch, "git merge feature", repo) == 0
    assert "放行" in capsys.readouterr().err


def test_e1_diff_nonzero_allowed_with_visible_message(monkeypatch, repo, capsys):
    _stage(repo)
    real_run_git = hook_module._run_git

    def diff_fails(target, args):
        if "diff" in args:
            return subprocess.CompletedProcess(
                args, 128, stdout="", stderr="fatal: injected"
            )
        return real_run_git(target, args)

    monkeypatch.setattr(hook_module, "_run_git", diff_fails)
    assert _run(monkeypatch, "git merge feature", repo) == 0
    err = capsys.readouterr().err
    assert "放行" in err
    assert "128" in err


def test_git_timeout_is_module_constant():
    assert isinstance(hook_module._GIT_TIMEOUT_SECONDS, (int, float))
