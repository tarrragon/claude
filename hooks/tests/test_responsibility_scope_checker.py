"""
Responsibility Scope Checker 測試（0.2.1-W3-052.1，C3 移植）

驗證 `responsibility_scope_checker` 能正確依 `where.files` 頂層路徑 domain
分散度判定職責邊界：

- domain 數 <= 2（SSOT 閾值）不觸發
- domain 數 > 2 觸發
- `.claude/` 下取次一層作為 domain（同子系統耦合不誤判）
- ANA / DOC type 豁免
- 換行分隔字串輸入（runtime hook 實際輸入型別）也能正確觸發

`where.files` 的去重/去佔位符/雙型別正規化邏輯已抽至
`ticket_parser.extract_where_files`，對應測試見
`test_ticket_parser_extract_where_files.py`，本檔不重複覆蓋。
"""

import logging
import sys
from pathlib import Path

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.responsibility_scope_checker import (
    check_file_scope_diversity,
    _domain_of,
    _extract_domains,
)


def _logger():
    log = logging.getLogger("test_responsibility_scope_checker")
    log.addHandler(logging.NullHandler())
    return log


class TestDomainOf:
    def test_claude_subdir_takes_second_segment(self):
        assert _domain_of(".claude/hooks/foo.py") == ".claude/hooks"
        assert _domain_of(".claude/pm-rules/bar.md") == ".claude/pm-rules"

    def test_non_claude_takes_top_level(self):
        assert _domain_of("lib/models/foo.dart") == "lib"
        assert _domain_of("test/unit/foo_test.dart") == "test"

    def test_empty_path_returns_empty(self):
        assert _domain_of("") == ""

    def test_leading_dot_slash_prefix_stripped_correctly(self):
        """`str.lstrip("./")` 會把 `.claude` 誤剝成 `claude`（字元集合逐字剝除），
        本測試鎖定該回歸不再發生。"""
        assert _domain_of(".claude/hooks/foo.py") == ".claude/hooks"
        assert _domain_of("./lib/foo.dart") == "lib"


class TestExtractDomains:
    def test_same_claude_subsystem_counts_once(self):
        """同一 .claude 子系統下的 hook + 測試不應被算成兩個 domain"""
        fm = {"where": {"files": [
            ".claude/hooks/foo.py",
            ".claude/hooks/tests/test_foo.py",
        ]}}
        assert _extract_domains(fm, _logger()) == {".claude/hooks"}

    def test_placeholder_and_empty_excluded(self):
        fm = {"where": {"files": ["lib/foo.dart", "待定義", ""]}}
        assert _extract_domains(fm, _logger()) == {"lib"}

    def test_newline_joined_string_input(self):
        """runtime hook 實際輸入型別：`where.files` 為換行字串。"""
        fm = {"where": {"files": ".claude/hooks/foo.py\n.claude/lib/bar.py\n.claude/skills/baz.py"}}
        assert _extract_domains(fm, _logger()) == {".claude/hooks", ".claude/lib", ".claude/skills"}


class TestCheckFileScopeDiversity:
    def test_within_threshold_passes(self):
        fm = {"type": "IMP", "where": {"files": ["lib/foo.dart", "test/foo_test.dart"]}}
        assert check_file_scope_diversity(fm, _logger()) == []

    def test_over_threshold_fails(self):
        fm = {
            "type": "IMP",
            "where": {"files": ["lib/foo.dart", "test/foo_test.dart", "docs/spec/foo.md", "pubspec.yaml"]},
        }
        result = check_file_scope_diversity(fm, _logger())
        assert len(result) == 1
        assert result[0].startswith("domain_count:4>2")

    def test_ana_type_exempt(self):
        fm = {
            "type": "ANA",
            "where": {"files": ["lib/a.dart", "test/b.dart", "docs/c.md", "pubspec.yaml"]},
        }
        assert check_file_scope_diversity(fm, _logger()) == []

    def test_doc_type_exempt(self):
        fm = {
            "type": "DOC",
            "where": {"files": ["lib/a.dart", "test/b.dart", "docs/c.md", "pubspec.yaml"]},
        }
        assert check_file_scope_diversity(fm, _logger()) == []

    def test_no_where_field_passes(self):
        fm = {"type": "IMP"}
        assert check_file_scope_diversity(fm, _logger()) == []

    def test_newline_joined_string_input_still_triggers(self):
        """runtime hook 輸入型別回歸測試（0.2.1-W3-052.1 實測發現的真實回歸：
        本票自身 where.files 在 runtime hook 讀取下為換行字串，
        修復前 domain_count 判定被靜默吞掉為 0，checklist 誤報 [x] 通過）。"""
        fm = {
            "type": "IMP",
            "where": {"files": ".claude/hooks/acceptance_checkers/\n"
                                ".claude/skills/ticket/hooks/acceptance-gate-hook.py\n"
                                ".claude/lib/ticket_quality/detectors.py"},
        }
        result = check_file_scope_diversity(fm, _logger())
        assert len(result) == 1
        assert result[0].startswith("domain_count:3>2")
