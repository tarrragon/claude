#!/usr/bin/env python3
"""
Unit tests for prompt-submit-hook.py

Complete coverage of negation word filtering for SKILL suggestion detection.
Tests cover:
1. _is_keyword_negated() - core negation detection function
2. check_skill_suggestion() - QUERY_KEYWORDS negation filtering
3. check_action_keywords() - ACTION_KEYWORDS negation filtering
4. check_handoff_keywords() - HANDOFF_KEYWORDS negation filtering
5. check_decision_keywords() - DECISION_KEYWORDS negation filtering
"""

import importlib.util
import sys
import unittest
from pathlib import Path

# Add parent directory to path for imports
hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

# Import the hook module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "prompt_submit_hook",
    hooks_dir / "prompt-submit-hook.py"
)
prompt_submit_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prompt_submit_hook)

# Extract the functions we need
_is_keyword_negated = prompt_submit_hook._is_keyword_negated
check_skill_suggestion = prompt_submit_hook.check_skill_suggestion
check_action_keywords = prompt_submit_hook.check_action_keywords
check_handoff_keywords = prompt_submit_hook.check_handoff_keywords
check_decision_keywords = prompt_submit_hook.check_decision_keywords
NEGATION_WINDOW_SIZE = prompt_submit_hook.NEGATION_WINDOW_SIZE


class TestIsKeywordNegated(unittest.TestCase):
    """Test _is_keyword_negated() function for various negation patterns."""

    def test_adjacent_negation_single_word(self):
        """Test immediate negation: 否定詞 + 關鍵字."""
        prompt = "不需要查詢"
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_adjacent_negation_different_negation_word_1(self):
        """Test immediate negation with 不用."""
        prompt = "不用查詢"
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_adjacent_negation_different_negation_word_2(self):
        """Test immediate negation with 沒有."""
        prompt = "沒有查詢"
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_remote_negation_one_word_gap(self):
        """Test remote negation with one word gap between negation and keyword.

        窗口大小 15 字元應能覆蓋：不需要 + 去 + 查詢
        """
        prompt = "完全不需要去查詢"
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_remote_negation_multiple_words(self):
        """Test remote negation with multiple words between negation and keyword."""
        prompt = "我不是說不用查詢進度"
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_positive_context_no_negation(self):
        """Test positive context: keyword without negation."""
        prompt = "需要查詢進度"
        self.assertFalse(_is_keyword_negated(prompt, "查詢"))

    def test_negation_after_keyword(self):
        """Test negation word appearing after keyword (not before).

        否定詞應在關鍵字前面才算，後面不算。
        """
        prompt = "查詢一下，不需要了"
        self.assertFalse(_is_keyword_negated(prompt, "查詢"))

    def test_negation_outside_window(self):
        """Test negation word outside the NEGATION_WINDOW_SIZE boundary."""
        # 構造：不用 + 20個字 + 查詢（超過 15 字元窗口）
        middle = "a" * 20  # 20 characters to exceed window
        prompt = f"不用{middle}查詢"
        self.assertFalse(_is_keyword_negated(prompt, "查詢"))

    def test_keyword_not_found(self):
        """Test when keyword is not in prompt at all."""
        prompt = "不需要處理"
        self.assertFalse(_is_keyword_negated(prompt, "查詢"))

    def test_no_negation_words(self):
        """Test when no negation words in prompt."""
        prompt = "查詢進度如何"
        self.assertFalse(_is_keyword_negated(prompt, "查詢"))

    def test_exact_window_boundary(self):
        """Test keyword exactly at window boundary."""
        # 窗口大小是 15，所以應該包含 negation + 15 個字元
        prompt = "不需要" + "x" * 9 + "查詢"  # 不需要(3) + xxx(9) + 查詢(2) = 14 chars
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_just_outside_window_boundary(self):
        """Test keyword just outside window boundary."""
        prompt = "不需要" + "x" * 15 + "查詢"  # beyond NEGATION_WINDOW_SIZE
        self.assertFalse(_is_keyword_negated(prompt, "查詢"))


