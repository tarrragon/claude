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


SPEC_PATH = "docs/spec/billing/SPEC-012.md"


def _staged_repo(tmp_path: Path, content: str) -> Path:
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(["init", "-q"], repo)
    (repo / "methodologies").mkdir()
    (repo / "methodologies/x-methodology.md").write_text(content, encoding="utf-8")
    _git(["add", "-A"], repo)
    return repo


def test_both_tracks_listed_separately_on_same_file(tmp_path, capsys):
    """E1 對照：同一檔同時含 ticket ID 與專案路徑，兩軌各自列出，不合併計數。"""
    repo = _staged_repo(tmp_path, f"見 {SPEC_PATH} 與 {HIT_ID}\n")
    sync_mod.report_rule8_hits_before_push(repo)
    out = capsys.readouterr().out
    assert f"- .claude/methodologies/x-methodology.md: {HIT_ID}" in out
    assert "[rule8 推送前報告｜專案路徑軌] 待推送內容有 1 檔含未豁免的專案路徑，共 1 處" in out
    assert f"- .claude/methodologies/x-methodology.md: {SPEC_PATH}" in out


def test_path_only_hit_not_reported_as_clean(tmp_path, capsys):
    """只有路徑命中時不得印「無未豁免命中」：舊版只掃 ticket ID 軌，會把這種推送報成乾淨。"""
    repo = _staged_repo(tmp_path, f"見 {SPEC_PATH}\n")
    sync_mod.report_rule8_hits_before_push(repo)
    out = capsys.readouterr().out
    assert "無未豁免命中" not in out
    assert "無未豁免的專案 ticket ID" in out
    assert f"- .claude/methodologies/x-methodology.md: {SPEC_PATH}" in out


def test_framework_relative_path_not_listed_in_path_track(tmp_path, capsys):
    """路徑軌沿用守衛的排除：框架內可解析的相對路徑不列。"""
    repo = _staged_repo(tmp_path, "模組見 lib/hook_io.py\n")
    sync_mod.report_rule8_hits_before_push(repo)
    out = capsys.readouterr().out
    assert "專案路徑軌" not in out
    assert "無未豁免命中" in out


def test_scan_failure_reported_and_returns_block(push_repo, monkeypatch, capsys):
    """報告腳本載入失敗：不拋例外，寫 stderr，回傳應阻擋（fail-closed，用戶裁定）。"""
    monkeypatch.setattr(sync_mod, "_RULE8_REPORT_SCRIPT", push_repo / "missing.py")
    assert sync_mod.report_rule8_hits_before_push(push_repo) is True
    captured = capsys.readouterr()
    assert "[rule8 推送前報告] 掃描失敗，無法確認待推送內容，視為應阻擋" in captured.err
    assert "待推送內容有" not in captured.out


# ---------- 推送前 rule8 閘門（3.4.0-W1-309.2.2，用戶裁定改為阻擋） ----------


def test_enforce_blocks_unexempted_ticket_id(push_repo, capsys):
    """正向對照（E2）：含未豁免 ticket ID 的待推送檔被擋下，exit 1 並提示覆寫旗標。"""
    with pytest.raises(SystemExit) as exc:
        sync_mod.enforce_rule8_before_push(push_repo, None)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert f"- .claude/references/edited.md: {HIT_ID}" in out
    assert "[FAIL] rule8 推送前檢查未通過" in out
    assert '--rule8-override "<理由>"' in out


def test_enforce_passes_clean_push_without_override(tmp_path, capsys):
    """乾淨內容不需覆寫即放行（閘門不誤擋）。"""
    repo = _staged_repo(tmp_path, "乾淨內容\n")
    sync_mod.enforce_rule8_before_push(repo, None)
    assert "[FAIL]" not in capsys.readouterr().out


def test_enforce_path_track_only_does_not_block(tmp_path, capsys):
    """專案路徑軌只提示：只有路徑命中時放行。"""
    repo = _staged_repo(tmp_path, f"見 {SPEC_PATH}\n")
    sync_mod.enforce_rule8_before_push(repo, None)
    out = capsys.readouterr().out
    assert "[FAIL]" not in out
    assert f"- .claude/methodologies/x-methodology.md: {SPEC_PATH}" in out


