"""
Ticket create 命令模組

負責建立新的 Atomic Ticket。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from ticket_system.lib.ticket_loader import (
    get_tickets_dir,
    save_ticket,
    load_ticket,
    resolve_version,
    get_ticket_path,
)
from ticket_system.lib.ticket_validator import (
    validate_ticket_id,
    extract_wave_from_ticket_id,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    WarningMessages,
    InfoMessages,
    SectionHeaders,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_lifecycle_messages import (
    CreateMessages,
    format_msg,
)
from ticket_system.lib.parallel_analyzer import ParallelAnalyzer
from ticket_system.lib.tdd_sequence import suggest_tdd_sequence
from ticket_system.lib.ticket_builder import (
    TicketConfig,
    format_ticket_id,
    format_child_ticket_id,
    get_next_seq,
    get_next_child_seq,
    create_ticket_frontmatter,
    create_ticket_body,
    update_parent_children,
)
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY


def execute(args: argparse.Namespace) -> int:
    """執行 create 命令"""
    version = resolve_version(args.version)
    if not version:
        print(format_error(ErrorMessages.VERSION_NOT_DETECTED))
        return 1

    # 初始化 wave
    wave = args.wave

    # 判斷是否建立子任務
    if args.parent:
        # 建立子任務 ID（總是自動遞增，忽略 --seq）
        child_seq = get_next_child_seq(args.parent)
        if args.seq is not None:
            print(format_warning(
                WarningMessages.SEQ_IGNORED_WITH_PARENT,
                seq=args.seq,
                child_seq=child_seq,
            ))
        ticket_id = format_child_ticket_id(args.parent, child_seq)

        # 從 parent_id 中提取 wave
        extracted_wave = extract_wave_from_ticket_id(args.parent)
        if extracted_wave is not None:
            wave = extracted_wave
    else:
        # 建立根任務 ID
        if not wave:
            print(format_error(ErrorMessages.MISSING_WAVE_PARAMETER))
            return 1

        if args.seq is None:
            seq = get_next_seq(version, wave)
        else:
            seq = args.seq
        ticket_id = format_ticket_id(version, wave, seq)

    # 驗證 Ticket ID
    if not validate_ticket_id(ticket_id):
        print(format_error(ErrorMessages.INVALID_TICKET_ID_FORMAT, ticket_id=ticket_id))
        return 1

    # 處理 where_files
    where_files = []
    if args.where_files:
        where_files = [f.strip() for f in args.where_files.split(",")]

    # 處理 blocked_by
    blocked_by = []
    if args.blocked_by:
        blocked_by = [b.strip() for b in args.blocked_by.split(",")]

    # 處理 related_to
    related_to = []
    if args.related_to:
        related_to = [r.strip() for r in args.related_to.split(",")]

    # 處理 acceptance（支援多次 --acceptance 和 | 分隔）
    acceptance = None
    if args.acceptance:
        acceptance = []
        for item in args.acceptance:
            acceptance.extend(a.strip() for a in item.split("|"))
        acceptance = [a for a in acceptance if a]

    # 識別任務類型並取得 TDD 順序建議
    ticket_type = args.type or "IMP"
    tdd_result = suggest_tdd_sequence(task_type=ticket_type)

    # 若有 TDD Phase 順序，取第一個 Phase 作為初始階段
    tdd_phase = tdd_result.phases[0] if tdd_result.phases else None

    # 建立配置
    config: TicketConfig = {
        "ticket_id": ticket_id,
        "version": version,
        "wave": wave,
        "title": args.title or f"{args.action} {args.target}",
        "ticket_type": ticket_type,
        "priority": args.priority or "P2",
        "who": args.who or "pending",
        "what": args.what or f"{args.action} {args.target}",
        "when": args.when or "待定義",
        "where_layer": args.where_layer or "待定義",
        "where_files": where_files,
        "why": args.why or "待定義",
        "how_task_type": args.how_type or "Implementation",
        "how_strategy": args.how_strategy or "待定義",
        "parent_id": args.parent,
        "blocked_by": blocked_by if blocked_by else None,
        "related_to": related_to if related_to else None,
        "acceptance": acceptance,
        "tdd_phase": tdd_phase,
        "tdd_stage": tdd_result.phases,
    }

    # 建立 frontmatter
    frontmatter = create_ticket_frontmatter(config)

    # 建立 body
    body = create_ticket_body(frontmatter["what"], frontmatter["who"]["current"])

    # 建立 Ticket 物件
    ticket = frontmatter.copy()
    ticket["_body"] = body

    # 儲存
    tickets_dir = get_tickets_dir(version)
    tickets_dir.mkdir(parents=True, exist_ok=True)

    ticket_path = get_ticket_path(version, ticket_id)
    save_ticket(ticket, ticket_path)

    print(format_info(InfoMessages.TICKET_CREATED, ticket_id=ticket_id))
    print(f"   Location: {ticket_path}")
    print(format_msg(CreateMessages.TASK_TYPE_LABEL, task_type=args.type or 'IMP'))

    # 如果有 parent，更新 parent 的 children
    parent_info: Optional[Dict[str, Any]] = None
    if args.parent:
        if update_parent_children(version, args.parent, ticket_id):
            print(f"   Parent: {args.parent} (已更新 children)")
            # 載入 parent 以進行並行分析
            parent_info = load_ticket(version, args.parent)
        else:
            print(format_warning(WarningMessages.PARENT_UPDATE_FAILED, parent_id=args.parent))

    # 顯示建立時檢查清單
    _print_create_checklist(
        ticket_id=ticket_id,
        ticket_type=args.type or "IMP",
        parent_id=args.parent,
        parent_info=parent_info,
        new_ticket=ticket
    )

    return 0


def _print_create_checklist(
    ticket_id: str,
    ticket_type: str,
    parent_id: Optional[str] = None,
    parent_info: Optional[Dict[str, Any]] = None,
    new_ticket: Optional[Dict[str, Any]] = None,
) -> None:
    """印出建立時的檢查清單、TDD 順序建議和並行分析結果。

    Args:
        ticket_id: 新建立的 Ticket ID
        ticket_type: Ticket 類型
        parent_id: 父 Ticket ID（如果是子任務）
        parent_info: 父 Ticket 的資訊（用於並行分析）
        new_ticket: 新建立的 Ticket 資訊（用於並行分析）
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

    # 驗收條件格式提示
    print(CreateMessages.ACCEPTANCE_4V_CHECK)
    print(CreateMessages.ACCEPTANCE_4V_DESC)

    # 依賴提示
    print(CreateMessages.BLOCKED_BY_CHECK)

    # 決策樹欄位提示
    print(CreateMessages.DECISION_TREE_CHECK)
    print(CreateMessages.DECISION_TREE_DESC)

    print()

    # 輸出 TDD 順序建議（適用於所有任務類型）
    _print_tdd_sequence_suggestion(ticket_type)

    # 輸出並行分析結果（對子任務）
    if parent_id and parent_info and new_ticket:
        _print_parallel_analysis_result(parent_info, new_ticket, ticket_id)


