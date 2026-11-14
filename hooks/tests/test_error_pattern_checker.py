"""
Error Pattern Checker 測試（0.2.1-W3-337）

驗證 `check_error_pattern_conflicts`（acceptance-gate Step 2.7）正確依
`where.files` 提取關鍵詞並搜尋 error-patterns 目錄：

- list 型別 where.files（YAML sequence 寫法）能正確觸發
- str 型別 where.files（YAML scalar 寫法——單一路徑不加 dash，或 `|`
  block literal scalar，schema 容忍的合法輸入，0.2.1-W3-330 稽核發現
  修復前呼叫端因僅判斷 `isinstance(x, list)` 而恆定靜默略過此型別）
  同樣能正確觸發（0.2.1-W3-337 迴歸測試）
- DOC/ANA/REF 型別豁免
- 無 where.files 時安全略過
"""

import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.error_pattern_checker import check_error_pattern_conflicts


def _logger():
    log = logging.getLogger("test_error_pattern_checker")
    log.addHandler(logging.NullHandler())
    return log


@pytest.fixture
def project_dir_with_pattern(tmp_path):
    """建立含一個 error-pattern 檔（內容含 'widget' 關鍵詞）的暫存專案目錄。"""
    patterns_dir = tmp_path / ".claude" / "error-patterns" / "implementation"
    patterns_dir.mkdir(parents=True)
    (patterns_dir / "IMP-999-widget-rebuild-loop.md").write_text(
        "# IMP-999\n\nwidget rebuild loop 相關案例，涉及 widget_helper 模組。\n",
        encoding="utf-8",
    )
    return tmp_path


class TestCheckErrorPatternConflictsListInput:
    """list 型別輸入（既有行為，確保修法不回歸）"""

    def test_matching_keyword_returns_conflict(self, project_dir_with_pattern):
        fm = {"type": "IMP", "where": {"files": ["lib/widget_helper.dart"]}}
        result = check_error_pattern_conflicts(fm, project_dir_with_pattern, _logger())
        assert len(result) == 1
        assert "IMP-999-widget-rebuild-loop.md" in result[0]

    def test_no_matching_keyword_returns_empty(self, project_dir_with_pattern):
        fm = {"type": "IMP", "where": {"files": ["lib/unrelated_module.dart"]}}
        result = check_error_pattern_conflicts(fm, project_dir_with_pattern, _logger())
        assert result == []


class TestCheckErrorPatternConflictsStringInput:
    """str 型別輸入（`where.files` 合法 scalar 寫法，0.2.1-W3-337 迴歸）"""

    def test_newline_joined_string_still_triggers(self, project_dir_with_pattern):
        fm = {
            "type": "IMP",
            "where": {"files": "lib/widget_helper.dart\nlib/other.dart"},
        }
        result = check_error_pattern_conflicts(fm, project_dir_with_pattern, _logger())
        assert len(result) == 1
        assert "IMP-999-widget-rebuild-loop.md" in result[0]

    def test_single_file_string_still_triggers(self, project_dir_with_pattern):
        """單一檔案時 where.files 亦可能為純字串（無換行符）"""
        fm = {"type": "IMP", "where": {"files": "lib/widget_helper.dart"}}
        result = check_error_pattern_conflicts(fm, project_dir_with_pattern, _logger())
        assert len(result) == 1


class TestCheckErrorPatternConflictsExemptAndEdgeCases:
    def test_doc_type_exempt(self, project_dir_with_pattern):
        fm = {"type": "DOC", "where": {"files": ["lib/widget_helper.dart"]}}
        assert check_error_pattern_conflicts(fm, project_dir_with_pattern, _logger()) == []

    def test_ana_type_exempt(self, project_dir_with_pattern):
        fm = {"type": "ANA", "where": {"files": ["lib/widget_helper.dart"]}}
        assert check_error_pattern_conflicts(fm, project_dir_with_pattern, _logger()) == []

    def test_no_where_files_returns_empty(self, project_dir_with_pattern):
        fm = {"type": "IMP"}
        assert check_error_pattern_conflicts(fm, project_dir_with_pattern, _logger()) == []

    def test_missing_error_patterns_dir_returns_empty(self, tmp_path):
        fm = {"type": "IMP", "where": {"files": ["lib/widget_helper.dart"]}}
        assert check_error_pattern_conflicts(fm, tmp_path, _logger()) == []


