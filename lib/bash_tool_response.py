"""Bash PostToolUse tool_response 的成功判定（共用）。

平台事件依據（官方 hooks 文件）：PostToolUse 只在工具呼叫成功完成後觸發，Bash 命令
失敗（shell 層結束碼非 0）改走 PostToolUseFailure 事件，payload 無 tool_response，
改帶 `error` 欄位（首行 `Exit code N`，其後為交錯的 stdout 與 stderr）。
因此在 PostToolUse 內收到的 Bash 命令，shell 層結束碼必為 0；未被遮蔽的失敗命令
只會到達 PostToolUseFailure:Bash 群組的 hook（post-test-hook、cli-error-feedback-hook
已於該群組註冊）。依 hook_event_name 分流：PostToolUseFailure 以 parse_failure_error()
解析 error，只把首行 `Exit code N` 當作穩定格式，其後內容僅作文字比對用。

真實 tool_response 只有 stdout、stderr、interrupted、isImage、noOutputExpected，
沒有 exit_code（文件未列）。以 get("exit_code", -1) 判定成功會恆走失敗分支。

stderr 恆為空字串：實測（2026-10）Bash PostToolUse payload 中 stderr 全數為 ""，
命令的 stderr 輸出併入 stdout。以 stderr 判斷失敗的分支在 PostToolUse 永不觸發；
失敗訊號只能取自 PostToolUseFailure 的 error 欄位。亦不可改以 stdout 內容推斷失敗，
成功命令的 stdout 可能引述錯誤字樣而造成誤報。

判定順序：
1. exit_code 存在（相容舊形狀或未來平台補上）：沿用原判定，0 或 75 才算成功。
   75 為 ticket CLI 的 auto-commit 失敗專用碼；真實 PostToolUse 不會出現，僅供相容 payload。
2. exit_code 缺席：interrupted 為 True 即未成功。
3. stdout 須含呼叫端命令自身的成功回音。此步驟的用途是涵蓋複合命令中被管線或分號遮蔽的
   失敗（如 `ticket ... | tail` 整體結束碼為 0），不是推斷 shell 層結束碼。

已知誤判（推斷式判定的固有限度）：
- 命令的成功回音文字被改寫後，成功命令被判為未成功（漏報成功）。
- 被遮蔽的失敗命令 stdout 偶然含相同字樣，被判為成功（漏報失敗）。
- 未遮蔽的失敗命令根本不觸發 PostToolUse，由 PostToolUseFailure 事件負責（見 parse_failure_error）。
"""

import re
from typing import Any, Callable, Iterable, Optional, Tuple

from .ticket_command_parse import is_invocation_masked

FAILURE_EVENT_NAME = "PostToolUseFailure"
_EXIT_CODE_LINE = re.compile(r"^Exit code (\d+)[ \t]*$")


def is_failure_event(input_data: Any) -> bool:
    """payload 的 hook_event_name 是否為 PostToolUseFailure。"""
    return isinstance(input_data, dict) and input_data.get("hook_event_name") == FAILURE_EVENT_NAME


def parse_failure_error(error: Any) -> Optional[Tuple[int, str]]:
    """解析 PostToolUseFailure 的 error 欄位，回傳 (結束碼, 其後輸出)。

    只有首行 `Exit code N` 視為穩定格式；error 非字串或首行不符時回傳 None，
    呼叫端須 fail-open（不阻擋、不評估）。
    """
    if not isinstance(error, str):
        return None
    first, _, rest = error.partition("\n")
    match = _EXIT_CODE_LINE.match(first)
    if match is None:
        return None
    return int(match.group(1)), rest

# ticket CLI 寫入命令「動作已完成、僅 auto-commit 失敗」的專用退出碼（sysexits EX_TEMPFAIL）
EXIT_AUTO_COMMIT_FAILED = 75
_OK_EXIT_CODES = (0, EXIT_AUTO_COMMIT_FAILED)


def auto_commit_failure_as_success(input_data: Any) -> Optional[dict]:
    """PostToolUseFailure 且結束碼為 75 時，回傳可供完成類 hook 沿用的 PostToolUse 形狀 payload。

    結束碼 75 表示動作已完成、僅 auto-commit 失敗，完成後處理仍須執行。回傳的 payload
    以 error 首行之後的輸出作為 tool_response.stdout。其他結束碼、error 格式不符、
    非 dict 輸入一律回傳 None，呼叫端視為不處理（fail-open，不阻擋）。
    """
    if not is_failure_event(input_data):
        return None
    parsed = parse_failure_error(input_data.get("error"))
    if parsed is None or parsed[0] != EXIT_AUTO_COMMIT_FAILED:
        return None
    normalized = dict(input_data)
    normalized["tool_response"] = {"stdout": parsed[1], "stderr": ""}
    return normalized


def _layered_verdict(
    command: str, state_verifier: Optional[Callable[[], bool]]
) -> Optional[bool]:
    """分層判定的前兩層；回傳 None 表示須退回標記判定。"""
    masked = is_invocation_masked(command)
    if masked is None:
        return None
    if not masked:
        return True  # 未遮蔽：收到 PostToolUse 即蘊含成功
    if state_verifier is None:
        return None
    try:
        return bool(state_verifier())
    except Exception:  # 驗證器自身失敗不等於命令失敗：退回標記判定，不吞掉判定能力
        return None


def is_bash_success(
    tool_response: Any,
    success_markers: Iterable[str],
    ignore_case: bool = False,
    command: Optional[str] = None,
    state_verifier: Optional[Callable[[], bool]] = None,
) -> bool:
    """判定 Bash 命令是否成功。

    Args:
        tool_response: PostToolUse 的 tool_response；非 dict 一律視為未成功
        success_markers: 呼叫端命令自身的成功回音；stdout 含任一即符合
        ignore_case: 標記比對是否忽略大小寫
        command: 原始命令字串；提供時啟用分層判定（未提供則行為與舊版完全相同）。
            層次：(1) 未遮蔽（見 is_invocation_masked）即成功，不看 stdout；
            (2) 遮蔽且有 state_verifier，以其回傳值為準；(3) 其餘（無法解析、
            無驗證器、驗證器拋例外）退回標記判定。
        state_verifier: 無參數 callable，回傳票面狀態是否符合預期（呼叫端負責時間窗）
    """
    if not isinstance(tool_response, dict):
        return False
    if "exit_code" in tool_response:
        if tool_response["exit_code"] not in _OK_EXIT_CODES:
            return False
    elif tool_response.get("interrupted") is True:
        return False
    if command is not None:
        verdict = _layered_verdict(command, state_verifier)
        if verdict is not None:
            return verdict
    stdout = tool_response.get("stdout", "")
    if not isinstance(stdout, str):
        return False
    if ignore_case:
        stdout = stdout.lower()
        return any(m.lower() in stdout for m in success_markers)
    return any(m in stdout for m in success_markers)
