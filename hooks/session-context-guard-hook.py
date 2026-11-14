#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///

"""
Session Context Guard Hook - PostToolUse Hook

功能: 每次 ticket complete 成功後判斷 context 是否該整理，提醒在本 session 執行
      /compact 或 /clear（不建議換新 session）。

判定來源（用量檔優先）:
  1. line-board 的 context 用量檔（主 checkout 的
     .claude/hook-logs/line-board/context/<session_id>.json）可讀且百分比可用時，
     以實測用量判定，門檻與 line-board contextJudge.ts 的一般線門檻一致：
     達 45% 建議 /compact；達 30% 提示沒有進行中的票時可 /clear。票數不參與。
  2. 用量檔缺失（未載入 line-board）、解析失敗或百分比缺席時，退回下方的票數門檻。

觸發時機: Bash 工具執行後
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 以共用解析器檢查 command 是否為 ticket track complete/finish/batch-complete
  3. 檢查 stdout 是否包含完成標記（"已完成"）
  4. 若偵測成功，遞增計數器並在閾值時輸出警告

計數器存放: /tmp/claude-session-completed-tickets-{session_id}
（session_id 取自 hook 輸入；一次 complete 只由本 hook 計數，post-ticket-lifecycle-hook 不再計數）
失敗語意: fail-open——取不到 session_id 或檔案讀寫失敗時略過計數，不阻擋
票數閾值（只在讀不到用量時使用）:
  - 2 個：輕度提醒（context 正在累積）
  - 3 個以上：強烈建議 /compact

背景：Claude Code 的 hook 事件不暴露 token 用量，票數原本是唯一的代理指標；
  line-board 以 session.measure 寫入實測用量後，有用量檔的 session 改以用量判定，
  避免票小、用量低時仍建議整理 context（票數與用量兩套訊號互相矛盾）。

行為: 不阻擋（exit 0），僅在 additionalContext 輸出警告訊息
"""

import sys
import json
import re
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output, get_hook_log_dir
from lib.ticket_command_parse import has_complete_command
from lib.bash_tool_response import (
    FAILURE_EVENT_NAME, is_failure_event, auto_commit_failure_as_success, is_bash_success,
)
from lib.ticket_completed_verifier import make_completed_verifier, is_complete_transition_success
from lib.constants import SESSION_COMPLETED_TICKETS_COUNTER_TEMPLATE
from lib.session_state_key import session_state_path

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

HOOK_NAME = "session-context-guard"

# 計數器檔案路徑（以 hook 輸入的 session_id 識別 session）
COUNTER_FILE_TEMPLATE = SESSION_COMPLETED_TICKETS_COUNTER_TEMPLATE

# 輕度提醒閾值（完成 2 個 Ticket）
SOFT_WARN_THRESHOLD = 2

# 強烈建議閾值（完成 3 個以上 Ticket）
STRONG_WARN_THRESHOLD = 3

# line-board 寫入的 context 用量檔（hook 名稱與子目錄）。
# 寫入端 usageWriter.ts 以 git worktree list 的第一項定位主 checkout，非 CLAUDE_PROJECT_DIR，
# 故不屬 LD（session 啟動根），讀回端以 get_hook_log_dir 對齊同一個主 checkout。
CONTEXT_USAGE_HOOK_NAME = "line-board"
CONTEXT_USAGE_SUBDIR = "context"

# 用量檔名的 session_id 格式（同 line-board hooks/contextUsage.ts 的 SESSION_ID_PATTERN）
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]+")

# 用量門檻，與 line-board hooks/contextJudge.ts 的一般線門檻一致（測試比對兩邊常數）
# 持有進行中的票時達 45% 建議 /compact；沒有進行中的票時達 30% 可 /clear
LANE_T_COMPACT = 45
LANE_T_CLEAR = 30

# 完成成功標記（ticket CLI 輸出）
COMPLETE_SUCCESS_MARKER = "已完成"

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}


# ============================================================================
# 計數器管理
# ============================================================================

def get_counter_file(input_data: dict, logger=None) -> Optional[Path]:
    """取得計數器檔案路徑（以 hook 輸入的 session_id 識別 session；取不到回傳 None）"""
    return session_state_path(COUNTER_FILE_TEMPLATE, input_data, logger)


