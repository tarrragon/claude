"""sync-claude-push／pull 讀取 git 路徑清單的 CJK 檔名 E2（tarrragon/claude#111）。

git 預設 core.quotepath=true 會把非 ASCII 路徑加引號並八進位跳脫；本檔以 tmp git repo
的 CJK 檔名 fixture 驗證各讀取點改 -z 後取得原始路徑，ASCII 檔名維持不變。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


push = _load("sync_claude_push_nul_cjk", "sync-claude-push.py")
pull = _load("sync_claude_pull_nul_cjk", "sync-claude-pull.py")

CJK = "中文檔.md"


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "core.quotepath=true", *args],
        cwd=cwd, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _init(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    return tmp_path


def _commit_all(repo: Path, msg: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def test_push_blocking_entries_cjk_and_ascii(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    (repo / ".claude" / "docs").mkdir(parents=True)
    (repo / ".claude" / "docs" / CJK).write_text("x", encoding="utf-8")
    (repo / ".claude" / "docs" / "plain.md").write_text("x", encoding="utf-8")
    entries = push._list_blocking_entries(repo)
    paths = {p for _, p in entries}
    assert f"docs/{CJK}" in paths
    assert "docs/plain.md" in paths


def test_push_list_base_files_cjk(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    (repo / CJK).write_text("x", encoding="utf-8")
    (repo / "plain.md").write_text("x", encoding="utf-8")
    sha = _commit_all(repo, "base")
    assert push._list_base_files(repo, sha) == {CJK, "plain.md"}


def test_pull_compute_upstream_delta_cjk(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    (repo / "plain.md").write_text("a", encoding="utf-8")
    base = _commit_all(repo, "base")
    (repo / CJK).write_text("x", encoding="utf-8")
    (repo / "plain.md").write_text("b", encoding="utf-8")
    _commit_all(repo, "next")
    assert pull.compute_upstream_delta(repo, base) == {CJK: "A", "plain.md": "M"}


def test_pull_is_git_tracked_case_fallback_cjk(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    (repo / "dir").mkdir()
    (repo / "dir" / "Ab中.md").write_text("x", encoding="utf-8")
    _commit_all(repo, "base")
    # 大小寫不同 → 走 ls-files 列舉 fallback；CJK 名稱須以原始形式比對
    assert pull._is_git_tracked("dir/ab中.md", repo) is True
    assert pull._is_git_tracked("dir/nope中.md", repo) is False


def test_pull_list_base_files_cjk(tmp_path: Path) -> None:
    repo = _init(tmp_path)
    (repo / CJK).write_text("x", encoding="utf-8")
    (repo / "plain.md").write_text("x", encoding="utf-8")
    sha = _commit_all(repo, "base")
    assert pull._list_base_files(repo, sha) == {CJK, "plain.md"}
