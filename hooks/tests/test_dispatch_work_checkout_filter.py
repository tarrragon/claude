"""並行期判定依派發登記條目的工作位置過濾（work_checkout）。

以真實 git 建主 repo 與 linked worktree，不 mock git。
"""
import json
import subprocess
from pathlib import Path

import pytest

from lib import dispatch_tracker, hook_base
from lib.dispatch_tracker import filter_dispatches_for_checkout
from lib.hook_base import has_parallel_dispatch


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


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
    hook_base.clear_project_root_cache()
    dispatch_tracker.reset_cache()
    yield main, wt
    hook_base.clear_project_root_cache()
    dispatch_tracker.reset_cache()


def _write(main, entries):
    p = main / ".claude" / "dispatch-active.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"dispatches": entries}), encoding="utf-8")
    dispatch_tracker.reset_cache()


def _entry(loc=None):
    e = {
        "agent_description": "d",
        "tool_use_id": "t",
        "agent_id": "a",
        "ticket_id": "",
        "files": [],
        "branch_name": "",
        "dispatched_at": "2099-01-01T00:00:00+00:00",
    }
    if loc is not None:
        e["work_checkout"] = str(loc)
    return e


def test_main_ignores_entry_working_in_other_worktree(repos, monkeypatch):
    main, wt = repos
    _write(main, [_entry(wt)])
    monkeypatch.chdir(main)
    assert has_parallel_dispatch(checkout=main) is False


def test_main_counts_entry_working_in_main(repos, monkeypatch):
    main, wt = repos
    _write(main, [_entry(main)])
    monkeypatch.chdir(main)
    assert has_parallel_dispatch(checkout=main) is True


def test_worktree_ignores_entry_working_in_main(repos, monkeypatch):
    main, wt = repos
    _write(main, [_entry(main)])
    monkeypatch.chdir(wt)
    assert has_parallel_dispatch(checkout=wt) is False


def test_worktree_counts_entry_working_in_itself(repos, monkeypatch):
    main, wt = repos
    _write(main, [_entry(wt)])
    monkeypatch.chdir(wt)
    assert has_parallel_dispatch(checkout=wt) is True


def test_unknown_target_does_not_filter(repos, monkeypatch):
    """作用目標未知（預設 checkout=None）：不以 cwd 推定，全數計入。"""
    main, wt = repos
    _write(main, [_entry(wt)])
    monkeypatch.chdir(main)
    assert has_parallel_dispatch() is True


def test_legacy_entry_without_field_counts_everywhere(repos, monkeypatch):
    main, wt = repos
    _write(main, [_entry()])
    monkeypatch.chdir(main)
    assert has_parallel_dispatch(checkout=main) is True
    monkeypatch.chdir(wt)
    assert has_parallel_dispatch(checkout=wt) is True


def test_symlink_alias_matches_same_directory(repos, tmp_path):
    main, wt = repos
    alias = tmp_path / "alias"
    alias.symlink_to(main)
    assert filter_dispatches_for_checkout([_entry(alias)], main) == [_entry(alias)]
    assert filter_dispatches_for_checkout([_entry(wt)], alias) == []


HOOK = Path(__file__).parent.parent / "bare-commit-guard-hook.py"


def _guard_exit(repos, entry_loc, cwd, cmd_dir):
    """跑 bare-commit-guard：命令為 git -C <cmd_dir> commit -m x -- f.txt。"""
    import os

    main, wt = repos
    _write(main, [dict(_entry(entry_loc), files=["other/zzz.txt"])])
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": "git -C %s commit -m x -- f.txt" % cmd_dir},
        "cwd": str(cwd),
        "session_id": "other",
    })
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PROJECT_DIR", "HOOK_TEST_ISOLATION")}
    proc = subprocess.run(
        ["python3", str(HOOK)], input=payload, text=True, cwd=str(cwd),
        capture_output=True, env=env,
    )
    return proc.returncode


