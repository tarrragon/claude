"""append-log（非 --replace）把補寫內容插在 CLI 寫入的 H3 子節之前。

背景：dispatch 在 Problem Analysis 尾端寫入〈派發日誌〉〈Commit 規範〉，create 寫入
〈查重紀錄〉。補寫內容沒有自己的標題時，原本附加在章節尾端，落進最後一個子節：
分析先行檢查點剝除整個子節後判為未填，持續 deny；dispatch 冪等覆寫〈Commit 規範〉時
補寫也會被刪除。

情境（同一批寫入，含與不含 CLI 子節對照）：
1. dispatch 形態：補寫落在〈派發日誌〉之前，兩個子節原文不變
2. create 形態（查重紀錄）：補寫落在〈查重紀錄〉之前
3. 不含 CLI 子節：附加在尾端，與修改前相同（E1 對照）
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib import ticket_loader
from ticket_system.lib.managed_subsections import insert_before_generated
from ticket_system.lib.parser import parse_frontmatter

DISPATCH_LOG = "### 派發日誌\n\n- 2026-11-17 15:30 派發 thyme-python-developer\n"
COMMIT_RULE = "### Commit 規範\n\n- 提交訊息以票號開頭\n"
DEDUP_RECORD = "### 查重紀錄\n\n`--dedup-checked none`，查重關鍵字（逐字）：\n\n- `關鍵字`\n"
TEMPLATE_H3 = "### 問題根因\n\n<!-- 選填：問題如何發現？ -->\n\n"
ANALYSIS = "補寫：寫入點在 foo.py 的 bar()。"


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


def _write_ticket(path: Path, tid: str, pa: str) -> None:
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
    body = "## Problem Analysis\n\n" + pa + "\n---\n\n## Solution\n\n<!-- 選填 -->\n"
    path.write_text(fm + body, encoding="utf-8")


def _append(tid: str, content: str) -> int:
    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(ticket_id=tid, section="Problem Analysis", content=content, replace=False)
    return execute_append_log(ns, "0.0.0")


def _problem_analysis(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index("## Problem Analysis")
    return text[start:text.index("## Solution")]


def test_dispatch_shape_inserts_before_dispatch_log(tmp_ticket_dir, patch_paths):
    tid = "0.0.0-W0-INS1"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, TEMPLATE_H3 + DISPATCH_LOG + "\n" + COMMIT_RULE)

    assert _append(tid, ANALYSIS) == 0

    pa = _problem_analysis(path)
    assert pa.index(ANALYSIS) < pa.index("### 派發日誌") < pa.index("### Commit 規範")
    assert DISPATCH_LOG.rstrip() in pa and COMMIT_RULE.rstrip() in pa
    # 補寫不落在 Commit 規範子節內（下次 dispatch 冪等覆寫該子節時不會被刪）
    assert ANALYSIS not in pa[pa.index("### Commit 規範"):]


def test_dedup_shape_inserts_before_dedup_record(tmp_ticket_dir, patch_paths):
    tid = "0.0.0-W0-INS2"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, TEMPLATE_H3 + DEDUP_RECORD)

    assert _append(tid, ANALYSIS) == 0

    pa = _problem_analysis(path)
    assert pa.index(ANALYSIS) < pa.index("### 查重紀錄")
    assert DEDUP_RECORD.rstrip() in pa


def test_e1_without_generated_subsection_appends_at_end(tmp_ticket_dir, patch_paths):
    """E1 對照：同一寫入，章節無 CLI 子節時附加在尾端（修改前行為）。"""
    tid = "0.0.0-W0-INS3"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, "### 問題根因\n\n已寫的根因。\n")

    assert _append(tid, ANALYSIS) == 0

    pa = _problem_analysis(path).rstrip().rstrip("-").rstrip()
    assert pa.index("已寫的根因。") < pa.index(ANALYSIS)
    assert pa.endswith(ANALYSIS)


def test_other_section_with_same_heading_appends_at_end(tmp_ticket_dir, patch_paths):
    """對照：只有 Problem Analysis 改落點；Solution 裡人寫的同名標題不影響附加在尾端。"""
    tid = "0.0.0-W0-INS5"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, "已寫的分析。\n")
    text = path.read_text(encoding="utf-8").replace(
        "## Solution\n\n<!-- 選填 -->\n", "## Solution\n\n" + COMMIT_RULE + "\n人寫的討論。\n")
    path.write_text(text, encoding="utf-8")

    from ticket_system.commands.track_acceptance import execute_append_log

    ns = argparse.Namespace(ticket_id=tid, section="Solution", content=ANALYSIS, replace=False)
    assert execute_append_log(ns, "0.0.0") == 0

    sol = path.read_text(encoding="utf-8").split("## Solution", 1)[1]
    assert sol.index("### Commit 規範") < sol.index("人寫的討論。") < sol.index(ANALYSIS)


def test_second_append_keeps_chronological_order(tmp_ticket_dir, patch_paths):
    tid = "0.0.0-W0-INS4"
    path = tmp_ticket_dir / f"{tid}.md"
    _write_ticket(path, tid, TEMPLATE_H3 + DISPATCH_LOG + "\n" + COMMIT_RULE)

    assert _append(tid, "第一次補寫") == 0
    assert _append(tid, "第二次補寫") == 0

    pa = _problem_analysis(path)
    assert pa.index("第一次補寫") < pa.index("第二次補寫") < pa.index("### 派發日誌")


def test_insert_before_generated_picks_earliest_subsection():
    section = "## Problem Analysis\n\n人寫\n\n" + DEDUP_RECORD + "\n" + DISPATCH_LOG
    out = insert_before_generated(section, "\n新內容")
    assert out.index("人寫") < out.index("新內容") < out.index("### 查重紀錄") < out.index("### 派發日誌")
