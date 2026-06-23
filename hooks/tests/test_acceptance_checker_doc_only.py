"""
Acceptance Checker - 純文件 IMP 訊息差異化測試（W10-072.2）

驗證 verify_acceptance_record 對純文件 IMP（where.files ≥ 80% 屬純文件路徑）
輸出差異化提示訊息（ACCEPTANCE_RECORD_DOC_ONLY_HINT），而非建議派 acceptance-auditor。

測試矩陣：
  doc-only IMP（100%）：全部 .claude/rules/ 路徑    → DOC_ONLY_HINT 命中
  doc-only IMP（80% 邊界）：4/5 文件 + 1 程式碼      → DOC_ONLY_HINT 命中
  一般 IMP（60%）：3/5 文件 + 2 程式碼               → MISSING_WARNING 命中（< 80%）
  一般 IMP（純程式碼）：全部 .py 路徑                 → MISSING_WARNING 命中
  無 where.files：frontmatter 無路徑資訊             → MISSING_WARNING 命中
  is_doc_only_imp 單元：path 判別正確
"""

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.acceptance_checker import (
    is_doc_only_imp,
    verify_acceptance_record,
)


@pytest.fixture
def logger():
    return logging.getLogger("test_acceptance_checker_doc_only")


@pytest.fixture
def empty_body():
    """無驗收關鍵字、無勾選的 body（觸發 should_check_acceptance + not has_accept）"""
    return "# Ticket\n\n尚未驗收。\n"


def _make_frontmatter(files, ticket_type="IMP"):
    return {
        "type": ticket_type,
        "title": "測試 ticket",
        "acceptance": ["[ ] 項目一"],  # 未勾選 → has_accept=False
        "where": {"files": files},
    }


# ----------------------------------------------------------------------------
# verify_acceptance_record 整合測試
# ----------------------------------------------------------------------------


def test_doc_only_imp_pure_doc_paths_emits_doc_hint(logger, empty_body):
    """100% 純文件路徑 → DOC_ONLY_HINT 命中"""
    fm = _make_frontmatter(
        [
            ".claude/rules/core/quality-baseline.md",
            ".claude/methodologies/atomic-ticket-methodology.md",
            "docs/work-logs/v0.18.0/v0.18.0.md",
        ]
    )
    _, msg, _, _ = verify_acceptance_record(empty_body, fm, "test-doc-100", logger)
    assert msg is not None
    assert "純文件 IMP" in msg
    assert "手動驗收" in msg
    # 不應包含「派發 acceptance-auditor 執行驗收」一般訊息片段
    assert "派發 acceptance-auditor 執行驗收" not in msg


def test_doc_only_imp_at_80_percent_boundary_emits_doc_hint(logger, empty_body):
    """80% 邊界（4/5 文件）→ DOC_ONLY_HINT 命中"""
    fm = _make_frontmatter(
        [
            ".claude/rules/core/quality-baseline.md",
            ".claude/methodologies/test.md",
            "docs/test.md",
            ".claude/pm-rules/decision-tree.md",
            ".claude/hooks/some_code.py",  # 1 個非文件
        ]
    )
    _, msg, _, _ = verify_acceptance_record(empty_body, fm, "test-doc-80", logger)
    assert msg is not None
    assert "純文件 IMP" in msg


def test_general_imp_below_threshold_emits_general_warning(logger, empty_body):
    """60% 文件（3/5）< 80% → 一般 MISSING_WARNING"""
    fm = _make_frontmatter(
        [
            ".claude/rules/test.md",
            "docs/test.md",
            ".claude/methodologies/test.md",
            ".claude/hooks/code1.py",
            ".claude/hooks/code2.py",
        ]
    )
    _, msg, _, _ = verify_acceptance_record(empty_body, fm, "test-mixed-60", logger)
    assert msg is not None
    assert "純文件 IMP" not in msg
    assert "派發 acceptance-auditor" in msg


def test_general_imp_pure_code_emits_general_warning(logger, empty_body):
    """純程式碼路徑 → 一般 MISSING_WARNING"""
    fm = _make_frontmatter(
        [
            ".claude/hooks/some_hook.py",
            ".claude/lib/utils.py",
        ]
    )
    _, msg, _, _ = verify_acceptance_record(empty_body, fm, "test-code", logger)
    assert msg is not None
    assert "純文件 IMP" not in msg
    assert "派發 acceptance-auditor" in msg


def test_imp_without_where_files_emits_general_warning(logger, empty_body):
    """無 where.files → 一般 MISSING_WARNING（資訊不足無法判斷）"""
    fm = {
        "type": "IMP",
        "title": "測試",
        "acceptance": ["[ ] 項目一"],
    }
    _, msg, _, _ = verify_acceptance_record(empty_body, fm, "test-no-files", logger)
    assert msg is not None
    assert "純文件 IMP" not in msg


# ----------------------------------------------------------------------------
# is_doc_only_imp 單元測試
# ----------------------------------------------------------------------------


def test_is_doc_only_imp_pure_doc_returns_true():
    fm = _make_frontmatter([".claude/rules/x.md", "docs/y.md"])
    assert is_doc_only_imp(fm) is True


def test_is_doc_only_imp_pure_code_returns_false():
    fm = _make_frontmatter([".claude/hooks/x.py", "src/y.js"])
    assert is_doc_only_imp(fm) is False


def test_is_doc_only_imp_below_80_percent_returns_false():
    # 3/5 = 60%
    fm = _make_frontmatter(
        [
            ".claude/rules/a.md",
            ".claude/methodologies/b.md",
            "docs/c.md",
            "src/d.js",
            "src/e.js",
        ]
    )
    assert is_doc_only_imp(fm) is False


def test_is_doc_only_imp_at_80_percent_returns_true():
    # 4/5 = 80%
    fm = _make_frontmatter(
        [
            ".claude/rules/a.md",
            ".claude/methodologies/b.md",
            "docs/c.md",
            ".claude/pm-rules/d.md",
            "src/e.js",
        ]
    )
    assert is_doc_only_imp(fm) is True


def test_is_doc_only_imp_empty_or_missing_returns_false():
    assert is_doc_only_imp(None) is False
    assert is_doc_only_imp({}) is False
    assert is_doc_only_imp({"where": {}}) is False
    assert is_doc_only_imp({"where": {"files": []}}) is False


def test_is_doc_only_imp_md_extension_anywhere_counts_as_doc():
    """任意路徑 .md 結尾視為純文件"""
    fm = _make_frontmatter(["README.md", "CHANGELOG.md"])
    assert is_doc_only_imp(fm) is True
