"""
Ticket lifecycle 操作模組

負責 Ticket 生命週期的核心操作：claim（認領）、complete（完成）、release（釋放）
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
    STATUS_CLOSED,
    TERMINAL_STATUSES,
    CLOSE_REASONS,
    CLOSE_REASON_RETROSPECTIVE_UNKNOWN,
)
from ticket_system.lib.ticket_loader import (
    get_project_root,
    get_ticket_path,
    list_tickets,
    load_ticket,
    save_ticket,
)
from ticket_system.lib.staleness import format_stale_warning
from ticket_system.lib.ticket_validator import (
    validate_claimable_status,
    validate_completable_status,
    validate_acceptance_criteria,
    validate_execution_log,
    validate_execution_log_by_type,
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
from ticket_system.lib.command_tracking_messages import (
    ClaimWrapMessages,
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
from ticket_system.lib.project_root import resolve_project_cwd
from ticket_system.commands.claim_verification import (
    collect_ac_verifications,
    prompt_user_decision,
    render_results,
    run_all_verifications,
    summarize_results,
)


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
# Body 同步輔助函式（W17-016.4）
# ============================================================================

def sync_completion_body_fields(
    body: str,
    completed_at: str,
    executing_agent: str = "",
) -> str:
    """
    將 frontmatter 的完成資訊同步寫回 body 的 Completion Info 區塊。

    處理三個欄位（僅替換 placeholder，不覆蓋已填值）：
    - **Completion Time**: (pending) → completed_at ISO
    - **Executing Agent**: 若為空或 placeholder，填入 executing_agent
    - **Review Status**: 保留現狀（無權威資料來源）

    Args:
        body: Ticket body 文字
        completed_at: ISO 時間字串
        executing_agent: who.current 值（可為空）

    Returns:
        更新後的 body 文字；若無相符欄位則原樣返回。
    """
    if not body:
        return body

    # Completion Time: 僅替換 (pending) placeholder
    body = re.sub(
        r"(\*\*Completion Time\*\*:\s*)\(pending\)",
        lambda m: f"{m.group(1)}{completed_at}",
        body,
    )

    # Executing Agent: 僅當為空或 placeholder 時填入
    if executing_agent:
        body = re.sub(
            r"(\*\*Executing Agent\*\*:\s*)(\(pending\)|TBD|未指派)?\s*$",
            lambda m: f"{m.group(1)}{executing_agent}",
            body,
            flags=re.MULTILINE,
        )

    return body


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

    def claim_with_verification(
        self,
        ticket_id: str,
        skip_verify: bool = False,
        auto_yes: bool = False,
    ) -> int:
        """整合 AC 自動驗證的 claim 主流程入口（PROP-010 方案 2）。

        決策樹：

        - ``skip_verify=True`` → 略過驗證、走既有 ``claim``；
          若 ``auto_yes=True`` 同時為真，額外 stderr 提示 ``--yes`` 被忽略。
        - ``collect_ac_verifications`` 拋 ``ValueError`` → 降級直接 claim。
        - Ticket 無 AC（S1） → 直接 claim。
        - ``run_all_verifications`` 拋 ``KeyboardInterrupt`` → return 130。
        - ``summary.status == 'none_verifiable'``（S2） → 顯示摘要後 claim。
        - ``summary.status == 'all_passed'``（S4） → stderr 拒絕訊息 + return 1。
        - ``summary.status == 'has_failures'``（S3） → render + prompt。
          y → claim；n → return 1。

        Args:
            ticket_id: Ticket ID。
            skip_verify: ``--skip-verify`` flag，完全略過驗證。
            auto_yes: ``--yes`` flag，非互動模式自動選 y。

        Returns:
            0 / 1 / 130 exit code。
        """
        # --skip-verify + --yes 衝突：提示 --yes 被忽略
        if skip_verify and auto_yes:
            print(
                "[Warning] --yes 已被忽略（同時指定 --skip-verify 時不執行驗證，"
                "--yes 無作用）",
                file=sys.stderr,
            )

        if skip_verify:
            print("[AC verification] 已跳過（--skip-verify）")
            return self.claim(ticket_id)

        # 非 tty 且無任何 flag：fail-closed 拒絕 claim（§B.4）
        if not sys.stdin.isatty() and not auto_yes:
            print(
                "[AC verification] 非互動環境且未指定 --yes / --skip-verify，"
                "已取消；請顯式傳 flag 表明意圖",
                file=sys.stderr,
            )
            return 1

        # 嘗試解析 AC 與模板配對
        try:
            pairs = collect_ac_verifications(ticket_id)
        except ValueError as err:
            print(
                f"[Warning] AC 解析失敗：{err}；降級為直接 claim",
                file=sys.stderr,
            )
            return self.claim(ticket_id)

        # S1：無 AC
        if not pairs:
            return self.claim(ticket_id)

        # 執行驗證
        cwd = resolve_project_cwd()
        try:
            results = run_all_verifications(pairs, cwd)
        except KeyboardInterrupt:
            print(
                "[AC verification] 中斷：未更新 Ticket 狀態",
                file=sys.stderr,
            )
            return 130

        summary = summarize_results(results)

        # S2：全部不可驗證
        if summary.status == "none_verifiable":
            print(
                f"[AC verification] Ticket {ticket_id}：{summary.total} 項 AC "
                f"皆無法自動驗證（跳過驗證，直接 claim）"
            )
            return self.claim(ticket_id)

        # S4：全部可驗證 AC 已達成 → 拒絕 claim
        if summary.status == "all_passed":
            print(
                f"[AC verification] Ticket {ticket_id}：{summary.passed} 項可驗證 "
                f"AC 皆已達成",
                file=sys.stderr,
            )
            print(
                f"建議改用 `ticket track complete {ticket_id}`，"
                "或檢討 Ticket 是否需拆分",
                file=sys.stderr,
            )
            return 1

        # S3：has_failures → 顯示結果 + prompt
        rendered = render_results(summary, results, ticket_id)
        if rendered:
            print(rendered)
        decision = prompt_user_decision(summary, auto_yes)
        if decision == "y":
            return self.claim(ticket_id)
        return 1

    def complete(
        self,
        ticket_id: str,
        yes_spawned: bool = False,
        skip_body_check: bool = False,
    ) -> int:
        """
        完成 Ticket - 使用「先查後做」驗證流程

        驗證步驟：
        1. 載入 Ticket
        2. 檢查狀態（已完成 → 友好訊息；未認領/被阻塞 → 阻止）
        3. 檢查驗收條件（有未完成項 → 列出並阻止）
        3.5. 執行日誌 soft check
        3.6. ANA spawned 非 terminal blocking confirmation（W12-005 / PC-075 Phase 2）
        4. 執行完成操作

        Args:
            ticket_id: Ticket ID，例如 "0.31.0-W4-001"
            yes_spawned: 非互動環境下旁路 ANA spawned 非 terminal 的 confirmation

        Returns:
            0 表示成功，2 表示 spawned 阻擋/取消，其他非 0 表示失敗
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

        # Step 3.5：type-aware body schema 驗證（W17-016.3 hard block + escape valve）
        # 對照 .claude/pm-rules/ticket-body-schema.md 各 type 必填章節；含佔位符則阻擋。
        body = ticket.get("_body", "")
        ticket_type = ticket.get("type", "")
        if body and not skip_body_check:
            typed_passed, typed_unfilled = validate_execution_log_by_type(ticket_type, body)
            if not typed_passed:
                print()
                print(f"[Error] {ticket_id} body 未依 {ticket_type} schema 填寫必填章節")
                print()
                print("   未填寫的必填章節：")
                for section in typed_unfilled:
                    print(f"   - {section}")
                print()
                print("   依 .claude/pm-rules/ticket-body-schema.md，此 type 以下章節為必填且須替換佔位符：")
                for section in typed_unfilled:
                    print(
                        f'   ticket track append-log {ticket_id} --section "{section}" --content "內容"'
                    )
                print()
                print("   逃生閥：--skip-body-check（需附理由於 Completion Info）")
                return 1
        elif body and skip_body_check:
            # 逃生閥啟用：仍執行舊 soft check 作為可見提醒
            log_filled, unfilled_sections = validate_execution_log(ticket_id, body)
            if not log_filled:
                print()
                print(format_warning(WarningMessages.EXECUTION_LOG_NOT_FILLED))
                for section in unfilled_sections:
                    print(f"   - {section}")
                print()
                print("   --skip-body-check 已啟用，強制完成；請於 Completion Info 記錄理由")
                print()

        # Step 3.6：ANA spawned 非 terminal blocking confirmation（W12-005 / PC-075 Phase 2）
        spawned_exit = _handle_ana_spawned_confirmation(ticket, self.version, yes_spawned)
        if spawned_exit is not None:
            return spawned_exit

        # Step 4：執行完成操作
        ticket["status"] = STATUS_COMPLETED
        ticket["completed_at"] = datetime.now().isoformat(timespec="seconds")

        # W17-016.4：同步 completed_at / Executing Agent 寫回 body
        existing_body = ticket.get("_body", "")
        if existing_body:
            who = ticket.get("who") or {}
            executing_agent = who.get("current") if isinstance(who, dict) else ""
            ticket["_body"] = sync_completion_body_fields(
                existing_body,
                ticket["completed_at"],
                executing_agent or "",
            )

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

        # W5-019：父 complete → 子 cascade 解鎖 + 未完成 children 警告
        # 置於 _auto_handoff_if_needed 之前，讓解鎖後的子狀態可影響 handoff 建議
        children_ids = ticket.get("children", [])
        if children_ids:
            unblocked, pending = _cascade_unblock_children(ticket, self.version)
            if unblocked:
                _print_cascade_unblocked(unblocked)
            if pending:
                _print_children_warnings(pending)

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

    def close(
        self,
        ticket_id: str,
        resolved_by: str,
        reason_code: str,
        reason_note: str = "",
        retrospective: bool = False,
    ) -> int:
        """
        關閉 Ticket - 問題已在其他 Ticket 一併解決，無需獨立處理

        與 complete 的區別：
        - complete：自己做完（需 who + acceptance 全勾）
        - close：被其他 Ticket 解決（需 resolved_by）

        W15-027 / PC-090：reason_code 必填且須為 CLOSE_REASONS 六種枚舉之一。
        retrospective=True 時允許填 'unknown'（C4 回顧式 close 補填場景）。

        Args:
            ticket_id: 要關閉的 Ticket ID
            resolved_by: 解決此問題的 Ticket ID
            reason_code: close_reason 枚舉值（必填，PC-090 C1）
            reason_note: 關閉原因補充說明（選填）
            retrospective: 是否為回顧式 close 補填（允許 unknown）

        Returns:
            0 表示成功，非 0 表示失敗
        """
        # Step 0：驗證 reason_code 枚舉（PC-090 C1/C4）
        valid_codes = set(CLOSE_REASONS)
        if retrospective:
            valid_codes = valid_codes | {CLOSE_REASON_RETROSPECTIVE_UNKNOWN}

        if not reason_code or reason_code not in valid_codes:
            sorted_codes = sorted(CLOSE_REASONS)
            print(
                f"[Error] --reason 必填且須為合法枚舉：{sorted_codes}"
                f"（retrospective 模式額外允許 '{CLOSE_REASON_RETROSPECTIVE_UNKNOWN}'）\n"
                f"        收到：{reason_code!r}\n"
                f"        參見：.claude/error-patterns/process-compliance/"
                f"PC-090-deferred-close-anti-pattern.md"
            )
            return 1

        # Step 1：載入 Ticket
        ticket, error = load_and_validate_ticket(self.version, ticket_id)
        if error:
            return 1

        # Step 2：驗證狀態
        status = ticket.get("status", STATUS_PENDING)

        if status == STATUS_CLOSED:
            print(format_error(
                ErrorMessages.CLOSE_ALREADY_CLOSED, ticket_id=ticket_id
            ))
            return 1

        # completed 可轉為 closed（事後發現應為 close 而非 complete）
        if status == STATUS_COMPLETED:
            print(f"[INFO] {ticket_id} 從 completed 轉為 closed")
            ticket.pop("completed_at", None)

        # Step 3：執行關閉操作
        default_note = f"已在 {resolved_by} 一併解決"
        close_note = reason_note if reason_note else default_note

        ticket["status"] = STATUS_CLOSED
        ticket["closed_at"] = datetime.now().isoformat(timespec="seconds")
        ticket["closed_by"] = resolved_by
        ticket["close_reason"] = reason_code
        ticket["close_reason_note"] = close_note
        if retrospective:
            ticket["retrospective"] = True

        ticket_path = resolve_ticket_path(ticket, self.version, ticket_id)
        save_ticket(ticket, ticket_path)

        print(format_info(InfoMessages.TICKET_CLOSED, ticket_id=ticket_id))
        print(f"   解決者: {resolved_by}")
        print(f"   原因代碼: {reason_code}")
        if retrospective:
            print(f"   回顧式補填（retrospective: true）")
        print(f"   補充說明: {close_note}")
        print(f"   關閉時間: {ticket['closed_at']}")

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
    # Context 驗證（W12-009：所有 Ticket 類型適用）
    print(LifecycleMessages.CHECKLIST_TARGET_EXISTS)
    print(LifecycleMessages.CHECKLIST_ASSUMPTIONS_VALID)
    print(LifecycleMessages.CHECKLIST_CROSS_PROJECT)
    print(LifecycleMessages.CHECKLIST_DEV_ENV)

    # 根據 Ticket 類型給出特定提示
    ticket_type = ticket.get("type", "IMP")
    if ticket_type in ["IMP", "ADJ"]:
        print(LifecycleMessages.CHECKLIST_ERROR_PATTERNS)
        print(LifecycleMessages.CHECKLIST_CONTEXT_BUNDLE)

    print(LifecycleMessages.CHECKLIST_SCOPE_VERIFICATION)
    print(LifecycleMessages.CHECKLIST_EXECUTION_LOG)
    print()

    # 附加簡化 WRAP 三問提示（Ticket 0.18.0-W10-028，來源 W10-027）
    _print_claim_wrap_prompt(ticket_type)


