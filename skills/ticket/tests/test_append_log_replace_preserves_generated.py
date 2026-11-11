"""append-log --replace 只覆寫人寫部分，保留 CLI 自動產生的子節。

背景：--replace 原只保留派發日誌與 Commit 規範兩個 H3，Context Bundle 的
auto-extracted 區塊（Task Reference 等子節）與 create 寫入的〈查重紀錄〉會被
整段刪除，且票檔受讀檔守衛保護無法手動還原。

情境（同一批 fixture 形態，含與不含自動子節對照）：
1. Context Bundle 含 auto-extracted 區塊 + 人寫段落 → 區塊保留、人寫段落被取代
2. Problem Analysis 含〈查重紀錄〉+ 人寫 H3 → 查重紀錄保留、人寫 H3 被取代
3. 不含任何自動子節 → 整段覆寫，行為與修改前相同（E1 對照）
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
    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    monkeypatch.setattr(ticket_loader, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _fake_load_ticket)

    from ticket_system.commands import track_acceptance as ta_mod

    monkeypatch.setattr(ta_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ta_mod, "load_ticket", _fake_load_ticket)


def _write_ticket(path: Path, tid: str, body: str) -> None:
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        "type: IMP\n"
        "status: in_progress\n"
        "assigned: true\n"
        "children: []\n"
        "blockedBy: []\n"
        "acceptance: []\n"
        "spawned_tickets: []\n"
        "---\n\n"
    )
    path.write_text(fm + body, encoding="utf-8")


def _replace(tid: str, section: str, content: str) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(ticket_id=tid, section=section, content=content, replace=True)
    return execute_append_log(ns, "0.0.0")


AUTO_BLOCK = (
    "<!-- auto-extracted: sources: 0.0.0-W0-001 | chars: 120 -->\n"
    "### Task Reference\n"
    "- 來源票的 why 摘要  # from 0.0.0-W0-001\n"
    "\n"
    "### Related Files\n"
    "- src/a.py  # from 0.0.0-W0-001\n"
)

DEDUP_RECORD = (
    "### 查重紀錄\n"
    "\n"
    "`--dedup-checked none`，查重關鍵字（逐字）：\n"
    "\n"
    "- `關鍵字`\n"
)


def test_context_bundle_auto_block_preserved(tmp_ticket_dir, patch_paths, capsys):
    tid = "0.0.0-W0-PRES1"
    path = tmp_ticket_dir / f"{tid}.md"
    body = (
        "## Context Bundle\n\n"
        + AUTO_BLOCK
        + "\n舊的人寫補充說明\n\n"
        "---\n\n"
        "## NeedsContext\n"
    )
    _write_ticket(path, tid, body)

    assert _replace(tid, "Context Bundle", "新的人寫補充說明") == 0

    text = path.read_text(encoding="utf-8")
    assert AUTO_BLOCK.rstrip() in text
    assert "### Task Reference" in text and "### Related Files" in text
    assert "新的人寫補充說明" in text
    assert "舊的人寫補充說明" not in text
    assert "## NeedsContext" in text
    assert "保留自動產生的子節" in capsys.readouterr().out


def test_dedup_record_preserved_and_human_h3_replaced(tmp_ticket_dir, patch_paths, capsys):
    tid = "0.0.0-W0-PRES2"
    path = tmp_ticket_dir / f"{tid}.md"
    body = (
        "## Problem Analysis\n\n"
        "### 問題根因\n\n舊的根因\n\n"
        + DEDUP_RECORD
        + "\n---\n\n"
        "## Solution\n"
    )
    _write_ticket(path, tid, body)

    assert _replace(tid, "Problem Analysis", "### 問題根因\n\n新的根因") == 0

    text = path.read_text(encoding="utf-8")
    assert DEDUP_RECORD.rstrip() in text
    assert "新的根因" in text
    assert "舊的根因" not in text
    out = capsys.readouterr().out
    # 摘要只列人寫 H3，不把查重紀錄列為將被取代
    assert "### 問題根因" in out
    assert "將被取代的子節：\n### 問題根因\n" in out
    assert "### 查重紀錄\n" not in out.split("將被取代的子節：")[1]


def test_no_generated_subsection_replaces_whole_section_e1(tmp_ticket_dir, patch_paths, capsys):
    tid = "0.0.0-W0-PRES3"
    path = tmp_ticket_dir / f"{tid}.md"
    body = (
        "## Context Bundle\n\n"
        "舊的人寫補充說明\n\n"
        "---\n\n"
        "## NeedsContext\n"
    )
    _write_ticket(path, tid, body)

    assert _replace(tid, "Context Bundle", "新的人寫補充說明") == 0

    text = path.read_text(encoding="utf-8")
    assert "新的人寫補充說明" in text
    assert "舊的人寫補充說明" not in text
    assert "auto-extracted" not in text
    assert "保留自動產生的子節" not in capsys.readouterr().out
