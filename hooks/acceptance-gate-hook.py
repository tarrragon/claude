#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Acceptance Gate Hook - 驗收流程完整引導（Orchestrator）

在 `ticket track complete` 執行前檢查並引導驗收流程。

功能：
- 監控 Bash 工具中的 ticket track complete 命令
- 協調 8 個獨立 checker 模組執行驗收檢查
- 生成 Hook 輸出（含 AskUserQuestion 場景提醒）

檢查項目（由 acceptance_checkers/ 模組執行）：
- 子任務完成度（阻塞）
- 驗收記錄（警告）
- ANA Ticket 後續 Ticket
- Error-pattern 衝突（Step 2.7）
- Error-pattern 新增（場景 #17）
- 5W1H 完整性
- Execution log 填寫
- 同 Wave pending sibling tickets（場景 #9）

Exit Code：
- 0 (EXIT_SUCCESS): 命令允許執行
- 2 (EXIT_BLOCK): 阻止執行（子任務未完成）
- 1 (EXIT_ERROR): Hook 執行錯誤

Hook 類型: PreToolUse
觸發時機: Bash 工具執行前，命令含 "ticket track complete" 或 "ticket track batch-complete"

使用方式:
    echo '{"tool_name":"Bash","tool_input":{"command":"ticket track complete 0.31.0-W4-036"}}' | python3 acceptance-gate-hook.py
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, NamedTuple, TypedDict

# 加入 hook_utils 路徑（相同目錄）
_hooks_dir = Path(__file__).parent
if _hooks_dir not in [p for p in sys.path if Path(p) == _hooks_dir]:
    sys.path.insert(0, str(_hooks_dir))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    extract_tool_input,
    parse_ticket_frontmatter,
    check_error_patterns_changed,
    get_project_root,
    find_ticket_file,
    save_check_log,
    validate_hook_input,
    is_subagent_environment,
)
from lib.hook_messages import GateMessages, CoreMessages, AskUserQuestionMessages, format_message

from acceptance_checkers import (
    extract_children_from_frontmatter,
    is_doc_type,
    is_ana_type,
    check_children_completed_from_frontmatter,
    verify_acceptance_record,
    check_error_pattern_conflicts,
    check_5w1h_completeness,
    check_execution_log_filled,
    check_ana_has_spawned_tickets,
    find_pending_sibling_tickets,
)
from acceptance_checkers.ticket_parser import get_ticket_start_time


# ============================================================================
# 資料結構定義
# ============================================================================

class TicketFrontmatter(TypedDict, total=False):
    """Ticket Frontmatter 結構"""
    id: str
    title: str
    type: str
    status: str
    children: str
    spawned_tickets: str
    created: str
    started_at: str
    priority: str


class AcceptanceCheckResult(NamedTuple):
    """驗收狀態檢查結果"""
    should_block: bool
    has_acceptance: bool
    message: Optional[str]
    has_new_error_patterns: bool
    new_error_pattern_files: List[str]
    pending_sibling_tickets: List[str] = []
    task_type: str = ""
    priority: str = ""
    error_pattern_conflicts: List[str] = []
    incomplete_5w1h_fields: List[str] = []
    has_empty_execution_log: bool = False


# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2

TICKET_ID_PATTERN = r'\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*'

# Error-pattern 衝突提醒訊息模板
ERROR_PATTERN_CONFLICT_WARNING = (
    "[WARNING] error-pattern 衝突檢查（Step 2.7）\n"
    "本 Ticket 修改的模組與以下 error-pattern 相關，請確認是否已考慮這些已知問題：\n"
    "{conflict_list}\n"
    "建議：complete 前確認修改未引入已知的錯誤模式。"
)


# ============================================================================
# 命令識別
# ============================================================================

def extract_ticket_id_from_command(command: str, logger) -> Optional[str]:
    """從命令中提取 Ticket ID"""
    if "ticket track complete" not in command and "ticket track batch-complete" not in command:
        return None

    match = re.search(TICKET_ID_PATTERN, command)
    if match:
        ticket_id = match.group(0)
        logger.info(f"從命令中提取 Ticket ID: {ticket_id}")
        return ticket_id

    logger.debug(f"無法從命令中提取 Ticket ID: {command}")
    return None


def is_complete_command(command: str) -> bool:
    """判斷是否為 ticket track complete 命令"""
    return "ticket track complete" in command or "ticket track batch-complete" in command


