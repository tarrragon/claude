"""finish 啟用提交在已安裝 reference-transaction 守衛的 repo 內成功（tarrragon/claude#55）。

既有 test_finish_activation_commit.py 的 fixture repo 未安裝 git 層守衛，
因此沒測到「保護分支 main 上 commit 非豁免檔案 pubspec.yaml」被 deny 的路徑。
本檔的 fixture 安裝真實的 reference-transaction hook（呼叫本 repo 的
git-ref-transaction-content-guard.py），在 main 上跑啟用下一版與
Commit Version Activation。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402

GUARD_HOOK = (
    Path(__file__).resolve().parents[3]
    / "hooks"
    / "git-ref-transaction-content-guard.py"
)
GUARD_LOG_DIR = Path(".claude") / "hook-logs" / "git-ref-transaction-content-guard"

pytestmark = pytest.mark.skipif(
    shutil.which("uv") is None, reason="reference-transaction 守衛以 uv run 執行"
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _install_ref_transaction_hook(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "reference-transaction"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(
        "#!/bin/sh\n"
        '[ "$1" = "prepared" ] || exit 0\n'
        f'exec uv run --quiet "{GUARD_HOOK}" "$@"\n',
        encoding="utf-8",
    )
    hook.chmod(0o755)


@pytest.fixture
def guarded_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """main 分支上的 Flutter fixture，seed 後才安裝守衛。"""
    assert GUARD_HOOK.is_file(), GUARD_HOOK
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".gitignore").write_text(".claude/hook-logs/\n", encoding="utf-8")
    (tmp_path / "pubspec.yaml").write_text(
        "name: sample\nversion: 0.1.0\ndependencies:\n  flutter:\n    sdk: flutter\n",
        encoding="utf-8",
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
    _install_ref_transaction_hook(tmp_path)
    return tmp_path


def _guard_log_text(repo: Path) -> str:
    log_dir = repo / GUARD_LOG_DIR
    if not log_dir.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(log_dir.glob("*.log")))


def _last_commit_files(repo: Path) -> set:
    out = _git(repo, "show", "--name-only", "--pretty=format:", "HEAD")
    return {line for line in out.splitlines() if line}


def test_hook_is_really_installed_and_denies_dependency_change(
    guarded_repo: Path,
) -> None:
    """正向對照（E2）：守衛確實在工作，改依賴行的 commit 被擋。"""
    pubspec = guarded_repo / "pubspec.yaml"
    pubspec.write_text(
        pubspec.read_text(encoding="utf-8").replace("sdk: flutter", "sdk: other"),
        encoding="utf-8",
    )
    _git(guarded_repo, "add", "pubspec.yaml")
    result = subprocess.run(
        ["git", "commit", "-q", "-m", "dep change"],
        cwd=guarded_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "branch-verify" in result.stderr


def test_finish_activation_commit_passes_ref_transaction_guard(
    guarded_repo: Path,
) -> None:
    repo = guarded_repo
    baseline = vr.snapshot_git_status_paths(repo)
    with patch.object(vr, "get_project_root", return_value=repo):
        assert vr.ensure_version_activated(
            "0.1.1", todolist_path=repo / "docs" / "todolist.yaml"
        )
        extra = vr.resolve_activation_version_paths(repo)
        assert vr.commit_changes(
            "0.1.0", baseline=baseline, extra_paths=extra
        ) is True

    assert "pubspec.yaml" in _last_commit_files(repo)
    assert _git(repo, "status", "--porcelain").strip() == ""
    assert vr.check_residual_after_finish(repo, baseline) == []
    log_text = _guard_log_text(repo)
    assert "純版本號變動" in log_text and "0.1.1" in log_text
    assert os.environ["CLAUDE_PROJECT_DIR"] == str(repo)
