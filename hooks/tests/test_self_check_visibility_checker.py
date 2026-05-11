"""
Self-Check Visibility Checker 測試（W17-064）

驗證 `self_check_visibility_checker` 在三個核心場景的行為：

1. IMP/ANA/DOC ticket Solution 含 `### 自檢結果` → 靜默通過（return None）
2. IMP/ANA/DOC ticket Solution 缺 `### 自檢結果` → 輸出 warning 字串
3. 非 IMP/ANA/DOC type（如 TST/RES/INV/ADJ）→ 不觸發（return None）
"""

import logging
import sys
from pathlib import Path

# 將 .claude/hooks 加入 sys.path，讓測試能 import acceptance_checkers
_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.self_check_visibility_checker import (
    check_self_check_visibility,
)


def _logger():
    log = logging.getLogger("test_self_check_visibility_checker")
    log.addHandler(logging.NullHandler())
    return log


# 測試樣本 ticket body（含 frontmatter）
def _ticket_with_self_check() -> str:
    return """---
id: test
type: IMP
---

## Task Summary
摘要。

## Solution

### 修復摘要
做了 X。

### 自檢結果
- [x] 命名規範
- [x] 函式長度

## Test Results
通過。
"""


def _ticket_without_self_check() -> str:
    return """---
id: test
type: IMP
---

## Task Summary
摘要。

## Solution

### 修復摘要
做了 X。

## Test Results
通過。
"""


# ----------------------------------------------------------------------------
# 場景 1：含 ### 自檢結果（靜默）
# ----------------------------------------------------------------------------

class TestSelfCheckPresent:
    def test_imp_with_self_check_returns_none(self):
        result = check_self_check_visibility(
            _ticket_with_self_check(), "IMP", _logger()
        )
        assert result is None

    def test_ana_with_self_check_returns_none(self):
        content = _ticket_with_self_check().replace("type: IMP", "type: ANA")
        result = check_self_check_visibility(content, "ANA", _logger())
        assert result is None

    def test_doc_with_self_check_returns_none(self):
        content = _ticket_with_self_check().replace("type: IMP", "type: DOC")
        result = check_self_check_visibility(content, "DOC", _logger())
        assert result is None


# ----------------------------------------------------------------------------
# 場景 2：無 ### 自檢結果（warning）
# ----------------------------------------------------------------------------

class TestSelfCheckMissing:
    def test_imp_without_self_check_returns_warning(self):
        result = check_self_check_visibility(
            _ticket_without_self_check(), "IMP", _logger()
        )
        assert result is not None
        assert "Layer 1" in result
        assert "自檢結果" in result

    def test_ana_without_self_check_returns_warning(self):
        content = _ticket_without_self_check().replace("type: IMP", "type: ANA")
        result = check_self_check_visibility(content, "ANA", _logger())
        assert result is not None

    def test_doc_without_self_check_returns_warning(self):
        content = _ticket_without_self_check().replace("type: IMP", "type: DOC")
        result = check_self_check_visibility(content, "DOC", _logger())
        assert result is not None

    def test_no_solution_section_returns_none(self):
        """Solution 章節都還沒填寫的 ticket，不應觸發本檢查"""
        content = """---
id: test
type: IMP
---

## Task Summary
摘要。
"""
        result = check_self_check_visibility(content, "IMP", _logger())
        assert result is None

    def test_solution_with_h3_self_check_only_in_other_section(self):
        """### 自檢結果 出現在 Solution 之外的章節 → 仍視為缺失"""
        content = """---
id: test
type: IMP
---

## Solution

### 修復摘要
X。

## Test Results

### 自檢結果
誤放這裡。
"""
        result = check_self_check_visibility(content, "IMP", _logger())
        assert result is not None


# ----------------------------------------------------------------------------
# 場景 3：非 IMP/ANA/DOC（不觸發）
# ----------------------------------------------------------------------------

class TestNonApplicableType:
    def test_tst_type_returns_none(self):
        content = _ticket_without_self_check().replace("type: IMP", "type: TST")
        result = check_self_check_visibility(content, "TST", _logger())
        assert result is None

    def test_res_type_returns_none(self):
        result = check_self_check_visibility(
            _ticket_without_self_check(), "RES", _logger()
        )
        assert result is None

    def test_empty_type_returns_none(self):
        result = check_self_check_visibility(
            _ticket_without_self_check(), "", _logger()
        )
        assert result is None

    def test_lowercase_imp_still_triggers(self):
        """type 大小寫不敏感"""
        result = check_self_check_visibility(
            _ticket_without_self_check(), "imp", _logger()
        )
        assert result is not None
