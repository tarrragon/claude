"""
Ticket track 命令模組

負責追蹤 Ticket 狀態和執行相關操作。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse


def _parse_wave_arg(value: str) -> int:
    """Parse --wave argument, accepting both integer and W{n} format.

    Examples: "2" -> 2, "W2" -> 2, "w28" -> 28
    """
    stripped = value.strip().upper()
    if stripped.startswith('W'):
        return int(stripped[1:])
    return int(value)


def _parse_top_arg(value: str) -> int:
    """Parse --top argument: 非負整數。

    負值或非整數會 raise argparse.ArgumentTypeError（argparse 自動轉 exit 2）。
    """
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("--top must be integer")
    if n < 0:
        raise argparse.ArgumentTypeError("--top must be >= 0")
    return n

from ticket_system.lib.ticket_loader import (
    resolve_version,
    require_version,
)
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id
from ticket_system.lib.messages import (
    ArgparseFormatErrorParser,
    ErrorMessages,
    format_error,
    format_info,
)
from ticket_system.lib.command_tracking_messages import (
    TrackMessages,
)
# 導入生命週期模組
from .lifecycle import (
    execute_claim,
    execute_complete,
    execute_close,
    execute_release,
)
# 導入查詢操作模組
from .track_query import (
    execute_query,
    execute_summary,
    execute_tree,
    execute_chain,
    execute_deps,
    execute_full,
    execute_log,
    execute_list,
    execute_version,
    execute_search,
)
# 導入欄位操作模組
from .fields import (
    execute_get_who,
    execute_set_who,
    execute_get_what,
    execute_set_what,
    execute_get_when,
    execute_set_when,
    execute_get_where,
    execute_set_where,
    execute_get_why,
    execute_set_why,
    execute_get_how,
    execute_set_how,
    execute_set_priority,
    execute_add_acceptance,
    execute_remove_acceptance,
    execute_add_spawned,
    execute_set_decision_tree,
)
# 導入批量操作模組
from .track_batch import (
    execute_batch_claim,
    execute_batch_complete,
)
# 導入驗收條件和執行日誌模組
from .track_acceptance import (
    execute_check_acceptance,
    execute_append_log,
    execute_accept_creation,
)
# 導入 set-acceptance / validate 子命令
from .track_set_acceptance import execute_set_acceptance
from .track_validate import execute_validate
# 導入關係和狀態管理模組
from .track_relations import (
    execute_add_child,
    execute_phase,
    execute_agent,
    execute_set_blocked_by,
    execute_set_related_to,
)
# 導入驗收審核模組
from .track_audit import (
    execute_audit,
)
# 導入看板命令模組
from .track_board import (
    execute_board,
)
# 導入快照命令模組
from .track_agent_status import (
    execute_agent_status,
    register_agent_status,
)
from .track_snapshot import (
    execute_snapshot,
)
from .track_handoff_ready import (
    execute_handoff_ready,
    register_handoff_ready,
)
from .track_checkpoint_status import (
    execute_checkpoint_status,
    register_checkpoint_status,
)
from .track_dispatch_check import (
    execute_dispatch_check,
    register_dispatch_check,
)
# Context Bundle 合理性檢查（W17-003 落地，獨立於 dispatch-check）
from .track_dispatch_validate import (
    execute_dispatch_validate,
    register_dispatch_validate,
)
# 派發前認知負擔閾值檢查（W17-053 落地，獨立於 dispatch-check / dispatch-validate）
from .track_dispatch_readiness import (
    execute_dispatch_readiness,
    register_dispatch_readiness,
)
# parallel-check 子任務衝突偵測（W17-203.1 落地）
from .track_parallel_check import (
    execute_parallel_check,
    register_parallel_check,
)
# 統一 scheduler CLI（W17-011.1 / W17-009 落地）
from .track_runqueue import (
    execute_runqueue,
    register_runqueue,
)
# dashboard 聚合視圖（W10-114 / W10-113 ANA Solution M1+M4'）
from .track_dashboard import (
    execute_dashboard,
    register_dashboard,
)
# stuck-anas 列出卡住的 ANA（W17-008.15 方案 D）
from .track_stuck_anas import (
    execute_stuck_anas,
    register_stuck_anas,
)
# stale-list 列舉 stale pending ticket 明細（W17-200）
from .track_stale_list import (
    execute_stale_list,
    register_stale_list,
)
# hook-health 掃描 .claude/hook-logs/ 評估觸發頻率（W13-018，源自 W13-008 IMP-3）
from .track_hook_health import (
    execute_hook_health,
    register_hook_health,
)
# td-status 校準 TD 清單（W10-083 / PC-094）
from .track_td_status import (
    execute_td_status,
    register_td_status,
)
# 導入版本審計命令模組
from .audit_version import (
    execute_audit_version,
)


def _execute_claim(args: argparse.Namespace, version: str) -> int:  # type: ignore
    """認領 Ticket（包裝生命週期模組）"""
    return execute_claim(args, version)


def _execute_complete(args: argparse.Namespace, version: str) -> int:
    """標記完成 - 包裝生命週期模組"""
    return execute_complete(args, version)


def _execute_close(args: argparse.Namespace, version: str) -> int:
    """關閉 Ticket（包裝生命週期模組）"""
    return execute_close(args, version)


def _execute_release(args: argparse.Namespace, version: str) -> int:
    """釋放 Ticket（包裝生命週期模組）"""
    return execute_release(args, version)


def _create_version_agnostic_handlers() -> dict:
    """
    建立不需版本資訊的命令處理器字典（W17-014 / W17-008.11 方案 B）

    這些命令操作專案全局狀態（snapshot / agent-status / handoff-ready /
    checkpoint-status / dispatch-check），不對單一 Ticket 操作，因此
    handler 簽名為 `handler(args)`，不接受 version 參數。

    與 `_create_version_aware_handlers()` 形成雙 dict 設計，消除原本
    line 224-236 的 5 命令 if-elif 雙軌；execute() 先查 agnostic 再查 aware。
    """
    return {
        "snapshot": execute_snapshot,
        "agent-status": execute_agent_status,
        "handoff-ready": execute_handoff_ready,
        "checkpoint-status": execute_checkpoint_status,
        "dispatch-check": execute_dispatch_check,
        "stuck-anas": execute_stuck_anas,
        "stale-list": execute_stale_list,
        "parallel-check": execute_parallel_check,
        "hook-health": execute_hook_health,
    }


def _create_command_handlers() -> dict:
    """
    建立 version-aware 命令處理器字典（handler(args, version) 簽名）

    設計目的：
    - 遵循開放封閉原則（OCP）
    - 支援動態註冊新命令
    - 消除 if-elif 鏈

    註：不需版本資訊的全局狀態命令見 `_create_version_agnostic_handlers()`。
    """
    return {
        "summary": execute_summary,
        "query": execute_query,
        "claim": _execute_claim,
        "complete": _execute_complete,
        "close": _execute_close,
        "tree": execute_tree,
        "list": execute_list,
        "search": execute_search,
        "release": _execute_release,
        "chain": execute_chain,
        "deps": execute_deps,
        "full": execute_full,
        # show 為 full 的 alias（W17-008.2 / W17-004 落差 2：對齊 git/docker/kubectl 慣例）
        "show": execute_full,
        "log": execute_log,
        "batch-claim": execute_batch_claim,
        "batch-complete": execute_batch_complete,
        "set-who": execute_set_who,
        "set-what": execute_set_what,
        "set-when": execute_set_when,
        "set-where": execute_set_where,
        "set-why": execute_set_why,
        "set-how": execute_set_how,
        "who": execute_get_who,
        "what": execute_get_what,
        "when": execute_get_when,
        "where": execute_get_where,
        "why": execute_get_why,
        "how": execute_get_how,
        "agent": execute_agent,
        "phase": execute_phase,
        "check-acceptance": execute_check_acceptance,
        "set-acceptance": execute_set_acceptance,
        "validate": execute_validate,
        "append-log": execute_append_log,
        "accept-creation": execute_accept_creation,
        "add-child": execute_add_child,
        "set-blocked-by": execute_set_blocked_by,
        "set-related-to": execute_set_related_to,
        "set-priority": execute_set_priority,
        "add-acceptance": execute_add_acceptance,
        "remove-acceptance": execute_remove_acceptance,
        "add-spawned": execute_add_spawned,
        "set-decision-tree": execute_set_decision_tree,
        "audit": execute_audit,
        "audit-version": execute_audit_version,
        "board": execute_board,
        # W17-011.1 / W17-009 統一 scheduler CLI
        "runqueue": execute_runqueue,
        # W10-114 聚合 dashboard 視圖（in_progress + top N ready + stale）
        "dashboard": execute_dashboard,
        # W10-083 / PC-094 TD 清單校準
        "td-status": execute_td_status,
        # W17-003 Context Bundle 合理性檢查（version-aware：需讀取 ticket md）
        "dispatch-validate": execute_dispatch_validate,
        # W17-053 派發前認知負擔閾值檢查（version-aware：需讀取 ticket md）
        "dispatch-readiness": execute_dispatch_readiness,
    }


def execute(args: argparse.Namespace) -> int:
    """執行 track 命令"""
    operation = args.operation

    # version 命令特殊處理（簽名為 handler(args, None)，與 agnostic 簽名 handler(args) 不同）
    if operation == "version":
        return execute_version(args, None)

    # version-agnostic 命令優先查找（W17-014 方案 B：雙 dict 消除雙軌）
    agnostic_handlers = _create_version_agnostic_handlers()
    if operation in agnostic_handlers:
        return agnostic_handlers[operation](args)

    # 其他命令需要版本資訊
    # 優先級：
    # 1. 使用 --version 明確指定的版本
    # 2. 從 Ticket ID 中提取版本（針對 query、set-*、tree、chain、full、log 等需要 ticket_id 的命令）
    # 3. 自動偵測當前活躍版本

    explicit_version = getattr(args, 'version', None)
    version = None

    # --version all 特殊處理：跨版本查詢（W9-002）
    if explicit_version and explicit_version.lower() == "all":
        if operation in ("list", "search"):
            all_handlers = _create_command_handlers()
            return all_handlers[operation](args, "all")
        else:
            print(format_error("--version all 僅支援 list 和 search 命令"))
            return 1

    # 如果未明確指定版本，嘗試從 Ticket ID 提取
    if not explicit_version and hasattr(args, 'ticket_id'):
        extracted_version = extract_version_from_ticket_id(args.ticket_id)
        if extracted_version:
            version = extracted_version

    # 如果仍未取得版本，使用自動偵測
    if not version:
        try:
            version = require_version(explicit_version)
        except ValueError:
            print(format_error(ErrorMessages.VERSION_NOT_DETECTED))
            return 1

    # 從命令處理器字典查找對應的處理函式
    handlers = _create_command_handlers()
    if operation not in handlers:
        print(format_error(ErrorMessages.INVALID_OPERATION, operation=operation))
        return 1

    handler = handlers[operation]
    return handler(args, version)


def _register_lifecycle_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊生命週期相關子命令：claim, complete, release"""
    # claim 操作
    p_claim = subparsers.add_parser("claim", help=TrackMessages.HELP_CLAIM)
    p_claim.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_claim.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_claim.add_argument(
        "--skip-verify",
        dest="skip_verify",
        action="store_true",
        help="跳過 AC 自動驗證（逃生閥），直接進入既有 claim 流程",
    )
    p_claim.add_argument(
        "--yes",
        "-y",
        dest="yes",
        action="store_true",
        help="非互動模式：AC 驗證仍執行，但自動選 y 繼續 claim",
    )
    p_claim.add_argument(
        "--quiet",
        dest="quiet",
        action="store_true",
        help="Context Bundle 抽取摘要單行輸出（W17-002.2）",
    )
    p_claim.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Context Bundle 抽取摘要附欄位預覽（W17-002.2）",
    )
    p_claim.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Context Bundle 抽取結果以 JSON 結構化輸出（W17-002.1）",
    )

    # complete 操作
    p_complete = subparsers.add_parser("complete", help=TrackMessages.HELP_COMPLETE)
    p_complete.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_complete.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_complete.add_argument(
        "--yes-spawned",
        dest="yes_spawned",
        action="store_true",
        help="ANA 有 spawned 非 terminal 時旁路 blocking confirmation（非互動環境必需）",
    )
    p_complete.add_argument(
        "--skip-body-check",
        dest="skip_body_check",
        action="store_true",
        help="逃生閥：跳過 type-aware body schema 必填章節驗證（W17-016.3；需於 Completion Info 附理由）",
    )
    p_complete.add_argument(
        "--force",
        dest="force",
        action="store_true",
        help="逃生閥：父 ticket 有未完成 children 時旁路阻擋強制完成（W11-003.2；會輸出警告）",
    )
    p_complete.add_argument(
        "--no-stage",
        dest="no_stage",
        action="store_true",
        help="跳過 complete 後自動 git add metadata 檔案（W11-035 方案 D opt-out）",
    )

    # close 操作（W15-027 / PC-090：--reason 枚舉必填）
    from ticket_system.constants import CLOSE_REASONS, CLOSE_REASON_RETROSPECTIVE_UNKNOWN
    _close_reason_choices = sorted(CLOSE_REASONS) + [CLOSE_REASON_RETROSPECTIVE_UNKNOWN]
    p_close = subparsers.add_parser("close", help="關閉 Ticket（已在其他 Ticket 一併解決）")
    p_close.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_close.add_argument("--resolved-by", required=True, dest="resolved_by",
                         help="解決此問題的 Ticket ID")
    p_close.add_argument(
        "--reason",
        required=True,
        choices=_close_reason_choices,
        help=(
            "close_reason 枚舉（PC-090 C1 必填）。合法值："
            f"{sorted(CLOSE_REASONS)}；--retrospective 模式額外允許 "
            f"'{CLOSE_REASON_RETROSPECTIVE_UNKNOWN}'"
        ),
    )
    p_close.add_argument("--reason-note", dest="reason_note", default="",
                         help="關閉原因補充說明（選填）")
    p_close.add_argument("--retrospective", action="store_true",
                         help="回顧式補填模式，允許 --reason unknown（PC-090 C4）")
    p_close.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # release 操作
    p_release = subparsers.add_parser("release", help=TrackMessages.HELP_RELEASE)
    p_release.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_release.add_argument("--version", help=TrackMessages.ARG_VERSION)


