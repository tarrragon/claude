"""
Acceptance Checker - frontmatter acceptance list 勾選狀態檢查測試

對應 Ticket 0.18.0-W11-003.1：
  資料源對齊 — has_acceptance_record 應讀 frontmatter acceptance list 的勾選狀態，
  與 CLI track_acceptance.py 寫入端對齊。

測試矩陣：
  AC4 全勾選        : frontmatter 5 項全 [x]，body 無關鍵字 → True
  部分勾選          : frontmatter 4/5 [x]，body 無關鍵字     → False
  全未勾選          : frontmatter 全未勾選                    → False
  body 關鍵字不計入  : frontmatter 未全勾選，body 含舊驗收關鍵字 → False
                      （body 由被審方自由寫入，不構成驗收訊號，tarrragon/claude#70）
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


# body 由被審方自由寫入：下列舊驗收關鍵字任一出現在 body，都不得讓
# 未全勾選的 frontmatter 判為有驗收記錄（正向對照：關鍵字確實存在於 body）。
_LEGACY_KEYWORDS = [
    "驗收結果: 通過",
    "Acceptance Audit Report",
    "驗收通過",
    "驗收者：",
    "Auditor:",
    "PM 直接驗收",
    "acceptance-auditor",
]


@pytest.mark.parametrize("keyword", _LEGACY_KEYWORDS)
def test_body_keyword_with_unchecked_acceptance_returns_false(logger, keyword):
    """frontmatter 未勾選 + body 含舊關鍵字 → False（關鍵字不構成驗收訊號）"""
    frontmatter = {"acceptance": ["[ ] 項目一"]}
    body = f"# Ticket\n\n{keyword} 紀錄完整。\n"
    assert keyword in body
    assert has_acceptance_record(body, logger, frontmatter=frontmatter) is False


@pytest.mark.parametrize("frontmatter", [{"acceptance": []}, {"type": "IMP"}, None])
def test_body_keyword_without_acceptance_list_returns_false(logger, frontmatter):
    """空 list、無 acceptance 欄位、frontmatter=None + body 含關鍵字 → False"""
    body = "# Ticket\n\nPM 直接驗收，通過。\n"
    assert has_acceptance_record(body, logger, frontmatter=frontmatter) is False


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


def test_none_frontmatter_no_keyword_returns_false(logger):
    """frontmatter=None + body 無關鍵字 → False"""
    body = "# Ticket\n\n尚未驗收。\n"
    assert has_acceptance_record(body, logger, frontmatter=None) is False


def test_legacy_signature_no_frontmatter_kwarg(logger):
    """既有 caller 未傳 frontmatter（位置參數）→ 仍可呼叫，無驗收清單即 False"""
    body = "# Ticket\n\n驗收結果: 通過\n"
    # 保留既有二參數呼叫方式
    assert has_acceptance_record(body, logger) is False
