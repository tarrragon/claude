#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
NeedsContext Listener Hook - PostToolUse (Bash)

功能:
  監聽 `ticket track append-log ... --section NeedsContext ...` 命令執行事件，
  當代理人透過 NeedsContext section 回報資料缺口時，觸發 PushNotification 讓 PM
  立即得知並補料，避免代理人靜默卡住或用錯誤假設繼續工作。

觸發時機: Bash 工具呼叫後 (PostToolUse, matcher: Bash)
行為:
  - 若命令為 ticket track append-log --section NeedsContext 且執行成功，
    輸出 systemMessage 讓 PM 看到提示
  - 其他情況靜默通過 (exit 0)

來源:
  - 0.18.0-W17-010（W17-007 ANA 三 IMP 合併）
  - 協議定義：ticket body 中 `## NeedsContext` section，子項含缺失項/觸發位置/
    影響/建議補料/重派成本

修復記錄（觸發條件過寬 + 成功檢查過弱）:
  - 觸發條件改為 shell token 解析（parse_command_statements）後，在每個語句
    的 token 清單內做任意位置的視窗掃描（連續六個 token 精確比對，無前綴
    白名單，不限於命令位置），取代先前對命令字串原文做全文 regex search 的
    作法——後者會把引號
    內的參數值（如文件撰寫、issue body、探針腳本提及該命令形態的字面文字）
    誤判為實際要執行的命令，且未驗證擷取的 ticket_id 是否為合法格式（可能
    命中字面佔位符如 `<ticket-id>`）。
  - 成功檢查改為讀 tool_response 的 exit_code 是否為 0，且 stdout 是否含
    CLI 的成功回音（`已追加日誌到`）；先前僅檢查 `tool_response.get(
    "success") is False`，但 Bash 工具的 tool_response 通常不帶 `success`
    欄位（CLI 以非零 exit code 表示失敗時該欄位仍可能缺席），故寫入被拒
    （如票狀態非 in_progress）仍會主動宣告已更新。

已知誤判（可接受）:
  - 因為是語句內任意位置的視窗掃描，echo、grep、man、ssh 等命令之後接完整
    命令字面（未加引號而被切成獨立 token）時也會命中。
  - 可接受理由：本 hook 為提示型（PostToolUse 只提醒、不阻擋），誤判只多一則
    提醒；且命中需同時滿足三個條件——含合法格式的 ticket ID（FULL_ANCHORED_RE）、
    `--section NeedsContext`、PostToolUse 回音含「已追加日誌到」（成功回音）。
  - 未覆蓋（漏判）：以變數帶入 ticket ID 或 section 名稱，命令文字中看不到
    實際值，經用戶裁定改靠自律。
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging,
    read_json_from_stdin,
    extract_tool_input,
    run_hook_safely,
    is_subagent_environment,
)
from lib.bash_tool_response import is_bash_success
from lib.git_command_parse import parse_command_statements
from lib.ticket_id_pattern import FULL_ANCHORED_RE

HOOK_NAME = "needs-context-listener-hook"
EXIT_SUCCESS = 0

# 視窗掃描比對的 token 子序列（語句內任意位置）：
# ticket track append-log <id> --section NeedsContext
_APPEND_LOG_PATTERN_LEN = 6
_SECTION_FLAG_TOKEN = "--section"
_NEEDS_CONTEXT_SECTION_TOKEN = "NeedsContext"

# CLI append-log 成功時的回音字樣（見 ticket_system/lib/messages.py 的
# LOG_APPENDED = "[OK] {ticket_id} 已追加日誌到 '{section}'"）
_LOG_APPENDED_SUCCESS_MARKER = "已追加日誌到"


# ticket CLI 寫入命令「動作已完成、僅 auto-commit 失敗」的專用退出碼（sysexits EX_TEMPFAIL）