def _print_claim_wrap_prompt(ticket_type: str) -> None:
    """
    印出認領時的簡化 WRAP 三問提示。

    所有 ticket 類型共用三問區段；ANA 類型額外附加完整 /wrap-decision 提示。
    來源：Ticket 0.18.0-W10-027（ANA 分析結論）。

    Args:
        ticket_type: Ticket 類型（IMP/ANA/DOC 等），用於條件式輸出與文案格式化
    """
    _print_stage_separator(ClaimWrapMessages.WRAP_SECTION_TITLE)
    print()
    print(ClaimWrapMessages.WRAP_INTRO)
    print()
    print(ClaimWrapMessages.WRAP_WIDEN)
    print()
    print(ClaimWrapMessages.WRAP_ATTAIN_DISTANCE)
    print()
    print(ClaimWrapMessages.WRAP_PREPARE_WRONG)
    print()
    print(ClaimWrapMessages.WRAP_APPLIES_TO.format(ticket_type=ticket_type))
    print()

    if ticket_type == "ANA":
        print(ClaimWrapMessages.ANA_REALITY_TEST)
        print()
        print(ClaimWrapMessages.ANA_EXTRA_HEADER)
        print(ClaimWrapMessages.ANA_EXTRA_BODY)
        print()


# ============================================================================
# W5-019：父子 cascade 解鎖 + children 警告
# ============================================================================


