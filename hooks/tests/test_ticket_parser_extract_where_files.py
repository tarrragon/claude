"""
ticket_parser.extract_where_files 測試（0.2.1-W3-052.1）

`where.files` 在 frontmatter 中可能是 `list[str]` 或 `str`，兩者皆為 schema
容忍的合法寫法（見 `extract_where_files` docstring）：
- `list[str]`：YAML sequence 寫法（`files:\n  - a.py\n  - b.py`）
- `str`：YAML scalar 寫法——單一路徑不加 dash（`files: a.py`），或 `|`
  block literal scalar（多行路徑）

本測試覆蓋兩種型別皆須正確正規化為 `list[str]`。若呼叫端只用
`isinstance(files, list)` 判斷，會將合法的 scalar 寫法輸入靜默視為空清單
（0.2.1-W3-052.1 實測 runtime hook 輸出時發現的真實回歸）。
"""

import logging
import sys
from pathlib import Path

import yaml

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.ticket_parser import (
    extract_where_files,
    extract_where_files_write_only,
)


def _logger():
    log = logging.getLogger("test_ticket_parser_extract_where_files")
    log.addHandler(logging.NullHandler())
    return log


class TestExtractWhereFilesListInput:
    """list[str] 輸入（完整 YAML 解析器產出）"""

    def test_dedupes_and_strips_placeholders(self):
        fm = {"where": {"files": ["a.py", "a.py", "待定義", "", "  b.py  "]}}
        assert extract_where_files(fm, _logger()) == ["a.py", "b.py"]

    def test_preserves_order(self):
        fm = {"where": {"files": ["c.py", "a.py", "b.py"]}}
        assert extract_where_files(fm, _logger()) == ["c.py", "a.py", "b.py"]


class TestExtractWhereFilesStringInput:
    """換行分隔字串輸入（`files: |` block scalar 等合法 YAML scalar 寫法
    的正規化，見 acceptance-gate-hook.py 實測回歸）"""

    def test_newline_joined_string_normalized_to_list(self):
        fm = {
            "where": {
                "files": ".claude/hooks/acceptance_checkers/\n"
                ".claude/skills/ticket/hooks/acceptance-gate-hook.py\n"
                ".claude/lib/ticket_quality/detectors.py"
            }
        }
        result = extract_where_files(fm, _logger())
        assert result == [
            ".claude/hooks/acceptance_checkers/",
            ".claude/skills/ticket/hooks/acceptance-gate-hook.py",
            ".claude/lib/ticket_quality/detectors.py",
        ]

    def test_string_input_dedupes_and_strips_placeholders(self):
        fm = {"where": {"files": "a.py\na.py\n待定義\n\n  b.py  "}}
        assert extract_where_files(fm, _logger()) == ["a.py", "b.py"]


class TestExtractWhereFilesScalarYamlForms:
    """0.2.1-W3-665.3：str 分支保留判定的固定行為測試。

    `where.files` 純量寫法為合法 YAML（非手寫 parser 缺陷），`yaml.safe_load`
    對下列兩種寫法皆回傳 str，`extract_where_files` 須正確正規化為單元素
    list（W3-665.2 Phase 4 linux 視角實測確認可達，見 ticket Context Bundle
    「更正」節）。本測試以 `yaml.safe_load` 實際解析 YAML 原文，鎖定整條
    「原文 -> 解析 -> 正規化」鏈路的行為，不只測 dict 字面量。
    """

    def test_single_unquoted_scalar_no_dash(self):
        parsed = yaml.safe_load("files: a.py\n")
        assert parsed == {"files": "a.py"}
        fm = {"where": parsed}
        assert extract_where_files(fm, _logger()) == ["a.py"]

    def test_block_literal_scalar_pipe(self):
        parsed = yaml.safe_load("files: |\n  a.py\n  b.py\n")
        assert parsed == {"files": "a.py\nb.py\n"}
        fm = {"where": parsed}
        assert extract_where_files(fm, _logger()) == ["a.py", "b.py"]


class TestExtractWhereFilesEdgeCases:
    def test_missing_where_returns_empty(self):
        assert extract_where_files({}, _logger()) == []

    def test_where_not_dict_returns_empty(self):
        assert extract_where_files({"where": "not-a-dict"}, _logger()) == []

    def test_files_missing_returns_empty(self):
        assert extract_where_files({"where": {}}, _logger()) == []

    def test_files_wrong_type_returns_empty(self):
        assert extract_where_files({"where": {"files": 123}}, _logger()) == []


class TestExtractWhereFilesIntentMarkerStripping:
    """讀寫意圖標記剝離（0.2.1-W3-801）：`extract_where_files` 回傳完整
    影響集（不分讀寫），標記僅供 `extract_where_files_write_only` 判斷。"""

    def test_read_marker_stripped_from_full_set(self):
        fm = {"where": {"files": ["a.py::read", "b.py"]}}
        assert extract_where_files(fm, _logger()) == ["a.py", "b.py"]

    def test_write_marker_stripped_from_full_set(self):
        fm = {"where": {"files": ["a.py::write"]}}
        assert extract_where_files(fm, _logger()) == ["a.py"]

    def test_dedup_after_strip_not_before(self):
        """剝離須置於去重之前：同路徑的 ::read 與 ::write 標記正規化為
        單一路徑，而非兩個相異項（若去重先於剝離會保留兩筆）。"""
        fm = {"where": {"files": ["a.py::read", "a.py::write"]}}
        assert extract_where_files(fm, _logger()) == ["a.py"]

    def test_escaped_marker_preserved_as_literal_path(self):
        fm = {"where": {"files": [r"a.py\::read"]}}
        assert extract_where_files(fm, _logger()) == ["a.py::read"]

    def test_unrecognized_suffix_treated_as_path(self):
        fm = {"where": {"files": ["a.py::readonly"]}}
        assert extract_where_files(fm, _logger()) == ["a.py::readonly"]


class TestExtractWhereFilesWriteOnly:
    """`extract_where_files_write_only`：::read 標記排除於寫入集，未標記
    與 ::write 標記維持既有觸發行為（預設視為寫入）。"""

    def test_read_marked_path_excluded(self):
        fm = {"where": {"files": [".claude/hooks/foo.py::read"]}}
        assert extract_where_files_write_only(fm, _logger()) == []

    def test_unmarked_path_included_by_default(self):
        fm = {"where": {"files": [".claude/hooks/foo.py"]}}
        assert extract_where_files_write_only(fm, _logger()) == [".claude/hooks/foo.py"]

    def test_write_marked_path_included(self):
        fm = {"where": {"files": [".claude/hooks/foo.py::write"]}}
        assert extract_where_files_write_only(fm, _logger()) == [".claude/hooks/foo.py"]

    def test_mixed_read_and_write_paths(self):
        fm = {
            "where": {
                "files": [
                    ".claude/hooks/read_only.py::read",
                    ".claude/hooks/written.py",
                ]
            }
        }
        assert extract_where_files_write_only(fm, _logger()) == [
            ".claude/hooks/written.py"
        ]
