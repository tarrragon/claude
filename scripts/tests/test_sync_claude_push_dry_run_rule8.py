"""sync-claude-push --dry-run 輸出推送前 rule8 報告。

dry-run 依正式推送的順序在暫存 clone 上準備內容，再呼叫同一個
report_rule8_hits_before_push。E1 對照：同一場景內容含／不含專案 ticket ID，報告結果不同。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_dry_run_rule8", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_dry_run_rule8"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]

HIT_ID = "0.2.1-W3-777"


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _init(path: Path) -> None:
    path.mkdir(parents=True)
    _git(["init", "-q", "-b", "main"], path)
    _git(["config", "user.email", "t@example.com"], path)
    _git(["config", "user.name", "t"], path)


def _scene(tmp_path: Path, edited_text: str) -> tuple[Path, Path]:
    """上游有 references/edited.md 舊版；本地把它改成 edited_text 並 commit。"""
    upstream = tmp_path / "upstream"
    _init(upstream)
    (upstream / "references").mkdir()
    (upstream / "references/edited.md").write_text("舊內容\n", encoding="utf-8")
    _git(["add", "-A"], upstream)
    _git(["commit", "-q", "-m", "base"], upstream)

    project = tmp_path / "project"
    _init(project)
    refs = project / ".claude" / "references"
    refs.mkdir(parents=True)
    (refs / "edited.md").write_text(edited_text, encoding="utf-8")
    (project / ".claude" / "VERSION").write_text("1.0.1\n", encoding="utf-8")
    (project / ".claude" / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    _git(["add", "-A"], project)
    _git(["commit", "-q", "-m", "local"], project)
    return project, upstream


def test_rule8_report_lists_hit(tmp_path: Path, capsys):
    project, upstream = _scene(tmp_path, f"新增引用 {HIT_ID}\n")
    sync_mod._dry_run_report_rule8(project, upstream, "HEAD")
    out = capsys.readouterr().out
    assert "[rule8 推送前報告] 待推送內容有 1 檔" in out
    assert f"- .claude/references/edited.md: {HIT_ID}" in out


def test_rule8_report_clean_content_has_no_hits(tmp_path: Path, capsys):
    project, upstream = _scene(tmp_path, "無專案 ID\n")
    sync_mod._dry_run_report_rule8(project, upstream, "HEAD")
    out = capsys.readouterr().out
    assert "無未豁免命中" in out
    assert "待推送內容有" not in out
    assert "正式推送會被擋" not in out


def test_dry_run_states_real_push_would_be_blocked(tmp_path: Path, capsys):
    """E1 對照：同一場景含未豁免 ID 時 dry-run 明示正式推送會被擋，且預覽本身不 exit。"""
    project, upstream = _scene(tmp_path, f"新增引用 {HIT_ID}\n")
    sync_mod._dry_run_report_rule8(project, upstream, "HEAD")
    out = capsys.readouterr().out
    assert "[dry-run] 正式推送會被擋" in out
    assert "--rule8-override" in out


def test_dry_run_states_block_for_unreadable_pending_file(tmp_path: Path, capsys):
    """待推送檔非 UTF-8 時，dry-run 列出該檔並明示正式推送會被擋。"""
    project, upstream = _scene(tmp_path, "乾淨內容\n")
    (project / ".claude" / "references" / "edited.md").write_bytes(b"\xff\xfe\x80 bin")
    _git(["add", "-A"], project)
    _git(["commit", "-q", "-m", "binary"], project)
    sync_mod._dry_run_report_rule8(project, upstream, "HEAD")
    out = capsys.readouterr().out
    assert "- .claude/references/edited.md" in out
    assert "無法讀取" in out
    assert "[dry-run] 正式推送會被擋" in out


def test_rule8_report_without_release_files_does_not_abort(tmp_path: Path, capsys):
    """缺 VERSION／CHANGELOG 時預覽照常輸出報告，不在 copy_release_files exit。"""
    project, upstream = _scene(tmp_path, f"新增引用 {HIT_ID}\n")
    (project / ".claude" / "VERSION").unlink()
    sync_mod._dry_run_report_rule8(project, upstream, "HEAD")
    assert f"- .claude/references/edited.md: {HIT_ID}" in capsys.readouterr().out


def test_run_dry_run_includes_rule8_report(tmp_path: Path, monkeypatch, capsys):
    project, upstream = _scene(tmp_path, f"新增引用 {HIT_ID}\n")
    monkeypatch.setattr(sync_mod, "REPO_URL", str(upstream))
    monkeypatch.setattr(sync_mod, "find_project_root", lambda: project)
    monkeypatch.setattr(sync_mod, "collect_claude_commits", lambda *_a, **_k: [])
    sync_mod.run_dry_run()
    out = capsys.readouterr().out
    assert "--- 推送前 rule8 報告（dry-run）---" in out
    assert f"- .claude/references/edited.md: {HIT_ID}" in out
    # 預覽不推送：上游 repo 仍只有 base commit
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=str(upstream), capture_output=True, text=True
    ).stdout.strip().splitlines()
    assert len(log) == 1