def _register_query_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊查詢相關子命令：summary, query, tree, list, chain, full, log, version"""
    # summary 操作
    p_summary = subparsers.add_parser("summary", help=TrackMessages.HELP_SUMMARY)
    p_summary.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # query 操作
    p_query = subparsers.add_parser("query", help=TrackMessages.HELP_QUERY)
    p_query.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_query.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # tree 操作
    p_tree = subparsers.add_parser("tree", help=TrackMessages.HELP_TREE)
    p_tree.add_argument("ticket_id", help=TrackMessages.ARG_ROOT_TICKET_ID)
    p_tree.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # list 操作
    p_list = subparsers.add_parser("list", help=TrackMessages.HELP_LIST)
    p_list.add_argument("--pending", action="store_true", help=TrackMessages.ARG_PENDING)
    p_list.add_argument("--in-progress", action="store_true", help=TrackMessages.ARG_IN_PROGRESS)
    p_list.add_argument("--completed", action="store_true", help=TrackMessages.ARG_COMPLETED)
    p_list.add_argument("--blocked", action="store_true", help=TrackMessages.ARG_BLOCKED)
    p_list.add_argument("--wave", type=_parse_wave_arg, help=TrackMessages.ARG_WAVE)
    p_list.add_argument("--status", nargs='+', help=TrackMessages.ARG_STATUS)
    p_list.add_argument("--format", choices=["table", "ids", "yaml"], default="table", help=TrackMessages.ARG_FORMAT)
    p_list.add_argument("--version", help=TrackMessages.ARG_VERSION)
    # W10-115: 預設限制 top 10 + priority 排序，--all 取得全量
    p_list.add_argument(
        "--top",
        type=_parse_top_arg,
        default=None,
        help="限制輸出最多 N 筆（預設 10），依 priority(P0>P1>P2>P3) → created → id 排序",
    )
    p_list.add_argument(
        "--all",
        dest="list_all",
        action="store_true",
        help="取得全量輸出（覆蓋 --top；與 --top 共存時 --all 優先並 emit warning）",
    )

    # search 操作（W9-002: 跨維度查詢）
    p_search = subparsers.add_parser("search", help="搜尋 Tickets（依 UC/Spec/Prop 引用或檔案路徑）")
    p_search.add_argument("--ref", help="搜尋引用特定 UC/Spec/Prop 的 Tickets（如 UC-01、SPEC-001、PROP-007）")
    p_search.add_argument("--file", dest="file_path", help="搜尋修改特定檔案的 Tickets（如 src/core/errors/）")
    p_search.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_search.add_argument("--format", choices=["table", "ids", "yaml"], default="table", help=TrackMessages.ARG_FORMAT)

    # chain 操作
    p_chain = subparsers.add_parser("chain", help=TrackMessages.HELP_CHAIN)
    p_chain.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_chain.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # deps 操作：顯示衍生關係（spawned_tickets + source_ticket）
    p_deps = subparsers.add_parser(
        "deps",
        help="顯示 Ticket 衍生關係（spawned_tickets + source_ticket，與 tree/chain 血緣分離）",
    )
    p_deps.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_deps.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # full 操作
    p_full = subparsers.add_parser("full", help=TrackMessages.HELP_FULL)
    p_full.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_full.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # show 操作（W17-008.2 / W17-004 落差 2：full 的 alias，對齊 git/docker/kubectl 慣例）
    p_show = subparsers.add_parser(
        "show",
        help=f"{TrackMessages.HELP_FULL}（full 的 alias，對齊 git/docker/kubectl 慣例）",
    )
    p_show.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_show.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # log 操作
    p_log = subparsers.add_parser("log", help=TrackMessages.HELP_LOG)
    p_log.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_log.add_argument("--version", help=TrackMessages.ARG_VERSION)
    # W17-008.3: --section 過濾，對齊 append-log 介面對稱性
    p_log.add_argument("--section", help=TrackMessages.ARG_SECTION, default=None)

    # version 操作
    p_version = subparsers.add_parser("version", help=TrackMessages.HELP_VERSION)
    p_version.add_argument("version_str", help=TrackMessages.ARG_VERSION_STR)


def _register_field_read_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊欄位讀取子命令：who, what, when, where, why, how"""
    # who 操作 (READ)
    p_who = subparsers.add_parser("who", help=TrackMessages.HELP_WHO)
    p_who.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_who.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # what 操作 (READ)
    p_what = subparsers.add_parser("what", help=TrackMessages.HELP_WHAT)
    p_what.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_what.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # when 操作 (READ)
    p_when = subparsers.add_parser("when", help=TrackMessages.HELP_WHEN)
    p_when.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_when.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # where 操作 (READ)
    p_where = subparsers.add_parser("where", help=TrackMessages.HELP_WHERE)
    p_where.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_where.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # why 操作 (READ)
    p_why = subparsers.add_parser("why", help=TrackMessages.HELP_WHY)
    p_why.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_why.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # how 操作 (READ)
    p_how = subparsers.add_parser("how", help=TrackMessages.HELP_HOW)
    p_how.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_how.add_argument("--version", help=TrackMessages.ARG_VERSION)


