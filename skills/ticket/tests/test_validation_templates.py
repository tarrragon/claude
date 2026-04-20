"""
validation_templates 模組測試（RED 階段 — 尚未實作）

覆蓋 Phase 1 §7 的 7 個 validation_templates 測試場景：
1. 每個模板正向匹配（5 個模板 × 1 case = 5）
2. 每個模板負向拒絕（5 個模板 × 1 case = 5）
3. 大小寫無關
4. 多模板衝突優先序（第一註冊者勝出）
5. unverifiable 模板回傳結構（is_verifiable=False 且 unverifiable_reason 非空）
6. 無匹配回傳 None（區分「無匹配」與「不可驗證」）
7. list_templates 為只讀

測試對象：
- .claude/skills/ticket/ticket_system/lib/validation_templates.py（Phase 3b 才會實作）
- 預期 import：match_template, list_templates, ValidationCommand, Template

5 個模板名稱（來自 Phase 1 §4）：
- npm_test_pass
- coverage_threshold
- lint_pass
- flaky_fixed（unverifiable）
- skipped_evaluated（unverifiable）
"""

import pytest

# 下列 import 在 Phase 3b 實作前會 ImportError，使本檔案所有測試保持 RED。
from ticket_system.lib.validation_templates import (  # noqa: E402
    match_template,
    list_templates,
    ValidationCommand,
    Template,
)


# ---------------------------------------------------------------------------
# 場景 1：每個模板正向匹配
# ---------------------------------------------------------------------------


class TestPositiveMatches:
    """場景 1：5 個模板正向匹配，回傳對應的 ValidationCommand。"""

    def test_npm_test_pass_positive_match(self):
        """場景 1a：npm_test_pass 正向匹配。"""
        result = match_template("npm test 全部通過且無錯誤")
        assert result is not None, "預期匹配 npm_test_pass，實際 None"
        assert isinstance(result, ValidationCommand)
        assert result.template_name == "npm_test_pass", (
            f"預期 template_name=npm_test_pass，實際 {result.template_name}"
        )
        assert result.is_verifiable is True
        assert result.command is not None and "npm test" in result.command

    def test_coverage_threshold_positive_match(self):
        """場景 1b：coverage_threshold 正向匹配。"""
        result = match_template("測試覆蓋率 >= 80%")
        assert result is not None, "預期匹配 coverage_threshold"
        assert result.template_name == "coverage_threshold"
        assert result.is_verifiable is True
        assert result.command is not None and "coverage" in result.command.lower()

    def test_lint_pass_positive_match(self):
        """場景 1c：lint_pass 正向匹配。"""
        result = match_template("lint 通過，無警告")
        assert result is not None, "預期匹配 lint_pass"
        assert result.template_name == "lint_pass"
        assert result.is_verifiable is True
        assert result.command is not None and "lint" in result.command.lower()

    def test_flaky_fixed_positive_match(self):
        """場景 1d：flaky_fixed 正向匹配（unverifiable）。"""
        result = match_template("flaky test 已修復或標記")
        assert result is not None, "預期匹配 flaky_fixed"
        assert result.template_name == "flaky_fixed"
        assert result.is_verifiable is False, "flaky_fixed 為 unverifiable"

    def test_skipped_evaluated_positive_match(self):
        """場景 1e：skipped_evaluated 正向匹配（unverifiable）。"""
        result = match_template("skipped 測試已評估並記錄原因")
        assert result is not None, "預期匹配 skipped_evaluated"
        assert result.template_name == "skipped_evaluated"
        assert result.is_verifiable is False


# ---------------------------------------------------------------------------
# 場景 2：每個模板負向拒絕
# ---------------------------------------------------------------------------


