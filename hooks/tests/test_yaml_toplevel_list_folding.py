#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 _parse_yaml_lines 對頂層 block-style 列表項目的 YAML 折行延續行處理
（0.2.1-W3-518）。

背景：pyyaml.dump 預設 width=80，長列表項目（如 CJK 內容約 75+ 字元、或含
ASCII 空白的英文/混合內容）會在項目中間折行，延續行縮排較 dash 深 2 格且
不再以 "- " 開頭。修復前 `_parse_yaml_lines` 對此類延續行無任何累積邏輯，
落入「巢狀鍵值對／多行標記／列表項目」通用分支後被靜默捨棄——單一列表
項目的文字只保留折行前的第一行，第二行起完全遺失且無任何錯誤訊息或例外。

驗證方式：用 `yaml.dump`（與 CLI 內部完整 YAML parser 相同的函式庫）產生
含折行的頂層列表 frontmatter，分別以 `yaml.safe_load`（ground truth）與
`parse_ticket_frontmatter`（本專案輕量解析器）讀取，斷言兩者對列表項目的
文字內容一致（不再於第一個折行處截斷）。
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import parse_ticket_frontmatter


def _wrap(frontmatter_body: str) -> str:
    return "---\n" + frontmatter_body + "\n---\n\n# Body\n"


def _dump_and_parse(data: dict):
    """以 yaml.dump(width=80) 產生 frontmatter 文字，回傳
    (輕量解析器結果, yaml.safe_load ground truth 結果)。"""
    frontmatter_body = yaml.dump(
        data, allow_unicode=True, default_flow_style=False, width=80
    )
    content = _wrap(frontmatter_body.rstrip("\n"))
    lightweight_result = parse_ticket_frontmatter(content)
    ground_truth = yaml.safe_load(frontmatter_body)
    return lightweight_result, ground_truth


class TestTopLevelListFoldingNoIndent:
    """0 縮排頂層列表（`key:\\n- item`）的折行延續行"""

    def test_cjk_long_acceptance_item_not_truncated(self):
        """對應本票 acceptance 條件 1：長 CJK acceptance 項目折行後完整讀回。"""
        long_item = (
            "[ ] 已判定 subagent 早退的正確範圍（完全豁免 vs 僅跳過 "
            "AskUserQuestion），並將結論記錄於 Problem Analysis 或 Solution"
        )
        data = {"id": "0.0.0-W1-001", "acceptance": [long_item, "short one"]}

        lightweight_result, ground_truth = _dump_and_parse(data)

        # 先確認測資本身真的會觸發折行（否則測試對修復無鑑別力）：
        # 折行後 long_item 不會以單一完整行的形式出現在 dump 輸出中。
        dumped = yaml.dump(data, allow_unicode=True, default_flow_style=False, width=80)
        assert "'" + long_item + "'" not in dumped, "測資未觸發預期的 pyyaml 折行，測試前提不成立"

        assert lightweight_result.get("acceptance") == ground_truth["acceptance"]
        assert lightweight_result["acceptance"][0] == long_item

    def test_english_long_item_with_multiple_fold_points(self):
        """英文長句可能觸發多次折行，確認多段延續行都正確併回同一項目。"""
        long_item = (
            "this is a very long english sentence deliberately written to "
            "force pyyaml width eighty folding across multiple continuation "
            "lines so the fix must join every single one back correctly"
        )
        data = {"id": "0.0.0-W1-002", "children": [long_item, "0.0.0-W1-002.1"]}

        lightweight_result, ground_truth = _dump_and_parse(data)

        assert lightweight_result.get("children") == ground_truth["children"]
        assert lightweight_result["children"][0] == long_item

    def test_multiple_long_items_each_fold_independently(self):
        """多個長項目各自折行時，延續行必須併回「最後一個」列表項目，不可錯位。"""
        item_a = "第一個很長的驗收條件用來測試折行後延續行是否正確累積回這個項目而不是下一個"
        item_b = "第二個同樣很長的驗收條件也要測試折行延續行是否正確累積回它自己而非前一個項目"
        data = {"id": "0.0.0-W1-003", "acceptance": [item_a, item_b]}

        lightweight_result, ground_truth = _dump_and_parse(data)

        assert lightweight_result.get("acceptance") == ground_truth["acceptance"]

    def test_short_items_unaffected(self):
        """短列表項目（不觸發折行）行為不變，確認修復未引入回歸。"""
        data = {"id": "0.0.0-W1-004", "children": ["a", "b", "c"]}

        lightweight_result, ground_truth = _dump_and_parse(data)

        assert lightweight_result.get("children") == ground_truth["children"]


class TestTopLevelListFolding2SpaceIndent:
    """2 縮排頂層列表（`key:\\n  - item`）的折行延續行"""

    def test_2space_indent_long_item_not_truncated(self):
        content = _wrap(
            "id: 0.0.0-W1-005\n"
            "children:\n"
            "  - this is a very long english sentence used to force pyyaml width\n"
            "    eighty folding behavior for the 2-space indent list variant\n"
            "  - short-item"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("children") == [
            "this is a very long english sentence used to force pyyaml width "
            "eighty folding behavior for the 2-space indent list variant",
            "short-item",
        ]


class TestFoldingDoesNotBreakExistingNestedDictParsing:
    """折行延續行判定（current_nested_key is None + list 累積中）不可誤傷既有巢狀 dict 解析。"""

    def test_list_followed_by_nested_dict_still_parses(self):
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children:\n"
            "- 0.1.0-W1-001.1\n"
            "who:\n"
            "  current: thyme-python-developer\n"
            "status: in_progress"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("children") == ["0.1.0-W1-001.1"]
        assert isinstance(result.get("who"), dict)
        assert result["who"].get("current") == "thyme-python-developer"
        assert result.get("status") == "in_progress"

    def test_where_files_nested_list_parses_as_real_list(self):
        """where.files（巢狀於 2 縮排 key 下的列表）由 yaml.safe_load 解析為
        真正的 list（0.2.1-W3-665.2 遷移後：舊 parser 時代的 `\\n` 字串
        累積行為已解除，見 test_scalar_continuation_colon_fix.py 同案例）。"""
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "where:\n"
            "  layer: 待定義\n"
            "  files:\n"
            "  - a.py\n"
            "  - b.py"
        )
        result = parse_ticket_frontmatter(content)
        assert isinstance(result.get("where"), dict)
        files_value = result["where"].get("files", [])
        assert files_value == ["a.py", "b.py"]
