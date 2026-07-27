"""
測試 agent-ticket-validation-hook 的 TICKET_EXEMPT_AGENT_TYPES 白名單（0.2.1-W3-010）。

設計依據：
- 唯讀常駐審查委員（basil-writing-critic / linux）符合 hook 既有豁免判準
  （tools 僅唯讀，不產生 Edit/Write/git commit 持久化副作用），
  但先前不在白名單中，導致 PM 無合規派發路徑（0.2.1-W3-009 缺口 A）。
- 本次僅擴充常數清單，不變更 is_exempt_agent_type 判斷邏輯，
  不新增第二條免 Ticket ID 路徑。

涵蓋 acceptance：
- basil-writing-critic 與 linux 無 Ticket ID 派發時 allow / exit 0
- 非白名單唯讀 agent（如 incident-responder）無 Ticket ID 派發時仍 deny / exit 2
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
        "agent_ticket_validation_hook_exempt_types", hook_path
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


def _payload(prompt: str, subagent_type: str) -> dict:
    return {"tool_input": {"prompt": prompt, "subagent_type": subagent_type}}


class TestNewExemptAgentTypesAllow:
    """basil-writing-critic / linux 無 Ticket ID 派發時應放行（不阻擋）。"""

    def test_basil_writing_critic_without_ticket_id_allows(self):
        module = _load_hook_module()
        rc, parsed = _run_main(
            _payload("審查此份 Solution 的技術正確性", "basil-writing-critic"),
            module,
        )
        assert rc == 0
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_linux_without_ticket_id_allows(self):
        module = _load_hook_module()
        rc, parsed = _run_main(
            _payload("檢視此程式碼的架構品味", "linux"),
            module,
        )
        assert rc == 0
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"


class TestNonWhitelistedReadOnlyAgentStillDenies:
    """非白名單唯讀 agent（如 incident-responder）無 Ticket ID 派發時仍應 deny（邊界案例）。"""

    def test_incident_responder_without_ticket_id_denies(self):
        module = _load_hook_module()
        rc, parsed = _run_main(
            _payload("分析此次事件的根因", "incident-responder"),
            module,
        )
        assert rc == 2
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
