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


# ----------------------------------------------------------------------------
# 286.3：分層成功判定（反向）與多陳述命令的失敗歸因
# ----------------------------------------------------------------------------

_MULTI = (
    "ticket track set-who 0.5.0-W1-286.3 basil > /dev/null 2>&1; "
    "ticket track check-acceptance 0.5.0-W1-286.3 2 3"
)
_MULTI_ERR = "usage: ticket track check-acceptance [-h]\nerror: unrecognized arguments: 3"


def test_unmasked_success_with_swallowed_output_gives_no_feedback(capsys):
    """成功但輸出被吸走（stdout 空、無 [OK]）的未遮蔽命令不給錯誤回饋。"""
    stdin = _make_input(
        "ticket track set-who 0.5.0-W1-286.3 basil > /dev/null 2>&1", exit_code=0
    )
    rc, out = _run_main(stdin, capsys)
    assert rc == 0
    assert "additionalContext" not in json.loads(out)["hookSpecificOutput"]


def test_unmasked_success_quoting_error_text_gives_no_feedback(capsys):
    """E1 對照之一：未遮蔽成功命令的 stdout 引述 usage 錯誤字樣，不誤報。"""
    stdin = _make_input(
        "ticket track full 0.5.0-W1-286.3", stdout="error: unrecognized arguments: 3",
        exit_code=0,
    )
    rc, out = _run_main(stdin, capsys)
    assert "additionalContext" not in json.loads(out)["hookSpecificOutput"]


def test_masked_command_with_error_output_still_gives_feedback(capsys):
    """E1 對照之二：被遮蔽（管線）且輸出含錯誤時仍給回饋。"""
    stdin = _make_input(
        "ticket track check-acceptance 0.5.0-W1-286.3 2 3 2>&1 | tail -5",
        stdout=_MULTI_ERR, exit_code=0,
    )
    rc, out = _run_main(stdin, capsys)
    assert "[CLI 錯誤偵測]" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


def test_failure_event_attributes_to_failing_statement(capsys):
    """多陳述命令：失敗歸因指向 check-acceptance，不是開頭的 set-who。"""
    stdin = json.dumps({
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "Bash",
        "tool_input": {"command": _MULTI},
        "error": "Exit code 2\n" + _MULTI_ERR,
    })
    rc, out = _run_main(stdin, capsys)
    additional = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "失敗命令：ticket track check-acceptance" in additional
    assert "set-who" not in additional


def test_ambiguous_multi_statement_does_not_name_a_statement():
    """輸出同時帶出兩個陳述的動詞：無法歸因，不指名任何陳述。"""
    summary, base = hook.extract_command_summary(
        _MULTI, "usage: set-who and check-acceptance error"
    )
    assert summary == hook.AMBIGUOUS_STATEMENT_SUMMARY
    assert base == "ticket"


def test_single_cli_statement_among_other_commands_keeps_whole_summary():
    summary, _ = hook.extract_command_summary(
        "cd /x 2>/dev/null; ticket track set-where 0.19.0-W3-071 --layer Domain",
        "unrecognized arguments",
    )
    assert summary.startswith("cd /x")


# ----------------------------------------------------------------------------
# 0.5.0-W1-295：遮蔽路徑 stdout 行首 [Error] 偵測（check_general_cli_failure）
# ----------------------------------------------------------------------------

import logging


def _general(command: str, stdout: str = "", stderr: str = ""):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout, "stderr": stderr},
    }
    return hook.check_general_cli_failure(payload, logging.getLogger("t295"))


def test_masked_stdout_error_prefix_is_failure():
    """正向對照：舊實作只看 stderr，此情境回傳 None。"""
    out = _general("ticket track claim X; echo done", "[Error] not found\ndone\n")
    assert out == hook.WorkflowMessages.CLI_FAILURE_HELP_REMINDER


def test_posttooluse_stderr_is_not_a_failure_signal():
    """stderr 在 PostToolUse 恆空，分支不再依賴它；即使塞值也不觸發（E1 對照）。"""
    assert _general("somecli run; echo done", "done\n", stderr="boom") is None


def test_success_stdout_with_error_words_gives_no_feedback():
    """成功命令 stdout 含錯誤字樣（非行首 [Error]）不回饋。"""
    assert _general("somecli run", "Traceback: error: failed to open\n") is None


def _general_failure(command: str, error: str):
    payload = {
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "error": error,
    }
    return hook.check_general_cli_failure(payload, logging.getLogger("t306"))


def test_failure_event_nonzero_exit_gives_feedback():
    """E2 正向對照：PostToolUseFailure 結束碼非 0 且有輸出 → 回饋。"""
    out = _general_failure("somecli run", "Exit code 1\nboom: cannot open\n")
    assert out == hook.WorkflowMessages.CLI_FAILURE_HELP_REMINDER


def test_failure_event_unparseable_error_fails_open():
    assert _general_failure("somecli run", "garbage") is None


def test_masked_stdout_error_not_at_line_start_is_not_failure():
    assert _general("ticket track query X; echo ok", "title: see [Error] in text\n") is None


def test_unmasked_stdout_error_prefix_is_not_failure():
    assert _general("ticket track query X", "[Error] quoted in ticket body\n") is None


def test_unparseable_command_fails_open():
    assert _general("ticket track claim 'X; echo", "[Error] x\n") is None


# ----------------------------------------------------------------------------
# 「已由其他 hook 處理」依命令開頭比對（子字串誤判 E2 對照）
# ----------------------------------------------------------------------------

REMINDER = hook.WorkflowMessages.CLI_FAILURE_HELP_REMINDER
_FAIL_OUT = "Exit code 1\nboom: cannot open\n"


def test_pip_install_pytest_failure_is_not_suppressed():
    assert _general_failure("pip install pytest", _FAIL_OUT) == REMINDER


def test_quoted_flutter_test_in_argument_is_not_suppressed():
    assert _general_failure("cat x | somecli 'flutter test'", _FAIL_OUT) == REMINDER


def test_quoted_dart_analyze_in_argument_is_not_suppressed():
    assert _general_failure("somecli 'dart analyze' y", _FAIL_OUT) == REMINDER


def test_real_pytest_failure_is_suppressed():
    assert _general_failure("pytest tests/test_a.py", _FAIL_OUT) is None


def test_real_flutter_test_failure_is_suppressed():
    assert _general_failure("flutter test test/a_test.dart", _FAIL_OUT) is None


def test_real_ticket_cli_failure_is_suppressed():
    assert _general_failure("ticket track claim X", _FAIL_OUT) is None


def test_prefixed_commands_are_still_suppressed():
    for cmd in (
        "FOO=1 pytest tests/a.py",
        "cd x && flutter test",
        "uv --directory x run pytest tests",
        "uv run ticket track query X",
        "cd x && dart analyze lib",
        "go vet ./...",
        "go test ./...",
    ):
        assert _general_failure(cmd, _FAIL_OUT) is None, cmd


def test_shared_judge_exception_does_not_suppress():
    with patch.object(hook, "find_test_invocations", side_effect=RuntimeError("boom")):
        assert _general_failure("pytest tests/a.py", _FAIL_OUT) == REMINDER


def test_unparseable_command_is_not_suppressed():
    assert hook.is_handled_by_other_hooks("pytest 'unclosed") is False
