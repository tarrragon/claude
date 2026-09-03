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


class TestTriggerConditionTokenBased:
    """0.2.1-W3-1216：觸發條件改為命令位置 token 比對，不對命令字串全文
    做 regex search（避免引號內參數／文件撰寫／探針腳本誤判為實際執行）。
    """

    def test_command_only_mentions_form_in_quoted_arg_not_triggered(self):
        """命令僅以引號內文字提及該命令形態（非實際執行）不應觸發。"""
        rc, out = _run_main_logic(
            _payload_for(
                'ticket create --why "之後需要執行 ticket track append-log '
                '<id> --section NeedsContext 補料"'
            )
        )
        assert rc == 0
        assert out.strip() == "", f"僅提及命令形態不應觸發，實際：{out!r}"

    def test_unrelated_script_content_not_triggered(self):
        """完全無關腳本引數含分散字樣不應觸發（探針腳本 false positive 迴歸）。"""
        rc, out = _run_main_logic(
            _payload_for(
                'python3 create_issue.py --title "append-log NeedsContext 示範"'
            )
        )
        assert rc == 0
        assert out.strip() == "", f"無關腳本內容不應觸發，實際：{out!r}"

    def test_literal_placeholder_ticket_id_not_triggered(self):
        """擷取的 ticket_id 為字面佔位符（如 <ticket-id>）時不觸發。"""
        rc, out = _run_main_logic(
            _payload_for(
                'ticket track append-log <ticket-id> --section "NeedsContext" "..."'
            )
        )
        assert rc == 0
        assert out.strip() == "", f"字面佔位符 ticket_id 不應觸發，實際：{out!r}"

    def test_real_command_still_triggered_after_unrelated_prefix_statement(self):
        """對照組：無關語句之後接的真實命令仍須被偵測（不過度收窄）。"""
        ticket_id = "0.19.0-W3-097"
        rc, out = _run_main_logic(
            _payload_for(
                'echo "mentions git stash and append-log NeedsContext" && '
                f'ticket track append-log {ticket_id} --section "NeedsContext" "..."'
            )
        )
        assert rc == 0
        assert out.strip(), "無關前置語句不應影響後續真實命令的偵測"
        payload = json.loads(out)
        msg = payload["hookSpecificOutput"]["additionalContext"]
        assert ticket_id in msg


class TestSuccessCheckViaRealExecutionResult:
    """0.2.1-W3-1216：成功檢查改用 exit_code + stdout 成功回音，不再僅信
    tool_response.success（Bash 工具回應通常不帶此欄位）。
    """

    def test_nonzero_exit_code_no_message(self):
        """寫入被拒（如票狀態非 in_progress，CLI 以非零 exit code 退出）時不宣告已更新。"""
        rc, out = _run_main_logic(
            {
                "tool_input": {
                    "command": (
                        'ticket track append-log 0.19.0-W3-097 --section '
                        '"NeedsContext" "..."'
                    )
                },
                "tool_response": {
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "[Error] 票狀態非 in_progress，拒絕寫入",
                },
            }
        )
        assert rc == 0
        assert out.strip() == "", f"exit_code 非 0 時不應輸出，實際：{out!r}"

    def test_zero_exit_code_without_success_echo_no_message(self):
        """exit_code 為 0 但 stdout 未含 CLI 成功回音時不宣告已更新（防禦性檢查）。"""
        rc, out = _run_main_logic(
            {
                "tool_input": {
                    "command": (
                        'ticket track append-log 0.19.0-W3-097 --section '
                        '"NeedsContext" "..."'
                    )
                },
                "tool_response": {
                    "exit_code": 0,
                    "stdout": "[Warning] 未變更",
                },
            }
        )
        assert rc == 0
        assert out.strip() == "", f"未含成功回音時不應輸出，實際：{out!r}"

    def test_success_echo_in_stdout_still_triggers_message(self):
        """真實 append-log 成功（exit_code=0 且 stdout 含成功回音）時仍正常觸發。"""
        ticket_id = "0.19.0-W3-097"
        rc, out = _run_main_logic(
            {
                "tool_input": {
                    "command": (
                        f'ticket track append-log {ticket_id} --section '
                        '"NeedsContext" "..."'
                    )
                },
                "tool_response": {
                    "exit_code": 0,
                    "stdout": f"[OK] {ticket_id} 已追加日誌到 'NeedsContext'",
                },
            }
        )
        assert rc == 0
        assert out.strip(), f"成功回音應觸發訊息，實際：{out!r}"
        payload = json.loads(out)
        assert ticket_id in payload["hookSpecificOutput"]["additionalContext"]

    def test_missing_stdout_field_falls_back_to_success_flag(self):
        """tool_response 未帶 stdout 欄位時（部分 Bash 回應形態），不因此判定失敗；
        既有 success 欄位仍為判斷依據，維持既有測試樁相容性。"""
        rc, out = _run_main_logic(
            _payload_for(
                'ticket track append-log 0.19.0-W3-097 --section "NeedsContext" "..."'
            )
        )
        assert rc == 0
        assert out.strip(), f"stdout 缺席不應阻擋既有成功路徑，實際：{out!r}"
