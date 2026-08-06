"""
God Ticket Scale Checker 測試（0.2.1-W3-052.1）

驗證 `god_ticket_scale_checker` 能正確依 frontmatter `where.files` 判定規模：

- 檔案數 <= 5（SSOT 閾值）不觸發
- 檔案數 > 5 觸發，回傳含實際數字與閾值的違規字串
- ANA / DOC type 豁免
- `where` 缺失時視為 0 檔案（不觸發）
- 換行分隔字串輸入（runtime hook 實際輸入型別，見
  `test_ticket_parser_extract_where_files.py`）也能正確觸發，
  而非被 `isinstance(files, list)` 靜默吞掉（0.2.1-W3-052.1 實測回歸）

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

from acceptance_checkers.god_ticket_scale_checker import check_god_ticket_scale


def _logger():
    log = logging.getLogger("test_god_ticket_scale_checker")
    log.addHandler(logging.NullHandler())
    return log


class TestCheckGodTicketScale:
    def test_under_threshold_passes(self):
        fm = {"type": "IMP", "where": {"files": [f"file{i}.py" for i in range(5)]}}
        assert check_god_ticket_scale(fm, _logger()) == []

    def test_over_threshold_fails(self):
        fm = {"type": "IMP", "where": {"files": [f"file{i}.py" for i in range(6)]}}
        result = check_god_ticket_scale(fm, _logger())
        assert result == ["file_count:6>5"]

    def test_ana_type_exempt(self):
        fm = {"type": "ANA", "where": {"files": [f"file{i}.py" for i in range(20)]}}
        assert check_god_ticket_scale(fm, _logger()) == []

    def test_doc_type_exempt(self):
        fm = {"type": "DOC", "where": {"files": [f"file{i}.py" for i in range(20)]}}
        assert check_god_ticket_scale(fm, _logger()) == []

    def test_missing_type_still_triggers(self):
        """缺 type frontmatter 視為向後相容仍觸發（沿用 Type-aware Quality Gate 慣例）"""
        fm = {"where": {"files": [f"file{i}.py" for i in range(6)]}}
        result = check_god_ticket_scale(fm, _logger())
        assert result == ["file_count:6>5"]

    def test_no_where_field_passes(self):
        fm = {"type": "IMP"}
        assert check_god_ticket_scale(fm, _logger()) == []

    def test_newline_joined_string_input_still_triggers(self):
        """runtime hook 輸入型別回歸測試：`where.files` 為換行字串
        （非 list）時仍須正確計數並觸發，見 extract_where_files docstring。"""
        files_str = "\n".join(f"file{i}.py" for i in range(6))
        fm = {"type": "IMP", "where": {"files": files_str}}
        result = check_god_ticket_scale(fm, _logger())
        assert result == ["file_count:6>5"]