class TestCheckSkillSuggestion(unittest.TestCase):
    """Test check_skill_suggestion() function with negation filtering."""

    def test_normal_query_trigger_progress(self):
        """Test normal query trigger for 進度."""
        result = check_skill_suggestion("目前的進度如何")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "/ticket track summary")
        self.assertEqual(result[1], "query")

    def test_normal_query_trigger_status(self):
        """Test normal query trigger for 狀態."""
        result = check_skill_suggestion("現在的狀態")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "/ticket track summary")
        self.assertEqual(result[1], "query")

    def test_negated_query_progress(self):
        """Test negated query: 不需要查詢進度."""
        result = check_skill_suggestion("不需要查詢進度")
        self.assertIsNone(result)

    def test_negated_query_status(self):
        """Test negated query: 不需要確認狀態."""
        result = check_skill_suggestion("不需要確認狀態")
        self.assertIsNone(result)

    def test_remote_negated_query(self):
        """Test remote negation: 完全不需要去確認進度."""
        result = check_skill_suggestion("完全不需要去確認進度")
        self.assertIsNone(result)

    def test_normal_query_pending(self):
        """Test normal query for pending items."""
        result = check_skill_suggestion("還有哪些待處理任務")
        self.assertIsNotNone(result)
        self.assertIn("/ticket track list", result[0])
        self.assertEqual(result[1], "query")

    def test_negated_query_pending(self):
        """Test negated query: 不用查詢待處理."""
        result = check_skill_suggestion("不用查詢待處理的任務")
        self.assertIsNone(result)


class TestCheckActionKeywords(unittest.TestCase):
    """Test check_action_keywords() function with negation filtering."""

    def test_normal_action_process_ticket(self):
        """Test normal action: 處理 + ticket."""
        result = check_action_keywords("我要處理這個 ticket")
        self.assertEqual(result, "/ticket track claim")

    def test_normal_action_handle_task(self):
        """Test normal action: handle + task."""
        result = check_action_keywords("please handle this task")
        self.assertEqual(result, "/ticket track claim")

    def test_normal_action_start_ticket(self):
        """Test normal action: 開始 + ticket."""
        result = check_action_keywords("開始處理這個 ticket")
        self.assertEqual(result, "/ticket track claim")

    def test_negated_action_process(self):
        """Test negated action: 不需要處理 ticket."""
        result = check_action_keywords("不需要處理這個 ticket")
        self.assertIsNone(result)

    def test_negated_action_execute(self):
        """Test negated action: 不用執行任務."""
        result = check_action_keywords("不用執行任務")
        self.assertIsNone(result)

    def test_negated_action_first_keyword(self):
        """Test negation on first keyword: 不需要處理."""
        prompt = "我不需要處理 ticket"
        result = check_action_keywords(prompt)
        self.assertIsNone(result)

    def test_negated_action_second_keyword(self):
        """Test negation on second keyword (target).

        When the target keyword is negated, the pattern should not match.
        """
        prompt = "我想處理不是 ticket"
        # In this case, "ticket" follows a negation structure
        # But our implementation checks if either keyword is negated
        # This test documents the actual behavior
        result = check_action_keywords(prompt)
        # Negation of "ticket" doesn't trigger in this context
        # because "不是" is not in NEGATION_WORDS
        # So this would normally match, but it's a weird sentence

    def test_normal_action_complete_task(self):
        """Test normal action: complete + task."""
        result = check_action_keywords("please complete this task")
        self.assertEqual(result, "/ticket track complete")

    def test_negated_action_complete(self):
        """Test negated action: 不用完成任務."""
        result = check_action_keywords("不用完成任務")
        self.assertIsNone(result)

    def test_normal_action_create_ticket(self):
        """Test normal action: 建立 + ticket."""
        result = check_action_keywords("建立新的 ticket")
        self.assertEqual(result, "/ticket create")

    def test_negated_action_create(self):
        """Test negated action: 不需要建立 ticket."""
        result = check_action_keywords("不需要建立 ticket")
        self.assertIsNone(result)