def test_enforce_override_allows_and_prints_reason(push_repo, capsys):
    """帶覆寫旗標時放行，印出理由。"""
    sync_mod.enforce_rule8_before_push(push_repo, "上游歷史存量，已建票清理")
    out = capsys.readouterr().out
    assert "[FAIL]" not in out
    assert "已以 --rule8-override 放行：上游歷史存量，已建票清理" in out


def test_enforce_blocks_when_guard_load_fails(push_repo, monkeypatch, capsys):
    """失敗落點：守衛載入失敗 → 阻擋並提示覆寫旗標。"""
    monkeypatch.setattr(sync_mod, "_RULE8_REPORT_SCRIPT", push_repo / "missing.py")
    with pytest.raises(SystemExit) as exc:
        sync_mod.enforce_rule8_before_push(push_repo, None)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "掃描失敗" in captured.err
    assert "--rule8-override" in captured.out


def test_enforce_blocks_when_git_diff_fails(tmp_path, capsys):
    """失敗落點：git diff 失敗（非 git 目錄）→ 阻擋並提示覆寫旗標。"""
    not_repo = tmp_path / "not-a-repo"
    not_repo.mkdir()
    with pytest.raises(SystemExit) as exc:
        sync_mod.enforce_rule8_before_push(not_repo, None)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "git diff 失敗" in captured.err
    assert "--rule8-override" in captured.out


def _staged_repo_with_bytes(tmp_path: Path, data: bytes) -> Path:
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(["init", "-q"], repo)
    (repo / "references").mkdir()
    (repo / "references/blob.md").write_bytes(data)
    _git(["add", "-A"], repo)
    return repo


NON_UTF8 = b"\xff\xfe\x00 not utf-8 \x80\x81"


def test_enforce_blocks_unreadable_pending_file(tmp_path, capsys):
    """正向對照（E2）：待推送檔非 UTF-8、未經掃描，不帶覆寫時被擋（fail-closed）。"""
    repo = _staged_repo_with_bytes(tmp_path, NON_UTF8)
    with pytest.raises(SystemExit) as exc:
        sync_mod.enforce_rule8_before_push(repo, None)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "1 檔無法讀取（非 UTF-8 或讀取失敗），未經掃描，視為應阻擋" in out
    assert "- .claude/references/blob.md" in out
    assert "無未豁免命中" not in out


def test_enforce_unreadable_pending_file_passes_with_override(tmp_path, capsys):
    """同一份不可讀內容，帶覆寫時放行（E1 對照）。"""
    repo = _staged_repo_with_bytes(tmp_path, NON_UTF8)
    sync_mod.enforce_rule8_before_push(repo, "二進位資產，已人工確認")
    out = capsys.readouterr().out
    assert "[FAIL]" not in out
    assert "已以 --rule8-override 放行：二進位資產，已人工確認" in out


def test_override_reason_written_to_commit_message_body():
    msg = sync_mod.build_push_commit_message("3.4.0", "摘要", [], rule8_override="理由 A")
    assert msg.splitlines()[0] == "v3.4.0: 摘要"
    assert "--rule8-override: 理由 A" in msg.splitlines()[2:]


def test_override_and_clean_deletions_both_in_body():
    msg = sync_mod.build_push_commit_message("3.4.0", "s", ["a.md"], rule8_override="r")
    assert msg.splitlines()[2:] == ["--rule8-override: r", "--clean 刪除 1 個檔案:", "- a.md"]


def test_override_flag_requires_non_empty_reason(capsys):
    with pytest.raises(SystemExit) as exc:
        sync_mod.parse_args(["--rule8-override", "  "])
    assert exc.value.code == 2
    assert "--rule8-override 的理由不可為空" in capsys.readouterr().err


def test_override_flag_parsed():
    assert sync_mod.parse_args(["--rule8-override", "原因"]).rule8_override == "原因"
    assert sync_mod.parse_args([]).rule8_override is None
