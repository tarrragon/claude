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


# ----------------------------------------------------------------------------
# 0.2.1-W3-876.2：訊息改引導 `ticket track dispatch` + CLI 骨架同步驗證
# ----------------------------------------------------------------------------

def test_block_message_points_to_dispatch_command(monkeypatch, capsys):
    """BLOCK 訊息須引導使用 `ticket track dispatch`（取代舊版 append-log-only 指引）。"""
    prompt = _make_prompt(35)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "ticket track dispatch" in captured.err


def test_soft_hint_points_to_dispatch_command(monkeypatch, capsys):
    """SOFT_HINT 訊息須引導使用 `ticket track dispatch`（取代舊版手動複製模板指引）。"""
    prompt = _make_prompt(15)
    exit_code = _run_hook(monkeypatch, {"prompt": prompt})
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "ticket track dispatch" in captured.err


_DISPATCH_SKELETON_CONSTANT_NAMES = (
    "SKELETON_TEMPLATE_NORMAL",
    "SKELETON_TEMPLATE_REVIEW",
    "STAGING_PHRASE_AGENT",
    "STAGING_PHRASE_AGENT_PROMPT",
    "STAGING_PHRASE_PM",
    "STAGING_PHRASE_NONE",
    "HOOK_TICKET_REMINDER",
)


def _load_dispatch_skeleton_module():
    """直接 import `ticket_system.lib.dispatch_skeleton`（CLI 本體使用的
    骨架組裝模組），非重建物或 ast 靜態解析。

    Why：該模組刻意不 import filelock、不做檔案 I/O（見模組 docstring），
    故 hook 測試套件的獨立 python 環境（未必安裝 `filelock`）可直接匯入，
    不需繞道 ast 解析 track_dispatch.py 常數或重建組裝順序——兩者皆測「代理
    物」而非 CLI 本體，重建物與本體一旦漂移即無訊號。

    `ticket_system/__init__.py` 與 `ticket_system/lib/__init__.py` 皆不
    re-export 任何觸發 filelock 的符號（後者刻意清空 re-export 層），故僅
    需將 `.claude/skills/ticket` 加入 sys.path 即可安全匯入本模組，不會
    連帶觸發 ticket_loader -> file_lock -> filelock 的 import chain。
    """
    skills_ticket_dir = _HOOKS_DIR.parent / "skills" / "ticket"
    if str(skills_ticket_dir) not in sys.path:
        sys.path.insert(0, str(skills_ticket_dir))

    from ticket_system.lib import dispatch_skeleton

    return dispatch_skeleton


def _load_skeleton_constants():
    """回傳 `dispatch_skeleton` 模組內 `_DISPATCH_SKELETON_CONSTANT_NAMES`
    列出的骨架常數，供既有關鍵字同步測試沿用。"""
    module = _load_dispatch_skeleton_module()
    return {name: getattr(module, name) for name in _DISPATCH_SKELETON_CONSTANT_NAMES}


def test_cli_skeleton_keywords_stay_in_sync_with_hook_expectations():
    """CLI 骨架常數（SKELETON_TEMPLATE_NORMAL/REVIEW）必須仍含 hook 判定用的
    模板關鍵字，兩者一旦漂移（CLI 骨架改字但 hook 關鍵字未同步更新），會使
    hook 誤判「已用模板」為 False，導致 PM 依 dispatch CLI 產生的合規 prompt
    反而被 SOFT_HINT 誤攔。任一關鍵字缺席即測試失敗，提醒同步修正。
    """
    constants = _load_skeleton_constants()
    assert "SKELETON_TEMPLATE_NORMAL" in constants
    assert "SKELETON_TEMPLATE_REVIEW" in constants

    normal_skeleton = constants["SKELETON_TEMPLATE_NORMAL"]
    assert has_template_keywords(normal_skeleton) is True, (
        "SKELETON_TEMPLATE_NORMAL 未命中任何 TEMPLATE_KEYWORDS，"
        "CLI 骨架與 hook 關鍵字已漂移"
    )

    review_skeleton = constants["SKELETON_TEMPLATE_REVIEW"]
    assert has_template_keywords(review_skeleton) is True, (
        "SKELETON_TEMPLATE_REVIEW 未命中任何 TEMPLATE_KEYWORDS，"
        "CLI 骨架與 hook 關鍵字已漂移"
    )