def _register_field_write_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊欄位寫入子命令：set-who, set-what, set-when, set-where, set-why, set-how"""
    # set-who 操作
    p_set_who = subparsers.add_parser("set-who", help=TrackMessages.HELP_SET_WHO)
    p_set_who.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_who.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_who.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-what 操作
    p_set_what = subparsers.add_parser("set-what", help=TrackMessages.HELP_SET_WHAT)
    p_set_what.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_what.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_what.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-when 操作
    p_set_when = subparsers.add_parser("set-when", help=TrackMessages.HELP_SET_WHEN)
    p_set_when.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_when.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_when.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-where 操作
    p_set_where = subparsers.add_parser("set-where", help=TrackMessages.HELP_SET_WHERE)
    p_set_where.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_where.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_where.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-why 操作
    p_set_why = subparsers.add_parser("set-why", help=TrackMessages.HELP_SET_WHY)
    p_set_why.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_why.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_why.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-how 操作
    p_set_how = subparsers.add_parser("set-how", help=TrackMessages.HELP_SET_HOW)
    p_set_how.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_how.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_how.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-priority 操作
    p_set_priority = subparsers.add_parser("set-priority", help=TrackMessages.HELP_SET_PRIORITY)
    p_set_priority.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_priority.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_priority.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # add-acceptance 操作
    p_add_acc = subparsers.add_parser("add-acceptance", help=TrackMessages.HELP_ADD_ACCEPTANCE)
    p_add_acc.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_add_acc.add_argument("value", help="驗收條件文字")
    p_add_acc.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # remove-acceptance 操作
    p_rm_acc = subparsers.add_parser("remove-acceptance", help=TrackMessages.HELP_REMOVE_ACCEPTANCE)
    p_rm_acc.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_rm_acc.add_argument("index", type=int, help="要移除的驗收條件編號（從 1 開始）")
    p_rm_acc.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # add-spawned 操作
    p_add_spawned = subparsers.add_parser("add-spawned", help=TrackMessages.HELP_ADD_SPAWNED)
    p_add_spawned.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_add_spawned.add_argument("value", nargs="+", help="Spawned Ticket ID（可一次傳多個，對齊 Unix 慣例如 rm a b c）")
    p_add_spawned.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-decision-tree 操作
    p_set_dt = subparsers.add_parser("set-decision-tree", help=TrackMessages.HELP_SET_DECISION_TREE)
    p_set_dt.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_dt.add_argument("--entry", help="entry_point 欄位值")
    p_set_dt.add_argument("--decision", help="final_decision 欄位值")
    p_set_dt.add_argument("--rationale", help="rationale 欄位值")
    p_set_dt.add_argument("--version", help=TrackMessages.ARG_VERSION)


def _register_batch_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊批量操作子命令：batch-claim, batch-complete"""
    # batch-claim 操作
    p_batch_claim = subparsers.add_parser("batch-claim", help=TrackMessages.HELP_BATCH_CLAIM)
    p_batch_claim.add_argument("ticket_ids", help=TrackMessages.ARG_TICKET_IDS)
    p_batch_claim.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # batch-complete 操作
    p_batch_complete = subparsers.add_parser("batch-complete", help=TrackMessages.HELP_BATCH_COMPLETE)
    p_batch_complete.add_argument("ticket_ids", nargs="?", default="", help=TrackMessages.ARG_TICKET_IDS)
    p_batch_complete.add_argument("--wave", type=_parse_wave_arg, help="完成指定 Wave 的所有 in_progress Ticket")
    p_batch_complete.add_argument("--parent", help="完成指定父任務的所有子任務")
    p_batch_complete.add_argument("--status", default="in_progress", help="與 --wave 搭配使用，篩選特定狀態")
    p_batch_complete.add_argument("--dry-run", action="store_true", help="模擬執行，只顯示清單不實際執行")
    p_batch_complete.add_argument("--version", help=TrackMessages.ARG_VERSION)