# ---------------------------------------------------------------------------
# 2026-11-12 收斂：通用目錄名排除、底線連字號互通、相關度排序、README 排除
# ---------------------------------------------------------------------------

from acceptance_checkers.error_pattern_checker import (  # noqa: E402
    extract_conflict_keywords,
)


def _write(patterns_root: Path, rel: str, body: str) -> None:
    path = patterns_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


@pytest.fixture
def ranked_corpus(tmp_path):
    """模擬全庫：多數 pattern 只提到通用目錄 hooks，少數直接相關。"""
    root = tmp_path / ".claude" / "error-patterns"
    for i in range(30):
        _write(root, f"process-compliance/PC-{i:03d}-generic.md", "說明 .claude/hooks 的慣例。\n")
    _write(root, "process-compliance/PC-900-hook-health-monitor-noise.md",
           "hook-health-monitor 在 SessionStart 誤報。\n")
    _write(root, "implementation/IMP-901-other.md", "提到 hook_health_monitor 模組。\n")
    _write(root, "process-compliance/PC-902-dir-only.md", "acceptance_checkers 目錄的慣例。\n")
    _write(root, "README.md", "索引：hook-health-monitor、acceptance_checkers。\n")
    return tmp_path


def test_generic_directory_names_not_used_as_keywords():
    keywords = extract_conflict_keywords([".claude/hooks/hook-health-monitor.py"])
    assert "hooks" not in keywords
    assert ".claude" not in keywords
    assert "hook-health-monitor" in keywords


def test_stem_keyword_weighted_above_directory_keyword():
    keywords = extract_conflict_keywords([".claude/hooks/acceptance_checkers/x_checker.py"])
    assert keywords["x_checker"] > keywords["acceptance_checkers"]


def test_single_hook_file_no_longer_matches_whole_corpus(ranked_corpus):
    """修改前：關鍵詞含 hooks，30 個只提到 hooks 的 pattern 全部命中。"""
    fm = {"type": "IMP", "where": {"files": [".claude/hooks/hook-health-monitor.py"]}}

    result = check_error_pattern_conflicts(fm, ranked_corpus, _logger())

    assert not any("generic" in r for r in result)
    assert len(result) == 2


def test_underscore_and_hyphen_variants_both_match(ranked_corpus):
    fm = {"type": "IMP", "where": {"files": [".claude/hooks/hook-health-monitor.py"]}}

    result = check_error_pattern_conflicts(fm, ranked_corpus, _logger())

    assert any("PC-900" in r for r in result)
    assert any("IMP-901" in r for r in result)


def test_relevant_patterns_ranked_first(ranked_corpus):
    """正向對照：檔名與關鍵詞直接相關的 pattern 排在只命中目錄名者之前。"""
    fm = {
        "type": "IMP",
        "where": {"files": [".claude/hooks/acceptance_checkers/hook-health-monitor.py"]},
    }

    result = check_error_pattern_conflicts(fm, ranked_corpus, _logger())

    assert "PC-900" in result[0]
    assert "PC-902" in result[-1]


def test_readme_index_excluded(ranked_corpus):
    fm = {"type": "IMP", "where": {"files": [".claude/hooks/hook-health-monitor.py"]}}

    result = check_error_pattern_conflicts(fm, ranked_corpus, _logger())

    assert not any(r.endswith("README.md") for r in result)


def test_result_order_is_deterministic(ranked_corpus):
    fm = {"type": "IMP", "where": {"files": [".claude/hooks/acceptance_checkers/hook-health-monitor.py"]}}

    first = check_error_pattern_conflicts(fm, ranked_corpus, _logger())
    second = check_error_pattern_conflicts(fm, ranked_corpus, _logger())

    assert first == second
