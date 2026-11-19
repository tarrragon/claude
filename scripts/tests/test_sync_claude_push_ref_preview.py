"""sync-claude-push --ref 時 --dry-run 預覽與 skill 殘留檢查改取 ref 樹（3.4.0-W1-215）。

E1 對照：同一個 fixture 各跑帶 ref、不帶 ref，斷言結果不同。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_ref_preview", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_ref_preview"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """tag v1 的 skill 乾淨；HEAD 的 skill 引用不存在的 lib/ghost.py（殘留）。"""
    _git(["init"], tmp_path)
    _git(["config", "user.email", "t@example.com"], tmp_path)
    _git(["config", "user.name", "t"], tmp_path)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "real.py").write_text("x = 1\n", encoding="utf-8")
    skill = tmp_path / ".claude" / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# demo\n\nclean text\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "v1"], tmp_path)
    _git(["tag", "v1"], tmp_path)
    (skill / "SKILL.md").write_text(
        "# demo\n\nSee lib/ghost.py for details.\n", encoding="utf-8"
    )
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "v2"], tmp_path)
    return tmp_path


def _residue_ok(repo: Path, ref: str) -> bool:
    claude_dir = repo / ".claude"
    if ref == "HEAD":
        return sync_mod.check_skill_residue(claude_dir, False)
    tree = sync_mod._stage_ref_claude_dir(repo, ref)
    try:
        return sync_mod.check_skill_residue(
            claude_dir, False, skills_dir=tree / "skills"
        )
    finally:
        import shutil

        shutil.rmtree(tree, ignore_errors=True)


def test_residue_check_ref_and_default_differ(repo: Path):
    assert _residue_ok(repo, "HEAD") is False
    assert _residue_ok(repo, "v1") is True


def test_residue_check_ref_path_blocks_residual_ref(repo: Path):
    """正向對照：ref 路徑（sha，非 HEAD 字串）遇含殘留的 commit 仍阻擋。"""
    import shutil

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    tree = sync_mod._stage_ref_claude_dir(repo, sha)
    try:
        assert sync_mod.check_skill_residue(
            repo / ".claude", False, skills_dir=tree / "skills"
        ) is False
    finally:
        shutil.rmtree(tree, ignore_errors=True)


def test_residue_default_skills_dir_unchanged(repo: Path):
    explicit = sync_mod.check_skill_residue(
        repo / ".claude", False, skills_dir=repo / ".claude" / "skills"
    )
    assert explicit is sync_mod.check_skill_residue(repo / ".claude", False)


def _run_dry(monkeypatch, repo: Path, ref: str | None) -> Path:
    seen: dict[str, Path] = {}
    monkeypatch.setattr(sync_mod, "find_project_root", lambda: repo)
    monkeypatch.setattr(
        sync_mod,
        "run_git",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", ""),
    )

    def fake_report(claude_dir: Path, clone: Path) -> None:
        seen["claude_dir"] = claude_dir
        seen["listing"] = sorted(p.name for p in (claude_dir / "skills").iterdir())
        seen["text"] = (claude_dir / "skills" / "demo" / "SKILL.md").read_text()

    monkeypatch.setattr(sync_mod, "_dry_run_report_pc_collision", fake_report)
    # clone 失敗時不會呼叫預覽；讓 clone 成功以進入預覽分支
    monkeypatch.setattr(
        sync_mod,
        "run_git",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""),
    )
    monkeypatch.setattr(sync_mod, "get_last_sync_timestamp", lambda _p: "2000-01-01")
    monkeypatch.setattr(sync_mod, "collect_claude_commits", lambda *_a, **_k: [])
    if ref is None:
        sync_mod.run_dry_run()
    else:
        sync_mod.run_dry_run(ref)
    return seen["claude_dir"], seen["text"]


def test_dry_run_preview_uses_ref_tree(monkeypatch, repo: Path):
    head_dir, head_text = _run_dry(monkeypatch, repo, None)
    ref_dir, ref_text = _run_dry(monkeypatch, repo, "v1")
    # 不帶 ref：讀 checkout；帶 ref：讀 ref 樹（暫存目錄）
    assert head_dir == repo / ".claude"
    assert ref_dir != repo / ".claude"
    assert "ghost" in head_text and "ghost" not in ref_text
    assert not ref_dir.exists()  # 暫存已清理


def test_help_mentions_ref_scope(capsys):
    with pytest.raises(SystemExit):
        sync_mod.parse_args(["--help"])
    out = capsys.readouterr().out
    assert "殘留檢查" in out
