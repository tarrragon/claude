#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_ticket_frontmatter 的 10 案例 YAML 折行/型別回歸矩陣。

背景：手寫逐行 parser 時代，`yaml.dump`（建立端，width 預設 80）折行寫入
frontmatter 時，手寫 parser（消費端）解析同一檔案在 10 案例矩陣中 9 個
MISMATCH（值錯而非拋錯——parser 不進例外路徑，多數情況連 warning 都沒有）。
本檔將該分析用矩陣正式落地為回歸測試，防止未來任何解析器變更再度引入同類
MISMATCH。matrix 產生方式與原分析一致：
`yaml.dump(allow_unicode=True, default_flow_style=False, sort_keys=False)`，
折行觸發：欄位值以多個詞組成、總長度超過 pyyaml.dump 預設 width=80 且斷點
處有空白。

每案例斷言 `parse_ticket_frontmatter(建立端 yaml.dump 輸出)` 與
`yaml.safe_load(同一輸出)`（ground truth）完全一致——parse_ticket_frontmatter
遷移為 `yaml.safe_load` 後兩者理應恆等，此矩陣即為該恆等式的回歸保護。
"""

import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import parse_ticket_frontmatter


def _dump_and_parse(data: dict):
    """以 yaml.dump(width=80) 產生 frontmatter 文字，回傳
    (parse_ticket_frontmatter 結果, yaml.safe_load ground truth 結果, dumped 文字)。
    """
    frontmatter_body = yaml.dump(
        data, allow_unicode=True, default_flow_style=False, sort_keys=False, width=80
    )
    content = "---\n" + frontmatter_body.rstrip("\n") + "\n---\n\n# Body\n"
    lightweight_result = parse_ticket_frontmatter(content)
    ground_truth = yaml.safe_load(frontmatter_body)
    return lightweight_result, ground_truth, frontmatter_body


def _long_words(n: int, prefix: str = "word") -> str:
    """產生 n 個以空白分隔的詞，確保總長度超過 width=80 觸發折行。"""
    return " ".join(f"{prefix}{i:02d}" for i in range(n))


class TestTopScalarFolded:
    """案例 1：top_scalar_folded（頂層純量欄位，如 why，觸發折行）"""

    def test_why_field_folds_and_round_trips(self):
        data = {"id": "0.0.0-W1-001", "why": _long_words(20)}
        lightweight_result, ground_truth, dumped = _dump_and_parse(data)

        # 先確認測資本身真的觸發折行（否則測試對回歸無鑑別力）
        assert "\n  " in dumped, "測資未觸發預期的 pyyaml 折行，測試前提不成立"
        assert lightweight_result == ground_truth
        assert lightweight_result["why"] == data["why"]


class TestTopScalarFoldedColon:
    """案例 2：top_scalar_folded_colon（延續行含冒號，如 "reason:"，
    W3-338 防護對象：不得誤判為巢狀鍵）"""

    def test_continuation_line_with_colon_not_misjudged_as_nested_key(self):
        value = _long_words(15) + " reason: not-a-nested-key " + _long_words(10)
        data = {"id": "0.0.0-W1-002", "why": value}
        lightweight_result, ground_truth, dumped = _dump_and_parse(data)

        assert "\n  " in dumped, "測資未觸發預期的 pyyaml 折行，測試前提不成立"
        assert lightweight_result == ground_truth
        assert isinstance(lightweight_result["why"], str)
        assert "reason:" in lightweight_result["why"]


class TestTopScalarFoldedDash:
    """案例 3：top_scalar_folded_dash（延續行含 " - "，不得誤判為列表項）"""

    def test_continuation_line_with_dash_not_misjudged_as_list_item(self):
        value = _long_words(15) + " - not-a-list-item - " + _long_words(10)
        data = {"id": "0.0.0-W1-003", "why": value}
        lightweight_result, ground_truth, dumped = _dump_and_parse(data)

        assert "\n  " in dumped, "測資未觸發預期的 pyyaml 折行，測試前提不成立"
        assert lightweight_result == ground_truth
        assert isinstance(lightweight_result["why"], str)
        assert lightweight_result["why"] == value


class TestNestedScalarFolded:
    """案例 4：nested_scalar_folded（巢狀純量欄位，如 how.strategy，觸發折行）"""

    def test_how_strategy_folds_and_round_trips(self):
        data = {
            "id": "0.0.0-W1-004",
            "how": {"task_type": "Implementation", "strategy": _long_words(20)},
        }
        lightweight_result, ground_truth, dumped = _dump_and_parse(data)

        assert "\n    " in dumped, "測資未觸發預期的 pyyaml 折行，測試前提不成立"
        assert lightweight_result == ground_truth
        assert lightweight_result["how"]["strategy"] == data["how"]["strategy"]


class TestNestedScalarFoldedColon:
    """案例 5：nested_scalar_folded_colon（巢狀純量延續行含冒號）"""

    def test_nested_continuation_line_with_colon(self):
        value = _long_words(15) + " note: not-a-nested-key " + _long_words(10)
        data = {
            "id": "0.0.0-W1-005",
            "how": {"task_type": "Implementation", "strategy": value},
        }
        lightweight_result, ground_truth, dumped = _dump_and_parse(data)

        assert "\n    " in dumped, "測資未觸發預期的 pyyaml 折行，測試前提不成立"
        assert lightweight_result == ground_truth
        assert lightweight_result["how"]["strategy"] == value
        assert lightweight_result["how"]["task_type"] == "Implementation"


class TestToplevelListFolded:
    """案例 6：toplevel_list_folded（頂層列表項目折行，如 acceptance——
    W3-338 已修復對象，本矩陣確認 yaml.safe_load 遷移後仍為 OK）"""

    def test_acceptance_item_folds_and_round_trips(self):
        data = {"id": "0.0.0-W1-006", "acceptance": [_long_words(20), "short one"]}
        lightweight_result, ground_truth, dumped = _dump_and_parse(data)

        assert "\n  " in dumped, "測資未觸發預期的 pyyaml 折行，測試前提不成立"
        assert lightweight_result == ground_truth
        assert lightweight_result["acceptance"][0] == data["acceptance"][0]


class TestNestedListMulti:
    """案例 7：nested_list_multi（巢狀列表兩項，如 where.files——
    舊 parser MISMATCH：list → 'a.py\\nb.py' 字串，yaml.safe_load 還原為真正 list）"""

    def test_where_files_two_items_stays_list(self):
        data = {
            "id": "0.0.0-W1-007",
            "where": {"layer": "hooks", "files": ["a.py", "b.py"]},
        }
        lightweight_result, ground_truth, _dumped = _dump_and_parse(data)

        assert lightweight_result == ground_truth
        assert lightweight_result["where"]["files"] == ["a.py", "b.py"]
        assert isinstance(lightweight_result["where"]["files"], list)


class TestNestedListFolded:
    """案例 8：nested_list_folded（巢狀列表單項折行，如 where.files 單一長
    路徑——舊 parser MISMATCH：list → 字串且內含 \\n）"""

    def test_where_files_single_long_item_folds_and_stays_list(self):
        # 折行只在斷點處有空白時觸發（YAML plain/quoted scalar 折行規則），
        # 純路徑（無空白）即使很長也不會折行，故用詞組模擬真實長驗收條件。
        long_item = _long_words(20, prefix="very-long-path-segment-")
        data = {
            "id": "0.0.0-W1-008",
            "where": {"files": [long_item]},
        }
        lightweight_result, ground_truth, dumped = _dump_and_parse(data)

        assert "\n    " in dumped, "測資未觸發預期的 pyyaml 折行，測試前提不成立"
        assert lightweight_result == ground_truth
        assert lightweight_result["where"]["files"] == [long_item]
        assert isinstance(lightweight_result["where"]["files"], list)


class TestEmptyMap:
    """案例 9：empty_map（who.history: {}——舊 parser MISMATCH：
    {} → '{}' 字串，yaml.safe_load 還原為真正的空 dict）"""

    def test_who_history_empty_dict_stays_dict(self):
        data = {
            "id": "0.0.0-W1-009",
            "who": {"current": "thyme-python-developer", "history": {}},
        }
        lightweight_result, ground_truth, _dumped = _dump_and_parse(data)

        assert lightweight_result == ground_truth
        assert lightweight_result["who"]["history"] == {}
        assert isinstance(lightweight_result["who"]["history"], dict)


class TestBoolNullInt:
    """案例 10：bool_null_int（True/None/3——舊 parser MISMATCH：
    一律轉字串 'true'/'null'/'3'，yaml.safe_load 保留原生型別）"""

    def test_bool_null_int_preserve_native_types(self):
        data = {
            "id": "0.0.0-W1-010",
            "assigned": True,
            "completed_at": None,
            "wave": 3,
        }
        lightweight_result, ground_truth, _dumped = _dump_and_parse(data)

        assert lightweight_result == ground_truth
        assert lightweight_result["assigned"] is True
        assert lightweight_result["completed_at"] is None
        assert lightweight_result["wave"] == 3
        assert isinstance(lightweight_result["wave"], int)


class TestFailSafeOnInvalidYaml:
    """公開契約：解析失敗（真正的 YAML 語法錯誤，非折行/型別差異）回空 dict
    並記錄 warning，不拋例外中斷呼叫端。舊 parser 因手寫逐行處理幾乎不會
    進此例外路徑（折行不觸發例外，值錯而非拋錯）；yaml.safe_load 換用
    真正的 YAML parser 後，此路徑首次被實質行使，須有測試覆蓋。"""

    def test_invalid_yaml_syntax_returns_empty_dict_with_warning(self, caplog):
        logger = logging.getLogger("test-hook-ticket-fail-safe")

        # 真正的 YAML 語法錯誤：flow-style 序列未閉合中括號
        content = "---\nid: 0.0.0-W1-999\nchildren: [a, b\nstatus: pending\n---\n"

        with caplog.at_level(logging.WARNING, logger="test-hook-ticket-fail-safe"):
            result = parse_ticket_frontmatter(content, logger)

        assert result == {}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, "解析失敗應記錄恰一則 warning"
        assert "解析 frontmatter 失敗" in warnings[0].getMessage()

    def test_non_dict_top_level_returns_empty_dict_with_warning(self, caplog):
        """頂層為純量或 list（非 dict）視為解析失敗，同樣 fail-safe。"""
        logger = logging.getLogger("test-hook-ticket-fail-safe-nondict")

        # 頂層為純量字串（非 mapping）
        content = "---\njust a plain scalar\n---\n"

        with caplog.at_level(logging.WARNING, logger="test-hook-ticket-fail-safe-nondict"):
            result = parse_ticket_frontmatter(content, logger)

        assert result == {}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "非 dict" in warnings[0].getMessage()

    def test_non_yaml_error_exception_is_caught_and_returns_empty_dict(self, caplog):
        """F1：非 YAMLError 的例外（如深度巢狀 flow 觸發 RecursionError）亦須
        被 fail-safe 契約涵蓋，不得逸出中斷呼叫端（docstring 明文承諾）。"""
        logger = logging.getLogger("test-hook-ticket-fail-safe-recursion")

        # 深度巢狀 flow-style 序列觸發 PyYAML 內部 RecursionError（非 YAMLError）
        depth = 5000
        content = "---\nk: " + "[" * depth + "]" * depth + "\n---\nbody\n"

        with caplog.at_level(logging.WARNING, logger="test-hook-ticket-fail-safe-recursion"):
            result = parse_ticket_frontmatter(content, logger)

        assert result == {}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, "非 YAMLError 逸出亦應記錄恰一則 warning"
        assert "解析 frontmatter 失敗" in warnings[0].getMessage()
