"""
Tests for prompt-submit-hook.py

Comprehensive tests for prompt submission hook functionality,
including SKILL suggestion detection and keyword negation analysis.
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for importing hook modules
hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))

# Import function from parent directory
import importlib.util

hook_file = hook_dir / "prompt-submit-hook.py"
spec = importlib.util.spec_from_file_location("prompt_submit_hook", hook_file)
prompt_submit_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompt_submit_hook)

_is_keyword_negated = prompt_submit_hook._is_keyword_negated


def test_hook_module_exists():
    """Verify hook file exists"""
    hook_file = hook_dir / "prompt-submit-hook.py"
    assert hook_file.exists(), f"Hook file not found: {hook_file}"


# =============================================================================
# _is_keyword_negated 函式測試
# =============================================================================


class TestIsKeywordNegated:
    """Tests for _is_keyword_negated function"""

    # =========================================================================
    # 基本分支：有否定詞 + 關鍵字在窗口內 → True
    # =========================================================================

    def test_negation_with_keyword_in_window_basic(self):
        """Test: negation word directly followed by keyword"""
        # 「不需要查詢」- 否定詞和關鍵字緊鄰
        assert _is_keyword_negated("不需要查詢進度", "查詢") is True

    def test_negation_with_keyword_in_window_with_space(self):
        """Test: negation word with space before keyword"""
        # 「不需要 查詢」- 否定詞和關鍵字之間有空格
        assert _is_keyword_negated("不需要 查詢進度", "查詢") is True

    def test_negation_with_keyword_in_window_separated(self):
        """Test: negation word with other characters within window"""
        # 「不需要去查詢」- 否定詞和關鍵字之間有其他詞彙
        assert _is_keyword_negated("不需要去查詢進度", "查詢") is True

    def test_negation_with_multiple_keywords_first_negated(self):
        """Test: keyword in window of negation"""
        # 「完全不需要去查詢進度」- 否定詞前有修飾詞
        assert _is_keyword_negated("完全不需要去查詢進度", "查詢") is True

    def test_negation_各種否定詞_不是(self):
        """Test: 不是 negation word"""
        assert _is_keyword_negated("不是說查詢進度", "查詢") is True

    def test_negation_各種否定詞_不用(self):
        """Test: 不用 negation word"""
        assert _is_keyword_negated("不用查詢進度", "查詢") is True

    def test_negation_各種否定詞_不要(self):
        """Test: 不要 negation word"""
        assert _is_keyword_negated("不要查詢進度", "查詢") is True

    def test_negation_各種否定詞_沒有(self):
        """Test: 沒有 negation word"""
        assert _is_keyword_negated("沒有查詢進度", "查詢") is True

    def test_negation_各種否定詞_無需(self):
        """Test: 無需 negation word"""
        assert _is_keyword_negated("無需查詢進度", "查詢") is True

    def test_negation_各種否定詞_不必(self):
        """Test: 不必 negation word"""
        assert _is_keyword_negated("不必查詢進度", "查詢") is True

    def test_negation_各種否定詞_無須(self):
        """Test: 無須 negation word"""
        assert _is_keyword_negated("無須查詢進度", "查詢") is True

    # =========================================================================
    # 邊界情況：否定詞在文本末尾或接近末尾
    # =========================================================================

    def test_negation_at_end_keyword_in_window(self):
        """Test: negation word at end with keyword just within window"""
        # 「你好世界不用查詢」- 否定詞後只有15字符空間
        prompt = "你好世界不用查詢進度的事情"
        assert _is_keyword_negated(prompt, "查詢") is True

    def test_negation_near_end_keyword_at_boundary(self):
        """Test: keyword at exact window boundary"""
        # NEGATION_WINDOW_SIZE = 15, 測試關鍵字在窗口末尾
        # 「不用」位置0，窗口為 [2:17]，「查詢」恰好在位置14-15（在窗口內）
        prompt = "不用來一個超長的中間詞語然後查詢"
        # Window[2:17] = "來一個超長的中間詞語然後查詢"，包含「查詢」
        assert _is_keyword_negated(prompt, "查詢") is True

    def test_negation_keyword_before_window_end(self):
        """Test: keyword just before window ends"""
        # 確保關鍵字在 NEGATION_WINDOW_SIZE 內
        prompt = "不用一二三四五六查詢"  # 不用(0-1) + 一二三四五六(2-7) + 查詢(8-9)
        assert _is_keyword_negated(prompt, "查詢") is True

    # =========================================================================
    # 分支：沒有否定詞 → False
    # =========================================================================

    def test_no_negation_word_in_prompt(self):
        """Test: prompt without any negation words"""
        assert _is_keyword_negated("我想查詢進度", "查詢") is False

    def test_no_negation_word_multiple_keywords(self):
        """Test: prompt with keywords but no negation"""
        assert _is_keyword_negated("要處理任務並查詢進度", "查詢") is False

    def test_no_keyword_in_prompt(self):
        """Test: prompt with negation but not the keyword"""
        assert _is_keyword_negated("不需要檢查狀態", "查詢") is False

    # =========================================================================
    # 分支：有否定詞但關鍵字超出窗口 → False
    # =========================================================================

    def test_negation_keyword_outside_window_after(self):
        """Test: keyword appears after window (beyond NEGATION_WINDOW_SIZE)"""
        # 「不用」後跟超過15個字符才是「查詢」
        prompt = "不用一二三四五六七八九十十一十二查詢"
        # 「不用」位置0，窗口為[2:17]，但「查詢」位置在18+
        assert _is_keyword_negated(prompt, "查詢") is False

    def test_negation_keyword_far_away(self):
        """Test: negation and keyword are far apart"""
        # 「不用...查詢」在15字符窗口內，所以應返回True
        # 測試需要keyword在窗口外的情況，用不同的keyword
        assert _is_keyword_negated("不用聯繫任何人我要查詢進度的詳細信息非常重要", "非常") is False

    # =========================================================================
    # 分支：多個否定詞的情況
    # =========================================================================

    def test_multiple_negations_first_has_keyword(self):
        """Test: multiple negations, first one contains keyword"""
        # 「不需要查詢，也不用跟蹤」- 第一個否定詞包含「查詢」
        assert _is_keyword_negated("不需要查詢，也不用跟蹤", "查詢") is True

    def test_multiple_negations_second_has_keyword(self):
        """Test: multiple negations, second one contains keyword"""
        # 「不用跟蹤，也不需要查詢」- 第二個否定詞包含「查詢」
        assert _is_keyword_negated("不用跟蹤，也不需要查詢進度", "查詢") is True

    def test_multiple_negations_none_has_keyword(self):
        """Test: multiple negations but none contains keyword"""
        assert _is_keyword_negated("不用跟蹤，也沒有通知", "查詢") is False

    # =========================================================================
    # 邊界情況：空字符串和特殊情況
    # =========================================================================

    def test_empty_prompt(self):
        """Test: empty prompt"""
        assert _is_keyword_negated("", "查詢") is False

    def test_empty_keyword(self):
        """Test: empty keyword"""
        # 空字符串會被 'in' 操作符視為在任何字符串中，所以返回 True
        # 這是 Python 的標準行為：'' in 'any string' == True
        assert _is_keyword_negated("不需要查詢", "") is True

    def test_single_character_keyword(self):
        """Test: single character keyword"""
        assert _is_keyword_negated("不要去查", "去") is True

    def test_long_keyword(self):
        """Test: long multi-character keyword"""
        assert _is_keyword_negated("不用批量派發任務", "批量派發") is True

    # =========================================================================
    # 語境測試：實際使用情況
    # =========================================================================

    def test_real_case_不需要查詢進度(self):
        """Test: real-world case 「不需要查詢進度」"""
        assert _is_keyword_negated("不需要查詢進度", "查詢") is True

    def test_real_case_我不是說不用查詢(self):
        """Test: real-world case 「我不是說不用查詢」"""
        assert _is_keyword_negated("我不是說不用查詢進度", "查詢") is True

    def test_real_case_沒有需要處理任務(self):
        """Test: real-world case 「沒有需要處理任務」"""
        assert _is_keyword_negated("沒有需要處理任務", "處理") is True

    def test_real_case_請不要派發任務(self):
        """Test: real-world case 「請不要派發任務」"""
        assert _is_keyword_negated("請不要派發任務", "派發") is True

    def test_real_case_positive_需要查詢進度(self):
        """Test: real-world positive case 「需要查詢進度」"""
        assert _is_keyword_negated("需要查詢進度", "查詢") is False

    def test_real_case_positive_我要處理任務(self):
        """Test: real-world positive case 「我要處理任務」"""
        assert _is_keyword_negated("我要處理任務", "處理") is False

    # =========================================================================
    # 對稱性測試：確保多次呼叫結果一致
    # =========================================================================

    def test_idempotent_multiple_calls(self):
        """Test: function is idempotent"""
        prompt = "不需要查詢進度"
        keyword = "查詢"
        result1 = _is_keyword_negated(prompt, keyword)
        result2 = _is_keyword_negated(prompt, keyword)
        result3 = _is_keyword_negated(prompt, keyword)
        assert result1 == result2 == result3 is True
