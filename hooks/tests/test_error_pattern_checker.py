"""
Error Pattern Checker 測試（0.2.1-W3-337）

驗證 `check_error_pattern_conflicts`（acceptance-gate Step 2.7）正確依
`where.files` 提取關鍵詞並搜尋 error-patterns 目錄：

- list 型別 where.files（完整 YAML 解析器）能正確觸發
- 換行分隔字串型別 where.files（本 hook 套件輕量解析器實際輸出型別，
  0.2.1-W3-330 稽核發現 100% 既有票命中此型別，修復前恆定靜默略過）
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
    """換行分隔字串型別輸入（0.2.1-W3-337 迴歸：runtime hook 實際輸入型別）"""

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