def _print_tdd_sequence_suggestion(ticket_type: str) -> None:
    """輸出 TDD 順序建議。

    Args:
        ticket_type: Ticket 類型（IMP、ADJ、DOC 等）
    """
    result = suggest_tdd_sequence(task_type=ticket_type)

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
        # 簡化 phase 名稱以供輸出
        phase_display = phase.replace("phase", "Phase ").upper()
        phase_desc = {
            "phase1": "Phase 1 - 功能設計 (lavender)",
            "phase2": "Phase 2 - 測試設計 (sage)",
            "phase3a": "Phase 3a - 策略規劃 (pepper)",
            "phase3b": "Phase 3b - 實作執行 (parsley)",
            "phase4": "Phase 4 - 重構優化 (cinnamon)",
        }
        print(f"   {i}. {phase_desc.get(phase, phase)}")

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
        # 取得子任務資訊
        # 注意：child_id 可能是子任務 ID，需要從 parent_id 中提取版本
        parent_version = parent_info.get("version", "")

        child_info = load_ticket(parent_version, child_id)
        if not child_info:
            continue

        task = {
            "task_id": child_id,
            "where_files": child_info.get("where", {}).get("files", []),
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


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 create 子命令"""
    parser = subparsers.add_parser("create", help="建立新的 Atomic Ticket")

    parser.add_argument("--version", help="版本號（自動偵測）")
    parser.add_argument("--wave", type=int, required=False, help="Wave 編號（建立根任務時必須，子任務可省略）")
    parser.add_argument("--seq", type=int, help="序號（自動產生）")
    parser.add_argument("--action", required=True, help="動詞")
    parser.add_argument("--target", required=True, help="目標")
    parser.add_argument("--title", help="標題（預設: action + target）")
    parser.add_argument(
        "--type", help="類型: IMP, TST, ADJ, RES, ANA, INV, DOC（預設: IMP）"
    )
    parser.add_argument("--priority", help="優先級: P0, P1, P2, P3（預設: P2）")
    parser.add_argument("--who", help="執行代理人")
    parser.add_argument("--what", help="任務描述（預設: action + target）")
    parser.add_argument("--when", help="觸發時機")
    parser.add_argument(
        "--where-layer", help="架構層級: Domain, Application, Infrastructure, Presentation"
    )
    parser.add_argument("--where", "--where-files", dest="where_files", help="影響檔案（逗號分隔）")
    parser.add_argument("--why", help="需求依據")
    parser.add_argument("--how-type", help="Task Type: Implementation, Analysis, etc.")
    parser.add_argument("--how-strategy", help="實作策略")
    parser.add_argument("--parent", help="父 Ticket ID")
    parser.add_argument("--blocked-by", help="依賴的 Ticket IDs（逗號分隔）")
    parser.add_argument("--related-to", help="相關的 Ticket IDs（逗號分隔，多對多關聯）")
    parser.add_argument("--acceptance", action="append", help="驗收條件（可多次指定或 | 分隔）")

    parser.set_defaults(func=execute)
