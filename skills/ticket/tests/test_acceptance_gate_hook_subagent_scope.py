"""
測試 acceptance-gate-hook 對 subagent 環境的早退範圍收斂（0.2.1-W3-519）。

背景：修復前 main() 於偵測到 subagent 環境（agent_id 存在）時直接
return EXIT_SUCCESS，短路整條驗收流程；is_subagent_environment() 的
docstring 明寫用途僅為「避免在 subagent 中輸出 AskUserQuestion 提醒」，
兩者範圍不一致，使 children_completed / hook_protection_acceptance 等
blocking checker 對 subagent（本框架絕大多數 ticket 執行主體）從未真正
生效過。

修復後：
- subagent 環境只抑制「PM 必須使用 AskUserQuestion」的互動提醒文字
  （場景 #1/#2/#9/#17）
- blocking checker（children_completed / hook_protection_acceptance）
  與其他 warning（checklist、error-pattern 衝突等）不受 is_subagent 影響，
  對 subagent 與 PM 一致生效

涵蓋：
1. children 未完成時，subagent complete 仍被 block（回歸核心）
2. 防護類 hook ticket 缺三項必含 acceptance 時，subagent complete 仍被 block
3. generate_hook_output 於 is_subagent=True 時抑制場景 #1/#2/#9/#17 提醒文字，
   is_subagent=False（PM）時維持原有提醒
4. should_block 語意（checklist、error-pattern 衝突等非互動 warning）不因
   is_subagent 而改變
"""

from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_hook_module():
    """動態 import hook（檔名含 dash，無法用一般 import）。"""
    hook_path = (
        Path(__file__).resolve().parents[1]
        / "hooks"
        / "acceptance-gate-hook.py"
    )
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook_subagent", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_ticket(project_dir: Path, ticket_id: str, body: str) -> Path:
    """建立一個最小可解析的 Ticket 檔案（docs/work-logs/v{version}/tickets/ 結構）。"""
    version_part = ticket_id.split("-W")[0]
    ticket_dir = project_dir / "docs" / "work-logs" / f"v{version_part}" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    ticket_file = ticket_dir / f"{ticket_id}.md"
    ticket_file.write_text(body, encoding="utf-8")
    return ticket_file


def _payload(command: str, agent_id: str = None) -> dict:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent_id:
        payload["agent_id"] = agent_id
    return payload


def _run_main(module, payload: dict, tmp_path: Path):
    buf = io.StringIO()
    with patch.object(module, "read_json_from_stdin", return_value=payload), \
         patch.object(module, "get_project_root", return_value=tmp_path), \
         patch.object(module, "save_check_log"), \
         redirect_stdout(buf):
        rc = module.main()
    return rc, buf.getvalue()


# ----------------------------------------------------------------------------
# 情境 1：children 未完成，subagent complete 仍必須被 block（回歸核心）
# ----------------------------------------------------------------------------

class TestSubagentStillBlockedByChildrenChecker:
    def test_subagent_complete_with_pending_child_is_blocked(self, tmp_path):
        module = _load_hook_module()
        _write_ticket(
            tmp_path,
            "0.0.0-W1-900",
            """---
id: 0.0.0-W1-900
title: parent
type: IMP
status: in_progress
version: 0.0.0
children: [0.0.0-W1-900.1]
---

## Solution

placeholder

## Test Results

placeholder
""",
        )
        _write_ticket(
            tmp_path,
            "0.0.0-W1-900.1",
            """---
id: 0.0.0-W1-900.1
title: child
type: IMP
status: pending
version: 0.0.0
children: []
---

# Body
""",
        )

        payload = _payload("ticket track complete 0.0.0-W1-900", agent_id="thyme-python-developer")
        rc, _ = _run_main(module, payload, tmp_path)

        assert rc == module.EXIT_BLOCK, (
            "subagent complete 時 children_completed checker 仍必須 block；"
            "修復前 subagent 早退會使此檢查完全不執行，錯誤放行"
        )

    def test_pm_complete_with_pending_child_is_blocked(self, tmp_path):
        """對照組：PM（無 agent_id）本就應被 block，確認行為未變。"""
        module = _load_hook_module()
        _write_ticket(
            tmp_path,
            "0.0.0-W1-901",
            """---
id: 0.0.0-W1-901
title: parent
type: IMP
status: in_progress
version: 0.0.0
children: [0.0.0-W1-901.1]
---

## Solution

placeholder

## Test Results

placeholder
""",
        )
        _write_ticket(
            tmp_path,
            "0.0.0-W1-901.1",
            """---
id: 0.0.0-W1-901.1
title: child
type: IMP
status: pending
version: 0.0.0
children: []
---

# Body
""",
        )

        payload = _payload("ticket track complete 0.0.0-W1-901")
        rc, _ = _run_main(module, payload, tmp_path)

        assert rc == module.EXIT_BLOCK


# ----------------------------------------------------------------------------
# 情境 2：防護類 hook ticket 缺三項必含 acceptance，subagent complete 仍必須被 block
# ----------------------------------------------------------------------------

