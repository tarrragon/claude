"""
ticket_validator._is_placeholder 與 validate_execution_log* 測試

W17-032：修復 _is_placeholder 誤判含 HTML 註解但有實質內容的 section 為 placeholder。

核心規則：
- HTML 註解本身不算內容；剝除後若仍有實質文字，section 視為已填寫。
- 既有佔位符偵測（空白、(pending)/TBD/TODO/N/A、（待填寫：...）、純 HTML 註解）須保留。
"""
import pytest

from ticket_system.lib.ticket_validator import (
    _is_placeholder,
    validate_execution_log,
    validate_execution_log_by_type,
)


class TestIsPlaceholderHtmlComment:
    """HTML 註解相關佔位符行為測試（W17-032 修復重點）"""

    def test_html_comment_with_substantial_content_is_not_placeholder(self):
        """
        TC-032-01：Schema 註解 + 實質內容 → 非 placeholder

        這是 W17-032 修復的核心 case：body schema 範本內置 Schema 標註註解，
        append-log 實際內容後，`_is_placeholder` 不應誤判為佔位符。
        """
        text = (
            "<!-- Schema[IMP/Test Results]: 必填（至少記錄執行指令與通過數）-->\n"
            "\n"
            "執行指令：pytest tests/\n"
            "結果：15 passed, 0 failed"
        )
        assert _is_placeholder(text) is False

    def test_html_comment_only_is_placeholder(self):
        """TC-032-02：僅含 HTML 註解無其他內容 → 仍為 placeholder"""
        text = "<!-- To be filled by executing agent -->"
        assert _is_placeholder(text) is True

    def test_schema_comment_only_is_placeholder(self):
        """TC-032-03：僅 Schema 註解無實質內容 → 仍為 placeholder（保留行為）"""
        text = "<!-- Schema[IMP/Test Results]: 必填 -->"
        assert _is_placeholder(text) is True

    def test_multiple_html_comments_only_is_placeholder(self):
        """TC-032-04：多段 HTML 註解但無實質內容 → placeholder"""
        text = (
            "<!-- Schema[IMP/Test Results]: 必填 -->\n"
            "<!-- To be filled by executing agent -->"
        )
        assert _is_placeholder(text) is True

    def test_html_comment_plus_chinese_placeholder_is_placeholder(self):
        """TC-032-05：HTML 註解 + 中文佔位符（待填寫） → placeholder（組合 case）"""
        text = (
            "<!-- Schema[IMP/Problem Analysis]: 選填 -->\n"
            "\n"
            "（待填寫：問題發生的直接原因是什麼？）"
        )
        assert _is_placeholder(text) is True

    def test_html_comment_plus_pending_marker_is_placeholder(self):
        """TC-032-06：HTML 註解 + (pending) → placeholder"""
        text = (
            "<!-- Schema[IMP/Solution]: 選填 -->\n"
            "(pending)"
        )
        assert _is_placeholder(text) is True

    def test_multiline_html_comment_with_content_is_not_placeholder(self):
        """TC-032-07：跨行 HTML 註解 + 實質內容 → 非 placeholder"""
        text = (
            "<!-- 調查過程記錄（可選）：\n"
            "搜尋指令：grep -rn 'pattern' path/\n"
            "確認的位置：\n"
            "- file1.py:123\n"
            "-->\n"
            "\n"
            "實際根因：regex 匹配過於寬鬆"
        )
        assert _is_placeholder(text) is False


class TestIsPlaceholderLegacyBehavior:
    """既有佔位符偵測行為（保留不變）"""

    def test_empty_string_is_placeholder(self):
        assert _is_placeholder("") is True

    def test_whitespace_only_is_placeholder(self):
        assert _is_placeholder("   \n\t  ") is True

    def test_none_is_placeholder(self):
        assert _is_placeholder(None) is True  # type: ignore[arg-type]

    def test_non_string_is_placeholder(self):
        assert _is_placeholder(123) is True  # type: ignore[arg-type]

    def test_pending_marker_is_placeholder(self):
        assert _is_placeholder("(pending)") is True

    def test_tbd_marker_is_placeholder(self):
        assert _is_placeholder("TBD") is True

    def test_todo_marker_is_placeholder(self):
        assert _is_placeholder("TODO: 待處理") is True

    def test_chinese_placeholder_is_placeholder(self):
        assert _is_placeholder("（待填寫：問題發生的直接原因）") is True

    def test_chinese_required_placeholder_is_placeholder(self):
        assert _is_placeholder("（必填：至少記錄執行指令與通過數）") is True

    def test_plain_text_is_not_placeholder(self):
        assert _is_placeholder("這是實質內容，描述問題根因。") is False


class TestValidateExecutionLogIntegration:
    """validate_execution_log 整合測試：HTML 註解 + 內容不應被擋"""

    def test_body_with_schema_comments_and_content_passes(self):
        """完整 body：所有 section 含 Schema 註解 + 實質內容 → 通過

        注意：validate_execution_log 的 section extraction 遇到 `### ` 即視為下一段，
        因此本測試刻意在 `## XXX` 下放扁平文字（不加 `### 子標題`），
        專注驗證 `_is_placeholder` 對「HTML 註解 + 扁平實質內容」的判斷。
        """
        body = """# Execution Log

## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 選填 -->

regex 誤判導致 complete 被擋。

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

剝除 HTML 註解後再判斷實質內容。

## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

pytest tests/ -v：15 passed
"""
        passed, unfilled = validate_execution_log("TEST-001", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_body_with_schema_comments_only_fails(self):
        """body 所有 section 僅有 Schema 註解 → 全部 unfilled"""
        body = """# Execution Log

## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 選填 -->

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->
"""
        passed, unfilled = validate_execution_log("TEST-002", body)
        assert passed is False
        assert set(unfilled) == {"Problem Analysis", "Solution", "Test Results"}


class TestValidateExecutionLogByTypeIntegration:
    """validate_execution_log_by_type 整合測試（type-aware schema）"""

    def test_imp_with_test_results_filled_passes(self):
        """IMP：Test Results 含 Schema 註解 + 實質內容 → 通過"""
        body = """## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

pytest tests/：全數通過（15 passed）
commit: abc1234
"""
        passed, unfilled = validate_execution_log_by_type("IMP", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_imp_with_test_results_schema_comment_only_fails(self):
        """IMP：Test Results 僅 Schema 註解無實質內容 → 不通過"""
        body = """## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->
"""
        passed, unfilled = validate_execution_log_by_type("IMP", body)
        assert passed is False
        assert unfilled == ["Test Results"]

    def test_ana_with_both_filled_passes(self):
        """ANA：Problem Analysis + Solution 都有實質內容（含 Schema 註解）→ 通過"""
        body = """## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填 -->

分析：W17-016 body schema 機制與 placeholder 偵測衝突。

## Solution
<!-- Schema[ANA/Solution]: 必填 -->

選項 C：剝除所有 HTML 註解後再判斷實質內容。
"""
        passed, unfilled = validate_execution_log_by_type("ANA", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_doc_always_passes(self):
        """DOC：無必填 section → 直接通過"""
        passed, unfilled = validate_execution_log_by_type("DOC", "")
        assert passed is True
        assert unfilled == []
