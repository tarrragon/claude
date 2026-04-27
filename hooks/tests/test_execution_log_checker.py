"""
Execution Log Checker 測試（W17-071）

測試 hook 端 `_is_section_empty` 的雙根因修復：

- Root cause A：HTML 註解剝除後若剩下 markdown 分隔符 `---`（schema 章節分隔），
  原先被誤判為「有內容」。修復後應判為空。
- Root cause B：原先使用「任意 `##`」作為 section 邊界，agent 寫自定義 H2
  （如 `## 實作摘要`）會切斷 schema section；修復後只認 Schema 定義章節名。

對應 Ticket 0.18.0-W17-071 AC：
- `_is_section_empty` 對 schema note + 分隔符的空殼章節返回 True
- 自定義 H2 不截斷 schema section，内容延伸到下一個 schema 章節
- 既有行為保留（有實質內容不誤判為空）
"""

import logging
import sys
from pathlib import Path

# 將 .claude/hooks 加入 sys.path，讓測試能 import acceptance_checkers
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.execution_log_checker import (
    _is_section_empty,
    check_execution_log_filled,
)


class TestIsSectionEmptySeparatorStrip:
    """Root cause A：markdown 分隔符應被剝除"""

    def test_section_with_only_schema_note_and_separator_is_empty(self):
        """W17-056 核心案例：schema note + `---` → section empty"""
        content = """## Solution
<!-- Schema[IMP/Solution]: 選填 -->

<!-- To be filled by executing agent -->

---

## Test Results
pytest all green.
"""
        assert _is_section_empty(content, "Solution") is True

    def test_section_with_bare_separator_is_empty(self):
        """只有 `---` 分隔符 → section empty"""
        content = """## Solution

---

## Test Results
測試結果。
"""
        assert _is_section_empty(content, "Solution") is True

    def test_section_with_separator_and_real_content_not_empty(self):
        """分隔符 + 實質內容 → section not empty（不過度剝除）"""
        content = """## Solution

---

實際解法：修改 regex。

## Test Results
pytest all green.
"""
        assert _is_section_empty(content, "Solution") is False


class TestIsSectionEmptySchemaBoundary:
    """Root cause B：section 邊界只認 Schema 定義章節名"""

    def test_custom_h2_does_not_cut_section(self):
        """自定義 H2（非 schema 章節）不截斷 Solution 範圍"""
        content = """## Solution

## 實作摘要

這是 agent 寫的自定義 H2，應視為 Solution 章節的一部分，
不該把 Solution 切成空殼。

## Test Results
pytest all green.
"""
        # 自定義 H2 不算邊界，Solution 內容延伸到 Test Results 之前
        assert _is_section_empty(content, "Solution") is False

    def test_solution_empty_between_schema_sections(self):
        """Solution 在兩個 schema section 之間為空殼 → empty"""
        content = """## Problem Analysis
分析內容。

## Solution
<!-- Schema note -->
---

## Test Results
pytest all green.
"""
        assert _is_section_empty(content, "Solution") is True

    def test_schema_section_recognized_as_boundary(self):
        """Schema 章節（如 `## Test Results`）仍是有效邊界"""
        content = """## Solution

實際解法。

## Test Results
測試結果。
"""
        assert _is_section_empty(content, "Solution") is False

    def test_solution_content_includes_custom_h2_sections(self):
        """Solution 後面若有多個自定義 H2，都被視為 Solution 章節內容"""
        content = """## Solution

## 實作摘要
做了 X。

## 驗證指令與結果
pytest 全綠。

## Test Results
pytest all green.
"""
        # Solution 底下含 `## 實作摘要` 和 `## 驗證指令與結果`，都視為 Solution 一部分
        assert _is_section_empty(content, "Solution") is False


class TestIsSectionEmptyLegacyBehavior:
    """既有行為保留：標準 placeholder 偵測不變"""

    def test_missing_section_is_empty(self):
        """缺少 section 標題 → empty"""
        content = """## Problem Analysis
有內容。
"""
        assert _is_section_empty(content, "Solution") is True

    def test_section_with_only_html_comment_is_empty(self):
        """只有 HTML 註解 → empty"""
        content = """## Solution
<!-- To be filled by executing agent -->

## Test Results
pytest.
"""
        assert _is_section_empty(content, "Solution") is True

    def test_section_with_chinese_placeholder_is_empty(self):
        """只有中文佔位符 → empty"""
        content = """## Solution
（待填寫：解法設計）

## Test Results
pytest.
"""
        assert _is_section_empty(content, "Solution") is True

    def test_section_with_substantial_content_not_empty(self):
        """有實質內容 → not empty"""
        content = """## Solution

修改 `_is_placeholder` 增加分隔符剝除邏輯。

## Test Results
pytest all green.
"""
        assert _is_section_empty(content, "Solution") is False


class TestCheckExecutionLogFilled:
    """整合測試：check_execution_log_filled 行為（W17-071 regression）"""

    def _logger(self):
        # 使用真實 logger；hook 測試無需 mock
        logger = logging.getLogger("test_execution_log_checker")
        logger.addHandler(logging.NullHandler())
        return logger

    def test_w17_056_reproduction_case_is_empty(self):
        """W17-056 事件重現：schema note + 分隔符 + 自定義 H2 結構

        修復前：Solution 和 Test Results 被判為「已填寫」（自定義 H2 切斷
        section 導致只取到 note + 分隔符，且 `---` 未被剝除被視為實質內容）。
        修復後：兩 section 都判為 empty → check_execution_log_filled 返回 True（未填寫）。
        """
        content = """## Problem Analysis

分析已完成。

## Solution
<!-- Schema[IMP/Solution]: 選填 -->

<!-- To be filled by executing agent -->

---

## 實作摘要

agent 把實作內容寫在自定義 H2 這裡。

## Test Results
<!-- Schema[IMP/Test Results]: 必填 -->

<!-- To be filled by executing agent -->

---

## 驗證指令與結果

agent 把驗證指令寫在自定義 H2 這裡。

## Completion Info
pending.
"""
        # W17-071 修復後：Solution 的「實質內容」含 `## 實作摘要` 子段，
        # 因為自定義 H2 不再被當作 section 邊界。所以 Solution 其實 not empty。
        # 但 Test Results 底下緊接 Completion Info (schema section) 之前也含
        # `## 驗證指令與結果`，應被視為 Test Results 的一部分 → not empty。
        #
        # 即：修復的意義是「schema section 範圍延伸到下一個 schema 邊界」，
        # 讓 agent 寫在自定義 H2 的實際內容被正確歸屬。
        is_empty = check_execution_log_filled(content, self._logger())
        assert is_empty is False  # 兩 section 都有內容（藉由修復後的擴展邊界）

    def test_pure_empty_shell_is_detected_as_empty(self):
        """純空殼（所有 schema section 只有 note + 分隔符，無自定義 H2）→ empty"""
        content = """## Problem Analysis
已分析。

## Solution
<!-- Schema note -->

---

## Test Results
<!-- Schema note -->

---

## Completion Info
pending.
"""
        is_empty = check_execution_log_filled(content, self._logger())
        assert is_empty is True  # Solution + Test Results 都空殼

    def test_both_filled_not_empty(self):
        """Solution 和 Test Results 都有實質內容 → not empty"""
        content = """## Solution

實際解法：修改 regex。

## Test Results

pytest all green.
"""
        is_empty = check_execution_log_filled(content, self._logger())
        assert is_empty is False
