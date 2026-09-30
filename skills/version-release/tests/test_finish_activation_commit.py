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
