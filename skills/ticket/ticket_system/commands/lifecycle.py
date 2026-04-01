"""
Ticket lifecycle 操作模組

負責 Ticket 生命週期的核心操作：claim（認領）、complete（完成）、release（釋放）
"""

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
)
from ticket_system.lib.ticket_loader import (
    get_project_root,
    get_ticket_path,
    list_tickets,
    load_ticket,
    save_ticket,
)
from ticket_system.lib.ticket_validator import (
    validate_claimable_status,
    validate_completable_status,
    validate_acceptance_criteria,
    validate_execution_log,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    WarningMessages,
    format_error,
    format_info,
    format_warning,
)
from ticket_system.lib.command_lifecycle_messages import (
    LifecycleMessages,
    format_msg,
)
from ticket_system.lib.tdd_sequence import (
    validate_phase_prerequisite,
    PHASE_LABELS,
)
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
    resolve_ticket_path,
)
from ticket_system.lib.worklog_appender import append_worklog_progress
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY


# ============================================================================
# 自動 Handoff 輔助函式
# ============================================================================

def _auto_handoff_if_needed(ticket: Dict[str, Any], analysis: Dict[str, Any], version: str) -> None:
    """
    完成 Ticket 後，若有建議的下一步任務，自動建立 handoff 檔案

    Args:
        ticket: 已完成的 Ticket 資料
        analysis: 任務鏈分析結果（包含 suggestions）
        version: Ticket 所屬版本
    """
    # 若任務鏈全部完成，不建立 handoff
    if analysis.get("chain_complete", False):
        return

    # 若無建議的下一步，不建立 handoff
    suggestions = analysis.get("suggestions", [])
    if not suggestions:
        return

    # 選擇優先級最高的建議任務
    next_suggestion = suggestions[0]
    next_ticket_id = next_suggestion.get("ticket_id")
    next_title = next_suggestion.get("title", "")

    if not next_ticket_id:
        return

    # 載入下一步任務
    next_ticket = load_ticket(version, next_ticket_id)
    if not next_ticket:
        return

    # 調用 handoff.py 的內部函式建立 handoff 檔案
    try:
        from ticket_system.commands.handoff import _create_handoff_file_internal
        exit_code = _create_handoff_file_internal(next_ticket, "auto")
        if exit_code == 0:
            _print_auto_handoff_prompt(next_ticket_id, next_title)
    except ImportError:
        # 如果無法匯入，靜默跳過自動 handoff
        pass


def _print_auto_handoff_prompt(next_ticket_id: str, next_title: str) -> None:
    """
    印出自動 handoff 完成後的提示訊息

    Args:
        next_ticket_id: 下一步任務 ID
        next_title: 下一步任務標題
    """
    print()
    print(LifecycleMessages.AUTO_HANDOFF_SEPARATOR)
    print(LifecycleMessages.AUTO_HANDOFF_HEADER)
    print(LifecycleMessages.AUTO_HANDOFF_SEPARATOR)
    print()
    print(format_msg(LifecycleMessages.AUTO_HANDOFF_NEXT_TASK, next_ticket_id=next_ticket_id))
    print(format_msg(LifecycleMessages.AUTO_HANDOFF_NEXT_TASK_TITLE, next_title=next_title))
    print()
    print(LifecycleMessages.AUTO_HANDOFF_CLEAR_PROMPT)
    print()
    print(LifecycleMessages.AUTO_HANDOFF_AUTO_LOAD)
    print(LifecycleMessages.AUTO_HANDOFF_SEPARATOR)
    print()


# ============================================================================
# Phase 前置條件驗證輔助函式
# ============================================================================

