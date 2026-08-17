"""
測試 acceptance-gate-hook generate_hook_output 場景 #9（Handoff 方向）不再因
HANDOFF_DIRECTION_REMINDER.format() 缺 next_ticket_id 參數而 KeyError
（0.2.1-W3-521）。

背景：0.2.1-W3-519 撰寫 test_acceptance_gate_hook_subagent_scope.py 時實測
發現，is_subagent=False 且 pending_sibling_tickets 長度 >= 2（場景 #9 門檻）
時，generate_hook_output 呼叫
AskUserQuestionMessages.HANDOFF_DIRECTION_REMINDER.format(sibling_count=...,
sibling_list=...) 缺模板要求的 next_ticket_id 參數，觸發 KeyError，被
main() 頂層 try/except 吞成 EXIT_ERROR——任何 PM（非 subagent）真實遇到同
Wave 2 個以上 pending sibling ticket 時 complete 皆會觸發。

修復：.format() 呼叫補上 next_ticket_id=check_result.pending_sibling_
tickets[0]（本分支已保證清單長度 >= 2，索引 0 恆安全）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_hook_module():
    """動態 import hook（檔名含 dash，無法用一般 import）。"""
    hook_path = (
        Path(__file__).resolve().parents[1]
        / "hooks"
        / "acceptance-gate-hook.py"
    )
    spec = importlib.util.spec_from_file_location(
        "acceptance_gate_hook_handoff_next_ticket_id", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result_with_pending_siblings(module, sibling_ids, **overrides):
    defaults = dict(
        should_block=False,
        has_acceptance=True,
        message=None,
        has_new_error_patterns=False,
        new_error_pattern_files=[],
        pending_sibling_tickets=sibling_ids,
        task_type="IMP",
        priority="P1",
    )
    defaults.update(overrides)
    return module.AcceptanceCheckResult(**defaults)


class TestHandoffReminderNoLongerKeyErrors:
    def test_two_pending_siblings_pm_does_not_raise(self, tmp_path):
        """回歸核心：is_subagent=False 且 sibling 長度恰為門檻值 2 時不再拋 KeyError。"""
        module = _load_hook_module()
        result = _result_with_pending_siblings(
            module, ["0.0.0-W1-002", "0.0.0-W1-003"]
        )

        # 修復前此呼叫會拋 KeyError: 'next_ticket_id'（透過 pytest 的預設行為，
        # 未被 try/except 包裹的例外會直接讓測試失敗，等同於斷言「不拋例外」）
        output = module.generate_hook_output(
            "0.0.0-W1-001", result, tmp_path, module.setup_hook_logging("test"), is_subagent=False
        )

        context = output["hookSpecificOutput"].get("additionalContext", "")
        assert "AskUserQuestion" in context
        assert "Handoff 方向選擇" in context

    def test_more_than_two_pending_siblings_uses_first_as_next_ticket_id(self, tmp_path):
        """next_ticket_id 應取 pending_sibling_tickets 的第一個元素。"""
        module = _load_hook_module()
        sibling_ids = ["0.0.0-W1-010", "0.0.0-W1-011", "0.0.0-W1-012"]
        result = _result_with_pending_siblings(module, sibling_ids)

        output = module.generate_hook_output(
            "0.0.0-W1-001", result, tmp_path, module.setup_hook_logging("test"), is_subagent=False
        )
        context = output["hookSpecificOutput"].get("additionalContext", "")

        assert f"/ticket track claim {sibling_ids[0]}" in context
        # 其餘 sibling 仍列於清單中（非取代整份清單，只取代範例指令的票號）
        assert sibling_ids[1] in context
        assert sibling_ids[2] in context

    def test_subagent_still_suppresses_this_reminder_regardless_of_fix(self, tmp_path):
        """對照組：is_subagent=True 時本提醒仍被抑制（0.2.1-W3-519 既有行為），
        確認本次修復未意外連帶改變 subagent 抑制邏輯。"""
        module = _load_hook_module()
        result = _result_with_pending_siblings(
            module, ["0.0.0-W1-002", "0.0.0-W1-003"]
        )

        output = module.generate_hook_output(
            "0.0.0-W1-001", result, tmp_path, module.setup_hook_logging("test"), is_subagent=True
        )
        context = output["hookSpecificOutput"].get("additionalContext", "")

        assert "Handoff 方向選擇" not in context
        assert "AskUserQuestion" not in context

    def test_single_pending_sibling_below_threshold_unaffected(self, tmp_path):
        """sibling 數量 < 2（未達場景 #9 門檻）不觸發本提醒，行為不變。"""
        module = _load_hook_module()
        result = _result_with_pending_siblings(module, ["0.0.0-W1-002"])

        output = module.generate_hook_output(
            "0.0.0-W1-001", result, tmp_path, module.setup_hook_logging("test"), is_subagent=False
        )
        context = output["hookSpecificOutput"].get("additionalContext", "")

        assert "Handoff 方向選擇" not in context
