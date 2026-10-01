"""release 提交步驟的 git 寫入失敗不得繼續打 tag。

缺陷：Step 3 的 `git add` 撞到並行 session 留下的 index.lock 時只印 WARN 就
繼續，接著把不含定版內容的 commit 打上 tag 並推送。

fixture 為 tmp repo + 本地 bare origin；index.lock 以實體檔案製造，不 mock git。
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402

TAG = "v0.1.0"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    work.mkdir()
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    (work / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "seed")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


def _release(repo: Path, monkeypatch) -> bool:
    """模擬 finish：baseline 在先，定版內容在後，再跑 git 步驟。"""
    monkeypatch.setattr(vr, "GIT_LOCK_WAIT_SECONDS", 0.05, raising=False)
    baseline = vr.snapshot_git_status_paths(repo)
    (repo / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0] - 2026-10-01\n\n定版內容\n", encoding="utf-8"
    )
    with patch.object(vr, "get_project_root", return_value=repo):
        return vr.git_merge_and_push("0.1.0", False, baseline=baseline)


def _tags(repo: Path, remote: bool = False) -> str:
    if remote:
        return _git(repo, "ls-remote", "--tags", "origin").strip()
    return _git(repo, "tag", "-l").strip()


def test_persistent_index_lock_aborts_before_tag(repo, monkeypatch, capsys) -> None:
    """E2 正向對照：鎖持續存在 -> 不建 tag、不推送、stderr 帶出路徑與 git 原始錯誤。"""
    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    head_before = _git(repo, "rev-parse", "HEAD").strip()

    assert _release(repo, monkeypatch) is False

    assert _tags(repo) == ""
    assert _tags(repo, remote=True) == ""
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before
    assert lock.exists(), "工具不得刪除鎖"
    err = capsys.readouterr().err
    assert "CHANGELOG.md" in err
    assert "index.lock" in err


def test_transient_lock_retries_and_tag_contains_changelog(repo, monkeypatch) -> None:
    """鎖是暫時的：重試後成功，定版內容進入被 tag 的 commit。"""
    lock = repo / ".git" / "index.lock"
    real_run = subprocess.run
    changelog_adds = []

    def run_with_lock_on_first_add(cmd, *a, **kw):
        # 第一次 add CHANGELOG.md 時鎖存在（真實 git 因此失敗），該次呼叫返回後
        # 由「並行 session」釋放鎖。以呼叫邊界而非計時器釋放：計時器在 git 啟動
        # 慢於計時長度時，第一次 add 就已看不到鎖，修正前的程式也會綠。
        if cmd[:2] != ["git", "add"] or "CHANGELOG.md" not in cmd:
            return real_run(cmd, *a, **kw)
        changelog_adds.append(cmd)
        if len(changelog_adds) > 1:
            return real_run(cmd, *a, **kw)
        lock.write_text("", encoding="utf-8")
        try:
            return real_run(cmd, *a, **kw)
        finally:
            lock.unlink()

    monkeypatch.setattr(vr.subprocess, "run", run_with_lock_on_first_add)

    assert _release(repo, monkeypatch) is True
    assert len(changelog_adds) >= 2, "鎖競爭後須重試 add"

    assert _tags(repo) == TAG
    assert "定版內容" in _git(repo, "show", f"{TAG}:CHANGELOG.md")
    assert TAG in _tags(repo, remote=True)


def test_no_lock_tags_as_usual(repo, monkeypatch) -> None:
    """正向對照：git add 一次成功，照常建立並推送 tag。"""
    assert _release(repo, monkeypatch) is True

    assert _tags(repo) == TAG
    assert "定版內容" in _git(repo, "show", f"{TAG}:CHANGELOG.md")
    assert TAG in _tags(repo, remote=True)


def test_failed_checkout_main_aborts_before_tag(repo, monkeypatch, capsys) -> None:
    """盤點：checkout main 失敗原本被忽略；現在須在打 tag 前中止。"""
    # main 已被另一個 worktree 佔用 -> 本處 `git checkout main` 必失敗
    _git(repo, "checkout", "-q", "-b", "side")
    _git(repo, "worktree", "add", "-q", str(repo.parent / "wt-main"), "main")

    assert _release(repo, monkeypatch) is False

    assert _tags(repo) == ""
    assert "checkout" in capsys.readouterr().err


def test_add_failure_with_successful_commit_still_aborts(repo, monkeypatch, capsys) -> None:
    """還原 0.4.0 形態：git add 失敗但 git commit 成功（其他檔已在 index）。"""
    monkeypatch.setattr(vr, "GIT_LOCK_MAX_ATTEMPTS", 2, raising=False)
    real_run = subprocess.run

    def run_add_always_locked(cmd, *a, **kw):
        if cmd[:2] == ["git", "add"]:
            return subprocess.CompletedProcess(
                cmd, 128, stdout="",
                stderr="fatal: Unable to create '.git/index.lock': File exists.",
            )
        return real_run(cmd, *a, **kw)

    (repo / "docs").mkdir()
    (repo / "docs" / "other.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "docs/other.md")  # 讓 commit 在 add 失敗時仍有東西可提交
    monkeypatch.setattr(vr.subprocess, "run", run_add_always_locked)

    assert _release(repo, monkeypatch) is False

    assert _tags(repo) == ""
    err = capsys.readouterr().err
    assert "CHANGELOG.md" in err
    assert "index.lock" in err
