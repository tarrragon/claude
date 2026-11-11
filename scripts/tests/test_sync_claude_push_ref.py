"""sync-claude-push --ref 參數測試（3.2.0-W1-024，E1 對照：帶與不帶參數產物不同）。"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_ref", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_ref"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """tag v1 的 .claude 含 rules.md=old；HEAD 另改為 new 並新增 later.md。"""
    _git(["init"], tmp_path)
    _git(["config", "user.email", "t@example.com"], tmp_path)
    _git(["config", "user.name", "t"], tmp_path)
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "rules.md").write_text("old\n", encoding="utf-8")
    _git(["add", ".claude"], tmp_path)
    _git(["commit", "-m", "v1"], tmp_path)
    _git(["tag", "v1"], tmp_path)
    (claude / "rules.md").write_text("new\n", encoding="utf-8")
    (claude / "later.md").write_text("later\n", encoding="utf-8")
    _git(["add", ".claude"], tmp_path)
    _git(["commit", "-m", "v2"], tmp_path)
    return tmp_path


def test_ref_and_default_produce_different_staging(repo: Path, tmp_path_factory):
    head_dir = tmp_path_factory.mktemp("head")
    ref_dir = tmp_path_factory.mktemp("ref")
    head_n = sync_mod.stage_tracked_tree(repo, head_dir)
    ref_n = sync_mod.stage_tracked_tree(repo, ref_dir, "v1")

    # E1：兩者產物不同
    assert (head_dir / "later.md").exists() != (ref_dir / "later.md").exists()
    assert (head_dir / "rules.md").read_text() != (ref_dir / "rules.md").read_text()
    # 各自內容正確
    assert head_n == 2 and (head_dir / "rules.md").read_text() == "new\n"
    assert ref_n == 1 and (ref_dir / "rules.md").read_text() == "old\n"


def test_default_equals_explicit_head(repo: Path, tmp_path_factory):
    a = tmp_path_factory.mktemp("a")
    b = tmp_path_factory.mktemp("b")
    sync_mod.stage_tracked_tree(repo, a)
    sync_mod.stage_tracked_tree(repo, b, "HEAD")
    assert (a / "rules.md").read_text() == (b / "rules.md").read_text() == "new\n"
    assert (a / "later.md").exists() and (b / "later.md").exists()


def test_parse_args_ref_default_and_value():
    assert sync_mod.parse_args([]).ref == "HEAD"
    assert sync_mod.parse_args(["--ref", "v1"]).ref == "v1"


def test_help_mentions_ref(capsys):
    with pytest.raises(SystemExit) as exc:
        sync_mod.parse_args(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--ref" in out and "tag" in out


def test_resolve_ref_rejects_unknown(repo: Path):
    sync_mod.resolve_ref_or_exit(repo, "v1")
    with pytest.raises(SystemExit) as exc:
        sync_mod.resolve_ref_or_exit(repo, "no-such-ref")
    assert exc.value.code == 1
