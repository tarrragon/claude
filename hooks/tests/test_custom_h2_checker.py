"""
Custom H2 Checker 測試（W17-072）

驗證 `custom_h2_checker` 能正確偵測 ticket body 中的非 Schema H2 章節：

- Schema H2 不被誤報（Task Summary / Problem Analysis / Solution / Test Results / ...）
- 自定義 H2 被偵測（`## 實作摘要` / `## 驗證指令與結果` / `## 修復摘要` 等）
- frontmatter 的 `---` 分隔符不造成誤判
- H3 / H4 子章節不被納入（僅限 H2 層級）
- 混合情境下只回報非 Schema H2
"""

import logging
import sys
from pathlib import Path

# 將 .claude/hooks 加入 sys.path，讓測試能 import acceptance_checkers
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.custom_h2_checker import (
    _strip_frontmatter,
    check_custom_h2_sections,
    find_custom_h2_sections,
)


def _logger():
    log = logging.getLogger("test_custom_h2_checker")
    log.addHandler(logging.NullHandler())
    return log


# ----------------------------------------------------------------------------
# _strip_frontmatter
# ----------------------------------------------------------------------------

class TestStripFrontmatter:
    def test_with_frontmatter(self):
        content = """---
id: 0.18.0-W17-072
type: IMP
---

# Body

## Solution
內容。
"""
        body = _strip_frontmatter(content)
        assert body.lstrip().startswith("# Body")
        assert "id: 0.18.0-W17-072" not in body

    def test_without_frontmatter(self):
        content = "## Solution\n內容\n"
        body = _strip_frontmatter(content)
        assert body == content

    def test_incomplete_frontmatter_returns_original(self):
        """frontmatter 開頭 `---` 但無結束分隔符 → 回傳原文"""
        content = "---\nid: test\n\n## Solution\n內容\n"
        body = _strip_frontmatter(content)
        assert body == content


# ----------------------------------------------------------------------------
# find_custom_h2_sections
# ----------------------------------------------------------------------------

class TestFindCustomH2Sections:
    def test_all_schema_h2_no_violation(self):
        """所有 H2 都是 Schema 章節 → 回傳空 list"""
        content = """---
id: test
---

## Task Summary
摘要。

## Problem Analysis
分析。

## Solution
解法。

## Test Results
測試結果。

## Completion Info
pending.
"""
        assert find_custom_h2_sections(content) == []

    def test_single_custom_h2_detected(self):
        """單一自定義 H2 → 回報"""
        content = """---
id: test
---

## Solution

## 實作摘要
違規。

## Test Results
"""
        result = find_custom_h2_sections(content)
        assert result == ["實作摘要"]

    def test_multiple_custom_h2_detected(self):
        """多個自定義 H2 → 全部回報"""
        content = """---
id: test
---

## Solution

## 實作摘要
X。

## 驗證指令與結果
Y。

## Test Results
"""
        result = find_custom_h2_sections(content)
        assert result == ["實作摘要", "驗證指令與結果"]

    def test_h3_not_reported(self):
        """H3 子章節不應被偵測（即使名稱是自定義）"""
        content = """---
id: test
---

## Solution

### 實作摘要
H3 是允許的。

### 設計決策
也是允許的。

## Test Results
"""
        assert find_custom_h2_sections(content) == []

    def test_mixed_schema_and_custom(self):
        """混合情境：Schema + 自定義 → 只回報自定義"""
        content = """---
id: test
---

## Problem Analysis
OK。

## 額外分析
違規。

## Solution
OK。

## 驗證
違規。

## Test Results
OK。
"""
        result = find_custom_h2_sections(content)
        assert result == ["額外分析", "驗證"]

    def test_w17_056_reproduction_case(self):
        """W17-056 事件重現：`## 實作摘要` + `## 驗證指令與結果` 被偵測"""
        content = """---
id: 0.18.0-W17-056
type: IMP
---

# Execution Log

## Task Summary
摘要。

## Problem Analysis
分析。

## Solution
<!-- Schema note -->

---

## 實作摘要
agent 違規寫這裡。

## Test Results
<!-- Schema note -->

---

## 驗證指令與結果
agent 違規寫這裡。

## Completion Info
pending.
"""
        result = find_custom_h2_sections(content)
        assert result == ["實作摘要", "驗證指令與結果"]

    def test_no_h2_at_all(self):
        """body 無任何 H2 → 空 list"""
        content = """---
id: test
---

# Title

只有 H1。
"""
        assert find_custom_h2_sections(content) == []

    def test_frontmatter_dashes_not_misinterpreted(self):
        """frontmatter 的 `---` 分隔符不應造成 H2 誤判"""
        content = """---
id: test
status: pending
---

## Solution
OK。
"""
        assert find_custom_h2_sections(content) == []


# ----------------------------------------------------------------------------
# check_custom_h2_sections（整合）
# ----------------------------------------------------------------------------

class TestCheckCustomH2Sections:
    def test_returns_empty_list_on_compliance(self):
        content = """---
id: test
---

## Solution
OK。

## Test Results
OK。
"""
        assert check_custom_h2_sections(content, _logger()) == []

    def test_returns_violations_on_custom_h2(self):
        content = """---
id: test
---

## Solution

## 實作摘要
違規。
"""
        result = check_custom_h2_sections(content, _logger())
        assert result == ["實作摘要"]
