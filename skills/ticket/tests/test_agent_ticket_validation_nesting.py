"""
agent-ticket-validation-hook 守衛改判實際巢狀層數。

兩個量的區別：被派發票的樹深度（parent_id 鏈）不等於派發者所處的平台巢狀層數。
- 主線程派發（payload 無 agent_id）：不受被派發票樹深度限制。
- 子代理人派發（payload 有 agent_id）：以派發者持有票的 can_descend 判定；
  持有票映射缺失時退回被派發票深度判準（保守）。
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

import importlib.util
from pathlib import Path


def _load_hook_module():
    """動態 import hook（檔名含 dash）。"""
    hook_path = (
        Path(__file__).resolve().parents[1] / "hooks" / "agent-ticket-validation-hook.py"
    )
    spec = importlib.util.spec_from_file_location("agent_ticket_validation_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(prompt: str, subagent_type: str = "thyme-python-developer") -> dict:
    return {"tool_input": {"prompt": prompt, "subagent_type": subagent_type}}


def _run(module, payload, depths, holder=None):
    """depths: ticket_id -> depth；holder: 派發者持有票（None 表映射缺失）。"""
    buf = io.StringIO()
    with patch.object(module, "validate_ticket", return_value=(True, None)), \
            patch.object(module, "compute_depth", side_effect=lambda t: depths[t]), \
            patch.object(module, "find_dispatcher_ticket", return_value=holder, create=True), \
            patch.object(module, "read_json_from_stdin", return_value=payload), \
            patch.object(module, "prompt_references_handoff_ticket", return_value=False), \
            patch.object(module, "save_check_log"), \
            redirect_stdout(buf):
        rc = module.main()
    return rc, json.loads(buf.getvalue())


def test_main_thread_dispatch_depth_4_allows():
    """主線程派發深度 4 的票放行（修正前紅）。"""
    module = _load_hook_module()
    rc, parsed = _run(module, _payload("Ticket: 1.0.0-W1-004"), {"1.0.0-W1-004": 4})
    assert rc == module.EXIT_SUCCESS
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_subagent_holding_depth_3_is_blocked():
    """對照：子代理人持有深度 3 的票再往下派發被擋。"""
    module = _load_hook_module()
    payload = {**_payload("Ticket: 1.0.0-W1-004"), "agent_id": "abc"}
    rc, parsed = _run(module, payload, {"1.0.0-W1-004": 4, "1.0.0-W1-013": 3}, holder="1.0.0-W1-013")
    assert rc == module.EXIT_BLOCK
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_subagent_holding_depth_2_allows_depth_3_target():
    module = _load_hook_module()
    payload = {**_payload("Ticket: 1.0.0-W1-003"), "agent_id": "abc"}
    rc, _ = _run(module, payload, {"1.0.0-W1-003": 3, "1.0.0-W1-012": 2}, holder="1.0.0-W1-012")
    assert rc == module.EXIT_SUCCESS


def test_subagent_unmapped_holder_falls_back_to_target_depth():
    """派發者映射缺失：退回被派發票深度判準（維持舊行為）。"""
    module = _load_hook_module()
    payload = {**_payload("Ticket: 1.0.0-W1-004"), "agent_id": "abc"}
    rc, _ = _run(module, payload, {"1.0.0-W1-004": 4}, holder=None)
    assert rc == module.EXIT_BLOCK