def _get_completed_phases_in_chain(ticket: Dict[str, Any], version: str) -> List[str]:
    """
    取得同任務鏈中已完成的所有 Phase。

    根據 Ticket 的 tdd_phase 欄位和任務鏈結構，找出該任務鏈中
    所有已完成（status: completed）的 Phase。

    Args:
        ticket: 當前 Ticket 資料
        version: Ticket 所屬版本

    Returns:
        List[str]: 已完成的 Phase 清單（如 ["phase1", "phase2", "phase3a"]）
    """
    completed_phases = []

    # Guard Clause：若無 chain 資訊，無法分析
    chain = ticket.get("chain", {})
    if not chain:
        return completed_phases

    # 取得任務鏈根 ID
    root_id = chain.get("root", ticket.get("id", ""))

    # 列出所有 Ticket 並建立映射
    all_tickets = list_tickets(version)
    ticket_map = {t.get("id"): t for t in all_tickets}

    # Guard Clause：無法取得所有 Ticket
    if not all_tickets:
        return completed_phases

    # 找出所有屬於同一任務鏈的 Ticket（透過 chain.root）
    chain_tickets = [
        t for t in all_tickets
        if t.get("chain", {}).get("root") == root_id
    ]

    # 遍歷任務鏈中的所有 Ticket，收集已完成且有 tdd_phase 的任務
    for t in chain_tickets:
        status = t.get("status", "")
        tdd_phase = t.get("tdd_phase", "")

        # 只收集已完成且有 tdd_phase 的任務
        if status == STATUS_COMPLETED and tdd_phase:
            # 正規化 phase 名稱（確保格式一致）
            normalized_phase = _normalize_phase_name(tdd_phase)
            if normalized_phase and normalized_phase not in completed_phases:
                completed_phases.append(normalized_phase)

    return completed_phases


def _normalize_phase_name(phase: str) -> str:
    """
    正規化 Phase 名稱，確保與標準格式一致。

    支援各種輸入格式：
    - "phase1", "Phase 1", "phase1", "Phase 1（功能設計）" → "phase1"
    - "phase3a", "Phase 3a", "phase3a" → "phase3a"
    - "Phase 2（測試設計）" → "phase2"

    Args:
        phase: 原始 Phase 名稱

    Returns:
        str: 正規化後的 Phase 名稱（如 "phase1"），若無效返回空字符串
    """
    if not phase:
        return ""

    # 轉換為小寫並移除空格
    normalized = phase.lower().strip()

    # 移除中括弧及其內容（如 "Phase 1（功能設計）" → "phase 1"）
    if "（" in normalized:
        normalized = normalized.split("（")[0].strip()
    if "(" in normalized:
        normalized = normalized.split("(")[0].strip()

    # 移除 "phase" 前綴，解析數字部分
    if normalized.startswith("phase"):
        # 提取數字部分（如 "phase1" → "1", "phase3a" → "3a"）
        num_part = normalized[5:].strip()
        # 重新組合為標準格式
        if num_part:
            return f"phase{num_part}"

    # 若不符合預期格式，返回空字符串
    return ""


