"""
Ticket create 命令模組

負責建立新的 Atomic Ticket。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
import sys
import traceback
from typing import Any, Dict, List, Optional

from ticket_system.constants import PRIORITY_LEVELS, TICKET_TYPES
from ticket_system.lib.ticket_loader import (
    get_tickets_dir,
    save_ticket,
    load_ticket,
    resolve_version,
    get_ticket_path,
)
from ticket_system.lib.version import suggest_version_for_ticket
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id
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
from ticket_system.lib.acceptance_parser import parse_acceptance_items
from ticket_system.lib.ticket_id_allocator import resolve_ticket_id_and_wave
from ticket_system.lib.field_validators import (
    build_decision_tree_path,
    check_when_blocked_by_consistency,
    directory_declaration_warnings,
    missing_where_paths,
    validate_blocked_by_references,
    validate_discovered_during_arg,
    validate_source_ticket_arg,
    validate_where_files,
)
from ticket_system.lib.topic_inference import (
    infer_topic,
    requires_topic_assignment,
    validate_topic_selection,
)
from ticket_system.lib.constants import (
    DEFAULT_PRIORITY,
    DEFAULT_HOW_TASK_TYPE,
    DEFAULT_UNDEFINED_VALUE,
)
from ticket_system.lib.tdd_sequence import suggest_tdd_sequence
from ticket_system.lib.ticket_builder import (
    TicketConfig,
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
from ticket_system.lib.create_reporter import print_create_checklist









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
    where_errors = validate_where_files(where_files)
    if where_errors:
        print(format_error(ErrorEnvelope(
            component="create",
            action="validate_where_files",
            errno="INVALID_WHERE_FILE_TOKEN",
            hint="--where 含非路徑 token（key=value 前綴髒值），請改用純路徑：\n"
            + "\n".join(f"  - {e}" for e in where_errors),
        )))
        return None

    # 目錄級 where.files 宣告 WARNING（PC-BAL-040）：建票時檔案未必可知，
    # 故此層僅警告非硬擋（硬擋在 `ticket track dispatch`，見 track_dispatch.py）。
    for warning in directory_declaration_warnings(where_files, args.type or "IMP"):
        print(warning)

    # where.files 路徑存在性 WARNING：建票時新檔案的 where 宣告合法
    # （如尚未建立的測試檔），故此層僅警告不阻擋。
    from ticket_system.lib.paths import get_project_root

    for missing in missing_where_paths(get_project_root(), where_files):
        print(format_warning(
            CreateMessages.WHERE_PATH_NOT_FOUND_WARNING,
            path=missing,
        ))

    # 處理 blocked_by
    blocked_by = [b.strip() for b in args.blocked_by.split(",")] if args.blocked_by else []

    # 處理 related_to
    related_to = [r.strip() for r in args.related_to.split(",")] if args.related_to else []

    # 處理 acceptance（支援多次 --acceptance 和分隔符拆條 + 反斜線跳脫 + 拆條警告）
    acceptance = None
    if args.acceptance:
        acceptance, accept_warnings = parse_acceptance_items(args.acceptance)
        for warning in accept_warnings:
            print(warning, file=sys.stderr)

    # 識別任務類型
    ticket_type = args.type or "IMP"

    # 建立決策樹路徑
    try:
        decision_tree_path = build_decision_tree_path(
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
        "discovered_during": getattr(args, "discovered_during", None),
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
    if not validate_blocked_by_references(version, ticket_id, blocked_by):
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

    # Tier 1 警告層：when-blockedBy 一致性檢查（僅警告不阻擋）
    check_when_blocked_by_consistency(
        when=config.get("when"),
        blocked_by=blocked_by,
    )

    return True


# _validate_create_checklist 已下沉至 lib/ticket_builder.py（1.0.0-W1-027，
# 三建票路徑共用驗證邏輯，根除散落漂移 ARCH-020）。保留私有別名以向後相容
# 既有 import（tests/test_create_ux_merged_validation.py）與本檔呼叫鏈。
_validate_create_checklist = validate_create_checklist


def _suggest_field_value(field: str, ticket_type: str, action: str) -> str | None:
    """根據 ticket_type + action 推導缺失欄位的建議值。"""
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

    # 落盤前存在性檢查：create 只能新增，不可覆寫既有 ticket。get_next_seq
    # 的三來源聯集（本地 ∪ main ref ∪ sibling worktree）理論上保證 candidate
    # 不撞已知來源，但掃描完成到落盤之間仍有極短時間窗，且降級分支（sibling
    # worktree 掃描失敗 / 非 git 環境鎖亦降級）下該保證會弱化。此處作最後一道
    # 防線：若目標路徑已存在，一律拒絕覆寫並清楚報錯，不靜默覆寫既有內容
    # （quality-baseline 規則 4：異常必須可觀測）。顯式 --seq 模式已在更早的
    # resolve_ticket_id_and_wave 檢查過存在性，故此處命中只會是 auto-seq
    # 計算出撞號候選值（並行 create race 的殘跡）。
    if ticket_path.exists():
        sys.stderr.write(
            f"[ERROR] _build_and_save_ticket: ticket {ticket_id} 目標路徑已存在"
            f"（{ticket_path}），拒絕覆寫。可能為並行 create 撞號（跨 worktree /"
            f"跨 session），請以 --seq 指定其他序號重試\n"
        )
        raise FileExistsError(
            f"Ticket {ticket_id} 已存在於 {ticket_path}，create 拒絕覆寫既有 ticket"
        )

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

    # auto-commit 呼叫已移至 execute() 內、Context Bundle 寫入
    # （_auto_extract_context_bundle_post_create）之後，使既有的那一筆 commit
    # 涵蓋完整內容；graceful degrade 與 worktree force-remove 防護說明見該處。

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




def _verify_ticket_intact(version: str, ticket_id: str) -> bool:
    """重新讀取 ticket 判斷其是否仍完整（未因寫入失敗而受損）。

    繞過 process-scoped 快取（parser._ticket_cache）：save_ticket 只在
    成功寫入後才失效快取，寫入失敗的路徑不會失效，直接呼叫 load_ticket
    可能讀到快取住的舊值而非磁碟現況，掩蓋真正的受損狀態。先清該 ticket
    的快取鍵，確保讀到磁碟當下內容。

    load_ticket 對 0 byte / 無 frontmatter 檔案回傳 None，對 YAML 解析
    失敗回傳含 `_yaml_error` 的字典；兩者皆視為受損信號。
    """
    from ticket_system.lib import parser as _parser

    # 快取鍵須用 parser.get_ticket_path（parser.load_ticket 內部實際解析
    # 路徑時所綁定的同一個名稱），而非 ticket_loader/paths 各自獨立綁定
    # 的版本——三者在生產環境等價，但測試以 monkeypatch 個別替換路徑時
    # 只有前者保證與 parser.load_ticket 讀到的快取鍵一致，否則快取鍵不
    # 匹配、pop 不到目標鍵，讀到的仍是損毀前的舊快取值。
    try:
        ticket_path = _parser.get_ticket_path(version, ticket_id)
        _parser._ticket_cache.pop(str(ticket_path), None)
    except Exception:
        pass

    reloaded = _parser.load_ticket(version, ticket_id)
    if reloaded is None:
        return False
    if "_yaml_error" in reloaded:
        return False
    return True


def _auto_extract_context_bundle_post_create(
    version: str,
    ticket_id: str,
    quiet: bool = False,
    verbose: bool = False,
    json_output: bool = False,
) -> bool:
    """Create 後的 Context Bundle 自動抽取 wire-in（W17-002.2）。

    僅當 target ticket 具備 source_ticket / blocked_by / related_to 之一時才觸發。
    異常降級：任何例外都寫入 stderr traceback，不 re-raise（主流程不因此中斷）。

    設計依據：create-insert 虛擬碼規格；驗證失敗採 Non-raising（降級不拋錯，
    主流程不因 Context Bundle 抽取失敗而中斷）。

    Returns:
        bool: True 表示 ticket 檔案完整（抽取成功，或抽取失敗但票面未受
        影響）；False 表示抽取失敗且事後驗證票面已受損。呼叫端應據此決定
        退出碼與是否略過 auto-commit——不可無條件宣稱「不影響 ticket
        建立」而不驗證（先前的重複故障：連續四次寫入失敗把票面清空為
        0 byte，訊息仍宣稱無影響，且被 auto-commit 提交入庫）。
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
            return True
        if not (
            target.get("source_ticket")
            or target.get("blocked_by")
            or target.get("blockedBy")
            or target.get("related_to")
            or target.get("relatedTo")
        ):
            return True

        result, _notes = extract_and_write_context_bundle(version, ticket_id)
        if json_output:
            print(format_cli_summary_json(result))
        else:
            print(format_cli_summary(result, quiet=quiet, verbose=verbose))
        return True
    except Exception:
        sys.stderr.write(traceback.format_exc())
        intact = _verify_ticket_intact(version, ticket_id)
        if intact:
            sys.stderr.write(
                "[Context Bundle] 抽取失敗，已重新讀取驗證 ticket 檔案完整"
                "未受影響\n"
            )
        else:
            sys.stderr.write(
                "[Context Bundle] 抽取失敗且 ticket 檔案已受損（重新讀取驗證"
                "失敗，內容可能已被截斷），請立即檢查 git diff 並視需要以 "
                "git checkout 還原\n"
            )
        return intact


