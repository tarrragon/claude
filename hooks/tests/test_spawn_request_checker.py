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
