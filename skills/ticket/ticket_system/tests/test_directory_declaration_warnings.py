"""目錄級 where.files 宣告的 WARNING/硬擋測試（0.2.1-W3-891 / PC-BAL-040）。

覆蓋範圍：
1. `field_validators.directory_declaration_warnings`（create.py / fields.py
   共用的核心判定邏輯，逐案測試）
2. `fields.execute_set_where` 的 `--files` 子欄位路徑實際輸出 WARNING

`track_dispatch.py` 的硬擋行為已在 `test_track_dispatch.py` 覆蓋。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.commands import fields as fields_mod
from ticket_system.lib import field_validators


class TestDirectoryDeclarationWarnings:
    def test_trailing_slash_triggers_warning(self):
        warnings = field_validators.directory_declaration_warnings([".claude/hooks/"], "IMP")
        assert len(warnings) == 1
        assert "[WARNING]" in warnings[0]
        assert ".claude/hooks/" in warnings[0]

    def test_precise_file_path_no_warning(self):
        warnings = field_validators.directory_declaration_warnings(
            [".claude/hooks/example-guard-hook.py"], "IMP"
        )
        assert warnings == []

    def test_read_marker_suppresses_warning(self):
        warnings = field_validators.directory_declaration_warnings([".claude/hooks/::read"], "IMP")
        assert warnings == []

    def test_ana_type_suggests_read_default(self):
        warnings = field_validators.directory_declaration_warnings([".claude/hooks/"], "ANA")
        assert len(warnings) == 1
        assert "::read" in warnings[0]

    def test_doc_type_suggests_read_default(self):
        warnings = field_validators.directory_declaration_warnings([".claude/hooks/"], "DOC")
        assert len(warnings) == 1
        assert "::read" in warnings[0]

    def test_imp_type_does_not_default_to_read_suggestion_wording(self):
        # 兩種模板皆含 ::read 建議文字，差別在於是否以「本票類型建議唯讀」
        # 開頭；IMP 型不應套用該開頭字樣。
        warnings = field_validators.directory_declaration_warnings([".claude/hooks/"], "IMP")
        assert "本票類型建議唯讀存取" not in warnings[0]

    def test_multiple_tokens_each_evaluated(self):
        warnings = field_validators.directory_declaration_warnings(
            [".claude/hooks/", ".claude/hooks/example-guard-hook.py", ".claude/lib/"], "IMP"
        )
        assert len(warnings) == 2

    def test_empty_tokens_no_warning(self):
        assert field_validators.directory_declaration_warnings([], "IMP") == []


# --- fields.py execute_set_where --files 整合測試 -------------------------


def _write_ticket_md(path: Path, tid: str, ticket_type: str = "IMP") -> None:
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        f"type: {ticket_type}\n"
        "status: in_progress\n"
        "assigned: true\n"
        "children: []\n"
        "blockedBy: []\n"
        "acceptance: []\n"
        "spawned_tickets: []\n"
        "where:\n  layer: Infrastructure\n  files: []\n"
        "---\n\n"
        "# Execution Log\n\n## Task Summary\n\nTest.\n"
    )
    path.write_text(fm, encoding="utf-8")


@pytest.fixture
def set_where_ticket(tmp_path, monkeypatch):
    tid = "0.0.0-W0-SETWHERE"
    md_path = tmp_path / f"{tid}.md"
    _write_ticket_md(md_path, tid)

    monkeypatch.setattr(fields_mod, "get_ticket_path", lambda version, t: md_path)
    monkeypatch.setattr("ticket_system.lib.parser.get_ticket_path", lambda version, t: md_path)

    # 0.2.1-W3-278: 新增的 where.files 路徑存在性檢查以 get_project_root() 為基準，
    # 這裡導向 tmp_path 並實際建立測試引用的路徑，讓既有「精確路徑不觸發目錄
    # 級 WARNING」的測試不因新檢查而多出無關的路徑不存在 WARNING。
    monkeypatch.setattr("ticket_system.lib.paths.get_project_root", lambda: tmp_path)
    example_file = tmp_path / ".claude" / "hooks" / "example-guard-hook.py"
    example_file.parent.mkdir(parents=True, exist_ok=True)
    example_file.write_text("", encoding="utf-8")

    return tid


def test_execute_set_where_files_flag_warns_on_directory(set_where_ticket, capsys):
    args = argparse.Namespace(
        ticket_id=set_where_ticket,
        value=None,
        layer=None,
        files=".claude/hooks/",
    )
    rc = fields_mod.execute_set_where(args, "0.0.0")

    assert rc == 0
    out = capsys.readouterr().out
    assert "[WARNING]" in out
    assert ".claude/hooks/" in out


def test_execute_set_where_files_flag_no_warning_for_precise_path(set_where_ticket, capsys):
    args = argparse.Namespace(
        ticket_id=set_where_ticket,
        value=None,
        layer=None,
        files=".claude/hooks/example-guard-hook.py",
    )
    rc = fields_mod.execute_set_where(args, "0.0.0")

    assert rc == 0
    out = capsys.readouterr().out
    assert "[WARNING]" not in out


def test_execute_set_where_files_flag_warns_on_missing_path(set_where_ticket, capsys):
    args = argparse.Namespace(
        ticket_id=set_where_ticket,
        value=None,
        layer=None,
        files=".claude/hooks/does-not-exist.py",
    )
    rc = fields_mod.execute_set_where(args, "0.0.0")

    assert rc == 0
    out = capsys.readouterr().out
    assert "[WARNING]" in out
    assert "路徑不存在" in out
    assert ".claude/hooks/does-not-exist.py" in out