class TestSubagentStillBlockedByHookProtectionAcceptance:
    def test_subagent_complete_missing_hook_protection_fields_is_blocked(self, tmp_path):
        module = _load_hook_module()
        _write_ticket(
            tmp_path,
            "0.0.0-W1-910",
            """---
id: 0.0.0-W1-910
title: touches hooks dir
type: IMP
status: in_progress
version: 0.0.0
children: []
where:
  files:
  - .claude/hooks/some-new-guard-hook.py
acceptance:
- '[x] 功能已實作'
---

## Solution

placeholder

## Test Results

placeholder
""",
        )

        payload = _payload("ticket track complete 0.0.0-W1-910", agent_id="basil-hook-architect")
        rc, _ = _run_main(module, payload, tmp_path)

        assert rc == module.EXIT_BLOCK, (
            "subagent complete 時 hook_protection_acceptance checker（本 wave 新增的"
            "防護類 hook 三項必含 acceptance 硬擋）仍必須生效，不可因 subagent 身份被略過"
        )


# ----------------------------------------------------------------------------
# 情境 3：generate_hook_output 對 is_subagent 的抑制範圍限定於互動提醒文字
# ----------------------------------------------------------------------------

class TestGenerateHookOutputSubagentSuppressesOnlyInteractivePrompts:
    def _clean_result(self, module, **overrides):
        # pending_sibling_tickets 刻意 < 2（場景 #9 門檻），避開既有（與本票無關的）
        # HANDOFF_DIRECTION_REMINDER.format() 缺 next_ticket_id 參數的 KeyError——
        # 該問題僅在 is_subagent=False 且 sibling >= 2 時觸發，已透過
        # ticket track add-spawn-request 另行追蹤，不在本票範圍修復。
        defaults = dict(
            should_block=False,
            has_acceptance=True,
            message=None,
            has_new_error_patterns=True,
            new_error_pattern_files=["PC-999-example.md"],
            pending_sibling_tickets=["0.0.0-W1-002"],
            task_type="IMP",
            priority="P0",
        )
        defaults.update(overrides)
        return module.AcceptanceCheckResult(**defaults)

    def test_subagent_output_has_no_askuserquestion_text(self, tmp_path):
        module = _load_hook_module()
        result = self._clean_result(module)

        output = module.generate_hook_output(
            "0.0.0-W1-001", result, tmp_path, module.setup_hook_logging("test"), is_subagent=True
        )
        context = output["hookSpecificOutput"].get("additionalContext", "")

        assert "AskUserQuestion" not in context, (
            "subagent 環境不應輸出任何要求「PM 必須使用 AskUserQuestion」的互動提醒文字"
        )

    def test_pm_output_still_has_askuserquestion_text(self, tmp_path):
        """對照組：PM（is_subagent=False）維持原有互動提醒，確認未被本次修復連帶移除。"""
        module = _load_hook_module()
        result = self._clean_result(module)

        output = module.generate_hook_output(
            "0.0.0-W1-001", result, tmp_path, module.setup_hook_logging("test"), is_subagent=False
        )
        context = output["hookSpecificOutput"].get("additionalContext", "")

        assert "AskUserQuestion" in context, "PM 環境（is_subagent=False）必須維持原有互動提醒"

    def test_default_is_subagent_false_backward_compatible(self, tmp_path):
        """未傳 is_subagent 參數時預設 False，維持既有呼叫端（如測試）行為不變。"""
        module = _load_hook_module()
        result = self._clean_result(module)

        output = module.generate_hook_output(
            "0.0.0-W1-001", result, tmp_path, module.setup_hook_logging("test")
        )
        context = output["hookSpecificOutput"].get("additionalContext", "")

        assert "AskUserQuestion" in context

    def test_subagent_should_block_semantics_unaffected(self, tmp_path):
        """is_subagent 僅影響提醒文字，should_block 的 permissionDecision 不受影響。"""
        module = _load_hook_module()
        blocked_result = self._clean_result(
            module, should_block=True, message="[ERROR] blocked", has_new_error_patterns=False,
            new_error_pattern_files=[], pending_sibling_tickets=[],
        )

        output_subagent = module.generate_hook_output(
            "0.0.0-W1-001", blocked_result, tmp_path, module.setup_hook_logging("test"), is_subagent=True
        )
        output_pm = module.generate_hook_output(
            "0.0.0-W1-001", blocked_result, tmp_path, module.setup_hook_logging("test"), is_subagent=False
        )

        assert output_subagent["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert output_pm["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_subagent_still_gets_non_interactive_warnings(self, tmp_path):
        """error-pattern 衝突等非互動 warning（不透過 AskUserQuestionMessages）不因 is_subagent 被抑制。"""
        module = _load_hook_module()
        result = self._clean_result(
            module,
            has_new_error_patterns=False,
            new_error_pattern_files=[],
            pending_sibling_tickets=[],
            error_pattern_conflicts=["PC-100-example.md"],
        )

        output = module.generate_hook_output(
            "0.0.0-W1-001", result, tmp_path, module.setup_hook_logging("test"), is_subagent=True
        )
        context = output["hookSpecificOutput"].get("additionalContext", "")

        assert "error-pattern 衝突" in context, (
            "非互動性 warning（如 error-pattern 衝突提醒）不應被 is_subagent 連帶抑制，"
            "只有明確要求 PM 呼叫 AskUserQuestion 的提醒才受影響"
        )
