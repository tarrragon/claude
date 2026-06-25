"""
Ticket create 命令模組

負責建立新的 Atomic Ticket。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
import os
import sys
import traceback
from typing import Any, Dict, List, Optional

from ticket_system.lib.ticket_loader import (
    get_tickets_dir,
    save_ticket,
    load_ticket,
    resolve_version,
    get_ticket_path,
    list_tickets,
)
from ticket_system.lib.version import suggest_version_for_ticket
from ticket_system.lib.ticket_validator import (
    validate_ticket_id,
    extract_wave_from_ticket_id,
    extract_version_from_ticket_id,
    validate_blocked_by,
)
from ticket_system.lib.messages import (
    ErrorEnvelope,
    ErrorMessages,
    WarningMessages,
    InfoMessages,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_lifecycle_messages import (
    CreateMessages,
    format_msg,
)
from ticket_system.lib.command_tracking_messages import TrackMessages
from ticket_system.lib.ambiguous_prefix import register_ambiguous_prefix
from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    DEFAULT_PRIORITY,
    DEFAULT_HOW_TASK_TYPE,
    DEFAULT_UNDEFINED_VALUE,
    MAX_TICKET_DEPTH,
)
from ticket_system.lib.depth import compute_depth
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
    update_source_spawned_tickets,
    validate_create_checklist,
)
from ticket_system.lib.file_lock import create_id_allocation_lock
from ticket_system.lib.duplicate_detector import (
    detect_duplicate_tickets,
    detect_in_progress_groups,
    enforce_blocking_duplicate,
)
from ticket_system.lib.create_reporter import (
    extract_where_files,
    print_create_checklist,
)


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
            print(format_error(ErrorEnvelope(
                component="create",
                action="validate_blocked_by",
                errno="BLOCKED_BY_NOT_FOUND",
                hint=f"找不到依賴的 Ticket: {bid}（請確認 ID 正確且已建立）",
            )))
            return False

    # 驗證 2：blockedBy 循環依賴檢測
    all_tickets = list_tickets(version)
    valid, cycle_msg, cycle_path = validate_blocked_by(
        ticket_id,
        blocked_by,
        all_tickets
    )
    if not valid and cycle_msg:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_blocked_by",
            errno="BLOCKED_BY_CYCLE",
            hint=cycle_msg,
        )))
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
            print(format_error(ErrorEnvelope(
                component="create",
                action="validate_decision_tree",
                errno="DECISION_TREE_EMPTY_VALUE",
                hint=f"欄位 {name} 不可為空字串",
            )))
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
    5. 非豁免時無參數 → 返回 None（不提前退出，交 _validate_create_checklist
       與其他必填欄位一次列全，W1-029 A2 同手法）
    6. 非豁免時有完整參數 → 返回字典（驗證後）
    7. 非豁免時部分參數 → raise ValueError（拒絕，保留參數級精確 hint）

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
        # 無參數：豁免或非豁免皆 return None，不在此提前退出。
        # 非豁免全缺交給 _validate_create_checklist 的 decision_tree_path
        # 完整性檢查，與 when/who/how_strategy 等必填一次列全，避免跨階段
        # 分批報錯造成多輪試錯（W1-029，A2 同手法，對齊本檔 why 修復 796-799）。
        # PARTIAL（provided_count 1-2）與 EMPTY_VALUE 仍即時精確報錯，不退化。
        return None

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
        print(format_error(ErrorEnvelope(
            component="create",
            action="build_decision_tree",
            errno="EXEMPTED_PARTIAL_PARAMS",
            hint="子任務或 DOC 類型可豁免 decision-tree 參數，但若提供必須三參數齊備",
        )))
    else:
        missing_fields = []
        if entry is None:
            missing_fields.append("entry_point")
        if decision is None:
            missing_fields.append("final_decision")
        if rationale is None:
            missing_fields.append("rationale")
        print(format_error(ErrorEnvelope(
            component="create",
            action="build_decision_tree",
            errno="DECISION_TREE_MISSING_PARTIAL",
            hint=f"缺少欄位: {', '.join(missing_fields)}（三參數必須齊備）",
        )))
    raise ValueError("決策樹參數不完整")



def _print_in_progress_group_hint(
    version: str, wave: Optional[int], new_ticket_id: str
) -> None:
    """印出 in_progress group 提示（不阻擋）。

    若新 ticket 自身即為某 group 的子（ID 前綴匹配），跳過提示避免噪音。
    """
    groups = detect_in_progress_groups(version, wave)
    if not groups:
        return

    for group in groups:
        gid = group.get("id") or ""
        if gid and new_ticket_id.startswith(gid + "."):
            return

    print()
    for group in groups:
        gid = group.get("id", "<unknown>")
        children_count = len(group.get("children") or [])
        print(
            f"  → 偵測到 in_progress group：{gid} "
            f"({children_count} children)。是否該 --parent {gid}？"
        )


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

        # 深度上限檢查（W1-056.5 協議 v2 D3）：沿 parent_id 鏈計算新子任務深度，
        # 達/超過 MAX_TICKET_DEPTH 時 warn（不硬擋，留旁路）。深度沿 parent_id 鏈
        # 而非 ID 字串數點（linux F1 fatal 教訓）。
        new_depth = compute_depth(args.parent, version) + 1
        if new_depth >= MAX_TICKET_DEPTH:
            print(format_warning(
                WarningMessages.DEPTH_LIMIT_REACHED,
                ticket_id=ticket_id,
                depth=new_depth,
                max_depth=MAX_TICKET_DEPTH,
            ))

        # 從 parent_id 中提取 wave
        extracted_wave = extract_wave_from_ticket_id(args.parent)
        if extracted_wave is not None:
            wave = extracted_wave
    else:
        # 建立根任務 ID
        if not wave:
            print(format_error(ErrorEnvelope(
                component="create",
                action="resolve_ticket_id",
                errno="MISSING_WAVE_PARAMETER",
                hint="建立根任務必須提供 --wave 參數（子任務則用 --parent 自動繼承 wave）",
            )))
            return None

        if args.seq is None:
            # auto-seq 模式：get_next_seq 回傳值已內部保證可用（W1-051 內聚
            # collision guard 至 get_next_seq 降級分支），caller 不再兜底。
            # 防護 W1-042：兩來源（本地 glob + main ref）同時掃空降級時，
            # get_next_seq 內的 resolve_available_seq 推進至本地檔案系統可用
            # 序號——僅保證本地 FS 可用，main-only 票不在保證範圍（W1-052 措辭
            # 對齊；PC-152 collision 家族；消除 caller while-loop 特例外洩）。
            seq = get_next_seq(version, wave)
            ticket_id = format_ticket_id(version, wave, seq)
        else:
            # 顯式 --seq 模式：尊重用戶意圖，撞號報錯退出（不覆寫、不自動跳號）。
            seq = args.seq
            ticket_id = format_ticket_id(version, wave, seq)
            if get_ticket_path(version, ticket_id).exists():
                print(format_error(ErrorEnvelope(
                    component="create",
                    action="resolve_ticket_id",
                    errno="TICKET_ID_ALREADY_EXISTS",
                    hint=(
                        f"顯式 --seq {seq} 對應的 Ticket ID 已存在: {ticket_id}。"
                        f"請改用其他 --seq，或省略 --seq 由系統自動配下一個可用序號"
                    ),
                )))
                return None

    # 驗證 Ticket ID
    if not validate_ticket_id(ticket_id):
        print(format_error(ErrorEnvelope(
            component="create",
            action="resolve_ticket_id",
            errno="INVALID_TICKET_ID_FORMAT",
            hint=f"Ticket ID 格式無效: {ticket_id}（預期: <version>-W<wave>-<seq>）",
        )))
        return None

    return (version, ticket_id, wave)


def _inherit_parent_who(parent_ticket: Optional[Dict[str, Any]]) -> str:
    """從 parent ticket 取 who.current，相容舊字串格式。

    W11-003.7: 舊 ticket（v0.16/v0.17 早期）who 為字串；新格式為 dict {current, history}。
    型別防護策略：dict 走 .get("current")、str 直接使用、None/缺失 fallback "pending"。
    """
    if not parent_ticket:
        return "pending"
    who = parent_ticket.get("who")
    if isinstance(who, dict):
        return who.get("current") or "pending"
    if isinstance(who, str) and who:
        return who
    return "pending"


def _inherit_parent_where_layer(parent_ticket: Optional[Dict[str, Any]]) -> str:
    """從 parent ticket 取 where.layer，相容舊字串格式。

    W11-003.7: 舊 ticket where 為字串（即 layer 描述），新格式為 dict {layer, files}。
    型別防護策略：dict 走 .get("layer")、str 直接使用、None/缺失 fallback DEFAULT_UNDEFINED_VALUE。
    """
    if not parent_ticket:
        return DEFAULT_UNDEFINED_VALUE
    where = parent_ticket.get("where")
    if isinstance(where, dict):
        return where.get("layer") or DEFAULT_UNDEFINED_VALUE
    if isinstance(where, str) and where:
        return where
    return DEFAULT_UNDEFINED_VALUE


def _validate_where_file_token(token: str) -> tuple:
    """驗證單一 --where 路徑 token 是否為合法檔案路徑。

    防護 where.files 髒值：曾出現將 'key=value' 形式（如 src=.claude/x、
    layer=core）誤當路徑傳入 --where，髒值寫進 where.files 後致下游路徑
    分類器誤判（含前綴的 token 被當非框架路徑），級聯成派發誤診。

    判定規則：取路徑「第一段」（首個 '/' 之前的字串），若其中含 '='，
    視為 key=value 前綴髒值並 reject。'=' 出現在第一段之後（路徑中段或
    檔名）屬合法檔名字元，放行。空字串由上游過濾，此處視為合法。

    Args:
        token: 單一路徑 token

    Returns:
        (is_valid, hint) tuple：
        - is_valid: True 表示合法路徑；False 表示髒值
        - hint: 髒值時的修正提示（含剝除前綴後的建議路徑）；合法時為空字串
    """
    if not token:
        return True, ""

    first_segment = token.split("/", 1)[0]
    if "=" not in first_segment:
        return True, ""

    # 第一段含 '='：視為 key=value 前綴髒值，提供剝除前綴的修正建議
    stripped = token.split("=", 1)[1]
    hint = (
        f"路徑 token 含非路徑前綴（'='）於首段: '{token}'。"
        f"請改用純路徑，例如剝除前綴後的 '{stripped}'"
    )
    return False, hint


def _validate_where_files(tokens: List[str]) -> List[str]:
    """批次驗證 --where 路徑 token，收集所有髒值錯誤訊息。

    Args:
        tokens: 已 strip 的路徑 token 列表

    Returns:
        錯誤訊息列表（每個髒值 token 一條）；全部合法時回空 list
    """
    errors: List[str] = []
    for token in tokens:
        is_valid, hint = _validate_where_file_token(token)
        if not is_valid:
            errors.append(hint)
    return errors


_ACCEPTANCE_SEP = "|"


def _parse_acceptance_items(raw_items: List[str]) -> tuple:
    """解析 --acceptance 多值，支援分隔符拆條 + 反斜線跳脫 + 拆條警告。

    分隔符 `|` 用於在單一 --acceptance 值內表達多條驗收條件。但當內文本身
    需要使用該字元（如描述 shell pipe），無條件 split 會靜默拆條（W3-089）。

    處理規則：
    - `\\|`（反斜線 + 分隔符）視為跳脫，還原為字面 `|`，不拆條。
    - 未跳脫的 `|` 才作為分隔符拆條。
    - 單一 --acceptance 值經未跳脫分隔符拆出 > 1 段時，回傳警告供呼叫端提示，
      讓使用者確認是否為預期行為（與 PC-079 同家族：CLI 參數含工具特殊字元）。

    Args:
        raw_items: argparse 收集的 --acceptance 值列表（可能多次指定）

    Returns:
        (acceptance, warnings) tuple：
        - acceptance: 解析後的驗收條件列表（已去空白、去空項）
        - warnings: 警告訊息列表（每個被拆條的原始值各一條）
    """
    acceptance: List[str] = []
    warnings: List[str] = []
    for item in raw_items:
        segments = _split_unescaped(item, _ACCEPTANCE_SEP)
        cleaned = [s.strip() for s in segments]
        cleaned = [s for s in cleaned if s]
        if len(cleaned) > 1:
            preview = "\n".join(f"             {i + 1}. {s}" for i, s in enumerate(cleaned))
            warnings.append(
                format_warning(
                    CreateMessages.ACCEPTANCE_PIPE_SPLIT_WARNING,
                    count=len(cleaned),
                    preview=preview,
                )
            )
        acceptance.extend(cleaned)
    return acceptance, warnings


def _split_unescaped(text: str, sep: str) -> List[str]:
    """以 sep 拆分 text，但反斜線跳脫的 sep 還原為字面字元不拆。

    逐字元掃描：`\\sep` → 字面 sep；單獨 `\\` 後接其他字元 → 保留原樣；
    未跳脫 sep → 切段。避免 str.split 無法區分跳脫的限制。
    """
    segments: List[str] = []
    buffer: List[str] = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == "\\" and i + 1 < length and text[i + 1] == sep:
            buffer.append(sep)
            i += 2
            continue
        if char == sep:
            segments.append("".join(buffer))
            buffer = []
            i += 1
            continue
        buffer.append(char)
        i += 1
    segments.append("".join(buffer))
    return segments


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

    # 驗證路徑 token：reject 非路徑髒值（如 src=.claude/x、layer=core）。
    # 髒值若寫入 where.files 會致下游派發路徑分類誤判，故前置攔下。
    where_errors = _validate_where_files(where_files)
    if where_errors:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_where_files",
            errno="INVALID_WHERE_FILE_TOKEN",
            hint="--where 含非路徑 token（key=value 前綴髒值），請改用純路徑：\n"
            + "\n".join(f"  - {e}" for e in where_errors),
        )))
        return None

    # 處理 blocked_by
    blocked_by = [b.strip() for b in args.blocked_by.split(",")] if args.blocked_by else []

    # 處理 related_to
    related_to = [r.strip() for r in args.related_to.split(",")] if args.related_to else []

    # 處理 acceptance（支援多次 --acceptance 和分隔符拆條 + 反斜線跳脫 + 拆條警告）
    acceptance = None
    if args.acceptance:
        acceptance, accept_warnings = _parse_acceptance_items(args.acceptance)
        for warning in accept_warnings:
            print(warning, file=sys.stderr)

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

    # PC-018: why 必填（DOC 類型豁免）。不在此提前退出——統一交給
    # _validate_create_checklist 與 when/who/how_strategy 等缺漏一次列全，
    # 避免分批報錯造成多輪試錯（1.0.0-W1-024.1 A2）
    why_value = args.why or (parent_ticket.get("why") if parent_ticket else DEFAULT_UNDEFINED_VALUE)

    return {
        "ticket_id": ticket_id,
        "version": version,
        "wave": wave,
        "title": args.title or f"{args.action} {args.target}",
        "ticket_type": ticket_type,
        "priority": args.priority or DEFAULT_PRIORITY,
        "who": args.who or _inherit_parent_who(parent_ticket),
        "what": args.what or f"{args.action} {args.target}",
        "when": args.when or DEFAULT_UNDEFINED_VALUE,
        "where_layer": args.where_layer or _inherit_parent_where_layer(parent_ticket),
        "where_files": where_files,
        "why": why_value,
        "how_task_type": args.how_type or DEFAULT_HOW_TASK_TYPE,
        "how_strategy": args.how_strategy or DEFAULT_UNDEFINED_VALUE,
        "parent_id": args.parent,
        "blocked_by": blocked_by if blocked_by else None,
        "related_to": related_to if related_to else None,
        "source_ticket": args.source_ticket,
        "acceptance": acceptance,
        "tdd_phase": tdd_phase,
        "tdd_stage": tdd_result.phases,
        "decision_tree_path": decision_tree_path,
    }


def _validate_before_persist(
    version: str,
    ticket_id: str,
    config: TicketConfig,
    allow_duplicate: bool = False,
) -> bool:
    """驗證層：執行持久化前的所有驗證。

    負責：
    1. 驗證 blockedBy 存在性和循環依賴
    2. Tier 2 阻擋層：同窗口高相似度冪等防護（命中且未旁路時阻擋）
    3. Tier 1 警告層：重複偵測（僅警告不阻擋）

    Args:
        version: 版本號
        ticket_id: Ticket ID
        config: Ticket 配置
        allow_duplicate: --allow-duplicate 旁路 Tier 2 阻擋層

    Returns:
        True 表示驗證通過，False 表示驗證失敗
    """
    blocked_by = config.get("blocked_by")

    # 驗證 blockedBy 存在性
    if not _validate_blocked_by_references(version, ticket_id, blocked_by):
        return False

    # Tier 2 阻擋層（W1-040.1 冪等防護）：命中且未旁路 → 阻擋
    if not enforce_blocking_duplicate(
        version=version,
        new_title=config["title"],
        new_what=config["what"],
        new_ticket_id=ticket_id,
        allow_duplicate=allow_duplicate,
    ):
        return False

    # Tier 1 警告層：重複偵測（僅警告不阻擋）
    detect_duplicate_tickets(
        version=version,
        new_title=config["title"],
        new_what=config["what"],
        new_ticket_id=ticket_id,
    )

    return True


# _validate_create_checklist 已下沉至 lib/ticket_builder.py（1.0.0-W1-027，
# 三建票路徑共用驗證邏輯，根除散落漂移 ARCH-020）。保留私有別名以向後相容
# 既有 import（tests/test_create_ux_merged_validation.py）與本檔呼叫鏈。
_validate_create_checklist = validate_create_checklist


def _suggest_field_value(field: str, ticket_type: str, action: str) -> str | None:
    """根據 ticket_type + action 推導缺失欄位的建議值（0.3.4-W2-001）。"""
    suggestions: dict[str, dict[str, str | None]] = {
        "who": {
            "ANA": "主線程",
            "DOC": "主線程",
            "IMP": "待派發",
            "ADJ": "待派發",
            "TST": "待派發",
            "RES": "主線程",
            "INV": "主線程",
        },
        "acceptance": {
            "ANA": "產出分析報告，含具體改進建議與 IMP spawn 規劃",
            "IMP": "測試通過 + 功能驗證",
            "DOC": "文件更新完成",
            "ADJ": "改善項目驗證通過",
        },
    }
    return suggestions.get(field, {}).get(ticket_type)


def _enforce_create_checklist(missing: List[str], force: bool,
                              ticket_type: str = "IMP", action: str = "") -> None:
    """W11-003.5: 將清單式驗證從 WARNING 升級為阻擋建立。

    根據缺失欄位清單與 --force 旗標決定行為：
    - 無缺失：直接 return（不阻擋）
    - 有缺失 + 未 --force：印錯誤訊息、建議值並 sys.exit(1)
    - 有缺失 + --force：印 WARNING 但允許繼續（保留快速建立逃生閥）

    0.3.4-W2-001: 缺失欄位附帶基於 type+action 的建議值，從「攔截」改為「攔截+引導」。

    Args:
        missing: _validate_create_checklist 回傳的缺失欄位清單
        force: 是否啟用 --force 跳過阻擋
        ticket_type: Ticket 類型（用於推導建議值）
        action: --action 參數值（用於推導建議值）
    """
    if not missing:
        return

    if force:
        print()
        print(format_warning("Create 清單驗證：以下欄位未填寫（已 --force 跳過阻擋）"))
        for field in missing:
            suggestion = _suggest_field_value(field, ticket_type, action)
            hint = f"  [建議] --{field.replace('.', '-')} \"{suggestion}\"" if suggestion else ""
            print(f"  - {field}{hint}")
        print()
        return

    print()
    print(format_error(ErrorEnvelope(
        component="create",
        action="enforce_checklist",
        errno="CHECKLIST_VALIDATION_FAILED",
        hint=f"以下欄位為必填（缺失將阻擋建立）: {', '.join(missing)}",
    )))
    for field in missing:
        suggestion = _suggest_field_value(field, ticket_type, action)
        if suggestion:
            print(f"  - {field}")
            print(f"    [建議] --{field.replace('.', '-')} \"{suggestion}\"")
        else:
            print(f"  - {field}")
    print()
    print(
        "請補齊上述欄位後重試。若需快速建立可加 --force 跳過此檢查"
        "（不建議用於正式 Ticket，後續仍需補齊以利交接）。"
    )
    print()
    sys.exit(1)


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
    body = create_ticket_body(
        frontmatter["what"],
        frontmatter["who"]["current"],
        frontmatter.get("type", ""),
    )
    ticket = frontmatter.copy()
    ticket["_body"] = body

    tickets_dir = get_tickets_dir(version)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = get_ticket_path(version, ticket_id)
    save_ticket(ticket, ticket_path)

    # 落盤後驗證（W1-042）：確認檔案確實寫入預期路徑。
    # W1-039 事件中出現「記錄平面幻影但世界平面無檔案落盤」，此驗證使
    # 落盤失敗成為顯性錯誤而非靜默成功（規則 4：異常可觀測）。
    if not ticket_path.exists():
        sys.stderr.write(
            f"[ERROR] _build_and_save_ticket: ticket {ticket_id} save_ticket 後 "
            f"檔案不存在於預期路徑 {ticket_path}（落盤驗證失敗）\n"
        )
        raise FileNotFoundError(
            f"Ticket {ticket_id} 落盤驗證失敗：{ticket_path} 不存在"
        )

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
    print_create_checklist(
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
    allow_duplicate = bool(getattr(args, "allow_duplicate", False))
    if not _validate_before_persist(version, ticket_id, config, allow_duplicate):
        return 1

    # 步驟 1.5：PROP-009 清單式欄位驗證（W11-003.5 升級為阻擋；--force 可豁免）
    ticket_type = config.get("ticket_type", "IMP")
    missing_fields = _validate_create_checklist(config, ticket_type)
    force_flag = bool(getattr(args, "force", False))
    _enforce_create_checklist(
        missing_fields, force=force_flag,
        ticket_type=ticket_type, action=config.get("action", ""),
    )

    # 步驟 2：持久化
    ticket = _build_and_save_ticket(version, ticket_id, config)
    ticket_path = str(get_ticket_path(version, ticket_id))

    # 步驟 3：更新關係
    parent_info = _update_parent_and_get_parent_info(args, version, ticket_id)

    # 步驟 3.5：更新 source 的 spawned_tickets（PC-073；與 --parent 互斥，兩者不會同時觸發）
    if args.source_ticket:
        if update_source_spawned_tickets(args.source_ticket, ticket_id):
            print(format_msg(
                CreateMessages.SOURCE_TICKET_UPDATED,
                source_id=args.source_ticket,
                new_id=ticket_id,
            ))
        else:
            print(format_warning(
                CreateMessages.SOURCE_UPDATE_FAILED,
                source_id=args.source_ticket,
            ))

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

    # 步驟 5（W17-008.15 方案 D）：未帶 --parent 時提示 in_progress group
    if not args.parent:
        wave_for_hint = config.get("wave") if isinstance(config, dict) else None
        _print_in_progress_group_hint(version, wave_for_hint, ticket_id)

    return 0


def _validate_source_ticket_arg(args: argparse.Namespace) -> bool:
    """Step 1.5：--source-ticket 參數前置驗證（PC-073）。

    檢查順序（fail-fast，三視角共識）：
    1. 互斥檢查：--source-ticket 與 --parent 不可同用
    2. ID 格式檢查：沿用 validate_ticket_id
    3. 存在性檢查：載入 source ticket
    4. 狀態警告：completed 允許但顯示 WARNING（allow + warning，不阻擋）

    所有錯誤路徑在持久化前結束；fail-fast 順序一致。

    Args:
        args: 命令行參數（含 source_ticket 和 parent）

    Returns:
        bool: True 表示驗證通過（或未提供 --source-ticket）；False 表示應 early return 1
    """
    # Guard Clause：未提供 --source-ticket 則跳過
    if not args.source_ticket:
        return True

    # 子步驟 1：互斥檢查（最先；測試 B4 的 ordering 斷言依此成立）
    if args.parent:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_source_ticket",
            errno="SOURCE_PARENT_MUTUALLY_EXCLUSIVE",
            hint="--source-ticket 與 --parent 不可同時使用（前者為衍生關係，後者為父子關係）",
        )))
        return False

    # 子步驟 2：ID 格式檢查（沿用 validate_ticket_id）
    if not validate_ticket_id(args.source_ticket):
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_source_ticket",
            errno="INVALID_TICKET_ID_FORMAT",
            hint=f"--source-ticket ID 格式無效: {args.source_ticket}",
        )))
        return False

    # 子步驟 3：存在性檢查
    source_version = extract_version_from_ticket_id(args.source_ticket)
    if source_version is None:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_source_ticket",
            errno="SOURCE_TICKET_NOT_FOUND",
            hint=f"無法從 ID 推斷版本: {args.source_ticket}",
        )))
        return False
    source_ticket = load_ticket(source_version, args.source_ticket)
    if source_ticket is None:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_source_ticket",
            errno="SOURCE_TICKET_NOT_FOUND",
            hint=f"找不到 source ticket: {args.source_ticket}（請確認 ID 正確且檔案存在）",
        )))
        return False

    # 子步驟 4：狀態警告（allow + warning；不阻擋）
    if source_ticket.get("status") == STATUS_COMPLETED:
        print(format_warning(
            CreateMessages.SOURCE_TICKET_COMPLETED_WARN,
            source_id=args.source_ticket,
        ))
        # 非 ANA type 無額外警告（pepper §8 決策：消除特例）

    return True


def _auto_extract_context_bundle_post_create(
    version: str,
    ticket_id: str,
    quiet: bool = False,
    verbose: bool = False,
    json_output: bool = False,
) -> None:
    """Create 後的 Context Bundle 自動抽取 wire-in（W17-002.2）。

    僅當 target ticket 具備 source_ticket / blocked_by / related_to 之一時才觸發。
    異常降級：任何例外都寫入 stderr traceback，退出碼保 0（主流程不阻斷）。

    設計依據：W17-002 Phase 1 §5.1 create-insert 虛擬碼 + §v2.3 Non-raising。
    """
    try:
        from ticket_system.lib.context_bundle_extractor import (
            extract_and_write_context_bundle,
            format_cli_summary,
            format_cli_summary_json,
        )
        from ticket_system.lib.ticket_loader import load_ticket

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
        sys.stderr.write(traceback.format_exc())
        sys.stderr.write("[Context Bundle] 抽取失敗，不影響 ticket 建立\n")


def execute(args: argparse.Namespace) -> int:
    """執行 create 命令 — 協調四個步驟"""
    ticket_type = args.type or "IMP"
    action = args.action or ""

    # 版本歸屬引導：根據 type + action 建議目標版本
    suggestion = suggest_version_for_ticket(ticket_type, action)
    user_specified_version = args.version is not None

    if suggestion and not user_specified_version:
        suggested_ver, reason = suggestion
        print(format_info(
            "[版本歸屬引導] 建議版本: {version}（{reason}）",
            version=suggested_ver,
            reason=reason,
        ))
        args.version = suggested_ver

    version = resolve_version(args.version)
    if not version:
        print(format_error(ErrorEnvelope(
            component="create",
            action="resolve_version",
            errno="VERSION_NOT_DETECTED",
            hint="無法自動偵測版本號，請使用 --version 明確指定（或確認 todolist.yaml 已設定 current_version）",
        )))
        return 1

    # 版本歸屬 warning：用戶指定版本但與建議不符
    if suggestion and user_specified_version:
        suggested_ver, reason = suggestion
        if version != suggested_ver:
            print(format_warning(
                "[版本歸屬引導] 指定版本 {version} 與建議版本 {suggested} 不符"
                "（{reason}）。如有意為之請忽略此警告",
                version=version,
                suggested=suggested_ver,
                reason=reason,
            ))

    # 驗證版本已在 todolist.yaml 中註冊
    from ticket_system.lib.version import validate_version_registered
    is_valid, error_msg = validate_version_registered(version)
    if not is_valid:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_version",
            errno="VERSION_NOT_REGISTERED",
            hint=error_msg,
        )))
        return 1

    # IMP-072 方案 A：Step 1（ID 分配）到 Step 3（落盤）之間原本無鎖，跨
    # process / 跨 session 並行 create 會同讀相同 max seq 配出同一 ID，後寫者
    # 靜默覆寫前者。目錄級 fcntl lock 將整段臨界區序列化；lock 取得失敗時
    # graceful degradation（stderr warn + 無鎖續行），不阻斷單 process create。
    with create_id_allocation_lock(get_tickets_dir(version)):
        # Step 1: 解析版本和 Ticket ID
        resolved = _resolve_ticket_id_and_wave(args, version)
        if resolved is None:
            return 1
        version, ticket_id, wave = resolved

        # Step 1.5: --source-ticket 前置驗證（PC-073）
        # 順序：互斥 → 格式 → 存在 → 狀態
        if not _validate_source_ticket_arg(args):
            return 1

        # 識別任務類型並取得 TDD 順序建議（需要在 Step 2 使用）
        ticket_type = args.type or "IMP"
        tdd_result = suggest_tdd_sequence(task_type=ticket_type)

        # Step 2: CLI 參數轉換為 TicketConfig
        config = _parse_cli_args_to_config(args, version, ticket_id, wave, tdd_result)
        if config is None:
            return 1

        # Step 3: 驗證 blockedBy + 重複偵測 + 持久化 + 輸出
        rc = _persist_and_report(args, config, version, ticket_id, tdd_result)

    # Step 4 (W17-002.2)：Context Bundle 自動抽取（post-persist enhancement）
    if rc == 0:
        _auto_extract_context_bundle_post_create(
            version,
            ticket_id,
            quiet=bool(getattr(args, "quiet", False)),
            verbose=bool(getattr(args, "verbose", False)),
            json_output=bool(getattr(args, "json_output", False)),
        )

    return rc



# 1.0.0-W1-028: 縮寫歧義攔截已抽為共用 helper，泛化原 _AmbiguousHowAction。
# 共用 hint 文字常數，供 --how / --ho 等更短前綴共用同一提示（DRY）。
_HOW_AMBIGUOUS_HINT = (
    "--how 不是有效旗標，請使用完整旗標名："
    "--how-type（任務類型，如 Implementation / Analysis）"
    "或 --how-strategy（實作策略）"
)


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
    # --how / --ho 攔截：exact match 優先於縮寫展開，給友善提示
    # （1.0.0-W1-024.1 A3 + 1.0.0-W1-028 模式化）。--ho 為更短前綴同類誤打，
    # 共用同一中文提示（約束 2 落地：攔截而非懸而未決）。
    register_ambiguous_prefix(parser, "--how", _HOW_AMBIGUOUS_HINT)
    register_ambiguous_prefix(parser, "--ho", _HOW_AMBIGUOUS_HINT)
    parser.add_argument("--how-type", help="Task Type: Implementation, Analysis, etc.")
    parser.add_argument("--how-strategy", help="實作策略")
    parser.add_argument("--parent", help="父 Ticket ID（子任務序號自動產生，勿指定 --seq）")
    parser.add_argument(
        "--source-ticket",
        dest="source_ticket",
        help=(
            "衍生來源 Ticket ID（建立 spawned_tickets 衍生關係，與 --parent 互斥）；"
            "衍生項獨立排程，不阻擋 source complete（PC-073）"
        ),
    )
    parser.add_argument("--blocked-by", help="依賴的 Ticket IDs（逗號分隔，如 'ID1,ID2'）")
    parser.add_argument("--related-to", help="相關的 Ticket IDs（逗號分隔，如 'ID1,ID2'）")
    parser.add_argument("--acceptance", action="append", help="驗收條件（多次 --acceptance 或 | 分隔，如 '條件A|條件B'）")
    # --decision-tree 攔截：撞 --decision-tree-entry/-decision/-rationale（1.0.0-W1-028）
    register_ambiguous_prefix(
        parser,
        "--decision-tree",
        "--decision-tree 不是有效旗標，請使用完整旗標名："
        "--decision-tree-entry（進入決策樹的層級）、"
        "--decision-tree-decision（做出的決策）"
        "或 --decision-tree-rationale（決策理由）",
    )
    parser.add_argument("--decision-tree-entry", help="進入決策樹的層級")
    parser.add_argument("--decision-tree-decision", help="做出的決策")
    parser.add_argument("--decision-tree-rationale", help="決策理由")
    parser.add_argument(
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Context Bundle 抽取摘要單行輸出（W17-002.2）",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Context Bundle 抽取摘要附欄位預覽（W17-002.2）",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Context Bundle 抽取結果以 JSON 結構化輸出（W17-002.1）",
    )
    parser.add_argument(
        "--force",
        dest="force",
        action="store_true",
        help=(
            "跳過 PROP-009 清單式欄位驗證（5W1H/acceptance/decision_tree_path）"
            "的阻擋（W11-003.5 逃生閥；不建議用於正式 Ticket）"
        ),
    )

    parser.add_argument(
        "--allow-duplicate",
        dest="allow_duplicate",
        action="store_true",
        help=(
            "旁路 Tier 2 同窗口高相似度阻擋層（W1-040.1 冪等防護逃生閥）；"
            "用於失誤後刻意重建近似 Ticket 的合法情境"
        ),
    )

    parser.set_defaults(func=execute)