def _print_phase_prerequisite_warning(
    ticket_id: str,
    current_phase: str,
    missing_prerequisites: List[str],
    version: str,
) -> None:
    """
    印出 Phase 前置條件警告訊息。

    顯示缺失的前置 Phase 及其對應的 Ticket ID。

    Args:
        ticket_id: 當前 Ticket ID
        current_phase: 當前 Phase
        missing_prerequisites: 缺失的前置 Phase 清單
        version: 版本號
    """
    print()
    print(LifecycleMessages.PHASE_PREREQUISITE_WARNING_SEPARATOR)
    print(LifecycleMessages.PHASE_PREREQUISITE_WARNING_HEADER)
    print(LifecycleMessages.PHASE_PREREQUISITE_WARNING_SEPARATOR)
    print()

    # 顯示當前 Ticket 的 Phase
    current_phase_label = PHASE_LABELS.get(current_phase, current_phase)
    print(format_msg(LifecycleMessages.PHASE_PREREQUISITE_CURRENT, ticket_id=ticket_id, current_phase_label=current_phase_label))

    # 顯示缺失的前置 Phase
    if missing_prerequisites:
        print()
        print(LifecycleMessages.PHASE_PREREQUISITE_MISSING_HEADER)
        for missing_phase in missing_prerequisites:
            missing_label = PHASE_LABELS.get(missing_phase, missing_phase)
            print(format_msg(LifecycleMessages.PHASE_PREREQUISITE_MISSING_ITEM, missing_label=missing_label))

        # 嘗試找到同任務鏈中對應的 Ticket
        all_tickets = list_tickets(version)
        ticket = load_ticket(version, ticket_id)
        if ticket and all_tickets:
            chain = ticket.get("chain", {})
            root_id = chain.get("root", ticket_id)

            # 找出屬於同任務鏈的缺失 Phase 對應 Ticket
            print()
            print(LifecycleMessages.PHASE_PREREQUISITE_CORRESPONDING)
            for missing_phase in missing_prerequisites:
                for t in all_tickets:
                    t_root = t.get("chain", {}).get("root", t.get("id", ""))
                    t_phase = _normalize_phase_name(t.get("tdd_phase", ""))
                    if t_root == root_id and t_phase == missing_phase:
                        t_id = t.get("id", "")
                        t_status = t.get("status", "pending")
                        t_title = t.get("title", "")
                        print(format_msg(LifecycleMessages.PHASE_PREREQUISITE_CORRESPONDING_ID, ticket_id=t_id))
                        print(format_msg(LifecycleMessages.PHASE_PREREQUISITE_CORRESPONDING_TITLE, title=t_title))
                        print(format_msg(LifecycleMessages.PHASE_PREREQUISITE_CORRESPONDING_STATUS, status=t_status))

    print()
    print(LifecycleMessages.PHASE_PREREQUISITE_SUGGESTION)
    print()


# ============================================================================
# TicketLifecycle 物件層 - 封裝生命週期操作
# ============================================================================

