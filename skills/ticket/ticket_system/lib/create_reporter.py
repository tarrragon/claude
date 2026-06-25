"""
Ticket create 報告輸出模組

從 commands/create.py 提取的 reporting 群組。
負責建立後的檢查清單、TDD 順序建議、並行分析、
認知負擔評估和策略完整度檢查。
"""
if __name__ == "__main__":
    from .messages import print_not_executable_and_exit
    print_not_executable_and_exit()


from typing import Any, Dict, List, Optional

from ticket_system.lib.ticket_loader import load_ticket
from ticket_system.lib.constants import (
    COGNITIVE_LOAD_FILE_THRESHOLD,
    DEFAULT_UNDEFINED_VALUE,
    TDD_PHASE_DISPLAY,
)
from ticket_system.lib.messages import (
    SectionHeaders,
    format_warning,
)
from ticket_system.lib.command_lifecycle_messages import (
    CreateMessages,
    format_msg,
)
from ticket_system.lib.acceptance_auditor import detect_vague_acceptance, detect_srp_violations
from ticket_system.lib.parallel_analyzer import ParallelAnalyzer
from ticket_system.lib.tdd_sequence import suggest_tdd_sequence
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY


def extract_where_files(ticket_data: Optional[Dict[str, Any]]) -> List[str]:
    """從 ticket dict 取 where.files，相容舊字串格式。

    W11-026: 舊 ticket where 為字串（即 layer 描述，無 files 概念），新格式為 dict {layer, files}。
    型別防護策略：dict 走 .get("files", [])、str / None / 缺失皆回空 list。

    與 _inherit_parent_where_layer 同模式但取 files（list 而非 str）。
    本 helper 可重用於任何包含 where 欄位的 ticket dict（parent / child / new_ticket）。
    """
    if not ticket_data:
        return []
    where = ticket_data.get("where")
    if isinstance(where, dict):
        files = where.get("files")
        return files if isinstance(files, list) else []
    return []


def print_create_checklist(
    ticket_id: str,
    ticket_type: str,
    parent_id: Optional[str] = None,
    parent_info: Optional[Dict[str, Any]] = None,
    new_ticket: Optional[Dict[str, Any]] = None,
    used_default_acceptance: bool = False,
    tdd_result: Any = None,
) -> None:
    """印出建立時的檢查清單、TDD 順序建議和並行分析結果。

    Args:
        ticket_id: 新建立的 Ticket ID
        ticket_type: Ticket 類型
        parent_id: 父 Ticket ID（如果是子任務）
        parent_info: 父 Ticket 的資訊（用於並行分析）
        new_ticket: 新建立的 Ticket 資訊（用於並行分析）
        used_default_acceptance: 是否使用了預設驗收條件
        tdd_result: TDD 序列建議結果（避免重複呼叫）
    """
    print()
    print(SEPARATOR_PRIMARY)
    print(SectionHeaders.CREATION_CHECKLIST)
    print(SEPARATOR_PRIMARY)
    print()

    print(CreateMessages.POST_CREATE_CHECKLIST)

    # SA 前置審查提示
    if ticket_type == "IMP" and not parent_id:
        print(CreateMessages.SA_REVIEW_NEEDED)

    # 拆分提示
    print(CreateMessages.SPLIT_NEEDED)

    # 變更 4：初步認知負擔評估
    _print_cognitive_load_assessment(new_ticket)

    # 變更 5：strategy 完整度檢查（W3-011, PC-040 引導）
    _print_strategy_completeness_check(new_ticket)

    # SRP 偵測（W3-002）
    if new_ticket:
        what_text = new_ticket.get("what", "") or ""
        acceptance = new_ticket.get("acceptance", []) or []
        srp_warnings = detect_srp_violations(what_text, acceptance)
        if srp_warnings:
            for warning in srp_warnings:
                print(format_warning(warning))

    # 驗收條件格式提示
    print(CreateMessages.ACCEPTANCE_4V_CHECK)
    print(CreateMessages.ACCEPTANCE_4V_DESC)

    # 如果使用了預設驗收條件，輸出 WARNING
    if used_default_acceptance:
        print(format_warning(CreateMessages.DEFAULT_ACCEPTANCE_WARNING))

    # 問題 1 修正：檢查含糊驗收條件（無論是否使用預設）
    if new_ticket:
        acceptance = new_ticket.get("acceptance", [])
        if acceptance:
            vague_warnings = detect_vague_acceptance(acceptance)
            if vague_warnings:
                for warning in vague_warnings:
                    print(format_warning(CreateMessages.VAGUE_ACCEPTANCE_WARNING, vague_words=warning))

    # 依賴提示
    print(CreateMessages.BLOCKED_BY_CHECK)

    # 決策樹欄位提示
    print(CreateMessages.DECISION_TREE_CHECK)
    print(CreateMessages.DECISION_TREE_DESC)

    print()

    # 輸出 TDD 順序建議（適用於所有任務類型）
    _print_tdd_sequence_suggestion(ticket_type, tdd_result)

    # 輸出並行分析結果（對子任務）
    if parent_id and parent_info and new_ticket:
        _print_parallel_analysis_result(parent_info, new_ticket, ticket_id)