def _can_cascade_unblock(
    child: Dict[str, Any],
    ticket_map: Dict[str, Any],
) -> bool:
    """
    判斷 blocked 的 child 是否可被解鎖。

    依 Phase 1 §6.8 AND 語義：child.blockedBy 中所有 ticket 皆 completed/closed
    才可解鎖。blockedBy 為空時視為可解鎖（異常狀態處理）。找不到 blocker 時保守
    保留 blocked。

    Args:
        child: 子 Ticket dict
        ticket_map: 版本內所有 ticket 的 id → dict 映射

    Returns:
        True 表示可解鎖（blocked → pending），False 表示保留 blocked
    """
    blocked_by = child.get("blockedBy") or []
    if not blocked_by:
        return True
    for blocker_id in blocked_by:
        blocker = ticket_map.get(blocker_id)
        if blocker is None:
            # 資料不一致時保守保留 blocked
            return False
        if blocker.get("status") not in (STATUS_COMPLETED, STATUS_CLOSED):
            return False
    return True


# ============================================================================
# ANA spawned 非 terminal 檢查（W12-005 / PC-075 Phase 2 — 方案 K）
# ============================================================================

# Terminal 狀態由 ticket_system/lib/constants.TERMINAL_STATUSES 統一提供，
# 與 .claude/hooks/acceptance_checkers/children_checker 的檢查同源（W14-004）。


