"""Tests for sync-claude-push.py no-change early-exit (W3-075).

涵蓋 check_no_change_early_exit 的五種狀態：
  - 首次推送（.sync-state.json 不存在）
  - state 檔損壞（JSON 解析失敗）
  - state 檔缺欄位
  - hash 相同且無新 commit（應 abort）
  - hash 相同但有新 commit（不 abort）
  - hash 不同（不 abort）
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# sync-claude-push.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_ee", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_ee"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


@pytest.fixture
def claude_dir(tmp_path: Path) -> Path:
    """建立含一個檔案的 fake .claude/ 目錄。"""
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "dummy.txt").write_text("content\n", encoding="utf-8")
    return d


def _write_state(claude_dir: Path, hash_value: str, time_value: str = "2026-05-28T11:00:00") -> None:
    state = {
        "last_push_hash": hash_value,
        "last_push_version": "1.0.0",
        "last_push_time": time_value,
    }
    (claude_dir / ".sync-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_first_push_no_state_file(claude_dir: Path, tmp_path: Path) -> None:
    """無 .sync-state.json 時不應 abort。"""
    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "首次推送" in reason


def test_corrupted_state_file(claude_dir: Path, tmp_path: Path) -> None:
    """JSON 解析失敗時不應 abort（fail-safe）。"""
    (claude_dir / ".sync-state.json").write_text("{ not valid json", encoding="utf-8")
    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "解析失敗" in reason


def test_state_missing_fields(claude_dir: Path, tmp_path: Path) -> None:
    """state 缺欄位時不應 abort。"""
    (claude_dir / ".sync-state.json").write_text(
        json.dumps({"last_push_version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )
    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "缺欄位" in reason


def test_hash_match_no_new_commit_aborts(
    claude_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash 相同且無新 commit 時應 abort。"""
    current_hash = sync_mod._compute_content_hash(claude_dir)
    _write_state(claude_dir, current_hash)

    # mock collect_claude_commits 回傳空 list（無新 commit）
    monkeypatch.setattr(sync_mod, "collect_claude_commits", lambda root, since: [])

    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is True
    assert "無實質變更" in reason


def test_hash_match_but_has_new_commit_continues(
    claude_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash 相同但有新 commit（罕見：commit 後 revert）時不應 abort。"""
    current_hash = sync_mod._compute_content_hash(claude_dir)
    _write_state(claude_dir, current_hash)

    monkeypatch.setattr(
        sync_mod, "collect_claude_commits", lambda root, since: ["feat: x", "revert: x"]
    )

    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "2 個新 commit" in reason


def test_hash_mismatch_continues(
    claude_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash 不同時不應 abort。"""
    _write_state(claude_dir, "deadbeef00000000")

    monkeypatch.setattr(sync_mod, "collect_claude_commits", lambda root, since: [])

    should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, tmp_path)
    assert should_exit is False
    assert "hash 不同" in reason


def _run_git(args: list[str], cwd: Path, commit_date: str | None = None) -> None:
    """執行 git 指令；commit_date 供 commit 指令固定 author/committer 時間，
    避免測試依賴真實牆鐘時間差（--since 邊界對同一秒內的多個 commit 不穩定）。
    """
    env = None
    if commit_date is not None:
        import os

        env = {**os.environ, "GIT_AUTHOR_DATE": commit_date, "GIT_COMMITTER_DATE": commit_date}
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env)