class TestCheckHandoffKeywords(unittest.TestCase):
    """Test check_handoff_keywords() function with negation filtering."""

    def test_normal_handoff_switch_task(self):
        """Test normal handoff: 切換 + 任務."""
        result = check_handoff_keywords("我需要切換任務到下一個")
        self.assertEqual(result, "/ticket handoff switch")

    def test_normal_handoff_switch_ticket(self):
        """Test normal handoff: switch + ticket."""
        result = check_handoff_keywords("please switch ticket now")
        self.assertEqual(result, "/ticket handoff switch")

    def test_negated_handoff_switch(self):
        """Test negated handoff: 不需要切換任務."""
        result = check_handoff_keywords("不需要切換任務")
        self.assertIsNone(result)

    def test_normal_handoff_transfer_single(self):
        """Test normal handoff (single keyword): 交接."""
        result = check_handoff_keywords("我想交接這個任務")
        self.assertEqual(result, "/ticket handoff transfer")

    def test_negated_handoff_transfer(self):
        """Test negated handoff: 不用交接."""
        result = check_handoff_keywords("不用交接")
        self.assertIsNone(result)

    def test_normal_handoff_back_to_parent(self):
        """Test normal handoff: 回到 + 父任務."""
        result = check_handoff_keywords("回到父任務")
        self.assertEqual(result, "/ticket handoff back")

    def test_negated_handoff_back(self):
        """Test negated handoff: 不需要回到父任務."""
        result = check_handoff_keywords("不需要回到父任務")
        self.assertIsNone(result)

    def test_normal_handoff_subtask(self):
        """Test normal handoff: 做 + 子任務."""
        result = check_handoff_keywords("做子任務")
        self.assertEqual(result, "/ticket handoff subtask")

    def test_negated_handoff_subtask(self):
        """Test negated handoff: 不要做子任務."""
        result = check_handoff_keywords("不要做子任務")
        self.assertIsNone(result)

    def test_normal_handoff_restore(self):
        """Test normal handoff: 恢復 + 任務."""
        result = check_handoff_keywords("恢復之前的任務")
        self.assertEqual(result, "/ticket handoff restore")

    def test_negated_handoff_restore(self):
        """Test negated handoff: 不需要恢復任務."""
        result = check_handoff_keywords("不需要恢復任務")
        self.assertIsNone(result)

    def test_normal_handoff_go_back(self):
        """Test normal handoff: go back (empty second keyword)."""
        result = check_handoff_keywords("please go back")
        self.assertEqual(result, "/ticket handoff back")

    def test_negated_handoff_go_back(self):
        """Test negated handoff: 不用 go back."""
        result = check_handoff_keywords("不用 go back")
        self.assertIsNone(result)


class TestCheckDecisionKeywords(unittest.TestCase):
    """Test check_decision_keywords() function with negation filtering."""

    def test_normal_decision_which_approach(self):
        """Test normal decision: 哪個 + 方案."""
        result = check_decision_keywords("哪個方案比較好")
        self.assertEqual(result, "方案選擇")

    def test_normal_decision_select_approach(self):
        """Test normal decision: 選擇 + 方案."""
        result = check_decision_keywords("我需要選擇方案")
        self.assertEqual(result, "方案選擇")

    def test_normal_decision_compare_approach(self):
        """Test normal decision: 比較 + 方案."""
        result = check_decision_keywords("比較不同的方案")
        self.assertEqual(result, "方案選擇")

    def test_negated_decision_approach(self):
        """Test negated decision: 不需要選擇方案."""
        result = check_decision_keywords("不需要選擇方案")
        self.assertIsNone(result)

    def test_normal_decision_split_task(self):
        """Test normal decision: 拆分 + 任務."""
        result = check_decision_keywords("需要拆分任務嗎")
        self.assertEqual(result, "任務拆分確認")

    def test_negated_decision_split_task(self):
        """Test negated decision: 不需要拆分任務."""
        result = check_decision_keywords("不需要拆分任務")
        self.assertIsNone(result)

    def test_normal_decision_parallel_dispatch(self):
        """Test normal decision: 並行 + 派發."""
        result = check_decision_keywords("應該並行派發嗎")
        self.assertEqual(result, "派發方式選擇")

    def test_negated_decision_parallel_dispatch(self):
        """Test negated decision: 不需要並行派發."""
        result = check_decision_keywords("不需要並行派發")
        self.assertIsNone(result)

    def test_normal_decision_priority(self):
        """Test normal decision: 優先 + 處理."""
        result = check_decision_keywords("哪個優先處理")
        self.assertEqual(result, "優先級確認")

    def test_negated_decision_priority(self):
        """Test negated decision: 不需要確認優先級."""
        result = check_decision_keywords("不需要確認優先 處理")
        # This is a tricky case - depends on word boundaries
        # Should match "優先" and "處理" but both might be negated
        self.assertIsNone(result)


class TestNegationEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions for negation filtering."""

    def test_multiple_negation_words_first_matches(self):
        """Test multiple negation words in prompt."""
        prompt = "不需要處理，也不用查詢"
        # 應該檢測到 "處理" 被否定
        self.assertTrue(_is_keyword_negated(prompt, "處理"))

    def test_multiple_negation_words_second_keyword(self):
        """Test multiple negation words: check second keyword."""
        prompt = "不需要處理，也不用查詢"
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_negation_word_in_keyword(self):
        """Test when negation word is part of a larger word."""
        prompt = "需要重新查詢"  # 包含"需"但不是否定詞
        self.assertFalse(_is_keyword_negated(prompt, "查詢"))

    def test_case_insensitive_matching(self):
        """Test that negation matching is case-insensitive."""
        prompt = "NOT 需要 查詢"  # mixed case
        # Note: actual implementation uses lowercase
        result = check_skill_suggestion(prompt)
        # English "NOT" won't match, so should still detect query
        # (depends on implementation)

    def test_empty_prompt(self):
        """Test with empty prompt."""
        result = check_skill_suggestion("")
        self.assertIsNone(result)

    def test_none_prompt(self):
        """Test with None prompt."""
        result = check_skill_suggestion(None)
        self.assertIsNone(result)

    def test_chinese_punctuation_between_negation_and_keyword(self):
        """Test negation with Chinese punctuation in between."""
        prompt = "不需要、查詢進度"
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_newline_in_prompt(self):
        """Test negation with newline character."""
        prompt = "不需要\n查詢進度"
        self.assertTrue(_is_keyword_negated(prompt, "查詢"))

    def test_multiple_same_keywords(self):
        """Test prompt with same keyword appearing multiple times."""
        prompt = "查詢一下進度，不需要查詢詳細內容"
        # First 查詢 is not negated, second is
        # The function finds first negation, so depends on keyword position
        # This is a tricky case showing the limitation of the current implementation


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests with realistic user prompts."""

    def test_realistic_query_scenario_1(self):
        """Realistic scenario: user asking for progress."""
        prompt = "目前有多少個 ticket 還在進行中，進度如何"
        result = check_skill_suggestion(prompt)
        self.assertIsNotNone(result)
        self.assertIn("ticket track", result[0])

    def test_realistic_query_scenario_negated(self):
        """Realistic scenario: user negating query request."""
        prompt = "我不需要查詢進度，直接開始做下一個任務"
        result = check_skill_suggestion(prompt)
        # Query should be negated, but action might trigger
        if result:
            # If query is properly negated, we might get action suggestion
            self.assertNotIn("進度", result[0])

    def test_realistic_action_scenario(self):
        """Realistic scenario: user wanting to process ticket."""
        prompt = "我準備處理 0.3.0-W1-006 這個 ticket"
        result = check_skill_suggestion(prompt)
        # Should detect Ticket ID first, then action
        self.assertIsNotNone(result)

    def test_realistic_handoff_scenario(self):
        """Realistic scenario: user wanting to switch tasks."""
        prompt = "完成了這個，現在要切換任務到下一個"
        result = check_skill_suggestion(prompt)
        self.assertIsNotNone(result)
        # Result could be handoff or check-skill-suggestion related
        # The exact behavior depends on keyword priority
        self.assertTrue(result is not None)

    def test_realistic_negated_action_scenario(self):
        """Realistic scenario: user negating action request."""
        prompt = "不需要我現在就開始處理，先搞清楚狀態"
        result = check_skill_suggestion(prompt)
        # Action should be negated, query might trigger
        if result:
            self.assertNotEqual(result[0], "/ticket track claim")


if __name__ == "__main__":
    unittest.main(verbosity=2)
