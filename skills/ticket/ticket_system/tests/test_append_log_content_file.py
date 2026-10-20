"""append-log --content-file：自檔案讀取內容，不經命令列傳遞。

覆蓋：
1. 檔案內容逐字寫入（含反引號、$(...)、換行）
2. 與位置參數同時給 / 都不給 -> 拒絕，票面不變
3. 讀檔失敗 -> 非 0，票面不變
4. 位置參數用法不變（E1）
5. --replace 與 --content-file 併用
6. parser 層：content 變為可省略，--content-file 已註冊
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib import ticket_loader
from ticket_system.lib.parser import parse_frontmatter


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


@pytest.fixture
def patch_paths(tmp_ticket_dir: Path, monkeypatch):
    def _path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _load(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    monkeypatch.setattr(ticket_loader, "get_ticket_path", _path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _load)

    from ticket_system.commands import track_acceptance as ta_mod

    monkeypatch.setattr(ta_mod, "get_ticket_path", _path)
    monkeypatch.setattr(ta_mod, "load_ticket", _load)


TID = "0.0.0-W0-CF1"
BODY = (
    "## Solution\n"
    "<!-- Schema[IMP/Solution]: 選填 -->\n\n"
    "既有內容 X\n\n"
    "---\n\n"
    "## Test Results\n"
)


def _make_ticket(d: Path) -> Path:
    path = d / f"{TID}.md"
    fm = (
        "---\n"
        f"id: {TID}\n"
        "title: test\n"
        "type: IMP\n"
        "status: in_progress\n"
        "assigned: true\n"
        "tdd_phase: phase3b\n"
        "children: []\n"
        "blockedBy: []\n"
        "acceptance: []\n"
        "spawned_tickets: []\n"
        "---\n\n"
    )
    path.write_text(fm + BODY, encoding="utf-8")
    return path


def _call(content=None, content_file=None, replace=False) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(
        ticket_id=TID,
        section="Solution",
        content=content,
        content_file=content_file,
        replace=replace,
    )
    return execute_append_log(ns, "0.0.0")


class TestContentFile:
    def test_verbatim_content(self, tmp_ticket_dir, patch_paths, tmp_path):
        path = _make_ticket(tmp_ticket_dir)
        payload = "行1 `git status` $(echo hi)\n行2 \"q\" 'x' \\n $HOME\n"
        f = tmp_path / "in.txt"
        f.write_text(payload, encoding="utf-8")
        assert _call(content_file=str(f)) == 0
        text = path.read_text(encoding="utf-8")
        assert "行1 `git status` $(echo hi)\n行2 \"q\" 'x' \\n $HOME" in text
        assert "既有內容 X" in text

    def test_both_given_rejected(self, tmp_ticket_dir, patch_paths, tmp_path):
        path = _make_ticket(tmp_ticket_dir)
        before = path.read_text(encoding="utf-8")
        f = tmp_path / "in.txt"
        f.write_text("檔案內容", encoding="utf-8")
        assert _call(content="位置內容", content_file=str(f)) != 0
        assert path.read_text(encoding="utf-8") == before

    def test_neither_given_rejected(self, tmp_ticket_dir, patch_paths):
        path = _make_ticket(tmp_ticket_dir)
        before = path.read_text(encoding="utf-8")
        assert _call() != 0
        assert path.read_text(encoding="utf-8") == before

    def test_unreadable_file_fails_ticket_unchanged(
        self, tmp_ticket_dir, patch_paths, tmp_path, capsys
    ):
        path = _make_ticket(tmp_ticket_dir)
        before = path.read_text(encoding="utf-8")
        assert _call(content_file=str(tmp_path / "missing.txt")) != 0
        assert "--content-file" in capsys.readouterr().err
        assert path.read_text(encoding="utf-8") == before

    def test_non_utf8_file_fails_ticket_unchanged(
        self, tmp_ticket_dir, patch_paths, tmp_path, capsys
    ):
        path = _make_ticket(tmp_ticket_dir)
        before = path.read_text(encoding="utf-8")
        f = tmp_path / "bad.bin"
        f.write_bytes(b"\xff\xfe\x80invalid")
        assert _call(content_file=str(f)) != 0
        assert "--content-file" in capsys.readouterr().err
        assert path.read_text(encoding="utf-8") == before

    @pytest.mark.parametrize("payload", ["", "   \n\t\n"])
    @pytest.mark.parametrize("replace", [False, True])
    def test_empty_or_blank_file_rejected_ticket_unchanged(
        self, tmp_ticket_dir, patch_paths, tmp_path, capsys, payload, replace
    ):
        path = _make_ticket(tmp_ticket_dir)
        before = path.read_text(encoding="utf-8")
        f = tmp_path / "empty.txt"
        f.write_text(payload, encoding="utf-8")
        assert _call(content_file=str(f), replace=replace) != 0
        assert "--content-file" in capsys.readouterr().err
        text = path.read_text(encoding="utf-8")
        assert text == before
        assert "既有內容 X" in text

    def test_positional_unchanged(self, tmp_ticket_dir, patch_paths):
        path = _make_ticket(tmp_ticket_dir)
        assert _call(content="位置內容 Y") == 0
        text = path.read_text(encoding="utf-8")
        assert "既有內容 X" in text and "位置內容 Y" in text

    def test_replace_with_content_file(self, tmp_ticket_dir, patch_paths, tmp_path):
        path = _make_ticket(tmp_ticket_dir)
        f = tmp_path / "in.txt"
        f.write_text("覆寫自檔案", encoding="utf-8")
        assert _call(content_file=str(f), replace=True) == 0
        text = path.read_text(encoding="utf-8")
        assert "既有內容 X" not in text
        assert "覆寫自檔案" in text


class TestParser:
    def test_parser_accepts_content_file_without_positional(self):
        from ticket_system.commands.track import _register_acceptance_commands

        root = argparse.ArgumentParser()
        _register_acceptance_commands(root.add_subparsers(dest="track_cmd"))
        ns = root.parse_args(
            ["append-log", "T-1", "--section", "Solution",
             "--content-file", "/tmp/x"]
        )
        assert ns.content_file == "/tmp/x"
        assert ns.content is None