def _match_append_log_needscontext(tokens: List[str]) -> Optional[str]:
    """在單一語句 token 清單中尋找 `ticket track append-log <id> --section
    NeedsContext` 子序列，回傳格式合法的 ticket_id；否則回傳 None。

    以 token 視窗精確比對（非字串 search）：在語句內任意位置滑動六個 token
    的視窗，不限命令位置、無前綴白名單。引號內的參數值（如 ticket 描述文字
    提及該命令形態的字面文字）在 tokenize 階段已收斂成單一 token，不會與
    這六個分開的 token 精確匹配，故不會誤判。
    已知誤判：echo、grep、man、ssh 之後接完整命令字面時也會命中；提示型
    hook 誤判只多一則提醒，且仍須合法 ticket ID 與 `--section NeedsContext`，
    成功回音檢查在 main_logic。
    """
    for i in range(len(tokens) - _APPEND_LOG_PATTERN_LEN + 1):
        window = tokens[i : i + _APPEND_LOG_PATTERN_LEN]
        if window[0] != "ticket" or window[1] != "track" or window[2] != "append-log":
            continue
        if window[4] != _SECTION_FLAG_TOKEN:
            continue
        if window[5] != _NEEDS_CONTEXT_SECTION_TOKEN:
            continue
        ticket_id = window[3]
        if not FULL_ANCHORED_RE.match(ticket_id):
            # 排除字面佔位符（如 <ticket-id>）等非合法 ID 格式
            continue
        return ticket_id
    return None


def extract_ticket_id(command: str) -> Optional[str]:
    """若命令為 ticket track append-log <id> --section NeedsContext，回傳 ticket_id。

    以 shell token 解析（parse_command_statements）後逐語句做任意位置視窗
    掃描（非僅命令位置，見 _match_append_log_needscontext），取代
    先前對命令字串原文做全文 regex search 的作法——後者會把引號內的參數值
    （如 ticket --why 描述文字提及該命令形態）誤判為實際要執行的命令。找到
    候選 ticket_id 後另以 FULL_ANCHORED_RE 驗證格式，排除字面佔位符（如
    `<ticket-id>`）；content 內文出現 NeedsContext 不會觸發（避免自我實測
    時的 false positive）。
    """
    if not command:
        return None
    statements = parse_command_statements(command)
    if not statements:
        return None
    for tokens in statements:
        ticket_id = _match_append_log_needscontext(tokens)
        if ticket_id is not None:
            return ticket_id
    return None


def main_logic() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    payload = read_json_from_stdin(logger)

    # 偵測 subagent 環境：agent_id 僅在 subagent 中出現（W1-071 / PC-V1-004 入口污染防護）
    # 「請 PM 確認補料」屬 PM-only 訊息，注入 subagent context 無作用且污染其報告 token
    if is_subagent_environment(payload):
        logger.debug(
            "偵測到 subagent 環境（agent_id=%s），跳過 NeedsContext 提醒",
            payload.get("agent_id") if isinstance(payload, dict) else None,
        )
        return EXIT_SUCCESS

    tool_input = extract_tool_input(payload)
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    ticket_id = extract_ticket_id(command)
    if not ticket_id:
        return EXIT_SUCCESS

    # 檢查執行是否成功：以 exit_code 與 stdout 成功回音為主，用實跑結果驗證
    # （不僅看 tool_response.success，見上方「修復記錄」段落）
    tool_response = payload.get("tool_response", {}) if isinstance(payload, dict) else {}
    if not isinstance(tool_response, dict):
        tool_response = {}

    # 舊版相容：若有明確失敗指示（success 欄位存在且為 False）則不通知
    if tool_response.get("success") is False:
        return EXIT_SUCCESS

    # 成功判定改接共用 helper（interrupted 檢查加成功回音）。PostToolUse 只在 shell 層
    # 結束碼為 0 時觸發，結束碼 75 屬非零、不會在此出現，原 75 分支已移除。
    # stdout 欄位缺席（測試樁或部分 Bash 回應）時不因此判定失敗，交由上方 success 欄位把關
    # 分層判定只接第 1 層：append-log 每次呼叫都實際追加，沒有「重複呼叫但無轉換」的情形，
    # 在乎的是命令成功，不需票面驗證器；被遮蔽時退回成功回音標記。
    if "stdout" in tool_response and not is_bash_success(
        tool_response, (_LOG_APPENDED_SUCCESS_MARKER,), command=command
    ):
        return EXIT_SUCCESS

    # W3-097 中性化（方案 V）：不預設 caller 為代理人，對 PM 自填與代理人回報情境皆適用
    message = (
        f"[NeedsContext] 已更新於 {ticket_id}，"
        f"請 PM 確認是否需補料或評估後續動作"
    )
    logger.info(message)

    # 透過 hookSpecificOutput systemMessage 讓 PM 看到
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return EXIT_SUCCESS


def main() -> int:
    return run_hook_safely(main_logic, HOOK_NAME)


if __name__ == "__main__":
    sys.exit(main())
