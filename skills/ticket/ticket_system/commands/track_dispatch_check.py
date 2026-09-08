"""ticket track dispatch-check 命令（0.18.0-W10-017.2）。

取代 PC-050 `cat .claude/dispatch-active.json` 片段，提供 CLI 化的活躍派發判定：
- exit 0: 無活躍派發（檔案不存在 / dispatches=[]，視同已清空）
- exit 1: 有活躍派發（列出每筆 agent_description / ticket_id / dispatched_at）
- exit 2: IO 或 JSON 格式錯誤（stderr + 保守 NO-GO 供 Hook 程式化判定）

語意等價依據：
- PC-050 派發後清點 / 收到完成通知兩處均為讀檔 + 判斷 dispatches 陣列空/非空
- 新 CLI 多加：格式化輸出 + exit code，不改變判定規則

`--prune`（3-F M-6）：清理符合以下任一判準的條目（OR，非 AND），取代
文件原載「見 [STALE] 手動清理 dispatch-active.json」的無痕跡做法：

(A) session 存活判準：既有年齡門檻標為 [STALE]，且條目 `session_id`
    非空且不在 pm-registry.json 的 session 集合內（委派 track_sessions
    既有 registry 讀取邏輯）。`session_id` 為空（無法歸戶）或 registry
    暫時不可用（無法判定存在與否）時一律保守不清理——避免把「heartbeat
    慢但仍存活的 agent」（session 仍在 registry 內，只是自身 heartbeat
    逾 TTL）誤判為「不存在」而清空其唯一的存活佐證。
(B) 票終態判準：條目 `ticket_id` 非空且該票目前狀態為終態
    （completed/closed，見 `_is_ticket_terminal`）。獨立於 (A)——不要求
    [STALE]，也不受 registry 是否可用影響，因為票是否終態的判準權威
    來源是票狀態本身，不需 session 存活佐證。

兩者任一成立即清理。清理結果落 `.claude/hook-logs/dispatch-check-
prune/`（雙通道：stderr + hook-logs，符合可觀測性規則 4）。

寫入路徑：清理判準 (A)(B) 在本檔計算，實際的讀-改-寫委派給
`dispatch_tracker.prune_dispatches`（見 `_load_dispatch_tracker` /
`_make_prune_predicate`），與 `record_dispatch` 等既有寫入路徑共用同一把
`_state_lock` 排他鎖與 `_write_state` 原子替換，不在本檔重新實作鎖與
原子寫。`dispatch_tracker` 模組不可用時 fail-open（不清理，寫 stderr），
不回退為無鎖直寫。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# dispatch-active.json 屬跨 agent 協調狀態，root 解析改用
# get_ticket_state_root()（非 get_project_root()）——linked worktree 內
# 統一寫入/讀取主倉庫，理由與 get_ticket_state_root docstring 一致。
from ticket_system.lib.claude_lib_loader import load_claude_lib
from ticket_system.lib.paths import get_ticket_state_root

_DISPATCH_ACTIVE_RELPATH = Path(".claude/dispatch-active.json")

# 3-H 個案 1／2：dispatch-check 原判定只收「dispatches 是否為空」，無記錄
# 新鮮度維度，PM 依 WARN 後無可執行下一步（無從分辨活躍派發是剛發出還是
# 已逾時遺留）。沿用 track_dashboard.DEFAULT_STALE_THRESHOLD_MIN（60 分鐘）
# 同一新鮮度慣例，不另立門檻常數。
_STALE_THRESHOLD_MIN = 60

# --prune 寫入 hook-logs 的 hook 識別名稱（3-F M-6）。
_PRUNE_HOOK_NAME = "dispatch-check-prune"


def _format_age(dispatched_at: object, now: datetime) -> str:
    """回傳 dispatched_at 距 now 的新鮮度標註；無法解析（缺失/格式錯誤/
    未來時間）回傳空字串，不猜測。"""
    if not isinstance(dispatched_at, str) or not dispatched_at.strip():
        return ""
    try:
        ts = datetime.fromisoformat(dispatched_at.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_minutes = (now - ts).total_seconds() / 60
    if age_minutes < 0:
        return ""
    if age_minutes >= _STALE_THRESHOLD_MIN:
        return f" [STALE {age_minutes:.0f}min]"
    return f" ({age_minutes:.0f}min)"


def _format_entry(entry: dict, now: Optional[datetime] = None) -> str:
    desc = entry.get("agent_description", "(unknown)")
    tid = entry.get("ticket_id") or "(no ticket)"
    ts = entry.get("dispatched_at", "(no timestamp)")
    age = _format_age(entry.get("dispatched_at"), now) if now is not None else ""
    return f"  - {desc} | ticket: {tid} | {ts}{age}"


def _load_registry_session_ids() -> Optional[Set[str]]:
    """讀取 pm-registry.json 的 session id 集合，供 `--prune` 判定「session
    是否存在」。委派 `track_sessions` 既有 registry 讀取邏輯（同一 SSOT，
    避免重複實作 git-common-dir 解析與 JSON 容錯降級）。

    Returns:
        Set[str]: registry 可讀取時的 session id 集合（可能為空集合）。
        None: registry 不可用（git 不可用 / 檔案不存在 / 解析失敗 /
            結構不符）——呼叫端須視為「無法判定」而非「全部不存在」，
            避免 registry 暫時性不可用時把所有 [STALE] 條目誤判為可清理。
    """
    from ticket_system.commands.track_sessions import _load_registry, _registry_path

    registry_path = _registry_path()
    if registry_path is None:
        return None
    registry = _load_registry(registry_path)
    if registry is None:
        return None
    sessions = registry.get("sessions")
    if not isinstance(sessions, dict):
        return None
    return set(sessions.keys())


def _get_prune_logger() -> Optional[Any]:
    """Lazy 載入 `.claude/lib/hook_logging.py` 的 `setup_hook_logging`，
    供 `--prune` 落 hook-logs（取代 PM 手動改 JSON 的無痕跡清理）。

    載入失敗時降級為 None，呼叫端須同時寫 stderr（可觀測性規則 4：不可
    僅靠 hook-logs 單一通道，失敗時不可整段靜默）。
    """
    try:
        hook_logging = load_claude_lib("hook_logging")
        if hook_logging is None:
            return None
        return hook_logging.setup_hook_logging(_PRUNE_HOOK_NAME)
    except Exception:  # noqa: BLE001 — 日誌基礎設施失敗不可阻擋主流程
        return None


def _is_ticket_terminal(ticket_id: str) -> bool:
    """判斷 ticket_id 對應的票目前是否為終態（completed/closed）。

    `--prune` 第二條獨立清理判準——票已終態代表對應派發不可能仍在進行，
    判準權威來源是票狀態本身，不需 session 存活佐證，因此與既有的
    [STALE] + session 判準完全獨立（不受 registry 是否可用影響）。

    查無法解析版本 / 查無此票 / 讀取例外一律回傳 False（保守：判定不了
    就不視為終態，避免誤刪仍可能有效的派發記錄——與 `_load_registry_
    session_ids` 對「無法判定」一律不清理的保守原則一致）。
    """
    try:
        from ticket_system.lib.constants import TERMINAL_STATUSES
        from ticket_system.lib.ticket_loader import load_ticket
        from ticket_system.lib.ticket_validator import (
            extract_version_from_ticket_id,
        )

        version = extract_version_from_ticket_id(ticket_id)
        if not version:
            return False
        ticket = load_ticket(version, ticket_id)
        if not ticket:
            return False
        return ticket.get("status") in TERMINAL_STATUSES
    except Exception:  # noqa: BLE001 — 保守降級，不阻擋 --prune 主流程
        return False


def _load_dispatch_tracker() -> Optional[Any]:
    """Lazy 載入 `.claude/lib/dispatch_tracker`（薄封裝，供測試以
    `monkeypatch.setattr(mod, "_load_dispatch_tracker", ...)` 覆寫，比照
    `lifecycle.py` `_load_dispatch_tracker` 既有慣例）。

    `--prune` 透過此模組的 `prune_dispatches` 完成讀-改-寫，不在本檔
    重新實作鎖與原子寫——該檔曾直接 `dispatch_file.write_text(...)`，
    同時繞過 `_state_lock`（與 `record_dispatch` 等寫入路徑交錯時
    lost update）與 `_write_state` 的原子替換（無鎖讀端可能讀到截斷
    內容）兩層既有防護。
    """
    return load_claude_lib("dispatch_tracker")


def _make_prune_predicate(
    now: datetime, session_ids: Optional[Set[str]]
) -> Any:
    """建立單一 dispatch 條目的清理判準（供 `dispatch_tracker.
    prune_dispatches` 呼叫）。判定條件為 OR，任一成立即清理：

    (A) 既有年齡門檻標為 [STALE]，且 `session_id` 非空但不在 pm-registry
        的 session 集合內（session 存活判準）。`session_id` 為空（無法
        歸戶）或 registry 不可用（`session_ids` 為 None）時，本條件一律
        不成立。
    (B) `ticket_id` 非空，且該票目前狀態為終態（票終態判準，見
        `_is_ticket_terminal`）。獨立於 (A)——不要求 [STALE]，也不受
        registry 是否可用影響。空 `ticket_id`（無票派發）一律不查此
        判準，其清除路徑是 agent 終止事件，非本判準涵蓋範圍。
    """
    registry_available = session_ids is not None

    def _should_remove(entry: Dict[str, Any]) -> bool:
        condition_a = False
        if registry_available:
            is_stale = "[STALE" in _format_age(entry.get("dispatched_at"), now)
            session_id = entry.get("session_id") or ""
            session_exists = bool(session_id) and session_id in session_ids
            condition_a = bool(is_stale and session_id and not session_exists)

        ticket_id = entry.get("ticket_id") or ""
        condition_b = bool(ticket_id) and _is_ticket_terminal(ticket_id)

        return condition_a or condition_b

    return _should_remove


def _log_pruned_entries(removed_entries: List[Dict[str, Any]]) -> None:
    """對每筆已清理的條目寫入 stderr + hook-logs（雙通道，可觀測性規則 4）。"""
    logger = _get_prune_logger()
    for entry in removed_entries:
        message = (
            "[dispatch-check --prune] 已清理 [STALE] 且 session 不存在的條目："
            f"agent={entry.get('agent_description', '(unknown)')} "
            f"ticket={entry.get('ticket_id') or '(no ticket)'} "
            f"session_id={entry.get('session_id') or '(empty)'} "
            f"dispatched_at={entry.get('dispatched_at', '(no timestamp)')}"
        )
        sys.stderr.write(message + "\n")
        if logger:
            logger.info(message)


def execute_dispatch_check(args: argparse.Namespace) -> int:
    """執行 dispatch-check 命令。

    `--prune`：清理「[STALE] 且 session 不存在」的條目後再評估活躍派發。

    Returns:
        0: 無活躍派發（含清理後歸零）；1: 有活躍派發；2: IO/格式錯誤。
    """

    dispatch_file = get_ticket_state_root() / _DISPATCH_ACTIVE_RELPATH

    if not dispatch_file.exists():
        print("[PASS] 無活躍派發，可繼續")
        return 0

    try:
        raw = dispatch_file.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, PermissionError) as e:
        sys.stderr.write(f"[FAIL] dispatch-active.json 讀取失敗: {e}\n")
        return 2
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[FAIL] dispatch-active.json JSON 格式錯誤: {e}\n")
        return 2

    if not isinstance(data, dict):
        sys.stderr.write("[FAIL] dispatch-active.json root 結構不是 dict\n")
        return 2

    dispatches = data.get("dispatches", [])
    if not isinstance(dispatches, list):
        sys.stderr.write("[FAIL] dispatch-active.json dispatches 欄位不是 list\n")
        return 2

    if not dispatches:
        print("[PASS] 無活躍派發，可繼續")
        return 0

    now = datetime.now(timezone.utc)

    if getattr(args, "prune", False):
        session_ids = _load_registry_session_ids()
        registry_available = session_ids is not None
        should_remove = _make_prune_predicate(now, session_ids)

        dispatch_tracker = _load_dispatch_tracker()
        if dispatch_tracker is None:
            sys.stderr.write(
                "[dispatch-check --prune] dispatch_tracker 模組不可用，"
                "本次不清理（fail-open：不在此檔重新實作鎖與原子寫）\n"
            )
            removed_entries: List[Dict[str, Any]] = []
        else:
            dispatches, removed_entries = dispatch_tracker.prune_dispatches(
                get_ticket_state_root(), should_remove
            )

        if removed_entries:
            _log_pruned_entries(removed_entries)
            if registry_available:
                print(
                    f"[INFO] --prune：已清理 {len(removed_entries)} 筆 "
                    "[STALE] 且 session 不存在或票已終態的條目"
                )
            else:
                print(
                    "[INFO] --prune：pm-registry 不可用，session 存活判準略過；"
                    f"依票終態判準已清理 {len(removed_entries)} 筆"
                )
        elif not registry_available:
            print("[INFO] --prune：pm-registry 不可用，無法判定 session 是否存在，本次不清理")
        else:
            print("[INFO] --prune：無符合「[STALE] 且 session 不存在或票已終態」條件的條目")

        if not dispatches:
            print("[PASS] 無活躍派發，可繼續")
            return 0

    stale_count = sum(
        1
        for entry in dispatches
        if isinstance(entry, dict) and "[STALE" in _format_age(entry.get("dispatched_at"), now)
    )
    print(f"[WARN] 有 {len(dispatches)} 個活躍派發：")
    for entry in dispatches:
        if isinstance(entry, dict):
            print(_format_entry(entry, now))
        else:
            print(f"  - (malformed entry: {entry!r})")
    if stale_count:
        print(
            f"[WARN] 其中 {stale_count} 筆逾 {_STALE_THRESHOLD_MIN} 分鐘未見更新"
            "（[STALE] 標記），可能為遺留記錄，建議對照 `track sessions` 或"
            "執行 `dispatch-check --prune`（僅清理 session 確認不存在的條目）"
        )
    return 1


def register_dispatch_check(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 dispatch-check 子命令。"""
    p = subparsers.add_parser(
        "dispatch-check",
        help="檢查 .claude/dispatch-active.json 活躍派發（0=無/1=有/2=IO錯誤）",
    )
    p.add_argument(
        "--prune",
        action="store_true",
        default=False,
        help=(
            "清理 [STALE] 且 session 不存在（比對 pm-registry）的條目，"
            "寫入 .claude/hook-logs/dispatch-check-prune/（3-F M-6）"
        ),
    )
    return p
