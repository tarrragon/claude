#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
CLI 錯誤回饋合併 Hook - PostToolUse Hook

合併自:
- cli-failure-help-reminder-hook.py（一般 CLI 命令失敗提醒，PC-005 防護）
- skill-cli-error-feedback-hook.py（ticket/skill CLI 錯誤偵測，SKILL 引導不足回饋）

觸發時機: Bash 工具執行後
執行順序:
  1. check_skill_cli_error — 優先處理 ticket/skill CLI 錯誤（更 specific）
  2. check_general_cli_failure — 處理一般 CLI 失敗（若 skill CLI 已處理則跳過）

Envelope 偵測模式 (W17-008.5.5；補移植於 0.0.1-W1-005):
- 偵測 stdout/stderr 是否含 ErrorEnvelope 版本標記 `__error_envelope_v1__`
- 命中表示 CLI 已輸出完整結構化錯誤訊息（format_error 雙路徑），hook 不需重複補充引導
- Marker 來源: .claude/skills/ticket/ticket_system/lib/messages.py:ERROR_ENVELOPE_VERSION_MARKER
- 升級至 v2 時兩處須同改

行為: 不阻擋（exit 0），僅在 additionalContext 輸出提醒訊息
"""

import sys
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

_FRAMEWORK_HOOKS = str(Path(__file__).resolve().parents[3] / "hooks")
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, _FRAMEWORK_HOOKS)

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, is_subagent_environment
from lib.hook_messages import WorkflowMessages
from lib.bash_tool_response import is_bash_success, is_failure_event, parse_failure_error
from lib.ticket_command_parse import is_invocation_masked
from lib.git_command_parse import parse_command_statements
from lib.test_command_parse import find_test_invocations, _strip_launch_prefixes

# ticket CLI 錯誤輸出的固定 stdout 行首前綴
STDOUT_ERROR_PREFIX = "[Error]"

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}

# --- Skill CLI Error 常數（來自 skill-cli-error-feedback-hook） ---

# 需要偵測的 CLI 命令前綴
SKILL_CLI_COMMANDS = [
    "ticket",
    "skill",
    "/ticket",
    "/skill",
]

# SKILL 引導缺陷的錯誤模式
SKILL_ERROR_PATTERNS = [
    (r"unrecognized arguments?:", "參數不存在"),
    (r"unrecognized sub-command", "參數不存在"),
    (r"argument .+ not recognized", "參數不存在"),
    (r"error: argument .+: ", "參數格式錯誤"),
    (r"invalid argument", "參數格式錯誤"),
    (r"argument .+ expected", "參數格式錯誤"),
    (r"invalid choice: '([^']+)'", "未知子命令"),
    (r"unknown command '([^']+)'", "未知子命令"),
    (r"no such command", "未知子命令"),
]

# 排除的錯誤模式（業務邏輯錯誤）
EXCLUDED_ERROR_PATTERNS = [
    r"ticket not found",
    r"no pending ticket",
    r"ticket already .+",
    r"cannot .+ completed ticket",
    r"not in progress",
    r"blocked ticket",
    r"insufficient permission",
    r"version mismatch",
    r"no such file or directory",
    r"permission denied",
    r"json decode error",
    r"invalid json",
]

# ErrorEnvelope 版本標記（W17-008.5.5；移植自 skill-cli-error-feedback-hook.py，0.0.1-W1-005）
# 與 .claude/skills/ticket/ticket_system/lib/messages.py:ERROR_ENVELOPE_VERSION_MARKER 同步
# 升級至 v2 時兩處須同改
ENVELOPE_VERSION_MARKER = "__error_envelope_v1__"

SKILL_CLI_ERROR_FEEDBACK_TEMPLATE = """
============================================================
[CLI 錯誤偵測] 參數或子命令不符預期
============================================================

檢測到 SKILL/Ticket CLI 命令使用了不存在或格式錯誤的參數。

錯誤類型：{error_type}
失敗命令：{command_summary}

可能成因（不預設何者為真，需依實際情況判斷）：
  1. 功能尚未實作：CLI 缺對應的參數/子命令路徑
  2. SKILL 引導不足：SKILL.md 路由表或對應 references/<name>-command.md 未涵蓋此用法
  3. 使用者誤用：參數拼寫或語法有誤

建議動作：
  1. 查閱完整語法：執行 `{command_base} --help`，確認該參數/子命令是否存在
  2. 若 --help 未列出此參數/子命令 -> 屬功能缺口，建立 ticket 追蹤：
     `/ticket create --type ANA --title "[ANA] 評估 CLI 是否需支援 <參數/子命令>"`
  3. 若 --help 已列出但用法不同 -> 屬文件缺口，補充對應 references/<name>-command.md（依觸發子命令查 SKILL.md〈子命令路由表〉找對應檔案）：
     `/ticket create --type ADJ --title "[ADJ] 補充對應 references/<name>-command.md 文件"`

