"""
Agent Prompt Length Guard Hook 測試

對應 Ticket 0.18.0-W17-048.2 AC：
- Hook 在 prompt > 10 行且未含模板關鍵字時輸出軟提示（stderr），仍放行（exit 0）
- 保留 30 行硬上限（> 30 行 exit 2）
- 含模板關鍵字（如「讀取 ticket」「ticket track full」「Context Bundle」等）不觸發提示
- 既有 30 行硬上限與非 Agent/Task 工具豁免行為無 regression
"""

import importlib.util
import io
import json
import sys
from pathlib import Path


# 動態載入 hook module（檔名含連字號，無法直接 import）
_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "agent_prompt_length_guard_hook",
    _HOOKS_DIR / "agent-prompt-length-guard-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

main = _hook.main
has_template_keywords = _hook.has_template_keywords
PROMPT_LINE_LIMIT = _hook.PROMPT_LINE_LIMIT
SOFT_HINT_THRESHOLD = _hook.SOFT_HINT_THRESHOLD
TEMPLATE_KEYWORDS = _hook.TEMPLATE_KEYWORDS


# ----------------------------------------------------------------------------
# 單元測試：has_template_keywords
# ----------------------------------------------------------------------------

def test_has_template_keywords_detects_read_ticket_chinese():
    """含「讀取 ticket」應回傳 True。"""
    assert has_template_keywords("請讀取 ticket 並執行 context bundle") is True


def test_has_template_keywords_detects_ticket_track_full():
    """含「ticket track full」應回傳 True。"""
    assert has_template_keywords("執行 ticket track full 0.18.0-W1-001") is True


def test_has_template_keywords_detects_context_bundle():
    """含「Context Bundle」應回傳 True。"""
    assert has_template_keywords("依 Context Bundle 執行流程") is True


def test_has_template_keywords_empty_prompt_returns_false():
    """空字串應回傳 False。"""
    assert has_template_keywords("") is False


def test_has_template_keywords_no_keyword_returns_false():
    """無任何關鍵字應回傳 False。"""
    assert has_template_keywords("請實作 Widget 並撰寫測試") is False


# ----------------------------------------------------------------------------
# 整合測試：main() Hook 入口點
# ----------------------------------------------------------------------------

def _run_hook(monkeypatch, tool_input: dict, tool_name: str = "Agent") -> int:
    """以 monkeypatch 模擬 stdin 輸入並執行 main()。

    回傳：exit code（0=放行, 2=阻擋）
    """
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    return main()


def _make_prompt(line_count: int, keyword: str = "") -> str:
    """產生指定行數的測試 prompt，可選擇包含特定關鍵字。"""
    lines = [f"第 {i} 行" for i in range(1, line_count + 1)]
    if keyword:
        # 將關鍵字插入中間某行
        idx = min(len(lines) // 2, len(lines) - 1)
        lines[idx] = f"{lines[idx]} {keyword}"
    return "\n".join(lines)


# 8 項測試案例（對應 ticket Context Bundle「測試要求」）

def test_over_30_lines_still_blocks(monkeypatch, capsys):
    """案例 1：超過 30 行 → exit 2 + BLOCK 訊息（30 行硬上限 regression 保護）。"""
    prompt = _make_prompt(35)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "超過" in captured.err
    assert "30" in captured.err
    assert "PC-040" in captured.err


def test_15_lines_with_template_keyword_passes_silently(monkeypatch, capsys):
    """案例 2：15 行含「讀取 ticket」→ exit 0，無提示。"""
    prompt = _make_prompt(15, keyword="讀取 ticket")
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "提示" not in captured.err
    assert "W17-048" not in captured.err


def test_15_lines_without_keyword_emits_soft_hint(monkeypatch, capsys):
    """案例 3：15 行缺關鍵字 → exit 0 + SOFT_HINT 訊息。"""
    prompt = _make_prompt(15)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "提示" in captured.err
    assert "W17-048" in captured.err
    assert "15 行" in captured.err


def test_8_lines_never_emits_hint(monkeypatch, capsys):
    """案例 4：8 行（低於 threshold）→ exit 0，無提示。"""
    prompt = _make_prompt(8)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""


def test_boundary_exactly_10_lines_no_hint(monkeypatch, capsys):
    """案例 5：剛好 10 行缺關鍵字 → exit 0，無提示（threshold 是 > 10，不含等於）。"""
    prompt = _make_prompt(10)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""


def test_boundary_exactly_11_lines_emits_hint(monkeypatch, capsys):
    """案例 6：剛好 11 行缺關鍵字 → exit 0 + SOFT_HINT（邊界上方）。"""
    prompt = _make_prompt(11)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "提示" in captured.err
    assert "11 行" in captured.err


def test_30_lines_with_keyword_passes_silently(monkeypatch, capsys):
    """案例 7：30 行（等於硬上限）含「ticket track full」→ exit 0，無提示。"""
    prompt = _make_prompt(30, keyword="ticket track full")
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "提示" not in captured.err
    assert "超過" not in captured.err


def test_non_agent_tool_passes_without_check(monkeypatch, capsys):
    """案例 8：非 Agent/Task 工具（如 Bash）→ exit 0 直接放行，無任何輸出。"""
    prompt = _make_prompt(50)  # 即便超過 30 行
    exit_code = _run_hook(monkeypatch, {"prompt": prompt}, tool_name="Bash")
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""


# ----------------------------------------------------------------------------
# 額外邊界測試：保護既有行為不 regression
# ----------------------------------------------------------------------------

def test_empty_prompt_passes(monkeypatch, capsys):
    """空 prompt 應放行。"""
    exit_code = _run_hook(monkeypatch, {"prompt": ""})
    assert exit_code == 0


def test_task_tool_also_checked(monkeypatch, capsys):
    """Task 工具（與 Agent 同）也應套用檢查。"""
    prompt = _make_prompt(35)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt}, tool_name="Task")
    assert exit_code == 2


def test_31_lines_without_keyword_blocks(monkeypatch, capsys):
    """31 行（剛超硬上限）即便缺關鍵字也應 BLOCK 非軟提示。"""
    prompt = _make_prompt(31)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "超過" in captured.err
    # 不應同時輸出軟提示
    assert "W17-048" not in captured.err


def test_tool_input_as_json_string(monkeypatch, capsys):
    """tool_input 以 JSON 字串傳入時仍應正確解析。"""
    prompt = _make_prompt(35)
    payload = {
        "tool_name": "Agent",
        "tool_input": json.dumps({"prompt": prompt}),
    }
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    exit_code = main()
    assert exit_code == 2


def test_constants_sanity():
    """常數 sanity check：SOFT_HINT_THRESHOLD < PROMPT_LINE_LIMIT。"""
    assert SOFT_HINT_THRESHOLD < PROMPT_LINE_LIMIT
    assert SOFT_HINT_THRESHOLD == 10
    assert PROMPT_LINE_LIMIT == 30
    assert len(TEMPLATE_KEYWORDS) >= 1