# ============================================================================
# 主協調函式
# ============================================================================

def check_acceptance_status(ticket_id: str, project_dir: Path, logger) -> AcceptanceCheckResult:
    """
    檢查 Ticket 的驗收狀態（主協調函式）

    協調所有 checker 模組：
    1. 子任務完成度檢查
    2. 驗收記錄驗證
    2.5. ANA Ticket 後續 Ticket 檢查
    2.7. Error-pattern 衝突檢查
    3. Error-pattern 新增檢查
    4. Sibling tickets 完成度檢查（場景 #9）
    5. 5W1H 完整性
    6. Execution log 填寫
    """
    ticket_file = find_ticket_file(ticket_id, project_dir, logger)

    if not ticket_file:
        logger.error(f"找不到 Ticket 檔案: {ticket_id}")
        return AcceptanceCheckResult(False, False, None, False, [])

    try:
        content = ticket_file.read_text(encoding="utf-8")
        frontmatter = parse_ticket_frontmatter(content)

        # 步驟 1：檢查子任務完成度
        should_block, error_msg = check_children_completed_from_frontmatter(
            ticket_file, frontmatter, project_dir, ticket_id, logger
        )
        if should_block:
            return AcceptanceCheckResult(True, False, error_msg, False, [], [], "", "", [], [], False)

        # 步驟 2：驗證驗收記錄
        should_block, warning_msg, should_check_acceptance, has_acceptance = verify_acceptance_record(
            content, frontmatter, ticket_id, logger
        )

        if not warning_msg:
            logger.info(f"Ticket {ticket_id} 驗收檢查通過")

        # 步驟 2.5：檢查 ANA Ticket 是否有後續 Ticket
        if is_ana_type(frontmatter.get("type")):
            ana_should_warn, ana_warning_msg = check_ana_has_spawned_tickets(frontmatter, logger)
            if ana_should_warn:
                if warning_msg:
                    warning_msg = warning_msg + "\n\n" + ana_warning_msg
                else:
                    warning_msg = ana_warning_msg

        # 步驟 2.7：檢查修改模組與既有 error-pattern 的衝突
        error_pattern_conflicts = check_error_pattern_conflicts(frontmatter, project_dir, logger)

        # 步驟 3：檢查 error-pattern 新增
        has_new_error_patterns = False
        new_error_pattern_files = []

        if should_check_acceptance:
            ticket_start_time = get_ticket_start_time(frontmatter, logger)
            if ticket_start_time:
                has_new_error_patterns, new_error_pattern_files = check_error_patterns_changed(
                    project_dir, ticket_start_time, logger
                )
                if has_new_error_patterns:
                    logger.info(f"發現 {len(new_error_pattern_files)} 個新增/修改的 error-pattern")
            else:
                logger.warning(f"無法取得 ticket 的開始時間，跳過 error-pattern 檢查")

        # 步驟 4：檢查 pending sibling tickets（場景 #9）
        pending_siblings = find_pending_sibling_tickets(ticket_id, project_dir, logger)
        logger.info(f"發現 {len(pending_siblings)} 個 pending sibling tickets")

        # 步驟 5：檢查 5W1H 完整性
        incomplete_5w1h = check_5w1h_completeness(frontmatter, logger)

        # 步驟 6：檢查 execution log 填寫
        has_empty_log = check_execution_log_filled(content, logger)

        task_type = frontmatter.get("type", "")
        priority = frontmatter.get("priority", "")

        return AcceptanceCheckResult(
            False,
            has_acceptance,
            warning_msg,
            has_new_error_patterns,
            new_error_pattern_files,
            pending_siblings,
            task_type,
            priority,
            error_pattern_conflicts,
            incomplete_5w1h,
            has_empty_log,
        )

    except Exception as e:
        logger.error(f"檢查驗收狀態失敗: {e}", exc_info=True)
        sys.stderr.write(f"ERROR: 檢查驗收狀態失敗: {e}\n")
        return AcceptanceCheckResult(False, False, None, False, [])


# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    ticket_id: str,
    check_result: AcceptanceCheckResult,
    project_dir: Path,
    logger,
) -> Dict[str, Any]:
    """生成 Hook 輸出"""
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny" if check_result.should_block else "allow"
        }
    }

    context_parts = []

    # 統一清單輸出（PROP-009 面向 C）
    checklist_items = []

    # 項目 1: acceptance
    if check_result.has_acceptance:
        checklist_items.append("[x] 1. acceptance 已全勾選")
    else:
        checklist_items.append("[WARNING] 1. acceptance 未全勾選")

    # 項目 2: 5W1H
    if not check_result.incomplete_5w1h_fields:
        checklist_items.append("[x] 2. 5W1H 已補完")
    else:
        fields_str = ", ".join(check_result.incomplete_5w1h_fields)
        checklist_items.append(f"[WARNING] 2. 5W1H 未補完（{fields_str}）")

    # 項目 3: error-pattern
    if check_result.error_pattern_conflicts:
        checklist_items.append("[WARNING] 3. error-pattern 衝突待確認")
    else:
        checklist_items.append("[x] 3. error-pattern 無衝突")

    # 項目 4: execution log
    if not check_result.has_empty_execution_log:
        checklist_items.append("[x] 4. execution log 已填寫")
    else:
        checklist_items.append("[WARNING] 4. execution log 未填寫")

    # 項目 5: spawned_tickets (只對 ANA 類型顯示)
    ticket_type_upper_for_checklist = (check_result.task_type or "").upper()
    if ticket_type_upper_for_checklist == "ANA":
        if check_result.message and "spawned" in check_result.message.lower():
            checklist_items.append("[WARNING] 5. spawned_tickets 未建立（ANA）")
        else:
            checklist_items.append("[x] 5. spawned_tickets 已更新（ANA）")
    else:
        checklist_items.append("[--] 5. spawned_tickets（非 ANA，不適用）")

    checklist_text = "[Complete 清單]\n" + "\n".join(checklist_items)
    context_parts.append(checklist_text)

    # 優先級 1：錯誤或警告訊息
    if check_result.message:
        context_parts.append(check_result.message)

    # 優先級 2：error-pattern 場景 #17 提醒（與 warning_msg 並存觸發）
    if check_result.has_new_error_patterns:
        file_list_formatted = "\n".join(f"  - {f}" for f in (check_result.new_error_pattern_files or []))
        reminder_msg = AskUserQuestionMessages.ERROR_PATTERN_REMINDER.format(
            file_list=file_list_formatted
        )
        context_parts.append(reminder_msg)
        logger.info(f"新增場景 #17 (error-pattern) 提醒")

    # 優先級 2.5：error-pattern 衝突提醒（Step 2.7，WARNING 不阻擋）
    if check_result.error_pattern_conflicts:
        conflict_list_formatted = "\n".join(
            f"  - {f}" for f in check_result.error_pattern_conflicts
        )
        conflict_msg = ERROR_PATTERN_CONFLICT_WARNING.format(
            conflict_list=conflict_list_formatted
        )
        context_parts.append(conflict_msg)
        logger.info(f"新增 error-pattern 衝突提醒，衝突數量: {len(check_result.error_pattern_conflicts)}")

    # 優先級 3：Handoff 方向選擇 場景 #9（無訊息時，sibling >= 2）
    if (
        not check_result.message
        and len(check_result.pending_sibling_tickets) >= 2
    ):
        sibling_list_formatted = "\n".join(
            f"  - {sibling_id}"
            for sibling_id in check_result.pending_sibling_tickets
        )
        reminder_msg = AskUserQuestionMessages.HANDOFF_DIRECTION_REMINDER.format(
            sibling_count=len(check_result.pending_sibling_tickets),
            sibling_list=sibling_list_formatted
        )
        context_parts.append(reminder_msg)
        logger.info(f"新增場景 #9 (Handoff 方向) 提醒，sibling 數量: {len(check_result.pending_sibling_tickets)}")

    # 優先級 4：complete 流程提醒（驗收方式，場景 #1）
    if (
        not check_result.message
        and len(check_result.pending_sibling_tickets) < 2
    ):
        ticket_type_upper = (check_result.task_type or "").upper()
        priority_upper = (check_result.priority or "").upper()
        is_auto_accept_type = ticket_type_upper in ("DOC", "ANA")
        needs_manual_confirmation = priority_upper == "P0" and not is_auto_accept_type

        if needs_manual_confirmation:
            context_parts.append(AskUserQuestionMessages.COMPLETE_REMINDER)
            logger.info(f"新增場景 #1 (complete 流程) 提醒（P0 Ticket，type={ticket_type_upper}）")
        else:
            logger.info(
                f"跳過場景 #1（自動簡化驗收，priority={priority_upper}, type={ticket_type_upper}）"
            )

    # 優先級 5：complete 後下一步提醒（路由選擇，場景 #2）
    if not check_result.message:
        context_parts.append(AskUserQuestionMessages.COMPLETE_NEXT_STEP_REMINDER)
        logger.info("新增場景 #2 (complete 後下一步) 提醒")

    if context_parts:
        output["hookSpecificOutput"]["additionalContext"] = "\n\n".join(context_parts)

    output["check_result"] = {
        "should_block": check_result.should_block,
        "timestamp": datetime.now().isoformat()
    }

    return output


