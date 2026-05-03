"""
skill-cli-error-feedback-hook 測試套件

驗證 envelope 偵測 + 既有 SKILL 引導缺陷偵測流程：

純函式：
- is_envelope_output: stderr/stdout 含 marker → True；皆無 → False
- is_skill_cli_command / is_excluded_error / detect_skill_error_type 既有覆蓋

主流程整合（依 ticket Context Bundle 5 案例）：
1. envelope 命中（stderr 含 marker）→ 不輸出 additionalContext
2. envelope 命中（stdout 含 marker）→ 不輸出 additionalContext
3. envelope 未命中 + SKILL_ERROR_PATTERNS 命中 → 輸出 SKILL_CLI_ERROR_FEEDBACK_TEMPLATE
4. envelope 未命中 + EXCLUDED_ERROR_PATTERNS 命中 → 跳過
5. envelope 未命中 + 無任何 error pattern 命中 → 跳過
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

# 動態導入（檔名含 dash）
hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "skill-cli-error-feedback-hook.py"
spec = importlib.util.spec_from_file_location("skill_cli_error_feedback_hook", hook_file)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


# ----------------------------------------------------------------------------
# Marker 同步驗證
# ----------------------------------------------------------------------------


def test_envelope_marker_value():
    """marker 字面值必須與 messages.py 同步。"""
    assert hook.ENVELOPE_VERSION_MARKER == "__error_envelope_v1__"


# ----------------------------------------------------------------------------
# is_envelope_output 純函式測試
# ----------------------------------------------------------------------------


def test_is_envelope_output_stderr_hit():
    assert hook.is_envelope_output("error __error_envelope_v1__ details", "") is True


def test_is_envelope_output_stdout_hit():
    assert hook.is_envelope_output("", "payload __error_envelope_v1__ end") is True


def test_is_envelope_output_both_empty():
    assert hook.is_envelope_output("", "") is False


def test_is_envelope_output_no_marker():
    assert hook.is_envelope_output("ticket not found", "") is False


# ----------------------------------------------------------------------------
# 主流程整合測試（mock stdin）
# ----------------------------------------------------------------------------


def _make_input(command: str, stderr: str = "", stdout: str = "", exit_code: int = 1) -> str:
    return json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {
            "stderr": stderr,
            "stdout": stdout,
            "exit_code": exit_code,
        },
    })


def _run_main(stdin_text: str, capsys):
    with patch("sys.stdin.read", return_value=stdin_text):
        rc = hook.main()
    captured = capsys.readouterr()
    return rc, captured.out


def test_case_1_envelope_in_stderr_skips_feedback(capsys):
    """情境 1: envelope 命中（stderr）→ 不輸出 additionalContext。"""
    stdin = _make_input(
        "ticket track claim 0.18.0-W17-999",
        stderr="[ERROR] something __error_envelope_v1__ details",
    )
    rc, out = _run_main(stdin, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_case_2_envelope_in_stdout_skips_feedback(capsys):
    """情境 2: envelope 命中（stdout）→ 不輸出 additionalContext。"""
    stdin = _make_input(
        "ticket track create --type FOO --title bar",
        stdout="result __error_envelope_v1__ trailing",
    )
    rc, out = _run_main(stdin, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_case_3_skill_error_pattern_without_envelope_emits_feedback(capsys):
    """情境 3: envelope 未命中 + SKILL_ERROR_PATTERNS 命中 → 輸出引導。"""
    stdin = _make_input(
        "ticket track claim --bogus-flag x",
        stderr="ticket: error: unrecognized arguments: --bogus-flag",
    )
    rc, out = _run_main(stdin, capsys)
    assert rc == 0
    payload = json.loads(out)
    additional = payload["hookSpecificOutput"].get("additionalContext", "")
    assert "[SKILL 引導品質回饋]" in additional
    assert "參數不存在" in additional


def test_case_4_excluded_error_without_envelope_skips(capsys):
    """情境 4: envelope 未命中 + EXCLUDED_ERROR_PATTERNS 命中 → 跳過。"""
    stdin = _make_input(
        "ticket track claim 0.99.0-W1-999",
        stderr="ticket not found: 0.99.0-W1-999",
    )
    rc, out = _run_main(stdin, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]


def test_case_5_no_pattern_match_skips(capsys):
    """情境 5: envelope 未命中 + 無任何 error pattern → 跳過。"""
    stdin = _make_input(
        "ticket track summary",
        stderr="some unrelated runtime hiccup",
    )
    rc, out = _run_main(stdin, capsys)
    assert rc == 0
    payload = json.loads(out)
    assert "additionalContext" not in payload["hookSpecificOutput"]
