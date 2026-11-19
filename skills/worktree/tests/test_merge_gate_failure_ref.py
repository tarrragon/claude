"""紅燈合併 commit 的保留 ref：建立、gc 後可回放、過期清理、失敗 fail-open。一律在拋棄式 repo。"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import merge_gate as mg  # noqa: E402

NS = mg.FAILURE_REF_NAMESPACE
DAY = 24 * 3600
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)


def make_commit(repo, date):
    env = {**os.environ, "GIT_COMMITTER_DATE": f"{date} +0000", "GIT_AUTHOR_DATE": f"{date} +0000",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    out = git(repo, "commit-tree", EMPTY_TREE, "-m", f"c{date}", env=env)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    assert git(r, "init", "-q").returncode == 0
    git(r, "hash-object", "-t", "tree", "-w", "--stdin")  # 空 tree 寫入物件庫
    subprocess.run(["git", "-C", str(r), "mktree"], input="", text=True, capture_output=True)
    return r


def test_ref_created_and_survives_gc(repo):
    sha = make_commit(repo, 1_700_000_000)
    assert mg.preserve_failure_commit(str(repo), sha, now=1_700_000_000 + DAY) == f"{NS}/{sha}"
    assert git(repo, "rev-parse", f"{NS}/{sha}").stdout.strip() == sha
    git(repo, "reflog", "expire", "--expire=now", "--all")
    git(repo, "gc", "--prune=now", "-q")
    assert git(repo, "cat-file", "-t", sha).stdout.strip() == "commit"


def test_expired_refs_pruned_fresh_kept(repo):
    old = make_commit(repo, 1_700_000_000)
    new = make_commit(repo, 1_700_000_000 + 40 * DAY)
    git(repo, "update-ref", f"{NS}/{old}", old)
    mg.preserve_failure_commit(str(repo), new, now=1_700_000_000 + 41 * DAY)
    assert git(repo, "for-each-ref", "--format=%(refname)", NS).stdout.split() == [f"{NS}/{new}"]


def test_non_sha_tag_skipped(repo):
    assert mg.preserve_failure_commit(str(repo), "nocommit") == ""
    assert git(repo, "for-each-ref", NS).stdout == ""


def test_failure_is_fail_open_with_stderr_and_log(tmp_path, capsys):
    not_repo = tmp_path / "plain"
    not_repo.mkdir()
    assert mg.preserve_failure_commit(str(not_repo), "a" * 40) == ""
    assert "建立失敗" in capsys.readouterr().err
    assert "建立失敗" in (not_repo / mg._LOG_FILE).read_text()


def test_rc_reason_names_ref():
    reason = mg._rc_reason("hooks", 1, "1 failed", "", None, f"{NS}/abc")
    assert reason.endswith(f"合併 commit 回放 ref：{NS}/abc")
    assert "回放 ref" not in mg._rc_reason("hooks", 1, "1 failed")