def read_counter(input_data: dict, logger=None) -> int:
    """讀取當前 session 完成的 Ticket 計數（無檔案或讀取失敗為 0，fail-open）"""
    counter_file = get_counter_file(input_data, logger)
    if counter_file is None or not counter_file.exists():
        return 0
    try:
        return int(counter_file.read_text().strip())
    except (ValueError, IOError):
        return 0


def increment_counter(input_data: dict, logger=None) -> int:
    """遞增計數器並回傳新值；取不到 session_id 時略過並回傳 0（fail-open，不觸發提醒）"""
    counter_file = get_counter_file(input_data, logger)
    if counter_file is None:
        return 0
    count = read_counter(input_data, logger) + 1
    try:
        counter_file.write_text(str(count))
    except IOError as e:
        # fail-open：寫入失敗只少一次累計，不阻擋操作；留日誌可追蹤
        if logger is not None:
            logger.warning("計數器寫入失敗: %s", e)
    return count


# ============================================================================
# 指令偵測
# ============================================================================

def is_ticket_complete_command(command: str) -> bool:
    """判斷是否為 ticket track complete/finish/batch-complete 命令。

    走共用解析器；無法解析（未閉合引號）時視為非完成命令（本 hook 不阻擋，
    漏計數優於誤計數）。
    """
    return has_complete_command(command) is True


def is_complete_successful(tool_response, command: str) -> bool:
    """判斷 ticket complete 是否成功（分層：未遮蔽即成功、遮蔽以票面驗證、其餘比對標記）"""
    return is_complete_transition_success(
        tool_response,
        [COMPLETE_SUCCESS_MARKER],
        command,
        make_completed_verifier(command),
    )


# ============================================================================
# context 用量（line-board 用量檔）
# ============================================================================

def usage_file_path(session_id: str) -> Path:
    """本 session 的用量檔路徑（主 checkout 下；worktree 內也指向主 checkout 那份）。"""
    return get_hook_log_dir(CONTEXT_USAGE_HOOK_NAME) / CONTEXT_USAGE_SUBDIR / f"{session_id}.json"


def read_usage_record(input_data: dict, logger) -> Optional[dict]:
    """本 session 的用量檔內容；讀不到、解析失敗或 sessionId 不符時回傳 None，呼叫端退回票數判定。"""
    session_id = input_data.get("session_id")
    if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
        logger.info("session_id 缺失或格式不符，改用票數判定")
        return None
    path = usage_file_path(session_id)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # 未載入 line-board 的 session 沒有用量檔，屬正常情形
        logger.info("無用量檔，改用票數判定: %s", path)
        return None
    except (OSError, ValueError) as exc:
        logger.warning("用量檔讀取或解析失敗，改用票數判定: %s (%s)", path, exc)
        return None
    if not isinstance(record, dict) or record.get("sessionId") != session_id:
        logger.warning("用量檔內容與 session_id 不符，改用票數判定: %s", path)
        return None
    return record


def is_pre_compact_measure(record: dict) -> bool:
    """用量是 compact 前的量測：phase 為 compacted 且 measuredAt 不晚於 phase.at（同 line-board isPreCompactMeasure）。

    compact 完成當下用量檔寫入 phase compacted，但百分比仍是 compact 前的值，下一次回應前不更新；
    以它判定會對剛 compact 過的 session 再建議 /compact。
    """
    phase = record.get("phase")
    if not isinstance(phase, dict) or phase.get("kind") != "compacted":
        return False
    at, measured = phase.get("at"), record.get("measuredAt")
    return isinstance(at, (int, float)) and isinstance(measured, (int, float)) and measured <= at


def usage_percent(record: dict, logger) -> Optional[float]:
    """用量檔的百分比；缺席時回傳 None，呼叫端退回票數判定。

    百分比取法同 line-board 的 selectedPercent：autoCompactThreshold 為 null 用 percent，否則用 compactPercent。
    """
    key = "percent" if record.get("autoCompactThreshold") is None else "compactPercent"
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        logger.info("用量檔 %s 缺席，改用票數判定", key)
        return None
    return value


# ============================================================================
# 警告訊息生成
# ============================================================================

_RULE = "============================================================"


