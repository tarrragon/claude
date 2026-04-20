"""
Acceptance Checker - frontmatter acceptance list 勾選狀態檢查測試

對應 Ticket 0.18.0-W11-003.1：
  資料源對齊 — has_acceptance_record 應讀 frontmatter acceptance list 的勾選狀態，
  與 CLI track_acceptance.py 寫入端對齊。

測試矩陣：
  AC4 全勾選        : frontmatter 5 項全 [x]，body 無關鍵字 → True
  部分勾選          : frontmatter 4/5 [x]，body 無關鍵字     → False
  空 list fallback  : frontmatter 空或缺欄位，body 含關鍵字  → True
  舊 Ticket（AC6）  : 無 acceptance 欄位，body 含關鍵字       → True
  全未勾選 + 無關鍵字: frontmatter 全未勾選，body 無關鍵字    → False
"""

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.acceptance_checker import has_acceptance_record


@pytest.fixture
def logger():
    return logging.getLogger("test_acceptance_checker")


def test_all_checked_frontmatter_returns_true(logger):
    """AC4：frontmatter acceptance 全部 [x] 勾選 → True（不需 body 關鍵字）"""
    frontmatter = {
        "acceptance": [
            "[x] 項目一",
            "[x] 項目二",
            "[x] 項目三",
            "[x] 項目四",
            "[x] 項目五",
        ]
    }
    body = "# Ticket\n\n一些正文內容，沒有驗收關鍵字。\n"
    assert has_acceptance_record(body, logger, frontmatter=frontmatter) is True


def test_partially_checked_frontmatter_returns_false(logger):
    """部分勾選（4/5）→ False（且 body 無關鍵字可 fallback）"""
    frontmatter = {
        "acceptance": [
            "[x] 項目一",
            "[x] 項目二",
            "[x] 項目三",
            "[x] 項目四",
            "[ ] 項目五",
        ]
    }
    body = "# Ticket\n\n尚未完成。\n"
    assert has_acceptance_record(body, logger, frontmatter=frontmatter) is False


def test_empty_acceptance_fallback_to_body_keyword(logger):
    """空 list + body 含關鍵字 → True（fallback 既有邏輯）"""
    frontmatter = {"acceptance": []}
    body = "# Ticket\n\n驗收通過，紀錄完整。\n"
    assert has_acceptance_record(body, logger, frontmatter=frontmatter) is True


def test_missing_acceptance_field_fallback_to_body(logger):
    """AC6：無 acceptance 欄位（舊 Ticket）+ body 含關鍵字 → True"""
    frontmatter = {"type": "IMP"}  # 無 acceptance 欄位
    body = "# Ticket\n\nPM 直接驗收，通過。\n"
    assert has_acceptance_record(body, logger, frontmatter=frontmatter) is True


def test_all_unchecked_no_keyword_returns_false(logger):
    """frontmatter 全未勾選 + body 無關鍵字 → False"""
    frontmatter = {
        "acceptance": [
            "[ ] 項目一",
            "[ ] 項目二",
        ]
    }
    body = "# Ticket\n\n待處理。\n"
    assert has_acceptance_record(body, logger, frontmatter=frontmatter) is False


def test_none_frontmatter_backward_compat(logger):
    """frontmatter=None（向後相容舊 caller）+ body 含關鍵字 → True"""
    body = "# Ticket\n\nAcceptance Audit Report: all passed.\n"
    assert has_acceptance_record(body, logger, frontmatter=None) is True


def test_none_frontmatter_no_keyword_returns_false(logger):
    """frontmatter=None + body 無關鍵字 → False"""
    body = "# Ticket\n\n尚未驗收。\n"
    assert has_acceptance_record(body, logger, frontmatter=None) is False


def test_legacy_signature_no_frontmatter_kwarg(logger):
    """既有 caller 未傳 frontmatter（位置參數）→ 仍可運作（body 關鍵字）"""
    body = "# Ticket\n\n驗收結果: 通過\n"
    # 保留既有二參數呼叫方式
    assert has_acceptance_record(body, logger) is True
