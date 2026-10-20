"""
lib.dispatch_scope 單元測試（自 bare-commit-guard 抽出的並行期目標過濾）。

鎖定「保守方向」：目標無法判定、帶 GIT_DIR／--git-dir 類覆寫時一律不過濾
（全數計入），這是放寬並行期判定曾開出繞過的位置。每個不過濾案例都配
「可判定時確實過濾」的對照（E2：只斷言保守路徑分辨不出過濾是否已死）。
"""

import logging
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import dispatch_scope as scope  # noqa: E402
from lib.git_command_parse import find_git_invocations  # noqa: E402

_LOG = logging.getLogger("test_dispatch_scope")


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True,
    )


@pytest.fixture
def repos(tmp_path):
    """主 checkout 與其 linked worktree。"""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "f.txt").write_text("x\n")
    _git(main, "add", "f.txt")
    _git(main, "commit", "-q", "-m", "base")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "wtbr", str(wt), "main")
    return main.resolve(), wt.resolve()


def _inv(command, base_dir):
    return find_git_invocations(command, {"commit"}, str(base_dir), scan=True)


class TestOverridesGitDir:
    @pytest.mark.parametrize("command", [
        "GIT_DIR=/x/.git git commit -m m",
        "GIT_WORK_TREE=/x git commit -m m",
        "env GIT_DIR=/x/.git git commit -m m",
        "git --git-dir=/x/.git commit -m m",
        "git --work-tree=/x commit -m m",
    ])
    def test_override_forms_detected(self, command, tmp_path):
        (inv,) = _inv(command, tmp_path)
        assert scope._overrides_git_dir(inv) is True

    def test_plain_and_dash_c_not_override(self, tmp_path):
        for command in ("git commit -m m", "git -C %s commit -m m" % tmp_path):
            (inv,) = _inv(command, tmp_path)
            assert scope._overrides_git_dir(inv) is False


class TestCommitTargetCheckouts:
    def test_known_target_resolves_to_toplevel(self, repos):
        main, wt = repos
        assert scope._commit_target_checkouts(_inv("git commit -m m", wt), _LOG) == [wt]
        got = scope._commit_target_checkouts(
            _inv("git -C %s commit -m m" % main, wt), _LOG
        )
        assert got == [main]

    def test_chained_commits_union_each_target(self, repos):
        main, wt = repos
        command = "git -C %s commit -m a && git -C %s commit -m b" % (wt, main)
        assert scope._commit_target_checkouts(_inv(command, wt), _LOG) == [wt, main]

    def test_git_dir_override_returns_none_not_filtered(self, repos):
        main, wt = repos
        command = "GIT_DIR=%s/.git git commit -m m" % main
        assert scope._commit_target_checkouts(_inv(command, wt), _LOG) is None

    def test_one_unknown_among_many_returns_none(self, repos):
        main, wt = repos
        command = "git commit -m a && cd $SOMEWHERE && git commit -m b"
        assert scope._commit_target_checkouts(_inv(command, wt), _LOG) is None

    def test_no_invocations_returns_none(self):
        assert scope._commit_target_checkouts(None, _LOG) is None
        assert scope._commit_target_checkouts([], _LOG) is None

    def test_missing_directory_is_not_filtered(self, tmp_path):
        gone = tmp_path / "gone"
        assert scope._commit_target_checkout(
            _inv("git -C %s commit -m m" % gone, tmp_path), _LOG
        ) is None

    def test_non_git_directory_is_not_filtered(self, tmp_path):
        assert scope._commit_target_checkout(_inv("git commit -m m", tmp_path), _LOG) is None


class TestFilterDispatchesForTargets:
    def _entry(self, ticket, checkout):
        return {"ticket_id": ticket, "files": ["a"], "work_checkout": str(checkout)}

    def test_none_targets_keeps_everything(self, repos):
        main, wt = repos
        entries = [self._entry("T-1", main), self._entry("T-2", wt)]
        assert scope._filter_dispatches_for_targets(entries, None) == entries

    def test_known_target_keeps_only_matching_entries(self, repos):
        main, wt = repos
        entries = [self._entry("T-1", main), self._entry("T-2", wt)]
        assert scope._filter_dispatches_for_targets(entries, [wt]) == [entries[1]]
        assert scope._filter_dispatches_for_targets(entries, [main, wt]) == entries

    def test_legacy_entry_without_checkout_is_kept(self, repos):
        main, wt = repos
        legacy = {"ticket_id": "T-0", "files": ["a"]}
        assert scope._filter_dispatches_for_targets([legacy], [wt]) == [legacy]


class TestRegistryFailSemantics:
    def test_registry_unreadable_is_unavailable_not_session_ended(self, monkeypatch, tmp_path):
        def boom(*a, **k):
            raise OSError("nope")

        monkeypatch.setattr(scope, "get_registry_paths", boom)
        assert scope._read_registry_sessions(tmp_path, _LOG) == ({}, False)

    def test_unavailable_registry_keeps_all_entries(self, monkeypatch, tmp_path):
        monkeypatch.setattr(scope, "_read_registry_sessions", lambda r, lg: ({}, False))
        entries = [{"ticket_id": "T-1", "files": ["a"], "session_id": "s-gone"}]
        assert scope._exclude_orphan_confirmed(entries, tmp_path, "s-self", _LOG) == entries

    def test_no_session_ids_skips_registry_read(self, monkeypatch, tmp_path):
        def must_not_run(*a, **k):
            raise AssertionError("不應讀 registry")

        monkeypatch.setattr(scope, "_read_registry_sessions", must_not_run)
        entries = [{"ticket_id": "T-1", "files": ["a"]}]
        assert scope._exclude_orphan_confirmed(entries, tmp_path, "s-self", _LOG) == entries


class TestDeclaredFilesAndSafeRead:
    def test_active_dispatch_read_failure_fails_open_to_empty(self, monkeypatch, tmp_path):
        def boom(root):
            raise RuntimeError("corrupt")

        monkeypatch.setattr(scope, "get_active_dispatches", boom)
        assert scope._get_active_dispatches_safe(tmp_path) == []

    def test_live_where_files_replaces_snapshot(self, monkeypatch, tmp_path):
        monkeypatch.setattr(scope, "_read_ticket_where_files", lambda t, r: ["new.py"])
        out = scope._with_live_declared_files(
            [{"ticket_id": "T-1", "files": ["old.py"]}], tmp_path, _LOG
        )
        assert out[0]["files"] == ["new.py"]

    def test_read_failure_falls_back_to_snapshot(self, monkeypatch, tmp_path):
        def boom(t, r):
            raise ValueError("no ticket")

        monkeypatch.setattr(scope, "_read_ticket_where_files", boom)
        entry = {"ticket_id": "T-1", "files": ["old.py"]}
        assert scope._with_live_declared_files([entry], tmp_path, _LOG) == [entry]

    def test_empty_ticket_id_falls_back_to_snapshot(self, tmp_path):
        entry = {"ticket_id": "", "files": ["old.py"]}
        assert scope._with_live_declared_files([entry], tmp_path, _LOG) == [entry]
