"""finish 啟用提交納入本次 bump 的版本檔 E2（tarrragon/claude#55）。

缺陷：finish 的 Activate Next Version 會 bump 版本檔（Flutter 為 pubspec.yaml），
但 Commit Version Activation 的 stage 範圍只收 CHANGELOG.md 與 docs/，版本檔
殘留於工作區，殘留守衛因而 rc=1。
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _flutter_repo(tmp_path: Path) -> Path:
    """Flutter fixture：pubspec 0.1.0、todolist 有已完成 0.1.0 與 planned 0.1.1。"""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "pubspec.yaml").write_text(
        "name: sample\nversion: 0.1.0\n", encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0] - 2026-09-01\n\n舊版本\n", encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "todolist.yaml").write_text(
        'last_updated: "2026-07-01"\n\n'
        "versions:\n"
        '  - version: "0.1.0"\n'
        "    status: active\n"
        '  - version: "0.1.1"\n'
        "    status: planned\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def _activate_next(repo: Path) -> None:
    with patch.object(vr, "get_project_root", return_value=repo):
        assert vr.ensure_version_activated(
            "0.1.1", todolist_path=repo / "docs" / "todolist.yaml"
        )


def _last_commit_files(repo: Path) -> set:
    out = _git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
    return {line for line in out.splitlines() if line}


def test_activation_commit_includes_bumped_version_file(tmp_path: Path) -> None:
    repo = _flutter_repo(tmp_path)
    baseline = vr.snapshot_git_status_paths(repo)
    _activate_next(repo)
    assert "version: 0.1.1" in (repo / "pubspec.yaml").read_text(encoding="utf-8")

    with patch.object(vr, "get_project_root", return_value=repo):
        extra = vr.resolve_activation_version_paths(repo)
        assert vr.commit_changes(
            "0.1.0", baseline=baseline, extra_paths=extra
        ) is True

    assert "pubspec.yaml" in _last_commit_files(repo)
    assert vr.check_residual_after_finish(repo, baseline) == []
    assert _git(repo, "status", "--porcelain").strip() == ""


def test_activation_commit_without_extra_paths_leaves_version_file(
    tmp_path: Path,
) -> None:
    """對照：不傳 extra_paths 時版本檔不納入（守衛維持原行為）。"""
    repo = _flutter_repo(tmp_path)
    baseline = vr.snapshot_git_status_paths(repo)
    _activate_next(repo)
    with patch.object(vr, "get_project_root", return_value=repo):
        vr.commit_changes("0.1.0", baseline=baseline)
    assert "pubspec.yaml" not in _last_commit_files(repo)
    assert vr.check_residual_after_finish(repo, baseline) == ["pubspec.yaml"]


def test_non_version_file_outside_docs_is_not_staged(tmp_path: Path) -> None:
    """E2：差集內的非版本檔、非 docs 檔不被 extra_paths 擴權納入。"""
    repo = _flutter_repo(tmp_path)
    baseline = vr.snapshot_git_status_paths(repo)
    _activate_next(repo)
    (repo / "stray.txt").write_text("not ours", encoding="utf-8")

    with patch.object(vr, "get_project_root", return_value=repo):
        extra = vr.resolve_activation_version_paths(repo)
        assert vr.commit_changes(
            "0.1.0", baseline=baseline, extra_paths=extra
        ) is True

    committed = _last_commit_files(repo)
    assert "pubspec.yaml" in committed
    assert "stray.txt" not in committed
    assert vr.check_residual_after_finish(repo, baseline) == ["stray.txt"]


def test_resolve_paths_monorepo_subdir_version_file(tmp_path: Path) -> None:
    """monorepo：config 指定子目錄版本檔時，回傳相對 root 的路徑。"""
    sub = tmp_path / "app"
    sub.mkdir()
    (sub / "pubspec.yaml").write_text("name: a\nversion: 0.1.0\n", encoding="utf-8")
    cfg = {"version_source": {"primary": "app/pubspec.yaml"}}
    with patch.object(vr, "load_version_release_config", return_value=cfg):
        assert vr.resolve_activation_version_paths(tmp_path) == {"app/pubspec.yaml"}


# ---------------------------------------------------------------------------
# 0.4.2-W1-045：啟用提交必須推送到遠端，摘要依實際推送結果產生
# ---------------------------------------------------------------------------


def _repo_with_bare_remote(tmp_path: Path):
    """Flutter fixture 加 bare remote；seed 已推送，啟用提交尚未。"""
    work = tmp_path / "work"
    work.mkdir(parents=True)
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    repo = _flutter_repo(work)
    _git(repo, "branch", "-M", "main")
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "origin", "main")
    return repo, bare


def _make_activation_commit(repo: Path) -> str:
    """跑啟用步驟與其提交，回傳提交前的 HEAD。"""
    baseline = vr.snapshot_git_status_paths(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    _activate_next(repo)
    with patch.object(vr, "get_project_root", return_value=repo):
        extra = vr.resolve_activation_version_paths(repo)
        assert vr.commit_changes(
            "0.1.0", baseline=baseline, extra_paths=extra,
            commit_message="docs: 啟用",
        )
    return head_before


def _remote_main(bare: Path) -> str:
    return _git(bare, "rev-parse", "main").strip()


def _reject_pushes(bare: Path) -> None:
    hook = bare / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'rejected by test' >&2\nexit 1\n")
    hook.chmod(0o755)


def test_e1_activation_push_success_vs_rejected(tmp_path: Path, capsys) -> None:
    """E1 對照：同一 fixture，推送成功與 remote 拒絕，HEAD 對遠端的比對結果必須不同。"""
    ok_repo, ok_bare = _repo_with_bare_remote(tmp_path / "ok")
    ok_before = _make_activation_commit(ok_repo)
    with patch.object(vr, "get_project_root", return_value=ok_repo):
        ok_result = vr.publish_activation_commit(ok_repo, ok_before)
    ok_synced = _git(ok_repo, "rev-parse", "HEAD").strip() == _remote_main(ok_bare)

    bad_repo, bad_bare = _repo_with_bare_remote(tmp_path / "bad")
    _reject_pushes(bad_bare)
    bad_before = _make_activation_commit(bad_repo)
    capsys.readouterr()
    with patch.object(vr, "get_project_root", return_value=bad_repo):
        bad_result = vr.publish_activation_commit(bad_repo, bad_before)
    bad_err = capsys.readouterr().err
    bad_head = _git(bad_repo, "rev-parse", "HEAD").strip()
    bad_synced = bad_head == _remote_main(bad_bare)

    assert (ok_result, ok_synced) == (True, True)
    assert (bad_result, bad_synced) == (False, False)
    assert bad_head[:7] in bad_err


def test_summary_text_follows_actual_push_result(capsys) -> None:
    vr.print_summary("0.1.0", True, False, activation_pushed=True)
    pushed_out = capsys.readouterr().out
    vr.print_summary("0.1.0", True, False, activation_pushed=False)
    unpushed_out = capsys.readouterr().out
    assert "已推送" in pushed_out
    assert "已推送" not in unpushed_out
    assert "未推送" in unpushed_out


def test_no_new_commit_means_no_push_needed(tmp_path: Path) -> None:
    repo, bare = _repo_with_bare_remote(tmp_path)
    head = _git(repo, "rev-parse", "HEAD").strip()
    _reject_pushes(bare)
    with patch.object(vr, "get_project_root", return_value=repo):
        assert vr.publish_activation_commit(repo, head) is True