class TicketLifecycle:
    """
    Ticket 生命週期管理物件層

    封裝 claim、complete、release 的核心邏輯，提高可測試性和程式碼組織。
    version 成為實例變數，減少函式參數傳遞冗餘。
    """

    def __init__(self, version: str) -> None:
        """
        初始化生命週期物件

        Args:
            version: Ticket 所屬版本，例如 "0.31.0"
        """
        self.version = version

    def claim(self, ticket_id: str) -> int:
        """
        認領 Ticket - 將狀態從 pending 變更為 in_progress

        執行步驟：
        1. 載入 Ticket 並驗證存在
        2. 驗證狀態（是否可認領）
        3. 若有 tdd_phase，驗證前置 Phase 條件
        4. 若前置條件未滿足，顯示警告但允許使用者決定是否繼續
        5. 更新 Ticket 狀態
        6. 顯示認領檢查清單

        Args:
            ticket_id: Ticket ID，例如 "0.31.0-W4-001"

        Returns:
            0 表示成功，非 0 表示失敗
        """
        ticket, error = load_and_validate_ticket(self.version, ticket_id)
        if error:
            return 1

        status = ticket.get("status", STATUS_PENDING)

        # 驗證是否可認領
        can_claim, error_msg = validate_claimable_status(ticket_id, status)
        if not can_claim:
            print(f"[Warning] {error_msg}")
            return 1

        # 檢查 Phase 前置條件（若 Ticket 有 tdd_phase 欄位）
        tdd_phase = ticket.get("tdd_phase", "")
        if tdd_phase:
            # 正規化 Phase 名稱
            normalized_phase = _normalize_phase_name(tdd_phase)

            # 取得同任務鏈中已完成的 Phase
            completed_phases = _get_completed_phases_in_chain(ticket, self.version)

            # 驗證前置條件
            validation_result = validate_phase_prerequisite(
                normalized_phase,
                completed_phases
            )

            # 若前置條件未滿足，顯示警告
            if not validation_result.valid:
                _print_phase_prerequisite_warning(
                    ticket_id,
                    normalized_phase,
                    validation_result.missing_prerequisites,
                    self.version,
                )

        # 更新 Ticket 狀態
        ticket["status"] = STATUS_IN_PROGRESS
        ticket["assigned"] = True
        ticket["started_at"] = datetime.now().isoformat(timespec="seconds")

        ticket_path = resolve_ticket_path(ticket, self.version, ticket_id)
        save_ticket(ticket, ticket_path)

        print(format_info(InfoMessages.TICKET_CLAIMED, ticket_id=ticket_id))
        print(f"   開始時間: {ticket['started_at']}")

        # 顯示認領檢查清單
        _print_claim_checklist(ticket)

        return 0

    def complete(self, ticket_id: str) -> int:
        """
        完成 Ticket - 使用「先查後做」驗證流程

        驗證步驟：
        1. 載入 Ticket
        2. 檢查狀態（已完成 → 友好訊息；未認領/被阻塞 → 阻止）
        3. 檢查驗收條件（有未完成項 → 列出並阻止）
        4. 執行完成操作

        Args:
            ticket_id: Ticket ID，例如 "0.31.0-W4-001"

        Returns:
            0 表示成功，非 0 表示失敗
        """
        # Step 1：載入 Ticket
        ticket, error = load_and_validate_ticket(self.version, ticket_id)
        if error:
            return 1

        # Step 2：驗證狀態
        status = ticket.get("status", STATUS_PENDING)
        completed_at = ticket.get("completed_at")

        can_complete, status_msg, is_already_complete = validate_completable_status(
            ticket_id,
            status,
            completed_at
        )

        # 若已完成，顯示友好訊息並返回 0
        if is_already_complete:
            print(format_info(status_msg))
            return 0

        # 若不可完成，阻止操作
        if not can_complete:
            print(f"[Error] {status_msg}")
            return 1

        # Step 3：驗證驗收條件
        acceptance_list = ticket.get("acceptance")
        criteria_complete, incomplete_items = validate_acceptance_criteria(
            ticket_id,
            acceptance_list
        )

        # 若有未完成的驗收條件，列出並阻止
        if not criteria_complete:
            print(f"[Error] {ticket_id} 有未完成的驗收條件")
            print()
            print("   未完成項:")
            for item in incomplete_items:
                print(f"   {item}")
            print()
            print("   請完成所有驗收條件後再執行 complete")
            return 1

        # Step 3.5：檢查執行日誌是否已填寫（soft check - 警告但不阻止）
        body = ticket.get("_body", "")
        if body:
            log_filled, unfilled_sections = validate_execution_log(ticket_id, body)
            if not log_filled:
                print()
                print(format_warning(WarningMessages.EXECUTION_LOG_NOT_FILLED))
                for section in unfilled_sections:
                    print(f"   - {section}")
                print()
                print(f"   {WarningMessages.EXECUTION_LOG_SUGGESTION}")
                for section in unfilled_sections:
                    print(f'   ticket track append-log {ticket_id} --section "{section}" "內容"')
                print()
                print("   繼續完成? (已執行完成操作)")
                print()

        # Step 4：執行完成操作
        ticket["status"] = STATUS_COMPLETED
        ticket["completed_at"] = datetime.now().isoformat(timespec="seconds")

        ticket_path = resolve_ticket_path(ticket, self.version, ticket_id)
        save_ticket(ticket, ticket_path)

        print(format_info(InfoMessages.TICKET_COMPLETED, ticket_id=ticket_id))

        # 自動追加 worklog 進度行
        ticket_title = ticket.get("title", "")
        append_worklog_progress(self.version, ticket_id, ticket_title)

        # 驗收提示
        _print_stage_separator("驗收提示")
        print()
        print("Ticket 完成後，請執行驗收流程：")
        print()
        print("  1. 確認所有驗收條件已勾選")
        print("  2. 確認所有建議已處理（無 pending）")
        print("  3. 派發 acceptance-auditor 執行驗收")
        print()
        print("  豁免條件：P0 緊急任務、純文件更新、任務範圍單純")
        print()
        print(
            f"  [Proposals 同步] 若此 Ticket ({ticket_id}) 被 proposals-tracking.yaml 引用，"
        )
        print(
            "  請同步更新對應提案的 checklist 狀態和 verified_by 欄位"
        )

        # 任務鏈後續步驟建議
        all_tickets = list_tickets(self.version)
        analysis = _analyze_next_steps(ticket, all_tickets)
        _print_next_steps(analysis)

        # 自動 handoff：若有後續任務，自動建立 handoff 檔案
        _auto_handoff_if_needed(ticket, analysis, self.version)

        return 0

    def release(self, ticket_id: str) -> int:
        """
        釋放 Ticket - 將進行中的 Ticket 狀態變更為被阻塞

        Args:
            ticket_id: Ticket ID，例如 "0.31.0-W4-001"

        Returns:
            0 表示成功，非 0 表示失敗
        """
        ticket, error = load_and_validate_ticket(self.version, ticket_id)
        if error:
            return 1

        status = ticket.get("status", STATUS_PENDING)

        # 只有進行中的 Ticket 可以釋放
        if status == STATUS_PENDING:
            print(f"[Warning] {ticket_id} 尚未被接手，無法釋放")
            return 1
        if status == STATUS_COMPLETED:
            print(f"[Warning] {ticket_id} 已完成，無法釋放")
            return 1
        if status == STATUS_BLOCKED:
            print(f"[Warning] {ticket_id} 已被阻塞，無法釋放")
            return 1

        # 釋放 Ticket
        ticket["status"] = STATUS_BLOCKED
        ticket["assigned"] = False
        ticket["started_at"] = None

        ticket_path = resolve_ticket_path(ticket, self.version, ticket_id)
        save_ticket(ticket, ticket_path)

        print(format_info(InfoMessages.TICKET_RELEASED, ticket_id=ticket_id))
        print(f"   狀態: 被阻塞")
        return 0


