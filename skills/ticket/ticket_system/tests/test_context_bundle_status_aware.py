"""Status-aware Context Bundle 抽取測試（0.2.1-W3-646）。

驗證抽取器依來源票 status 分流：
    - render 端輸出 per-source status 標籤（completed / closed 有標籤，
      pending / in_progress 無標籤，維持既有行為）。
    - acceptance 過濾改 status-aware（completed 保留已勾選項作為結論摘要，
      其餘保留未勾選項，維持既有行為）。

對應票：0.2.1-W3-634 六視角審查後反轉版主方案；分流依據見 ARCH-BAL-018
（快照欄位正確性定義在來源進入終態後反轉，待執行端同步現值、終態端保留
原值並標示）。closed 來源之 Solution 100% 空白樣板（實測 23 張無例外，
見票面 Problem Analysis），標籤設計須避免指向該空章節。
"""

from __future__ import annotations

import pytest

from ticket_system.lib import context_bundle_extractor as cbe

TARGET_ID = "0.1.0-W1-100"
SOURCE_ID = "0.1.0-W1-001"


def _make_source(status: str, **overrides) -> dict:
    base = {
        "id": SOURCE_ID,
        "status": status,
        "what": "source what content",
        "why": "source why content",
        "acceptance": ["- [x] confirmed-alpha", "- [ ] pending-beta"],
    }
    base.update(overrides)
    return base


def _make_target(source_id: str = SOURCE_ID) -> dict:
    return {"id": TARGET_ID, "source_ticket": source_id}


@pytest.fixture
def patch_load_ticket(monkeypatch):
    """回傳 setter：呼叫後把指定 id 的 dict 註冊到假 load_ticket（不觸真實檔案 I/O）。"""
    registry: dict = {}

    def _fake_load_ticket(version, ticket_id):
        return registry.get(ticket_id)

    monkeypatch.setattr(cbe, "load_ticket", _fake_load_ticket)

    def _register(ticket_id: str, ticket: dict) -> None:
        registry[ticket_id] = ticket

    return _register


# ============================================================
# acceptance #1：四種來源 status 各有測試涵蓋 render 輸出
# ============================================================


@pytest.mark.parametrize(
    "status,expect_suffix",
    [
        ("pending", ""),
        ("in_progress", ""),
        ("completed", "（來源已完成，結論見 Solution）"),
        ("closed", "（來源已關閉，無結論）"),
    ],
)
def test_render_label_by_source_status(patch_load_ticket, status, expect_suffix):
    patch_load_ticket(SOURCE_ID, _make_source(status))
    target = _make_target()

    result = cbe.extract_context_bundle(target)
    markdown = cbe.render_context_bundle_markdown(result)

    why_line = next(line for line in markdown.splitlines() if f"{SOURCE_ID} why:" in line)
    if expect_suffix:
        assert why_line.endswith(expect_suffix)
    else:
        assert why_line.endswith("source why content")


# ============================================================
# acceptance #1：四種來源 status 各有測試涵蓋 acceptance 保留行為
# ============================================================


@pytest.mark.parametrize(
    "status,expected_kept,expected_dropped",
    [
        ("pending", "pending-beta", "confirmed-alpha"),
        ("in_progress", "pending-beta", "confirmed-alpha"),
        ("completed", "confirmed-alpha", "pending-beta"),
        ("closed", "pending-beta", "confirmed-alpha"),
    ],
)
def test_acceptance_filter_by_source_status(
    patch_load_ticket, status, expected_kept, expected_dropped
):
    patch_load_ticket(SOURCE_ID, _make_source(status))
    target = _make_target()

    result = cbe.extract_context_bundle(target)
    markdown = cbe.render_context_bundle_markdown(result)

    assert expected_kept in markdown
    assert expected_dropped not in markdown


# ============================================================
# acceptance #2：closed 來源的標籤不導向空 Solution 章節
# ============================================================


def test_closed_label_does_not_point_to_solution(patch_load_ticket):
    patch_load_ticket(SOURCE_ID, _make_source("closed"))
    target = _make_target()

    result = cbe.extract_context_bundle(target)
    markdown = cbe.render_context_bundle_markdown(result)

    assert "Solution" not in markdown
    assert "已關閉" in markdown


def test_completed_label_points_to_solution(patch_load_ticket):
    patch_load_ticket(SOURCE_ID, _make_source("completed"))
    target = _make_target()

    result = cbe.extract_context_bundle(target)
    markdown = cbe.render_context_bundle_markdown(result)

    assert "Solution" in markdown


# ============================================================
# acceptance #3：多來源情境下標籤為 per-source 標註而非單一靜態字串
# ============================================================


def test_multi_source_per_source_labels(patch_load_ticket):
    completed_id = "0.1.0-W1-001"
    closed_id = "0.1.0-W1-002"
    patch_load_ticket(completed_id, _make_source("completed", id=completed_id))
    patch_load_ticket(closed_id, _make_source("closed", id=closed_id))
    target = {
        "id": TARGET_ID,
        "source_ticket": completed_id,
        "blockedBy": [closed_id],
    }

    result = cbe.extract_context_bundle(target)
    markdown = cbe.render_context_bundle_markdown(result)

    completed_line = next(
        line for line in markdown.splitlines() if f"{completed_id} why:" in line
    )
    closed_line = next(
        line for line in markdown.splitlines() if f"{closed_id} why:" in line
    )

    assert completed_line.endswith("（來源已完成，結論見 Solution）")
    assert closed_line.endswith("（來源已關閉，無結論）")
    assert completed_line != closed_line


# ============================================================
# acceptance #4：status 標籤渲染不觸發區塊邊界誤判
# ============================================================


def test_status_label_lines_classified_as_auto_content(patch_load_ticket):
    patch_load_ticket(SOURCE_ID, _make_source("completed"))
    target = _make_target()

    result = cbe.extract_context_bundle(target)
    markdown = cbe.render_context_bundle_markdown(result)

    for line in markdown.splitlines():
        if line.startswith("- "):
            assert cbe._is_auto_content_line(line) is True


def test_status_label_merge_round_trip_no_residual(patch_load_ticket):
    """merge_auto_extracted_block 對含 status 標籤的區塊仍維持冪等（無殘留）。"""
    patch_load_ticket(SOURCE_ID, _make_source("completed"))
    target = _make_target()

    result = cbe.extract_context_bundle(target)
    markdown = cbe.render_context_bundle_markdown(result)

    merged_once, _notes_once = cbe.merge_auto_extracted_block("", markdown)
    merged_twice, notes_twice = cbe.merge_auto_extracted_block(merged_once, markdown)

    assert merged_once == merged_twice
    assert "no_change_idempotent" in notes_twice
