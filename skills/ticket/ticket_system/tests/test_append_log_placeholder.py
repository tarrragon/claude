"""W3-035 — append-log 寫入 Schema 章節時應替換 placeholder 文字。

問題（4/9 W3 ANA saffron 都遇到）：
section 含 `<!-- To be filled by executing agent -->` 或 `（待填寫：...）`
這類 placeholder 時，append-log 直接 `section_text + new_entry` 導致
placeholder 殘留，body-schema-checker 後續 false positive 阻擋 complete。

修復策略：
- placeholder-only section（含 Schema 註解 + 待填寫文字）→ 用 new_entry 替換 placeholder
- 既有實質內容 → 正常 append
- 保留 Schema HTML 註解（`<!-- Schema[...]: ... -->`），這是 type-aware schema 標記

覆蓋 cases：
1. To be filled placeholder → 替換
2. 中文待填寫 placeholder → 替換
3. Schema 註解 + placeholder → Schema 保留、placeholder 替換
4. 既有實質內容 → 正常 append
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
    """寫入測試 ticket（含指定 body sections）。"""
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


def _call_append_log(ticket_id: str, section: str, content: str) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(ticket_id=ticket_id, section=section, content=content)
    return execute_append_log(ns, "0.0.0")


# ============================================================
# Tests
# ============================================================


class TestAppendLogPlaceholderReplace:
    """W3-035: append-log 寫入 placeholder-only section 應替換 placeholder。"""

    def test_replaces_to_be_filled_html_placeholder(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 1: section 僅含 `<!-- To be filled by executing agent -->` placeholder。"""
        tid = "0.0.0-W0-TEST1"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "## Solution\n"
            "<!-- Schema[IMP/Solution]: 選填 -->\n\n"
            "<!-- To be filled by executing agent -->\n\n"
            "---\n\n"
            "## Test Results\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Solution", "實際實作內容 X")
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        # placeholder 應被移除
        assert "To be filled by executing agent" not in new_body
        # 新內容存在
        assert "實際實作內容 X" in new_body
        # Schema 註解保留
        assert "Schema[IMP/Solution]" in new_body

    def test_replaces_chinese_pending_placeholder(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 2: section 含 `（待填寫：...）` 中文 placeholder。"""
        tid = "0.0.0-W0-TEST2"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "## Problem Analysis\n"
            "<!-- Schema[IMP/Problem Analysis]: 選填 -->\n\n"
            "### 問題根因\n\n"
            "（待填寫：問題發生的直接原因是什麼？）\n\n"
            "### 影響範圍\n\n"
            "（待填寫：哪些檔案受影響？）\n\n"
            "---\n\n"
            "## Solution\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Problem Analysis", "根因：X 模組 race")
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        # 中文待填寫 placeholder 應被替換
        assert "（待填寫：" not in new_body
        # 新內容存在
        assert "根因：X 模組 race" in new_body
        # Schema 註解保留
        assert "Schema[IMP/Problem Analysis]" in new_body

    def test_preserves_schema_comment_when_replacing(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 3: Schema HTML 註解必須保留（type-aware schema 標記）。"""
        tid = "0.0.0-W0-TEST3"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "## Test Results\n"
            "<!-- Schema[IMP/Test Results]: 必填（至少記錄執行指令與通過數）"
            "（.claude/pm-rules/ticket-body-schema.md） -->\n\n"
            "<!-- To be filled by executing agent -->\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Test Results", "npm test 全通過 (123/123)")
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        # Schema 註解保留完整
        assert (
            "<!-- Schema[IMP/Test Results]: 必填"
            in new_body
        )
        # placeholder 移除
        assert "To be filled by executing agent" not in new_body
        # 新內容存在
        assert "npm test 全通過 (123/123)" in new_body

    def test_normal_append_when_substantial_content_exists(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 4: section 已有實質內容 → 正常 append（不替換）。"""
        tid = "0.0.0-W0-TEST4"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "## Solution\n"
            "<!-- Schema[IMP/Solution]: 選填 -->\n\n"
            "### 既有實作摘要\n\n"
            "已完成 A、B、C 三個子任務。\n\n"
            "---\n\n"
            "## Test Results\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Solution", "追加：D 子任務也已完成")
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        # 既有內容保留
        assert "已完成 A、B、C 三個子任務" in new_body
        # 新內容也存在（append 而非替換）
        assert "追加：D 子任務也已完成" in new_body
