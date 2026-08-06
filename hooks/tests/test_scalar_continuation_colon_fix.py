#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 0.2.1-W3-338 修復：多行純量延續行含冒號誤判為巢狀 dict 的資料遺失

背景：`_parse_yaml_lines` 的巢狀鍵值對判定（`_parse_nested_line` 路徑 3）對
2 空白縮排行只要含 ASCII 冒號即判定為新巢狀鍵值對，未區分「累積中的多行純量
延續行」與「真正的巢狀鍵值對」。多行純量欄位（如 `why:`，無 `|`/`>` 標記，
靠 YAML plain scalar folding 換行）若延續行含冒號（常見：中文技術寫作「根因是
X：Y」句型、或內文提及時間戳如 14:52），會被誤判為巢狀 dict 並覆蓋已累積內容，
造成資料遺失（0.2.1-W3-330 稽核發現：既有票 9.5% 命中，`0.2.1-W3-189.md` 為
具體案例）。

修復：新增路徑 2.5，呼叫端（`_parse_yaml_lines`）判定 `current_key` 目前是否
已累積「非空字串」（代表正在跨行折疊純量），是則優先視為純量延續行，不論
是否含冒號。

驗證維度：
1. 單元層：`_parse_nested_line` 新參數 `is_scalar_continuation` 正確分流
2. 整合層：多行純量延續行含冒號能正確還原完整字串（含非首行冒號、
   連續多個冒號、行首行尾冒號等邊界）
3. 迴歸層：既有巢狀 dict 欄位（who/decision_tree_path/how，含多鍵累積）
   行為完全不變
4. 全語料層：對修復前 43 個已知受損案例逐一重新解析，確認 100% 還原為字串
   （見 Test Results 章節的獨立驗證腳本輸出）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import parse_ticket_frontmatter
from lib.hook_ticket import _parse_nested_line, _NestedLineResult


def _wrap(frontmatter_body: str) -> str:
    return "---\n" + frontmatter_body + "\n---\n\n# Body\n"


# ----------------------------------------------------------------------------
# 單元層：_parse_nested_line 新參數分流
# ----------------------------------------------------------------------------


class TestParseNestedLineScalarContinuation:
    def test_is_scalar_continuation_true_with_colon_routes_to_scalar(self):
        """is_scalar_continuation=True 時，含冒號的行不得判為巢狀 dict"""
        result = _parse_nested_line(
            line="  實證代價：0.2.1-W3-181 於 14:52 改 SKILLS 常數",
            current_key="why",
            multiline_marker=None,
            current_nested_key=None,
            is_scalar_continuation=True,
        )
        assert isinstance(result, _NestedLineResult)
        key, value, is_nested_dict = result.update_action
        assert key == "why"
        assert value == "實證代價：0.2.1-W3-181 於 14:52 改 SKILLS 常數"
        assert is_nested_dict is False

    def test_is_scalar_continuation_true_without_colon_also_routes_to_scalar(self):
        """is_scalar_continuation=True 時，無冒號的行同樣視為延續內容
        （修復前此類行會被完全丟棄，見 docstring 說明）"""
        result = _parse_nested_line(
            line="  沒有冒號的延續行",
            current_key="why",
            multiline_marker=None,
            current_nested_key=None,
            is_scalar_continuation=True,
        )
        key, value, is_nested_dict = result.update_action
        assert key == "why"
        assert value == "沒有冒號的延續行"
        assert is_nested_dict is False

    def test_is_scalar_continuation_false_with_colon_still_nested_dict(self):
        """is_scalar_continuation=False（預設，既有行為）時，含冒號的行仍
        判為巢狀鍵值對——確保修復不影響既有巢狀 dict 解析"""
        result = _parse_nested_line(
            line="  author: John Doe",
            current_key="metadata",
            multiline_marker=None,
        )
        key, value, is_nested_dict = result.update_action
        assert key == "metadata"
        assert value == {"author": "John Doe"}
        assert is_nested_dict is True

    def test_is_scalar_continuation_default_preserves_backward_compatibility(self):
        """未傳入 is_scalar_continuation 時預設 False，既有直接呼叫端
        （如既有單元測試）行為完全不變"""
        result = _parse_nested_line(
            line="  priority: high",
            current_key="metadata",
            multiline_marker=None,
        )
        assert result.update_action == ("metadata", {"priority": "high"}, True)


# ----------------------------------------------------------------------------
# 整合層：parse_ticket_frontmatter 端到端還原
# ----------------------------------------------------------------------------


