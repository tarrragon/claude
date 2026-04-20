"""
ANA Spawned Checker - spawned_tickets 狀態檢查測試（W12-004 Phase 1）

測試 check_spawned_tickets_status 的行為：spawned 任一非 terminal 時產生警告。

對應 Ticket 0.18.0-W12-004 AC：
- spawned 全 terminal (completed/closed) → 無警告
- spawned 任一 pending/in_progress/blocked → 產生警告
- shallow 一層（不 recurse spawned 的後代）
- 找不到 spawned 檔案視為非 terminal（保守警告）
"""

import sys
import logging
from pathlib import Path

import pytest

# 將 .claude/hooks 加入 sys.path，讓測試能 import acceptance_checkers
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.ana_spawned_checker import check_spawned_tickets_status


def _write_ticket(project_dir: Path, ticket_id: str, status: str) -> Path:
    """建立最小可解析的 spawned Ticket 檔案。"""
    version_part = ticket_id.split("-W")[0]
    ticket_dir = project_dir / "docs" / "work-logs" / f"v{version_part}" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
id: {ticket_id}
title: {ticket_id}
type: IMP
status: {status}
version: {version_part}
---

# Body
"""
    ticket_file = ticket_dir / f"{ticket_id}.md"
    ticket_file.write_text(content, encoding="utf-8")
    return ticket_file


@pytest.fixture
def logger():
    log = logging.getLogger("test-ana-spawned")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path


# ----------------------------------------------------------------------------
# 情境 1：spawned 全 terminal → 無警告
# ----------------------------------------------------------------------------

def test_spawned_all_completed_no_warning(project_dir, logger):
    """spawned 全 completed 時不應警告。"""
    _write_ticket(project_dir, "0.18.0-W12-100.1", status="completed")
    _write_ticket(project_dir, "0.18.0-W12-100.2", status="completed")

    warning = check_spawned_tickets_status(
        ["0.18.0-W12-100.1", "0.18.0-W12-100.2"], project_dir, logger
    )
    assert warning is None


def test_spawned_all_closed_no_warning(project_dir, logger):
    """closed 視為 terminal，不應警告。"""
    _write_ticket(project_dir, "0.18.0-W12-101.1", status="closed")
    warning = check_spawned_tickets_status(
        ["0.18.0-W12-101.1"], project_dir, logger
    )
    assert warning is None


def test_spawned_mixed_terminal_no_warning(project_dir, logger):
    """completed + closed 混合（皆 terminal），不應警告。"""
    _write_ticket(project_dir, "0.18.0-W12-102.1", status="completed")
    _write_ticket(project_dir, "0.18.0-W12-102.2", status="closed")
    warning = check_spawned_tickets_status(
        ["0.18.0-W12-102.1", "0.18.0-W12-102.2"], project_dir, logger
    )
    assert warning is None


# ----------------------------------------------------------------------------
# 情境 2：spawned 非 terminal → 警告
# ----------------------------------------------------------------------------

def test_spawned_pending_should_warn(project_dir, logger):
    """spawned pending 時應警告，訊息含 ID 和狀態。"""
    _write_ticket(project_dir, "0.18.0-W12-110.1", status="pending")
    warning = check_spawned_tickets_status(
        ["0.18.0-W12-110.1"], project_dir, logger
    )
    assert warning is not None
    assert "0.18.0-W12-110.1" in warning
    assert "pending" in warning


def test_spawned_in_progress_should_warn(project_dir, logger):
    """spawned in_progress 時應警告。"""
    _write_ticket(project_dir, "0.18.0-W12-111.1", status="in_progress")
    warning = check_spawned_tickets_status(
        ["0.18.0-W12-111.1"], project_dir, logger
    )
    assert warning is not None
    assert "0.18.0-W12-111.1" in warning
    assert "in_progress" in warning


def test_spawned_blocked_should_warn(project_dir, logger):
    """spawned blocked 時應警告。"""
    _write_ticket(project_dir, "0.18.0-W12-112.1", status="blocked")
    warning = check_spawned_tickets_status(
        ["0.18.0-W12-112.1"], project_dir, logger
    )
    assert warning is not None
    assert "0.18.0-W12-112.1" in warning
    assert "blocked" in warning


def test_spawned_mixed_only_lists_non_terminal(project_dir, logger):
    """spawned 含 completed + pending 時，警告只列出 pending（避免噪音）。"""
    _write_ticket(project_dir, "0.18.0-W12-120.1", status="completed")
    _write_ticket(project_dir, "0.18.0-W12-120.2", status="pending")
    warning = check_spawned_tickets_status(
        ["0.18.0-W12-120.1", "0.18.0-W12-120.2"], project_dir, logger
    )
    assert warning is not None
    assert "0.18.0-W12-120.2" in warning
    # completed 的 ticket 不應出現在警告列表（避免噪音）
    assert "0.18.0-W12-120.1" not in warning


# ----------------------------------------------------------------------------
# 情境 3：邊界條件
# ----------------------------------------------------------------------------

def test_spawned_empty_no_warning(project_dir, logger):
    """空清單 → 不警告（caller 應已處理「無 spawned」情境，由 check_ana_has_spawned_tickets 負責）。"""
    warning = check_spawned_tickets_status([], project_dir, logger)
    assert warning is None


def test_spawned_not_found_should_warn(project_dir, logger):
    """spawned ticket 檔案不存在 → 視為非 terminal（保守警告）。"""
    warning = check_spawned_tickets_status(
        ["0.18.0-W12-130.1"], project_dir, logger
    )
    assert warning is not None
    assert "0.18.0-W12-130.1" in warning


def test_spawned_shallow_only_no_recurse(project_dir, logger):
    """shallow 一層：spawned 的子任務即使 pending 也不檢查（明示不 recurse）。

    結構：
      ana (待 complete)
        spawned: [imp.1 completed]
                   children: [imp.1.1 pending]  ← 不 recurse 進此層
    應通過（不警告），因為 imp.1 自身為 completed。
    """
    _write_ticket(project_dir, "0.18.0-W12-140.1", status="completed")
    # 寫一個 grand-child pending 但不應影響結果
    _write_ticket(project_dir, "0.18.0-W12-140.1.1", status="pending")

    warning = check_spawned_tickets_status(
        ["0.18.0-W12-140.1"], project_dir, logger
    )
    assert warning is None, "shallow 一層：grand-child pending 不應觸發警告"


# ----------------------------------------------------------------------------
# 歷史回測：W11-005 ANA 場景（W12-003 ANA 結論明確要求的回歸測試）
# ----------------------------------------------------------------------------

def test_w11_005_historical_regression(project_dir, logger):
    """W11-005 ANA completed + spawned [W12-001 pending] 必須觸發新警告。

    W12-003 ANA 整合結論第 5 點：W11-005 是歷史實例（type=ANA, status=completed,
    spawned=[W12-001 pending]）— 在新警告層下，若該 ANA 重新觸發 acceptance gate，
    必須輸出非 terminal 警告。本測試模擬該情境，確認警告層正確觸發。
    """
    # 模擬 W12-001 (spawned IMP) 仍處 pending
    _write_ticket(project_dir, "0.18.0-W12-001", status="pending")

    # 模擬 W11-005 ANA 對 W12-001 的 spawned 關聯
    warning = check_spawned_tickets_status(
        ["0.18.0-W12-001"], project_dir, logger
    )
    assert warning is not None, "W11-005 歷史實例必須觸發新警告"
    assert "0.18.0-W12-001" in warning
    assert "pending" in warning
    # 確認警告含「防護性 ANA」提醒（非 terminal 標題部分）
    assert "防護性" in warning or "非 terminal" in warning
