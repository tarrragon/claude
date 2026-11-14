"""
external-query-guide 只提醒、不代用戶核可權限（3.3.0-W1-013.2）。

PreToolUse 的 allow 會略過平台權限提示，WebFetch 對 allowlist 外的網域因此不再
提示。本 hook 是提醒類：指導訊息改走 additionalContext（exit 0 的 stderr 模型看
不到），不輸出 permissionDecision。

E1 對照：外部查詢工具輸出 additionalContext，非外部查詢工具不輸出任何 JSON。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


def _load_hook_module():
    hook_path = Path(__file__).resolve().parents[1] / "external-query-guide-hook.py"
    spec = importlib.util.spec_from_file_location("external_query_guide_no_allow", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(monkeypatch, capsys, payload):
    hook = _load_hook_module()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    rc = hook.main()
    out = capsys.readouterr().out.strip()
    return rc, (json.loads(out) if out else None)


@pytest.mark.parametrize(
    "tool_name,tool_input",
    [
        ("WebFetch", {"url": "https://example.com/a", "prompt": "x"}),
        ("WebSearch", {"query": "x"}),
    ],
)
def test_external_query_emits_context_without_decision(monkeypatch, capsys, tool_name, tool_input):
    rc, obj = _run(monkeypatch, capsys, {"tool_name": tool_name, "tool_input": tool_input})
    assert rc == 0
    hso = obj["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert "permissionDecisionReason" not in hso
    assert tool_name in hso["additionalContext"]
    assert "oregano-data-miner" in hso["additionalContext"]


def test_non_external_tool_emits_nothing(monkeypatch, capsys):
    rc, obj = _run(monkeypatch, capsys, {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}})
    assert rc == 0
    assert obj is None
