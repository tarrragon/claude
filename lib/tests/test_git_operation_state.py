"""
lib.git_operation_state 單元測試（自 bare-commit-guard 抽出的進行中操作偵測）。

用真實 git 倉庫製造 merge／cherry-pick／revert／rebase 狀態，不 mock 偵測
函式。每個「偵測到」案例都配「乾淨倉庫不誤報」的對照（E2：只斷言正常輸入
通過分辨不出偵測器是否已死）。失敗語意：git 子程序異常時 fail-open 回
無進行中操作，並寫 stderr 與 logger。
"""

import logging
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import git_operation_state as ops  # noqa: E402
from lib.git_command_parse import GitInvocation  # noqa: E402


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=check,
    )


@pytest.fixture
def repo(tmp_path):
    """含 base 與兩條互相衝突分支的倉庫，停在 main。"""
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "f.txt").write_text("base\n")
    _git(r, "add", "f.txt")
    _git(r, "commit", "-q", "-m", "base")
    for br, text in (("side", "side\n"), ("other", "other\n")):
        _git(r, "checkout", "-q", "-b", br, "main")
        (r / "f.txt").write_text(text)
        _git(r, "commit", "-q", "-am", br)
    _git(r, "checkout", "-q", "main")
    return r


class _Sink:
    def __init__(self):
        self.warnings = []

    def warning(self, msg, *args):
        self.warnings.append(msg % args if args else msg)


class TestPendingOperation:
    def test_clean_repo_reports_none(self, repo):
        assert ops._pending_operation(repo) is None

    def test_merge_in_progress(self, repo):
        _git(repo, "merge", "--no-ff", "--no-commit", "side", check=False)
        assert ops._pending_operation(repo) == ops._OP_MERGE

    def test_cherry_pick_conflict(self, repo):
        _git(repo, "checkout", "-q", "side")
        _git(repo, "cherry-pick", "other", check=False)
        assert ops._pending_operation(repo) == ops._OP_CHERRY_PICK

    def test_revert_conflict(self, repo):
        # side 上再改同一行，回復較早的 side commit 必衝突並留下 REVERT_HEAD
        _git(repo, "checkout", "-q", "side")
        (repo / "f.txt").write_text("later\n")
        _git(repo, "commit", "-q", "-am", "later")
        _git(repo, "revert", "HEAD~1", "--no-edit", check=False)
        assert ops._pending_operation(repo) == ops._OP_REVERT

    def test_rebase_conflict(self, repo):
        _git(repo, "checkout", "-q", "other")
        _git(repo, "rebase", "side", check=False)
        assert ops._pending_operation(repo) == ops._OP_REBASE


class TestPendingOperationInDirs:
    def test_blocking_state_in_any_dir_wins(self, repo, tmp_path):
        clean = tmp_path / "clean"
        clean.mkdir()
        _git(clean, "init", "-q", "-b", "main")
        _git(repo, "merge", "--no-ff", "--no-commit", "side", check=False)
        assert ops._pending_operation_in_dirs([str(clean), str(repo)]) == ops._OP_MERGE
        assert ops._pending_operation_in_dirs([str(clean)]) is None

    def test_rebase_edit_is_not_blocking(self):
        assert ops._OP_REBASE_EDIT not in ops._BLOCKING_OPS
        for op in (ops._OP_MERGE, ops._OP_CHERRY_PICK, ops._OP_REVERT, ops._OP_REBASE):
            assert op in ops._BLOCKING_OPS


class TestDetectFailureSemantics:
    def test_git_missing_fail_open_with_stderr_and_log(self, monkeypatch, tmp_path, capsys):
        def boom(*a, **k):
            raise FileNotFoundError("git")

        monkeypatch.setattr(ops.subprocess, "run", boom)
        sink = _Sink()
        assert ops._pending_operation(tmp_path, sink) is None
        assert "偵測失敗" in capsys.readouterr().err
        assert len(sink.warnings) == 1  # 合併回報一次，不重複

    def test_merge_head_absent_is_not_a_failure(self, repo, capsys):
        sink = _Sink()
        assert ops._merge_in_progress(repo, sink) is False
        assert sink.warnings == []
        assert capsys.readouterr().err == ""


class TestResolveDetectDirs:
    def _inv(self, effective_dir, dir_unknown=False):
        return GitInvocation(
            statement=["git", "commit"], subcommand="commit", subcommand_index=1,
            dash_c_path=None,
            effective_dir=effective_dir, dir_unknown=dir_unknown,
        )

    def test_known_dir_checks_only_effective_dir(self, tmp_path):
        got = ops._resolve_detect_dirs("/cwd", self._inv("/eff"), tmp_path)
        assert got == ["/eff"]

    def test_unknown_dir_checks_cwd_and_root(self, tmp_path):
        got = ops._resolve_detect_dirs("/cwd", self._inv(None, True), tmp_path)
        assert got == ["/cwd", str(tmp_path)]

    def test_no_invocation_dedups_cwd_equal_root(self, tmp_path):
        assert ops._resolve_detect_dirs(str(tmp_path), None, tmp_path) == [str(tmp_path)]
        assert ops._base_dir(None, tmp_path) == str(tmp_path)