# ============================================================================
# 生命週期階段提示模組
# ============================================================================

def _print_stage_separator(title: str) -> None:
    """印出階段分隔線"""
    print()
    print(SEPARATOR_PRIMARY)
    print(f"[{title}]")
    print(SEPARATOR_PRIMARY)


def _check_pending_children(
    ticket: Dict[str, Any],
    ticket_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    優先級 1：檢查待處理的子 Ticket
    """
    suggestions = []
    children = ticket.get("children", [])
    for child_id in children:
        child = ticket_map.get(child_id)
        if child and child.get("status") == "pending":
            suggestions.append({
                "priority": 1,
                "ticket_id": child_id,
                "title": child.get("title", ""),
                "reason": "子 Ticket 現在可以開始",
                "status_change": "pending → 可認領",
            })
    return suggestions


def _check_unblocked_tickets(
    ticket_id: str,
    all_tickets: List[Dict[str, Any]],
    ticket_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    優先級 2：檢查被解除阻塞的 Ticket
    """
    suggestions = []
    for t in all_tickets:
        blocked_by = t.get("blockedBy", [])
        if ticket_id in blocked_by and t.get("status") in ["pending", "blocked"]:
            # 檢查是否所有阻塞都已解除
            all_unblocked = all(
                ticket_map.get(b, {}).get("status") == "completed"
                for b in blocked_by
            )
            if all_unblocked:
                suggestions.append({
                    "priority": 2,
                    "ticket_id": t.get("id"),
                    "title": t.get("title", ""),
                    "reason": f"阻塞已解除（blockedBy {ticket_id} 已完成）",
                    "status_change": f"{t.get('status')} → 可認領",
                })
    return suggestions


def _check_siblings(
    ticket: Dict[str, Any],
    ticket_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    優先級 3：檢查同層兄弟 Ticket
    """
    suggestions = []
    ticket_id = ticket.get("id", "")
    chain_info = ticket.get("chain", {})
    parent_id = chain_info.get("parent")

    if not parent_id:
        return suggestions

    parent = ticket_map.get(parent_id)
    if not parent:
        return suggestions

    siblings = parent.get("children", [])
    for sibling_id in siblings:
        if sibling_id != ticket_id:
            sibling = ticket_map.get(sibling_id)
            if sibling and sibling.get("status") == "pending":
                suggestions.append({
                    "priority": 3,
                    "ticket_id": sibling_id,
                    "title": sibling.get("title", ""),
                    "reason": "同層兄弟 Ticket 待處理",
                    "status_change": "pending",
                })
    return suggestions


def _check_same_wave(
    ticket: Dict[str, Any],
    all_tickets: List[Dict[str, Any]],
    existing_suggestions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    優先級 4：檢查同 Wave 的其他 pending Ticket
    """
    suggestions = []
    ticket_id = ticket.get("id", "")
    current_wave = ticket.get("wave")

    if not current_wave:
        return suggestions

    existing_ids = {s["ticket_id"] for s in existing_suggestions}
    same_wave_pending = [
        t for t in all_tickets
        if t.get("wave") == current_wave
        and t.get("status") == "pending"
        and t.get("id") != ticket_id
        and t.get("id") not in existing_ids
    ]

    if same_wave_pending:
        # 取第一個作為建議
        next_ticket = same_wave_pending[0]
        suggestions.append({
            "priority": 4,
            "ticket_id": next_ticket.get("id"),
            "title": next_ticket.get("title", ""),
            "reason": f"同 Wave 還有 {len(same_wave_pending)} 個待處理",
            "status_change": "pending",
        })
    return suggestions


def _calc_chain_progress(
    ticket: Dict[str, Any],
    all_tickets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    優先級 5：計算任務鏈進度
    """
    ticket_id = ticket.get("id", "")
    chain_info = ticket.get("chain", {})
    root_id = chain_info.get("root", ticket_id)

    # 嘗試從 chain.root 取得鏈票
    chain_tickets = [t for t in all_tickets if t.get("chain", {}).get("root") == root_id]
    # 備用方案：使用 parent_id 關係
    if not chain_tickets:
        chain_tickets = [t for t in all_tickets if t.get("id") == root_id or t.get("parent_id") == root_id]

    completed_count = sum(1 for t in chain_tickets if t.get("status") == "completed")
    total_count = len(chain_tickets)

    return {
        "completed": completed_count,
        "total": total_count,
        "root_id": root_id,
    }


def _analyze_next_steps(ticket: Dict[str, Any], all_tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析任務鏈後續步驟

    優先級：
    1. 有子 Ticket 可開始
    2. 有被解除阻塞的 Ticket
    3. 有同層兄弟 Ticket
    4. 同 Wave 有其他 pending
    5. 任務鏈全部完成
    """
    ticket_id = ticket.get("id", "")

    result = {
        "completed_id": ticket_id,
        "completed_title": ticket.get("title", ""),
        "suggestions": [],
        "chain_progress": {"completed": 0, "total": 0},
        "chain_complete": False,
    }

    # 建立 ticket_id -> ticket 的映射
    ticket_map = {t.get("id"): t for t in all_tickets}

    # 優先級 1：檢查子 Ticket
    suggestions = _check_pending_children(ticket, ticket_map)
    result["suggestions"].extend(suggestions)

    # 優先級 2：檢查被解除阻塞的 Ticket
    suggestions = _check_unblocked_tickets(ticket_id, all_tickets, ticket_map)
    result["suggestions"].extend(suggestions)

    # 優先級 3：檢查兄弟 Ticket
    suggestions = _check_siblings(ticket, ticket_map)
    result["suggestions"].extend(suggestions)

    # 優先級 4：檢查同 Wave 的其他 pending Ticket
    suggestions = _check_same_wave(ticket, all_tickets, result["suggestions"])
    result["suggestions"].extend(suggestions)

    # 優先級 5：計算任務鏈進度
    progress = _calc_chain_progress(ticket, all_tickets)
    result["chain_progress"] = progress

    # 檢查任務鏈是否全部完成
    if progress["completed"] == progress["total"] and progress["total"] > 0:
        result["chain_complete"] = True

    # 按優先級排序建議
    result["suggestions"].sort(key=lambda x: x["priority"])

    return result


def _print_next_steps(analysis: Dict[str, Any]) -> None:
    """印出任務鏈後續步驟建議"""
    _print_stage_separator("任務鏈後續步驟建議")
    print()

    # 已完成的 Ticket
    print(f"已完成: {analysis['completed_id']}")
    if analysis['completed_title']:
        print(f"        [{analysis['completed_title']}]")
    print()

    # 任務鏈進度
    progress = analysis["chain_progress"]
    if progress["total"] > 0:
        print(f"任務鏈進度: {progress['completed']}/{progress['total']} completed")
        print(f"   Root: {progress.get('root_id', 'N/A')}")
        print()

    # 任務鏈全部完成
    if analysis["chain_complete"]:
        print("任務鏈全部完成!")
        print()
        return

    # 建議
    suggestions = analysis["suggestions"]
    if suggestions:
        print("建議下一步:")
        for i, s in enumerate(suggestions[:3], 1):  # 最多顯示 3 個建議
            print(f"   {i}. {s['ticket_id']}")
            print(f"      [{s['title']}]")
            print(f"      原因: {s['reason']}")
            print(f"      狀態: {s['status_change']}")
            print()
    else:
        print("無建議的下一步 Ticket")
        print("   可能原因：同 Wave 無待處理 Ticket，或需要開始新 Wave")
        print()


def _print_claim_checklist(ticket: Dict[str, Any]) -> None:
    """印出認領時的檢查清單"""
    _print_stage_separator("認領檢查清單")
    print()

    # 檢查阻塞依賴
    blocked_by = ticket.get("blockedBy", [])
    if blocked_by:
        print(f"[WARNING] 此 Ticket 有阻塞依賴:")
        for b in blocked_by:
            print(f"   - {b}")
        print("   請確認這些依賴已完成後再開始")
        print()

    # 標準檢查項目
    print("開始前請確認:")
    print(LifecycleMessages.CHECKLIST_DESIGN_DOCS)
    print(LifecycleMessages.CHECKLIST_ACCEPTANCE)
    print(LifecycleMessages.CHECKLIST_DEV_ENV)

    # 根據 Ticket 類型給出特定提示
    ticket_type = ticket.get("type", "IMP")
    if ticket_type in ["IMP", "ADJ"]:
        print(LifecycleMessages.CHECKLIST_ERROR_PATTERNS)

    print(LifecycleMessages.CHECKLIST_SCOPE_VERIFICATION)
    print(LifecycleMessages.CHECKLIST_EXECUTION_LOG)
    print()


# ============================================================================
# 核心生命週期函式（導出給外部使用）
# ============================================================================

def execute_claim(args: argparse.Namespace, version: str) -> int:
    """
    認領 Ticket - 函式包裝層（向後相容）

    使用 TicketLifecycle 物件執行實際操作。
    """
    lifecycle = TicketLifecycle(version)
    return lifecycle.claim(args.ticket_id)


def execute_complete(args: argparse.Namespace, version: str) -> int:
    """
    完成 Ticket - 函式包裝層（向後相容）

    使用 TicketLifecycle 物件執行實際操作。
    """
    lifecycle = TicketLifecycle(version)
    return lifecycle.complete(args.ticket_id)


def execute_release(args: argparse.Namespace, version: str) -> int:
    """
    釋放 Ticket - 函式包裝層（向後相容）

    使用 TicketLifecycle 物件執行實際操作。
    """
    lifecycle = TicketLifecycle(version)
    return lifecycle.release(args.ticket_id)
