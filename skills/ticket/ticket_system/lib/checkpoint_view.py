"""Checkpoint view function 模組（W10-017.1 v2 新增，W10-017.1 Phase 3b 落地）。

本模組純 view function（無 I/O），輸入 CheckpointState + caller 路由參數，
輸出人類可讀字串/結構。CLI 三命令（snapshot / handoff-ready / checkpoint-status）
共用，禁止 CLI 自行詮釋 active_handoff（v2 §3.6 / §6.1）。

設計依據：
- v2.1 §3.3 / §6.1 / §6.2 命名鎖定 + 三 caller 路由
- v2.2 Q1 unknown caller raise ValueError
- v2.2 Q4 format_local_time 系統時區
- v2.3 Q6 [?] 三態標記
- Phase 3a Implementation Strategy §2 函式介面契約
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple, get_args

from .checkpoint_state import (
    CheckpointCaller,
    CheckpointState,
    _resolve_rule,
    format_next_action,
    format_phase_label,
)


# CLI 三命令的合法 caller 集合（v2.2 Q1 規格鎖定）。
# W10-017.11 AC 2：從 CheckpointCaller Literal 透過 get_args 派生，過濾掉 log
# fallback 值 "unknown"，避免雙源定義漂移。新增 CLI caller 時只需擴充 Literal。
_VALID_CALLERS = tuple(c for c in get_args(CheckpointCaller) if c != "unknown")


# ---------------------------------------------------------------------------
# format_local_time（v2.2 Q4 命名鎖定）
# ---------------------------------------------------------------------------


def format_local_time(state: CheckpointState) -> str:
    """轉 state.computed_at（UTC ISO8601）為本地時區可讀字串。

    決策（v2.2 Q4）：
    - 主路徑：datetime.fromisoformat(raw) + astimezone() 轉本地時區，
      strftime("%Y-%m-%d %H:%M (local)") 格式化。
    - Fallback（raw 解析失敗）：用 time.localtime + strftime 產生當前本地時間
      字串；raw 非空時保留原字串 + " (當前本地時間)" 標記，raw 空時回純當前本地時間。
    目的：避免拋例外阻塞 view 渲染（fail-open）。
    """

    raw = state.computed_at or ""
    try:
        dt = datetime.fromisoformat(raw)
        local = dt.astimezone()
        return local.strftime("%Y-%m-%d %H:%M (local)")
    except (ValueError, TypeError):
        # fallback：保留原字串 + (local) 標記
        # （fail-open；不應影響 snapshot 主流程）
        now_local = time.strftime("%Y-%m-%d %H:%M (local)", time.localtime())
        return raw + f" ({now_local})" if raw else now_local


# ---------------------------------------------------------------------------
# handoff_status_for（v2.1 §6.1 命名鎖定，v2.2 Q1 邊界）
# TD-A 錨點：caller 為 Literal[...] (見 checkpoint_state.CheckpointCaller)，
#   runtime 用 ValueError 守邊（v2.2 Q1），Phase 4 評估升級為 enum / dataclass tag。
# W10-017.13 AC1：dict dispatch 取代 if-elif 字串比對，新增 caller 僅需擴充表。
# ---------------------------------------------------------------------------


# 單一 caller 對單一 handoff_id 狀態的 builder：(handoff_id) -> (is_ok, message)
_HandoffStatusBuilder = Callable[[Optional[str]], Tuple[bool, str]]


def _snapshot_handoff_status(handoff_id: Optional[str]) -> Tuple[bool, str]:
    """snapshot caller: handoff 存在視為 NO-GO（pipeline 阻擋判定）。"""
    if handoff_id is None:
        return True, "無 pending handoff"
    return False, f"先處理 pending handoff: {handoff_id}"


def _handoff_ready_status(handoff_id: Optional[str]) -> Tuple[bool, str]:
    """handoff-ready caller: handoff 已建立視為 GO，無 handoff 則看其他阻擋。"""
    if handoff_id is None:
        return True, "無 pending handoff (看其他阻擋)"
    return True, f"handoff 已建立: {handoff_id}"


def _checkpoint_status_handoff_status(handoff_id: Optional[str]) -> Tuple[bool, str]:
    """checkpoint-status caller: 純資訊回報，永不阻擋。"""
    if handoff_id is None:
        return True, "無 pending handoff"
    return True, f"handoff pending: {handoff_id}"


# caller → builder 路由表（v2.1 §6.1 / §6.2）
# 新增 caller 時：(1) 在 CheckpointCaller Literal 加值；(2) 在此表加 entry。
_HANDOFF_STATUS_ROUTES: Dict[str, _HandoffStatusBuilder] = {
    "snapshot": _snapshot_handoff_status,
    "handoff-ready": _handoff_ready_status,
    "checkpoint-status": _checkpoint_status_handoff_status,
}


def handoff_status_for(
    state: CheckpointState, caller: str
) -> Tuple[bool, str]:
    """三 caller 路由詮釋 active_handoff，回 (is_ok_for_caller, message)。

    路由表（v2.1 §6.1 / §6.2）：
      caller          | active_handoff is None       | active_handoff not None
      snapshot        | (True, "無 pending handoff") | (False, "先處理 pending handoff: {id}")
      handoff-ready   | (True, "無 pending handoff (看其他阻擋)") | (True, "handoff 已建立: {id}")
      checkpoint-status | (True, "無 pending handoff") | (True, "handoff pending: {id}")

    實作（W10-017.13 AC1）：改用 _HANDOFF_STATUS_ROUTES dict dispatch，
    避免原 if-elif 字串比對無法在新增 caller 時被型別檢查器提醒遺漏。

    Args:
        state: CheckpointState 實例。
        caller: 必為 _VALID_CALLERS 之一，否則 raise ValueError（v2.2 Q1）。

    Raises:
        ValueError: caller 不在 _VALID_CALLERS 中。
    """

    if caller not in _VALID_CALLERS:
        raise ValueError(f"unknown caller: {caller}")

    # _VALID_CALLERS 與 _HANDOFF_STATUS_ROUTES 同步保證（見模組頂註解）。
    builder = _HANDOFF_STATUS_ROUTES[caller]
    return builder(state.active_handoff)


# ---------------------------------------------------------------------------
# get_suggested_commands（PRIORITIES 第 5 欄反查 helper）
# ---------------------------------------------------------------------------


def get_suggested_commands(state: CheckpointState) -> List[str]:
    """回傳 state 對應的建議命令清單。

    W10-017.12 AC3：改為委派 _resolve_rule，與 _derive_checkpoint 共用
    單次 PRIORITIES loop（原本此函式會做一次獨立掃描）。

    語意保持：依規則優先序命中第一條；PRIORITIES 全數未命中則落入 FALLBACK。
    """

    _phase, _label, _action, commands = _resolve_rule(state)
    return commands


# ---------------------------------------------------------------------------
# compute_blockers（W10-017.12 AC1：從 commands/track_handoff_ready 上移）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Blocker:
    """handoff-ready 阻擋項（純資料載體，view 由呼叫端渲染）。

    W10-017.12 AC1：從 commands/track_handoff_ready._Blocker 上移 lib 層，
    使 commands 層僅決定 exit code 與 print，業務判定集中 lib。

    Attributes:
        label: 人類可讀阻擋描述。
        fix: 修復建議（命令或指示）。
    """

    label: str
    fix: str


def compute_blockers(
    state: CheckpointState, ticket_id: Optional[str] = None
) -> List[Blocker]:
    """計算 handoff-ready 阻擋項清單（v2.1 §1.6 真值表）。

    W10-017.12 AC1：從 commands/track_handoff_ready._compute_blockers 上移至
    lib 層，commands 層只消費結果決定 exit code 與 print。

    全域阻擋項（不過濾 ticket-id）：
      - active_agents > 0
      - uncommitted_files > 0（None 視為未知，不視為阻擋）
      - len(unmerged_worktrees) > 0
    Ticket-id 過濾項：
      - in_progress_tickets 含「非當前 ticket」者 → 阻擋
        指定 ticket_id 自己 in_progress 視為「正常推進」非阻擋

    Args:
        state: 已填入資料來源欄位的 CheckpointState。
        ticket_id: 當前 ticket ID；用於排除自身 in_progress 判定。

    Returns:
        阻擋項清單；空清單表示 GO。
    """

    blockers: List[Blocker] = []

    if state.active_agents > 0:
        blockers.append(
            Blocker(
                label=f"活躍代理人未完成 (active_agents={state.active_agents})",
                fix="ticket track agent-status 查看; 等待完成",
            )
        )

    uncommitted = state.uncommitted_files
    if uncommitted is not None and uncommitted > 0:
        blockers.append(
            Blocker(
                label=f"未提交變更 (uncommitted_files={uncommitted})",
                fix=f"git add + git commit ({uncommitted} 檔)",
            )
        )

    if len(state.unmerged_worktrees) > 0:
        blockers.append(
            Blocker(
                label=f"未合併 worktree (count={len(state.unmerged_worktrees)})",
                fix="git worktree list; cd <wt> && git push; cd <main> && git merge",
            )
        )

    # in_progress_tickets：排除「自身 ticket」
    other_in_progress = [
        tid for tid in state.in_progress_tickets if tid != ticket_id
    ]
    if other_in_progress:
        blockers.append(
            Blocker(
                label=f"其他 ticket 進行中 ({len(other_in_progress)} 個)",
                fix=f"完成或 release 其他 ticket: {', '.join(other_in_progress)}",
            )
        )

    return blockers


# ---------------------------------------------------------------------------
# render_current_suggestion（v2.1 §3.2 區塊；命名屬語意契約）
# ---------------------------------------------------------------------------


def render_current_suggestion(state: CheckpointState) -> str:
    """渲染「--- 當前建議 ---」區塊。

    格式（v2.1 §3.2）：
        --- 當前建議 ---
          Checkpoint: {format_phase_label(state)}
          下一步: {format_next_action(state)}
          建議命令:
            {cmd_1}
            {cmd_2}
    """

    label = format_phase_label(state)
    action = format_next_action(state)
    commands = get_suggested_commands(state)

    lines = ["--- 當前建議 ---", f"  Checkpoint: {label}", f"  下一步: {action}"]
    if commands:
        lines.append("  建議命令:")
        for cmd in commands:
            lines.append(f"    {cmd}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# render_ready_check（v2.1 §1.4 + v2.3 Q6 三態標記）
# AD-4 錨點：uncommitted_files=None 顯示 [?]（區分「資料源失敗」vs「真實未提交」）。
# W10-017.13 AC2：改用結構化 CheckItem list，消除從 "[ ]" 字串反推「未通過」計數的
#   magic string 依賴。
# ---------------------------------------------------------------------------


def _mark(passed: bool) -> str:
    """純 ASCII 三態標記 helper（v2.3 Q6 規格）。

    Note: 僅用於 pass/fail 雙態。資料源未知情境（[?]）由 CheckItem.status
    直接存「unknown」走 _STATUS_TO_MARK 路由，不經此 helper。
    """
    return "[x]" if passed else "[ ]"


# CheckItem.status → 視覺標記
_STATUS_TO_MARK: Dict[str, str] = {
    "pass": "[x]",
    "fail": "[ ]",
    "unknown": "[?]",
}


@dataclass(frozen=True)
class CheckItem:
    """Ready Check 單一檢查項（結構化取代字串匹配）。

    W10-017.13 AC2：取代原本「從 rendered line 反推 [ ] 計數」的 magic string
    依賴。now 計數直接用 `sum(1 for ci in items if ci.status == "fail")`。

    Attributes:
        status: "pass" / "fail" / "unknown"（對應 [x] / [ ] / [?]）。
        text: 主敘述文字（不含前導 "  [x]" 標記）。
        hint: 可選的修復命令 hint（append 到同一行尾 "→ ..."）。
    """

    status: str  # Literal["pass", "fail", "unknown"]，runtime 以 _STATUS_TO_MARK 守邊
    text: str
    hint: Optional[str] = None

    def render(self) -> str:
        """渲染成單行（含前導兩空白 + mark + text + 可選 hint）。"""
        mark = _STATUS_TO_MARK.get(self.status, "[?]")
        line = f"  {mark} {self.text}"
        if self.hint:
            line += f" → {self.hint}"
        return line


def _build_ready_check_items(
    state: CheckpointState, caller: str
) -> List[CheckItem]:
    """依 state + caller 組出 4 項 CheckItem（依序：agents / uncommitted / worktree / handoff）。"""

    items: List[CheckItem] = []

    # 1. 活躍代理人
    agents_pass = state.active_agents == 0
    items.append(
        CheckItem(
            status="pass" if agents_pass else "fail",
            text=f"無活躍代理人 (active_agents={state.active_agents})",
            hint=None if agents_pass else "ticket track agent-status",
        )
    )

    # 2. 未提交變更（None=未知，標 [?]；AD-4 錨點）
    uncommitted = state.uncommitted_files
    if uncommitted is None:
        items.append(
            CheckItem(
                status="unknown",
                text="無未提交變更 (uncommitted_files=未知, 資料源不可用)",
            )
        )
    else:
        unc_pass = uncommitted == 0
        items.append(
            CheckItem(
                status="pass" if unc_pass else "fail",
                text=f"無未提交變更 (uncommitted_files={uncommitted})",
                hint=None if unc_pass else "git add + git commit",
            )
        )

    # 3. 未合併 worktree
    wt_count = len(state.unmerged_worktrees)
    wt_pass = wt_count == 0
    items.append(
        CheckItem(
            status="pass" if wt_pass else "fail",
            text=f"無未合併 worktree (count={wt_count})",
            hint=None if wt_pass else "git worktree list",
        )
    )

    # 4. handoff（透過 view function 路由）
    is_ok, msg = handoff_status_for(state, caller)
    items.append(
        CheckItem(
            status="pass" if is_ok else "fail",
            text=msg,
        )
    )

    return items


def render_ready_check(state: CheckpointState, caller: str) -> str:
    """渲染「--- /clear Ready Check ---」checklist。

    四項判定（v2.1 §1.4）：
      - 無活躍代理人: state.active_agents == 0
      - 無未提交變更: state.uncommitted_files in (0,)；None → [?]（v2.3 Q6 / AD-4）
      - 無未合併 worktree: len(state.unmerged_worktrees) == 0
      - handoff 行: handoff_status_for(state, caller)

    snapshot 視角追加 footer（AD-1 錨點：snapshot exit 永遠 0）：
      Pipeline 阻擋判定請改用: ticket track handoff-ready

    W10-017.13 AC2：未通過計數改用 CheckItem.status == "fail" 結構化統計，
    消除原本「從 rendered line 反推 '[ ]' 字串」的 magic string 依賴。
    """

    items = _build_ready_check_items(state, caller)
    lines = ["--- /clear Ready Check ---"]
    lines.extend(item.render() for item in items)

    # snapshot 視角 footer
    if caller == "snapshot":
        unchecked = sum(1 for ci in items if ci.status == "fail")
        lines.append(
            f"  顯示結果: {unchecked} 項未通過 (純展示, snapshot exit 永遠 0)"
        )
        lines.append(
            "  Pipeline 阻擋判定請改用: ticket track handoff-ready"
        )

    return "\n".join(lines)


__all__ = [
    "format_local_time",
    "handoff_status_for",
    "get_suggested_commands",
    "Blocker",
    "compute_blockers",
    "render_current_suggestion",
    "render_ready_check",
    "CheckItem",
]