class TestNegativeRejections:
    """場景 2：不相關文字不應匹配特定模板。"""

    def test_npm_test_not_matched_by_unrelated_text(self):
        """場景 2a：「更新文件」不應匹配 npm_test_pass。"""
        result = match_template("更新 README 文件")
        if result is not None:
            assert result.template_name != "npm_test_pass", (
                f"不應匹配 npm_test_pass，實際匹配：{result.template_name}"
            )

    def test_coverage_not_matched_by_unrelated_text(self):
        """場景 2b：「部署至 production」不應匹配 coverage_threshold。"""
        result = match_template("部署至 production 環境")
        if result is not None:
            assert result.template_name != "coverage_threshold"

    def test_lint_not_matched_by_unrelated_text(self):
        """場景 2c：「建立新 Ticket」不應匹配 lint_pass。"""
        result = match_template("建立新的 Ticket 並派發代理人")
        if result is not None:
            assert result.template_name != "lint_pass"

    def test_flaky_not_matched_by_unrelated_text(self):
        """場景 2d：「完成重構」不應匹配 flaky_fixed。"""
        result = match_template("完成 Phase 4 重構評估")
        if result is not None:
            assert result.template_name != "flaky_fixed"

    def test_skipped_not_matched_by_unrelated_text(self):
        """場景 2e：「效能優化」不應匹配 skipped_evaluated。"""
        result = match_template("效能優化至符合預期指標")
        if result is not None:
            assert result.template_name != "skipped_evaluated"


# ---------------------------------------------------------------------------
# 場景 3：大小寫無關
# ---------------------------------------------------------------------------


class TestCaseInsensitive:
    """場景 3：PM 可能大小寫混用，匹配應大小寫無關。"""

    def test_uppercase_npm_test_still_matches(self):
        """「NPM TEST 全部通過」能匹配 npm_test_pass。"""
        result = match_template("NPM TEST 全部通過")
        assert result is not None, "大寫輸入應能匹配"
        assert result.template_name == "npm_test_pass", (
            f"預期 npm_test_pass，實際 {result.template_name}"
        )

    def test_mixed_case_eslint_matches_lint(self):
        """「ESLint 執行通過」能匹配 lint_pass。"""
        result = match_template("ESLint 執行通過無錯誤")
        assert result is not None, "混合大小寫應能匹配"
        assert result.template_name == "lint_pass"


# ---------------------------------------------------------------------------
# 場景 4：多模板衝突優先序
# ---------------------------------------------------------------------------


class TestConflictPriority:
    """場景 4：同時命中多模板時，第一註冊者勝出（決定性保證）。"""

    def test_first_registered_wins_when_multiple_match(self):
        """同時命中 npm_test_pass 和 coverage_threshold 時，第一註冊者勝出。

        註冊順序（§4 表格）：npm_test_pass 先於 coverage_threshold。
        """
        # 構造同時包含「npm test」與「覆蓋率」兩個 pattern 的文字
        result = match_template("npm test 全部通過且覆蓋率 >= 80%")

        assert result is not None, "預期匹配到模板"
        # 依 §4 表格順序，npm_test_pass 先註冊
        assert result.template_name == "npm_test_pass", (
            f"預期第一註冊者 npm_test_pass 勝出，實際：{result.template_name}"
        )

    def test_conflict_resolution_is_deterministic(self):
        """重複呼叫結果一致（決定性保證）。"""
        text = "npm test 全部通過且覆蓋率 >= 80%"
        first = match_template(text)
        second = match_template(text)
        third = match_template(text)
        assert first is not None and second is not None and third is not None
        assert first.template_name == second.template_name == third.template_name, (
            "多次呼叫應回傳相同模板"
        )


# ---------------------------------------------------------------------------
# 場景 5：unverifiable 模板回傳結構
# ---------------------------------------------------------------------------


