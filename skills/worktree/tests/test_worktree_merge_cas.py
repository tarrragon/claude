"""
worktree merge 隔離索引 CAS 合併的 tmp repo 測試（0.5.0-W1-238.1）

五種情境：HEAD 於合併中被推進、空合併、三方合併成功、文字衝突中止、工作區有他人修改；
另含合併前檢查掛點的失敗、例外、未註冊三個對照。
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import worktree_manager as wm  # noqa: E402
import merge_cas as mc  # noqa: E402

A_LINES = [f"line{i}\n" for i in range(1, 11)]


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def commit_file(repo, name, text, msg):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-m", msg)


def replace_line(repo, name, lineno, text):
    lines = (repo / name).read_text().splitlines(keepends=True)
    lines[lineno - 1] = text + "\n"
    return "".join(lines)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_sleep", lambda _s: None)
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    commit_file(r, "a.txt", "".join(A_LINES), "base a")
    commit_file(r, "b.txt", "b\n", "base b")
    return r


def make_branch(repo, edits):
    """在 feat 分支提交 edits（{檔名: 全文}），回到 main。"""
    git(repo, "checkout", "-b", "feat")
    for name, text in edits.items():
        commit_file(repo, name, text, f"feat {name}")
    git(repo, "checkout", "main")


def head(repo):
    return git(repo, "rev-parse", "HEAD")


def no_merge_state(repo):
    assert not (repo / ".git" / "MERGE_HEAD").exists()


class TestCasMergeScenarios:
    def test_head_advanced_during_merge_still_lands(self, repo):
        make_branch(repo, {"b.txt": "b-feat\n"})
        calls = []

        def advance_once(commit, ref, expected_old, attempt):
            calls.append((commit, expected_old, attempt))
            if attempt == 1:
                commit_file(repo, "c.txt", "c\n", "concurrent")
            return wm.CheckResult(True)

        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=advance_once)

        assert out.ok and out.attempts == 2
        assert [c[2] for c in calls] == [1, 2]
        assert calls[0][0] != calls[1][0]  # 每次嘗試依新 HEAD 產生不同 commit
        no_merge_state(repo)
        assert head(repo) == out.commit_sha
        assert (repo / "c.txt").exists() and (repo / "b.txt").read_text() == "b-feat\n"
        assert git(repo, "status", "--porcelain") == ""

    def test_empty_merge_rejected(self, repo):
        make_branch(repo, {"b.txt": "same\n"})
        commit_file(repo, "b.txt", "same\n", "main makes the same change")
        before = head(repo)

        out = wm.merge_branch_cas("feat", repo=str(repo))

        assert not out.ok and "空合併" in out.error
        assert head(repo) == before
        no_merge_state(repo)

    def test_three_way_merge_success(self, repo):
        make_branch(repo, {"a.txt": replace_line_text(A_LINES, 9, "feat9")})
        commit_file(repo, "a.txt", replace_line_text(A_LINES, 1, "main1"), "main edit")
        main_before = head(repo)

        out = wm.merge_branch_cas("feat", repo=str(repo))

        assert out.ok
        merged = (repo / "a.txt").read_text().splitlines()
        assert merged[0] == "main1" and merged[8] == "feat9"
        assert git(repo, "rev-parse", "HEAD^1") == main_before
        assert git(repo, "rev-parse", "HEAD^2") == git(repo, "rev-parse", "feat")
        assert "a.txt" in out.synced and git(repo, "status", "--porcelain") == ""

    def test_text_conflict_aborts_without_moving_head(self, repo):
        make_branch(repo, {"a.txt": replace_line_text(A_LINES, 5, "feat5")})
        commit_file(repo, "a.txt", replace_line_text(A_LINES, 5, "main5"), "main edit")
        before = head(repo)

        out = wm.merge_branch_cas("feat", repo=str(repo))

        assert not out.ok and "衝突" in out.error
        assert head(repo) == before
        no_merge_state(repo)
        assert git(repo, "status", "--porcelain") == ""

    def test_dirty_shared_workspace_not_overwritten(self, repo):
        make_branch(repo, {"a.txt": replace_line_text(A_LINES, 9, "feat9"), "b.txt": "b-feat\n"})
        (repo / "a.txt").write_text("someone else's edit\n")

        out = wm.merge_branch_cas("feat", repo=str(repo))

        assert out.ok
        assert (repo / "a.txt").read_text() == "someone else's edit\n"
        assert "a.txt" in out.skipped and "a.txt" not in out.synced
        assert out.synced == ["b.txt"] and (repo / "b.txt").read_text() == "b-feat\n"


def replace_line_text(lines, lineno, text):
    copy = list(lines)
    copy[lineno - 1] = text + "\n"
    return "".join(copy)


class TestPreMergeCheckHook:
    def test_check_failure_leaves_ref_unchanged(self, repo):
        make_branch(repo, {"b.txt": "b-feat\n"})
        before = head(repo)
        seen = {}

        def reject(commit, ref, expected_old, attempt):
            seen.update(commit=commit, ref=ref, old=expected_old)
            return wm.CheckResult(False, "suite red")

        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=reject)

        assert not out.ok and out.error == "suite red"
        assert seen["ref"] == "refs/heads/main" and seen["old"] == before
        assert head(repo) == before
        no_merge_state(repo)
        assert git(repo, "status", "--porcelain") == ""

    def test_check_exception_leaves_ref_unchanged(self, repo):
        make_branch(repo, {"b.txt": "b-feat\n"})
        before = head(repo)

        def boom(commit, ref, expected_old, attempt):
            raise RuntimeError("runner crashed")

        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=boom)

        assert not out.ok and "runner crashed" in out.error
        assert head(repo) == before
        no_merge_state(repo)

    def test_no_check_registered_updates_ref(self, repo):
        make_branch(repo, {"b.txt": "b-feat\n"})
        before = head(repo)

        out = wm.merge_branch_cas("feat", repo=str(repo))

        assert out.ok and head(repo) == out.commit_sha != before

    def test_check_receives_commit_reachable_for_detached_checkout(self, repo, tmp_path):
        make_branch(repo, {"b.txt": "b-feat\n"})
        probe = tmp_path / "probe"

        def verify(commit, ref, expected_old, attempt):
            git(repo, "worktree", "add", "--detach", str(probe), commit)
            content = (probe / "b.txt").read_text()
            git(repo, "worktree", "remove", "--force", str(probe))
            return wm.CheckResult(content == "b-feat\n", "content mismatch")

        out = wm.merge_branch_cas("feat", repo=str(repo), pre_merge_check=verify)

        assert out.ok