def _register_relation_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊關係和狀態管理子命令：agent, phase, add-child, set-blocked-by, set-related-to"""
    # agent 操作
    p_agent = subparsers.add_parser("agent", help=TrackMessages.HELP_AGENT)
    p_agent.add_argument("agent_name", help=TrackMessages.ARG_AGENT_NAME)
    p_agent.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # phase 操作
    p_phase = subparsers.add_parser(
        "phase",
        help=TrackMessages.HELP_PHASE,
        epilog=(
            "範例:\n"
            "  ticket track phase 0.2.0-W3-001 phase1 lavender-interface-designer\n"
            "  ticket track phase 0.2.0-W3-001 phase3b parsley-flutter-developer\n"
            "\n"
            "Phase 支援簡寫: phase0, phase1, phase2, phase3a, phase3b, phase4"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_phase.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_phase.add_argument("phase", help=TrackMessages.ARG_PHASE)
    p_phase.add_argument("agent", help=TrackMessages.ARG_AGENT)
    p_phase.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # add-child 操作
    p_add_child = subparsers.add_parser(
        "add-child",
        help=TrackMessages.HELP_ADD_CHILD
    )
    p_add_child.add_argument("parent_id", help=TrackMessages.ARG_PARENT_ID)
    p_add_child.add_argument("child_id", help=TrackMessages.ARG_CHILD_ID)
    p_add_child.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-blocked-by 操作
    p_set_blocked_by = subparsers.add_parser(
        "set-blocked-by",
        help="設定 Ticket 的 blockedBy 欄位（阻塞依賴）"
    )
    p_set_blocked_by.add_argument("ticket_id", help="目標 Ticket ID")
    p_set_blocked_by.add_argument("value", help="被引用的 Ticket ID（空格分隔）")
    p_set_blocked_by.add_argument("--add", action="store_true", help="追加模式（去重）")
    p_set_blocked_by.add_argument("--remove", action="store_true", help="移除模式")
    p_set_blocked_by.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-related-to 操作
    p_set_related_to = subparsers.add_parser(
        "set-related-to",
        help="設定 Ticket 的 relatedTo 欄位（相關任務）"
    )
    p_set_related_to.add_argument("ticket_id", help="目標 Ticket ID")
    p_set_related_to.add_argument("value", help="相關的 Ticket ID（空格分隔）")
    p_set_related_to.add_argument("--add", action="store_true", help="追加模式（去重）")
    p_set_related_to.add_argument("--remove", action="store_true", help="移除模式")
    p_set_related_to.add_argument("--version", help=TrackMessages.ARG_VERSION)


def _register_acceptance_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊驗收條件和執行日誌子命令：check-acceptance, append-log, accept-creation, audit"""
    # check-acceptance 操作
    p_check_acceptance = subparsers.add_parser(
        "check-acceptance",
        help=TrackMessages.HELP_CHECK_ACCEPTANCE
    )
    p_check_acceptance.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_check_acceptance.add_argument("index", nargs="?", default=None, help=TrackMessages.ARG_INDEX)
    p_check_acceptance.add_argument(
        "--uncheck",
        action="store_true",
        help=TrackMessages.ARG_UNCHECK
    )
    p_check_acceptance.add_argument(
        "--all",
        action="store_true",
        help=TrackMessages.ARG_CHECK_ACCEPTANCE_ALL
    )
    p_check_acceptance.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-acceptance 操作
    p_set_acceptance = subparsers.add_parser(
        "set-acceptance",
        help="勾選/取消勾選驗收條件（--check/--uncheck 支援多 index，--all-check/--all-uncheck 批量）"
    )
    p_set_acceptance.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_acceptance.add_argument(
        "--check", nargs="+", metavar="INDEX",
        help="勾選指定 1-based index（可多個，空白分隔）"
    )
    p_set_acceptance.add_argument(
        "--uncheck", nargs="+", metavar="INDEX",
        help="取消勾選指定 1-based index（可多個）"
    )
    p_set_acceptance.add_argument(
        "--all-check", dest="all_check", action="store_true",
        help="勾選全部驗收條件"
    )
    p_set_acceptance.add_argument(
        "--all-uncheck", dest="all_uncheck", action="store_true",
        help="取消勾選全部驗收條件"
    )
    p_set_acceptance.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # validate 操作
    p_validate = subparsers.add_parser(
        "validate",
        help="驗證 Ticket frontmatter 4 欄位（status/completed_at/acceptance/who）合規性"
    )
    p_validate.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_validate.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # append-log 操作
    p_append_log = subparsers.add_parser(
        "append-log",
        help=TrackMessages.HELP_APPEND_LOG
    )
    p_append_log.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_append_log.add_argument(
        "--section",
        required=True,
        help=TrackMessages.ARG_SECTION
    )
    p_append_log.add_argument("content", help=TrackMessages.ARG_CONTENT)
    p_append_log.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # accept-creation 操作
    p_accept_creation = subparsers.add_parser(
        "accept-creation",
        help=TrackMessages.HELP_ACCEPT_CREATION
    )
    p_accept_creation.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_accept_creation.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # audit 操作
    p_audit = subparsers.add_parser(
        "audit",
        help=TrackMessages.HELP_AUDIT
    )
    p_audit.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_audit.add_argument("--version", help=TrackMessages.ARG_VERSION)




