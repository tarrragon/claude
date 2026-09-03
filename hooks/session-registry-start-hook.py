#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///

"""
Session Registry Start Hook - SessionStart

功能:
  PM session 啟動時，將自身註冊進跨 worktree 共享的 pm-registry.json
  （落於 `git rev-parse --git-common-dir` 解析出的主 .git/ 目錄），供同一
  repo 上其他並行 PM session 查詢存活狀態。

  子代理人環境（agent_id 存在於 stdin）不觸發，避免將短生命週期的
  subagent 執行誤記為獨立 PM session——registry 本意為 multi-PM 協調層
  （同一 repo 上多個獨立 worktree/branch 的主線程 PM），派發追蹤已由
  dispatch-active.json 承擔，兩者職責不重疊。

  registry 契約 v2（D4 增補 1）：依 stdin 的 `source` 欄位分流——
  `source == "resume"` 時 merge（繼承既有 lease，恢復語意）；其餘
  （startup/clear/未知值）一律 reset（新生 session 不繼承舊 lease，
  防 SessionEnd 漏觸發 + 同 session_id 重開時繼承 zombie lease）。

  非 git 環境（`get_registry_paths` 回傳 None）跳過註冊並 stderr 一次性
  提示（契約 v2 D3：不再 fallback 寫入讀端永不查詢的暫定路徑）。

  idle agent 回收掃描（唯讀，不執行任何 TaskStop）:
    註冊成功後，額外唯讀掃描 dispatch-active.json 中 turn_ended_at 已
    設定的 entry（回合已結束的候選），交叉比對 pm-registry.json 判定
    其歸屬，輸出報告區塊供 PM 依 parallel-dispatch.md「idle agent 回收
    SOP」處置。掃描不呼叫 ListAgents / TaskStop——這兩者只有互動式的
    PM/代理人對話迴圈能存取，本 hook 是外部腳本，只能交叉比對持久化
    狀態檔並產出建議動作，實際的續用/放生判斷與 ListAgents 觀察由收到
    報告的 PM 執行。

    產出形態三分（依 entry 的 session_id 與 pm-registry.json 交叉比對）:
    - 本 session 自有：直接可依 SOP 續用/放生
    - 他 session 所屬且該 session heartbeat 仍新鮮（is_fresh）：產出為
      向該 session 發出回收請求；接收方須以自身代理人清單驗證歸屬後才
      執行，不採信請求方提供的歸屬資訊
    - 擁有者已結束（session_id 不在 registry 的 sessions 中）：確定孤兒；
      heartbeat 已逾 STALE_THRESHOLD_MINUTES 但仍在 registry 中：疑似
      孤兒。兩者皆回報但語氣須可區分（前者無回收路徑，後者可能仍在）

    掃描失敗（任何例外）僅 logger.warning 降級忽略，不影響本 hook 的
    註冊主流程與退出碼——本節為輔助性回報，非本 hook 的核心職責。

觸發時機: 每個 CC session 啟動時 (SessionStart)
行為: 不阻擋（SessionStart 本就無 deny 機制），registry 損毀/缺檔時
      重建 + stderr 通知（雙通道可觀測性，異常不靜默）

Registry Schema 契約：見 .claude/lib/pm_registry.py 模組 docstring（SSOT）。

來源:
  - multi-PM 協調層 Phase 1（framework issue tarrragon/claude#77）
  - Registry Schema 契約 v2（釋放時機/欄位/upsert 語意重議，同 issue）
  - idle agent 回收 SOP 觸發層：parallel-dispatch.md「idle agent 回收
    SOP」判準已完整但無觸發層，補上 SessionStart 唯讀掃描回報
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    read_json_from_stdin,
    is_subagent_environment,
    get_project_root,
    run_hook_safely,
    resolve_session_id,
)
from lib.pm_registry import (
    get_registry_paths,
    register_session,
    read_registry,
    is_fresh,
    DEGRADED_READ_KEY,
)
from lib.dispatch_tracker import get_active_dispatches
from lib.hook_ticket import find_ticket_file, parse_ticket_frontmatter

HOOK_NAME = "session-registry-start-hook"
EXIT_SUCCESS = 0

# 與 .claude/skills/ticket/ticket_system/constants.py 的 TERMINAL_STATUSES
# 對齊（本檔 uv script dependencies 僅宣告 pyyaml，不耦合 skills/ 套件，
# 比照 session-start-scheduler-hint-hook.py 既有慣例本地維護副本）。
TERMINAL_TICKET_STATUSES = {"completed", "closed"}

_OWNERSHIP_LABELS = {
    "self": "本 session 自有",
    "cross_session_alive": "他 session 所屬（仍存活）",
    "orphan_confirmed": "確定孤兒（擁有者 session 已結束）",
    "orphan_suspected": "疑似孤兒（擁有者 session heartbeat 逾時）",
    "unknown_owner": "歸屬不明（記錄缺 session_id）",
    "registry_unavailable": "無法判定（pm-registry.json 讀取失敗或損毀）",
}

# 措辭須反映停止的可逆性：不含「已失效」「無效」「可刪除」等暗示不可逆
# 或暗示目標已無用的字樣。停止不是終態——對已停止代理人發訊息會帶完整
# transcript 恢復它，故語意為「釋放被佔用的執行體」而非「清除已死之物」。
_OWNERSHIP_ACTIONS = {
    "self": (
        "以 ListAgents 讀取 Teammates 區塊內的列（非區塊存在性——該判準"
        "在多代理人情境恆為真，僅單一代理人時失去鑑別力）確認其狀態，依"
        "parallel-dispatch.md「idle agent 回收 SOP」續用/放生判準決定；"
        "停止不是終態，SendMessage 到其名稱可帶原 transcript 恢復"
    ),
    "cross_session_alive": (
        "向擁有者 session 發出回收請求；接收方須先以自身代理人清單驗證"
        "該名稱確實屬於自己再執行，不採信本請求提供的歸屬資訊"
    ),
    "orphan_confirmed": (
        "目前無任何 session 可查得或執行回收，回報為框架限制；代理人本身"
        "是否仍在執行未知，本框架僅是無查證或回收路徑，非「已清除」"
    ),
    "orphan_suspected": (
        "擁有者 session 可能仍在但心跳已逾時，建議先確認該 session 是否"
        "異常終止，暫不視為確定孤兒"
    ),
    "unknown_owner": "無法判定歸屬 session，建議人工核對後處置",
    "registry_unavailable": (
        "pm-registry.json 讀取失敗或損毀，暫時無法判定此 entry 是否為孤兒"
        "——不得因 registry 暫時不可讀就當作「無擁有者」處置，待 registry"
        "修復（下次任一 session 啟動時自動重建）後重新掃描再判斷"
    ),
}


def _resolve_ticket_status(ticket_id: str, project_root: Path, logger) -> str:
    """查詢 ticket 現況（completed/closed/in_progress/查無），跨版本跨
    Wave（`find_ticket_file` 對無法解析版本號或直接路徑不存在時 fallback
    全量掃描，天然涵蓋跨版本查詢，不需自行限制搜尋目錄）。
    """
    if not ticket_id:
        return "查無"
    path = find_ticket_file(ticket_id, project_root=project_root, logger=logger)
    if path is None:
        return "查無"
    frontmatter = parse_ticket_frontmatter(path, logger=logger)
    status = frontmatter.get("status")
    return status if isinstance(status, str) and status else "查無"


def _classify_ownership(
    entry_session_id: str,
    self_session_id: str,
    registry_sessions: Dict,
    registry_available: bool = True,
) -> str:
    """三分產出形態 + 孤兒兩級 + registry 不可用降級：

    - "self"：entry 屬本 session
    - "cross_session_alive"：他 session 所屬且該 session heartbeat 仍新鮮
    - "orphan_confirmed"：session_id 不在 pm-registry.json 的 sessions 中
      （已 SessionEnd graceful release），無 session 可回收
    - "orphan_suspected"：session_id 存在於 registry 但 heartbeat 已逾
      STALE 門檻，可能異常終止未 graceful release
    - "unknown_owner"：entry 無 session_id（早期派發記錄缺此欄位），無法
      判定歸屬
    - "registry_unavailable"：registry 讀取失敗/損毀（`read_registry`
      降級分支），無法排除該 session 其實仍在 registry 中只是讀不到——
      registry 不可用時一律回傳本分類，不得誤判為 orphan_confirmed（見
      `registry_available=False` 時的判斷順序：先於 self 之後、其他分類
      之前短路，因為 registry 不可用本身無法否定「他 session 存活」的
      可能性）
    """
    if not entry_session_id:
        return "unknown_owner"
    if entry_session_id == self_session_id:
        return "self"
    if not registry_available:
        return "registry_unavailable"
    session_entry = registry_sessions.get(entry_session_id)
    if session_entry is None:
        return "orphan_confirmed"
    if not is_fresh(session_entry.get("heartbeat_ts")):
        return "orphan_suspected"
    return "cross_session_alive"


def _format_candidate_line(entry: Dict, ticket_status: str, ownership: str) -> str:
    name = entry.get("name") or entry.get("agent_description") or "(未命名)"
    ticket_id = entry.get("ticket_id") or "(無)"
    session_id = entry.get("session_id") or "(無)"
    reclaimable = "可清" if ticket_status in TERMINAL_TICKET_STATUSES else "非終止狀態，可能仍在等待下一輪派發"
    ownership_label = _OWNERSHIP_LABELS.get(ownership, ownership)
    action = _OWNERSHIP_ACTIONS.get(ownership, "")
    return (
        f"- {name}｜ticket {ticket_id}（現況：{ticket_status}，{reclaimable}）｜"
        f"{ownership_label}（session {session_id}）\n"
        f"  處置：{action}"
    )


def scan_idle_agents(
    project_root: Path,
    self_session_id: str,
    registry_file: Path,
    logger,
) -> Optional[str]:
    """唯讀掃描 dispatch-active.json 中 turn_ended_at 已設定的候選 entry，
    交叉比對 pm-registry.json 判定歸屬，組出回報區塊。不執行任何
    TaskStop、不修改任何狀態檔（純讀取），呼叫端無候選時應 suppress
    本節（回傳 None）。

    候選集合定義為「turn_ended_at 已設定」，非「ListAgents 判定為
    idle」——後者對跨 session 族群無鑑別力（ListAgents 只列本 session
    自有 teammate）。
    """
    candidates = [
        d for d in get_active_dispatches(project_root) if d.get("turn_ended_at")
    ]
    if not candidates:
        return None

    registry_data = read_registry(registry_file, logger=logger)
    registry_available = not registry_data.get(DEGRADED_READ_KEY, False)
    registry_sessions = registry_data.get("sessions", {}) or {}

    lines: List[str] = []
    for entry in candidates:
        ticket_status = _resolve_ticket_status(
            entry.get("ticket_id") or "", project_root, logger
        )
        ownership = _classify_ownership(
            entry.get("session_id") or "",
            self_session_id,
            registry_sessions,
            registry_available,
        )
        lines.append(_format_candidate_line(entry, ticket_status, ownership))

    return (
        "## idle agent 回收掃描（{} 筆候選，唯讀回報，未執行任何 TaskStop）\n\n"
        .format(len(lines))
        + "\n".join(lines)
        + "\n\n續用/放生完整判準見 "
        "`.claude/references/parallel-dispatch-agent-lifecycle-details.md`"
        "「idle agent 回收 SOP」，不另立平行判準。"
    )


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)

    if is_subagent_environment(input_data):
        logger.debug("subagent environment, skip registry registration")
        return EXIT_SUCCESS

    session_id = resolve_session_id(input_data)
    if not session_id:
        message = (
            "[session-registry-start-hook] 無法取得 session_id，跳過 registry 註冊"
            "（本 session 將不列於 `ticket track sessions`，無需處置）"
        )
        sys.stderr.write(message + "\n")
        logger.warning(message)
        return EXIT_SUCCESS

    source = (input_data or {}).get("source", "")

    project_root = get_project_root()
    registry_paths = get_registry_paths(cwd=str(project_root), logger=logger)
    if registry_paths is None:
        message = (
            "[session-registry-start-hook] 非 git 環境，跳過 registry 註冊"
            "（跨 session 協調功能於此環境本不適用，無需處置）"
        )
        sys.stderr.write(message + "\n")
        logger.info(message)
        return EXIT_SUCCESS
    registry_file, lock_file = registry_paths

    try:
        register_session(
            registry_file=registry_file,
            lock_file=lock_file,
            session_id=session_id,
            name=project_root.name,
            project=str(project_root),
            source=source,
            logger=logger,
        )
        logger.info(
            "session 已註冊至 pm-registry: session_id=%s name=%s source=%s",
            session_id,
            project_root.name,
            source or "(empty)",
        )
    except OSError as e:
        message = (
            "[session-registry-start-hook] registry 註冊失敗: {}"
            "（本 session 未寫入 registry，`ticket track sessions` 查詢不到本 session；"
            "下次 heartbeat 觸發時會自我修復補建 entry，無需手動處置）"
        ).format(e)
        sys.stderr.write(message + "\n")
        logger.warning(message)

    # idle agent 回收掃描：輔助性回報，失敗時降級忽略不影響本 hook 的
    # 核心職責（registry 註冊）與退出碼。
    scan_context = None
    try:
        scan_context = scan_idle_agents(project_root, session_id, registry_file, logger)
    except Exception as e:  # noqa: BLE001
        logger.warning("idle agent 回收掃描失敗（降級忽略）: %s", e)

    if scan_context:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": scan_context,
                    },
                    "suppressOutput": False,
                },
                ensure_ascii=False,
            )
        )

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