def _collect_non_terminal_spawned(
    spawned_ids: List[str], version: str
) -> List[Tuple[str, str]]:
    """查詢 spawned ticket 清單中非 terminal 的項目。

    透過 list_tickets 一次性查詢版本下全部 tickets（process-scoped 快取），
    避免 N 次 load_ticket I/O。

    Args:
        spawned_ids: spawned_tickets 欄位 ID 清單
        version: 版本字串

    Returns:
        List[(ticket_id, status)] — 非 terminal 項目。
        找不到的 ticket 以 status="not_found" 回報。
    """
    if not spawned_ids:
        return []

    all_tickets = list_tickets(version)
    ticket_map: Dict[str, Any] = {t.get("id"): t for t in all_tickets}

    non_terminal: List[Tuple[str, str]] = []
    for sid in spawned_ids:
        t = ticket_map.get(sid)
        if t is None:
            non_terminal.append((sid, "not_found"))
            continue
        status = t.get("status", "unknown")
        if status not in TERMINAL_STATUSES:
            non_terminal.append((sid, status))
    return non_terminal


def _print_spawned_list(non_terminal: List[Tuple[str, str]]) -> None:
    """印出 spawned 非 terminal 項目清單至 stderr（格式：  - {id}: {status}）。"""
    for sid, status in non_terminal:
        print(
            format_msg(
                LifecycleMessages.SPAWNED_NON_TERMINAL_ITEM,
                spawned_id=sid,
                status=status,
            ),
            file=sys.stderr,
        )


