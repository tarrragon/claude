"""
Ticket create 命令模組

負責建立新的 Atomic Ticket。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
import re
import sys
from typing import Any, Dict, List, Optional

from ticket_system.lib.ticket_loader import (
    get_tickets_dir,
    save_ticket,
    load_ticket,
    resolve_version,
    get_ticket_path,
    list_tickets,
)
from ticket_system.lib.ticket_validator import (
    validate_ticket_id,
    extract_wave_from_ticket_id,
    validate_blocked_by,
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
from ticket_system.lib.command_tracking_messages import TrackMessages
from datetime import datetime, timedelta
from ticket_system.lib.constants import (
    COGNITIVE_LOAD_FILE_THRESHOLD,
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    DUPLICATE_DETECTION_THRESHOLD,
    DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS,
    DEFAULT_PRIORITY,
    DEFAULT_HOW_TASK_TYPE,
    DEFAULT_UNDEFINED_VALUE,
    TDD_PHASE_DISPLAY,
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
from ticket_system.lib.acceptance_auditor import detect_vague_acceptance, detect_srp_violations
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY


def _validate_blocked_by_references(
    version: str,
    ticket_id: str,
    blocked_by: Optional[List[str]],
) -> bool:
    """
    驗證 blockedBy 欄位的存在性和循環依賴。

    執行兩個驗證：
    1. 存在性檢查：所有 blockedBy 中的 Ticket ID 必須存在
    2. 循環依賴檢測：設定 blockedBy 不應產生循環依賴

    Args:
        version: Ticket 版本號
        ticket_id: 當前要建立的 Ticket ID
        blocked_by: blockedBy 欄位清單（可為 None）

    Returns:
        bool: True 表示驗證通過，False 表示有錯誤（已輸出錯誤訊息）
    """
    # Guard Clause：無 blockedBy 欄位
    if not blocked_by:
        return True

    # 驗證 1：blockedBy 存在性檢查
    for bid in blocked_by:
        blocked_ticket = load_ticket(version, bid)
        if blocked_ticket is None:
            print(format_error(
                CreateMessages.BLOCKED_BY_NOT_FOUND,
                bid=bid
            ))
            return False

    # 驗證 2：blockedBy 循環依賴檢測
    all_tickets = list_tickets(version)
    valid, cycle_msg, cycle_path = validate_blocked_by(
        ticket_id,
        blocked_by,
        all_tickets
    )
    if not valid and cycle_msg:
        print(format_error(cycle_msg))
        return False

    return True


def _validate_decision_tree_params(
    entry: Optional[str],
    decision: Optional[str],
    rationale: Optional[str],
) -> bool:
    """驗證 decision_tree 參數值的基本正確性。

    檢查內容：
    1. 無空字串值

    Args:
        entry: entry_point 參數值
        decision: final_decision 參數值
        rationale: rationale 參數值

    Returns:
        True 如果驗證通過，False 如果有空字串或其他問題
    """
    params = [(entry, "entry_point"), (decision, "final_decision"), (rationale, "rationale")]
    for value, name in params:
        if value == "":  # 空字串值
            print(format_error(
                CreateMessages.DECISION_TREE_EMPTY_VALUE,
                field_name=name
            ))
            return False
    return True


def _build_decision_tree_path(
    entry: Optional[str],
    decision: Optional[str],
    rationale: Optional[str],
    is_child: bool,
    ticket_type: str,
) -> Optional[Dict[str, str]]:
    """驗證並構建 decision_tree_path 字典。

    邏輯：
    1. 豁免條件：子任務（is_child=True）或 DOC 類型
    2. 豁免時無參數 → 返回 None
    3. 豁免時有完整參數 → 返回字典（驗證後）
    4. 豁免時部分參數 → raise ValueError（拒絕）
    5. 非豁免時無參數 → raise ValueError（拒絕）
    6. 非豁免時有完整參數 → 返回字典（驗證後）
    7. 非豁免時部分參數 → raise ValueError（拒絕）

    Args:
        entry: --decision-tree-entry 參數值
        decision: --decision-tree-decision 參數值
        rationale: --decision-tree-rationale 參數值
        is_child: 是否為子任務（args.parent 非空）
        ticket_type: Ticket 類型（args.type）

    Returns:
        - Dict[str, str]：包含 entry_point, final_decision, rationale 三個鍵
        - None：豁免且無參數

    Raises:
        ValueError: 驗證失敗（參數不完整或其他問題）
    """
    # 判斷是否豁免
    is_exempted = is_child or ticket_type == "DOC"

    # 計算提供的參數個數
    params = [entry, decision, rationale]
    provided_count = sum(1 for p in params if p is not None)

    # 使用 early return 簡化邏輯
    if provided_count == 0:
        # 無參數
        if is_exempted:
            return None
        else:
            print(format_error(CreateMessages.DECISION_TREE_MISSING_ALL))
            raise ValueError("決策樹參數缺失")

    if provided_count == 3:
        # 完整三參數 - 驗證後返回字典
        if not _validate_decision_tree_params(entry, decision, rationale):
            raise ValueError("決策樹參數驗證失敗")
        return {
            "entry_point": entry,
            "final_decision": decision,
            "rationale": rationale,
        }

    # 部分參數 - 全部拒絕
    if is_exempted:
        print(format_error(CreateMessages.EXEMPTED_PARTIAL_PARAMS_ERROR))
    else:
        missing_fields = []
        if entry is None:
            missing_fields.append("entry_point")
        if decision is None:
            missing_fields.append("final_decision")
        if rationale is None:
            missing_fields.append("rationale")
        print(format_error(
            CreateMessages.DECISION_TREE_MISSING_PARTIAL,
            missing_fields=", ".join(missing_fields)
        ))
    raise ValueError("決策樹參數不完整")


def _tokenize(text: str) -> set:
    r"""
    將文字分割為詞集合。

    - 中文字符（\u4e00-\u9fff）逐字提取
    - 英文單詞（\w+）按單詞分割
    - 特殊字符和標點忽略

    Args:
        text: 待分割文字

    Returns:
        集合，包含所有詞彙
    """
    # 提取中文字符和英文單詞
    # 模式：中文字符（\u4e00-\u9fff）或英文單詞（\w+）
    pattern = r'[\u4e00-\u9fff]|\w+'
    tokens = re.findall(pattern, text)
    return set(tokens)


def _calculate_jaccard_similarity(text_a: str, text_b: str) -> float:
    """
    計算兩個字串的 Jaccard 相似度係數。

    使用集合論方式計算相似度：
    Jaccard = |intersection| / |union|

    對中文字符逐字分割，英文單詞以空白和標點分割。

    Args:
        text_a: 第一個比對文字
        text_b: 第二個比對文字

    Returns:
        float: 相似度值 [0.0, 1.0]，1.0 表示完全相同，0.0 表示完全不同

    Raises:
        TypeError: 如果輸入不是字串型別
    """
    # 輸入驗證
    if not isinstance(text_a, str) or not isinstance(text_b, str):
        raise TypeError("text_a 和 text_b 必須是字串型別")

    # 統一轉為小寫，不區分大小寫
    text_a = text_a.lower()
    text_b = text_b.lower()

    # 分割兩個文字
    set_a = _tokenize(text_a)
    set_b = _tokenize(text_b)

    # 邊界情況：兩個集合都為空
    if not set_a and not set_b:
        return 0.0

    # 計算 Jaccard 係數
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    if union == 0:
        return 0.0

    return intersection / union


def _is_in_detection_scope(ticket: Dict[str, Any], window_start: datetime) -> bool:
    """判斷 Ticket 是否在重複偵測掃描範圍內。

    掃描範圍：
    - pending: 始終包含
    - in_progress: 始終包含
    - completed: 僅 7 天內完成者（completed_at >= window_start）
    - 其他狀態: 排除

    Args:
        ticket: Ticket 字典
        window_start: 時間窗口起點（now - N 天）

    Returns:
        True 表示在掃描範圍內
    """
    status = ticket.get("status")

    if status == STATUS_PENDING:
        return True

    if status == STATUS_IN_PROGRESS:
        return True

    if status == STATUS_COMPLETED:
        completed_at_str = ticket.get("completed_at")
        if not completed_at_str:
            return False
        try:
            completed_at = datetime.fromisoformat(completed_at_str)
            return completed_at >= window_start
        except (ValueError, TypeError):
            return False

    return False


def _get_status_label(status: str) -> str:
    """根據 Ticket 狀態返回顯示標籤。

    pending 不加標籤（向下相容），in_progress 和 completed 加中文標籤。

    Args:
        status: Ticket 狀態字串

    Returns:
        狀態標籤字串，pending 返回空字串
    """
    if status == STATUS_IN_PROGRESS:
        return CreateMessages.DUPLICATE_STATUS_LABEL_IN_PROGRESS
    if status == STATUS_COMPLETED:
        return CreateMessages.DUPLICATE_STATUS_LABEL_COMPLETED
    return ""


def _detect_duplicate_tickets(
    version: str,
    new_title: str,
    new_what: str,
    new_ticket_id: str,
) -> None:
    """
    偵測並警告同版本中可能重複的 Ticket。

    掃描同版本的 pending/in_progress/completed（7 天內）Ticket，
    使用 Jaccard 相似度與即將建立的 Ticket 比對標題和目標。
    若發現相似度達閾值的 Ticket，輸出 WARNING 提示使用者。

    此函式設計為容錯式：內部所有異常都被靜默捕捉，不影響後續建立流程。

    Args:
        version: 目標版本號（如 "0.1.2"）
        new_title: 即將建立的 Ticket 標題
        new_what: 即將建立的 Ticket 目標描述
        new_ticket_id: 即將建立的 Ticket ID（用於排除自身）

    Returns:
        None（不返回偵測結果，以簽名方式消費 WARNING）
    """

    try:
        # 步驟 A：驗證輸入
        # 若 title 和 what 均為空，無法進行比對
        if not new_title and not new_what:
            return

        # 步驟 B：載入同版本 Ticket 並過濾候選範圍
        all_tickets = list_tickets(version)

        # 計算需排除的 ID 清單
        exclude_ids = {new_ticket_id}
        # 若是子任務，額外排除父任務 ID
        # 只檢查序號段（最後一個 - 之後）是否含 "."
        seq_part = new_ticket_id.rsplit("-", 1)[-1]
        if "." in seq_part:
            parent_id = new_ticket_id.rsplit(".", 1)[0]
            exclude_ids.add(parent_id)

        # 計算時間窗口（迴圈外一次計算）
        window_start = datetime.now() - timedelta(
            days=DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS
        )

        # 過濾候選 Ticket：pending + in_progress + 7 天內 completed
        candidate_tickets = [
            ticket
            for ticket in all_tickets
            if ticket.get("id") not in exclude_ids
            and _is_in_detection_scope(ticket, window_start)
        ]

        # 若無候選 Ticket，靜默通過
        if not candidate_tickets:
            return

        # 步驟 C：相似度計算
        new_combined = f"{new_title} {new_what}"
        similar_tickets = []

        for ticket in candidate_tickets:
            try:
                # 合併候選 Ticket 的 title 和 what 進行比對
                candidate_title = ticket.get("title", "")
                candidate_what = ticket.get("what", "")
                candidate_combined = f"{candidate_title} {candidate_what}"

                # 計算相似度
                similarity = _calculate_jaccard_similarity(
                    new_combined, candidate_combined
                )

                # 若達閾值，加入相似列表（含狀態供標籤使用）
                if similarity >= DUPLICATE_DETECTION_THRESHOLD:
                    similar_tickets.append(
                        (ticket.get("id", ""), candidate_title, ticket.get("status", ""))
                    )
            except Exception as e:
                # 單項異常不影響整體，跳過此 Ticket，繼續下一個
                sys.stderr.write(f"[DEBUG] 相似度計算異常 ({type(e).__name__}): {e}\n")
                continue

        # 步驟 D：輸出結果（含狀態標籤）
        if similar_tickets:
            # 組裝警告訊息
            warning_lines = [
                format_warning(
                    CreateMessages.DUPLICATE_TICKETS_WARNING_HEADER,
                    count=len(similar_tickets),
                )
            ]

            for ticket_id, title, status in similar_tickets:
                status_label = _get_status_label(status)
                if status_label:
                    warning_lines.append(
                        format_msg(
                            CreateMessages.DUPLICATE_TICKETS_WARNING_ITEM_WITH_STATUS,
                            ticket_id=ticket_id,
                            title=title,
                            status_label=status_label,
                        )
                    )
                else:
                    warning_lines.append(
                        format_msg(
                            CreateMessages.DUPLICATE_TICKETS_WARNING_ITEM,
                            ticket_id=ticket_id,
                            title=title,
                        )
                    )

            warning_lines.append(
                format_msg(CreateMessages.DUPLICATE_TICKETS_WARNING_SUGGESTION)
            )

            # 輸出警告
            print("\n".join(warning_lines))

    except Exception as e:
        # 外層容錯：任何異常都靜默通過
        # 重複偵測是輔助功能，不應阻斷核心建立流程
        # 異常類型輸出到 stderr，供除錯用
        sys.stderr.write(f"[DEBUG] 重複偵測異常 ({type(e).__name__}): {e}\n")


def _resolve_ticket_id_and_wave(args: argparse.Namespace, version: str) -> Optional[tuple]:
    """Step 1: 解析版本和 Ticket ID。

    Args:
        args: 命令行參數
        version: 已解析的版本號

    Returns:
        (version, ticket_id, wave) 或 None（失敗）
    """
    wave = args.wave

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
            return None

        seq = get_next_seq(version, wave) if args.seq is None else args.seq
        ticket_id = format_ticket_id(version, wave, seq)

    # 驗證 Ticket ID
    if not validate_ticket_id(ticket_id):
        print(format_error(ErrorMessages.INVALID_TICKET_ID_FORMAT, ticket_id=ticket_id))
        return None

    return (version, ticket_id, wave)


def _parse_cli_args_to_config(
    args: argparse.Namespace,
    version: str,
    ticket_id: str,
    wave: int,
    tdd_result: Any,
) -> Optional[TicketConfig]:
    """Step 2: CLI 參數轉換為 TicketConfig。

    Args:
        args: 命令行參數
        version: 版本號
        ticket_id: 已解析的 Ticket ID
        wave: Wave 編號
        tdd_result: TDD 序列建議結果

    Returns:
        TicketConfig 或 None（失敗）
    """
    # 處理 where_files
    where_files = [f.strip() for f in args.where_files.split(",")] if args.where_files else []

    # 處理 blocked_by
    blocked_by = [b.strip() for b in args.blocked_by.split(",")] if args.blocked_by else []

    # 處理 related_to
    related_to = [r.strip() for r in args.related_to.split(",")] if args.related_to else []

    # 處理 acceptance（支援多次 --acceptance 和 | 分隔）
    acceptance = None
    if args.acceptance:
        acceptance = []
        for item in args.acceptance:
            acceptance.extend(a.strip() for a in item.split("|"))
        acceptance = [a for a in acceptance if a]

    # 識別任務類型
    ticket_type = args.type or "IMP"

    # 建立決策樹路徑
    try:
        decision_tree_path = _build_decision_tree_path(
            entry=args.decision_tree_entry,
            decision=args.decision_tree_decision,
            rationale=args.decision_tree_rationale,
            is_child=bool(args.parent),
            ticket_type=ticket_type,
        )
    except ValueError:
        return None

    # 如果是子任務，載入父 Ticket 以繼承欄位
    parent_ticket: Optional[Dict[str, Any]] = None
    if args.parent:
        parent_ticket = load_ticket(version, args.parent)

    # 若有 TDD Phase 順序，取第一個 Phase 作為初始階段
    tdd_phase = tdd_result.phases[0] if tdd_result.phases else None

    # PC-018: why 必填驗證（DOC 類型豁免）
    why_value = args.why or (parent_ticket.get("why") if parent_ticket else DEFAULT_UNDEFINED_VALUE)
    if why_value == DEFAULT_UNDEFINED_VALUE and ticket_type != "DOC":
        print(f"[ERROR] --why 為必填欄位（type={ticket_type}）。請提供需求依據。", file=sys.stderr)
        print("  範例: --why '匯出功能需支援 v2 格式'", file=sys.stderr)
        sys.exit(1)

    return {
        "ticket_id": ticket_id,
        "version": version,
        "wave": wave,
        "title": args.title or f"{args.action} {args.target}",
        "ticket_type": ticket_type,
        "priority": args.priority or DEFAULT_PRIORITY,
        "who": args.who or (parent_ticket.get("who", {}).get("current") if parent_ticket else "pending"),
        "what": args.what or f"{args.action} {args.target}",
        "when": args.when or DEFAULT_UNDEFINED_VALUE,
        "where_layer": args.where_layer or (parent_ticket.get("where", {}).get("layer") if parent_ticket else DEFAULT_UNDEFINED_VALUE),
        "where_files": where_files,
        "why": why_value,
        "how_task_type": args.how_type or DEFAULT_HOW_TASK_TYPE,
        "how_strategy": args.how_strategy or DEFAULT_UNDEFINED_VALUE,
        "parent_id": args.parent,
        "blocked_by": blocked_by if blocked_by else None,
        "related_to": related_to if related_to else None,
        "acceptance": acceptance,
        "tdd_phase": tdd_phase,
        "tdd_stage": tdd_result.phases,
        "decision_tree_path": decision_tree_path,
    }


def _validate_before_persist(
    version: str,
    ticket_id: str,
    config: TicketConfig,
) -> bool:
    """驗證層：執行持久化前的所有驗證。

    負責：
    1. 驗證 blockedBy 存在性和循環依賴
    2. 重複偵測

    Args:
        version: 版本號
        ticket_id: Ticket ID
        config: Ticket 配置

    Returns:
        True 表示驗證通過，False 表示驗證失敗
    """
    blocked_by = config.get("blocked_by")

    # 驗證 blockedBy 存在性
    if not _validate_blocked_by_references(version, ticket_id, blocked_by):
        return False

    # 重複偵測
    _detect_duplicate_tickets(
        version=version,
        new_title=config["title"],
        new_what=config["what"],
        new_ticket_id=ticket_id,
    )

    return True


def _build_and_save_ticket(
    version: str,
    ticket_id: str,
    config: TicketConfig,
) -> Dict[str, Any]:
    """持久化層：建構並儲存 Ticket。

    負責：
    1. 建立 Ticket frontmatter 和 body
    2. 建立相應目錄
    3. 儲存 Ticket 到檔案系統

    Args:
        version: 版本號
        ticket_id: Ticket ID
        config: Ticket 配置

    Returns:
        Dict[str, Any]: 建立的 Ticket 物件
    """
    frontmatter = create_ticket_frontmatter(config)
    body = create_ticket_body(frontmatter["what"], frontmatter["who"]["current"])
    ticket = frontmatter.copy()
    ticket["_body"] = body

    tickets_dir = get_tickets_dir(version)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = get_ticket_path(version, ticket_id)
    save_ticket(ticket, ticket_path)

    return ticket


def _update_parent_and_get_parent_info(
    args: argparse.Namespace,
    version: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """關係層：更新父 Ticket 並取得其資訊。

    負責：
    1. 若為子任務，更新父 Ticket 的 children 欄位
    2. 載入並回傳父 Ticket 資訊（用於並行分析）

    Args:
        args: 命令行參數（含 parent 欄位）
        version: 版本號
        ticket_id: 新建立的 Ticket ID

    Returns:
        父 Ticket 資訊（Dict）或 None（非子任務）
    """
    parent_info: Optional[Dict[str, Any]] = None

    if args.parent:
        if update_parent_children(version, args.parent, ticket_id):
            print(format_msg(CreateMessages.PARENT_UPDATED, parent_id=args.parent))
            parent_info = load_ticket(version, args.parent)
        else:
            print(format_warning(
                WarningMessages.PARENT_UPDATE_FAILED,
                parent_id=args.parent,
                child_id=ticket_id
            ))

    return parent_info


def _report_creation_success(
    ticket_id: str,
    config: TicketConfig,
    args: argparse.Namespace,
    ticket: Dict[str, Any],
    parent_info: Optional[Dict[str, Any]],
    tdd_result: Any,
    ticket_path: str,
) -> None:
    """報告層：輸出建立成功的完整報告。

    負責：
    1. 輸出建立訊息（建立成功、檔案位置、任務類型）
    2. 輸出建立時檢查清單
    3. 輸出 TDD 順序建議
    4. 輸出並行分析結果（如適用）

    Args:
        ticket_id: Ticket ID
        config: Ticket 配置
        args: 命令行參數（含 parent 欄位）
        ticket: 新建立的 Ticket 物件
        parent_info: 父 Ticket 資訊（若為子任務）
        tdd_result: TDD 序列建議結果
        ticket_path: Ticket 檔案路徑
    """
    # 輸出建立訊息
    print(format_info(InfoMessages.TICKET_CREATED, ticket_id=ticket_id))
    print(format_msg(CreateMessages.TICKET_LOCATION, ticket_path=ticket_path))
    print(format_msg(CreateMessages.TASK_TYPE_LABEL, task_type=config["ticket_type"]))

    used_default_acceptance = config.get("acceptance") is None
    _print_create_checklist(
        ticket_id=ticket_id,
        ticket_type=config["ticket_type"],
        parent_id=args.parent,
        parent_info=parent_info,
        new_ticket=ticket,
        used_default_acceptance=used_default_acceptance,
        tdd_result=tdd_result,
    )


def _persist_and_report(
    args: argparse.Namespace,
    config: TicketConfig,
    version: str,
    ticket_id: str,
    tdd_result: Any,
) -> int:
    """Step 3: 協調層 — 驗證、持久化、更新關係、回報結果。

    協調四個子函式完成 Ticket 建立流程：
    1. 驗證層：檢查 blockedBy 和重複偵測
    2. 持久化層：建構並儲存 Ticket
    3. 關係層：更新父子關係
    4. 報告層：輸出建立報告

    Args:
        args: 命令行參數
        config: Ticket 配置
        version: 版本號
        ticket_id: Ticket ID
        tdd_result: TDD 序列建議結果

    Returns:
        0（成功）或 1（失敗）
    """
    # 步驟 1：驗證
    if not _validate_before_persist(version, ticket_id, config):
        return 1

    # 步驟 2：持久化
    ticket = _build_and_save_ticket(version, ticket_id, config)
    ticket_path = str(get_ticket_path(version, ticket_id))

    # 步驟 3：更新關係
    parent_info = _update_parent_and_get_parent_info(args, version, ticket_id)

    # 步驟 4：回報結果
    _report_creation_success(
        ticket_id=ticket_id,
        config=config,
        args=args,
        ticket=ticket,
        parent_info=parent_info,
        tdd_result=tdd_result,
        ticket_path=ticket_path,
    )

    return 0


def execute(args: argparse.Namespace) -> int:
    """執行 create 命令 — 協調四個步驟"""
    version = resolve_version(args.version)
    if not version:
        print(format_error(ErrorMessages.VERSION_NOT_DETECTED))
        return 1

    # Step 1: 解析版本和 Ticket ID
    resolved = _resolve_ticket_id_and_wave(args, version)
    if resolved is None:
        return 1
    version, ticket_id, wave = resolved

    # 識別任務類型並取得 TDD 順序建議（需要在 Step 2 使用）
    ticket_type = args.type or "IMP"
    tdd_result = suggest_tdd_sequence(task_type=ticket_type)

    # Step 2: CLI 參數轉換為 TicketConfig
    config = _parse_cli_args_to_config(args, version, ticket_id, wave, tdd_result)
    if config is None:
        return 1

    # Step 3: 驗證 blockedBy + 重複偵測 + 持久化 + 輸出
    return _persist_and_report(args, config, version, ticket_id, tdd_result)


def _print_create_checklist(
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
        # 使用集中化的 TDD Phase 顯示名稱映射
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

    where_files = new_ticket.get("where", {}).get("files") or []

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


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 create 子命令"""
    parser = subparsers.add_parser(
        "create",
        help="建立新的 Atomic Ticket",
        epilog=(
            "範例:\n"
            "  ticket create --action 實作 --target 'SessionListPage 排序功能' --wave 3\n"
            "  ticket create --action 修復 --target 'ticket CLI 錯誤提示' --wave 3 --type ADJ\n"
            "  ticket create --action 分析 --target 'Monorepo 版本策略' --wave 1 --type ANA\n"
            "  ticket create --action 實作 --target '子任務描述' --parent 0.2.0-W3-001\n"
            "\n"
            "必填參數: --action（動詞）、--target（目標）\n"
            "根任務還需: --wave（Wave 編號）\n"
            "子任務需: --parent（父 Ticket ID，wave 和 seq 自動產生）"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", help="版本號（自動偵測）")
    parser.add_argument("--wave", type=int, required=False, help="Wave 編號（建立根任務時必須，子任務可省略）")
    parser.add_argument("--seq", type=int, help="序號（自動產生，子任務由 --parent 決定，通常不需指定）")
    parser.add_argument("--action", required=True, help=TrackMessages.ARG_CREATE_ACTION)
    parser.add_argument("--target", required=True, help=TrackMessages.ARG_CREATE_TARGET)
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
    parser.add_argument("--where", "--where-files", dest="where_files", help="影響檔案（逗號分隔，如 'file1.py,file2.py'）")
    parser.add_argument("--why", help="需求依據（IMP/ANA/ADJ 類型必填）")
    parser.add_argument("--how-type", help="Task Type: Implementation, Analysis, etc.")
    parser.add_argument("--how-strategy", help="實作策略")
    parser.add_argument("--parent", help="父 Ticket ID（子任務序號自動產生，勿指定 --seq）")
    parser.add_argument("--blocked-by", help="依賴的 Ticket IDs（逗號分隔，如 'ID1,ID2'）")
    parser.add_argument("--related-to", help="相關的 Ticket IDs（逗號分隔，如 'ID1,ID2'）")
    parser.add_argument("--acceptance", action="append", help="驗收條件（多次 --acceptance 或 | 分隔，如 '條件A|條件B'）")
    parser.add_argument("--decision-tree-entry", help="進入決策樹的層級")
    parser.add_argument("--decision-tree-decision", help="做出的決策")
    parser.add_argument("--decision-tree-rationale", help="決策理由")

    parser.set_defaults(func=execute)
