#!/usr/bin/env python3
"""
AskUserQuestion Charset Guard Hook - 測試（W13-003 / W14-007）

驗證 SIMPLIFIED_CHARS / EMOJI_RANGES / JAPANESE_ONLY 偵測邏輯：
- W13-003：「隶」(U+96B6) 與「遗」(U+9057) 納入 SIMPLIFIED_CHARS
- W14-007：PC-084 17 字日文新字體專屬漢字偵測（読/訳/駅/両/発/図/広/実/気/楽/
  観/検/権/売/関/鉄/転）+ SIMPLIFIED_CHARS 清理 U+4F53（繁中異體字誤列）
"""

import importlib.util
import json as _json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HOOK_DIR))

_spec = importlib.util.spec_from_file_location(
    "askuserquestion_charset_guard_hook",
    HOOK_DIR / "askuserquestion-charset-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

find_violations = hook_module.find_violations
scan_payload = hook_module.scan_payload
SIMPLIFIED_CHARS = hook_module.SIMPLIFIED_CHARS
# W14-007 Phase 3b 落地於 hook；直接屬性存取，AttributeError 即為回歸訊號
JAPANESE_ONLY = hook_module.JAPANESE_ONLY
BLOCK_MESSAGE_TEMPLATE = hook_module.BLOCK_MESSAGE_TEMPLATE


# ============================================================================
# SIMPLIFIED_CHARS 清單（W13-003 新增字元 + 既有回歸）
# ============================================================================


class TestSimplifiedCharsMembership:
    """驗證 SIMPLIFIED_CHARS frozenset 含關鍵字元。"""

    def test_w13_003_new_chars_included(self):
        """W13-003 補強：『隶』『遗』必須在清單。"""
        assert "\u96b6" in SIMPLIFIED_CHARS, "隶 (U+96B6) 應在 SIMPLIFIED_CHARS"
        assert "\u9057" in SIMPLIFIED_CHARS, "遗 (U+9057) 應在 SIMPLIFIED_CHARS"

    def test_existing_chars_preserved(self):
        """回歸：既有常見簡體字『独/违/决』仍在清單。"""
        for ch in ("独", "违", "决", "关", "为", "与"):
            assert ch in SIMPLIFIED_CHARS, f"{ch} 應保留在 SIMPLIFIED_CHARS"

    def test_traditional_counterparts_not_in_list(self):
        """邊界：對應繁體『隸』『遺』『獨』『違』不可在清單。"""
        for ch in ("\u96b8", "\u907a", "獨", "違", "決"):
            assert ch not in SIMPLIFIED_CHARS, f"繁體 {ch} 不應在 SIMPLIFIED_CHARS"

    def test_simplified_chars_excludes_pc084_forbidden(self):
        """W14-007 F8：SIMPLIFIED_CHARS 不得含 PC-074/084 禁入字（繁日共用 / 繁中異體）。"""
        forbidden = (
            ("\u9451", "U+9451 繁日共用字（PC-084 首發案例）"),
            ("\u4f53", "U+4F53 繁中異體字（PC-084 首發 false positive）"),
            ("\u8a89", "U+8A89 繁中異體字（PC-084 保守不入）"),
            ("\u8c4a", "U+8C4A 繁中異體字（PC-084 保守不入）"),
            ("\u62dd", "U+62DD 繁中異體字（PC-084 保守不入）"),
        )
        for ch, reason in forbidden:
            assert ch not in SIMPLIFIED_CHARS, (
                f"{ch} ({reason}) 違反 PC-084 禁入，應從 SIMPLIFIED_CHARS 移除"
            )


# ============================================================================
# find_violations 行為驗證
# ============================================================================


class TestFindViolations:
    """驗證 find_violations 正確標記污染位置與類別。"""

    def test_pure_traditional_passes(self):
        """純繁體文字無違規。"""
        text = "建立獨立的隸屬關係，遺留項目已處理"
        violations = find_violations(text, "test.field")
        assert violations == []

    def test_detects_li_simplified(self):
        """含『隶』觸發違規，類別為簡體字。"""
        text = "F 案外移\u96b6\u5c6c Skill Market"  # 隶屬
        violations = find_violations(text, "test.field")
        codes = [v[2] for v in violations]
        assert 0x96B6 in codes, "應標記 U+96B6"
        categories = {v[3] for v in violations}
        assert "簡體字" in categories

    def test_detects_yi_simplified(self):
        """含『遗』觸發違規。"""
        text = "test mode 權限變更\u9057\u7559"  # 遗留
        violations = find_violations(text, "test.field")
        codes = [v[2] for v in violations]
        assert 0x9057 in codes, "應標記 U+9057"

    def test_detects_existing_simplified(self):
        """回歸：既有『独/违/决』仍觸發違規。"""
        text = "独立执行决策违反规则"
        violations = find_violations(text, "test.field")
        simplified_codes = [v[2] for v in violations if v[3] == "簡體字"]
        assert 0x72EC in simplified_codes  # 独
        assert 0x51B3 in simplified_codes  # 决
        assert 0x8FDD in simplified_codes  # 违

    def test_detects_emoji_ranges(self):
        """回歸：Emoji 範圍仍攔截。"""
        text = "進度 ⚡ 完成 ✅"
        violations = find_violations(text, "test.field")
        emoji_codes = [v[2] for v in violations if v[3] == "emoji"]
        assert 0x26A1 in emoji_codes  # ⚡
        assert 0x2705 in emoji_codes  # ✅

    def test_field_path_recorded(self):
        """field_path 正確標記在結果中。"""
        violations = find_violations("隶", "questions[0].options[1].description")
        assert violations
        assert violations[0][0] == "questions[0].options[1].description"


# ============================================================================
# scan_payload 整合驗證（AUQ 結構）
# ============================================================================


class TestScanPayload:
    """驗證 scan_payload 對 questions 陣列各層欄位的掃描覆蓋。"""

    def test_clean_payload_passes(self):
        """純繁體 + 無 emoji payload 無違規。"""
        questions = [
            {
                "question": "選擇下一步方案？",
                "header": "方案選擇",
                "options": [
                    {"label": "繼續執行", "description": "維持現狀"},
                    {"label": "切換目標", "description": "改做別的"},
                ],
            }
        ]
        assert scan_payload(questions) == []

    def test_detects_simplified_in_description(self):
        """W13-003 實證：description 含『隶屬』被攔截。"""
        questions = [
            {
                "question": "歸屬確認？",
                "header": "歸屬",
                "options": [
                    {"label": "A 方案", "description": "F 案隶屬 Skill Market"},
                    {"label": "B 方案", "description": "遗留物處理"},
                ],
            }
        ]
        violations = scan_payload(questions)
        codes = [v[2] for v in violations]
        assert 0x96B6 in codes  # 隶
        assert 0x9057 in codes  # 遗

    def test_detects_across_all_fields(self):
        """question / header / label / description 各欄位都被掃描。"""
        questions = [
            {
                "question": "独立問題",
                "header": "违反",
                "options": [
                    {"label": "决策", "description": "简单"},
                ],
            }
        ]
        violations = scan_payload(questions)
        field_paths = {v[0] for v in violations}
        assert "questions[0].question" in field_paths
        assert "questions[0].header" in field_paths
        assert "questions[0].options[0].label" in field_paths
        assert "questions[0].options[0].description" in field_paths

    def test_empty_questions_no_violation(self):
        """空陣列不報錯。"""
        assert scan_payload([]) == []

    def test_malformed_items_skipped(self):
        """非 dict 項目被跳過，不中斷掃描。"""
        questions = [
            "not a dict",
            {"question": "獨立", "options": "not a list"},
            None,
        ]
        assert scan_payload(questions) == []


# ============================================================================
# W14-007: JAPANESE_ONLY 日文漢字偵測（PC-084 候選清單）
# 類別 A：日文漢字命中（17 字全覆蓋）
# ============================================================================


PC084_JAPANESE_ONLY_17 = (
    "\u8aad"  # 読 U+8AAD
    "\u8a33"  # 訳 U+8A33
    "\u99c5"  # 駅 U+99C5
    "\u4e21"  # 両 U+4E21
    "\u767a"  # 発 U+767A
    "\u56f3"  # 図 U+56F3
    "\u5e83"  # 広 U+5E83
    "\u5b9f"  # 実 U+5B9F
    "\u6c17"  # 気 U+6C17
    "\u697d"  # 楽 U+697D
    "\u89b3"  # 観 U+89B3
    "\u691c"  # 検 U+691C
    "\u6a29"  # 権 U+6A29
    "\u58f2"  # 売 U+58F2
    "\u95a2"  # 関 U+95A2
    "\u9244"  # 鉄 U+9244
    "\u8ee2"  # 転 U+8EE2
)


class TestJapaneseDetection:
    """類別 A：日文漢字命中（PC-084 17 字可入清單）。"""

    def test_japanese_only_membership_17_chars(self):
        """A1: JAPANESE_ONLY 含 PC-084 17 個可入字。"""
        for ch in PC084_JAPANESE_ONLY_17:
            assert ch in JAPANESE_ONLY, (
                f"{ch} (U+{ord(ch):04X}) 應在 JAPANESE_ONLY（PC-084 日專可入）"
            )
        assert len(JAPANESE_ONLY) >= 17, (
            f"JAPANESE_ONLY 至少 17 字，實際 {len(JAPANESE_ONLY)}"
        )

    def test_detects_dokuji_read_as_japanese(self):
        """A2: 純文字含『読』觸發日文漢字違規。"""
        violations = find_violations("\u8aad\u66f8\u7b46\u8a18", "test.field")  # 読書筆記
        jp_hits = [v for v in violations if v[2] == 0x8AAD]
        assert jp_hits, "『読』(U+8AAD) 應被偵測"
        assert jp_hits[0][3] == "日文漢字"

    def test_detects_ryou_both_as_japanese(self):
        """A3: W14-013 實證字『両』命中日文漢字類別。"""
        violations = find_violations("\u4e21\u65b9\u5f0f\u9a57\u8b49", "test.field")  # 両方式驗證
        jp_hits = [v for v in violations if v[2] == 0x4E21]
        assert jp_hits, "『両』(U+4E21) 應被偵測"
        assert jp_hits[0][3] == "日文漢字"

    def test_detects_all_17_japanese_chars_in_single_text(self):
        """A4: 17 字串接全部命中且 category 統一為日文漢字。"""
        violations = find_violations(PC084_JAPANESE_ONLY_17, "test.field")
        jp_violations = [v for v in violations if v[3] == "日文漢字"]
        assert len(jp_violations) == 17, (
            f"17 字應全命中日文漢字類別，實際 {len(jp_violations)}"
        )
        hit_codes = {v[2] for v in jp_violations}
        expected_codes = {ord(ch) for ch in PC084_JAPANESE_ONLY_17}
        assert hit_codes == expected_codes

    def test_codepoint_and_category_recorded_for_japanese(self):
        """A5: 單字『駅』違規 tuple 欄位順序嚴格吻合。"""
        violations = find_violations("\u99c5", "payload.label")  # 駅
        assert violations == [("payload.label", "\u99c5", 0x99C5, "日文漢字")]


# ============================================================================
# 類別 B：繁中異體字不誤判（PC-084 保守不入）
# ============================================================================


class TestJapaneseExclusionsVariants:
    """類別 B：体/誉/豊/拝 為繁中異體字，不可誤判為日文漢字。"""

    def test_tai_body_variant_not_flagged(self):
        """B1: 『体』(U+4F53) 繁中異體不產生日文漢字違規。"""
        text = "\u8eab\u4f53\u529b\u884c\u7684\u7cbe\u795e"  # 身体力行的精神
        violations = find_violations(text, "test.field")
        jp_hits = [v for v in violations if v[2] == 0x4F53 and v[3] == "日文漢字"]
        assert not jp_hits, "『体』不應命中日文漢字類別"

    def test_yo_honor_variant_not_flagged(self):
        """B2: 『誉』(U+8A89) 繁中異體不產生違規。"""
        text = "\u8a89\u70ba\u570b\u58eb\u7121\u96d9"  # 誉為國士無雙
        violations = find_violations(text, "test.field")
        jp_hits = [v for v in violations if v[2] == 0x8A89 and v[3] == "日文漢字"]
        assert not jp_hits, "『誉』不應命中日文漢字類別"

    def test_hou_abundance_variant_not_flagged(self):
        """B3: 『豊』(U+8C4A) 繁中異體不產生違規。"""
        text = "\u8c4a\u9952\u7684\u7530\u5712\u98a8\u5149"  # 豊饒的田園風光
        violations = find_violations(text, "test.field")
        jp_hits = [v for v in violations if v[2] == 0x8C4A and v[3] == "日文漢字"]
        assert not jp_hits, "『豊』不應命中日文漢字類別"

    def test_hai_worship_variant_not_flagged(self):
        """B4: 『拝』(U+62DD) 繁中異體不產生違規。"""
        text = "\u53c3\u62dd\u795e\u793e\u5f8c\u8fd4\u56de"  # 參拝神社後返回
        violations = find_violations(text, "test.field")
        jp_hits = [v for v in violations if v[2] == 0x62DD and v[3] == "日文漢字"]
        assert not jp_hits, "『拝』不應命中日文漢字類別"

    def test_variants_not_in_japanese_only_frozenset(self):
        """B5: 4 個繁中異體字不在 JAPANESE_ONLY 清單（PC-084 禁入）。"""
        for ch, cp in (("\u4f53", 0x4F53), ("\u8a89", 0x8A89), ("\u8c4a", 0x8C4A), ("\u62dd", 0x62DD)):
            assert ch not in JAPANESE_ONLY, (
                f"{ch} (U+{cp:04X}) 為繁中異體字，PC-084 §候選字驗證範例禁入"
            )


# ============================================================================
# 類別 C：繁日共用字不誤判（PC-084 首發案例「鑑」）
# ============================================================================


class TestJapaneseExclusionsShared:
    """類別 C：『鑑』為繁日共用字，PC-084 首發 false positive 案例。"""

    def test_kan_mirror_not_in_japanese_only(self):
        """C1: 『鑑』(U+9451) 不在 JAPANESE_ONLY（PC-084 繁日共用禁入）。"""
        assert "\u9451" not in JAPANESE_ONLY, (
            "『鑑』(U+9451) 為繁日共用字（鑑別/借鑑/鑑於），PC-084 禁入"
        )

    def test_kan_in_traditional_text_passes(self):
        """C2: 繁中文本含 3 次『鑑』無違規（回歸 PC-084 重現場景）。"""
        # 鑑別能力不足，需借鑑前人經驗，鑑於此情況
        text = "\u9451\u5225\u80fd\u529b\u4e0d\u8db3\uff0c\u9700\u501f\u9451\u524d\u4eba\u7d93\u9a57\uff0c\u9451\u65bc\u6b64\u60c5\u6cc1"
        violations = find_violations(text, "test.field")
        assert violations == [], f"繁中『鑑』不應觸發違規，實際：{violations}"

    def test_kan_in_auq_description_no_false_positive(self):
        """C3: AUQ description『提升鑑別力』不誤判（回歸 PC-050/PC-070 11 處誤判）。"""
        questions = [
            {
                "question": "\u9078\u9805",  # 選項
                "header": "\u5217",  # 列
                "options": [
                    {
                        "label": "\u63a1\u7528",  # 採用
                        "description": "\u63d0\u5347\u9451\u5225\u529b",  # 提升鑑別力
                    },
                ],
            }
        ]
        assert scan_payload(questions) == []


# ============================================================================
# 類別 D：既有回歸（SIMPLIFIED_CHARS + EMOJI 不被破壞）
# ============================================================================


class TestRegressionSimplifiedAndEmoji:
    """類別 D：確保新增日文偵測不破壞既有簡體 / emoji 偵測。"""

    def test_w13_003_simplified_regression_unchanged(self):
        """D1: W13-003『隶/遗』仍標記為簡體字（不偏移類別）。"""
        # 『隶』U+96B6 + 『遗』U+9057（簡體）— 對比繁體『隸』U+96B8 / 『遺』U+907A
        text = "F \u6848\u5916\u79fb\u96b6\u5c6c\u9057\u7559\u8655\u7406"
        violations = find_violations(text, "test.field")
        li_hits = [v for v in violations if v[2] == 0x96B6]
        yi_hits = [v for v in violations if v[2] == 0x9057]
        assert li_hits and li_hits[0][3] == "簡體字"
        assert yi_hits and yi_hits[0][3] == "簡體字"

    def test_existing_simplified_chars_still_detected(self):
        """D2: 『独/决/违』仍觸發簡體字違規。"""
        text = "\u72ec\u7acb\u6267\u884c\u51b3\u7b56\u8fdd\u53cd\u89c4\u5219"  # 独立执行决策违反规则
        violations = find_violations(text, "test.field")
        simplified_codes = [v[2] for v in violations if v[3] == "簡體字"]
        for cp in (0x72EC, 0x51B3, 0x8FDD):
            assert cp in simplified_codes, f"U+{cp:04X} 應為簡體字違規"

    def test_trad_simp_shared_chars_not_flagged(self):
        """D3: 繁簡共用字（出入口年月日）不誤判（PC-074 教訓）。"""
        text = "\u51fa\u5165\u53e3\u6642\u5e74\u6708\u65e5\u4eba\u5927\u5c0f"  # 出入口時年月日人大小
        violations = find_violations(text, "test.field")
        assert violations == []

    def test_emoji_ranges_still_detected(self):
        """D4: emoji 範圍仍攔截。"""
        text = "\u9032\u5ea6 \u26a1 \u5b8c\u6210 \u2705 \u4efb\u52d9"  # 進度 ⚡ 完成 ✅ 任務
        violations = find_violations(text, "test.field")
        emoji_codes = [v[2] for v in violations if v[3] == "emoji"]
        assert 0x26A1 in emoji_codes
        assert 0x2705 in emoji_codes


# ============================================================================
# 類別 E：混合污染（多類別共存 + 判定順序）
# ============================================================================


class TestMixedContamination:
    """類別 E：同一文本混合多類別污染的處理。"""

    def test_mixed_simplified_and_japanese_both_detected(self):
        """E1: 『独立読書筆記』同時含簡體『独』與日漢『読』。"""
        text = "\u72ec\u7acb\u8aad\u66f8\u7b46\u8a18"  # 独立読書筆記
        violations = find_violations(text, "test.field")
        categories = {(v[2], v[3]) for v in violations}
        assert (0x72EC, "簡體字") in categories, "『独』應為簡體字類別"
        assert (0x8AAD, "日文漢字") in categories, "『読』應為日文漢字類別"

    def test_mixed_emoji_japanese_simplified(self):
        """E2: emoji + 簡體 + 日漢混合皆被正確分類。"""
        text = "\u26a1\u72ec\u7acb\u8aad\u66f8"  # ⚡独立読書
        violations = find_violations(text, "test.field")
        cats = {(v[2], v[3]) for v in violations}
        assert (0x26A1, "emoji") in cats
        assert (0x72EC, "簡體字") in cats
        assert (0x8AAD, "日文漢字") in cats

    def test_category_ordering_simplified_before_japanese(self):
        """E3: SIMPLIFIED_CHARS 判定分支優先於 JAPANESE_ONLY（契約）。"""
        # 『独』U+72EC 僅簡體 positive control；驗證類別為簡體不會被日文分支遮蔽
        violations = find_violations("\u72ec", "test.field")
        assert violations == [("test.field", "\u72ec", 0x72EC, "簡體字")]

    def test_scan_payload_full_structure_mixed_contamination(self):
        """E4: AUQ 全欄位混合污染，field_path 與類別正確。"""
        questions = [
            {
                "question": "\u72ec\u7acb\u554f\u984c",  # 独立問題
                "header": "\u8fdd\u53cd",  # 违反
                "options": [
                    {
                        "label": "\u8aad\u66f8",  # 読書
                        "description": "\u62dd\u795e \u26a1",  # 拝神 ⚡
                    },
                ],
            }
        ]
        violations = scan_payload(questions)
        cats = {v[3] for v in violations}
        assert "簡體字" in cats
        assert "日文漢字" in cats
        assert "emoji" in cats
        # 『拝』不應命中日文漢字（B 類保證）
        hai_jp = [v for v in violations if v[2] == 0x62DD and v[3] == "日文漢字"]
        assert not hai_jp


# ============================================================================
# 類別 F：邊界 + field_path + BLOCK_MESSAGE_TEMPLATE
# ============================================================================


class TestFieldPathAndTemplate:
    """類別 F：邊界、field_path 契約、錯誤訊息模板。"""

    def test_field_path_recorded_for_japanese_violation(self):
        """F1: find_violations 對日文漢字違規精確傳遞 field_path。"""
        violations = find_violations("\u8aad", "questions[0].options[2].description")
        assert violations
        assert violations[0][0] == "questions[0].options[2].description"
        assert violations[0][3] == "日文漢字"

    def test_scan_payload_field_path_japanese_in_label(self):
        """F2: options.label 的日文漢字 field_path 正確標記。"""
        questions = [
            {
                "question": "\u9078\u9805",  # 選項
                "header": "\u5217",  # 列
                "options": [
                    {"label": "\u5728\u65e5", "description": "\u7e41\u4e2d"},  # 在日 / 繁中
                    {"label": "\u99c5\u524d", "description": "\u7e41\u4e2d"},  # 駅前 / 繁中
                ],
            }
        ]
        violations = scan_payload(questions)
        eki_hits = [v for v in violations if v[2] == 0x99C5 and v[3] == "日文漢字"]
        assert eki_hits
        assert eki_hits[0][0] == "questions[0].options[1].label"

    def test_scan_payload_field_path_japanese_in_header(self):
        """F3: header 的日文漢字 field_path 正確標記。"""
        questions = [
            {
                "question": "\u6bd4\u8f03",  # 比較
                "header": "\u4e21\u6848\u6bd4\u8f03",  # 両案比較
                "options": [{"label": "A", "description": "B"}],
            }
        ]
        violations = scan_payload(questions)
        ryou_hits = [v for v in violations if v[2] == 0x4E21 and v[3] == "日文漢字"]
        assert ryou_hits
        assert ryou_hits[0][0] == "questions[0].header"

    def test_block_message_template_has_japanese_hint(self):
        """F4: BLOCK_MESSAGE_TEMPLATE 含『日文漢字』字樣 + 替換範例。"""
        assert "日文漢字" in BLOCK_MESSAGE_TEMPLATE, (
            "BLOCK_MESSAGE_TEMPLATE 應含『日文漢字』字樣"
        )
        # 至少 1 組日文→繁體替換範例
        pairs_found = any(
            pair in BLOCK_MESSAGE_TEMPLATE
            for pair in ("読\u2192\u8b80", "両\u2192\u5169", "\u99c5\u2192\u9a5b")
            # 読→讀 / 両→兩 / 駅→驛
        )
        assert pairs_found, (
            "BLOCK_MESSAGE_TEMPLATE 應至少含 1 組日文漢字替換範例（読→讀 / 両→兩 / 駅→驛）"
        )

    def test_empty_string_no_violation(self):
        """F5: 空字串無違規（邊界回歸）。"""
        assert find_violations("", "f") == []

    def test_pure_ascii_no_violation(self):
        """F6: 純 ASCII 無違規。"""
        assert find_violations("Hello World 123", "f") == []

    def test_pure_traditional_with_jp_compatible_chars(self):
        """F7: 純繁體含繁日共用字與異體字綜合不誤判。"""
        # 建立獨立的隸屬關係，鑑別產生結果，身体力行
        text = (
            "\u5efa\u7acb\u7368\u7acb\u7684\u96b8\u5c6c\u95dc\u4fc2\uff0c"
            "\u9451\u5225\u7522\u751f\u7d50\u679c\uff0c\u8eab\u4f53\u529b\u884c"
        )
        violations = find_violations(text, "test.field")
        assert violations == [], f"純繁體不應誤判，實際：{violations}"


# ============================================================================
# 類別 G：W13-006.2 雙通道輸出（exit 0 + JSON permissionDecisionReason）
# 根據 ANA W13-006.1 推薦方案 C：
#   - 攔截路徑改 exit 0
#   - stdout 輸出 hookSpecificOutput JSON（permissionDecision=deny）
#   - permissionDecisionReason 包含完整 BLOCK_MESSAGE_TEMPLATE 內容
#   - stderr 無輸出或僅極簡摘要（不含完整指引）
#   - logger.warning 保留（file log 可觀測性）
# ============================================================================


HOOK_PATH = HOOK_DIR / "askuserquestion-charset-guard-hook.py"


def _run_hook(payload: dict) -> tuple[int, str, str]:
    """以子行程方式執行 hook，回傳 (exit_code, stdout, stderr)。"""
    proc = subprocess.run(
        ["python3", str(HOOK_PATH)],
        input=_json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _make_auq_input(questions: list) -> dict:
    return {
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": questions},
    }


class TestDualChannelOutput:
    """W13-006.2：攔截時 exit 0 + stdout JSON + stderr 極簡。"""

    def test_clean_payload_exits_zero_and_no_stdout(self):
        """G1: 合法 payload → exit 0，stdout 空（或非 deny JSON），stderr 空。"""
        payload = _make_auq_input([
            {
                "question": "選擇方案？",
                "header": "方案",
                "options": [
                    {"label": "繼續", "description": "維持現狀"},
                    {"label": "切換", "description": "改方向"},
                ],
            }
        ])
        code, out, err = _run_hook(payload)
        assert code == 0, f"合法 payload 應 exit 0，實際 {code}；stderr={err}"
        # 合法 payload 不需 deny JSON（允許 stdout 空或無 hookSpecificOutput）
        if out.strip():
            parsed = _json.loads(out)
            hso = parsed.get("hookSpecificOutput", {})
            assert hso.get("permissionDecision") != "deny"
        assert err.strip() == "", f"合法 payload stderr 應為空，實際：{err!r}"

    def test_violating_payload_exits_zero_not_two(self):
        """G2: 違規 payload → exit 0（非 2），讓 stdout JSON 生效。"""
        payload = _make_auq_input([
            {
                "question": "問題",
                "header": "H",
                "options": [
                    {"label": "与方案", "description": "D"},
                ],
            }
        ])
        code, out, err = _run_hook(payload)
        assert code == 0, (
            f"違規攔截 exit code 應為 0（方案 C），實際 {code}；"
            f"stdout={out!r}；stderr={err!r}"
        )

    def test_violating_payload_stdout_has_valid_deny_json(self):
        """G3: 違規時 stdout 為合規 JSON（含三欄位 + deny）。"""
        payload = _make_auq_input([
            {
                "question": "問題",
                "header": "H",
                "options": [{"label": "与", "description": "独立"}],
            }
        ])
        code, out, err = _run_hook(payload)
        assert code == 0
        assert out.strip(), f"違規時 stdout 應有 JSON 內容，實際空；stderr={err!r}"
        parsed = _json.loads(out)
        hso = parsed.get("hookSpecificOutput")
        assert isinstance(hso, dict), f"缺 hookSpecificOutput：{parsed}"
        assert hso.get("hookEventName") == "PreToolUse"
        assert hso.get("permissionDecision") == "deny"
        reason = hso.get("permissionDecisionReason")
        assert isinstance(reason, str) and reason, "缺 permissionDecisionReason"

    def test_violating_payload_reason_contains_repair_guidance(self):
        """G4: permissionDecisionReason 含完整修復指引（BLOCK_MESSAGE_TEMPLATE 骨幹）。"""
        payload = _make_auq_input([
            {
                "question": "問題",
                "header": "H",
                "options": [{"label": "与", "description": "D"}],
            }
        ])
        _, out, _ = _run_hook(payload)
        reason = _json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        # 核心骨幹關鍵字（來自 BLOCK_MESSAGE_TEMPLATE）
        assert "PC-072" in reason, "reason 應含 PC-072 連結"
        assert "修復方式" in reason, "reason 應含修復指引段落"
        assert "違規清單" in reason, "reason 應含違規清單段落"
        # 具體違規位置被帶入
        assert "U+4E0E" in reason or "与" in reason, "reason 應列出違規字"

    def test_violating_payload_stderr_minimal_or_empty(self):
        """G5: 違規時 stderr 空或極簡（不含完整修復方式 1-4 步）。"""
        payload = _make_auq_input([
            {
                "question": "問題",
                "header": "H",
                "options": [{"label": "与", "description": "D"}],
            }
        ])
        _, _, err = _run_hook(payload)
        # 極簡定義：不得含「修復方式」完整 1-4 步清單
        # 既有 BLOCK_MESSAGE_TEMPLATE 的「修復方式：」段落不應出現在 stderr
        assert "修復方式：" not in err, (
            f"stderr 不應含完整『修復方式』段落（應走 stdout JSON），實際 stderr：{err!r}"
        )
        # 若 stderr 有內容，行數 <= 10（極簡摘要）
        if err.strip():
            assert err.count("\n") <= 10, (
                f"stderr 應為極簡摘要（<=10 行），實際 {err.count(chr(10))} 行：{err!r}"
            )

    def test_non_auq_tool_passes_silently(self):
        """G6: tool_name 非 AskUserQuestion → exit 0 + stdout/stderr 無 deny JSON。"""
        payload = {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/x"}}
        code, out, err = _run_hook(payload)
        assert code == 0
        if out.strip():
            parsed = _json.loads(out)
            assert parsed.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
