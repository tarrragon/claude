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


class TestValidateExecutionLogByTypeH3SubheaderBoundary:
    """W17-047 regression：h3 子標題不應被誤判為章節結束邊界

    原 bug：validate_execution_log_by_type 同時把 `## ` 與 `### ` 當章節邊界，
    導致章節內使用 h3 子標題組織內容時，內容被誤切至第一個 `### ` 之前，
    只剩章節標題 + Schema 註解，被判為 placeholder。

    修復後：僅 h2 (`## `) 行首匹配才是章節邊界；h3 子標題保留在章節內。
    """

    def test_ana_with_h3_subheaders_in_problem_analysis_passes(self):
        """W17-046 觸發案例：Problem Analysis 使用 h3 子標題組織內容，應通過。"""
        body = """## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填 -->

### 問題現象

body-check 誤判合法章節為 placeholder。

### 問題本質

章節邊界判定同時採用 `## ` 與 `### ` 兩層標記。

### 根因分析

第一個 `### ` 會被誤認為下一章節起點。

## Solution
<!-- Schema[ANA/Solution]: 必填 -->

### 修復方向

改用 re.MULTILINE 只匹配 `^## ` 行首。

### 測試要求

新增 regression case 覆蓋 h3 子標題情境。
"""
        passed, unfilled = validate_execution_log_by_type("ANA", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_imp_with_h3_subheaders_in_test_results_passes(self):
        """IMP：Test Results 含 h3 子標題，應通過。"""
        body = """## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

### 執行指令

pytest tests/ticket_system/

### 結果摘要

15 passed, 0 failed
"""
        passed, unfilled = validate_execution_log_by_type("IMP", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_ana_section_with_only_h3_subheader_no_body_still_passes_if_subheader_has_content(self):
        """章節內只有 h3 子標題 + 實質內容（無章節直屬內文），應通過。"""
        body = """## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填 -->
### 根因

核心原因是章節邊界邏輯把 h3 當作章節結束。

## Solution
<!-- Schema[ANA/Solution]: 必填 -->
### 方向

改用 h2 行首匹配。
"""
        passed, unfilled = validate_execution_log_by_type("ANA", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_ana_empty_section_still_fails(self):
        """既有行為保留：章節內真的沒內容（只有 Schema 註解）→ placeholder。"""
        body = """## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填 -->

## Solution
<!-- Schema[ANA/Solution]: 必填 -->

實質解法內容。
"""
        passed, unfilled = validate_execution_log_by_type("ANA", body)
        assert passed is False
        assert unfilled == ["Problem Analysis"]

    def test_ana_code_block_with_h2_like_string_not_treated_as_section_boundary(self):
        """Edge case：章節內 code block 含 `## ` 非行首字串，不應誤當章節邊界。

        注意：此測試確認 re.MULTILINE 的 `^` 行首錨點正確運作。
        code block 內若有 markdown 縮排後的 `## ` 才算行首（因為 fenced code block
        仍會讓字元在行首），故改用 `^## ` 的同時須確認程式碼範例在 Problem Analysis
        章節內的「行中」`## ` 不誤判。本測試以段落內的行中 `## ` 驗證。
        """
        body = """## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填 -->

這段文字提到 `## header` 作為 markdown 範例說明，此處 `## ` 不在行首。

另外還有段落混用行中文字：前綴 ## 不是章節起點。

## Solution
<!-- Schema[ANA/Solution]: 必填 -->

行首 `## ` 才是下一章節。
"""
        passed, unfilled = validate_execution_log_by_type("ANA", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_ana_section_boundary_recognizes_h2_after_h3(self):
        """章節內 h3 後仍能正確辨識 h2 為下一章節邊界。"""
        body = """## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填 -->

### 子標題 A
內容 A

### 子標題 B
內容 B

## Solution
<!-- Schema[ANA/Solution]: 必填 -->

Solution 內容。
"""
        passed, unfilled = validate_execution_log_by_type("ANA", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []
        # 再手動驗證：如果 Solution 僅 placeholder 應被標註
        body_solution_empty = """## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填 -->

### 子標題 A
內容 A

## Solution
<!-- Schema[ANA/Solution]: 必填 -->
"""
        passed2, unfilled2 = validate_execution_log_by_type("ANA", body_solution_empty)
        assert passed2 is False
        assert unfilled2 == ["Solution"]


class TestIsPlaceholderMarkdownSeparator:
    """W17-071 regression：剝除 HTML 註解後若剩下 markdown 分隔符 `---`

    應視為 placeholder（ticket body schema 以 `---` 分隔章節，本身非實質內容）。

    觸發案例：W17-056 事件，agent 寫實作內容在自定義 H2，schema section
    只剩 `<!-- Schema note -->` + `<!-- To be filled -->` + `---` 空殼。
    原本 `_is_placeholder` 對 `---` 返回 False，導致 false negative。
    """

    def test_bare_triple_dash_is_placeholder(self):
        """TC-071-01：純 `---` → placeholder"""
        assert _is_placeholder("---") is True

    def test_triple_dash_with_trailing_whitespace_is_placeholder(self):
        """TC-071-02：`---` 加空白/換行 → placeholder"""
        assert _is_placeholder("---\n") is True
        assert _is_placeholder("  ---  \n\n") is True

    def test_longer_dashes_is_placeholder(self):
        """TC-071-03：`----` 或更多 dash 的分隔符 → placeholder"""
        assert _is_placeholder("----") is True
        assert _is_placeholder("--------") is True

    def test_html_comment_plus_separator_is_placeholder(self):
        """TC-071-04：W17-056 核心案例：HTML 註解 + 分隔符 → placeholder"""
        text = (
            "<!-- Schema[IMP/Solution]: 選填 -->\n"
            "\n"
            "<!-- To be filled by executing agent -->\n"
            "\n"
            "---"
        )
        assert _is_placeholder(text) is True

    def test_schema_note_plus_separator_only_is_placeholder(self):
        """TC-071-05：Schema 註解 + 獨立分隔符 → placeholder"""
        text = (
            "<!-- Schema[IMP/Problem Analysis]: 選填 -->\n"
            "\n"
            "---\n"
        )
        assert _is_placeholder(text) is True

    def test_separator_with_real_content_is_not_placeholder(self):
        """TC-071-06：分隔符 + 實質內容 → 非 placeholder（不應過度剝除）"""
        text = (
            "<!-- Schema[IMP/Solution]: 必填 -->\n"
            "\n"
            "---\n"
            "\n"
            "實際解法：修改 regex pattern。\n"
        )
        assert _is_placeholder(text) is False

    def test_inline_triple_dash_not_on_own_line_is_not_placeholder(self):
        """TC-071-07：非獨立行的 `---`（如 `a---b`）不應被剝除當分隔符"""
        text = "實作 A---B 連接詞的解析邏輯。"
        assert _is_placeholder(text) is False


class TestValidateExecutionLogSchemaBoundary:
    """W17-071 regression：validate_execution_log section 邊界限定為 Schema 章節名

    觸發案例：agent 在 ticket body 寫自定義 H2（如 `## 實作摘要`）
    把 schema section（## Solution）的內容切斷。原本任意 `##`/`###` 都當邊界
    導致 schema section 只剩 note + 分隔符被誤判為已填寫。
    """

    def test_custom_h2_before_schema_section_does_not_cut(self):
        """TC-071-08：自定義 H2 不應切斷 schema section 內容範圍"""
        body = """# Execution Log

## Problem Analysis
<!-- Schema note -->

問題根因：regex 誤判。

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

## 實作摘要

這是 agent 寫的自定義 H2 章節，應被視為 Solution 章節的一部分，
不該被當作章節邊界把 Solution 內容切空。

## Test Results

pytest：全綠。
"""
        passed, unfilled = validate_execution_log("TEST-071-1", body)
        # Solution 有實質內容（自定義 H2 + 說明段落），應判為已填寫
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_solution_with_only_schema_note_and_separator_fails(self):
        """TC-071-09：W17-056 核心場景—自定義 H2 切斷後 Solution 空殼

        Solution 之後緊接自定義 H2 `## 實作摘要`（不在 schema 清單）——
        修復後自定義 H2 不被當邊界，所以 Solution 會把後續內容都吃進來。
        本 case 測試 `## Solution` 下本來就是空殼（只有 schema note + 分隔符），
        後續連 `## 實作摘要` 都沒有，只有下一個 schema 章節 `## Test Results`。
        """
        body = """# Execution Log

## Problem Analysis

根因已分析。

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

<!-- To be filled by executing agent -->

---

## Test Results

pytest：全綠。
"""
        passed, unfilled = validate_execution_log("TEST-071-2", body)
        assert passed is False
        assert "Solution" in unfilled

    def test_custom_h3_subsection_not_cut(self):
        """TC-071-10：自定義 H3 子標題不應截斷 schema section"""
        body = """## Problem Analysis

### 問題現象

body-check 誤判。

### 根因分析

regex 未剝除分隔符。

## Solution

### 修復方向

剝除分隔符 + 限定章節邊界。

## Test Results

pytest 全綠。
"""
        passed, unfilled = validate_execution_log("TEST-071-3", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_empty_sections_between_schema_boundaries_fails(self):
        """TC-071-11：所有 schema 章節都空殼（只有 schema note + 分隔符）→ 全 unfilled"""
        body = """# Execution Log

## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 選填 -->

---

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

---

## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

---

## Completion Info

pending
"""
        passed, unfilled = validate_execution_log("TEST-071-4", body)
        assert passed is False
        assert set(unfilled) == {"Problem Analysis", "Solution", "Test Results"}

    def test_h3_level_schema_section_still_recognized(self):
        """TC-071-12：h3 層級的 schema 章節（`### Problem Analysis`）仍能辨識"""
        body = """## Execution Log

### Problem Analysis

分析內容。

### Solution

解法內容。

### Test Results

測試結果。
"""
        passed, unfilled = validate_execution_log("TEST-071-5", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []


class TestValidateExecutionLogByTypeBacktickBoundary:
    """W17-074 regression：validate_execution_log_by_type 對 backtick 包住的章節名
    不應誤判為實際 header。

    觸發案例：W17-071 agent 實作時 live reproduction。Problem Analysis 章節中
    引用其他 schema 章節名時（如「該章節指 `## Test Results`」），原本用
    `body.find("## Test Results")` 做 substring 匹配會命中 backtick 內部位置，
    後續 content_start/next_section_idx 計算出空字串，導致 Test Results 被誤判
    為 placeholder（false positive：實際該章節有真實內容）。

    修復：section header 定位改用 line-anchored regex `^## Section\\b`（multiline），
    只匹配行首 header，不命中 backtick / 段落內的引用字串。

    同家族參照：W17-071 已對 validate_execution_log（通用三章節版本）套用相同修復，
    本次補 validate_execution_log_by_type（type-aware 版本）的漏網之魚。
    """

    def test_imp_body_with_backticked_section_name_in_problem_analysis_passes(self):
        """TC-074-01：W17-071 live reproduction 核心案例

        IMP body：Problem Analysis 中用 backtick 包住 `## Test Results` 作文字引用，
        同時 Test Results 章節本身有實質內容。修復後應通過（False positive 被消除）。
        """
        body = """## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 選填 -->

分析：W17-071 修復時發現 `## Test Results` 章節被誤判為 placeholder。
根因是 section header 定位使用 substring 匹配。

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

改用 line-anchored regex。

## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

pytest tests/ticket_system/：全綠（26 passed）。
commit: abc1234
"""
        passed, unfilled = validate_execution_log_by_type("IMP", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_imp_body_with_multiple_backticked_section_names_passes(self):
        """TC-074-02：body 含多個 backtick 包住的章節名引用，皆不誤判

        Problem Analysis 內同時提到 `## Test Results` 和 `## Solution` 兩個反引號
        引用，修復後 Test Results 的定位應命中真正行首 header。
        """
        body = """## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 選填 -->

既有 `## Solution` 章節與 `## Test Results` 章節皆需實質填寫。
此處的 backtick 引用不應被誤判為 header。

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

套用 line-anchored regex 修復策略。

## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

全數通過（15 passed, 0 failed）。
"""
        passed, unfilled = validate_execution_log_by_type("IMP", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_ana_body_with_backticked_problem_analysis_reference_passes(self):
        """TC-074-03：ANA body Solution 章節中用 backtick 引用 `## Problem Analysis`

        若原本用 body.find("## Problem Analysis") 會先命中 Solution 內 backtick 位置，
        導致 Problem Analysis 的 section_start 被判在錯誤位置。修復後應通過。
        """
        body = """## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填 -->

分析 W17-074 bug：section header 定位誤判。

## Solution
<!-- Schema[ANA/Solution]: 必填 -->

修復方向：將 `## Problem Analysis` 章節的定位邏輯改用 regex。
"""
        passed, unfilled = validate_execution_log_by_type("ANA", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []

    def test_imp_body_backticked_section_but_real_section_missing_still_fails(self):
        """TC-074-04：body 只有 backtick 引用但無真正 header → 仍應判為未填寫

        Problem Analysis 中提到 `## Test Results` 但整個 body 沒有真正的
        `## Test Results` 行首 header。修復後不應因 backtick 命中而誤判為存在。
        """
        body = """## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 選填 -->

這裡提到 `## Test Results` 但下方其實沒有該章節。

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

解法摘要。
"""
        passed, unfilled = validate_execution_log_by_type("IMP", body)
        assert passed is False
        assert "Test Results" in unfilled

    def test_imp_body_backticked_section_with_real_empty_section_fails(self):
        """TC-074-05：backtick 引用 + 真正章節為空殼 → 正確判為未填寫

        確認修復後若真正章節存在但內容只有 schema note + placeholder，仍判為
        未填寫（避免修復過度把 backtick 引用的位置當成有效 header）。
        """
        body = """## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 選填 -->

引用 `## Test Results` 章節規格。

## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

<!-- To be filled by executing agent -->
"""
        passed, unfilled = validate_execution_log_by_type("IMP", body)
        assert passed is False
        assert "Test Results" in unfilled

    def test_inline_backtick_section_name_not_at_line_start_not_cut(self):
        """TC-074-06：段落中間（非行首）的 `## Section` 引用不應被當章節邊界

        確認 line-anchored regex 不會誤把段落內縮排或行中的 `## Test Results`
        當成章節 header 起點。
        """
        body = """## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 選填 -->

這段文字中提到 `## Test Results` 並不在行首位置。
本句前綴 ## Test Results 也只是行中文字，不是 header。

## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

實際測試結果。
"""
        passed, unfilled = validate_execution_log_by_type("IMP", body)
        assert passed is True, f"Expected pass but unfilled={unfilled}"
        assert unfilled == []
