"""Tests: consumer 執行 sync-pull 時，本地 local-only 產物不被刪除（3.0.0-W1-006）。

背景：canonical 曾追蹤 analyses/、migration-backups/、plans/、.version-release.yaml，
3.0.0 停止追蹤後上游 delta 對這些路徑是刪除。consumer 的本地同名檔屬 consumer 自己的產物，
pull 不得刪除（delta 路徑與 full overlay 路徑各驗一次）。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_local_only", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_local_only"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

LOCAL_ONLY_FILES = [
    "analyses/a.md",
    "migration-backups/20260101-000000/t.md",
    "plans/p.md",
    ".version-release.yaml",
]


def _git(args: list[str], cwd: Path) -> str:
    out = subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )
    return out.stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upstream_deleting_local_only(tmp_path: Path) -> tuple[Path, str]:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["init", "-q"], upstream)
    _git(["config", "user.email", "t@t.t"], upstream)
    _git(["config", "user.name", "t"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    for rel in LOCAL_ONLY_FILES:
        _write(upstream, rel, "canonical\n")
    _write(upstream, "rules/keep.md", "x\n")
    _git(["add", "-A"], upstream)
    _git(["commit", "-q", "-m", "base"], upstream)
    base = _git(["rev-parse", "HEAD"], upstream)
    for rel in LOCAL_ONLY_FILES:
        (upstream / rel).unlink()
    _git(["add", "-A"], upstream)
    _git(["commit", "-q", "-m", "stop tracking local-only"], upstream)
    return upstream, base


def _consumer(tmp_path: Path, content: str) -> Path:
    project = tmp_path / "proj"
    for rel in LOCAL_ONLY_FILES:
        _write(project / ".claude", rel, content)
    _write(project / ".claude", "rules/keep.md", "x\n")
    return project


@pytest.mark.parametrize("content", ["consumer own\n", "canonical\n"])
def test_apply_delta_keeps_local_only_files(tmp_path, content):
    """上游刪除 local-only 路徑時，不論本地是否與 base 相同都保留。"""
    upstream, base = _upstream_deleting_local_only(tmp_path)
    project = _consumer(tmp_path, content)

    pull.apply_upstream_delta(project, upstream, base)

    for rel in LOCAL_ONLY_FILES:
        assert (project / ".claude" / rel).exists(), rel


def test_cleanup_stale_files_keeps_local_only_files(tmp_path):
    """full overlay 的過時檔清理不刪 consumer 本地 local-only 產物。"""
    project = _consumer(tmp_path, "consumer own\n")
    claude = project / ".claude"

    pull.cleanup_stale_files(claude, {Path("rules/keep.md")}, project_root=project)

    for rel in LOCAL_ONLY_FILES:
        assert (claude / rel).exists(), rel
