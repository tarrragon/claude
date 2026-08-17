"""
Spawn Request Checker Tests

對應 Ticket 1.5.0-W5-024：
驗證 Spawn Requests 章節的處理狀態檢查（pending -> WARNING，processed/dismissed -> 通過）。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.spawn_request_checker import check_spawn_requests  # noqa: E402


@pytest.fixture
def logger():
    log = logging.getLogger("test-spawn-request-checker")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


def _build_content(spawn_section: str) -> str:
    return (
        "# Execution Log\n\n"
        "## Problem Analysis\n内容\n\n"
        f"## Spawn Requests\n{spawn_section}\n"
        "## Completion Info\n內容\n"
    )


def test_no_spawn_requests_section(logger):
    content = "# Execution Log\n\n## Problem Analysis\n內容\n"
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is False
    assert msg is None


def test_empty_spawn_requests_section(logger):
    content = _build_content("\n")
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is False
    assert msg is None


def test_pending_entry_warns(logger):
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 補測試\n"
        "  - why: 覆蓋率不足\n"
        "  - suggested_type: IMP\n"
        "  - suggested_priority: P2\n"
        "  - related_files: foo.py\n"
        "  - context: 上下文\n"
        "  - status: pending\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is True
    assert msg is not None
    assert "SR-1" in msg
    assert "WARNING" in msg


def test_processed_entry_passes(logger):
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 補測試\n"
        "  - why: 覆蓋率不足\n"
        "  - suggested_type: IMP\n"
        "  - suggested_priority: P2\n"
        "  - related_files: foo.py\n"
        "  - context: 上下文\n"
        "  - status: processed\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is False
    assert msg is None


def test_dismissed_entry_passes(logger):
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 補測試\n"
        "  - status: dismissed\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is False
    assert msg is None


def test_mixed_entries_only_pending_warns(logger):
    entries = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 已處理\n"
        "  - status: processed\n"
        "\n- **SR-2** (2026-07-05 12:05)\n"
        "  - what: 未處理\n"
        "  - status: pending\n"
        "\n- **SR-3** (2026-07-05 12:10)\n"
        "  - what: 已捨棄\n"
        "  - status: dismissed\n"
    )
    content = _build_content(entries)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is True
    assert "SR-2" in msg
    assert "SR-1" not in msg
    assert "SR-3" not in msg


def test_missing_status_field_treated_as_pending(logger):
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 缺 status 欄位\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is True
    assert "SR-1" in msg


def test_invalid_status_value_treated_as_pending(logger):
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 非法狀態\n"
        "  - status: unknown\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is True
    assert "SR-1" in msg


# === AC#1: unparseable status line shows actual content ===

def test_unparseable_status_shows_actual_line(logger):
    """status 行附帶日期/票號等額外內容時，訊息應顯示實際行內容與期望格式。"""
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 已回填但格式不合\n"
        "  - status: processed (2026-07-10) -> 0.38.0-W5-009\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is True
    assert "SR-1" in msg
    assert "processed (2026-07-10)" in msg
    assert "pending|processed|dismissed" in msg


# === AC#2: missing field vs pending are distinguishable ===

def test_missing_field_message_distinguishable_from_pending(logger):
    """缺少 status 欄位的訊息與 status: pending 的訊息應可區分。"""
    pending_entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 確實 pending\n"
        "  - status: pending\n"
    )
    missing_entry = (
        "\n- **SR-2** (2026-07-05 12:05)\n"
        "  - what: 缺 status 欄位\n"
    )
    content = _build_content(pending_entry + missing_entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is True
    assert "SR-1" in msg
    assert "SR-2" in msg
    # pending and missing should appear in different sections
    assert "status: pending" in msg
    assert "欄位缺失" in msg


# === AC#3: fail-closed unchanged ===

def test_unparseable_still_treated_as_unprocessed(logger):
    """無法解析的 status 行仍 fail-closed 視為未處理（should_warn=True）。"""
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 格式不合\n"
        "  - status: processed (2026-07-10) -> 0.38.0-W5-009\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is True
    assert "fail-closed" in msg


# === 0.2.1-W3-324: 校準 CLI 實際寫入格式（附全形括號附註）不誤判 ===
# rule8-exempt: testdata:回歸樣本取自真實已完成 ticket 0.2.1-W3-319 的
# Spawn Requests 章節內容，驗證 CLI 實際產出格式可被正確解析


def test_processed_with_full_width_annotation_passes(logger):
    """`resolve-spawn-request` CLI 實際寫入格式（processed 緊接全形括號
    附註 `已建 <ticket-id>`）應被正確解析為已處理，不誤報未處理。"""
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 補測試\n"
        "  - status: processed（已建 0.2.1-W3-320）\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is False
    assert msg is None


def test_dismissed_with_reason_annotation_passes(logger):
    """dismissed 附理由的全形括號附註格式同樣應正確解析。"""
    entry = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 補測試\n"
        "  - status: dismissed（評估後不需要，已有既有機制涵蓋）\n"
    )
    content = _build_content(entry)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is False
    assert msg is None


def test_w3_319_three_sr_regression_sample_all_pass(logger):
    """0.2.1-W3-319 完成時實際留下的三筆 Spawn Request（皆為
    `resolve-spawn-request` CLI 寫入的 `processed（已建 <id>）` 格式），
    驗證真實回歸樣本可正確解析，不觸發 gate 誤報。"""
    entries = (
        "\n- **SR-1** (2026-08-06 11:24)\n"
        "  - what: 移除 settings.json 中的 hook 重複註冊與合併版並存\n"
        "  - status: processed（已建 0.2.1-W3-320）\n"
        "\n- **SR-2** (2026-08-06 11:24)\n"
        "  - what: 補齊 agent-ticket-validation-hook 的唯讀代理人豁免清單\n"
        "  - status: processed（已建 0.2.1-W3-321）\n"
        "\n- **SR-3** (2026-08-06 11:24)\n"
        "  - what: 決策 hook auto-commit 是否應繞過下游 repo 的 pre-commit hook\n"
        "  - status: processed（已建 0.2.1-W3-322）\n"
    )
    content = _build_content(entries)
    should_warn, msg = check_spawn_requests(content, {"id": "0.2.1-W3-319"}, logger)
    assert should_warn is False
    assert msg is None


# === AC#4: three causes coverage ===

def test_three_causes_all_present(logger):
    """三種成因同時出現時，訊息應分別列出。"""
    entries = (
        "\n- **SR-1** (2026-07-05 12:00)\n"
        "  - what: 確實 pending\n"
        "  - status: pending\n"
        "\n- **SR-2** (2026-07-05 12:05)\n"
        "  - what: 格式不合\n"
        "  - status: processed (2026-07-10)\n"
        "\n- **SR-3** (2026-07-05 12:10)\n"
        "  - what: 缺 status\n"
    )
    content = _build_content(entries)
    should_warn, msg = check_spawn_requests(content, {"id": "T-1"}, logger)
    assert should_warn is True
    assert "SR-1" in msg
    assert "SR-2" in msg
    assert "SR-3" in msg
    # Each cause type should be identifiable
    assert "pending" in msg.lower()
    assert "無法解析" in msg
    assert "欄位缺失" in msg