def _init_repo_with_claude_dir(tmp_path: Path) -> tuple[Path, str]:
    """建立含 .claude/ 的真實 git repo，用於驗證 diff 內容過濾（tarrragon/claude#66）。

    傳回 (repo, last_time)：last_time 是初始 commit 的固定 commit 時間，供
    check_no_change_early_exit 的 --since 判斷排除初始 commit本身。
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(["init", "-q"], cwd=repo)
    _run_git(["config", "user.email", "test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Test"], cwd=repo)

    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "dummy.txt").write_text("content\n", encoding="utf-8")
    (claude_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    # .sync-state.json 在正式專案是 gitignore 排除的本地狀態檔（非 git tracked），
    # 測試 repo 需同步排除，否則後續 _write_state 產生的檔案會被 `git add .`
    # 誤納入記帳 commit，汙染「僅變更 VERSION」的判定。
    (repo / ".gitignore").write_text(".claude/.sync-state.json\n", encoding="utf-8")
    _run_git(["add", "."], cwd=repo)
    initial_date = "2019-01-01T00:00:00+00:00"
    _run_git(["commit", "-q", "-m", "chore: initial"], cwd=repo, commit_date=initial_date)
    # since 落在初始 commit 之後、後續測試 commit（2020-01-02）之前，避免 git
    # log --since 對邊界日期採 inclusive 語意而誤含初始 commit。
    since_time = "2019-06-01T00:00:00+00:00"
    return repo, since_time


class TestVersionOnlyCommitLoop:
    """tarrragon/claude#66：VERSION 回寫記帳 commit 不應被誤判為實質變更。"""

    def test_version_only_commit_after_push_aborts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """push 後僅提交 VERSION 回寫（記帳 commit），下一輪應視為無實質變更並 abort。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo, last_time = _init_repo_with_claude_dir(tmp_path)
            claude_dir = repo / ".claude"

            # 模擬 push 完成當下：write_local_version 已把 VERSION 改為 1.1.0，
            # last_push_hash 是「VERSION 已是 1.1.0」時的內容指紋。
            (claude_dir / "VERSION").write_text("1.1.0\n", encoding="utf-8")
            current_hash = sync_mod._compute_content_hash(claude_dir)
            _write_state(claude_dir, current_hash, time_value=last_time)

            # 使用者事後才 `git add && git commit` 持久化這個已經算進 hash 的
            # VERSION 變更 -> 產生一個記帳 commit，但工作區內容（進而 hash）
            # 完全沒有再變化。
            _run_git(["add", "."], cwd=repo)
            _run_git(
                ["commit", "-q", "-m", "chore: sync VERSION to 1.1.0"],
                cwd=repo,
                commit_date="2020-01-02T00:00:00+00:00",
            )

            should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, repo)

            assert should_exit is True
            assert "無實質變更" in reason

    def test_real_change_commit_still_proceeds(self) -> None:
        """記帳 commit 之外仍有實質變更（改動 VERSION 以外的檔案）時，行為維持現行（不 abort）。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo, last_time = _init_repo_with_claude_dir(tmp_path)
            claude_dir = repo / ".claude"

            current_hash = sync_mod._compute_content_hash(claude_dir)
            _write_state(claude_dir, current_hash, time_value=last_time)

            (claude_dir / "dummy.txt").write_text("changed content\n", encoding="utf-8")
            _run_git(["add", "."], cwd=repo)
            _run_git(
                ["commit", "-q", "-m", "feat: real change"],
                cwd=repo,
                commit_date="2020-01-02T00:00:00+00:00",
            )

            should_exit, reason = sync_mod.check_no_change_early_exit(claude_dir, repo)

            assert should_exit is False
            assert "1 個新 commit" in reason


class TestShouldCheckNoChange:
    """main() 呼叫 check_no_change_early_exit 前的旗標判斷（0.2.1-W3-303）。

    涵蓋 ARCH-BAL-013 第三例：孤兒提醒建議的 `sync-push --clean` 不應被
    early-exit 攔下，須額外追加 --force 才能完成。
    """

    def test_no_flags_runs_check(self) -> None:
        """三個旗標皆未帶時，應執行 early-exit 檢查（既有行為不變）。"""
        assert sync_mod._should_check_no_change(None, False, False) is True

    def test_user_message_skips_check(self) -> None:
        """提供 commit message 時應跳過檢查（既有行為不變）。"""
        assert sync_mod._should_check_no_change("fix: x", False, False) is False

    def test_force_mode_skips_check(self) -> None:
        """帶 --force 時應跳過檢查（既有行為不變）。"""
        assert sync_mod._should_check_no_change(None, True, False) is False

    def test_clean_mode_skips_check(self) -> None:
        """帶 --clean 時應跳過檢查（0.2.1-W3-303 新增）：刪除傳播不依賴內容 hash 變化。"""
        assert sync_mod._should_check_no_change(None, False, True) is False

    def test_clean_and_force_both_skip_check(self) -> None:
        """--clean 與 --force 同時帶時仍應跳過檢查。"""
        assert sync_mod._should_check_no_change(None, True, True) is False
