"""
測試 acceptance-gate-hook effort=low 短路不再豁免 ticket track complete 命令
（0.2.1-W3-018）。

背景：修復前，effort=low 短路在「命令是否為 complete」判斷之前執行，
使 24/33 個 agent（effort: low）執行 complete 時完全跳過驗收檢查。
實證：0.2.1-W3-014 以非法 multi_view_status 值成功 complete。

修復後：
- 命令是否為 ticket track complete 的判斷前移至 effort 短路之前
- 非 complete 命令維持原有低成本短路（不受影響，W14-034 開銷控制意圖）
- complete 命令一律執行完整驗收檢查，不受 effort 短路影響

涵蓋四組合：effort low/high x complete/非 complete。
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
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(command: str, effort_level: str, tool_name: str = "Bash") -> dict:
    return {
        "tool_name": tool_name,
        "tool_input": {"command": command},
        "effort": {"level": effort_level},
    }


def _run_main(payload: dict):
    """執行 main()，回傳 (exit_code, stdout, check_acceptance_status 是否被呼叫)。"""
    module = _load_hook_module()

    call_marker = {"called": False}

    def _fake_check_acceptance_status(*args, **kwargs):
        call_marker["called"] = True
        return module.AcceptanceCheckResult(
            should_block=False,
            has_acceptance=True,
            message=None,
            has_new_error_patterns=False,
            new_error_pattern_files=[],
        )

    buf = io.StringIO()
    with patch.object(module, "read_json_from_stdin", return_value=payload), \
         patch.object(module, "is_subagent_environment", return_value=False), \
         patch.object(module, "check_acceptance_status", side_effect=_fake_check_acceptance_status), \
         patch.object(module, "_extract_ticket_or_skip", return_value="0.0.0-W1-999"), \
         patch.object(module, "save_check_log"), \
         redirect_stdout(buf):
        rc = module.main()

    return rc, buf.getvalue(), call_marker["called"], module


class TestNonCompleteCommandFastPath:
    """非 complete 命令維持原有低成本短路，不受本次修復影響（W14-034 意圖保留）。"""

    def test_effort_low_non_complete_short_circuits(self):
        payload = _payload("git status", effort_level="low")
        rc, _, called, module = _run_main(payload)
        assert rc == module.EXIT_SUCCESS
        assert called is False, "非 complete 命令不應觸發完整驗收檢查"

    def test_effort_high_non_complete_short_circuits(self):
        payload = _payload("git status", effort_level="high")
        rc, _, called, module = _run_main(payload)
        assert rc == module.EXIT_SUCCESS
        assert called is False, "非 complete 命令即使 effort=high 也應走 fast-path，不觸發完整檢查"


class TestCompleteCommandFullValidation:
    """ticket track complete 命令一律執行完整驗收檢查，不受 effort 短路豁免（本票修復核心）。"""

    def test_effort_low_complete_runs_full_validation(self):
        """回歸測試：修復前此案例會在完整驗證前短路放行（0.2.1-W3-014 實證場景）。"""
        payload = _payload("ticket track complete 0.0.0-W1-999", effort_level="low")
        rc, _, called, module = _run_main(payload)
        assert called is True, (
            "effort=low 時 ticket track complete 命令必須執行完整驗收檢查，"
            "不可短路放行（0.2.1-W3-014 迴歸）"
        )
        assert rc == module.EXIT_SUCCESS

    def test_effort_high_complete_runs_full_validation(self):
        payload = _payload("ticket track complete 0.0.0-W1-999", effort_level="high")
        rc, _, called, module = _run_main(payload)
        assert called is True
        assert rc == module.EXIT_SUCCESS


class TestBatchCompleteAlsoCovered:
    """is_complete_command 同時涵蓋 batch-complete，確認修復不僅限單一 complete 語法。"""

    def test_effort_low_batch_complete_runs_full_validation(self):
        payload = _payload("ticket track batch-complete 0.0.0-W1-999,0.0.0-W1-998", effort_level="low")
        rc, _, called, module = _run_main(payload)
        assert called is True


class TestInvalidMultiViewStatusIsIntercepted:
    """
    0.2.1-W3-014 實證場景：effort=low + 非法 multi_view_status 值 (single_view_ana)。

    修復前：effort=low 短路發生在命令判斷之前，acceptance-gate 完全不執行，
    非法值靜默通過。
    修復後：complete 命令一律進入 check_acceptance_status，multi_view_checker
    得以實際執行並產生 WARNING。
    """

    def test_ana_ticket_invalid_multi_view_status_triggers_warning_even_at_effort_low(
        self, tmp_path
    ):
        module = _load_hook_module()

        # 建立最小 ANA ticket，Solution 含非法 multi_view_status 值
        ticket_dir = tmp_path / "docs" / "work-logs" / "v0.0.0" / "tickets"
        ticket_dir.mkdir(parents=True)
        ticket_file = ticket_dir / "0.0.0-W1-999.md"
        ticket_file.write_text(
            """---
id: 0.0.0-W1-999
title: dummy
type: ANA
status: in_progress
children: []
---

## Solution

multi_view_status: single_view_ana

## Test Results

placeholder
""",
            encoding="utf-8",
        )

        payload = _payload("ticket track complete 0.0.0-W1-999", effort_level="low")

        buf = io.StringIO()
        with patch.object(module, "read_json_from_stdin", return_value=payload), \
             patch.object(module, "is_subagent_environment", return_value=False), \
             patch.object(module, "get_project_root", return_value=tmp_path), \
             patch.object(module, "find_ticket_file", return_value=ticket_file), \
             patch.object(module, "check_children_completed_from_frontmatter", return_value=(False, None)), \
             patch.object(module, "verify_acceptance_record", return_value=(False, None, True, True)), \
             patch.object(module, "find_pending_sibling_tickets", return_value=[]), \
             patch.object(module, "check_error_pattern_conflicts", return_value=[]), \
             patch.object(module, "save_check_log"), \
             redirect_stdout(buf):
            rc = module.main()

        output = buf.getvalue()
        assert rc == module.EXIT_SUCCESS
        assert "multi_view_status" in output or "single_view_ana" in output, (
            "effort=low 時非法 multi_view_status 值必須被 acceptance-gate 偵測並提示，"
            "而非如修復前那樣完全不執行檢查（0.2.1-W3-014 迴歸驗證）"
        )