def test_guard_dash_c_targets_entry_checkout_blocks(repos):
    main, wt = repos
    # 條目在 main；cwd=wt、-C main：作用於 main，須擋（回歸情境）
    assert _guard_exit(repos, main, wt, main) == 2
    # 條目在 wt；cwd=main、-C wt：對稱情境，須擋
    assert _guard_exit(repos, wt, main, wt) == 2


def test_guard_same_dir_matrix(repos):
    main, wt = repos
    assert _guard_exit(repos, main, main, main) == 2
    assert _guard_exit(repos, wt, wt, wt) == 2
    assert _guard_exit(repos, wt, main, main) == 0  # 他 worktree 的條目不擋 main
    assert _guard_exit(repos, main, wt, wt) == 0


def _guard_exit_cmd(repos, entry_loc, cwd, command):
    """跑 bare-commit-guard：任意命令文字，條目工作位置為 entry_loc。"""
    import os

    main, wt = repos
    _write(main, [dict(_entry(entry_loc), files=["other/zzz.txt"])])
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
        "session_id": "other",
    })
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PROJECT_DIR", "HOOK_TEST_ISOLATION")}
    proc = subprocess.run(
        ["python3", str(HOOK)], input=payload, text=True, cwd=str(cwd),
        capture_output=True, env=env,
    )
    return proc.returncode


def _regression_commands(main, wt):
    m = str(main)
    return {
        "multi_commit_second_targets_main":
            "git commit -m x -- g.txt; git -C %s commit -m x -- f.txt" % m,
        "and_chain_second_targets_main":
            "git -C %s commit -m x -- f.txt && git -C %s commit -m x -- f.txt" % (wt, m),
        "git_dir_env_prefix":
            "GIT_DIR=%s/.git GIT_WORK_TREE=%s git commit -m x -- f.txt" % (m, m),
        "env_wrapper_git_dir":
            "env GIT_DIR=%s/.git git commit -m x -- f.txt" % m,
        "git_dir_option":
            "git --git-dir=%s/.git --work-tree=%s commit -m x -- f.txt" % (m, m),
    }


@pytest.mark.parametrize("name", [
    "multi_commit_second_targets_main",
    "and_chain_second_targets_main",
    "git_dir_env_prefix",
    "env_wrapper_git_dir",
    "git_dir_option",
])
def test_guard_blocks_regression_forms(repos, name):
    main, wt = repos
    cmd = _regression_commands(main, wt)[name]
    # 條目在 main、cwd 在 worktree：實際目標含 main，須擋
    assert _guard_exit_cmd(repos, main, wt, cmd) == 2


def test_guard_keeps_blocking_dash_c_and_cd_main(repos):
    main, wt = repos
    assert _guard_exit_cmd(
        repos, main, wt, "git -C %s commit -m x -- f.txt" % main) == 2
    assert _guard_exit_cmd(
        repos, main, wt, "cd %s && git commit -m x -- f.txt" % main) == 2


def test_guard_filter_benefit_kept_entry_in_wt_single_main_commit(repos):
    main, wt = repos
    # 條目在 worktree、對主 checkout 單一 commit：過濾收益保留，放行
    cmd = "git -C %s commit -m x -- f.txt" % main
    assert _guard_exit_cmd(repos, wt, main, cmd) == 0
    assert _guard_exit_cmd(repos, wt, wt, cmd) == 0


def test_identity_reads_all_entries_unfiltered(repos):
    """身分判定走 get_active_dispatches，不受過濾影響。"""
    main, wt = repos
    _write(main, [_entry(wt), _entry(main), _entry()])
    assert len(dispatch_tracker.get_active_dispatches(main)) == 3


def test_filter_none_checkout_and_empty_location_kept():
    ds = [_entry(), {"work_checkout": ""}]
    assert filter_dispatches_for_checkout(ds, Path("/x")) == ds
    assert filter_dispatches_for_checkout([_entry("/y")], None) == [_entry("/y")]


def test_record_dispatch_persists_work_checkout(repos):
    main, wt = repos
    dispatch_tracker.record_dispatch(main, "desc", work_checkout=str(wt))
    got = dispatch_tracker.get_active_dispatches(main)
    assert got[0]["work_checkout"] == str(wt)
