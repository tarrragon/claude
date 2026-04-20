"""
session-start-scheduler-hint-hook 測試套件

驗證：
1. 正常：resume 有結果 → additionalContext 顯示 resume 輸出
2. Fallback：resume 無結果 → 呼叫 next（--format=list --top 1）
3. 雙無：resume + next 皆無 → suppressOutput=True
4. CLI 錯誤：subprocess 失敗 → 靜默不阻塞 session（stderr 有記錄）
5. Timeout：subprocess 超時 → 靜默不阻塞
6. hookEventName 必為 SessionStart
7. additionalContext 為字串
8. 輸出為合法 JSON
"""

import json
import subprocess
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock


# 動態載入 hook（檔名含 dash）
HOOK_PATH = Path(__file__).parent.parent / "session-start-scheduler-hint-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "session_start_scheduler_hint_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mk_completed(stdout: str, returncode: int = 0, stderr: str = ""):
    m = MagicMock(spec=subprocess.CompletedProcess)
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# 1. resume 有待恢復 → 顯示 resume 輸出
# ---------------------------------------------------------------------------
def test_resume_has_pending_uses_resume_output():
    hook = load_hook_module()
    resume_out = "─────\n（待恢復 handoff / top 3）\n  1. 0.18.0-W17-001\n"
    with patch.object(hook.subprocess, "run", return_value=_mk_completed(resume_out)) as mrun:
        ctx = hook.fetch_scheduler_context(logger=MagicMock())
    assert resume_out.strip() in ctx
    # 只會呼叫一次 resume，不會 fallback 到 next
    assert mrun.call_count == 1
    called_args = mrun.call_args[0][0]
    assert "runqueue" in called_args
    assert "--context=resume" in called_args


# ---------------------------------------------------------------------------
# 2. resume 無結果 → fallback 呼叫 next
# ---------------------------------------------------------------------------
def test_resume_empty_falls_back_to_next():
    hook = load_hook_module()
    empty_resume = "─────\n（無可執行 Ticket；blockedBy 全非空或 status 非 pending）"
    next_out = "─────\n  1. [P0] 0.18.0-W17-005  補上 append-log"

    def side_effect(cmd, **kwargs):
        if "--context=resume" in cmd:
            return _mk_completed(empty_resume)
        return _mk_completed(next_out)

    with patch.object(hook.subprocess, "run", side_effect=side_effect) as mrun:
        ctx = hook.fetch_scheduler_context(logger=MagicMock())

    assert next_out.strip() in ctx
    assert mrun.call_count == 2
    # 第二次呼叫含 --format=list
    second_cmd = mrun.call_args_list[1][0][0]
    assert "--format=list" in second_cmd
    assert "--top" in second_cmd


# ---------------------------------------------------------------------------
# 3. resume + next 皆無 → 回傳 None
# ---------------------------------------------------------------------------
def test_both_empty_returns_none():
    hook = load_hook_module()
    empty = "（無可執行 Ticket；blockedBy 全非空或 status 非 pending）"
    with patch.object(hook.subprocess, "run", return_value=_mk_completed(empty)):
        ctx = hook.fetch_scheduler_context(logger=MagicMock())
    assert ctx is None


# ---------------------------------------------------------------------------
# 4. subprocess 異常 → 靜默（stderr 記錄由 logger 負責）
# ---------------------------------------------------------------------------
def test_subprocess_error_returns_none_and_logs(capsys):
    hook = load_hook_module()
    logger = MagicMock()
    with patch.object(hook.subprocess, "run", side_effect=FileNotFoundError("ticket")):
        ctx = hook.fetch_scheduler_context(logger=logger)
    assert ctx is None
    # 規則 4：必須有錯誤記錄
    assert logger.error.called or logger.warning.called


# ---------------------------------------------------------------------------
# 5. subprocess timeout → 靜默
# ---------------------------------------------------------------------------
def test_subprocess_timeout_returns_none():
    hook = load_hook_module()
    logger = MagicMock()
    with patch.object(
        hook.subprocess, "run",
        side_effect=subprocess.TimeoutExpired(cmd="ticket", timeout=5),
    ):
        ctx = hook.fetch_scheduler_context(logger=logger)
    assert ctx is None
    assert logger.error.called or logger.warning.called


# ---------------------------------------------------------------------------
# 6. hookEventName 必為 SessionStart
# ---------------------------------------------------------------------------
def test_build_output_has_session_start_event():
    hook = load_hook_module()
    out = hook.build_hook_output("some context text")
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"


# ---------------------------------------------------------------------------
# 7. additionalContext 為字串且非空
# ---------------------------------------------------------------------------
def test_build_output_context_is_nonempty_string():
    hook = load_hook_module()
    out = hook.build_hook_output("一些排程提示")
    ac = out["hookSpecificOutput"]["additionalContext"]
    assert isinstance(ac, str)
    assert ac.strip() != ""
    assert "一些排程提示" in ac


# ---------------------------------------------------------------------------
# 8. 無排程內容 → suppressOutput=True
# ---------------------------------------------------------------------------
def test_build_output_none_suppresses():
    hook = load_hook_module()
    out = hook.build_hook_output(None)
    assert out.get("suppressOutput") is True
    assert "hookSpecificOutput" not in out


# ---------------------------------------------------------------------------
# 9. 完整輸出為合法 JSON（整合：stdin 空 + 兩次 CLI mock）
# ---------------------------------------------------------------------------
def test_main_outputs_valid_json(capsys, monkeypatch):
    hook = load_hook_module()
    resume_out = "（待恢復 handoff）\n  1. 0.18.0-W17-001"

    monkeypatch.setattr("sys.stdin", _StdinStub('{"hook_event_name":"SessionStart"}'))

    with patch.object(hook.subprocess, "run", return_value=_mk_completed(resume_out)):
        rc = hook.main()
    assert rc == 0
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert parsed["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "0.18.0-W17-001" in parsed["hookSpecificOutput"]["additionalContext"]


class _StdinStub:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text

    def isatty(self):
        return False