def _handle_ana_spawned_confirmation(
    ticket: Dict[str, Any], version: str, yes_spawned: bool
) -> Optional[int]:
    """檢查 ANA type Ticket 的 spawned 非 terminal 狀態，必要時阻擋 complete。

    流程（方案 K — blocking confirmation）：
      1. 非 ANA type → 跳過（返回 None）
      2. spawned_tickets 空 → 跳過
      3. 全 terminal → 跳過
      4. 含非 terminal：
         - 互動環境（isatty）：顯示清單 + y/N prompt
           - y → 返回 None（繼續 complete）
           - 其他 → 返回 2（取消）
         - 非互動：
           - yes_spawned=True → 顯示清單（flag 旁路）返回 None
           - 否則 → 顯示 ERROR + 引導，返回 2

    Args:
        ticket: 當前 Ticket dict
        version: 版本字串
        yes_spawned: CLI --yes-spawned flag

    Returns:
        None — 通過檢查，繼續 complete
        int  — exit code（2 表示取消/阻擋）
    """
    if ticket.get("type") != "ANA":
        return None

    spawned_ids = ticket.get("spawned_tickets") or []
    if not spawned_ids:
        return None

    non_terminal = _collect_non_terminal_spawned(spawned_ids, version)
    if not non_terminal:
        return None

    ticket_id = ticket.get("id", "未知")
    count = len(non_terminal)
    is_interactive = sys.stdin.isatty()

    if is_interactive:
        # 互動環境：顯示清單 + y/N prompt
        print(
            format_msg(
                LifecycleMessages.SPAWNED_NON_TERMINAL_HEADER,
                ticket_id=ticket_id,
                count=count,
            ),
            file=sys.stderr,
        )
        _print_spawned_list(non_terminal)
        answer = input(LifecycleMessages.SPAWNED_INTERACTIVE_PROMPT)
        if answer.strip().lower() == "y":
            return None
        print(LifecycleMessages.SPAWNED_CANCELLED_INFO, file=sys.stderr)
        return 2

    # 非互動環境
    if yes_spawned:
        print(
            format_msg(
                LifecycleMessages.SPAWNED_FLAG_BYPASS_HEADER,
                ticket_id=ticket_id,
                count=count,
            ),
            file=sys.stderr,
        )
        _print_spawned_list(non_terminal)
        return None

    print(
        format_msg(
            LifecycleMessages.SPAWNED_NON_INTERACTIVE_ERROR,
            ticket_id=ticket_id,
            count=count,
        ),
        file=sys.stderr,
    )
    _print_spawned_list(non_terminal)
    print(
        format_msg(
            LifecycleMessages.SPAWNED_NON_INTERACTIVE_USAGE,
            ticket_id=ticket_id,
        ),
        file=sys.stderr,
    )
    return 2


