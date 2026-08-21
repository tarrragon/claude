"""append-log --replace 旗標 —— 整段覆寫指定章節，header 與章節位置不變。

背景：ticket md 的 Read/Edit 被 ticket-file-access-guard-hook 阻擋，章節內容
寫錯（如 shell 逃逸字元污染、內容需修訂）時 append-log 只能累加，無合法修正
路徑。覆寫邏輯（_replace_or_append_section_content 之外的專用分支）已存在，
供 set-exit-status / set-completion-info 使用，缺的只是 append-log 自身的
argparse 旗標註冊。

覆蓋 cases：
1. --replace 對含實質內容的章節整段覆寫（不同於預設 append 行為）
2. 覆寫後 header 與章節在 body 中的位置不變（僅內容被取代）
3. 未帶 --replace 時維持既有 append 語意（回歸防護）
4. --replace 覆寫前於 stdout 印出將被取代的內容摘要（防呆）
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib import parser, ticket_loader
from ticket_system.lib.parser import parse_frontmatter


# ============================================================
# Fixtures
# ============================================================


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
        try:
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except Exception:
            return None
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


def _write_ticket_with_body(path: Path, tid: str, body_sections: str) -> None:
    fm = (
        "---\n"
        f"id: {tid}\n"
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
    path.write_text(fm + body_sections, encoding="utf-8")


def _call_append_log(
    ticket_id: str, section: str, content: str, replace: bool = False
) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(
        ticket_id=ticket_id, section=section, content=content, replace=replace
    )
    return execute_append_log(ns, "0.0.0")


# ============================================================
# Tests
# ============================================================


class TestAppendLogReplaceFlag:
    def test_replace_overwrites_substantial_content(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 1: --replace 對含實質內容的章節整段覆寫，不同於預設 append。"""
        tid = "0.0.0-W0-REPL1"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "## Solution\n"
            "<!-- Schema[IMP/Solution]: 選填 -->\n\n"
            "污染前內容：`rm -rf /`\n\n"
            "---\n\n"
            "## Test Results\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Solution", "已修訂內容", replace=True)
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        # 舊內容整段被取代，不殘留
        assert "污染前內容" not in new_body
        assert "rm -rf /" not in new_body
        # 新內容存在
        assert "已修訂內容" in new_body

    def test_replace_preserves_header_and_position(self, tmp_ticket_dir, patch_paths):
        """Case 2: 覆寫後 section header 與其在 body 中的位置不變。"""
        tid = "0.0.0-W0-REPL2"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "## Problem Analysis\n"
            "既有分析內容 A\n\n"
            "---\n\n"
            "## Solution\n"
            "既有方案內容 B\n\n"
            "---\n\n"
            "## Test Results\n"
            "既有測試內容 C\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Solution", "覆寫後的方案內容", replace=True)
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        lines = new_body.splitlines()

        # header 仍存在且順序不變（Problem Analysis 在 Solution 之前，
        # Solution 在 Test Results 之前）
        idx_pa = next(i for i, l in enumerate(lines) if l == "## Problem Analysis")
        idx_sol = next(i for i, l in enumerate(lines) if l == "## Solution")
        idx_tr = next(i for i, l in enumerate(lines) if l == "## Test Results")
        assert idx_pa < idx_sol < idx_tr

        # 未被覆寫的章節內容維持原樣
        assert "既有分析內容 A" in new_body
        assert "既有測試內容 C" in new_body

        # 被覆寫章節：舊內容消失、新內容存在
        assert "既有方案內容 B" not in new_body
        assert "覆寫後的方案內容" in new_body

    def test_default_append_semantics_unchanged_without_replace(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 3（回歸防護）：未帶 --replace 時維持既有 append 語意。"""
        tid = "0.0.0-W0-REPL3"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "## Solution\n"
            "<!-- Schema[IMP/Solution]: 選填 -->\n\n"
            "既有內容 X\n\n"
            "---\n\n"
            "## Test Results\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Solution", "追加內容 Y", replace=False)
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        # append 語意：舊內容保留、新內容追加
        assert "既有內容 X" in new_body
        assert "追加內容 Y" in new_body

    def test_replace_prints_old_content_summary_before_overwrite(
        self, tmp_ticket_dir, patch_paths, capsys
    ):
        """Case 4（防呆）：--replace 覆寫前於 stdout 印出將被取代的內容摘要。"""
        tid = "0.0.0-W0-REPL4"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "## Solution\n"
            "<!-- Schema[IMP/Solution]: 選填 -->\n\n"
            "即將被取代的舊內容標記\n\n"
            "---\n\n"
            "## Test Results\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Solution", "新內容", replace=True)
        assert rc == 0

        captured = capsys.readouterr()
        assert "即將被取代的舊內容標記" in captured.out
