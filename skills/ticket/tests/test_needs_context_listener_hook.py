"""
測試 needs-context-listener-hook 訊息中性化（W3-097，源自 W3-095 Phase 3 方案 V）。

目標：hook systemMessage 不預設 caller 為代理人，對 PM 自填與代理人回報情境皆適用。

涵蓋 acceptance：
- AC1：訊息中性語意（不含「代理人」「agent」「已回報」等預設 caller 詞彙）
- AC2：訊息格式含 ticket_id 與「請 PM 確認是否需補料或評估後續動作」
- AC3：迴歸保護 --section 非 NeedsContext 時不輸出 systemMessage
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
        / "needs-context-listener-hook.py"
    )
    spec = importlib.util.spec_from_file_location("needs_context_listener_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main_logic(payload: dict) -> tuple[int, str]:
    module = _load_hook_module()

    buf = io.StringIO()
    with patch.object(module, "read_json_from_stdin", return_value=payload), redirect_stdout(buf):
        rc = module.main_logic()
    return rc, buf.getvalue()


def _payload_for(command: str, success: bool = True) -> dict:
    return {
        "tool_input": {"command": command},
        "tool_response": {"success": success},
    }


class TestMessageNeutrality:
    def test_message_is_neutral_no_agent_assumption(self):
        """AC1：message 不含預設 caller=代理人的詞彙。"""
        rc, out = _run_main_logic(
            _payload_for(
                'ticket track append-log 0.19.0-W3-097 --section "NeedsContext" "..."'
            )
        )
        assert rc == 0
        assert out.strip(), "expected systemMessage output"
        payload = json.loads(out)
        msg = payload["hookSpecificOutput"]["additionalContext"]

        # 中性化：不預設 caller 是代理人
        forbidden = ["代理人", "agent", "已回報"]
        for word in forbidden:
            assert word not in msg, f"訊息應為中性語意，不應含 '{word}'：{msg!r}"

    def test_message_format_matches_spec(self):
        """AC2：訊息含 ticket_id + 「請 PM 確認是否需補料或評估後續動作」。"""
        ticket_id = "0.19.0-W3-097"
        rc, out = _run_main_logic(
            _payload_for(
                f'ticket track append-log {ticket_id} --section "NeedsContext" "..."'
            )
        )
        assert rc == 0
        payload = json.loads(out)
        msg = payload["hookSpecificOutput"]["additionalContext"]

        assert ticket_id in msg, f"訊息應含 ticket_id={ticket_id}：{msg!r}"
        assert "請 PM 確認是否需補料或評估後續動作" in msg, (
            f"訊息應含規格指定字串：{msg!r}"
        )
        assert "[NeedsContext]" in msg, f"訊息應含 [NeedsContext] 前綴：{msg!r}"


class TestRegressionGuards:
    def test_non_needscontext_section_no_message(self):
        """AC3 迴歸：--section 非 NeedsContext 時不輸出 systemMessage。"""
        rc, out = _run_main_logic(
            _payload_for(
                'ticket track append-log 0.19.0-W3-097 --section "Solution" "..."'
            )
        )
        assert rc == 0
        assert out.strip() == "", f"非 NeedsContext section 不應輸出，實際：{out!r}"

    def test_failed_command_no_message(self):
        """迴歸：tool_response.success=False 時不通知（避免誤報）。"""
        rc, out = _run_main_logic(
            _payload_for(
                'ticket track append-log 0.19.0-W3-097 --section "NeedsContext" "..."',
                success=False,
            )
        )
        assert rc == 0
        assert out.strip() == "", f"失敗命令不應輸出，實際：{out!r}"
