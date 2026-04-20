"""
Error Pattern Attribution Filter 測試（PC-099 regression）

對應 Ticket 0.18.0-W10-087：
驗證 `filter_error_patterns_by_ticket_scope` 正確處理 meta-ticket / 跨 session
false positive 場景，不再將「與當前 ticket 無關的 PC 新增」誤報為場景 #17 AUQ。

測試矩陣：
  (1) PC 含 frontmatter source_ticket 匹配當前 ticket → 保留
  (2) PC 含 frontmatter source_ticket 指向其他 ticket → 過濾
  (3) PC 含 frontmatter source_ticket 為 null → 回退至引用檢查
  (4) PC 無 frontmatter 但 ticket md 引用 PC ID → 保留（legacy 格式相容）
  (5) PC 無 frontmatter 且 ticket md 未引用 → 過濾（PC-099 核心防護）
  (6) PC 無 frontmatter 但 ticket md 引用 basename → 保留
  (7) 空候選清單 → 空回傳
  (8) PC 檔案讀取失敗 → 保守歸屬（保留，避免漏報）
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.error_pattern_attribution import (
    filter_error_patterns_by_ticket_scope,
)


CURRENT_TICKET = "0.18.0-W10-087"
OTHER_TICKET = "0.18.0-W10-085"


@pytest.fixture
def logger():
    lg = logging.getLogger("test-pc099")
    lg.addHandler(logging.NullHandler())
    lg.setLevel(logging.DEBUG)
    return lg


def _write_pc(project_dir: Path, rel_path: str, content: str) -> Path:
    full = project_dir / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


# ----------------------------------------------------------------------------
# Frontmatter source_ticket 匹配
# ----------------------------------------------------------------------------

def test_frontmatter_source_ticket_matches_current(tmp_path, logger):
    rel = ".claude/error-patterns/process-compliance/PC-100-a.md"
    _write_pc(
        tmp_path,
        rel,
        f"---\nsource_ticket: {CURRENT_TICKET}\n---\n\n# PC-100\n",
    )
    result = filter_error_patterns_by_ticket_scope(
        [rel], CURRENT_TICKET, "ticket body", tmp_path, logger
    )
    assert result == [rel]


def test_frontmatter_source_ticket_points_to_other(tmp_path, logger):
    rel = ".claude/error-patterns/process-compliance/PC-101-b.md"
    _write_pc(
        tmp_path,
        rel,
        f"---\nsource_ticket: {OTHER_TICKET}\n---\n\n# PC-101\n",
    )
    # ticket body 即使含 PC-101 也應以 frontmatter 為準
    result = filter_error_patterns_by_ticket_scope(
        [rel], CURRENT_TICKET, "see PC-101", tmp_path, logger
    )
    assert result == []


def test_frontmatter_source_ticket_null_falls_back_to_reference(tmp_path, logger):
    rel = ".claude/error-patterns/process-compliance/PC-102-c.md"
    _write_pc(
        tmp_path,
        rel,
        "---\nsource_ticket: null\n---\n\n# PC-102\n",
    )
    # frontmatter null → fallback；ticket 無引用
    result = filter_error_patterns_by_ticket_scope(
        [rel], CURRENT_TICKET, "no mention", tmp_path, logger
    )
    assert result == []

    # fallback 成功場景
    result_ref = filter_error_patterns_by_ticket_scope(
        [rel], CURRENT_TICKET, "relates to PC-102 issue", tmp_path, logger
    )
    assert result_ref == [rel]


# ----------------------------------------------------------------------------
# 無 frontmatter（legacy PC 格式）
# ----------------------------------------------------------------------------

def test_no_frontmatter_ticket_references_pc_id(tmp_path, logger):
    rel = ".claude/error-patterns/process-compliance/PC-103-legacy.md"
    _write_pc(tmp_path, rel, "# PC-103: legacy case\n\nno frontmatter\n")
    result = filter_error_patterns_by_ticket_scope(
        [rel], CURRENT_TICKET, "Context: handles PC-103 root cause", tmp_path, logger
    )
    assert result == [rel]


def test_no_frontmatter_no_reference_filtered_pc099_core(tmp_path, logger):
    """PC-099 核心保護：無 frontmatter 且 ticket 未引用 → 過濾。"""
    rel = ".claude/error-patterns/process-compliance/PC-099-meta-ticket.md"
    _write_pc(tmp_path, rel, "# PC-099\n\nunrelated session work\n")
    ticket_md = """---
id: 0.18.0-W10-087
title: some unrelated ticket work
---

# Body

This ticket is about something completely different.
"""
    result = filter_error_patterns_by_ticket_scope(
        [rel], CURRENT_TICKET, ticket_md, tmp_path, logger
    )
    assert result == []


def test_no_frontmatter_basename_referenced(tmp_path, logger):
    rel = ".claude/error-patterns/process-compliance/PC-104-named.md"
    _write_pc(tmp_path, rel, "# PC-104\n\nno frontmatter\n")
    ticket_md = (
        "see file PC-104-named.md for details"
    )
    result = filter_error_patterns_by_ticket_scope(
        [rel], CURRENT_TICKET, ticket_md, tmp_path, logger
    )
    assert result == [rel]


# ----------------------------------------------------------------------------
# 邊界條件
# ----------------------------------------------------------------------------

def test_empty_candidates_returns_empty(tmp_path, logger):
    assert filter_error_patterns_by_ticket_scope(
        [], CURRENT_TICKET, "any", tmp_path, logger
    ) == []


def test_unreadable_pc_falls_back_to_conservative_attribution(tmp_path, logger):
    rel = ".claude/error-patterns/process-compliance/PC-999-missing.md"
    # 故意不建立檔案，觸發 OSError
    result = filter_error_patterns_by_ticket_scope(
        [rel], CURRENT_TICKET, "any", tmp_path, logger
    )
    # 讀取失敗時保守歸屬以避免漏報
    assert result == [rel]


def test_mixed_candidates_only_attributed_kept(tmp_path, logger):
    """綜合場景：三個候選，僅一個真正歸屬。"""
    rel_own = ".claude/error-patterns/process-compliance/PC-110-own.md"
    rel_other = ".claude/error-patterns/process-compliance/PC-111-other.md"
    rel_legacy_unref = ".claude/error-patterns/process-compliance/PC-112-unref.md"

    _write_pc(tmp_path, rel_own, f"---\nsource_ticket: {CURRENT_TICKET}\n---\n")
    _write_pc(tmp_path, rel_other, f"---\nsource_ticket: {OTHER_TICKET}\n---\n")
    _write_pc(tmp_path, rel_legacy_unref, "# PC-112 legacy no reference\n")

    result = filter_error_patterns_by_ticket_scope(
        [rel_own, rel_other, rel_legacy_unref],
        CURRENT_TICKET,
        "ticket body not mentioning any PC id",
        tmp_path,
        logger,
    )
    assert result == [rel_own]