def _register_version_audit_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊版本審計命令：audit-version"""
    # audit-version 操作
    p_audit_version = subparsers.add_parser(
        "audit-version",
        help="掃描並驗證 Ticket 版本歸屬一致性"
    )
    p_audit_version.add_argument(
        "--fix",
        action="store_true",
        help="自動修復發現的版本不一致問題"
    )
    p_audit_version.add_argument(
        "--version",
        dest="audit_version",
        help="只檢查指定版本的 Tickets（如 0.1.0）"
    )


def _register_board_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊看板命令：board"""
    # board 操作
    p_board = subparsers.add_parser("board", help=TrackMessages.HELP_BOARD)
    p_board.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_board.add_argument(
        "--wave",
        help=TrackMessages.ARG_WAVE
    )
    p_board.add_argument(
        "--all",
        action="store_true",
        help=TrackMessages.ARG_ALL
    )


def _register_all_subcommands(
    track_subparsers: argparse._SubParsersAction,
) -> None:
    """統一註冊所有子命令組"""
    _register_lifecycle_commands(track_subparsers)
    _register_query_commands(track_subparsers)
    _register_field_read_commands(track_subparsers)
    _register_field_write_commands(track_subparsers)
    _register_batch_commands(track_subparsers)
    _register_relation_commands(track_subparsers)
    _register_acceptance_commands(track_subparsers)
    _register_version_audit_commands(track_subparsers)
    _register_board_commands(track_subparsers)
    _register_global_state_commands(track_subparsers)
    register_runqueue(track_subparsers)
    register_dashboard(track_subparsers)
    register_stuck_anas(track_subparsers)
    register_stale_list(track_subparsers)
    register_td_status(track_subparsers)
    register_hook_health(track_subparsers)
    register_dispatch_validate(track_subparsers)
    register_dispatch_readiness(track_subparsers)


