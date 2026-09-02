"""set-where 三組合（只 value / 只 --layer / 兩者皆有）修復回歸測試。

修復對象：value（路徑清單）與 --layer 同時提供時，value 先前會被
_execute_set_dict_subfields 的通用子欄位覆寫邏輯吃掉（先寫入 layer 子欄位
再被 --layer 覆寫），where.files 完全未同步，CLI 亦無任何提示。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.commands import fields as fields_mod


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
        "where:\n  layer: 待定義\n  files: []\n"
        "---\n\n"
        "# Execution Log\n\n## Task Summary\n\nTest.\n"
    )
    path.write_text(fm, encoding="utf-8")


@pytest.fixture
def set_where_ticket(tmp_path, monkeypatch):
    tid = "0.0.0-W0-SETWHERECOMBO"
    md_path = tmp_path / f"{tid}.md"
    _write_ticket_md(md_path, tid)

    monkeypatch.setattr(fields_mod, "get_ticket_path", lambda version, t: md_path)
    monkeypatch.setattr("ticket_system.lib.parser.get_ticket_path", lambda version, t: md_path)
    monkeypatch.setattr("ticket_system.lib.paths.get_project_root", lambda: tmp_path)

    example_file = tmp_path / "src" / "core" / "example.py"
    example_file.parent.mkdir(parents=True, exist_ok=True)
    example_file.write_text("", encoding="utf-8")

    return tid, md_path


def _load_where(tid: str) -> dict:
    from ticket_system.lib.ticket_ops import load_and_validate_ticket

    ticket, error = load_and_validate_ticket("0.0.0", tid)
    assert error is None
    return ticket["where"]


class TestSetWhereOnlyValue:
    """只帶路徑清單（value），未帶 --layer：既有行為，files 同步、layer 不變。"""

    def test_files_synced_layer_unchanged(self, set_where_ticket, capsys):
        tid, md_path = set_where_ticket
        args = argparse.Namespace(
            ticket_id=tid,
            value="src/core/example.py",
            layer=None,
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        where = _load_where(tid)
        assert where["files"] == ["src/core/example.py"]
        assert where["layer"] == "待定義"


class TestSetWhereOnlyLayer:
    """只帶 --layer：files 不變（維持既有行為），layer 更新。"""

    def test_layer_updated_files_unchanged(self, set_where_ticket, capsys):
        tid, md_path = set_where_ticket
        args = argparse.Namespace(
            ticket_id=tid,
            value=None,
            layer="Infrastructure",
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        where = _load_where(tid)
        assert where["layer"] == "Infrastructure"
        assert where["files"] == []


class TestSetWhereValueAndLayer:
    """value 與 --layer 同時提供：兩者皆須寫入（修復標的）。"""

    def test_both_files_and_layer_updated(self, set_where_ticket, capsys):
        tid, md_path = set_where_ticket
        args = argparse.Namespace(
            ticket_id=tid,
            value="src/core/example.py",
            layer="Infrastructure",
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        where = _load_where(tid)
        assert where["layer"] == "Infrastructure"
        assert where["files"] == ["src/core/example.py"]

    def test_output_contains_files_sync_line(self, set_where_ticket, capsys):
        tid, md_path = set_where_ticket
        args = argparse.Namespace(
            ticket_id=tid,
            value="src/core/example.py",
            layer="Infrastructure",
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        out = capsys.readouterr().out
        assert "files" in out
        assert "src/core/example.py" in out

    def test_multiple_paths_both_files_and_layer_updated(self, set_where_ticket, capsys):
        tid, md_path = set_where_ticket
        second_file = md_path.parent / "src" / "core" / "example2.py"
        second_file.write_text("", encoding="utf-8")
        args = argparse.Namespace(
            ticket_id=tid,
            value="src/core/example.py,src/core/example2.py",
            layer="Domain",
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        where = _load_where(tid)
        assert where["layer"] == "Domain"
        assert where["files"] == ["src/core/example.py", "src/core/example2.py"]

    def test_explicit_files_flag_takes_precedence_over_value(self, set_where_ticket, capsys):
        """value 提供路徑，但同時明確帶 --files 時，--files 優先（既有行為不變）。"""
        tid, md_path = set_where_ticket
        args = argparse.Namespace(
            ticket_id=tid,
            value="src/core/example.py",
            layer="Infrastructure",
            files="src/core/example.py",
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        where = _load_where(tid)
        assert where["layer"] == "Infrastructure"
        assert where["files"] == ["src/core/example.py"]

    def test_non_path_value_with_layer_does_not_sync_files(self, set_where_ticket, capsys):
        """value 非路徑型（架構描述文字）+ --layer：files 不同步，layer 正常寫入。"""
        tid, md_path = set_where_ticket
        args = argparse.Namespace(
            ticket_id=tid,
            value="N/A",
            layer="Presentation",
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        where = _load_where(tid)
        assert where["layer"] == "Presentation"
        assert where["files"] == []


class TestSetWhereAutoCommit:
    """where.files 範圍變更觸發 auto-commit，且不污染主 repo 共用 index。

    對照 set-acceptance / append-log 既有 auto-commit 保護等級：兩條輸入
    路徑（value 位置參數的路徑型輸入、--files 子欄位）皆須接上。
    """

    def _patch_auto_commit(self, monkeypatch):
        from ticket_system.lib import git_utils

        calls = []

        def _fake_auto_commit(path, ticket_id, section, operation="append-log"):
            calls.append(
                {"path": path, "ticket_id": ticket_id, "section": section, "operation": operation}
            )
            return "committed"

        monkeypatch.setattr(git_utils, "_auto_commit_ticket_md", _fake_auto_commit)
        return calls

    def test_value_path_triggers_auto_commit_with_set_where_operation(
        self, set_where_ticket, monkeypatch, capsys
    ):
        tid, md_path = set_where_ticket
        calls = self._patch_auto_commit(monkeypatch)
        args = argparse.Namespace(
            ticket_id=tid,
            value="src/core/example.py",
            layer=None,
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        assert len(calls) == 1
        assert calls[0]["ticket_id"] == tid
        assert calls[0]["operation"] == "set-where"
        assert "set-where" in calls[0]["operation"]

    def test_files_flag_triggers_auto_commit_with_set_where_operation(
        self, set_where_ticket, monkeypatch, capsys
    ):
        tid, md_path = set_where_ticket
        calls = self._patch_auto_commit(monkeypatch)
        args = argparse.Namespace(
            ticket_id=tid,
            value=None,
            layer=None,
            files="src/core/example.py",
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        assert len(calls) == 1
        assert calls[0]["ticket_id"] == tid
        assert calls[0]["operation"] == "set-where"

    def test_layer_only_does_not_trigger_auto_commit(self, set_where_ticket, monkeypatch, capsys):
        """who/how 的 set 操作不受影響：--layer without --files/value 不同步 files，
        不應觸發 auto-commit（acceptance 第 2 項）。"""
        tid, md_path = set_where_ticket
        calls = self._patch_auto_commit(monkeypatch)
        args = argparse.Namespace(
            ticket_id=tid,
            value=None,
            layer="Infrastructure",
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        assert calls == []

    def test_auto_commit_delegates_to_isolated_index_helper_only(
        self, set_where_ticket, monkeypatch, capsys
    ):
        """呼叫端本身不得繞過 `_auto_commit_ticket_md` 自行操作 git add/commit
        （acceptance 第 3 項的呼叫端側保證）：提交邏輯全權委派給該 helper
        （其內部走隔離索引 CAS，不觸碰共用 index），呼叫端只需被觀察到恰好
        呼叫一次此 helper、不存在其他 git 寫入路徑。"""
        tid, md_path = set_where_ticket
        calls = self._patch_auto_commit(monkeypatch)

        args = argparse.Namespace(
            ticket_id=tid,
            value="src/core/example.py",
            layer=None,
            files=None,
        )

        rc = fields_mod.execute_set_where(args, "0.0.0")

        assert rc == 0
        assert len(calls) == 1
