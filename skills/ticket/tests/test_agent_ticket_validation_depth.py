"""
測試 agent-ticket-validation-hook 嵌套深度感知（W1-056.9 / 協議 v2 D3 強制層）。

設計依據（1.0.0-W1-056.5 「### D3 層級自覺機制」+ D2 條件 D-3）：
- 每層 agent 從 ticket depth 推算層級；depth 達 MAX_TICKET_DEPTH 時禁止再 descend。
- 強制層判準：被派發引用的 ticket 若 not can_descend(ticket_id)（depth >= MAX）
  代表該 ticket 已處最深層，不應再以其派發嵌套 Agent，故 deny 並輸出指引。
- 深度計算複用 ticket_system.lib.depth.can_descend（禁止平行實作，ARCH-020）。

涵蓋 acceptance：
- AC1：嵌套派發 prompt 的 child ticket depth 超限時 deny 並輸出指引
- AC2：豁免 agent type（Explore/general-purpose/Plan）行為不變（Never break userspace）

不變量保護（迴歸）：
- depth 合規（can_descend=True）的派發維持 allow
- 無 ticket ID / ticket 不存在等既有路徑行為不變
- depth 模組 import 失敗時 fail-open（不阻擋既有派發）
"""

from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


def _load_hook_module():
    """動態 import hook（檔名含 dash，無法用一般 import）。"""
    hook_path = (
        Path(__file__).resolve().parents[1]
        / "hooks"
        / "agent-ticket-validation-hook.py"
    )
    spec = importlib.util.spec_from_file_location(
        "agent_ticket_validation_hook", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(payload: dict, module) -> tuple[int, dict]:
    """以注入 payload 執行 hook main，回傳 (exit_code, parsed_stdout_json)。"""
    buf = io.StringIO()
    with patch.object(module, "read_json_from_stdin", return_value=payload), \
            patch.object(module, "is_handoff_recovery_mode", return_value=False), \
            patch.object(module, "save_check_log"), \
            redirect_stdout(buf):
        rc = module.main()
    out = buf.getvalue()
    parsed = json.loads(out)
    return rc, parsed


def _payload(prompt: str, subagent_type: str = "thyme-python-developer") -> dict:
    return {"tool_input": {"prompt": prompt, "subagent_type": subagent_type}}


class TestDepthSuperLimitDeny:
    """AC1：depth 達上限的 ticket 不可再 descend 嵌套派發，故 deny。"""

    def test_depth_at_limit_denies_dispatch(self):
        module = _load_hook_module()
        with patch.object(module, "validate_ticket", return_value=(True, None)), \
                patch.object(module, "can_descend", return_value=False), \
                patch.object(module, "compute_depth", return_value=3):
            rc, parsed = _run_main(_payload("Ticket: 1.0.0-W1-056.5.1"), module)

        assert rc == module.EXIT_BLOCK
        decision = parsed["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        reason = parsed["hookSpecificOutput"]["permissionDecisionReason"]
        assert "深度" in reason
        assert str(module.MAX_TICKET_DEPTH) in reason

    def test_depth_within_limit_allows_dispatch(self):
        module = _load_hook_module()
        with patch.object(module, "validate_ticket", return_value=(True, None)), \
                patch.object(module, "can_descend", return_value=True), \
                patch.object(module, "compute_depth", return_value=2):
            rc, parsed = _run_main(_payload("Ticket: 1.0.0-W1-056.5"), module)

        assert rc == module.EXIT_SUCCESS
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestExemptAgentUnaffected:
    """AC2：豁免 agent type 行為完全不變（深度檢查不觸發）。"""

    def test_explore_skips_depth_check(self):
        module = _load_hook_module()
        with patch.object(module, "can_descend", return_value=False) as mock_cd:
            rc, parsed = _run_main(
                _payload("Ticket: 1.0.0-W1-056.5.1", subagent_type="Explore"),
                module,
            )
        assert rc == module.EXIT_SUCCESS
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"
        mock_cd.assert_not_called()

    def test_general_purpose_skips_depth_check(self):
        module = _load_hook_module()
        with patch.object(module, "can_descend", return_value=False) as mock_cd:
            rc, parsed = _run_main(
                _payload("Ticket: 1.0.0-W1-056.5.1", subagent_type="general-purpose"),
                module,
            )
        assert rc == module.EXIT_SUCCESS
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"
        mock_cd.assert_not_called()

    def test_plan_skips_depth_check(self):
        module = _load_hook_module()
        with patch.object(module, "can_descend", return_value=False) as mock_cd:
            rc, parsed = _run_main(
                _payload("Ticket: 1.0.0-W1-056.5.1", subagent_type="Plan"),
                module,
            )
        assert rc == module.EXIT_SUCCESS
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"
        mock_cd.assert_not_called()


class TestImportFailureFailOpen:
    """不變量：depth 模組不可用時 fail-open，不阻擋既有派發（Never break userspace）。"""

    def test_depth_unavailable_does_not_block(self):
        module = _load_hook_module()
        with patch.object(module, "validate_ticket", return_value=(True, None)), \
                patch.object(module, "DEPTH_AVAILABLE", False):
            rc, parsed = _run_main(_payload("Ticket: 1.0.0-W1-056.5.1"), module)
        assert rc == module.EXIT_SUCCESS
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestExistingPathsUnchanged:
    """迴歸：既有驗證路徑（無 ticket / ticket 不存在）行為不變。"""

    def test_no_ticket_id_still_denies(self):
        module = _load_hook_module()
        rc, parsed = _run_main(
            _payload("沒有引用任何 ticket 的 prompt"), module
        )
        assert rc == module.EXIT_BLOCK
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_invalid_ticket_denies_before_depth_check(self):
        module = _load_hook_module()
        with patch.object(
            module, "validate_ticket", return_value=(False, "Ticket 不存在")
        ), patch.object(module, "can_descend", return_value=True) as mock_cd:
            rc, parsed = _run_main(_payload("Ticket: 9.9.9-W9-999"), module)
        assert rc == module.EXIT_BLOCK
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
        mock_cd.assert_not_called()