詳見: .claude/skills/ticket/SKILL.md〈子命令路由表〉（依子命令查對應 references/*.md）

============================================================
"""

# --- General CLI Failure 常數（來自 cli-failure-help-reminder-hook） ---

# 已由其他 Hook 處理的命令模式（避免重複提醒）
# 測試類（flutter test／dart test／pytest／uv run pytest 等）由共用測試命令判定處理；
# 以下為共用判定不涵蓋的項目，剝除啟動前綴後依敘述開頭 token 序列比對
HANDLED_BY_OTHER_HOOKS = [
    ("dart", "analyze"),
    ("go", "test"),
    ("go", "vet"),
    ("ticket",),
    ("skill",),
]

# 預期可能有 stderr 輸出但非真正失敗的命令
EXPECTED_STDERR_COMMANDS = [
    "grep",
    "rg",
    "find",
    "which",
    "command -v",
    "type ",
    "hash ",
]

# git 命令中預期的非錯誤 stderr
GIT_INFO_STDERR_PATTERNS = [
    "Already up to date",
    "Already on",
    "Switched to",
    "Your branch is",
    "nothing to commit",
    "Everything up-to-date",
]


# ============================================================================
# Skill CLI Error 子邏輯（來自 skill-cli-error-feedback-hook）
# ============================================================================

# ticket CLI 寫入命令「動作已完成、僅 auto-commit 失敗」的專用退出碼（sysexits EX_TEMPFAIL）
# ticket CLI 寫入命令的成功回音（messages.py 以 [OK] 起頭）
_CLI_SUCCESS_MARKERS = ("[OK]",)

def _find_skill_cli_token(command: str) -> Optional[str]:
    """在複合命令（含 && / ; / | 等鏈式運算子）中尋找觸發 ticket/skill CLI 的片段，
    回傳該片段的首 token（已去除 `/` 前綴）；未命中回傳 None。

    供 `is_skill_cli_command`（是否命中）與 `extract_command_summary`
    （取實際 CLI 命令而非整條複合命令的第一個 token，0.0.1-W1-010）共用，
    避免同一套片段掃描邏輯在兩處各自實作一次而漂移。
    """
    for segment in re.split(r'[|&;]+', command):
        segment = segment.strip().lstrip('(').strip()
        if not segment:
            continue
        tokens = segment.split()
        if not tokens:
            continue
        first_token = tokens[0]
        if first_token.startswith("/"):
            first_token = first_token[1:]
        if first_token in SKILL_CLI_COMMANDS:
            return first_token
    return None


def is_skill_cli_command(command: str) -> bool:
    """判斷命令是否為 ticket/skill CLI 命令（首 token 比對）"""
    return _find_skill_cli_token(command) is not None


def is_excluded_error(stderr: str, stdout: str) -> bool:
    """判斷錯誤是否為排除類型（業務邏輯錯誤）"""
    combined = (stderr + " " + stdout).lower()
    for pattern in EXCLUDED_ERROR_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return True
    return False


def is_envelope_output(stderr: str, stdout: str) -> bool:
    """偵測輸出是否含 ErrorEnvelope 版本標記。

    與 messages.py:ERROR_ENVELOPE_VERSION_MARKER 同步。命中表示 CLI
    已輸出完整結構化錯誤，hook 不需重複補充引導。
    """
    return ENVELOPE_VERSION_MARKER in stderr or ENVELOPE_VERSION_MARKER in stdout


def detect_skill_error_type(stderr: str, stdout: str) -> Optional[str]:
    """偵測 SKILL 引導缺陷錯誤類型"""
    combined = stderr + " " + stdout
    for pattern, error_type in SKILL_ERROR_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return error_type
    return None


AMBIGUOUS_STATEMENT_SUMMARY = "（多陳述命令，無法判定出錯的陳述）"


def _skill_cli_segments(command: str) -> list:
    """複合命令中屬 ticket/skill CLI 的片段（已去 `(` 前綴與空白）。"""
    found = []
    for segment in re.split(r'[|&;]+', command):
        segment = segment.strip().lstrip('(').strip()
        tokens = segment.split()
        if not tokens:
            continue
        first = tokens[0][1:] if tokens[0].startswith("/") else tokens[0]
        if first in SKILL_CLI_COMMANDS:
            found.append(segment)
    return found


def _segment_verb(segment: str) -> Optional[str]:
    """片段的子命令動詞（`ticket track <verb>` 取 verb，否則取第二個 token）。"""
    tokens = segment.split()
    if len(tokens) >= 3 and tokens[1] == "track":
        return tokens[2]
    return tokens[1] if len(tokens) >= 2 else None


def locate_failing_statement(command: str, output: str) -> Optional[str]:
    """多陳述命令中，從錯誤輸出歸因實際出錯的 ticket/skill CLI 陳述。

    原缺陷：摘要一律取命令開頭，`ticket track set-who ... > /dev/null 2>&1;
    ticket track check-acceptance <id> 2 3` 出錯的是第二個陳述，卻標成 set-who。
    argparse 錯誤輸出帶出錯陳述的子命令名稱（usage / error 行），故以輸出中是否
    出現該動詞（完整字詞）歸因；恰好一個陳述命中才指名，其餘回傳 None（不指名）。
    """
    segments = _skill_cli_segments(command)
    if len(segments) == 1:
        return segments[0]
    hits = []
    for segment in segments:
        verb = _segment_verb(segment)
        if verb and re.search(r'(?<![\w-])' + re.escape(verb) + r'(?![\w-])', output):
            hits.append(segment)
    return hits[0] if len(hits) == 1 else None


def extract_command_summary(command: str, output: str = "") -> Tuple[str, str]:
    """提取命令摘要和基本命令

    `command_base` 優先取複合命令（含 `&&` / `;` / `|` 等鏈式運算子）中實際
    觸發 ticket/skill CLI 呼叫的片段首 token；未命中時 fallback 為整條命令
    的第一個 token（維持既有單一命令行為）。

    原缺陷（0.0.1-W1-010）：一律取整條命令的第一個 token，`cd <path>
    2>/dev/null; ticket track set-where ...` 這類複合命令會誤取 `cd`，使
    後續 `{command_base} --help` 建議變成無意義的 `cd --help`（`cd` 是
    shell builtin，無 `--help`）。

    多個 ticket/skill CLI 陳述時（286.3）：摘要與 command_base 指向 output 歸因
    出的出錯陳述；無法歸因時摘要標示無法判定，不指名任何陳述。
    """
    command_summary = command[:80] if len(command) > 80 else command

    if len(_skill_cli_segments(command)) > 1:
        failing = locate_failing_statement(command, output)
        if failing is None:
            command_summary = AMBIGUOUS_STATEMENT_SUMMARY
        else:
            command_summary = failing[:80]
            command = failing

    command_base = _find_skill_cli_token(command)
    if command_base is None:
        parts = command.strip().split()
        command_base = parts[0] if parts else command
        if command_base.startswith("/"):
            command_base = command_base[1:]

    return command_summary, command_base


def _failure_event_output(input_data: Dict[str, Any]) -> Optional[str]:
    """PostToolUseFailure 事件的失敗輸出（error 首行 Exit code N 之後的交錯 stdout/stderr）。

    error 格式無法解析時回傳 None，呼叫端 fail-open 跳過。
    """
    parsed = parse_failure_error(input_data.get("error"))
    return None if parsed is None else parsed[1]


def check_skill_cli_error(input_data: Dict[str, Any], logger) -> Optional[str]:
    """
    檢查 skill/ticket CLI 錯誤（來自 skill-cli-error-feedback-hook）

    Returns:
        additionalContext 字串，或 None 表示未觸發
    """
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    if not is_skill_cli_command(command):
        logger.debug("skill-cli: 跳過，非 ticket/skill CLI 命令")
        return None

    failure_event = is_failure_event(input_data)
    tool_response = input_data.get("tool_response") or {}
    if failure_event:
        failure_output = _failure_event_output(input_data)
        if failure_output is None:
            logger.debug("skill-cli: PostToolUseFailure 的 error 格式無法解析，fail-open 跳過")
            return None
        stderr, stdout = "", failure_output
    elif isinstance(tool_response, str):
        stderr = ""
        stdout = tool_response
    elif isinstance(tool_response, dict):
        stderr = tool_response.get("stderr", "")
        stdout = tool_response.get("stdout", "")
    else:
        logger.debug("skill-cli: tool_response 形狀異常，跳過")
        return None

    # 失敗事件已確定為失敗，不做成功回音判定
    # 成功判定改接共用 helper：真實 payload 無 exit_code，且 PostToolUse 只在 shell 層
    # 結束碼為 0 時觸發（失敗走 PostToolUseFailure，本專案未註冊）。結束碼 75 屬非零，
    # 在 PostToolUse 上不會出現，原 75 分支已移除。命令成功回音存在即跳過，避免成功命令
    # 的 stdout 引述錯誤字樣（如讀取內含 usage 錯誤文字的 ticket）被誤報。
    # 分層判定（286.3）：本 hook 是反向判定（非成功才給回饋），只接第 1 層——未遮蔽的命令
    # 收到 PostToolUse 即蘊含成功（argparse 錯誤結束碼非 0，走 PostToolUseFailure），
    # 不論 stdout 是否有 [OK]；被遮蔽時退回成功回音標記，維持原行為。
    if not failure_event and is_bash_success(
        tool_response, _CLI_SUCCESS_MARKERS, command=command
    ):
        logger.debug("skill-cli: 命令成功（含成功回音），跳過")
        return None

    if not stderr and not stdout:
        logger.debug("skill-cli: 無錯誤資訊，跳過")
        return None

    # 跳過 ErrorEnvelope 已輸出完整結構化訊息的情況（W17-008.5.5）
    if is_envelope_output(stderr, stdout):
        logger.debug("skill-cli: ErrorEnvelope 已輸出完整訊息，跳過補充: %s", command[:80])
        return None

    if is_excluded_error(stderr, stdout):
        logger.debug("skill-cli: 業務邏輯錯誤，跳過: %s", command[:80])
        return None

    error_type = detect_skill_error_type(stderr, stdout)
    if not error_type:
        logger.debug("skill-cli: 未偵測到 SKILL 引導缺陷錯誤")
        return None

    logger.info("skill-cli: 偵測到 SKILL 引導缺陷錯誤: %s", error_type)
    logger.info("skill-cli: 失敗命令: %s", command[:120])

    command_summary, command_base = extract_command_summary(command, stderr + "\n" + stdout)
    return SKILL_CLI_ERROR_FEEDBACK_TEMPLATE.format(
        error_type=error_type,
        command_summary=command_summary,
        command_base=command_base,
    )


# ============================================================================
# General CLI Failure 子邏輯（來自 cli-failure-help-reminder-hook）
# ============================================================================

def _statement_starts_with(tokens, prefix) -> bool:
    if len(tokens) < len(prefix):
        return False
    return [Path(tokens[0]).name] + list(tokens[1:len(prefix)]) == list(prefix)


def _is_non_test_handled(command: str) -> bool:
    statements = parse_command_statements(command)
    for statement in statements or []:
        stripped = _strip_launch_prefixes(statement)
        if any(_statement_starts_with(stripped, p) for p in HANDLED_BY_OTHER_HOOKS):
            return True
    return False


def is_handled_by_other_hooks(command: str, logger=None) -> bool:
    """判斷命令是否已由其他 Hook 處理。

    測試類走共用測試命令判定；其餘依敘述開頭比對（前綴處理與共用判定同一函式）。
    無法解析或判定拋例外一律回 False（寧可多提醒、不漏提醒）。
    """
    try:
        if find_test_invocations(command):
            return True
        return _is_non_test_handled(command)
    except Exception as e:
        if logger is not None:
            logger.error("general-cli: 已處理判定例外，不抑制提醒: %s", e, exc_info=True)
        return False


def is_expected_stderr(command: str, stderr: str) -> bool:
    """判斷 stderr 是否為預期輸出（非真正的 CLI 失敗）"""
    for pattern in EXPECTED_STDERR_COMMANDS:
        if command.strip().startswith(pattern):
            return True
    if "git " in command:
        for info_pattern in GIT_INFO_STDERR_PATTERNS:
            if info_pattern in stderr:
                return True
    return False


def _masked_stdout_error(command: str, tool_response: Any, logger) -> Optional[str]:
    """遮蔽路徑上 stdout 的 [Error] 失敗訊息；非遮蔽、無法判斷或未命中回傳 None。

    比對規則：stdout 任一行 lstrip 後以 STDOUT_ERROR_PREFIX（`[Error]`）開頭才算。
    ticket CLI 的錯誤固定寫在 stdout 且以該前綴起頭；成功命令輸出中途夾帶
    `[Error]` 字樣（非行首）不命中。
    僅在 is_invocation_masked(command) 為 True 時檢查：未遮蔽而收到 PostToolUse
    的命令結束碼為 0，不以 stdout 判失敗；None（無法解析）fail-open 視為不命中。
    """
    if not isinstance(tool_response, dict):
        return None
    stdout = tool_response.get("stdout", "")
    if not isinstance(stdout, str) or STDOUT_ERROR_PREFIX not in stdout:
        return None
    try:
        masked = is_invocation_masked(command)
    except Exception as e:
        logger.error("general-cli: 遮蔽判斷例外，fail-open: %s", e, exc_info=True)
        return None
    if masked is not True:
        return None
    for line in stdout.splitlines():
        if line.lstrip().startswith(STDOUT_ERROR_PREFIX):
            logger.info("general-cli: 遮蔽路徑 stdout 偵測到 %s 前綴", STDOUT_ERROR_PREFIX)
            return line.strip()
    return None


def _stdout_error_reminder(command: str, stdout_error: str, logger) -> Optional[str]:
    """遮蔽路徑 stdout [Error] 的提醒；ticket/skill 前綴不套用「已由其他 Hook 處理」排除
    （skill 分支只認參數類錯誤，業務錯誤無人處理），其餘 handled 命令仍排除。"""
    if is_handled_by_other_hooks(command, logger) and not is_skill_cli_command(command):
        logger.debug("general-cli: 已由其他 Hook 處理: %s", command[:80])
        return None
    logger.info("general-cli: 遮蔽失敗（stdout %s），輸出 PC-005 調查步驟提醒", STDOUT_ERROR_PREFIX)
    logger.info("general-cli: 失敗命令: %s", command[:120])
    return WorkflowMessages.CLI_FAILURE_HELP_REMINDER


def check_general_cli_failure(input_data: Dict[str, Any], logger) -> Optional[str]:
    """
    檢查一般 CLI 失敗（來自 cli-failure-help-reminder-hook）

    Returns:
        additionalContext 字串，或 None 表示未觸發
    """
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    if is_failure_event(input_data):
        # 失敗事件的 error 為交錯輸出，整段視為 stderr 並接既有分流
        failure_output = _failure_event_output(input_data)
        if failure_output is None:
            logger.debug("general-cli: PostToolUseFailure 的 error 格式無法解析，fail-open 跳過")
            return None
        stderr = failure_output
    else:
        # PostToolUse 的 tool_response.stderr 實測恆為空（stderr 併入 stdout），
        # 不以其判斷；此事件僅剩遮蔽路徑的 stdout 行首 [Error] 一條偵測。
        tool_response = input_data.get("tool_response") or {}
        stdout_error = _masked_stdout_error(command, tool_response, logger)
        if stdout_error:
            return _stdout_error_reminder(command, stdout_error, logger)
        logger.debug("general-cli: PostToolUse 無遮蔽失敗訊號，命令成功，跳過")
        return None

    if not stderr or not stderr.strip():
        logger.debug("general-cli: 無 stderr，命令成功，跳過")
        return None

    if is_handled_by_other_hooks(command, logger):
        logger.debug("general-cli: 已由其他 Hook 處理: %s", command[:80])
        return None

    if is_expected_stderr(command, stderr):
        logger.debug("general-cli: 預期的 stderr，跳過: %s", command[:80])
        return None

    logger.info("general-cli: 偵測到 CLI 失敗，輸出 PC-005 調查步驟提醒")
    logger.info("general-cli: 失敗命令: %s", command[:120])

    return WorkflowMessages.CLI_FAILURE_HELP_REMINDER


# ============================================================================
# 主要邏輯
# ============================================================================

def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 優先檢查 skill CLI 錯誤（更 specific）
    4. 若未觸發，檢查一般 CLI 失敗
    5. 輸出結果
    """
    logger = setup_hook_logging("cli-error-feedback-hook")

    try:
        input_data = read_json_from_stdin(logger)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    if not input_data:
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # subagent 環境跳過（CLI 錯誤回饋給 PM 看，代理人不需要）
    if is_subagent_environment(input_data):
        return EXIT_SUCCESS

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    additional_context = None

    # 子邏輯 1: Skill CLI 錯誤（優先，更 specific）
    try:
        additional_context = check_skill_cli_error(input_data, logger)
    except Exception as e:
        logger.error("check_skill_cli_error 例外: %s", e, exc_info=True)

    # 子邏輯 2: 一般 CLI 失敗（若 skill CLI 未觸發）
    if additional_context is None:
        try:
            additional_context = check_general_cli_failure(input_data, logger)
        except Exception as e:
            logger.error("check_general_cli_failure 例外: %s", e, exc_info=True)

    # 輸出結果
    if additional_context:
        output = {
            "hookSpecificOutput": {
                "hookEventName": ("PostToolUseFailure" if is_failure_event(input_data)
                                  else "PostToolUse"),
                "additionalContext": additional_context
            }
        }
    else:
        output = DEFAULT_OUTPUT

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "cli-error-feedback-hook")
    sys.exit(exit_code)
