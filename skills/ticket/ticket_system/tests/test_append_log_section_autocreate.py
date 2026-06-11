"""W1-025 — append-log 對缺失的合法 Schema 章節自動補建 + 前置檢核聚合。

問題（PM 派發前摩擦實證）：
IMP create 模板未預生成 Context Bundle 等 Schema 章節，PM 派發前
`append-log --section "Context Bundle"` 回報 SECTION_NOT_FOUND，被迫
繞道手動 Edit ticket md 插入章節。

修復策略（方案 B：CLI 自動補建，取代模板預生成）：
- 白名單合法且屬 SCHEMA_H2_SECTIONS 的缺失章節 → 於 canonical 順序位置
  自動建立（含首筆內容一次寫入）
- 非 Schema 章節（如 Execution Log）缺失 → 維持既有 SECTION_NOT_FOUND 錯誤
- 前置檢核（status / section 白名單 / 章節存在性）聚合為一次列全失敗原因，
  不再分三輪 fail-fast（W1-024 adversarial 複審發現）
- exit code 契約不變：status 失敗 = 2，其餘 = 1

覆蓋 cases：
1. 缺失 Context Bundle 自動補建於 canonical 位置（Test Results 後、NeedsContext 前）
2. 無更晚章節時補建於 body 末尾
3. 補建後再次 append 走正常 append 路徑（無重複 H2）
4. 非 Schema 章節缺失維持 SECTION_NOT_FOUND（不自動補建）
5. 前置檢核聚合：status + section 白名單失敗一次列全，exit 2
6. 僅 section 白名單失敗 → exit 1
7. status 失敗時不執行自動補建（檔案不變）
8. VALID_SECTIONS 白名單與 SCHEMA_H2_SECTIONS 對齊（SSOT guard）
9. 自動補建章節的內容仍套用 H2 → H3 降級（W1-068 規範化不被繞過）
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.lib import ticket_loader
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


def _write_ticket_with_body(
    path: Path, tid: str, body_sections: str, status: str = "in_progress"
) -> None:
    """寫入測試 ticket（含指定 body sections 與 status）。"""
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        "type: IMP\n"
        f"status: {status}\n"
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


# IMP 模板典型 body（無 Context Bundle 章節，模擬真實派發前摩擦場景）
IMP_BODY_WITHOUT_CONTEXT_BUNDLE = (
    "# Execution Log\n\n"
    "## Task Summary\n\n"
    "測試任務\n\n"
    "---\n\n"
    "## Problem Analysis\n\n"
    "（待填寫：問題發生的直接原因是什麼？）\n\n"
    "---\n\n"
    "## Solution\n\n"
    "<!-- To be filled by executing agent -->\n\n"
    "---\n\n"
    "## Test Results\n\n"
    "<!-- To be filled by executing agent -->\n\n"
    "---\n\n"
    "## NeedsContext\n\n"
    "---\n\n"
    "## Exit Status\n\n"
    "---\n\n"
    "## Completion Info\n\n"
    "**Review Status**: pending\n"
)


# ============================================================
# Tests: Schema 章節自動補建
# ============================================================


class TestAppendLogSectionAutocreate:
    """W1-025: 缺失的合法 Schema 章節於 canonical 位置自動補建。"""

    def test_autocreate_context_bundle_at_canonical_position(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 1: 缺失 Context Bundle → 補建於 Test Results 後、NeedsContext 前。"""
        tid = "0.0.0-W0-AC1"
        path = tmp_ticket_dir / f"{tid}.md"
        _write_ticket_with_body(path, tid, IMP_BODY_WITHOUT_CONTEXT_BUNDLE)

        rc = _call_append_log(tid, "Context Bundle", "### 規格依據\n\n- spec.md 第 3 節")
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        assert "## Context Bundle" in new_body
        assert "- spec.md 第 3 節" in new_body
        # canonical 順序：Test Results < Context Bundle < NeedsContext
        pos_tr = new_body.index("## Test Results")
        pos_cb = new_body.index("## Context Bundle")
        pos_nc = new_body.index("## NeedsContext")
        assert pos_tr < pos_cb < pos_nc

    def test_autocreate_appends_at_end_when_no_later_section(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 2: body 無 canonical 順序更晚的章節 → 補建於末尾。"""
        tid = "0.0.0-W0-AC2"
        path = tmp_ticket_dir / f"{tid}.md"
        body = (
            "# Execution Log\n\n"
            "## Task Summary\n\n"
            "測試任務\n\n"
            "---\n\n"
            "## Solution\n\n"
            "既有結論\n"
        )
        _write_ticket_with_body(path, tid, body)

        rc = _call_append_log(tid, "Completion Info", "**Completion Time**: 2026-06-11")
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        pos_sol = new_body.index("## Solution")
        pos_ci = new_body.index("## Completion Info")
        assert pos_sol < pos_ci
        assert "**Completion Time**: 2026-06-11" in new_body
        # 既有內容不受影響
        assert "既有結論" in new_body

    def test_second_append_uses_normal_path_no_duplicate_h2(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 3: 補建後再次 append → 正常 append，無重複 ## Context Bundle。"""
        tid = "0.0.0-W0-AC3"
        path = tmp_ticket_dir / f"{tid}.md"
        _write_ticket_with_body(path, tid, IMP_BODY_WITHOUT_CONTEXT_BUNDLE)

        assert _call_append_log(tid, "Context Bundle", "首筆內容") == 0
        assert _call_append_log(tid, "Context Bundle", "次筆內容") == 0

        new_body = path.read_text(encoding="utf-8")
        assert new_body.count("## Context Bundle") == 1
        assert "首筆內容" in new_body
        assert "次筆內容" in new_body

    def test_non_schema_section_missing_still_errors(
        self, tmp_ticket_dir, patch_paths, capsys
    ):
        """Case 4: 非 Schema 章節（Execution Log H2）缺失 → 維持 SECTION_NOT_FOUND。"""
        tid = "0.0.0-W0-AC4"
        path = tmp_ticket_dir / f"{tid}.md"
        _write_ticket_with_body(path, tid, IMP_BODY_WITHOUT_CONTEXT_BUNDLE)

        rc = _call_append_log(tid, "Execution Log", "一筆日誌")
        assert rc == 1

        captured = capsys.readouterr()
        assert "無 'Execution Log' 區段" in captured.out
        # 未自動補建
        assert "## Execution Log" not in path.read_text(encoding="utf-8")

    def test_autocreated_section_content_h2_downgraded(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 9: 補建路徑仍套用 H2 → H3 降級（W1-068 規範化不被繞過）。"""
        tid = "0.0.0-W0-AC9"
        path = tmp_ticket_dir / f"{tid}.md"
        _write_ticket_with_body(path, tid, IMP_BODY_WITHOUT_CONTEXT_BUNDLE)

        rc = _call_append_log(tid, "Context Bundle", "## 規格依據\n\n內容")
        assert rc == 0

        new_body = path.read_text(encoding="utf-8")
        assert "### 規格依據" in new_body
        assert "\n## 規格依據" not in new_body


# ============================================================
# Tests: 前置檢核聚合（一次列全失敗原因）
# ============================================================


class TestAppendLogAggregatedPreconditions:
    """W1-025: status / section 白名單 / 章節存在性一次列全，不分三輪 fail-fast。"""

    def test_status_and_section_failures_reported_in_one_call(
        self, tmp_ticket_dir, patch_paths, capsys
    ):
        """Case 5: pending status + 無效 section → 單次呼叫列全兩項失敗，exit 2。"""
        tid = "0.0.0-W0-AG1"
        path = tmp_ticket_dir / f"{tid}.md"
        _write_ticket_with_body(
            path, tid, IMP_BODY_WITHOUT_CONTEXT_BUNDLE, status="pending"
        )

        rc = _call_append_log(tid, "Bogus Section", "內容")
        assert rc == 2  # status 失敗維持既有 exit 2 契約

        captured = capsys.readouterr()
        # status 失敗 → stderr（既有通道）
        assert "status=pending" in captured.err
        # section 白名單失敗 → stdout（既有通道），同一次呼叫即列出
        assert "無效的 section: Bogus Section" in captured.out

    def test_section_only_failure_exits_1(
        self, tmp_ticket_dir, patch_paths, capsys
    ):
        """Case 6: 僅 section 白名單失敗（status 正常）→ exit 1。"""
        tid = "0.0.0-W0-AG2"
        path = tmp_ticket_dir / f"{tid}.md"
        _write_ticket_with_body(path, tid, IMP_BODY_WITHOUT_CONTEXT_BUNDLE)

        rc = _call_append_log(tid, "Bogus Section", "內容")
        assert rc == 1

        captured = capsys.readouterr()
        assert "無效的 section: Bogus Section" in captured.out
        assert captured.err == ""

    def test_status_failure_blocks_autocreate(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 7: pending status + 缺失 Schema 章節 → 不補建（檔案不變），exit 2。

        W1-058 後 Context Bundle / Problem Analysis 屬派發前章節，pending 可直寫；
        本 case 改用「重現實驗結果」（非派發前的缺失 Schema 章節）驗證原意：
        status 失敗時自動補建不得執行。
        """
        tid = "0.0.0-W0-AG3"
        path = tmp_ticket_dir / f"{tid}.md"
        _write_ticket_with_body(
            path, tid, IMP_BODY_WITHOUT_CONTEXT_BUNDLE, status="pending"
        )
        before = path.read_text(encoding="utf-8")

        rc = _call_append_log(tid, "重現實驗結果", "內容")
        assert rc == 2
        assert path.read_text(encoding="utf-8") == before

    def test_pending_pre_dispatch_section_autocreate_proceeds(
        self, tmp_ticket_dir, patch_paths
    ):
        """Case 7b（W1-058）: pending + 派發前章節（Context Bundle）→ 自動補建照常執行。"""
        tid = "0.0.0-W0-AG4"
        path = tmp_ticket_dir / f"{tid}.md"
        _write_ticket_with_body(
            path, tid, IMP_BODY_WITHOUT_CONTEXT_BUNDLE, status="pending"
        )

        rc = _call_append_log(tid, "Context Bundle", "### 派發前置資訊")
        assert rc == 0
        new_body = path.read_text(encoding="utf-8")
        assert "## Context Bundle" in new_body
        assert "### 派發前置資訊" in new_body


# ============================================================
# Tests: 白名單與 Schema SSOT 對齊
# ============================================================


class TestSectionWhitelistSchemaAlignment:
    """W1-025（W1-024 A4 併入）: VALID_SECTIONS 與 SCHEMA_H2_SECTIONS 對齊 guard。"""

    def test_valid_sections_covers_all_schema_sections(self):
        """Case 8: 白名單 = 全部 Schema 章節 + Execution Log（無缺漏、無多餘）。"""
        from ticket_system.lib.command_tracking_messages import TrackAcceptanceMessages
        from ticket_system.lib.ticket_builder import SCHEMA_H2_SECTIONS

        expected = set(SCHEMA_H2_SECTIONS) | {"Execution Log"}
        assert set(TrackAcceptanceMessages.VALID_SECTIONS) == expected