class TestUnverifiableStructure:
    """場景 5：unverifiable 模板匹配時回傳結構（PM 顯示跳過原因的基礎）。"""

    def test_flaky_fixed_has_unverifiable_reason(self):
        """flaky_fixed 匹配時 is_verifiable=False 且 unverifiable_reason 非空。"""
        result = match_template("flaky test 已修復")
        assert result is not None
        assert result.is_verifiable is False, "flaky_fixed 應為 unverifiable"
        assert result.command is None, "unverifiable 模板的 command 應為 None"
        assert result.unverifiable_reason is not None, (
            "unverifiable 模板必須提供 unverifiable_reason"
        )
        assert len(result.unverifiable_reason.strip()) > 0, (
            "unverifiable_reason 不應為空白字串"
        )

    def test_skipped_evaluated_has_unverifiable_reason(self):
        """skipped_evaluated 匹配時 is_verifiable=False 且 unverifiable_reason 非空。"""
        result = match_template("skipped 測試已評估")
        assert result is not None
        assert result.is_verifiable is False
        assert result.command is None
        assert result.unverifiable_reason is not None
        assert len(result.unverifiable_reason.strip()) > 0


# ---------------------------------------------------------------------------
# 場景 6：無匹配回傳 None
# ---------------------------------------------------------------------------


class TestNoMatch:
    """場景 6：完全不相關文字回傳 None（區分「無匹配」與「不可驗證」）。"""

    def test_completely_unrelated_text_returns_none(self):
        """「部署至 production」完全不相關，應回傳 None。"""
        result = match_template("部署至 production 環境並監控 24 小時")
        assert result is None, f"完全不相關文字應回傳 None，實際：{result}"

    def test_empty_string_returns_none(self):
        """空字串回傳 None。"""
        result = match_template("")
        assert result is None, "空字串應回傳 None"

    def test_none_vs_unverifiable_are_distinguishable(self):
        """「無匹配」(None) 應與「匹配但不可驗證」(ValidationCommand with is_verifiable=False) 可區分。"""
        no_match = match_template("完成架構重構與效能優化")
        unverifiable_match = match_template("flaky test 已修復")

        assert no_match is None, "不相關文字應為 None"
        assert unverifiable_match is not None, "flaky 應匹配到 unverifiable 模板"
        assert unverifiable_match.is_verifiable is False


# ---------------------------------------------------------------------------
# 場景 7：list_templates 為只讀
# ---------------------------------------------------------------------------


class TestListTemplatesReadOnly:
    """場景 7：list_templates 回傳副本，修改不影響後續查詢（防測試互汙染）。"""

    def test_list_templates_returns_at_least_five(self):
        """規則庫應至少含 5 個模板（AC 驗收條件）。"""
        templates = list_templates()
        assert len(templates) >= 5, f"預期至少 5 個模板，實際 {len(templates)}"

    def test_list_templates_contains_all_required_names(self):
        """5 個模板名稱必須存在（§4 表格）。"""
        templates = list_templates()
        names = {t.name for t in templates}
        required = {
            "npm_test_pass",
            "coverage_threshold",
            "lint_pass",
            "flaky_fixed",
            "skipped_evaluated",
        }
        missing = required - names
        assert not missing, f"規則庫缺少必要模板：{missing}"

    def test_each_template_has_non_empty_patterns(self):
        """每個模板的 patterns 不應為空（§6 驗收條件）。"""
        templates = list_templates()
        for t in templates:
            assert len(t.patterns) > 0, (
                f"模板 {t.name} 的 patterns 不應為空"
            )

    def test_mutating_returned_list_does_not_affect_subsequent_calls(self):
        """嘗試修改回傳值不影響後續查詢。"""
        templates_first = list_templates()
        original_count = len(templates_first)

        # 嘗試以各種方式「污染」回傳值
        try:
            templates_first.clear()  # list 副本可清空，但不應影響規則庫
        except AttributeError:
            # 若回傳 tuple 則會 raise，也是可接受的只讀形式
            pass

        templates_second = list_templates()
        assert len(templates_second) == original_count, (
            f"規則庫應不受外部修改影響，原 {original_count} 個，修改後 {len(templates_second)} 個"
        )

    def test_match_template_unaffected_after_list_mutation(self):
        """修改 list_templates 回傳值後，match_template 行為仍正常。"""
        templates = list_templates()
        try:
            templates.clear()
        except AttributeError:
            pass

        # match_template 應仍能正常工作
        result = match_template("npm test 全部通過")
        assert result is not None, "list_templates 被修改後，match_template 不應受影響"
        assert result.template_name == "npm_test_pass"