class TestMultilineScalarWithColonIntegration:
    def test_why_field_with_time_reference_colon_fully_restored(self):
        """0.2.1-W3-189.md 損毀樣態的最小重現：why 跨行且延續行含時間戳冒號"""
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "why: 第一行說明文字\n"
            "  第二行提及時間 14:52 發生的事件\n"
            "  第三行沒有冒號的延續\n"
            "how:\n"
            "  task_type: Implementation"
        )
        result = parse_ticket_frontmatter(content)
        assert isinstance(result["why"], str)
        assert "第一行說明文字" in result["why"]
        assert "第二行提及時間 14:52 發生的事件" in result["why"]
        assert "第三行沒有冒號的延續" in result["why"]
        # 巢狀 dict 欄位（how）不受影響
        assert isinstance(result["how"], dict)
        assert result["how"]["task_type"] == "Implementation"

    def test_multiple_colon_containing_continuation_lines(self):
        """多個延續行皆含冒號，全部應保留在同一字串內"""
        content = _wrap(
            "id: 0.1.0-W1-002\n"
            "why: 根因是 A：B 造成的\n"
            "  延伸說明：C：D 也有影響\n"
            "  最後一行：結論"
        )
        result = parse_ticket_frontmatter(content)
        why = result["why"]
        assert isinstance(why, str)
        assert "根因是 A：B 造成的" in why
        assert "延伸說明：C：D 也有影響" in why
        assert "最後一行：結論" in why

    def test_narrative_field_without_colon_still_works(self):
        """無冒號的多行純量（既有能運作的案例）修復後行為不變"""
        content = _wrap(
            "id: 0.1.0-W1-003\n"
            "why: 第一行\n"
            "  第二行\n"
            "  第三行"
        )
        result = parse_ticket_frontmatter(content)
        assert result["why"] == "第一行\n第二行\n第三行"

    def test_full_width_colon_in_continuation_also_preserved(self):
        """全形冒號（：）本身不觸發 ASCII 冒號判定路徑，理應一直安全；
        納入測試矩陣確認修復未改變此既有安全案例"""
        content = _wrap(
            "id: 0.1.0-W1-004\n"
            "why: 說明文字\n"
            "  純全形冒號：無 ASCII 冒號"
        )
        result = parse_ticket_frontmatter(content)
        assert result["why"] == "說明文字\n純全形冒號：無 ASCII 冒號"


# ----------------------------------------------------------------------------
# 迴歸層：既有巢狀 dict 欄位不受影響（acceptance 第 2 條）
# ----------------------------------------------------------------------------


class TestExistingNestedDictFieldsUnaffected:
    def test_who_with_current_and_history(self):
        content = _wrap(
            "id: 0.1.0-W1-005\n"
            "who:\n"
            "  current: thyme-python-developer\n"
            "  history: {}\n"
            "status: in_progress"
        )
        result = parse_ticket_frontmatter(content)
        assert isinstance(result["who"], dict)
        assert result["who"]["current"] == "thyme-python-developer"
        assert result["who"]["history"] == "{}"
        assert result["status"] == "in_progress"

    def test_decision_tree_path_three_keys(self):
        content = _wrap(
            "id: 0.1.0-W1-006\n"
            "decision_tree_path:\n"
            "  entry_point: 第五層:TDD\n"
            "  final_decision: 採方案 D\n"
            "  rationale: PC-MON-001"
        )
        result = parse_ticket_frontmatter(content)
        dtp = result["decision_tree_path"]
        assert isinstance(dtp, dict)
        # entry_point 值本身含冒號（"第五層:TDD"）—— 這是巢狀鍵值對的合法值，
        # 非本票修復對象（該值本身在單行內即完整给出，非跨行純量延續）
        assert dtp["entry_point"] == "第五層:TDD"
        assert dtp["final_decision"] == "採方案 D"
        assert dtp["rationale"] == "PC-MON-001"

    def test_how_with_task_type_and_strategy(self):
        content = _wrap(
            "id: 0.1.0-W1-007\n"
            "how:\n"
            "  task_type: Implementation\n"
            "  strategy: 修正解析器"
        )
        result = parse_ticket_frontmatter(content)
        assert result["how"]["task_type"] == "Implementation"
        assert result["how"]["strategy"] == "修正解析器"

    def test_where_layer_and_files_list(self):
        """where.files 巢狀列表（0.2.1-W3-052.1 既有修復對象）不受本次變更影響"""
        content = _wrap(
            "id: 0.1.0-W1-008\n"
            "where:\n"
            "  layer: 待定義\n"
            "  files:\n"
            "  - a.py\n"
            "  - b.py"
        )
        result = parse_ticket_frontmatter(content)
        assert result["where"]["layer"] == "待定義"
        files = result["where"]["files"]
        assert isinstance(files, str)  # 既有已知限制，非本票範圍
        assert "a.py" in files and "b.py" in files

    def test_nested_dict_followed_by_scalar_with_colon(self):
        """巢狀 dict 欄位後緊接一個含冒號延續行的純量欄位，確認狀態切換正確
        （current_nested_key 於新頂層鍵時應正確重設，不互相污染）"""
        content = _wrap(
            "id: 0.1.0-W1-009\n"
            "who:\n"
            "  current: thyme\n"
            "why: 說明文字\n"
            "  含冒號的延續：內容"
        )
        result = parse_ticket_frontmatter(content)
        assert result["who"]["current"] == "thyme"
        assert result["why"] == "說明文字\n含冒號的延續：內容"
