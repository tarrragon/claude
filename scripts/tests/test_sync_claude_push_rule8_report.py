"""sync-push 推送前的 rule8 掃描報告（3.3.0-W1-203.3）。

缺陷：sync-claude-push.py 只在產生 CHANGELOG 時剝除票號，不掃描要推送的檔案內容；
全樹 overlay 推送把本端存量帶進 canonical，推送前沒有任何可見性。
修復：提交暫存 repo 前，以 rule8-stock-report.py 掃描本次將改變遠端的檔案並報告；只報告不阻擋。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push_rule8", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push_rule8"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]

HIT_ID = "0.2.1-W3-777"


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture
def push_repo(tmp_path: Path) -> Path:
    """模擬推送用暫存 repo（根即 .claude 內容）：base 已有含 ID 的存量檔，本次新增／修改數檔。"""
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@example.com"], repo)
    _git(["config", "user.name", "t"], repo)
    (repo / "references").mkdir()
    (repo / "references/unchanged.md").write_text(f"遠端存量 {HIT_ID}\n", encoding="utf-8")
    (repo / "references/edited.md").write_text("舊內容\n", encoding="utf-8")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "base"], repo)
    # 本次推送帶來的變更
    (repo / "references/edited.md").write_text(f"新增引用 {HIT_ID}\n", encoding="utf-8")
    (repo / "references/new-clean.md").write_text("無專案 ID\n", encoding="utf-8")
    (repo / "hooks/tests").mkdir(parents=True)
    (repo / "hooks/tests/test_x.py").write_text(f"ID = '{HIT_ID}'\n", encoding="utf-8")
    _git(["add", "-A"], repo)
    return repo


def test_changed_file_with_ticket_id_listed(push_repo, capsys):
    sync_mod.report_rule8_hits_before_push(push_repo)
    out = capsys.readouterr().out
    assert "[rule8 推送前報告] 待推送內容有 1 檔" in out
    assert f"- .claude/references/edited.md: {HIT_ID}" in out
    # 未改變的遠端存量、無 ID 的新檔、測試路徑皆不列
    assert "unchanged.md" not in out
    assert "new-clean.md" not in out
    assert "test_x.py" not in out


def test_clean_push_reports_no_hits(tmp_path, capsys):
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(["init", "-q"], repo)
    (repo / "a.md").write_text("乾淨內容\n", encoding="utf-8")
    _git(["add", "-A"], repo)
    sync_mod.report_rule8_hits_before_push(repo)
    assert "待推送 1 檔，無未豁免命中" in capsys.readouterr().out


def test_scan_failure_written_to_stderr_without_raising(push_repo, monkeypatch, capsys):
    monkeypatch.setattr(sync_mod, "_RULE8_REPORT_SCRIPT", push_repo / "missing.py")
    sync_mod.report_rule8_hits_before_push(push_repo)  # 不得拋例外，推送照常進行
    captured = capsys.readouterr()
    assert "[rule8 推送前報告] 掃描失敗，照常推送" in captured.err
    assert "待推送內容有" not in captured.out
