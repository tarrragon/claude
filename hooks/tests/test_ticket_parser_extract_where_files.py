"""
ticket_parser.extract_where_files 測試（0.2.1-W3-052.1）

`where.files` 在不同解析器下呈現型別不同（見 `extract_where_files` docstring）：
- `list[str]`：完整 YAML 解析（如 `ticket track` CLI）
- 換行分隔字串：`acceptance-gate-hook.py` 實際使用的
  `lib.hook_ticket.parse_ticket_frontmatter`（對 dict 內巢狀 block-style
  列表的已知限制）

本測試覆蓋兩種型別皆須正確正規化為 `list[str]`，這是 0.2.1-W3-052.1 實測
runtime hook 輸出時發現的真實回歸（新 checker 對真實 ticket 檔案永遠不觸發，
因為 `isinstance(files, list)` 對字串型別回傳 False）。
"""

import logging
import sys
from pathlib import Path

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.ticket_parser import extract_where_files


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
    """換行分隔字串輸入（本 hook 套件輕量解析器 `parse_ticket_frontmatter`
    對 dict 內巢狀列表的已知限制，見 acceptance-gate-hook.py 實測回歸）"""

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


class TestExtractWhereFilesEdgeCases:
    def test_missing_where_returns_empty(self):
        assert extract_where_files({}, _logger()) == []

    def test_where_not_dict_returns_empty(self):
        assert extract_where_files({"where": "not-a-dict"}, _logger()) == []

    def test_files_missing_returns_empty(self):
        assert extract_where_files({"where": {}}, _logger()) == []

    def test_files_wrong_type_returns_empty(self):
        assert extract_where_files({"where": {"files": 123}}, _logger()) == []