def _print_tdd_sequence_suggestion(ticket_type: str, tdd_result: Any = None) -> None:
    """輸出 TDD 順序建議。

    Args:
        ticket_type: Ticket 類型（IMP、ADJ、DOC 等）
        tdd_result: TDD 序列建議結果（可選，若無則重新計算）
    """
    result = tdd_result or suggest_tdd_sequence(task_type=ticket_type)

    # 若無需 TDD 流程，略過此章節
    if not result.phases:
        return

    print(SEPARATOR_PRIMARY)
    print(SectionHeaders.TDD_SEQUENCE_SUGGESTION)
    print(SEPARATOR_PRIMARY)
    print()

    print(format_msg(CreateMessages.TASK_TYPE_LABEL, task_type=result.task_type))
    print(CreateMessages.SUGGESTED_ORDER)

    for i, phase in enumerate(result.phases, 1):
        phase_display = TDD_PHASE_DISPLAY.get(phase, phase)
        print(f"   {i}. {phase_display}")

    print()
    print(format_msg(CreateMessages.RATIONALE_LABEL, rationale=result.rationale))
    print()


def _print_parallel_analysis_result(
    parent_info: Dict[str, Any],
    new_ticket: Dict[str, Any],
    new_ticket_id: str,
) -> None:
    """輸出並行分析結果。

    根據父 Ticket 的所有子任務進行並行分析，輸出並行可行性。

    Args:
        parent_info: 父 Ticket 的資訊
        new_ticket: 新建立的 Ticket 資訊
        new_ticket_id: 新建立的 Ticket ID
    """
    # 收集所有子任務（包括新建立的）
    children = parent_info.get("children", [])
    if new_ticket_id not in children:
        children = list(children) + [new_ticket_id]

    # 若子任務數不足 2 個，無需並行分析
    if len(children) < 2:
        return

    # 準備任務清單以供並行分析
    tasks = []
    for child_id in children:
        parent_version = parent_info.get("version", "")

        child_info = load_ticket(parent_version, child_id)
        if not child_info:
            continue

        task = {
            "task_id": child_id,
            "where_files": extract_where_files(child_info),
            "blockedBy": child_info.get("blockedBy", []),
            "title": child_info.get("title", ""),
        }
        tasks.append(task)

    # 執行並行分析
    analysis_result = ParallelAnalyzer.analyze_tasks(tasks)

    # 輸出並行分析結果
    print(SEPARATOR_PRIMARY)
    print(SectionHeaders.PARALLEL_ANALYSIS)
    print(SEPARATOR_PRIMARY)
    print()

    print(f"分析結果: {'可並行' if analysis_result.can_parallel else '無法並行'}")
    print()

    if analysis_result.can_parallel and analysis_result.parallel_groups:
        print("並行群組:")
        for i, group in enumerate(analysis_result.parallel_groups, 1):
            print(f"   群組 {i}: {', '.join(group)}")
        print()

    if analysis_result.blocked_pairs:
        print("衝突對:")
        for task_a, task_b in analysis_result.blocked_pairs:
            print(f"   {task_a} <-> {task_b}")
        print()

    print(f"理由: {analysis_result.reason}")
    print()


def _print_cognitive_load_assessment(
    new_ticket: Optional[Dict[str, Any]] = None,
) -> None:
    """
    執行初步認知負擔評估（基於 where_files）。

    邏輯：
    - 若 where_files 為空或「待定義」，輸出提示「尚未填寫」
    - 若 where_files > 5 個，輸出 WARNING「認知負擔可能超閾值」
    - 否則無輸出（認知負擔正常）

    Args:
        new_ticket: 新建立的 Ticket 資訊
    """
    if not new_ticket:
        return

    where_files = extract_where_files(new_ticket)

    # 若 where_files 為空或「待定義」
    if not where_files or where_files == [DEFAULT_UNDEFINED_VALUE]:
        print(format_warning(CreateMessages.COGNITIVE_LOAD_FILES_UNDEFINED_WARNING))
        return

    # 若 where_files > 閾值，輸出警告
    if len(where_files) > COGNITIVE_LOAD_FILE_THRESHOLD:
        print(format_warning(
            CreateMessages.COGNITIVE_LOAD_FILE_THRESHOLD_WARNING,
            threshold=COGNITIVE_LOAD_FILE_THRESHOLD
        ))


def _print_strategy_completeness_check(
    new_ticket: Optional[Dict[str, Any]],
) -> None:
    """
    檢查 how.strategy 欄位是否已填寫（W3-011, PC-040 引導）。

    IMP/ADJ 類型的 Ticket 需要在派發代理人前提供 Context Bundle，
    strategy 欄位是其中的關鍵部分。提前提醒 PM 填寫。
    """
    if not new_ticket:
        return

    ticket_type = new_ticket.get("type", "IMP")
    if ticket_type not in ("IMP", "ADJ"):
        return

    strategy = new_ticket.get("how", {}).get("strategy", "")
    if not strategy or strategy == DEFAULT_UNDEFINED_VALUE:
        print(
            "[提醒] how.strategy 尚未填寫。"
            "派發代理人前，請將分析結果寫入 Ticket Context Bundle（PC-040）\n"
            "   → ticket track append-log <id> --section \"Problem Analysis\" "
            "\"### Context Bundle\\n...\""
        )