class TestResolveDetectDirsMulti:
    def _inv(self, statement, effective_dir):
        idx = statement.index("commit")
        return GitInvocation(
            statement=statement, subcommand="commit", subcommand_index=idx,
            dash_c_path=None, effective_dir=effective_dir,
        )

    def test_union_of_all_targets_in_order(self, tmp_path):
        invs = [self._inv(["git", "commit"], "/a"), self._inv(["git", "commit"], "/b")]
        assert ops._resolve_detect_dirs_multi("/cwd", invs, tmp_path) == ["/a", "/b"]

    def test_git_dir_override_forms_use_override_paths(self, tmp_path):
        for stmt in (
            ["GIT_DIR=/g", "git", "commit"],
            ["git", "--git-dir=/g", "commit"],
            ["git", "--git-dir", "/g", "commit"],
        ):
            got = ops._resolve_detect_dirs_multi("/cwd", [self._inv(stmt, "/cwd")], tmp_path)
            assert got == ["/g"], stmt

    def test_relative_override_joins_effective_dir(self, tmp_path):
        inv = self._inv(["git", "--git-dir=.git", "commit"], "/eff")
        assert ops._resolve_detect_dirs_multi("/cwd", [inv], tmp_path) == ["/eff/.git"]

    def test_no_override_equals_single_resolution(self, tmp_path):
        inv = self._inv(["git", "commit"], "/eff")
        assert ops._resolve_detect_dirs_multi("/cwd", [inv], tmp_path) == ["/eff"]

    def test_pending_in_git_dir_detects_state_file(self, tmp_path):
        assert ops._pending_operation_in_git_dir(str(tmp_path)) is None
        (tmp_path / "MERGE_HEAD").write_text("x\n")
        assert ops._pending_operation_in_git_dir(str(tmp_path)) == ops._OP_MERGE


def test_report_detect_failure_labels_target(capsys):
    ops._report_detect_failure("/d", "rc=1", logging.getLogger("t"), target=ops._TARGET_OTHER)
    err = capsys.readouterr().err
    assert "cherry-pick" in err and "MERGE_HEAD" not in err


class TestGitlinkOverride:
    """`--git-dir`／`GIT_DIR` 指向 worktree 的 `.git` gitlink 檔（真實 worktree）。"""

    @pytest.fixture
    def wt(self, repo, tmp_path):
        w = tmp_path / "wt"
        _git(repo, "worktree", "add", "-q", "-b", "wtbr", str(w), "main")
        return w

    @staticmethod
    def _inv(statement, effective_dir):
        idx = statement.index("commit")
        return GitInvocation(
            statement=statement, subcommand="commit", subcommand_index=idx,
            dash_c_path=None, effective_dir=effective_dir,
        )

    def _detect(self, stmt, base, root, logger=None):
        dirs = ops._resolve_detect_dirs_multi(str(base), [self._inv(stmt, str(base))], root)
        return ops._pending_operation_in_dirs(dirs, logger)

    def _stmts(self, wt):
        g = str(wt / ".git")
        return [
            ["git", f"--git-dir={g}", "commit"],
            ["git", "--git-dir", g, "commit"],
            [f"GIT_DIR={g}", "git", "commit"],
        ]

    def test_git_accepts_gitlink_and_commits_into_worktree(self, repo, wt, tmp_path):
        """前提實測：git 對 gitlink 檔當 --git-dir 照常運作（MERGE_HEAD 會被收尾）。"""
        assert (wt / ".git").is_file()
        _git(wt, "merge", "--no-ff", "--no-commit", "side", check=False)
        gd = _git(wt, "rev-parse", "--absolute-git-dir").stdout.strip()
        assert (Path(gd) / "MERGE_HEAD").is_file()
        (wt / "f.txt").write_text("resolved\n")
        _git(wt, "add", "f.txt")
        r = subprocess.run(
            ["git", f"--git-dir={wt / '.git'}", f"--work-tree={wt}",
             "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "x"],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        parents = _git(wt, "log", "-1", "--format=%P").stdout.split()
        assert len(parents) == 2

    @pytest.mark.parametrize("state", ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"])
    def test_gitlink_with_pending_state_is_blocked(self, repo, wt, tmp_path, state):
        gd = _git(wt, "rev-parse", "--absolute-git-dir").stdout.strip()
        head = _git(wt, "rev-parse", "HEAD").stdout.strip()
        (Path(gd) / state).write_text(head + "\n")
        for stmt in self._stmts(wt):
            assert self._detect(stmt, tmp_path, repo) in ops._BLOCKING_OPS, stmt

    def test_gitlink_without_pending_state_passes(self, repo, wt, tmp_path):
        for stmt in self._stmts(wt):
            assert self._detect(stmt, tmp_path, repo) is None, stmt

    def test_gitlink_relative_path_resolves_from_effective_dir(self, repo, wt):
        gd = _git(wt, "rev-parse", "--absolute-git-dir").stdout.strip()
        (Path(gd) / "MERGE_HEAD").write_text(
            _git(wt, "rev-parse", "HEAD").stdout.strip() + "\n")
        stmt = ["git", "--git-dir=.git", "commit"]
        assert self._detect(stmt, wt, repo) == ops._OP_MERGE

    def test_unparseable_gitlink_blocks_conservatively(self, repo, tmp_path):
        bad = tmp_path / "bad"
        bad.mkdir()
        (bad / ".git").write_text("garbage not a gitlink\n")
        sink = _Sink()
        stmt = ["git", f"--git-dir={bad / '.git'}", "commit"]
        assert self._detect(stmt, tmp_path, repo, sink) in ops._BLOCKING_OPS
