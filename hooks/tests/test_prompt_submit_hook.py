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


# =============================================================================
# check_decision_keywords 函式測試
# =============================================================================

check_decision_keywords = prompt_submit_hook.check_decision_keywords


class TestScenario8ExecutionDirectionConfirmation:
    """場景 #8（執行方向確認）的完整測試套件，35 個測試案例"""

    # =========================================================================
    # A. 正向測試（9 個）
    # =========================================================================

    class TestPositiveMatch:
        """正向測試：應觸發場景 #8"""

        # 場景 A1：任務順序詢問 - 3 個案例
        def test_positive_01a_task_order_basic(self):
            """正向測試 A1a：「順序」和「任務」基本觸發"""
            result = check_decision_keywords("任務的執行順序應該如何安排")
            assert result == "執行方向確認"

        def test_positive_01b_task_order_non_adjacent(self):
            """正向測試 A1b：「順序」和「任務」不相鄰"""
            result = check_decision_keywords("這些不同的任務順序也很重要")
            assert result == "執行方向確認"

        def test_positive_01c_task_order_long_text(self):
            """正向測試 A1c：長文本中找到關鍵字"""
            result = check_decision_keywords("我們現在需要確定這幾個不同任務的執行順序應該如何比較合理")
            assert result == "執行方向確認"

        # 場景 A2：下一步方向詢問 - 3 個案例
        def test_positive_02a_next_direction_basic(self):
            """正向測試 A2a：「接下來」和「做」基本觸發"""
            result = check_decision_keywords("接下來要做哪個任務")
            assert result == "執行方向確認"

        def test_positive_02b_next_direction_non_adjacent(self):
            """正向測試 A2b：「接下來」和「做」不相鄰"""
            result = check_decision_keywords("接下來需要我們做什麼工作")
            assert result == "執行方向確認"

        def test_positive_02c_next_direction_long_text(self):
            """正向測試 A2c：長文本中找到關鍵字"""
            result = check_decision_keywords("我們現在完成了上一個階段，接下來應該要做什麼")
            assert result == "執行方向確認"

        # 場景 A3：執行先後安排 - 3 個案例
        def test_positive_03a_execution_order_basic(self):
            """正向測試 A3a：「先後」和「執行」基本觸發"""
            result = check_decision_keywords("先後執行的順序要怎麼決定")
            assert result == "執行方向確認"

        def test_positive_03b_execution_order_non_adjacent(self):
            """正向測試 A3b：「先後」和「執行」不相鄰"""
            result = check_decision_keywords("這些任務先後去執行的話會不會有問題")
            assert result == "執行方向確認"

        def test_positive_03c_execution_order_long_text(self):
            """正向測試 A3c：長文本中找到關鍵字"""
            result = check_decision_keywords("現在我們有多個待執行的項目，先後執行的順序應該怎樣安排才比較合理")
            assert result == "執行方向確認"

    # =========================================================================
    # B. 否定語境測試（7 個）
    # =========================================================================

    class TestNegationContext:
        """否定語境測試：不應觸發場景 #8"""

        # 場景 B1：「順序」被否定詞修飾 - 3 個案例
        def test_negation_01a_order_negated_basic(self):
            """否定測試 B1a：「順序」被「不需要」否定"""
            result = check_decision_keywords("不需要確認任務順序")
            assert result is None

        def test_negation_01b_order_negated_alternative(self):
            """否定測試 B1b：「順序」被「無需」否定"""
            result = check_decision_keywords("無需考慮任務順序的問題")
            assert result is None

        def test_negation_01c_order_negated_far_distance(self):
            """否定測試 B1c：「順序」被遠距否定詞修飾"""
            result = check_decision_keywords("完全不需要去關心任務順序這個事")
            assert result is None

        # 場景 B2：「接下來」被否定詞修飾 - 2 個案例
        def test_negation_02a_next_negated_basic(self):
            """否定測試 B2a：「接下來」被「無須」否定"""
            result = check_decision_keywords("無須考慮接下來要做什麼")
            assert result is None

        def test_negation_02b_next_negated_alternative(self):
            """否定測試 B2b：「接下來」被「不用」否定"""
            result = check_decision_keywords("不用擔心接下來做什麼")
            assert result is None

        # 場景 B3：「執行」被否定詞修飾 - 2 個案例
        def test_negation_03a_execution_negated_basic(self):
            """否定測試 B3a：「執行」被「不要」否定"""
            result = check_decision_keywords("不要先後執行所有任務")
            assert result is None

        def test_negation_03b_execution_negated_alternative(self):
            """否定測試 B3b：「執行」被「不必」否定"""
            result = check_decision_keywords("不必先後執行這些檔案的修改")
            assert result is None

    # =========================================================================
    # C. 邊界條件測試（6 個）
    # =========================================================================

    class TestBoundaryConditions:
        """邊界條件測試：單一關鍵字不應觸發"""

        # 場景 C1：只含「順序」不含「任務」 - 2 個案例
        def test_boundary_01a_only_order_keyword(self):
            """邊界測試 C1a：只有「順序」"""
            result = check_decision_keywords("怎樣確定執行順序")
            assert result is None

        def test_boundary_01b_missing_order_keyword(self):
            """邊界測試 C1b：「任務」出現但「順序」不出現"""
            result = check_decision_keywords("這個任務怎麼做")
            assert result is None

        # 場景 C2：只含「接下來」不含「做」 - 2 個案例
        def test_boundary_02a_only_next_keyword(self):
            """邊界測試 C2a：只有「接下來」"""
            result = check_decision_keywords("接下來？")
            assert result is None

        def test_boundary_02b_missing_next_keyword(self):
            """邊界測試 C2b：「做」出現但「接下來」不出現"""
            result = check_decision_keywords("要做什麼")
            assert result is None

        # 場景 C3：只含「先後」不含「執行」 - 2 個案例
        def test_boundary_03a_only_execution_keyword(self):
            """邊界測試 C3a：只有「先後」"""
            result = check_decision_keywords("先後如何安排")
            assert result is None

        def test_boundary_03b_missing_execution_keyword(self):
            """邊界測試 C3b：「執行」出現但「先後」不出現"""
            result = check_decision_keywords("應該怎樣執行")
            assert result is None

    # =========================================================================
    # D. 與現有場景的邊界測試（3 個）
    # =========================================================================

    class TestScenarioBoundary:
        """場景邊界測試：驗證與其他場景無重疊"""

        def test_scenario_boundary_04a_scenario7_priority(self):
            """邊界測試 D1a：場景 #7（派發方式）不被誤觸發為 #8"""
            # #7 的關鍵字「並行」+「派發」應回傳 #7，不是 #8
            result = check_decision_keywords("要並行派發這些任務嗎")
            assert result == "派發方式選擇"  # #7，非 #8

        def test_scenario_boundary_04b_scenario8_no_confusion(self):
            """邊界測試 D1b：場景 #8 關鍵字與 #7 無重疊"""
            # #8 的新關鍵字不與 #7 重疊
            result = check_decision_keywords("任務順序和派發方式分開考慮")
            # 此測試驗證字典迭代順序和優先級
            assert result is not None  # 應該匹配某個場景

        def test_scenario_boundary_05a_scenario5_preserved(self):
            """邊界測試 D2a：場景 #5（優先級）保留原有行為"""
            # #5 的關鍵字「先做」+「哪個」應仍回傳 #5，不變為 #8
            result = check_decision_keywords("先做哪個任務比較好")
            assert result == "優先級確認"  # #5，非 #8

    # =========================================================================
    # E. 無匹配測試（2 個）
    # =========================================================================

    class TestNoMatch:
        """無匹配測試：不含決策類關鍵字"""

        def test_no_match_01a_pure_technical(self):
            """無匹配測試 E1a：純技術詢問"""
            result = check_decision_keywords("這個程式碼怎麼改")
            assert result is None

        def test_no_match_01b_casual_greeting(self):
            """無匹配測試 E1b：日常問候"""
            result = check_decision_keywords("你好，最近怎麼樣")
            assert result is None

    # =========================================================================
    # F. 整合測試（2 個）
    # =========================================================================

    class TestIntegration:
        """整合測試：驗證 Hook 完整流程"""

        def test_integration_01a_complete_flow_task_order(self):
            """整合測試 F1a：場景 #8 觸發後正確格式化訊息"""
            result = check_decision_keywords("接下來要做什麼")
            assert result == "執行方向確認"

        def test_integration_01b_complete_flow_mixed(self):
            """整合測試 F1b：多個決策關鍵字時優先級測試"""
            # 輸入同時含多個決策關鍵字，驗證優先級和匹配結果
            result = check_decision_keywords("任務的順序要怎樣安排")
            assert result == "執行方向確認"

    # =========================================================================
    # G. 邊界/誤觸發防護測試（6 個）
    # =========================================================================

    class TestBoundaryAndSafeguard:
        """邊界/誤觸發防護測試"""

        # 場景 G1：大小寫處理 - 2 個案例
        def test_boundary_06a_english_chinese_mix(self):
            """邊界測試 G1a：英文和中文混合"""
            # 輸入已小寫化（Hook 前置處理），task 不含「任務」
            result = check_decision_keywords("task 順序如何")
            assert result is None  # 缺少「任務」

        def test_boundary_06b_pure_english(self):
            """邊界測試 G1b：純英文"""
            result = check_decision_keywords("execution order")
            assert result is None  # 無中文關鍵字

        # 場景 G2：長文本 - 2 個案例
        def test_boundary_07a_long_text_over_100chars(self):
            """邊界測試 G2a：超過 100 字符的長文本"""
            long_text = "我想了解一下這幾個不同的任務執行順序應該如何安排比較好，有沒有什麼建議呢"
            result = check_decision_keywords(long_text)
            assert result == "執行方向確認"

        def test_boundary_07b_multi_line_combined(self):
            """邊界測試 G2b：多句組合"""
            multi_line = "現在我們有幾個任務，先後執行的順序要怎麼決定？你有什麼建議"
            result = check_decision_keywords(multi_line)
            assert result == "執行方向確認"

        # 場景 G3：否定詞窗口邊界 - 2 個案例
        def test_boundary_08a_keyword_within_window(self):
            """邊界測試 G3a：關鍵字在否定詞窗口內"""
            # 「不用」後 8 字符內是「順序」
            result = check_decision_keywords("不用一二三四五六順序")
            assert result is None  # 被否定

        def test_boundary_08b_keyword_just_outside_window(self):
            """邊界測試 G3b：關鍵字剛好超出窗口"""
            # 「不用」後超過 15 字符才是「順序」，但兩個關鍵字都要出現
            result = check_decision_keywords("不用一二三四五六七八九十十一十二三順序和任務")
            assert result == "執行方向確認"  # 不被否定（超出窗口）
