"""claim 時輸出 error-pattern 候選清單（3.3.0-W1-208.2）。

驗證四件事：
- 有 where.files 的 IMP：列出依相關度排序的前 N 筆與總數（正向對照：檔名直接
  相關的 pattern 必須出現在清單中）
- 比對失敗：不拋例外（claim 不受影響），失敗寫 stderr 與日誌
- where.files 為空、或豁免型別（DOC/ANA/REF）：不輸出候選
- 超過上限：只列上限筆數，標頭附總數
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ticket_system.commands import lifecycle


@pytest.fixture
def project(tmp_path, monkeypatch):
    """建立含 error-patterns 目錄的假專案，並把 claim 的專案根導向它。"""
    ep_dir = tmp_path / ".claude" / "error-patterns" / "implementation"
    ep_dir.mkdir(parents=True)
    monkeypatch.setattr(lifecycle, "get_project_root", lambda: tmp_path)
    # 日誌目錄改經 _hook_logs_root（3.3.0-W1-204.1.6.2）；一併導向假專案，
    # test_failure_does_not_raise_and_reports 讀此處檔案，寫到別處即 FileNotFoundError。
    monkeypatch.setattr(
        lifecycle, "_hook_logs_root", lambda: tmp_path / ".claude" / "hook-logs"
    )
    return tmp_path


def _write_pattern(project: Path, name: str, body: str) -> None:
    path = project / ".claude" / "error-patterns" / "implementation" / name
    path.write_text(body, encoding="utf-8")


def _imp_ticket(files):
    return {"id": "9.9.9-W1-001", "type": "IMP", "where": {"files": files}}


def test_imp_with_where_files_lists_related_pattern(project, capsys):
    _write_pattern(project, "IMP-900-widget-parser-crash.md", "widget_parser 解析失敗")
    _write_pattern(project, "IMP-901-unrelated.md", "與本票無關的內容")

    lifecycle._print_error_pattern_candidates(
        _imp_ticket([".claude/skills/demo/widget_parser.py"])
    )

    out = capsys.readouterr().out
    assert "[error-pattern 候選] 與 1 個 error-pattern 相關" in out
    assert "IMP-900-widget-parser-crash.md" in out
    assert "IMP-901-unrelated.md" not in out


def test_failure_does_not_raise_and_reports(project, capsys, monkeypatch):
    def boom(ticket, logger):
        raise RuntimeError("simulated checker failure")

    monkeypatch.setattr(lifecycle, "_find_error_pattern_candidates", boom)

    lifecycle._print_error_pattern_candidates(
        _imp_ticket([".claude/skills/demo/widget_parser.py"])
    )

    captured = capsys.readouterr()
    assert "比對失敗" in captured.err
    assert "simulated checker failure" in captured.err
    assert "[error-pattern 候選] 與" not in captured.out
    log_file = project / ".claude" / "hook-logs" / lifecycle._CLAIM_EP_LOG_FILENAME
    assert "simulated checker failure" in log_file.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "ticket",
    [
        _imp_ticket([]),
        {"id": "9.9.9-W1-002", "type": "IMP"},
        {"id": "9.9.9-W1-003", "type": "DOC",
         "where": {"files": [".claude/skills/demo/widget_parser.py"]}},
        {"id": "9.9.9-W1-004", "type": "ANA",
         "where": {"files": [".claude/skills/demo/widget_parser.py"]}},
    ],
    ids=["empty-files", "no-where", "doc-exempt", "ana-exempt"],
)
def test_no_output_when_empty_or_exempt(project, capsys, ticket):
    _write_pattern(project, "IMP-900-widget-parser-crash.md", "widget_parser 解析失敗")

    lifecycle._print_error_pattern_candidates(ticket)

    assert "[error-pattern 候選]" not in capsys.readouterr().out


def test_lists_at_most_limit_with_total(project, capsys):
    total = lifecycle.CLAIM_ERROR_PATTERN_CANDIDATE_LIMIT + 3
    for i in range(total):
        _write_pattern(project, f"IMP-{i:03d}-x.md", "widget_parser")

    lifecycle._print_error_pattern_candidates(
        _imp_ticket([".claude/skills/demo/widget_parser.py"])
    )

    out = capsys.readouterr().out
    limit = lifecycle.CLAIM_ERROR_PATTERN_CANDIDATE_LIMIT
    assert f"與 {total} 個 error-pattern 相關，依相關度列出前 {limit} 個" in out
    assert out.count("   - .claude/error-patterns/") == limit