# ============================================================================
# 主入口點輔助函式
# ============================================================================

def _output_allow_json() -> None:
    """輸出允許執行的 Hook 應答 JSON。"""
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}
    }, ensure_ascii=False, indent=2))


def _parse_and_validate_input(input_data: Dict[str, Any], logger) -> Optional[Tuple[str, str]]:
    """解析並驗證輸入資料。"""
    if input_data is None:
        logger.debug("輸入資料為 None，跳過驗證")
        _output_allow_json()
        return None

    if not validate_hook_input(input_data, logger, ("tool_name", "tool_input")):
        logger.error("輸入格式錯誤")
        _output_allow_json()
        return None

    tool_name = input_data.get("tool_name", "")
    tool_input = extract_tool_input(input_data, logger)
    command = tool_input.get("command", "")

    return tool_name, command


def _extract_ticket_or_skip(tool_name: str, command: str, logger) -> Optional[str]:
    """識別 complete 命令並提取 Ticket ID。"""
    if tool_name != "Bash":
        logger.debug(f"非 Bash 工具: {tool_name}，直接放行")
        _output_allow_json()
        return None

    if not is_complete_command(command):
        logger.debug(f"非 ticket track complete 命令: {command}")
        _output_allow_json()
        return None

    logger.info(f"識別到 ticket track complete 命令: {command}")

    ticket_id = extract_ticket_id_from_command(command, logger)
    if not ticket_id:
        logger.error("無法從命令中提取 Ticket ID")
        _output_allow_json()
        return None

    logger.info(f"提取 Ticket ID: {ticket_id}")
    return ticket_id


# ============================================================================
# 主入口點
# ============================================================================

def main() -> int:
    """主入口點 - 驗收流程協調"""
    logger = setup_hook_logging("acceptance-gate")

    try:
        logger.info(CoreMessages.HOOK_START.format(hook_name="Acceptance Gate Hook"))

        # 步驟 1: 解析驗證輸入
        input_data = read_json_from_stdin(logger)

        if is_subagent_environment(input_data):
            logger.info("偵測到 subagent 環境（agent_id=%s），跳過 AskUserQuestion 提醒", input_data.get("agent_id"))
            return EXIT_SUCCESS

        parsed = _parse_and_validate_input(input_data, logger)
        if parsed is None:
            return EXIT_SUCCESS
        tool_name, command = parsed

        # 步驟 2: 識別命令並提取 Ticket ID
        ticket_id = _extract_ticket_or_skip(tool_name, command, logger)
        if ticket_id is None:
            return EXIT_SUCCESS

        # 步驟 3: 檢查驗收狀態
        project_dir = get_project_root()
        result = check_acceptance_status(ticket_id, project_dir, logger)
        logger.info(
            f"驗收結果: should_block={result.should_block}, "
            f"has_acceptance={result.has_acceptance}, "
            f"has_new_error_patterns={result.has_new_error_patterns}, "
            f"pending_siblings={len(result.pending_sibling_tickets)}"
        )

        # 步驟 4: 生成輸出並儲存日誌
        output = generate_hook_output(ticket_id, result, project_dir, logger)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        status = "BLOCKED" if result.should_block else "ALLOWED"
        log_entry = f"""[{datetime.now().isoformat()}]
  TicketID: {ticket_id}
  Status: {status}

"""
        save_check_log("acceptance-gate", log_entry, logger)

        # 步驟 5: 決定 exit code
        if result.should_block:
            logger.warning("Acceptance Gate Hook：子任務未完成，阻止執行")
            return EXIT_BLOCK
        logger.info("Acceptance Gate Hook 檢查完成：允許執行")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/acceptance-gate/"
            },
            "error": {"type": type(e).__name__, "message": str(e)}
        }, ensure_ascii=False, indent=2))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "acceptance-gate"))
