"""
Ticket track 命令模組

負責追蹤 Ticket 狀態和執行相關操作。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
from typing import Optional

from ticket_system.lib.ticket_loader import (
    resolve_version,
    require_version,
)
from ticket_system.lib.messages import (
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
    execute_release,
)
# 導入查詢操作模組
from .track_query import (
    execute_query,
    execute_summary,
    execute_tree,
    execute_chain,
    execute_full,
    execute_log,
    execute_list,
    execute_version,
)
# 導入欄位操作模組
from .fields import (
    execute_get_field,
    execute_set_field,
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


def _execute_claim(args: argparse.Namespace, version: str) -> int:  # type: ignore
    """認領 Ticket（包裝生命週期模組）"""
    return execute_claim(args, version)


def _execute_complete(args: argparse.Namespace, version: str) -> int:
    """標記完成 - 包裝生命週期模組"""
    return execute_complete(args, version)


def _execute_release(args: argparse.Namespace, version: str) -> int:
    """釋放 Ticket（包裝生命週期模組）"""
    return execute_release(args, version)


def _create_command_handlers() -> dict:
    """
    建立命令處理器字典

    設計目的：
    - 遵循開放封閉原則（OCP）
    - 支援動態註冊新命令
    - 消除 if-elif 鏈
    """
    return {
        "summary": execute_summary,
        "query": execute_query,
        "claim": _execute_claim,
        "complete": _execute_complete,
        "tree": execute_tree,
        "list": execute_list,
        "release": _execute_release,
        "chain": execute_chain,
        "full": execute_full,
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
        "append-log": execute_append_log,
        "accept-creation": execute_accept_creation,
        "add-child": execute_add_child,
        "set-blocked-by": execute_set_blocked_by,
        "set-related-to": execute_set_related_to,
        "audit": execute_audit,
        "board": execute_board,
    }


def execute(args: argparse.Namespace) -> int:
    """執行 track 命令"""
    operation = args.operation

    # version 命令特殊處理（不需要版本資訊）
    if operation == "version":
        return execute_version(args, None)

    # 其他命令需要版本資訊（使用共用 API）
    try:
        version = require_version(getattr(args, 'version', None))
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

    # complete 操作
    p_complete = subparsers.add_parser("complete", help=TrackMessages.HELP_COMPLETE)
    p_complete.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_complete.add_argument("--version", help=TrackMessages.ARG_VERSION)

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
    p_list.add_argument("--wave", type=int, help=TrackMessages.ARG_WAVE)
    p_list.add_argument("--status", choices=["pending", "in_progress", "completed", "blocked"], help=TrackMessages.ARG_STATUS)
    p_list.add_argument("--format", choices=["table", "ids", "yaml"], default="table", help=TrackMessages.ARG_FORMAT)
    p_list.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # chain 操作
    p_chain = subparsers.add_parser("chain", help=TrackMessages.HELP_CHAIN)
    p_chain.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_chain.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # full 操作
    p_full = subparsers.add_parser("full", help=TrackMessages.HELP_FULL)
    p_full.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_full.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # log 操作
    p_log = subparsers.add_parser("log", help=TrackMessages.HELP_LOG)
    p_log.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_log.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # version 操作
    p_version = subparsers.add_parser("version", help=TrackMessages.HELP_VERSION)
    p_version.add_argument("version_str", help=TrackMessages.ARG_VERSION_STR)
    p_version.add_argument("--version", dest="version_param", help=TrackMessages.ARG_VERSION_PARAM)


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
    p_batch_complete.add_argument("--wave", type=int, help="完成指定 Wave 的所有 in_progress Ticket")
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
    p_phase = subparsers.add_parser("phase", help=TrackMessages.HELP_PHASE)
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
    p_check_acceptance.add_argument("index", help=TrackMessages.ARG_INDEX)
    p_check_acceptance.add_argument(
        "--uncheck",
        action="store_true",
        help=TrackMessages.ARG_UNCHECK
    )
    p_check_acceptance.add_argument("--version", help=TrackMessages.ARG_VERSION)

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
    _register_board_commands(track_subparsers)


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 track 子命令及所有操作"""
    parser = subparsers.add_parser("track", help=TrackMessages.HELP_TRACK)

    # 建立子操作解析器
    track_subparsers = parser.add_subparsers(
        dest="operation", required=True, help="操作類型"
    )

    # 按功能分組註冊所有子命令
    _register_all_subcommands(track_subparsers)

    parser.set_defaults(func=execute)