# ----------------------------------------------------------------------------
# 0.2.1-W3-1146：骨架實際行數綁定 PROMPT_LINE_LIMIT（PC-040 硬上限）
#
# 既有 test_cli_skeleton_keywords_stay_in_sync_with_hook_expectations 只驗
# 「模板關鍵字」是否同步，從未比對骨架實際行數與 PROMPT_LINE_LIMIT——骨架
# 從最初的 10-15 行成長至含精準 staging 制式句（`--commit-policy agent`
# 預設）的 39 行、再疊加 hooks 目錄額外提醒（HOOK_TICKET_REMINDER）的 47-48
# 行，全程該測試維持綠燈，因為它驗的維度（關鍵字命中）與缺陷所在的維度
# （行數）不同。本節補上該缺失的綁定測試。
# ----------------------------------------------------------------------------

def _build_normal_skeleton(*, with_hook_reminder: bool) -> str:
    """呼叫 `dispatch_skeleton.build_skeleton`（CLI 本體實際使用的組裝函式）
    產生 kind="normal", commit_policy="agent" 的骨架，量測對象為 CLI 本體
    而非重建物（`track_dispatch.py::_build_skeleton` 是本函式的薄轉接層，
    兩者呼叫的是同一份 `build_skeleton`）。
    """
    module = _load_dispatch_skeleton_module()
    return module.build_skeleton(
        kind="normal",
        ticket_id="0.2.1-W3-XXXX",
        task_summary="一句話動作描述測試填空",
        agent_name="thyme-python-developer",
        commit_policy="agent",
        touches_hook_scope=with_hook_reminder,
    )


def _skeleton_line_count(skeleton: str) -> int:
    """與 hook 的 `line_count = len(prompt.strip().splitlines())` 算法一致。"""
    return len(skeleton.strip().splitlines())


def test_dispatch_skeleton_normal_agent_commit_within_prompt_limit(monkeypatch, capsys):
    """`ticket track dispatch --as <agent>`（預設 --commit-policy agent，未觸
    及 hooks 目錄）產出的骨架，逐字貼入 Agent/Task prompt 時不得被
    agent-prompt-length-guard 的 Layer 1 硬上限阻擋（PROMPT_LINE_LIMIT=30）。

    修復前現況：SKELETON_TEMPLATE_NORMAL（12 行）+ STAGING_PHRASE_AGENT
    （26 行，含中間分隔空行）合計 39 行 > 30，本測試在修復前應為紅燈。
    """
    skeleton = _build_normal_skeleton(with_hook_reminder=False)
    actual_line_count = _skeleton_line_count(skeleton)

    assert actual_line_count <= PROMPT_LINE_LIMIT, (
        f"dispatch 骨架（未觸及 hooks 目錄）實際 {actual_line_count} 行，"
        f"超過 PROMPT_LINE_LIMIT={PROMPT_LINE_LIMIT}；逐字貼入 Agent/Task "
        "prompt 會被 Layer 1 硬上限阻擋（PC-040）"
    )

    # 交叉驗證：實際餵給 hook main() 亦不應被阻擋（避免僅靠行數計算與 hook
    # 真實判斷邏輯脫節）。
    exit_code = _run_hook(monkeypatch, {"prompt": skeleton})
    assert exit_code == 0, (
        f"dispatch 骨架實際餵給 hook 仍被阻擋（exit_code={exit_code}）："
        f"{capsys.readouterr().err}"
    )


def test_dispatch_skeleton_normal_agent_commit_with_hook_scope_within_prompt_limit(
    monkeypatch, capsys,
):
    """觸及 `.claude/hooks/` 的票額外疊加 HOOK_TICKET_REMINDER，為骨架最長
    情形（現況 47-48 行）；此變體同樣不得超過 Layer 1 硬上限。
    """
    skeleton = _build_normal_skeleton(with_hook_reminder=True)
    actual_line_count = _skeleton_line_count(skeleton)

    assert actual_line_count <= PROMPT_LINE_LIMIT, (
        f"dispatch 骨架（觸及 hooks 目錄，含 HOOK_TICKET_REMINDER）實際 "
        f"{actual_line_count} 行，超過 PROMPT_LINE_LIMIT={PROMPT_LINE_LIMIT}"
    )

    exit_code = _run_hook(monkeypatch, {"prompt": skeleton})
    assert exit_code == 0, (
        f"dispatch 骨架（hooks 目錄變體）實際餵給 hook 仍被阻擋"
        f"（exit_code={exit_code}）：{capsys.readouterr().err}"
    )