def _register_global_state_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊 version-agnostic 全局狀態命令（W17-014 方案 B 群組化）

    對應 `_create_version_agnostic_handlers()` 的 5 個命令：
    snapshot / agent-status / handoff-ready / checkpoint-status / dispatch-check
    """
    _register_snapshot_commands(subparsers)
    register_agent_status(subparsers)
    register_handoff_ready(subparsers)
    register_checkpoint_status(subparsers)
    register_dispatch_check(subparsers)
    register_parallel_check(subparsers)


def _register_snapshot_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """註冊快照命令：snapshot"""
    subparsers.add_parser("snapshot", help="產出專案全局狀態快照")


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 track 子命令及所有操作

    W17-008.5.4：track parser 與所有操作子 parser 套用 ArgparseFormatErrorParser，
    讓業務錯誤（invalid choice / invalid type value）改走 format_error 結構化路徑；
    純語法錯誤（unrecognized args / missing required positional）保留 argparse 預設。
    """
    parser = subparsers.add_parser("track", help=TrackMessages.HELP_TRACK)
    # 範圍邊界：scripts/ticket.py 的頂層 parser 不在本 ticket 範圍，
    # 故 track 本身為預設 ArgumentParser；這裡綁定 error() 將業務錯誤改走客製路徑。
    parser.error = ArgparseFormatErrorParser.error.__get__(parser, type(parser))  # type: ignore[method-assign]

    # 建立子操作解析器（parser_class 讓所有 operation subparser 繼承業務錯誤客製）
    track_subparsers = parser.add_subparsers(
        dest="operation",
        required=True,
        help="操作類型",
        parser_class=ArgparseFormatErrorParser,
    )

    # 按功能分組註冊所有子命令
    _register_all_subcommands(track_subparsers)

    parser.set_defaults(func=execute)

