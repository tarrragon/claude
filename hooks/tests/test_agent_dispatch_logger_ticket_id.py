"""agent-dispatch-logger 的 ticket_id 擷取：多層子票號完整、緊接中文字仍完整、標籤優先。

驗證：
1. 多層子票號（主幹加兩層以上點號後綴）完整記錄（修正前截成單層後綴）
2. 票號緊接中文字時仍完整擷取
3. prompt 同時提到背景票與「Ticket:」標籤的目標票時，取標籤後的目標票
   （修正前取第一個出現的票號）
4. 正向對照：單層子票號、無後綴、無票號的結果與修正前相同

票號以片段組裝，避免測試檔內出現字面票號（框架檔禁引用專案層級識別符）。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "agent-dispatch-logger-hook.py"

ROOT_ID = "9.9.9" + "-W1-" + "7"          # 主幹
CHILD = ROOT_ID + ".2"                     # 單層子票號
GRANDCHILD = ROOT_ID + ".2.3"              # 兩層子票號
DEEP = ROOT_ID + ".2.3.1"                  # 三層子票號
OTHER = "9.9.9" + "-W1-" + "5"             # 背景票


@pytest.fixture
def hook_mod():
    spec = importlib.util.spec_from_file_location("agent_dispatch_logger_ticket_id", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("prompt,expected", [
    (f"執行 {GRANDCHILD} 補測試", GRANDCHILD),
    (f"執行 {DEEP} 補測試", DEEP),
    (f"執行 {GRANDCHILD}的修正", GRANDCHILD),
    (f"處理{CHILD}的修正", CHILD),
    (f"背景見 {OTHER}\nTicket: {GRANDCHILD}", GRANDCHILD),
])
def test_ticket_id_extracted_in_full(hook_mod, prompt, expected):
    assert hook_mod.extract_ticket_id(prompt) == expected


@pytest.mark.parametrize("prompt,expected", [
    (f"執行 {CHILD} 補測試", CHILD),
    (f"執行 {ROOT_ID} 補測試", ROOT_ID),
    ("沒有票號的派發", ""),
    ("", ""),
])
def test_unchanged_cases(hook_mod, prompt, expected):
    # 正向對照：修正前後結果相同
    assert hook_mod.extract_ticket_id(prompt) == expected


def test_log_entry_records_full_child_id(hook_mod, monkeypatch, tmp_path):
    monkeypatch.setattr(hook_mod, "get_project_root", lambda: str(tmp_path))
    input_data = {
        "tool_name": "Agent",
        "tool_input": {"prompt": f"Ticket: {GRANDCHILD} 執行", "description": "d",
                       "subagent_type": "thyme-python-developer"},
        "tool_response": {"result": "done"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(input_data)))
    with pytest.raises(SystemExit):
        hook_mod.main()
    line = (tmp_path / hook_mod.LOG_DIR / hook_mod.LOG_FILE).read_text(encoding="utf-8").strip()
    assert json.loads(line)["ticket_id"] == GRANDCHILD
