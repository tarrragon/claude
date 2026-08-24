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

from ticket_system.constants import PRIORITY_LEVELS
from ticket_system.lib.ticket_loader import (
    resolve_version,
    require_version,
)
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id
from ticket_system.lib.ambiguous_prefix import register_ambiguous_prefix
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
    execute_get_title,
    execute_set_title,
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
    execute_add_spawn_request,
    execute_resolve_spawn_request,
)
# 導入 dispatch 子命令（派發即落票：--note 落票 + normal/review 骨架輸出）
from .track_dispatch import execute_dispatch, register_dispatch_command
from .track_commit import execute_commit, register_commit_command
# 導入 PC-093-exempt marker 補標記子命令
from .track_exempt_marker import execute_add_exempt_marker
from .track_multi_view_status import execute_fix_multi_view_status
# 導入實驗器材登記子命令（跨 session 實驗器材票面登記 CLI 化）
from .track_artifacts import (
    execute_register_artifact,
    execute_resolve_artifact,
    execute_list_artifacts,
)
# 導入 set-acceptance / validate 子命令
from .track_set_acceptance import execute_set_acceptance
# 導入 set-closed-by 子命令（closed 票 frontmatter 欄位修正路徑）
from .track_set_closed_by import execute_set_closed_by
# 導入 set-exit-status / set-completion-info 子命令（1.5.0-W5-021 制式化內容生成）
from .track_structured_body import (
    execute_set_exit_status,
    execute_set_completion_info,
)
from .track_validate import execute_validate
# 導入關係和狀態管理模組
from .track_relations import (
    execute_add_child,
    execute_set_parent,
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
    GROUP_BY_WAVE,
    GROUP_BY_TOPIC,
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
# 嵌套深度查詢（W1-056.8 落地，協議 v2 D3 層級自覺）
from .track_depth import (
    execute_depth,
    register_depth,
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
# hook-liveness 從 hook 檔/名稱解析 HOOK_NAME 後查 _liveness 觸發記錄
from .track_hook_liveness import (
    execute_hook_liveness,
    register_hook_liveness,
)
# td-status 校準 TD 清單（W10-083 / PC-094）
from .track_td_status import (
    execute_td_status,
    register_td_status,
)
# sessions 列出同專案 pm-registry session 清單（multi-PM 協調層 Phase 1）
from .track_sessions import (
    execute_sessions,
    register_sessions,
)
# activity 機械推導 in_progress 票 L1 新鮮度（multi-PM 協調層 Phase 2）
from .track_activity import (
    execute_activity,
    register_activity,
)
# conflicts 偵測 where.files 交集 + impl->test 擴張啟發式（multi-PM 協調層 Phase 2）
from .track_conflicts import (
    execute_conflicts,
    register_conflicts,
)
# onboard PM 入場四節彙整（multi-PM 協調層 Phase 2）
from .track_onboard import (
    execute_onboard,
    register_onboard,
)
# topics/topic 主題清單視圖與單一主題任務鏈 map（唯讀視圖層）
from .track_topics import (
    execute_topics,
    execute_topic,
    register_topics,
)
# topic-backfill-list/topic-backfill-assign 既有 pending 票的主題分批回填 CLI 入口
from .topic_backfill import (
    execute_topic_backfill_list,
    execute_topic_backfill_assign,
    register as register_topic_backfill,
)
# lease claim/release 寫入 + reclaim ghost 鑑識（multi-PM 協調層 Phase 3）
from ticket_system.lib.lease import (
    ReleaseGuardReason,
    check_release_guard,
    claim_lease,
    reclaim_ticket,
    release_lease,
)
# 導入版本審計命令模組
from .audit_version import (
    execute_audit_version,
)


def _execute_claim(args: argparse.Namespace, version: str) -> int:  # type: ignore
    """認領 Ticket（包裝生命週期模組）

    claim 成功後併同寫入 registry lease（multi-PM 協調層 Phase 3）：附加
    動作失敗不影響已成功的 claim，見 `claim_lease` 降級語意。
    """
    rc = execute_claim(args, version)
    if rc == 0:
        claim_lease(version, args.ticket_id)
    return rc


def _execute_complete(args: argparse.Namespace, version: str) -> int:
    """標記完成 - 包裝生命週期模組（亦作為 finish 別名的共用 handler）。

    complete 與 finish 兩個子命令名共用本函式：finish 是 complete 的別名
    （worktree 派發避開 CC runtime worktree isolation guard 對 argv 逐元素
    basename 誤判 bash builtin `complete`），行為完全等價，不是各自獨立實作。

    complete 成功後併同移除 registry lease（multi-PM 協調層 Phase 3，與
    claim 對稱）。
    """
    # W1-048: --as 身份申報對照（純前置檢查，deny 不寫入任何狀態）
    # W1-083: 傳入 command 名稱，使 telemetry 可做 per-command 歸因；
    # 取 args.operation（argparse 實際解析到的子命令名，如 finish）而非寫死
    # "complete"，使別名呼叫的 telemetry 歸因準確，不與原名混記
    from ticket_system.lib.identity_guard import check_identity
    deny = check_identity(
        version,
        args.ticket_id,
        getattr(args, "as_agent", None),
        command=getattr(args, "operation", "complete"),
    )
    if deny is not None:
        return deny
    rc = execute_complete(args, version)
    if rc == 0:
        release_lease(version, args.ticket_id)
    return rc


def _execute_close(args: argparse.Namespace, version: str) -> int:
    """關閉 Ticket（包裝生命週期模組）"""
    return execute_close(args, version)


def _execute_release(args: argparse.Namespace, version: str) -> int:
    """釋放 Ticket（包裝生命週期模組）

    前置閘門：ticket 由「非自身」FRESH session 持有時需顯式
    `--force-release-others` 才能繼續，防止並行 PM 誤操作清除他人存活
    session 的 lease、繞過 reclaim 三道防線（Phase 4 High 發現）。自身
    持有或 registry 未追蹤此票（無 lease 記錄）時行為與旁路前完全一致
    （`check_release_guard` fail-open 降級語意）。

    release 成功後併同移除 registry lease（multi-PM 協調層 Phase 3，與
    claim 對稱）。
    """
    if not bool(getattr(args, "force_release_others", False)):
        allowed, reason_code, reason = check_release_guard(args.ticket_id)
        if not allowed:
            print(f"[Warning] {reason}")
            return 1
        if reason_code is ReleaseGuardReason.NO_LEASE_TRACKED:
            # owner is None：registry 從未記錄此票的 lease（常見於 graceful
            # SessionEnd 遺留票）。release 只是把票放回 pending 池
            # （lifecycle.py 清 assigned/started_at），不是接管；真實風險是
            # PM 未察覺前一個 session 留下未合併分支或髒檔就把票放回池中。
            # 不阻擋、不改變 exit code，僅提示可查途徑。
            print(
                f"[INFO] {args.ticket_id}: 此票無 lease 記錄（owner is None），"
                "release 前可考慮改用 `ticket track reclaim` 的 dry-run 模式"
                "（不加 --confirm）先跑 ghost 鑑識，檢查是否有未合併分支或"
                "未提交的髒檔殘留。"
            )

    rc = execute_release(args, version)
    if rc == 0:
        release_lease(version, args.ticket_id)
    return rc


def _execute_reclaim(args: argparse.Namespace, version: str) -> int:
    """`ticket track reclaim`：僅接受 reclaimable 票，強制 ghost 鑑識三查，
    預設 dry-run；`--confirm` 且三查全過才轉回 pending 並清 registry lease
    （multi-PM 協調層 Phase 3，包裝 `ticket_system.lib.lease.reclaim_ticket`）。
    """
    return reclaim_ticket(version, args.ticket_id, confirm=bool(getattr(args, "confirm", False)))


def _execute_verify(args: argparse.Namespace, version: str) -> int:
    """單獨執行 AC 驗證（W4-019：與 claim 解耦）。"""
    from .lifecycle import TicketLifecycle
    lifecycle = TicketLifecycle(version)
    return lifecycle.verify_only(args.ticket_id)


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
        "hook-liveness": execute_hook_liveness,
        "sessions": execute_sessions,
        "activity": execute_activity,
        "conflicts": execute_conflicts,
        "onboard": execute_onboard,
        "topics": execute_topics,
        "topic": execute_topic,
        "topic-backfill-list": execute_topic_backfill_list,
        "topic-backfill-assign": execute_topic_backfill_assign,
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
        # W1-056.8 嵌套深度查詢（協議 v2 D3）
        "depth": execute_depth,
        "claim": _execute_claim,
        "complete": _execute_complete,
        # finish 為 complete 的別名（避開 CC runtime worktree guard 對
        # bash builtin 'complete' 的 basename 誤判），共用同一 handler
        "finish": _execute_complete,
        "close": _execute_close,
        "tree": execute_tree,
        "list": execute_list,
        "search": execute_search,
        "release": _execute_release,
        # multi-PM 協調層 Phase 3：僅接受 reclaimable 票，強制 ghost 鑑識三查
        "reclaim": _execute_reclaim,
        # W4-019: 拆 verify 子命令（單獨執行 AC 驗證，與 claim 解耦）
        "verify": _execute_verify,
        "chain": execute_chain,
        "deps": execute_deps,
        "full": execute_full,
        # show 為 full 的 alias（W17-008.2 / W17-004 落差 2：對齊 git/docker/kubectl 慣例）
        "show": execute_full,
        "log": execute_log,
        "batch-claim": execute_batch_claim,
        "batch-complete": execute_batch_complete,
        "set-who": execute_set_who,
        "set-title": execute_set_title,
        "set-what": execute_set_what,
        "set-when": execute_set_when,
        "set-where": execute_set_where,
        "set-why": execute_set_why,
        "set-how": execute_set_how,
        "who": execute_get_who,
        "title": execute_get_title,
        "what": execute_get_what,
        "when": execute_get_when,
        "where": execute_get_where,
        "why": execute_get_why,
        "how": execute_get_how,
        "agent": execute_agent,
        "phase": execute_phase,
        "check-acceptance": execute_check_acceptance,
        "set-acceptance": execute_set_acceptance,
        "set-closed-by": execute_set_closed_by,
        "set-exit-status": execute_set_exit_status,
        "set-completion-info": execute_set_completion_info,
        "validate": execute_validate,
        "append-log": execute_append_log,
        "dispatch": execute_dispatch,
        "commit": execute_commit,
        "add-spawn-request": execute_add_spawn_request,
        "resolve-spawn-request": execute_resolve_spawn_request,
        "add-exempt-marker": execute_add_exempt_marker,
        "fix-multi-view-status": execute_fix_multi_view_status,
        "register-artifact": execute_register_artifact,
        "resolve-artifact": execute_resolve_artifact,
        "list-artifacts": execute_list_artifacts,
        "accept-creation": execute_accept_creation,
        "add-child": execute_add_child,
        "set-parent": execute_set_parent,
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
        "--verify",
        dest="verify",
        action="store_true",
        help=(
            "W3-046: 明示啟用 AC 自動驗證（預設關閉，避免 npm test 全套件副作用 / "
            "PC-078 並行衝突）。僅供除錯場景使用"
        ),
    )
    # W4-019: --skip-verify 旗標已移除（W3-092 + W4-015 兩輪觀察期累計
    # 24hr / 75 commits / 5 ticket cycles 驗證：外部依賴 = 0、runtime
    # deprecation 觸發 = 0）。如需單獨執行 AC 驗證（不 claim），改用
    # `ticket track verify <id>`；如需跳過驗證直接 claim，不傳 --verify
    # 即為預設行為（W3-046 後 claim 預設不驗證）。
    p_claim.add_argument(
        "--yes",
        "-y",
        dest="yes",
        action="store_true",
        help="非互動模式：AC 驗證（若以 --verify 啟用）自動選 y 繼續 claim",
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
    p_claim.add_argument(
        "--as",
        dest="as_agent",
        default=None,
        metavar="AGENT_NAME",
        help="認領時申報執行身份，寫入 who.current（與後續 complete --as 對稱，"
        "免 set-who 繞過；--as 與 --verify 正交，W2-018）",
    )

    # complete 操作（與 finish 別名共用旗標定義，見 _add_complete_arguments：
    # 單一事實來源，避免手動同步兩份 add_argument 列表產生行為漂移）
    def _add_complete_arguments(target: argparse.ArgumentParser) -> None:
        target.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
        target.add_argument("--version", help=TrackMessages.ARG_VERSION)
        target.add_argument(
            "--yes-spawned",
            dest="yes_spawned",
            action="store_true",
            help="ANA 有 spawned 非 terminal 時旁路 blocking confirmation（非互動環境必需）",
        )
        target.add_argument(
            "--skip-body-check",
            dest="skip_body_check",
            action="store_true",
            help="逃生閥：跳過 type-aware body schema 必填章節驗證（W17-016.3；需於 Completion Info 附理由）",
        )
        target.add_argument(
            "--force",
            dest="force",
            action="store_true",
            help="逃生閥：父 ticket 有未完成 children 時旁路阻擋強制完成（W11-003.2；會輸出警告）",
        )
        target.add_argument(
            "--no-stage",
            dest="no_stage",
            action="store_true",
            help="跳過 complete 後自動 git add metadata 檔案（W11-035 方案 D opt-out）",
        )
        target.add_argument(
            "--as",
            dest="as_agent",
            default=None,
            metavar="AGENT_NAME",
            help="申報執行身份，與 who.current 對照不符即 deny（W1-048；未提供僅警告）",
        )

    p_complete = subparsers.add_parser("complete", help=TrackMessages.HELP_COMPLETE)
    _add_complete_arguments(p_complete)

    # finish 操作：complete 的別名。避開 CC runtime worktree isolation guard
    # 對 argv 逐元素 basename 比對其 shell builtin 集合，'complete' 命中
    # bash 內建 complete 而在 worktree 派發下條件性被誤判阻擋；worktree
    # 場景改用本別名即避開誤判，主 repo 場景維持原名。complete 本身不動、
    # 不加棄用警告——它不是要被取代，只是在特定環境有代稱；兩名共享同一
    # handler（_execute_complete）與全部旗標，行為完全等價。
    p_finish = subparsers.add_parser(
        "finish",
        help="complete 的別名（worktree 派發避開 CC runtime guard 對 bash builtin "
        "'complete' 的 basename 誤判；行為完全等價，含 --as / --force 全旗標）",
    )
    _add_complete_arguments(p_finish)

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

    # set-closed-by 操作（closed 票 closed_by 欄位修正路徑）
    p_set_closed_by = subparsers.add_parser(
        "set-closed-by",
        help="修正 closed 票的 closed_by 欄位（close 拒絕覆寫既有值時使用）",
    )
    p_set_closed_by.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_closed_by.add_argument(
        "--value", required=True,
        help="新的 closed_by 值，須為合法且存在的 Ticket ID",
    )
    p_set_closed_by.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # release 操作
    p_release = subparsers.add_parser("release", help=TrackMessages.HELP_RELEASE)
    p_release.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_release.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_release.add_argument(
        "--force-release-others",
        dest="force_release_others",
        action="store_true",
        help="逃生閥：票由其他存活中的 session（FRESH）持有時，強制釋放並清除其 "
        "lease（會繞過 reclaim 三道防線，僅在確認對方 session 已不再工作時使用）",
    )

    # reclaim 操作（multi-PM 協調層 Phase 3）：僅接受 reclaimable 票，強制
    # ghost 鑑識三查（未合併分支 / 髒檔交集 / 缺 Exit Status），任一命中即拒絕。
    # 預設 dry-run 僅印鑑識報告；--confirm 且三查全過才轉回 pending 並清
    # registry lease。
    p_reclaim = subparsers.add_parser(
        "reclaim",
        help="回收 STALE session 持有的 in_progress 票（強制 ghost 鑑識三查，"
        "預設 dry-run，--confirm 才實際執行）",
    )
    p_reclaim.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_reclaim.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_reclaim.add_argument(
        "--confirm",
        dest="confirm",
        action="store_true",
        help="三查鑑識全過才生效：轉回 pending 並清除 registry lease；"
        "未加此旗標僅印 dry-run 報告",
    )

    # verify 操作（W4-019）：單獨執行 AC 驗證，與 claim 解耦
    p_verify = subparsers.add_parser(
        "verify",
        help=(
            "單獨執行 AC 驗證（不變更 Ticket 狀態，與 claim 解耦）。"
            "W4-019：補足 W3-046 後 claim 預設不驗證所造成的查詢缺口"
        ),
    )
    p_verify.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_verify.add_argument("--version", help=TrackMessages.ARG_VERSION)


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

    # title 操作 (READ)
    p_title = subparsers.add_parser("title", help=TrackMessages.HELP_TITLE)
    p_title.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_title.add_argument("--version", help=TrackMessages.ARG_VERSION)

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
    # set-who 操作（value 可省略；--current 提供子欄位寫入路徑，W1-009）
    p_set_who = subparsers.add_parser("set-who", help=TrackMessages.HELP_SET_WHO)
    p_set_who.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_who.add_argument(
        "value", nargs="?", default=None,
        help=TrackMessages.ARG_VALUE + "（與 --current 二擇一或合併使用）",
    )
    p_set_who.add_argument("--current", help="僅寫入 who.current 子欄位（保留 history）")
    p_set_who.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-title 操作（title 與 what 獨立：title 為清單顯示用短標籤）
    p_set_title = subparsers.add_parser("set-title", help=TrackMessages.HELP_SET_TITLE)
    p_set_title.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_title.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_title.add_argument("--version", help=TrackMessages.ARG_VERSION)

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

    # set-where 操作（value 可省略；--layer/--files 提供子欄位寫入路徑，W1-009）
    p_set_where = subparsers.add_parser("set-where", help=TrackMessages.HELP_SET_WHERE)
    p_set_where.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_where.add_argument(
        "value", nargs="?", default=None,
        help=TrackMessages.ARG_VALUE + "（與 --layer/--files 二擇一或合併使用）",
    )
    p_set_where.add_argument("--layer", help="僅寫入 where.layer 子欄位（保留 files）")
    p_set_where.add_argument("--files", help="僅寫入 where.files 子欄位（逗號分隔多路徑，直接覆寫）")
    p_set_where.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-why 操作
    p_set_why = subparsers.add_parser("set-why", help=TrackMessages.HELP_SET_WHY)
    p_set_why.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_why.add_argument("value", help=TrackMessages.ARG_VALUE)
    p_set_why.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-how 操作（value 可省略；--task-type/--strategy 提供子欄位寫入路徑，W1-009）
    p_set_how = subparsers.add_parser("set-how", help=TrackMessages.HELP_SET_HOW)
    p_set_how.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_how.add_argument(
        "value", nargs="?", default=None,
        help=TrackMessages.ARG_VALUE + "（與 --task-type/--strategy 二擇一或合併使用）",
    )
    p_set_how.add_argument("--task-type", dest="task_type", help="僅寫入 how.task_type 子欄位（保留 strategy）")
    p_set_how.add_argument("--strategy", help="僅寫入 how.strategy 子欄位（保留 task_type）")
    p_set_how.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # set-priority 操作（choices 於參數層 fail-fast，寫入邊界收斂第一層）
    p_set_priority = subparsers.add_parser("set-priority", help=TrackMessages.HELP_SET_PRIORITY)
    p_set_priority.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_priority.add_argument("value", choices=PRIORITY_LEVELS, help=TrackMessages.ARG_VALUE)
    p_set_priority.add_argument("--version", help=TrackMessages.ARG_VERSION)

    # add-acceptance 操作
    p_add_acc = subparsers.add_parser("add-acceptance", help=TrackMessages.HELP_ADD_ACCEPTANCE)
    p_add_acc.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_add_acc.add_argument("value", help="驗收條件文字")
    p_add_acc.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_add_acc.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )
    p_add_acc.add_argument(
        "--as",
        dest="as_agent",
        default=None,
        metavar="AGENT_NAME",
        help="申報執行身份，與 who.current 對照不符即 deny（未提供僅警告）",
    )

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
    """註冊關係和狀態管理子命令：agent, phase, add-child, set-parent, set-blocked-by, set-related-to"""
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

    # set-parent 操作（parent_id 修正路徑：清除或改寫，並同步上游 children）
    p_set_parent = subparsers.add_parser(
        "set-parent",
        help=TrackMessages.HELP_SET_PARENT,
        epilog=(
            "範例:\n"
            "  ticket track set-parent <child-id> <new-parent-id>\n"
            "  ticket track set-parent <child-id> --clear\n"
            "\n"
            "new_parent_id 與 --clear 互斥，且不可同時缺席。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_set_parent.add_argument("child_id", help=TrackMessages.ARG_SET_PARENT_CHILD_ID)
    p_set_parent.add_argument(
        "new_parent_id",
        nargs="?",
        default=None,
        help=TrackMessages.ARG_SET_PARENT_NEW_PARENT_ID,
    )
    p_set_parent.add_argument(
        "--clear", action="store_true", help=TrackMessages.ARG_SET_PARENT_CLEAR
    )
    p_set_parent.add_argument("--version", help=TrackMessages.ARG_VERSION)

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
    p_check_acceptance.add_argument(
        "--as",
        dest="as_agent",
        default=None,
        metavar="AGENT_NAME",
        help="申報執行身份，與 who.current 對照不符即 deny（W1-048；未提供僅警告）",
    )

    # set-acceptance 操作
    p_set_acceptance = subparsers.add_parser(
        "set-acceptance",
        help="勾選/取消勾選驗收條件（--check/--uncheck 支援多 index，--all-check/--all-uncheck 批量；"
             "--add/--edit/--remove 建票後修訂條目）"
    )
    p_set_acceptance.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    # nargs="+" 搭配 action="append"：兩種多值形式都成立——空白分隔
    # （--check 1 2）與重複旗標（--check 1 --check 2）。只有 nargs="+" 時
    # 重複旗標會互相覆寫且無警告，呼叫端無從察覺值被丟棄。結果為巢狀
    # list，消費端以 _flatten_values 攤平。
    p_set_acceptance.add_argument(
        "--check", nargs="+", action="append", metavar="INDEX",
        help="勾選指定 1-based index（可多個，空白分隔或重複旗標）"
    )
    p_set_acceptance.add_argument(
        "--uncheck", nargs="+", action="append", metavar="INDEX",
        help="取消勾選指定 1-based index（可多個，空白分隔或重複旗標）"
    )
    # --all 攔截：撞 --all-check/--all-uncheck（1.0.0-W1-028）。作用域 scoped 至
    # set-acceptance subparser，不影響 list/stale-list/stuck-anas 的合法 --all
    # （約束 1）；td-status 無 --all 旗標（該命令內部的 --all 是 git log 參數，
    # 非 CLI 旗標，與本攔截無關）。
    register_ambiguous_prefix(
        p_set_acceptance,
        "--all",
        "--all 不是有效旗標，請使用完整旗標名："
        "--all-check（勾選全部驗收條件）"
        "或 --all-uncheck（取消勾選全部驗收條件）",
    )
    p_set_acceptance.add_argument(
        "--all-check", dest="all_check", action="store_true",
        help="勾選全部驗收條件"
    )
    p_set_acceptance.add_argument(
        "--all-uncheck", dest="all_uncheck", action="store_true",
        help="取消勾選全部驗收條件"
    )
    p_set_acceptance.add_argument(
        "--add", nargs="+", action="append", metavar="TEXT",
        help="追加驗收條目（可多個，空白分隔各自加引號，或重複旗標），預設未勾選"
    )
    p_set_acceptance.add_argument(
        "--edit", nargs=2, action="append", metavar=("INDEX", "TEXT"),
        help="覆寫指定 1-based index 的條目文字，保留原勾選狀態（可重複指定多組）"
    )
    p_set_acceptance.add_argument(
        "--remove", nargs="+", action="append", metavar="INDEX",
        help="移除指定 1-based index（可多個，空白分隔或重複旗標）；移除已勾選條目須另加 --force"
    )
    p_set_acceptance.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_set_acceptance.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="W3-044 逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )
    p_set_acceptance.add_argument(
        "--as",
        dest="as_agent",
        default=None,
        metavar="AGENT_NAME",
        help="申報執行身份，與 who.current 對照不符即 deny（W1-048；未提供僅警告）",
    )

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
    p_append_log.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="W3-044 逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )
    p_append_log.add_argument(
        "--replace",
        action="store_true",
        default=False,
        help=(
            "整段覆寫指定章節內容（header 與章節位置不變），"
            "取代累積式 append。不可逆操作：執行前會於 stdout 印出將被取代的"
            "內容摘要供核對。"
        ),
    )

    # add-spawn-request 操作
    p_add_spawn_request = subparsers.add_parser(
        "add-spawn-request",
        help="追加結構化 spawn request（建議 PM 開新 ticket）至 Spawn Requests 章節",
    )
    p_add_spawn_request.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_add_spawn_request.add_argument("--what", required=True, help="建議開票的目標描述")
    p_add_spawn_request.add_argument("--why", required=True, help="發現此問題的原因/觸發情境")
    p_add_spawn_request.add_argument(
        "--type", required=True, help="建議 ticket 類型（IMP/ADJ/ANA/DOC）"
    )
    p_add_spawn_request.add_argument(
        "--priority", required=True, help="建議優先級（P0/P1/P2/P3）"
    )
    p_add_spawn_request.add_argument("--files", default=None, help="相關檔案路徑，逗號分隔")
    p_add_spawn_request.add_argument("--context", default=None, help="補充 context（可選）")
    p_add_spawn_request.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_add_spawn_request.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="W3-044 逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )

    # resolve-spawn-request 操作：spawn request 狀態標記 CLI 化，
    # 取代直接手改 ticket md 繞過 auto-commit 保護
    p_resolve_spawn_request = subparsers.add_parser(
        "resolve-spawn-request",
        help="標記 spawn request（SR-N）狀態為 processed 或 dismissed，並同步回填 spawned_tickets",
    )
    p_resolve_spawn_request.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_resolve_spawn_request.add_argument("sr_label", help="Spawn Request 編號（如 SR-3）")
    p_resolve_spawn_request.add_argument(
        "--status",
        required=True,
        choices=("processed", "dismissed"),
        help="新狀態：processed（已建 ticket）或 dismissed（評估後不建）",
    )
    p_resolve_spawn_request.add_argument(
        "--spawned-ticket",
        nargs="+",
        default=None,
        dest="spawned_ticket",
        help="已建立的 ticket ID（可傳多個），--status processed 時同步回填 spawned_tickets",
    )
    p_resolve_spawn_request.add_argument(
        "--reason",
        default=None,
        help="狀態變更理由（--status dismissed 建議提供；processed 亦可附加說明）",
    )
    p_resolve_spawn_request.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_resolve_spawn_request.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )

    # add-exempt-marker 操作：對已寫入的自由章節既有行補 PC-093-exempt
    # marker——append-log 僅能追加、CLI 無編輯指令、該區段不在
    # ticket-file-access-guard-hook 白名單內故 Edit 被拒，三層疊加使
    # marker 完全無法事後補上，本命令僅追加獨立標記行，不修改原文字。
    from ticket_system.lib.exempt_marker import EXEMPT_CATEGORIES as _EXEMPT_CATEGORIES

    p_add_exempt_marker = subparsers.add_parser(
        "add-exempt-marker",
        help="對指定章節既有行補上 PC-093-exempt marker（僅追加標記行，不修改原文字）",
    )
    p_add_exempt_marker.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_add_exempt_marker.add_argument(
        "--section", required=True, help=TrackMessages.ARG_SECTION
    )
    p_add_exempt_marker.add_argument(
        "--match",
        dest="match_text",
        required=True,
        help="待標記行內的文字子字串；命中多行時須提供更精確文字收窄至單一行",
    )
    p_add_exempt_marker.add_argument(
        "--category",
        required=True,
        choices=sorted(_EXEMPT_CATEGORIES),
        help="PC-093-exempt marker 類別（與 phase4-decision-enforcement-hook 白名單一致）",
    )
    p_add_exempt_marker.add_argument(
        "--reason",
        required=True,
        help="豁免理由（>= 10 字元；baseline-gated 需含數字，ticket-tracked/history 需含 "
             "W{wave}-{seq} ticket ID，rule-quote 需含規則檔案路徑）",
    )
    p_add_exempt_marker.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_add_exempt_marker.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )

    # fix-multi-view-status 操作：對 ANA Ticket Solution 區段既有的
    # multi_view_status 行原地覆寫其值——該欄位一旦寫入非法值即無合法途徑
    # 修正（append-log 僅能追加、CLI 無編輯指令、Edit 被 hook 白名單拒絕），
    # 本命令僅覆寫該行，不修改章節其他內容。
    p_fix_multi_view_status = subparsers.add_parser(
        "fix-multi-view-status",
        help="覆寫 ANA Ticket Solution 區段既有的 multi_view_status 行值（僅覆寫該行）",
    )
    p_fix_multi_view_status.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_fix_multi_view_status.add_argument(
        "--section", default="Solution", help="欲覆寫的章節（預設 Solution）"
    )
    p_fix_multi_view_status.add_argument(
        "--match",
        dest="match_text",
        default=None,
        help="多重命中時（如既有非法值行 + 事後補正行並存）用文字子字串收窄至單一行",
    )
    p_fix_multi_view_status.add_argument(
        "--value",
        required=True,
        choices=["reviewed", "skipped", "n_a"],
        help="新值（合法值：.claude/config/ana-solution-schema.yaml 定義）",
    )
    p_fix_multi_view_status.add_argument(
        "--reason",
        required=True,
        help="修正理由（>= 10 字元；供 commit 訊息與稽核追蹤，不寫入 ticket body）",
    )
    p_fix_multi_view_status.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_fix_multi_view_status.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )

    # register-artifact 操作：實驗器材票面登記 CLI 化（parallel-dispatch.md
    # 「跨 session 實驗器材的自我標示與存活期治理」條件三）
    p_register_artifact = subparsers.add_parser(
        "register-artifact",
        help="登記實驗器材（路徑/用途/存活期）至 Solution 章節，並輸出可複製的首行 header 文字",
    )
    p_register_artifact.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_register_artifact.add_argument("--path", required=True, help="器材檔案路徑")
    p_register_artifact.add_argument("--purpose", required=True, help="放置目的（一句話）")
    p_register_artifact.add_argument("--expiry", required=True, help="預期存活期（到哪個事件為止）")
    p_register_artifact.add_argument(
        "--type", default="明示", choices=("明示", "盲測"),
        help="器材型別：明示（預設，需檔名+首行雙軌標示）或盲測（限同 session，票面登記為唯一標示）",
    )
    p_register_artifact.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_register_artifact.add_argument(
        "--force", action="store_true", default=False,
        help="逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )

    # resolve-artifact 操作：實驗器材收尾處置（存活期治理，移除或指名接手票）
    p_resolve_artifact = subparsers.add_parser(
        "resolve-artifact",
        help="標記實驗器材（EXP-N）狀態為 removed 或 kept（kept 須指名接手 ticket）",
    )
    p_resolve_artifact.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_resolve_artifact.add_argument("exp_label", help="實驗器材編號（如 EXP-2）")
    p_resolve_artifact.add_argument(
        "--status", required=True, choices=("removed", "kept"),
        help="新狀態：removed（已移除）或 kept（仍需保留，須帶 --successor）",
    )
    p_resolve_artifact.add_argument(
        "--successor", default=None,
        help="--status kept 時必填：接手觀測的 ticket ID",
    )
    p_resolve_artifact.add_argument("--reason", default=None, help="狀態變更理由（可選）")
    p_resolve_artifact.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_resolve_artifact.add_argument(
        "--force", action="store_true", default=False,
        help="逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )

    # list-artifacts 操作：結構化讀取已登記器材（供收尾檢查程式化消費）
    p_list_artifacts = subparsers.add_parser(
        "list-artifacts",
        help="列出 ticket 已登記的實驗器材（結構化輸出，--json 供程式化讀取）",
    )
    p_list_artifacts.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_list_artifacts.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_list_artifacts.add_argument(
        "--json", action="store_true", default=False, help="輸出 JSON 而非人類可讀表格",
    )

    # set-exit-status 操作（1.5.0-W5-021：CLI 生成 Exit Status fenced YAML 區塊）
    p_set_exit_status = subparsers.add_parser(
        "set-exit-status",
        help="設定 Exit Status 章節（CLI 生成 fenced YAML，取代自由格式撰寫）",
    )
    p_set_exit_status.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_exit_status.add_argument(
        "--status", required=True,
        help="枚舉: success|needs_context|blocked|partial_success|failed",
    )
    p_set_exit_status.add_argument("--reason", default="", help="狀態原因說明")
    p_set_exit_status.add_argument(
        "--confidence", required=True, help="信心度（0.0-1.0）"
    )
    p_set_exit_status.add_argument(
        "--acceptance-met", nargs="*", default=None,
        dest="acceptance_met", help="已完成的 acceptance index 列表",
    )
    p_set_exit_status.add_argument(
        "--acceptance-unmet", nargs="*", default=None,
        dest="acceptance_unmet", help="未完成的 acceptance index 列表",
    )
    p_set_exit_status.add_argument(
        "--artifacts", nargs="*", default=None, help="產出檔案路徑列表",
    )
    p_set_exit_status.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_set_exit_status.add_argument(
        "--force", action="store_true", default=False,
        help="W3-044 逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )

    # set-completion-info 操作（1.5.0-W5-021：CLI 生成 Completion Info 區塊）
    p_set_completion_info = subparsers.add_parser(
        "set-completion-info",
        help="設定 Completion Info 章節（CLI 生成格式，取代自由格式撰寫）",
    )
    p_set_completion_info.add_argument("ticket_id", help=TrackMessages.ARG_TICKET_ID)
    p_set_completion_info.add_argument("--agent", required=True, help="執行代理人名稱")
    p_set_completion_info.add_argument(
        "--review-status", dest="review_status", default="pending",
        help="枚舉: pending|reviewed|n/a",
    )
    p_set_completion_info.add_argument("--summary", default="", help="變更摘要")
    p_set_completion_info.add_argument("--version", help=TrackMessages.ARG_VERSION)
    p_set_completion_info.add_argument(
        "--force", action="store_true", default=False,
        help="W3-044 逃生閥：旁路 status precondition 檢查（記入 hook-logs）",
    )

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
    p_board.add_argument(
        "--group-by",
        choices=[GROUP_BY_WAVE, GROUP_BY_TOPIC],
        default=GROUP_BY_WAVE,
        help=TrackMessages.ARG_GROUP_BY,
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
    register_hook_liveness(track_subparsers)
    register_dispatch_validate(track_subparsers)
    register_dispatch_readiness(track_subparsers)
    register_depth(track_subparsers)
    register_sessions(track_subparsers)
    register_activity(track_subparsers)
    register_conflicts(track_subparsers)
    register_topics(track_subparsers)
    register_topic_backfill(track_subparsers)
    register_onboard(track_subparsers)
    register_dispatch_command(track_subparsers)
    register_commit_command(track_subparsers)


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

