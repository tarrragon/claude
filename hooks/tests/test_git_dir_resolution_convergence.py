"""
Test: 三支 hook 的 git 目標目錄解析收斂（0.5.0-W1-263）

bare-commit-guard、merge-staged-index-guard、git-index-lock-cleanup 對同一
命令必須解析出同一目錄（`~`、`..`、`-C a -C b` 串接、語句內 `cd`）。
另測 bare-commit-guard 的 dir_unknown 雙處偵測與偵測失敗日誌分標。
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

from lib.git_command_parse import find_git_dash_c_dirs, find_git_invocations  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bare = _load("bare_commit_guard_conv", "bare-commit-guard-hook.py")
merge_guard = _load("merge_staged_conv", "merge-staged-index-guard-hook.py")
lock_cleanup = _load("lock_cleanup_conv", "git-index-lock-cleanup-hook.py")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """cwd 下建好 a/b/x/other 目錄，HOME 指向 tmp 下的 home（含 x）。"""
    cwd = tmp_path / "cwd"
    for sub in ("a/b", "x", "other", "sub"):
        (cwd / sub).mkdir(parents=True)
    home = tmp_path / "home"
    (home / "x").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return cwd, home


def _bare_dir(command: str, cwd: Path) -> str:
    invs = find_git_invocations(command, {"commit"}, str(cwd), scan=True)
    dirs = bare._resolve_detect_dirs(str(cwd), invs[0], Path("/root-unused"))
    assert len(dirs) == 1
    return dirs[0]


def _merge_dir(command: str, cwd: Path) -> str:
    invs = find_git_invocations(command, {"merge"}, str(cwd), scan=True)
    return merge_guard._target_dir(invs[0], str(cwd))


def _lock_targets(command: str, cwd: Path):
    import logging
    return lock_cleanup.extract_target_dirs(command, str(cwd), logging.getLogger("t"))


def _cases(cwd: Path, home: Path):
    return [
        ("-C ~/x", str(home / "x")),
        ("-C sub/../other", str(cwd / "other")),
        ("-C a -C b", str(cwd / "a" / "b")),
        ("-C /abs/where", "/abs/where"),
    ]


@pytest.mark.parametrize("idx", range(4))
def test_three_hooks_resolve_same_dir(env, idx):
    cwd, home = env
    opts, expected = _cases(cwd, home)[idx]
    assert _bare_dir(f"git {opts} commit -m m", cwd) == expected
    assert _merge_dir(f"git {opts} merge topic", cwd) == expected
    if Path(expected).is_dir():
        assert expected in _lock_targets(f"git {opts} status", cwd)


def test_cd_statement_resolves_same_dir(env):
    cwd, _ = env
    expected = str(cwd / "x")
    assert _bare_dir("cd x && git commit -m m", cwd) == expected
    assert _merge_dir("cd x && git merge topic", cwd) == expected
    assert expected in _lock_targets("cd x && git status", cwd)


def test_chained_dash_c_lock_cleanup_keeps_every_path(env):
    """git-index-lock-cleanup 需要全部 -C 路徑：串接的中間目錄 a 也在目標內。"""
    cwd, _ = env
    targets = _lock_targets("git -C a -C b status", cwd)
    assert str(cwd / "a") in targets and str(cwd / "a" / "b") in targets


def test_find_git_dash_c_dirs_unparseable_returns_none():
    assert find_git_dash_c_dirs('git -C "unclosed status') is None


# ---- bare-commit-guard：dir_unknown 雙處偵測 ----


def _run_bare(monkeypatch, command, cwd, root, state_dirs):
    """state_dirs：有進行中合併狀態的目錄集合（以字串比對偵測目錄）。"""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(bare, "get_project_root", lambda: root)
    monkeypatch.setattr(
        bare, "_merge_in_progress", lambda d, *a, **k: str(d) in state_dirs
    )
    monkeypatch.setattr(bare, "_other_operation_state", lambda *a, **k: None)
    monkeypatch.setattr(bare, "_get_active_dispatches_safe", lambda r: [])
    monkeypatch.setattr(bare, "_get_staged_files", lambda r: [])
    monkeypatch.setattr(bare, "_get_unstaged_tracked_files", lambda r: [])
    return bare.main()


_UNKNOWN_CMD = 'git -C "$TARGET" commit -m m'


@pytest.mark.parametrize("where", ["cwd", "root"])
def test_dir_unknown_blocks_when_either_dir_in_progress(monkeypatch, tmp_path, where):
    cwd, root = tmp_path / "cwd", tmp_path / "root"
    state = {str(cwd if where == "cwd" else root)}
    assert _run_bare(monkeypatch, _UNKNOWN_CMD, cwd, root, state) == 2


def test_dir_unknown_passes_when_neither_dir_in_progress(monkeypatch, tmp_path):
    cwd, root = tmp_path / "cwd", tmp_path / "root"
    assert _run_bare(monkeypatch, _UNKNOWN_CMD, cwd, root, set()) == 0


def test_known_dir_checks_only_effective_dir(monkeypatch, tmp_path):
    """反向：目錄可知時只查 effective_dir，payload cwd 與 root 的狀態不影響。"""
    cwd, root = tmp_path / "cwd", tmp_path / "root"
    state = {str(cwd), str(root)}
    assert _run_bare(monkeypatch, "git -C /known commit -m m", cwd, root, state) == 0
    assert _run_bare(monkeypatch, "git -C /known commit -m m", cwd, root, {"/known"}) == 2


# ---- 偵測失敗日誌分標 ----


def _fake_run(merge_rc, other_rc):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        rc = other_rc if "--git-path" in cmd else merge_rc
        return subprocess.CompletedProcess(cmd, rc, "", "boom")

    return run, calls


def test_git_wholly_failing_reports_once(monkeypatch, capsys):
    run, calls = _fake_run(128, 128)
    monkeypatch.setattr(bare.subprocess, "run", run)
    assert bare._pending_operation("/d", None) is None
    err = capsys.readouterr().err
    assert err.count("偵測失敗") == 1
    assert "MERGE_HEAD" in err and "cherry-pick" in err
    assert len(calls) == 1  # 第二次偵測被略過


def test_only_other_state_failing_labelled_as_other(monkeypatch, capsys):
    run, _ = _fake_run(1, 128)
    monkeypatch.setattr(bare.subprocess, "run", run)
    assert bare._pending_operation("/d", None) is None
    err = capsys.readouterr().err
    assert err.count("偵測失敗") == 1
    assert "cherry-pick" in err and "MERGE_HEAD" not in err


# ---- 變異確認：解析退化時上列測試必須翻紅 ----


def test_mutation_no_expanduser_diverges_from_expected(env, monkeypatch):
    import lib.git_command_parse as lib

    cwd, home = env
    monkeypatch.setattr(lib.os.path, "expanduser", lambda p: p)
    assert _bare_dir("git -C ~/x commit -m m", cwd) != str(home / "x")


def test_mutation_single_dir_detection_misses_root(monkeypatch, tmp_path):
    cwd, root = tmp_path / "cwd", tmp_path / "root"
    monkeypatch.setattr(
        bare, "_resolve_detect_dirs", lambda c, inv, r: [str(c)]
    )
    assert _run_bare(monkeypatch, _UNKNOWN_CMD, cwd, root, {str(root)}) == 0