def build_usage_warning(percent: float) -> Optional[str]:
    """依實測用量建立提醒；未達 LANE_T_CLEAR 回傳 None（不提醒）。"""
    shown = round(percent)
    if percent >= LANE_T_COMPACT:
        return (
            f"{_RULE}\n"
            f"[Session Context Guard] context 用量 {shown}%，已達 /compact 門檻（{LANE_T_COMPACT}%）\n"
            f"{_RULE}\n"
            f"建議：目前的票做到可交接點後，在本 session 執行 /compact，不換新 session。\n"
            f"{_RULE}"
        )
    if percent >= LANE_T_CLEAR:
        return (
            f"{_RULE}\n"
            f"[Session Context Guard] context 用量 {shown}%，已達 /clear 門檻（{LANE_T_CLEAR}%）\n"
            f"{_RULE}\n"
            f"本 session 沒有其他進行中的票時，可在本 session 執行 /clear；還有進行中的票就繼續，"
            f"用量到 {LANE_T_COMPACT}% 再 /compact。\n"
            f"{_RULE}"
        )
    return None


def build_soft_warning(count: int) -> str:
    """建立輕度提醒訊息（讀不到用量、完成 2 個 Ticket）"""
    return (
        f"{_RULE}\n"
        f"[Session Context Guard] 本 session 已完成 {count} 個 Ticket（讀不到 context 用量，以票數估計）\n"
        f"{_RULE}\n"
        f"Context 正在累積。目前的票做到可交接點後，可在本 session 執行 /compact。\n"
        f"{_RULE}"
    )


def build_strong_warning(count: int) -> str:
    """建立強烈建議訊息（讀不到用量、完成 3 個以上 Ticket）"""
    return (
        f"{_RULE}\n"
        f"[Session Context Guard] 本 session 已完成 {count} 個 Ticket（讀不到 context 用量，以票數估計）\n"
        f"{_RULE}\n"
        f"建議：目前的票做到可交接點後，在本 session 執行 /compact，不換新 session。\n"
        f"{_RULE}"
    )


def build_count_warning(count: int) -> Optional[str]:
    """讀不到用量時以票數判定；第 1 張不提醒，回傳 None。"""
    if count >= STRONG_WARN_THRESHOLD:
        return build_strong_warning(count)
    if count >= SOFT_WARN_THRESHOLD:
        return build_soft_warning(count)
    return None


# ============================================================================
# 主要邏輯
# ============================================================================

def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查命令是否為 ticket track complete
    4. 檢查輸出是否包含成功標記
    5. 若全部符合，遞增計數器並依閾值輸出警告
    """
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    if not input_data:
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # PostToolUseFailure：僅結束碼 75（動作完成、auto-commit 失敗）沿用完成後處理
    event_name = "PostToolUse"
    if is_failure_event(input_data):
        input_data = auto_commit_failure_as_success(input_data)
        if input_data is None:
            logger.debug("失敗事件非結束碼 75，不處理")
            print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
            return EXIT_SUCCESS
        event_name = FAILURE_EVENT_NAME

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和輸出
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response") or {}

    # 偵測 ticket track complete 成功（共用分層判定；計數只在此判定成功時遞增一次）
    if not (is_ticket_complete_command(command) and is_complete_successful(tool_response, command)):
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 遞增計數器
    count = increment_counter(input_data, logger)
    logger.info("Ticket 完成計數：%d", count)

    # 用量檔優先；讀不到才以票數判定（計數照常遞增，供之後讀不到用量時使用）
    record = read_usage_record(input_data, logger)
    if record is not None and is_pre_compact_measure(record):
        # 剛 compact 過、尚未重新量測：不提醒，也不退回票數（計數不隨 compact 歸零，退回會誤報）
        logger.info("用量為 compact 前的量測，本次不提醒")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS
    percent = usage_percent(record, logger) if record is not None else None
    if percent is not None:
        warning = build_usage_warning(percent)
        logger.info("以用量判定：%s%%，%s", percent, "提醒" if warning else "未達門檻")
    else:
        warning = build_count_warning(count)
        logger.info("以票數判定：%d 個 Ticket，%s", count, "提醒" if warning else "未達門檻")
    if warning is None:
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # handoff 提醒為 PM-only：統一出口過濾 subagent 觸發（PC-V1-004 防護 C）
    emit_hook_output(
        event_name,
        additional_context=warning,
        audience="pm_only",
        input_data=input_data,
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, HOOK_NAME)
    sys.exit(exit_code)
