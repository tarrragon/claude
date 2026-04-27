#!/usr/bin/env python3
"""
Language Guard Hook - 測試（W17-068）

驗證 language-guard-hook.py 三類偵測：
- 既有：非預期語言（韓文 / 日文假名）
- W17-068 新增：emoji codepoint 範圍偵測
- W17-068 新增：隱含表達 6 句型偵測（document-writing-style v1.2.0 反模式）

設計原則：
- 三類偵測皆為「警告非阻擋」（exit 0），符合 W17-066 PCB §自我驗證重點
- 觸發後寫入 stderr + 日誌（規則 4：失敗必須可見）
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
    "language_guard_hook",
    HOOK_DIR / "language-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

contains_korean = hook_module.contains_korean
contains_japanese_kana = hook_module.contains_japanese_kana
contains_non_expected_language = hook_module.contains_non_expected_language
find_emoji_chars = hook_module.find_emoji_chars
find_implicit_expressions = hook_module.find_implicit_expressions
IMPLICIT_EXPRESSION_PATTERNS = hook_module.IMPLICIT_EXPRESSION_PATTERNS
EMOJI_RANGES = hook_module.EMOJI_RANGES

HOOK_PATH = HOOK_DIR / "language-guard-hook.py"


# ============================================================================
# 子行程執行輔助
# ============================================================================


def _run_hook(payload: dict) -> tuple:
    """以子行程方式執行 hook，回傳 (exit_code, stdout, stderr)。"""
    proc = subprocess.run(
        ["python3", str(HOOK_PATH)],
        input=_json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _make_transcript(assistant_content: str) -> dict:
    """建立含 assistant 回應的 transcript payload。"""
    return {
        "transcript": [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": assistant_content},
        ]
    }


# ============================================================================
# 類別 A：既有語言偵測（韓文 / 日文假名）回歸
# ============================================================================


class TestExistingLanguageDetection:
    """類別 A：既有韓文 / 日文假名偵測不被破壞。"""

    def test_detects_korean(self):
        """A1: 韓文（U+AC00-D7AF）偵測。"""
        text = "這是韓文：안녕하세요"  # 안녕하세요
        assert contains_korean(text)
        assert contains_non_expected_language(text)

    def test_detects_hiragana(self):
        """A2: 平假名（U+3040-309F）偵測。"""
        text = "日文：こんにちは"  # こんにちは
        assert contains_japanese_kana(text)

    def test_detects_katakana(self):
        """A3: 片假名（U+30A0-30FF）偵測。"""
        text = "外來語：コンピュータ"  # コンピュータ
        assert contains_japanese_kana(text)

    def test_pure_traditional_passes_language_check(self):
        """A4: 純繁體中文不觸發語言偵測。"""
        text = "建立獨立的隸屬關係，遺留項目已處理"
        assert not contains_korean(text)
        assert not contains_japanese_kana(text)
        assert not contains_non_expected_language(text)

    def test_pure_ascii_passes_language_check(self):
        """A5: 純 ASCII 不觸發語言偵測。"""
        text = "Hello World 123 test"
        assert not contains_non_expected_language(text)


# ============================================================================
# 類別 B：W17-068 emoji 偵測
# ============================================================================


class TestEmojiDetection:
    """類別 B：emoji codepoint 範圍偵測。"""

    def test_detects_misc_symbols_range(self):
        """B1: U+2600-27BF 範圍（含 ⚡ ✅ ❌）。"""
        text = "進度 ⚡ 完成 ✅"  # ⚡ ✅
        hits = find_emoji_chars(text)
        codes = {cp for _, cp in hits}
        assert 0x26A1 in codes, "⚡ 應被偵測"
        assert 0x2705 in codes, "✅ 應被偵測"

    def test_detects_pictographs_range(self):
        """B2: U+1F300-1F5FF 範圍（含目標符號 🎯 / 紅圓 🔴）。"""
        text = "標記 \U0001f3af 完成 \U0001f534"
        hits = find_emoji_chars(text)
        codes = {cp for _, cp in hits}
        assert 0x1F3AF in codes
        assert 0x1F534 in codes

    def test_detects_emoticons_range(self):
        """B3: U+1F600-1F64F 範圍（emoticons）。"""
        text = "Happy \U0001f600"
        hits = find_emoji_chars(text)
        codes = {cp for _, cp in hits}
        assert 0x1F600 in codes

    def test_detects_transport_range(self):
        """B4: U+1F680-1F6FF 範圍（transport）。"""
        text = "Launch \U0001f680"  # rocket
        hits = find_emoji_chars(text)
        codes = {cp for _, cp in hits}
        assert 0x1F680 in codes

    def test_detects_supplemental_pictographs_range(self):
        """B5: U+1F900-1F9FF 範圍。"""
        text = "Brain \U0001f9e0"
        hits = find_emoji_chars(text)
        codes = {cp for _, cp in hits}
        assert 0x1F9E0 in codes

    def test_detects_extended_a_range(self):
        """B6: U+1FA00-1FAFF 範圍。"""
        text = "Test \U0001fa90"  # ringed planet
        hits = find_emoji_chars(text)
        codes = {cp for _, cp in hits}
        assert 0x1FA90 in codes

    def test_no_emoji_returns_empty(self):
        """B7: 純文字無 emoji 回傳空 list。"""
        assert find_emoji_chars("純繁體文字測試") == []
        assert find_emoji_chars("Plain ASCII text") == []
        assert find_emoji_chars("") == []

    def test_deduplicates_repeated_emoji(self):
        """B8: 同一 emoji 重複出現只回報一次（去重）。"""
        text = "⚡ progress ⚡ done ⚡"
        hits = find_emoji_chars(text)
        codes = [cp for _, cp in hits]
        assert codes.count(0x26A1) == 1, f"⚡ 應去重，實際：{codes}"

    def test_emoji_ranges_constant_structure(self):
        """B9: EMOJI_RANGES 結構完整且涵蓋既有 charset hook 一致範圍。"""
        assert isinstance(EMOJI_RANGES, tuple)
        # 至少含 6 個範圍（與 askuserquestion-charset-guard-hook 對齊）
        assert len(EMOJI_RANGES) >= 6
        for start, end in EMOJI_RANGES:
            assert isinstance(start, int) and isinstance(end, int)
            assert start <= end


# ============================================================================
# 類別 C：W17-068 隱含表達 6 句型偵測
# ============================================================================


class TestImplicitExpressionDetection:
    """類別 C：隱含表達 6 句型偵測（document-writing-style v1.2.0 反模式表）。"""

    def test_patterns_loaded(self):
        """C1: IMPLICIT_EXPRESSION_PATTERNS 含 7 個句型（document-writing-style 6 條 + 拆分）。"""
        # document-writing-style v1.2.0 表格列出 6 列，但「按理應」「自然而然」同列分為 2 模式
        # 「通常來說」「一般情況下」同列分為 2 模式
        # 故實際 pattern 數 >= 6
        assert len(IMPLICIT_EXPRESSION_PATTERNS) >= 6
        for pattern, hint in IMPLICIT_EXPRESSION_PATTERNS:
            assert isinstance(pattern, str) and pattern
            assert isinstance(hint, str) and hint

    def test_detects_xiwang_duzhe(self):
        """C2: 「希望讀者理解」句型。"""
        text = "希望讀者理解這個機制的重要性。"
        hits = find_implicit_expressions(text)
        patterns = [p for p, _ in hits]
        assert "希望讀者理解" in patterns

    def test_detects_anli_ying(self):
        """C3: 「按理應」句型。"""
        text = "按理應該透過 hook 攔截，而非依賴自律。"
        hits = find_implicit_expressions(text)
        patterns = [p for p, _ in hits]
        assert "按理應" in patterns

    def test_detects_zirAn_erran(self):
        """C4: 「自然而然」句型。"""
        text = "若每個 PM 都這樣做，自然而然會形成共識。"
        hits = find_implicit_expressions(text)
        patterns = [p for p, _ in hits]
        assert "自然而然" in patterns

    def test_detects_tongchang_laishuo(self):
        """C5: 「通常來說」句型。"""
        text = "通常來說，這類錯誤可以由 lint 偵測。"
        hits = find_implicit_expressions(text)
        patterns = [p for p, _ in hits]
        assert "通常來說" in patterns

    def test_detects_yiban_qingkuangxia(self):
        """C6: 「一般情況下」句型。"""
        text = "一般情況下，PM 不應寫產品程式碼。"
        hits = find_implicit_expressions(text)
        patterns = [p for p, _ in hits]
        assert "一般情況下" in patterns

    def test_detects_jiashe_duzhe(self):
        """C7: 「假設讀者會注意到」句型。"""
        text = "我假設讀者會注意到這個邊界條件。"
        hits = find_implicit_expressions(text)
        patterns = [p for p, _ in hits]
        assert "假設讀者會注意到" in patterns

    def test_detects_lixiang_qingkuangxia(self):
        """C8: 「理想情況下」句型。"""
        text = "理想情況下，所有 hook 都會在 100ms 內回應。"
        hits = find_implicit_expressions(text)
        patterns = [p for p, _ in hits]
        assert "理想情況下" in patterns

    def test_detects_multiple_patterns_in_single_text(self):
        """C9: 多個句型共存時全部命中。"""
        text = (
            "通常來說系統會自動處理，理想情況下不需要人工介入，"
            "但按理應提供 fallback 給特殊場景。"
        )
        hits = find_implicit_expressions(text)
        patterns = {p for p, _ in hits}
        assert "通常來說" in patterns
        assert "理想情況下" in patterns
        assert "按理應" in patterns

    def test_clean_text_no_hits(self):
        """C10: 明示三層結構文字不觸發偵測（negative case）。"""
        text = (
            "強制規則：所有 hook 必須在 100ms 內回應。"
            "違反會導致 PreToolUse 階段超時。"
            "修正方向：拆分耗時邏輯到背景任務。"
        )
        assert find_implicit_expressions(text) == []

    def test_pure_ascii_no_hits(self):
        """C11: 純 ASCII 無命中。"""
        assert find_implicit_expressions("Plain English text without patterns.") == []

    def test_empty_text_no_hits(self):
        """C12: 空字串回傳空 list。"""
        assert find_implicit_expressions("") == []

    def test_hint_format_provides_correction_direction(self):
        """C13: 每個句型的 hint 包含修正方向（明示三層元素）。"""
        for pattern, hint in IMPLICIT_EXPRESSION_PATTERNS:
            # hint 應含「改為」「明示」等修正詞之一
            has_correction = any(
                keyword in hint
                for keyword in ("改為明示", "改為", "明示")
            )
            assert has_correction, (
                f"句型「{pattern}」的 hint 缺修正方向：{hint}"
            )


# ============================================================================
# 類別 D：子行程整合（exit code + stderr 雙通道）
# ============================================================================


class TestHookSubprocessIntegration:
    """類別 D：完整 hook 子行程執行（規則 4：失敗必須可見）。"""

    def test_clean_assistant_message_exits_zero_silent(self):
        """D1: 純繁體無違規 → exit 0，stderr 無警告。"""
        payload = _make_transcript("這是純繁體中文回應，無違規。")
        code, _, err = _run_hook(payload)
        assert code == 0, f"clean message 應 exit 0，實際 {code}"
        assert "[LANG GUARD]" not in err, f"clean 訊息不應有警告：{err}"

    def test_korean_in_assistant_message_exits_zero_with_warning(self):
        """D2: 韓文觸發警告但不阻擋（exit 0 + stderr 警告）。"""
        payload = _make_transcript("回應含韓文 안녕")  # 안녕
        code, _, err = _run_hook(payload)
        assert code == 0, "警告非阻擋，應 exit 0"
        assert "[LANG GUARD]" in err
        assert "韓文" in err or "日文" in err or "非繁體" in err

    def test_emoji_in_assistant_message_exits_zero_with_warning(self):
        """D3: emoji 觸發警告但不阻擋。"""
        payload = _make_transcript("進度 ⚡ 完成 ✅ 任務")
        code, _, err = _run_hook(payload)
        assert code == 0, "警告非阻擋，應 exit 0"
        assert "[LANG GUARD]" in err
        assert "emoji" in err.lower() or "U+26A1" in err or "U+2705" in err

    def test_implicit_expression_in_assistant_message_exits_zero_with_warning(self):
        """D4: 隱含表達句型觸發警告但不阻擋（PCB §自我驗證重點：警告非阻擋）。"""
        payload = _make_transcript(
            "通常來說系統會自動處理。理想情況下不需要人工介入。"
        )
        code, _, err = _run_hook(payload)
        assert code == 0, "隱含表達句型必為警告非阻擋（exit 0）"
        assert "[LANG GUARD]" in err
        assert "隱含表達" in err or "通常來說" in err or "理想情況下" in err

    def test_multiple_violations_all_reported(self):
        """D5: 多類違規共存時全部回報（emoji + 隱含表達）。"""
        payload = _make_transcript(
            "通常來說 ⚡ 系統會自動處理。"
        )
        code, _, err = _run_hook(payload)
        assert code == 0
        # emoji 警告
        assert "emoji" in err.lower() or "U+26A1" in err
        # 隱含表達警告
        assert "通常來說" in err

    def test_empty_stdin_passes_silently(self):
        """D6: 無 stdin 輸入靜默通過（已預期非標準輸入路徑）。"""
        proc = subprocess.run(
            ["python3", str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0, f"空 stdin 應 exit 0，實際 {proc.returncode}"
        # 空 stdin 屬已預期路徑，不應寫 stderr
        assert "[LANG GUARD]" not in proc.stderr

    def test_no_assistant_message_passes_silently(self):
        """D7: transcript 無 assistant 訊息靜默通過。"""
        payload = {"transcript": [{"role": "user", "content": "test"}]}
        code, _, err = _run_hook(payload)
        assert code == 0
        assert "[LANG GUARD]" not in err

    def test_malformed_transcript_passes_silently(self):
        """D8: malformed transcript 靜默通過（非 crash）。"""
        payload = {"transcript": "not a list"}
        code, _, err = _run_hook(payload)
        assert code == 0  # extract returns None, no warning


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
