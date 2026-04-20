#!/usr/bin/env python3
"""
AUQ Option Pattern Detector Hook - 測試（W5-042 Phase 3b）

依據 Phase 2 測試設計：3 TP + 3 FP + 4 邊界 + 6 契約 = 16 個測試。
規格: .claude/plans/hooks/auq-option-pattern-detector-spec.md
測試設計: .claude/plans/hooks/auq-option-pattern-detector-test-design.md
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# 動態匯入 Hook 模組（檔名含連字號，無法直接 import）
HOOK_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HOOK_DIR))

_spec = importlib.util.spec_from_file_location(
    "auq_option_pattern_detector_hook",
    HOOK_DIR / "auq-option-pattern-detector-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

detect_and_build_output = hook_module.detect_and_build_output
read_last_assistant_text = hook_module.read_last_assistant_text
AUQOptionPatternMessages = hook_module.AUQOptionPatternMessages


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def make_transcript(tmp_path):
    """Callable：寫入 JSONL transcript 並回傳 Path。"""

    def _make(assistant_text: str, prior_user: str = "先前任務") -> Path:
        p = tmp_path / "session.jsonl"
        lines = [
            json.dumps(
                {"type": "user", "message": {"role": "user", "content": prior_user}},
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": assistant_text}],
                    },
                },
                ensure_ascii=False,
            ),
        ]
        p.write_text("\n".join(lines), encoding="utf-8")
        return p

    return _make


@pytest.fixture
def hook_input(make_transcript):
    """Callable：建構完整 stdin dict。"""

    def _hook_input(assistant_text: str, *, agent_id=None, transcript_override=None):
        tpath = transcript_override if transcript_override is not None else make_transcript(assistant_text)
        data = {
            "hook_event_name": "UserPromptSubmit",
            "transcript_path": str(tpath),
            "session_id": "test-session",
            "cwd": "/tmp/project",
        }
        if agent_id:
            data["agent_id"] = agent_id
        return data

    return _hook_input


def run_detect(hook_input_dict, assistant_text):
    """Helper：直接呼叫 detect_and_build_output（跳過讀檔）。"""
    return detect_and_build_output(hook_input_dict, assistant_text)


def has_reminder(output: dict) -> bool:
    return "additionalContext" in output.get("hookSpecificOutput", {})


# ============================================================================
# 3.1 真陽性（TP）
# ============================================================================


class TestTruePositive:
    def test_TP1_detects_abc_options_with_question_ending(self, hook_input):
        text = "接下來有三個方向：\nA. 繼續下個 Ticket\nB. 補強測試\nC. 先 commit\n\n要選哪個？"
        out = run_detect(hook_input(text), text)
        assert has_reminder(out)
        assert "AUQ Option Pattern Reminder" in out["hookSpecificOutput"]["additionalContext"]
        assert "askuserquestion-rules" in out["hookSpecificOutput"]["additionalContext"]

    def test_TP2_detects_numeric_options_with_please_choose(self, hook_input):
        text = "有以下選項：\n1. 方案甲\n2. 方案乙\n3. 方案丙\n\n請選擇。"
        out = run_detect(hook_input(text), text)
        assert has_reminder(out)

    def test_TP3_detects_binary_confirmation_question(self, hook_input):
        text = "W5-042 Phase 1 已完成，要繼續進 Phase 2 嗎？"
        # 注意 W5-042 會觸發 E2 歷史豁免的 ticket_re，但「先前/已完成」等關鍵字需同時命中
        # 「已完成」命中 E2 history keyword - 為避免豁免，改寫不含歷史詞
        text = "Phase 1 剛剛結束。要繼續進 Phase 2 嗎？"
        out = run_detect(hook_input(text), text)
        assert has_reminder(out)


# ============================================================================
# 3.2 假陽性豁免（FP）
# ============================================================================


class TestFalsePositiveExempt:
    def test_FP1_exempts_document_reference_citation(self, hook_input):
        text = (
            "根據 askuserquestion-rules 的 18 個場景：\n"
            "A. 驗收決策\n"
            "B. 完成後收尾\n"
            "C. Wave 收尾\n"
            "詳見該文件，要選哪個？"
        )
        out = run_detect(hook_input(text), text)
        assert not has_reminder(out)

    def test_FP2_exempts_historical_decision_review(self, hook_input):
        text = (
            "先前 W5-040 當初提出三個方案：\n"
            "A. 規則強化\n"
            "B. Hook 補強\n"
            "C. CLAUDE.md 更新\n"
            "最後選了 A，要選哪個？"
        )
        out = run_detect(hook_input(text), text)
        assert not has_reminder(out)

    def test_FP3_exempts_options_inside_code_block(self, hook_input):
        text = (
            "以下是範例：\n"
            "```markdown\n"
            "A. foo\n"
            "B. bar\n"
            "C. baz\n"
            "```\n"
            "執行以下 Ticket。"
        )
        out = run_detect(hook_input(text), text)
        assert not has_reminder(out)


# ============================================================================
# 3.3 邊界測試（B）
# ============================================================================


class TestBoundary:
    def test_B1_no_trigger_with_only_two_options(self, hook_input):
        text = "兩個方向：\nA. 做\nB. 不做\n\n要哪個？"
        out = run_detect(hook_input(text), text)
        assert not has_reminder(out)

    def test_B2_no_trigger_when_question_far_from_options(self, hook_input):
        options = "選項：\nA. 甲\nB. 乙\nC. 丙\n"
        filler = "這是一段敘述內容，不含問句關鍵字。" * 40  # > 400 字
        text = options + filler + "\n說明結束。"  # 結尾無問句
        out = run_detect(hook_input(text), text)
        assert not has_reminder(out)

    def test_B3_exempts_rule_writing_context(self, hook_input):
        text = (
            "修改 .claude/pm-rules/decision-tree.md 與 "
            ".claude/pm-rules/askuserquestion-rules.md 和 "
            ".claude/rules/core/pm-role.md：\n"
            "A. 新增規則\nB. 修改措辭\nC. 刪除舊條款\n"
            "要選哪個？"
        )
        out = run_detect(hook_input(text), text)
        assert not has_reminder(out)

    def test_B4_skips_in_subagent_environment(self, hook_input):
        text = "接下來有三個方向：\nA. 甲\nB. 乙\nC. 丙\n\n要選哪個？"
        data = hook_input(text, agent_id="thyme-extension-engineer")
        out = run_detect(data, text)
        assert not has_reminder(out)


# ============================================================================
# 3.4 契約與例外測試（C）
# ============================================================================


class TestContract:
    def test_C1_output_always_contains_hook_event_name(self, hook_input):
        # 未命中場景
        text = "這是普通回覆，沒有選項也沒有問句。"
        out = run_detect(hook_input(text), text)
        assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"

    def test_C2_no_permission_decision_field(self, hook_input):
        text = "接下來有三個方向：\nA. 甲\nB. 乙\nC. 丙\n\n要選哪個？"
        out = run_detect(hook_input(text), text)
        assert "permissionDecision" not in out["hookSpecificOutput"]

    def test_C3_missing_transcript_path_passes_through(self, tmp_path, capsys):
        import logging

        logger = logging.getLogger("test-c3")
        result = read_last_assistant_text(str(tmp_path / "nonexistent.jsonl"), logger)
        assert result is None
        # 並且建構輸出時也是基礎 JSON
        out = detect_and_build_output({}, None)
        assert not has_reminder(out)
        assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"

    def test_C4_malformed_jsonl_passes_through(self, tmp_path):
        import logging

        p = tmp_path / "bad.jsonl"
        p.write_text("not a json\n{also broken\n", encoding="utf-8")
        logger = logging.getLogger("test-c4")
        result = read_last_assistant_text(str(p), logger)
        # 全部損壞行會被跳過，無 assistant 訊息 → None
        assert result is None

    def test_C5_no_stderr_output_on_expected_paths(self, hook_input, capsys):
        # TP1 / FP1 / 空 input 三種路徑均不應寫 stderr
        for text in [
            "A. 甲\nB. 乙\nC. 丙\n要選哪個？",
            "根據 askuserquestion-rules 參考文件：A. 甲 B. 乙 C. 丙 要選哪個？",
            "普通回覆。",
        ]:
            capsys.readouterr()  # 清空
            detect_and_build_output(hook_input(text), text)
            err = capsys.readouterr().err
            assert err == "", f"不應寫 stderr，但收到: {err!r}"

    def test_C6_logger_uses_info_debug_only(self, hook_input, caplog):
        import logging

        caplog.set_level(logging.DEBUG)
        # 執行一個命中 + 一個未命中流程
        text1 = "A. 甲\nB. 乙\nC. 丙\n要選哪個？"
        detect_and_build_output(hook_input(text1), text1)
        detect_and_build_output(hook_input("普通回覆。"), "普通回覆。")
        # detect_and_build_output 本身不 log；此測試驗證「沒有 WARNING/ERROR log
        # 在預期路徑被呼叫」。走 read_last_assistant_text 與 main 的 logger 由
        # hook 層使用 info/debug；此處斷言 caplog 無 WARNING+ 紀錄
        for record in caplog.records:
            assert record.levelno < logging.WARNING, f"禁止的 log level: {record}"