def _cascade_unblock_children(
    parent_ticket: Dict[str, Any],
    version: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    對 parent 的 blocked children 執行 cascade 解鎖，並收集未完成 children 清單。

    依 Phase 1 §2.2 規則：
    - children 中 blocked 且 blockedBy 僅剩 completed/closed → 解鎖為 pending
    - children 中 blocked 但仍有其他未完成依賴 → 保留 blocked，列入警告
    - children 中 pending/in_progress → 不改狀態，列入警告
    - children 中 completed/closed → 忽略
    - children 中找不到（資料不一致） → 跳過
    - save 失敗（§6.7） → 記錄 warning，不 fail-fast

    Args:
        parent_ticket: 已完成的父 Ticket dict
        version: 版本字串

    Returns:
        (unblocked_list, pending_list)
        - unblocked_list: [{id, title}, ...] 已 cascade 解鎖的 children
        - pending_list:   [{id, title, status}, ...] 未完成但未解鎖的 children
    """
    unblocked: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []

    children_ids = parent_ticket.get("children") or []
    if not children_ids:
        return unblocked, pending

    all_tickets = list_tickets(version)
    ticket_map: Dict[str, Any] = {t.get("id"): t for t in all_tickets}

    for child_id in children_ids:
        child = ticket_map.get(child_id)
        if child is None:
            # §6.5 找不到 child_id 跳過
            continue

        child_status = child.get("status", STATUS_PENDING)
        child_title = child.get("title", "")

        if child_status in (STATUS_COMPLETED, STATUS_CLOSED):
            continue

        if child_status == STATUS_BLOCKED:
            if _can_cascade_unblock(child, ticket_map):
                child["status"] = STATUS_PENDING
                try:
                    save_ticket(
                        child,
                        resolve_ticket_path(child, version, child_id),
                    )
                    unblocked.append({
                        "id": child_id,
                        "title": child_title,
                    })
                except Exception as err:
                    print(format_warning(
                        f"cascade 解鎖 {child_id} 儲存失敗：{err}"
                    ))
                    # §6.7 non-fail-fast：不計入 unblocked 也不列入 pending
                    continue
            else:
                pending.append({
                    "id": child_id,
                    "title": child_title,
                    "status": STATUS_BLOCKED,
                })
        else:
            # pending / in_progress → 警告但不改動
            pending.append({
                "id": child_id,
                "title": child_title,
                "status": child_status,
            })

    return unblocked, pending


def _print_cascade_unblocked(unblocked: List[Dict[str, Any]]) -> None:
    """印出 cascade 解鎖訊息（Phase 1 §3.3）。"""
    print()
    print("[Cascade] 以下子 Ticket 已自動解鎖（blocked → pending）：")
    for item in unblocked:
        print(f"   - {item['id']}: {item.get('title', '')}")


def _print_children_warnings(pending: List[Dict[str, Any]]) -> None:
    """印出未完成 children 警告訊息（Phase 1 §3.4）。"""
    print()
    print("[Warning] 父 Ticket 完成時尚有未完成的子 Ticket：")
    for item in pending:
        print(f"   - {item['id']} [{item['status']}]: {item.get('title', '')}")
    print("   （提示：父 complete 不阻止，但建議確認子任務是否需要獨立推進或 close）")


# ============================================================================
# 核心生命週期函式（導出給外部使用）
# ============================================================================

def execute_claim(args: argparse.Namespace, version: str) -> int:
    """
    認領 Ticket - 函式包裝層（向後相容）

    使用 TicketLifecycle 物件執行實際操作。若傳入 ``--skip-verify`` 或
    ``--yes``（或進入 AC 驗證流程的其他情境），委派 ``claim_with_verification``；
    兩者皆為預設 False 時仍走原 ``claim``（但本版本統一走驗證入口以確保
    S3/S4 行為一致，未帶 flag 時驗證層會依 tty 狀態決策）。

    PROP-010 方案 4：claim 前若 Ticket 建立已超過 INFO 閾值（7 天），
    輸出 stale 提示供 PM 重新評估。
    """
    # Stale 提示（pending 超過 7 天；靜默失敗不影響 claim 主流程）
    try:
        ticket = load_ticket(version, args.ticket_id)
        if ticket:
            warning = format_stale_warning(ticket)
            if warning:
                print(warning)
    except Exception as exc:  # 不可因 stale 檢查失敗阻擋 claim
        sys.stderr.write(f"[staleness] claim 前檢查異常：{exc}\n")

    lifecycle = TicketLifecycle(version)
    skip_verify = bool(getattr(args, "skip_verify", False))
    auto_yes = bool(getattr(args, "yes", False))
    # 統一走驗證入口（skip_verify=True 時內部會降級走既有 claim）
    rc = lifecycle.claim_with_verification(
        args.ticket_id, skip_verify=skip_verify, auto_yes=auto_yes
    )

    # W17-002.2：claim 成功後自動抽取 Context Bundle（異常降級；idempotent merge 自然防止重複）
    if rc == 0:
        _auto_extract_context_bundle_post_claim(
            version,
            args.ticket_id,
            quiet=bool(getattr(args, "quiet", False)),
            verbose=bool(getattr(args, "verbose", False)),
            json_output=bool(getattr(args, "json_output", False)),
        )

    return rc


def _auto_extract_context_bundle_post_claim(
    version: str,
    ticket_id: str,
    quiet: bool = False,
    verbose: bool = False,
    json_output: bool = False,
) -> None:
    """Claim 後的 Context Bundle 自動抽取 wire-in（W17-002.2）。

    觸發條件：target ticket 具 source_ticket / blocked_by / related_to 其一。
    幂等性：依賴 `merge_auto_extracted_block` 的 sources 主鍵幂等保證，
    若 Context Bundle 已存在同 sources 的 auto block，不再重寫（no_change_idempotent）。
    異常降級：任何例外寫 stderr traceback，退出碼保 0。

    設計依據：W17-002 Phase 1 §5.2 claim-insert 虛擬碼。
    """
    import traceback as _tb
    try:
        from ticket_system.lib.context_bundle_extractor import (
            extract_and_write_context_bundle,
            format_cli_summary,
            format_cli_summary_json,
        )

        target = load_ticket(version, ticket_id)
        if target is None:
            return
        if not (
            target.get("source_ticket")
            or target.get("blocked_by")
            or target.get("blockedBy")
            or target.get("related_to")
            or target.get("relatedTo")
        ):
            return

        result, _notes = extract_and_write_context_bundle(version, ticket_id)
        if json_output:
            print(format_cli_summary_json(result))
        else:
            print(format_cli_summary(result, quiet=quiet, verbose=verbose))
    except Exception:
        sys.stderr.write(_tb.format_exc())
        sys.stderr.write("[Context Bundle] 抽取失敗，不影響 ticket 認領\n")


def execute_complete(args: argparse.Namespace, version: str) -> int:
    """
    完成 Ticket - 函式包裝層（向後相容）

    使用 TicketLifecycle 物件執行實際操作。

    W12-005：新增 --yes-spawned flag 傳遞（ANA spawned 非 terminal 非互動旁路）。
    """
    lifecycle = TicketLifecycle(version)
    yes_spawned = bool(getattr(args, "yes_spawned", False))
    skip_body_check = bool(getattr(args, "skip_body_check", False))
    return lifecycle.complete(
        args.ticket_id,
        yes_spawned=yes_spawned,
        skip_body_check=skip_body_check,
    )


def execute_close(args: argparse.Namespace, version: str) -> int:
    """
    關閉 Ticket - 問題已在其他 Ticket 一併解決

    必填參數：
    - --resolved-by：解決此問題的 Ticket ID
    - --reason：close_reason 枚舉（PC-090 C1，六種合法值）

    選填參數：
    - --reason-note：關閉原因補充說明
    - --retrospective：回顧式補填模式，允許 reason=unknown（PC-090 C4）
    """
    resolved_by = args.resolved_by
    reason_code = getattr(args, "reason", "") or ""
    reason_note = getattr(args, "reason_note", "") or ""
    retrospective = bool(getattr(args, "retrospective", False))
    lifecycle = TicketLifecycle(version)
    return lifecycle.close(
        args.ticket_id,
        resolved_by,
        reason_code,
        reason_note=reason_note,
        retrospective=retrospective,
    )


def execute_release(args: argparse.Namespace, version: str) -> int:
    """
    釋放 Ticket - 函式包裝層（向後相容）

    使用 TicketLifecycle 物件執行實際操作。
    """
    lifecycle = TicketLifecycle(version)
    return lifecycle.release(args.ticket_id)