def execute(args: argparse.Namespace) -> int:
    """執行 create 命令 — 協調四個步驟

    版本歸屬引導（建議版本 / VERSION_NOT_REGISTERED 檢查）僅對根票生效。
    子任務（--parent 存在）無條件繼承父票 version/wave，不受引導與註冊檢查
    影響（W5-005.13：子票版本應與父票綁定，引導推導值可能未在 todolist
    註冊而導致子票建立 hard-fail）。
    """
    ticket_type = args.type or "IMP"
    action = args.action or ""
    is_child = bool(args.parent)
    user_specified_version = args.version is not None

    # 主題選取驗證：先於任何版本解析/持久化動作執行，拒絕不存在的主題名
    # 時直接中止，不建立任何 ticket。--new-topic 的實際寫入延後至建票
    # 成功後才執行（見 validate_topic_selection docstring）。
    topic, topic_error, new_topic_to_register = validate_topic_selection(args)
    topic_basis = None
    if topic_error:
        print(format_error(ErrorEnvelope(
            component="create",
            action="resolve_topic",
            errno="INVALID_TOPIC",
            hint=topic_error,
        )))
        return 1

    # 判準 S1/S2 自動推導：僅在兩個顯式旗標皆未給時啟動，不改寫顯式選擇
    # （0.2.1-W3-826 判準；顯式優先是 Never break userspace 的要求）。
    if topic is None:
        topic, topic_basis = infer_topic(args)

    if is_child:
        # 子任務：version 無條件繼承父票，跳過版本歸屬引導與註冊檢查。
        # 優先從 --parent ticket ID 解析版本（父票版本為唯一權威來源），
        # 僅在 --parent 格式異常無法解析時才 fallback 至 resolve_version()。
        version = extract_version_from_ticket_id(args.parent)
        if not version:
            version = resolve_version(args.version)
        if not version:
            print(format_error(ErrorEnvelope(
                component="create",
                action="resolve_version",
                errno="VERSION_NOT_DETECTED",
                hint="無法從 --parent 解析版本號，請確認 --parent 格式正確",
            )))
            return 1
    else:
        # 根票：版本歸屬引導：根據 type + action 建議目標版本
        suggestion = suggest_version_for_ticket(ticket_type, action)

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

        # 驗證版本已在 todolist.yaml 中註冊（僅根票；子票版本繼承父票，無需重複驗證）
        from ticket_system.lib.version import (
            determine_fallback_version,
            is_version_registered,
            validate_version_registered,
        )
        is_valid, error_msg = validate_version_registered(version)
        if not is_valid:
            # 僅完全未註冊（非「已註冊但非 active」）時附加繞過指令：
            # 完全未註冊時使用者多半是被動詞分類誤導至錯誤版本，此時提供
            # 現成的 --version 候選值最有幫助；已註冊但非 active 的情境
            # 語意不同（版本存在但被關閉/尚未開始），不適用同一套推導。
            if not is_version_registered(version):
                fallback = determine_fallback_version(args.source_ticket)
                if fallback:
                    fallback_version, fallback_reason = fallback
                    error_msg = error_msg + ErrorMessages.VERSION_NOT_REGISTERED_FALLBACK_SUFFIX.format(
                        fallback_version=fallback_version,
                        fallback_reason=fallback_reason,
                    )
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
        resolved = resolve_ticket_id_and_wave(args, version)
        if resolved is None:
            return 1
        version, ticket_id, wave = resolved

        # Step 1.5a: --discovered-during 前置驗證，先於 --source-ticket
        # 驗證執行——兩者互斥檢查不依賴 source ticket 是否存在，先做可
        # 避免不存在的 --source-ticket 值使互斥錯誤被存在性檢查蓋過。
        if not validate_discovered_during_arg(args):
            return 1

        # Step 1.5b: --source-ticket 前置驗證（PC-073）
        # 順序：互斥 → 格式 → 存在 → 狀態
        if not validate_source_ticket_arg(args):
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

    # 主題狀態回報：既有主題選取/新增不阻擋建票，僅於報告階段明確表示
    # 結果（已標記主題名 / 未指派），不寫入任何 ticket frontmatter 欄位。
    # 映射寫入（ticket_id -> topic）與 --new-topic 的主題名註冊皆延後至
    # 此（rc == 0 之後）才執行，避免建票失敗時已寫入 append-only 清單而
    # 留下孤兒主題或孤兒映射（修復缺口：原本只呼叫 append_topic 寫主題名
    # 清單，未寫入 ticket_id -> topic 映射，選定的主題不留下任何票與
    # 主題的關聯；append_assignment 內部已含冪等的 append_topic 呼叫，
    # 故 --new-topic 的主題名註冊亦一併由它完成，不再單獨呼叫）。
    if rc == 0:
        if topic:
            from ticket_system.lib.topic_assignments import append_assignment
            try:
                append_assignment(ticket_id, topic)
            except Exception as exc:
                # 映射寫入失敗降級為非致命：ticket 已成功建立，不應因
                # side-channel 映射寫入失敗而回頭判定整體建票失敗
                # （observability-rules 規則 1：降級處理需可見）。
                sys.stderr.write(
                    f"[create] 主題映射寫入失敗（非致命，ticket {ticket_id} "
                    f"已建立）：{exc}\n"
                )
            if topic_basis:
                print(format_info(
                    "[主題] 依 {basis} 自動指派主題：{topic}"
                    "（已記錄於主題中央清單與票-主題映射，未寫入 ticket "
                    "frontmatter；如需更正可用 topic-backfill-assign --reassign 改派）",
                    basis=topic_basis,
                    topic=topic,
                ))
            else:
                print(format_info(
                    "[主題] 已標記主題：{topic}（已記錄於主題中央清單與"
                    "票-主題映射，未寫入 ticket frontmatter）",
                    topic=topic,
                ))
        elif getattr(args, "no_topic", False):
            print(format_info(
                "[主題] 未指派主題（--no-topic 明示不指派）",
            ))
        elif requires_topic_assignment(args):
            # 判準 S3：ANA 未歸屬會使其整串衍生票一併失明，訊息須說明後果
            # 而非僅陳述狀態（0.2.1-W3-826 實驗 H2：純狀態提示無效）。
            print(format_warning(
                "[主題] 未指派主題且無法自動推導。此票為 ANA 型（判準 S3），"
                "其衍生票會經上游繼承取得主題，未歸屬將使整串後續票不出現於"
                "任何主題分組。請以 --topic 或 --new-topic 指定，"
                "或以 --no-topic 明示不指派",
            ))
        else:
            print(format_warning(
                "[主題] 未指派主題且無法自動推導。未歸屬票不出現於主題分組的"
                "任何群組，需另查 runqueue 才找得到。請以 --topic 或 "
                "--new-topic 指定，或以 --no-topic 明示不指派",
            ))

    # Step 4 (W17-002.2)：Context Bundle 自動抽取（post-persist enhancement）
    ticket_intact = True
    if rc == 0:
        try:
            ticket_intact = _auto_extract_context_bundle_post_create(
                version,
                ticket_id,
                quiet=bool(getattr(args, "quiet", False)),
                verbose=bool(getattr(args, "verbose", False)),
                json_output=bool(getattr(args, "json_output", False)),
            )
        finally:
            # create 落盤後 auto-commit ticket md，與 append-log/set-acceptance
            # 同保護等級。順序調整為在 Context Bundle 寫入之後才 commit，使
            # 既有的那一筆 commit 涵蓋完整內容（含 Context Bundle 區塊），不
            # 新增第二次 commit。以 try/finally 包住 Context Bundle 抽取，
            # 確保即使該步驟拋出例外，commit 仍會執行。
            #
            # 根因：worktree 內 create 產出的 ticket md 若停留 untracked，
            # `git diff`/`git diff --staged` 皆偵測不到，分支合併不會帶入該
            # 檔案的任何內容（merge 只作用於已 commit 的物件，未 commit 的
            # index/working tree 狀態不隨 merge 傳遞），`git worktree remove
            # --force` 會連同該 worktree 目錄整個丟棄——「先 git add 再等下次
            # append-log 補 commit」不足以防護：force 移除不看 staged 與否，
            # 只看 committed 與否。故直接複用 _auto_commit_ticket_md 完整
            # add+commit，不僅 add。
            # graceful degrade：非 git repo / index.lock 競爭 / commit 失敗
            # → create 仍 exit 0 + stderr 警告，body 已由 save_ticket 落於
            # working tree。
            #
            # 票面受損時（ticket_intact=False）略過 auto-commit：commit
            # 一個已知受損的檔案等於把破壞永久寫入 git 歷史，且會誤導後續
            # 讀者以為此狀態是刻意的。改為留在 working tree 讓人工介入。
            if ticket_intact:
                ticket_path = str(get_ticket_path(version, ticket_id))
                from ticket_system.lib import git_utils
                try:
                    commit_status = git_utils._auto_commit_ticket_md(
                        ticket_path, ticket_id, "Task Summary", operation="create",
                    )
                    if commit_status in ("not_git_repo", "git_failed"):
                        sys.stderr.write(
                            f"[create] auto-commit skipped（{commit_status}，非致命）；"
                            f"ticket md 已保留 working tree，可手動 git commit 持久化。\n"
                        )
                except Exception as exc:
                    sys.stderr.write(
                        f"[create] auto-commit 失敗（非致命，ticket md 已保留 "
                        f"working tree）：{exc}\n"
                    )
            else:
                sys.stderr.write(
                    "[create] 偵測到 ticket 檔案受損，已略過 auto-commit 避免"
                    "將受損內容提交入庫；請人工檢查並修復後手動 git add + commit\n"
                )

    if not ticket_intact:
        # 票面已受損：即使前面步驟回報 rc == 0，最終退出碼仍須反映失敗，
        # 不可讓 CLI 以成功狀態結束（先前故障：訊息宣稱不影響、退出碼 0，
        # 連續四次相同失敗都被讀成成功）。
        rc = 1

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
        "--type",
        choices=list(TICKET_TYPES),
        help="類型: IMP, ADJ, ANA, DOC（預設: IMP；TST/RES/INV 已收斂為歷史化石，新票不可用）",
    )
    parser.add_argument(
        "--priority",
        choices=PRIORITY_LEVELS,
        help="優先級: P0, P1, P2, P3（預設: P2）",
    )
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
    parser.add_argument(
        "--discovered-during",
        dest="discovered_during",
        help=(
            "發現衍生來源 Ticket ID（記錄發現脈絡，與 --source-ticket 互斥）；"
            "與 --source-ticket 的差異：--source-ticket 是規劃衍生，會經 S1 判準"
            "繼承上游主題；--discovered-during 是執行中撞到的跨主題發現，"
            "上游主題與新票內容無關，S1 不觸發，主題仍可能經 S2 檔案叢集推導"
        ),
    )
    parser.add_argument(
        "--topic",
        help="指定既有主題名（須為主題中央清單既有名稱；未命中會列出既有主題名並拒絕）",
    )
    parser.add_argument(
        "--new-topic",
        dest="new_topic",
        help="以顯式旗標新增主題並指派給本票（--topic 僅能選既有主題，新增須用此旗標）",
    )
    parser.add_argument(
        "--no-topic",
        dest="no_topic",
        action="store_true",
        help="明示本票不指派主題（略過自動推導未命中時的警告；與 --topic / --new-topic 互斥）",
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
