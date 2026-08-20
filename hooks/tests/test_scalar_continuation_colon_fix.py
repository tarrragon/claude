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

修復（W3-338，手寫 parser 時代）：新增路徑 2.5，呼叫端（`_parse_yaml_lines`）
判定 `current_key` 目前是否已累積「非空字串」（代表正在跨行折疊純量），是則
優先視為純量延續行，不論是否含冒號。該手寫 parser 已隨
`parse_ticket_frontmatter` 遷移至 `yaml.safe_load` 而退役；本檔原「單元層」
的 `TestParseNestedLineScalarContinuation`（直接測試已刪除的
`_parse_nested_line` 內部函式）一併移除——其守護的行為（冒號續行不誤判為
巢狀鍵）已由下方整合層測試對公開 API `parse_ticket_frontmatter` 的斷言涵蓋，
且該行為在 yaml.safe_load 下依 YAML 規範原生成立（冒號僅在後接空白時才是
mapping 分隔符）。

驗證維度：
1. 整合層：多行純量延續行含冒號能正確還原完整字串（含非首行冒號、
   連續多個冒號、行首行尾冒號等邊界）
2. 迴歸層：既有巢狀 dict 欄位（who/decision_tree_path/how，含多鍵累積）
   行為完全不變

註：yaml.safe_load 對多行 plain scalar 的折行語意是「換行 → 空白」
（YAML 規範原生行為），與手寫 parser 時代的「換行 → `\\n`」不同；下方測試
對完整還原的斷言已依此更新為空白併接。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import parse_ticket_frontmatter


def _wrap(frontmatter_body: str) -> str:
    return "---\n" + frontmatter_body + "\n---\n\n# Body\n"


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
        """無冒號的多行純量（既有能運作的案例）行為不變

        yaml.safe_load 對 plain scalar 折行採「換行 → 空白」（YAML 規範
        原生語意），非手寫 parser 時代的 `\\n` 併接。
        """
        content = _wrap(
            "id: 0.1.0-W1-003\n"
            "why: 第一行\n"
            "  第二行\n"
            "  第三行"
        )
        result = parse_ticket_frontmatter(content)
        assert result["why"] == "第一行 第二行 第三行"

    def test_full_width_colon_in_continuation_also_preserved(self):
        """全形冒號（：）本身不觸發 ASCII 冒號判定路徑，理應一直安全；
        納入測試矩陣確認修復未改變此既有安全案例（空白併接，見上方說明）"""
        content = _wrap(
            "id: 0.1.0-W1-004\n"
            "why: 說明文字\n"
            "  純全形冒號：無 ASCII 冒號"
        )
        result = parse_ticket_frontmatter(content)
        assert result["why"] == "說明文字 純全形冒號：無 ASCII 冒號"


# ----------------------------------------------------------------------------
# 迴歸層：既有巢狀 dict 欄位不受影響（acceptance 第 2 條）
# ----------------------------------------------------------------------------


class TestExistingNestedDictFieldsUnaffected:
    def test_who_with_current_and_history(self):
        """`history: {}`（flow-style 空 dict）由 yaml.safe_load 正確還原為
        真正的空 dict（W3-645 矩陣 `empty_map` 案例的 MISMATCH 修復對象，
        舊 parser 誤轉為字串 `'{}'`）。"""
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
        assert result["who"]["history"] == {}
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
        """where.files 巢狀列表由 yaml.safe_load 正確還原為真正的 list
        （舊 parser 的字串併接為已知限制，本票遷移後解除）"""
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
        assert isinstance(files, list)
        assert files == ["a.py", "b.py"]

    def test_nested_dict_followed_by_scalar_with_colon(self):
        """巢狀 dict 欄位後緊接一個含冒號延續行的純量欄位，確認狀態切換正確
        （yaml.safe_load 原生依縮排區分巢狀 dict 與頂層純量延續，空白併接）"""
        content = _wrap(
            "id: 0.1.0-W1-009\n"
            "who:\n"
            "  current: thyme\n"
            "why: 說明文字\n"
            "  含冒號的延續：內容"
        )
        result = parse_ticket_frontmatter(content)
        assert result["who"]["current"] == "thyme"
        assert result["why"] == "說明文字 含冒號的延續：內容"
