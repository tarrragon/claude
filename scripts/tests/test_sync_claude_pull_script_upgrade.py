"""Tests for sync-claude-pull.py 上游腳本較新時改由上游腳本執行（3.4.0-W1-293）。

端到端：本機 repo 當上游，專案內放「REPO_URL 指向該 repo 的本地舊腳本」；
上游放可辨識的新版腳本（寫標記檔並以特定結束碼結束），斷言本輪由新版執行。
判定規則（base 比對、preserve、守衛）以 _decide_script_upgrade 單元測試覆蓋。
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_SCRIPT = _SCRIPTS_DIR / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_script_upgrade", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_script_upgrade"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

REL = pull.UPSTREAM_SCRIPT_REL
GUARD = pull.SCRIPT_RERUN_GUARD_ENV
NEW_SCRIPT_EXIT_CODE = 7
RERUN_BANNER = "改由上游版本執行本輪合併"

NEW_UPSTREAM_SCRIPT = f'''\
import os, sys
from pathlib import Path
Path("rerun-marker.txt").write_text(
    os.environ.get("{GUARD}", "") + "|" + " ".join(sys.argv[1:]), encoding="utf-8")
sys.exit({NEW_SCRIPT_EXIT_CODE})
'''


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit_all(repo: Path, msg: str) -> str:
    _git(["add", "-A"], repo)
    _git(["commit", "-m", msg], repo)
    return _git(["rev-parse", "HEAD"], repo)


def _make_upstream(
    tmp_path: Path, script_text: str, version: str | None = "1.0.0"
) -> Path:
    up = tmp_path / "upstream"
    (up / "scripts").mkdir(parents=True)
    _git(["init"], up)
    if version is not None:
        (up / "VERSION").write_text(version + "\n", encoding="utf-8")
    else:
        (up / "README.md").write_text("x\n", encoding="utf-8")
    (up / REL).write_text(script_text, encoding="utf-8")
    _commit_all(up, "upstream")
    return up


def _make_project(
    tmp_path: Path, upstream: Path, local_version: str | None = "0.9.0"
) -> tuple[Path, Path]:
    """專案內放 REPO_URL 指向 upstream 的本地腳本（舊版）與 lib。"""
    root = tmp_path / "project"
    claude = root / ".claude"
    (claude / "scripts").mkdir(parents=True)
    if local_version is not None:
        (claude / "VERSION").write_text(local_version + "\n", encoding="utf-8")
    shutil.copytree(
        _SCRIPTS_DIR.parent / "lib", claude / "lib",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    old_text = _SCRIPT.read_text(encoding="utf-8").replace(
        'REPO_URL = "https://github.com/tarrragon/claude.git"',
        f'REPO_URL = "{upstream}"', 1,
    )
    local = claude / REL
    local.write_text(old_text, encoding="utf-8")
    _git(["init"], root)
    _commit_all(root, "init")
    return root, local


def _run_local(root: Path, local: Path, tmp_path: Path, extra_env: dict | None = None):
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != GUARD}
    env.update({"TMPDIR": str(tmpdir), **(extra_env or {})})
    proc = subprocess.run(
        [sys.executable, str(local), "--confirm-overlay"],
        cwd=str(root), env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return proc, tmpdir


# ---------- 端到端 ----------

def test_newer_upstream_script_runs_instead_of_local(tmp_path: Path):
    up = _make_upstream(tmp_path, NEW_UPSTREAM_SCRIPT)
    root, local = _make_project(tmp_path, up)
    proc, tmpdir = _run_local(root, local, tmp_path)
    assert proc.returncode == NEW_SCRIPT_EXIT_CODE, proc.stdout + proc.stderr
    assert RERUN_BANNER in proc.stdout
    marker = (root / "rerun-marker.txt").read_text(encoding="utf-8")
    assert marker == "1|--confirm-overlay"  # 守衛已設、argv 原樣傳遞
    assert "Traceback" not in proc.stderr
    assert list(tmpdir.iterdir()) == []  # temp_dir 與備份皆已清理


def test_identical_upstream_script_does_not_rerun(tmp_path: Path):
    """E1 對照組：上下游腳本位元組相同時不重新執行。"""
    up = _make_upstream(tmp_path, "placeholder\n")
    root, local = _make_project(tmp_path, up)
    (up / REL).write_bytes(local.read_bytes())
    _commit_all(up, "same script")
    proc, _ = _run_local(root, local, tmp_path)
    assert RERUN_BANNER not in proc.stdout
    assert not (root / "rerun-marker.txt").exists()
    assert proc.returncode != NEW_SCRIPT_EXIT_CODE


@pytest.mark.parametrize(
    "up_version,local_version,expect_in_note",
    [
        ("0.8.0", "0.9.0", ("0.8.0", "0.9.0")),  # pin 到較舊版本
        ("0.9.0", "0.9.0", ("0.9.0",)),  # 版本相等但腳本不同
        ("1.0.0", None, ("VERSION",)),  # 本地 VERSION 缺檔
        (None, "0.9.0", ("VERSION",)),  # 上游 VERSION 缺檔
    ],
)
def test_version_not_newer_or_unreadable_does_not_rerun(
    tmp_path: Path, up_version, local_version, expect_in_note
):
    up = _make_upstream(tmp_path, NEW_UPSTREAM_SCRIPT, version=up_version)
    root, local = _make_project(tmp_path, up, local_version=local_version)
    proc, _ = _run_local(root, local, tmp_path)
    assert RERUN_BANNER not in proc.stdout
    assert not (root / "rerun-marker.txt").exists()
    assert proc.returncode != NEW_SCRIPT_EXIT_CODE
    note_lines = [ln for ln in proc.stderr.splitlines() if "[sync-pull]" in ln]
    assert note_lines, proc.stderr
    assert all(token in note_lines[0] for token in expect_in_note)


def test_version_compare_is_numeric_not_string(tmp_path: Path):
    """對照：上游 1.10.0 > 本地 1.9.0（字串比較會判成較低）。"""
    up = _make_upstream(tmp_path, NEW_UPSTREAM_SCRIPT, version="v1.10.0 ")
    root, local = _make_project(tmp_path, up, local_version="1.9.0")
    proc, _ = _run_local(root, local, tmp_path)
    assert proc.returncode == NEW_SCRIPT_EXIT_CODE, proc.stdout + proc.stderr


def test_guard_env_prevents_rerun(tmp_path: Path):
    up = _make_upstream(tmp_path, NEW_UPSTREAM_SCRIPT)
    root, local = _make_project(tmp_path, up)
    proc, _ = _run_local(root, local, tmp_path, extra_env={GUARD: "1"})
    assert RERUN_BANNER not in proc.stdout
    assert not (root / "rerun-marker.txt").exists()


# ---------- 判定規則 ----------

def _decide_fixture(tmp_path: Path, monkeypatch, local_text: str):
    """上游 repo 兩個 commit：base 版（A）與較新版（B）；本地腳本內容由參數決定。"""
    up = tmp_path / "up"
    (up / "scripts").mkdir(parents=True)
    _git(["init"], up)
    (up / REL).write_text("base-version\n", encoding="utf-8")
    base_sha = _commit_all(up, "base")
    (up / REL).write_text("new-version\n", encoding="utf-8")
    _commit_all(up, "new")
    local = tmp_path / "local-script.py"
    local.write_text(local_text, encoding="utf-8")
    (up / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    cd = tmp_path / "cd"
    cd.mkdir()
    (cd / "VERSION").write_text("0.9.0\n", encoding="utf-8")
    monkeypatch.setattr(pull, "_local_script_path", lambda: local)
    monkeypatch.delenv(GUARD, raising=False)
    return up, base_sha


def test_local_equals_base_and_upstream_newer_reruns(tmp_path: Path, monkeypatch):
    up, base = _decide_fixture(tmp_path, monkeypatch, "base-version\n")
    assert pull._decide_script_upgrade(up, base, True, set(), tmp_path / "cd") == (True, None)


def test_local_specialized_does_not_rerun_and_says_why(tmp_path: Path, monkeypatch):
    up, base = _decide_fixture(tmp_path, monkeypatch, "locally-specialized\n")
    rerun, note = pull._decide_script_upgrade(up, base, True, set(), tmp_path / "cd")
    assert rerun is False
    assert note and "本地特化" in note


def test_preserved_script_does_not_rerun(tmp_path: Path, monkeypatch):
    up, base = _decide_fixture(tmp_path, monkeypatch, "base-version\n")
    rerun, note = pull._decide_script_upgrade(up, base, True, {REL}, tmp_path / "cd")
    assert rerun is False
    assert note and "preserve" in note


def test_no_base_and_differs_reruns(tmp_path: Path, monkeypatch):
    up, _ = _decide_fixture(tmp_path, monkeypatch, "whatever\n")
    assert pull._decide_script_upgrade(up, None, False, set(), tmp_path / "cd") == (True, None)


def test_guard_set_never_reruns(tmp_path: Path, monkeypatch):
    up, base = _decide_fixture(tmp_path, monkeypatch, "base-version\n")
    monkeypatch.setenv(GUARD, "1")
    assert pull._decide_script_upgrade(up, base, True, set(), tmp_path / "cd") == (False, None)


def test_upstream_without_script_does_not_rerun(tmp_path: Path, monkeypatch):
    up, base = _decide_fixture(tmp_path, monkeypatch, "base-version\n")
    (up / REL).unlink()
    assert pull._decide_script_upgrade(up, base, True, set(), tmp_path / "cd") == (False, None)


# ---------- main 接住例外、結束碼原樣傳回 ----------

def test_rerun_exit_code_passthrough_and_cleanup(tmp_path: Path, monkeypatch):
    temp_dir = tmp_path / "t"
    (temp_dir / "scripts").mkdir(parents=True)
    (temp_dir / REL).write_text("import sys; sys.exit(3)\n", encoding="utf-8")
    backup = tmp_path / "b"
    backup.mkdir()
    exc = pull.ScriptUpgradeRerun("a" * 40, backup)
    exc.temp_dir = temp_dir
    monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py"])
    assert pull._rerun_with_upstream_script(exc, tmp_path) == 3
    assert not temp_dir.exists() and not backup.exists()


def test_main_catches_rerun_and_exits_with_child_code(tmp_path: Path, monkeypatch):
    exc = pull.ScriptUpgradeRerun("b" * 40, tmp_path)
    monkeypatch.setattr(pull, "find_project_root", lambda: tmp_path)
    monkeypatch.setattr(pull, "_validate_environment", lambda _r: None)
    monkeypatch.setattr(pull, "warn_conflict_residue", lambda _c: [])
    monkeypatch.setattr(pull, "warn_pending_base", lambda _c: None)

    def _raise(*_a, **_k):
        raise exc

    monkeypatch.setattr(pull, "_clone_and_backup", _raise)
    monkeypatch.setattr(pull, "_rerun_with_upstream_script", lambda _e, _r: 9)
    monkeypatch.setattr(sys, "argv", ["sync-claude-pull.py"])
    with pytest.raises(SystemExit) as raised:
        pull.main()
    assert raised.value.code == 9
