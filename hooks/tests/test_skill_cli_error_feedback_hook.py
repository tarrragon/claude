"""
cli-error-feedback-hook envelope 抑制邏輯測試套件（移植自 skill-cli-error-feedback-hook.py，0.0.1-W1-005）

驗證 envelope 偵測 + 既有 SKILL 引導缺陷偵測流程（check_skill_cli_error 子邏輯）：

純函式：
- is_envelope_output: stderr/stdout 含 marker → True；皆無 → False
- is_skill_cli_command / is_excluded_error / detect_skill_error_type 既有覆蓋

主流程整合（依 ticket Context Bundle 5 案例）：
1. envelope 命中（stderr 含 marker）→ 不輸出 additionalContext
2. envelope 命中（stdout 含 marker）→ 不輸出 additionalContext
3. envelope 未命中 + SKILL_ERROR_PATTERNS 命中 → 輸出 SKILL_CLI_ERROR_FEEDBACK_TEMPLATE
4. envelope 未命中 + EXCLUDED_ERROR_PATTERNS 命中 → 跳過
5. envelope 未命中 + 無任何 error pattern 命中 → 跳過

範圍註記（0.0.1-W1-005）：原檔另含 W3-073 系統功能缺失分類（classify_error /
detect_system_gap / CLASSIFICATION_* / SYSTEM_GAP_FEEDBACK_TEMPLATE），驗證後
確認該子功能亦未被 cli-error-feedback-hook.py 承接。依 ticket 範圍限定（僅移植
envelope 抑制邏輯），本檔不含該部分測試；W3-073 承接與否另建 follow-up ticket。

0.0.1-W1-010 補充：
- extract_command_summary 對單一命令與複合命令兩情境的 command_base 取值
- SKILL_CLI_ERROR_FEEDBACK_TEMPLATE 泛化後不再預設「SKILL 引導不足」為
  唯一成因，且對任一成因皆保留建 ticket 出口
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

# 動態導入（檔名含 dash）
hooks_path = Path(__file__).parent.parent.parent / "skills" / "ticket" / "hooks"
hook_file = hooks_path / "cli-error-feedback-hook.py"
spec = importlib.util.spec_from_file_location("cli_error_feedback_hook", hook_file)
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
    assert "[CLI 錯誤偵測]" in additional
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


# ----------------------------------------------------------------------------
# extract_command_summary（0.0.1-W1-010：command_base 取值修正）
# ----------------------------------------------------------------------------


def test_extract_command_summary_simple_command_returns_first_token():
    """單一命令：command_base 為第一個 token（既有行為維持）。"""
    _, command_base = hook.extract_command_summary("ticket track claim --bogus-flag x")
    assert command_base == "ticket"


def test_extract_command_summary_slash_prefixed_command_strips_slash():
    """`/ticket` 前綴：command_base 去除斜線（既有行為維持）。"""
    _, command_base = hook.extract_command_summary("/ticket track claim x")
    assert command_base == "ticket"


def test_extract_command_summary_compound_command_returns_actual_cli_segment():
    """複合命令：command_base 取實際觸發 CLI 的片段，而非整條命令的第一個 token。

    重現 0.0.1-W1-008 分析中自然觸發的真實案例：`cd <path>; ticket ...`
    修復前會誤取 `cd`，使後續 `{command_base} --help` 建議變成無意義的
    `cd --help`（cd 是 shell builtin，無 --help）。
    """
    command = (
        "cd /Users/mac-eric/project/flutter_balance 2>/dev/null; "
        "ticket track set-where 0.19.0-W3-071 --layer Domain"
    )
    _, command_base = hook.extract_command_summary(command)
    assert command_base == "ticket"
    assert command_base != "cd"


def test_extract_command_summary_no_skill_cli_segment_falls_back_to_first_token():
    """複合命令但無 ticket/skill 片段：fallback 為整條命令的第一個 token。"""
    _, command_base = hook.extract_command_summary("ls -la; echo done")
    assert command_base == "ls"


def test_extract_command_summary_summary_still_truncates_at_80_chars():
    """command_summary 截斷行為不受本次修正影響（僅 command_base 改變）。"""
    long_command = "ticket track set-where 0.19.0-W3-071 --layer " + "x" * 60
    command_summary, _ = hook.extract_command_summary(long_command)
    assert len(command_summary) == 80


# ----------------------------------------------------------------------------
# SKILL_CLI_ERROR_FEEDBACK_TEMPLATE 泛化（0.0.1-W1-010）
# ----------------------------------------------------------------------------


def test_feedback_template_does_not_default_to_skill_guidance_as_sole_cause():
    """訊息不再以「SKILL 引導不足」為唯一成因描述（僅列為多個可能成因之一）。"""
    message = hook.SKILL_CLI_ERROR_FEEDBACK_TEMPLATE.format(
        error_type="參數不存在",
        command_summary="ticket track set-where 0 --layer Domain",
        command_base="ticket",
    )
    assert "可能成因" in message
    assert "功能尚未實作" in message
    assert "SKILL 引導不足" in message  # 仍是候選成因之一，但非唯一


def test_feedback_template_preserves_ticket_creation_exit_for_both_causes():
    """訊息對「功能缺口」與「文件缺口」兩種成因皆保留對應的建 ticket 出口。"""
    message = hook.SKILL_CLI_ERROR_FEEDBACK_TEMPLATE.format(
        error_type="參數不存在",
        command_summary="ticket track set-where 0 --layer Domain",
        command_base="ticket",
    )
    assert "ticket create --type ANA" in message  # 功能缺口出口
    assert "ticket create --type ADJ" in message  # 文件缺口出口


def test_main_end_to_end_compound_command_suggests_actual_cli_help_not_shell_builtin(capsys):
    """端到端重現 0.0.1-W1-008 實測案例：複合命令觸發時，建議語法為
    `ticket --help` 而非無意義的 `cd --help`。
    """
    stdin = _make_input(
        "cd /Users/mac-eric/project/flutter_balance 2>/dev/null; "
        "ticket track set-where 0.19.0-W3-071 --layer Domain",
        stderr="ticket: error: unrecognized arguments: --layer Domain",
    )
    rc, out = _run_main(stdin, capsys)
    assert rc == 0
    payload = json.loads(out)
    additional = payload["hookSpecificOutput"].get("additionalContext", "")
    assert "ticket --help" in additional
    assert "cd --help" not in additional
