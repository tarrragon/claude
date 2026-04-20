"""CheckpointState dataclass + Checkpoint 推導 + 5 層 fail-open 資料來源 + 主函式 + 觀測 log。

派發 1 範圍：dataclass + 決策推導 priority table。
派發 2 範圍：SAFE_CALL + 5 個 _read_* 資料來源。
派發 3 範圍（本次）：
- §4 _write_metrics_log(state, caller, duration_ms, errors) + 10MB rotate（fail-open）
- §1.2 checkpoint_state() 主函式串接 SAFE_CALL → _derive_checkpoint → log

設計依據：Phase 3a §1.2 / §4 / §5；Phase 2 §3 Group D / E。

TD / AD 錨點（W10-017.13 AC5 回填，供後續追溯；完整表見 017.1 worklog §技債追蹤）:
- TD-A: caller 以 Literal 守邊（CheckpointCaller），Phase 4 評估升級 enum → 見
  `CheckpointCaller` 定義附近註解。
- TD-B: get_suggested_commands O(n) 反查 PRIORITIES，現 5 列無效能問題；擴張 > 10
  列再建索引 dict → 見 checkpoint_view.get_suggested_commands。
- TD-C: snapshot 降級 vs full 渲染重複，已 W10-017.11/12 整併至 lib 層 view
  function → 見 commands/track_snapshot._render_degraded_snapshot。
- TD-D: IO_ERRORS 三命令差異，已統一至本檔 IO_ERRORS → 見下方 `IO_ERRORS` 定義。
- TD-E: pyproject testpaths 納入 ticket_system/tests → W10-017.13 AC4 已落地，
  見 pyproject.toml [tool.pytest.ini_options]。
- AD-1: snapshot exit code 永遠 0（fail-open）→ 見 commands/track_snapshot 及
  lib/checkpoint_view.render_ready_check footer。
- AD-2: handoff-ready 在 IO_ERRORS 時 exit 2（保守 NO-GO）→ 見
  commands/track_handoff_ready。
- AD-3: view function 不接收 ticket_id 參數（從 state._ticket_id 取）→ 見本檔
  `CheckpointState._ticket_id` 欄位。
- AD-4: render_ready_check 對 uncommitted_files=None 顯示 [?] → 見
  lib/checkpoint_view.render_ready_check / CheckItem.status="unknown"。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, NamedTuple, Optional, Tuple, TypeVar

from .paths import get_project_root


# CheckpointCaller：caller 欄位型別約束（TD6 / 017.8.4）。
# 包含兩類成員：
#   (1) CLI 三命令實際傳入值：snapshot / handoff-ready / checkpoint-status
#   (2) 未指定 caller 時的 log fallback 值：unknown
# checkpoint_view._VALID_CALLERS 從本 Literal 透過 typing.get_args 派生並過濾掉
# "unknown"，確保 CLI caller 集合單一 source of truth（W10-017.11 AC 1/2）。
# Python runtime 不強制 Literal，型別檢查器（mypy/pyright）會警告誤植。
CheckpointCaller = Literal[
    "snapshot", "handoff-ready", "checkpoint-status", "unknown"
]


# ---------------------------------------------------------------------------
# dataclass 定義（Phase 3a §1.1 / Phase 2 §3 Group A）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendingCheck:
    """未通過檢查項。

    Attributes:
        check_id: 識別字串（如 "data_source_git-status"）。
        reason: 可讀原因描述。
        blocker: 是否阻擋主流程（此 dataclass 為純資料載體，不負責判斷）。
        auto_detectable: 能否被自動偵測（False 表示需人工介入，如 worklog 一致性）。
    """

    check_id: str
    reason: str
    blocker: bool
    auto_detectable: bool


@dataclass
class CheckpointState:
    """Checkpoint 決策狀態（純 state，不含 view 字串）。

    Phase 4 L10 重構（W10-017.8.2）：原 phase_label / next_action 兩個人類可讀
    字串改由 format_phase_label(state) / format_next_action(state) view function
    產生，CheckpointState 保持純 state 不耦合 view 層，便於未來 i18n 擴展。

    欄位分為「推導」與「資料來源」兩類：
    - 推導欄位（由 _derive_checkpoint 等決定）：current_phase / ready_for_clear /
      pending_checks
    - 資料來源欄位（由 _read_* 填入）：active_agents / uncommitted_files /
      unmerged_worktrees / active_handoff / in_progress_tickets
    - 元資訊：data_sources / computed_at

    W10-017.13 AC3：pending_checks 欄位決策「保留」，理由記錄於此：
    - 由 SAFE_CALL 在資料源 I/O 失敗時 append auto_detectable=False 的 PendingCheck
    - ready_for_clear 推導依賴此 list（見 checkpoint_state() Step 4：
      `all(not c.auto_detectable for c in pending)`）
    - 既有測試 test_degraded_snapshot_dry.py 驗證 reason 文字（對外契約）
    - 非 dead field，PC-093 二選一原則此處為「保留 + 文件化」選項
    """

    current_phase: str
    ready_for_clear: bool
    pending_checks: List[PendingCheck]
    active_agents: int
    unmerged_worktrees: List[str]
    active_handoff: Optional[str]
    in_progress_tickets: List[str]
    data_sources: Dict[str, str]
    computed_at: str
    uncommitted_files: Optional[int] = None  # None 表示資料源失敗；0 表示 clean

    # 內部欄位：_derive_checkpoint 需判斷 ticket_id 是否指定
    # 以底線開頭，不計入「公開契約欄位」
    _ticket_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Checkpoint 推導 priority table（Phase 3a §1.4 / Phase 2 §3 Group C）
# ---------------------------------------------------------------------------

# linux Good Taste：用資料結構取代 if/elif 鏈；新增優先級只動資料。
# W10-017.12 AC2：改用 NamedTuple 取代匿名 5-tuple，欄位具名避免匿名 unpack。


class PriorityRule(NamedTuple):
    """單條優先級規則（PRIORITIES 元素）。

    Attributes:
        predicate: (state) -> bool，是否命中此優先級。
        phase: current_phase 字串（如 "1.85"）。
        label: 人類可讀 phase label。
        action_fn: (state) -> str，動態產生 next_action 訊息。
        commands_fn: (state) -> List[str]，產生建議命令清單
            （供 lib/checkpoint_view.py get_suggested_commands 反查）。
    """

    predicate: Callable[[CheckpointState], bool]
    phase: str
    label: str
    action_fn: Callable[[CheckpointState], str]
    commands_fn: Callable[[CheckpointState], List[str]]


class FallbackRule(NamedTuple):
    """PRIORITIES 全數未命中時的 fallback 規則。

    欄位與 PriorityRule 對齊（去除 predicate）。
    """

    phase: str
    label: str
    action_fn: Callable[[CheckpointState], str]
    commands_fn: Callable[[CheckpointState], List[str]]


PRIORITIES: List[PriorityRule] = [
    PriorityRule(
        predicate=lambda s: s.active_agents > 0,
        phase="1.85",
        label="C1.85 代理人運行中",
        action_fn=lambda s: f"等待 {s.active_agents} 個代理人或 ticket track agent-status",
        commands_fn=lambda s: ["ticket track agent-status"],
    ),
    PriorityRule(
        predicate=lambda s: len(s.unmerged_worktrees) > 0,
        phase="1.9",
        label="C1.9 worktree 待合併",
        action_fn=lambda s: f"合併 {len(s.unmerged_worktrees)} 個 worktree 並清理",
        commands_fn=lambda s: [
            "git worktree list",
            "cd <worktree> && git push",
            "cd <main> && git merge",
        ],
    ),
    PriorityRule(
        predicate=lambda s: s.uncommitted_files is not None and s.uncommitted_files > 0,
        phase="1",
        label="C1 未提交變更",
        action_fn=lambda s: f"git add + git commit ({s.uncommitted_files} 檔)",
        commands_fn=lambda s: ["git status", "git add <files>", 'git commit -m "<msg>"'],
    ),
    PriorityRule(
        predicate=lambda s: s.active_handoff is not None,
        phase="2",
        label="C2 handoff 就緒",
        action_fn=lambda s: f"ready for /clear (handoff pending: {s.active_handoff})",
        commands_fn=lambda s: ["/clear"],
    ),
    PriorityRule(
        predicate=lambda s: len(s.in_progress_tickets) > 0 and s._ticket_id is not None,
        phase="0.5",
        label="C0.5 階段進行中",
        action_fn=lambda s: "ticket track append-log 記錄階段進展",
        commands_fn=lambda s: [f"ticket track append-log {s._ticket_id or '<id>'} ..."],
    ),
]

FALLBACK: FallbackRule = FallbackRule(
    phase="3",
    label="C3 流程完成",
    action_fn=lambda s: "ready for /clear 或選下個 Ticket",
    commands_fn=lambda s: ["/clear", "ticket track query --status pending"],
)


def _resolve_rule(state: CheckpointState) -> Tuple[str, str, str, List[str]]:
    """依 PRIORITIES 從高到低找第一個命中的規則，回傳完整詮釋。

    W10-017.12 AC3：合併 _derive_checkpoint 與 get_suggested_commands 為單次
    PRIORITIES loop，避免兩次同構掃描（一次為 phase/label/action，一次為 commands）。

    Args:
        state: 已填入資料來源欄位的 CheckpointState。

    Returns:
        (current_phase, phase_label, next_action, suggested_commands) 四元組。
    """

    for rule in PRIORITIES:
        if rule.predicate(state):
            return rule.phase, rule.label, rule.action_fn(state), rule.commands_fn(state)
    return (
        FALLBACK.phase,
        FALLBACK.label,
        FALLBACK.action_fn(state),
        FALLBACK.commands_fn(state),
    )


def _derive_checkpoint(state: CheckpointState) -> Tuple[str, str, str]:
    """依 PRIORITIES 從高到低找第一個命中的優先級。

    Args:
        state: 已填入資料來源欄位的 CheckpointState。

    Returns:
        (current_phase, phase_label, next_action) 三元組。

    Note:
        W10-017.12 後改為 _resolve_rule 的薄包裝；保留 3-tuple 簽章以維持
        現有測試與呼叫端契約。
    """

    phase, label, action, _commands = _resolve_rule(state)
    return phase, label, action


# ---------------------------------------------------------------------------
# 工具：ISO 時間戳（供 dataclass 建構與測試 freeze_time 使用）
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """回傳目前 UTC 時間的 ISO 8601 字串（含時區資訊）。

    用 datetime.now(timezone.utc) 而非 deprecated utcnow。
    """

    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SAFE_CALL + IO_ERRORS whitelist（Phase 3a §1.3 / Phase 2 §3 Group B）
# ---------------------------------------------------------------------------

# 僅這些 I/O 類例外走 fallback；其他例外（MemoryError/AttributeError/KeyError 等）
# 視為程式 bug 上拋到 checkpoint_state() 主流程，依規則 4 stderr + log 雙通道。
IO_ERRORS: Tuple[type, ...] = (
    subprocess.CalledProcessError,
    subprocess.TimeoutExpired,
    FileNotFoundError,
    PermissionError,
    NotADirectoryError,
    IsADirectoryError,
    json.JSONDecodeError,
    OSError,
)

T = TypeVar("T")


def SAFE_CALL(
    fn: Callable[[], T],
    errors: Dict[str, str],
    pending: List[PendingCheck],
    source: str,
    fallback: T,
) -> T:
    """Fail-open 包裝：I/O 類例外走 fallback 並記錄到 errors/pending。

    捕獲判準（文件化）：
    - 捕獲（走 fallback）：資料來源不可用、權限拒絕、JSON 毀損、subprocess 失敗/超時
    - 不捕獲（上拋）：AttributeError / TypeError / KeyError / MemoryError / ImportError

    Args:
        fn: 不帶參數的可呼叫，執行資料來源讀取。
        errors: 錯誤累積字典（source -> "<ExcName>: <msg>"）；成功時設為 "ok"。
        pending: PendingCheck 累積清單；失敗時追加 auto_detectable=False 標記。
        source: 資料來源識別字串（如 "git-status"）。
        fallback: 失敗時回傳值。

    Returns:
        成功時為 fn() 結果，失敗時為 fallback。
    """

    try:
        result = fn()
    except IO_ERRORS as e:
        errors[source] = f"{type(e).__name__}: {str(e)[:100]}"
        pending.append(
            PendingCheck(
                check_id=f"data_source_{source}",
                reason=f"{source} unavailable: {e}",
                blocker=False,
                auto_detectable=False,
            )
        )
        return fallback
    else:
        errors.setdefault(source, "ok")
        return result


# ---------------------------------------------------------------------------
# 5 層 fail-open 資料來源（Phase 1 §3 / Phase 2 §3 Group B）
# ---------------------------------------------------------------------------

# Phase 1 §3 資料來源路徑規範（相對於 project_root）
_DISPATCH_ACTIVE_RELPATH = Path(".claude/state/dispatch-active.json")
_HANDOFF_PENDING_RELDIR = Path(".claude/handoffs/pending")


def _read_json_dict(path: Path) -> Optional[dict]:
    """讀取 JSON 檔並確保 root 為 dict，統一 I/O + 解析 + 結構檢查 pattern。

    Returns:
        dict: 成功解析且 root 為 dict 時回傳。
        None: 檔案存在可解析但 root 非 dict 時回傳（結構不符，非 I/O 錯誤）。

    Raises:
        FileNotFoundError: 檔案不存在（讓 SAFE_CALL 捕獲走 fallback）。
        PermissionError: 權限拒絕（同上）。
        json.JSONDecodeError: JSON 毀損（同上）。
    """

    raw_text = path.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    return data if isinstance(data, dict) else None

# subprocess 執行超時（秒）
_GIT_CMD_TIMEOUT = 5
_TICKET_CMD_TIMEOUT = 10


def _run_subprocess(
    argv: List[str], cwd: Path, timeout: int
) -> "subprocess.CompletedProcess[str]":
    """統一 subprocess.run 呼叫形狀（capture_output / text / check=True）。

    抽出目的：三處呼叫（git status / ticket query / git worktree）共用同一形狀，
    集中於此避免重複。參數語意與 subprocess.run 一致。

    Raises:
        subprocess.CalledProcessError: 子程序非零退出。
        subprocess.TimeoutExpired: 超時。
        FileNotFoundError: 命令不存在。
    """

    return subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )


def _read_git_status(project_root: Optional[Path] = None) -> int:
    """讀取 git status --porcelain，回傳未提交檔案數。

    Raises:
        subprocess.CalledProcessError: git 非零退出（非 git repo 等）。
        subprocess.TimeoutExpired: 超時。
        FileNotFoundError: git 命令不存在。
    """

    root = project_root or get_project_root()
    result = _run_subprocess(
        ["git", "status", "--porcelain"], root, _GIT_CMD_TIMEOUT
    )
    # 每一行代表一個變更檔案；空輸出 = 0
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return len(lines)


def _read_dispatch_active(
    project_root: Optional[Path] = None,
) -> Tuple[int, Dict[str, Any]]:
    """讀取 .claude/state/dispatch-active.json，回傳 (active_agents, raw_dict)。

    語意：dispatches 欄位中未完成（status != "completed"）的項目數。
    Phase 1 §3：缺檔時 active_agents=0（由 SAFE_CALL 捕 FileNotFoundError 走 fallback）。

    Raises:
        FileNotFoundError: 檔案或目錄不存在（含 .claude/state/ 整個目錄不存在）。
        PermissionError: 權限拒絕。
        json.JSONDecodeError: JSON 毀損。
    """

    root = project_root or get_project_root()
    path = root / _DISPATCH_ACTIVE_RELPATH
    # 注意：Path.read_text 對目錄不存在與檔案不存在皆拋 FileNotFoundError
    data = _read_json_dict(path)
    if data is None:
        # 非 dict 視為資料毀損；用 JSONDecodeError 以讓 SAFE_CALL 捕獲
        raise json.JSONDecodeError(
            "dispatch-active.json root is not a dict", "", 0
        )
    dispatches = data.get("dispatches", [])
    if not isinstance(dispatches, list):
        return 0, data
    active_count = sum(
        1
        for d in dispatches
        if isinstance(d, dict) and d.get("status") != "completed"
    )
    return active_count, data


def _read_handoff_pending(
    project_root: Optional[Path] = None,
) -> Optional[str]:
    """讀取 .claude/handoffs/pending/*.json，回傳最新 handoff 的 ticket_id。

    語意：目錄中有任何 *.json 即視為 active_handoff；多個時取 mtime 最新的。
    Phase 1 §3：缺目錄時回 None（由 SAFE_CALL 捕 FileNotFoundError 走 fallback）。

    Raises:
        FileNotFoundError: 目錄不存在（Phase 2 §B.5 明列情境）。
        PermissionError: 權限拒絕。
        json.JSONDecodeError: JSON 毀損。
    """

    root = project_root or get_project_root()
    pending_dir = root / _HANDOFF_PENDING_RELDIR
    # iterdir 對不存在目錄拋 FileNotFoundError → SAFE_CALL 走 fallback
    json_files = [p for p in pending_dir.iterdir() if p.suffix == ".json"]
    if not json_files:
        return None
    # 取 mtime 最新者
    latest = max(json_files, key=lambda p: p.stat().st_mtime)
    data = _read_json_dict(latest)
    if data is None:
        return None
    ticket_id = data.get("ticket_id")
    return ticket_id if isinstance(ticket_id, str) else None


def _query_in_progress_tickets(
    project_root: Optional[Path] = None,
) -> List[str]:
    """透過 `ticket track query --status in_progress` 取當前 in_progress ticket IDs。

    Raises:
        subprocess.CalledProcessError: ticket CLI 非零退出。
        subprocess.TimeoutExpired: 超時。
        FileNotFoundError: ticket 命令不存在。
        json.JSONDecodeError: 輸出非合法 JSON。
    """

    root = project_root or get_project_root()
    result = _run_subprocess(
        ["ticket", "track", "query", "--status", "in_progress", "--format", "json"],
        root,
        _TICKET_CMD_TIMEOUT,
    )
    out = result.stdout.strip()
    if not out:
        return []
    data = json.loads(out)
    # 預期 list-of-dict，每個含 id 或 ticket_id 欄位
    if not isinstance(data, list):
        return []
    ids: List[str] = []
    for item in data:
        if isinstance(item, dict):
            tid = item.get("id") or item.get("ticket_id")
            if isinstance(tid, str):
                ids.append(tid)
        elif isinstance(item, str):
            ids.append(item)
    return ids


def _read_git_worktrees(project_root: Optional[Path] = None) -> List[str]:
    """透過 `git worktree list --porcelain` 取未合併的 worktree 路徑清單。

    語意：排除主 worktree（cwd 所在）；僅回傳 linked worktree 的 path。

    Raises:
        subprocess.CalledProcessError: git 非零退出。
        subprocess.TimeoutExpired: 超時。
        FileNotFoundError: git 命令不存在。
    """

    root = project_root or get_project_root()
    result = _run_subprocess(
        ["git", "worktree", "list", "--porcelain"], root, _GIT_CMD_TIMEOUT
    )
    # porcelain 格式：每段以空行分隔，段內首行 "worktree <path>"
    paths: List[str] = []
    main_path = str(root.resolve())
    for block in result.stdout.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("worktree "):
                wt_path = line[len("worktree "):].strip()
                # 排除主 worktree
                try:
                    resolved = str(Path(wt_path).resolve())
                except OSError:
                    resolved = wt_path
                if resolved != main_path:
                    paths.append(wt_path)
                break
    return paths


# ---------------------------------------------------------------------------
# 觀測 log 寫入（Phase 3a §4 / Phase 2 §3 Group D）
# ---------------------------------------------------------------------------

# Phase 3a §4：log 路徑與 rotate 策略
_METRICS_LOG_RELPATH = Path(".claude/logs/pm-automation-metrics.jsonl")
_METRICS_LOG_ROTATE_BYTES = 10 * 1024 * 1024  # 10 MB
# 保留的歷史份數（.1.jsonl ~ .N.jsonl）。W10-017.8.3 (TD3) 由 1 擴充為 3。
_METRICS_LOG_ROTATE_KEEP = 3


def _rotate_metrics_log(log_path: Path, keep: int = _METRICS_LOG_ROTATE_KEEP) -> None:
    """滾動 metrics log：log → .1 → .2 → ... → .N，超過 N 份則丟棄最舊。

    例：keep=3 時，原檔 → .1.jsonl，舊 .1 → .2.jsonl，舊 .2 → .3.jsonl，
    舊 .3.jsonl 被覆蓋丟棄。

    此函式僅在呼叫端已判定需要 rotate 時被呼叫；不自行檢查檔案大小。
    """

    # 從最舊往新滾動，避免覆蓋還未搬移的檔案
    # i = keep, keep-1, ..., 2：將 .{i-1}.jsonl rename 為 .{i}.jsonl
    for i in range(keep, 1, -1):
        src = log_path.with_suffix(f".{i - 1}.jsonl")
        dst = log_path.with_suffix(f".{i}.jsonl")
        if src.exists():
            if dst.exists():
                dst.unlink()
            src.rename(dst)
    # 最後將原檔 → .1.jsonl
    first = log_path.with_suffix(".1.jsonl")
    if first.exists():
        first.unlink()
    log_path.rename(first)


def _write_metrics_log(
    state: CheckpointState,
    caller: Optional[CheckpointCaller],
    duration_ms: float,
    errors: Dict[str, str],
    *,
    project_root: Optional[Path] = None,
) -> None:
    """Append 一行 JSONL 到 pm-automation-metrics.jsonl（fail-open）。

    Schema（Phase 3a §4.1 / Phase 2 §3 Group D1）：
        ts / event / caller / ticket_id / current_phase / ready_for_clear
        / active_agents / uncommitted_files / duration_ms / data_source_errors

    Rotate：檔案 > 10 MB 時滾動為 .1/.2/.../.N.jsonl（預設保留 N=3 份），
    新檔從 0 開始；超過 N 份則丟棄最舊的 .N。

    Fail-open（規則 4 雙通道）：寫入失敗時 stderr warning + 不阻斷主流程。
    呼叫端（checkpoint_state）另外以 try/except 包住此函式本身保底。
    """

    root = project_root or get_project_root()
    log_path = root / _METRICS_LOG_RELPATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Rotate（預寫檢查）
    try:
        if log_path.exists() and log_path.stat().st_size > _METRICS_LOG_ROTATE_BYTES:
            _rotate_metrics_log(log_path, keep=_METRICS_LOG_ROTATE_KEEP)
    except OSError as rot_err:
        # rotate 失敗不阻斷；stderr warning 但繼續寫原檔
        sys.stderr.write(
            f"[checkpoint_state] metrics log rotate failed: {rot_err}\n"
        )

    data_source_errors = [k for k, v in errors.items() if v != "ok"]

    entry = {
        "ts": state.computed_at,
        "event": "checkpoint_state",
        "caller": caller or "unknown",
        "ticket_id": state._ticket_id or "",
        "current_phase": state.current_phase,
        "ready_for_clear": state.ready_for_clear,
        "active_agents": state.active_agents,
        "uncommitted_files": state.uncommitted_files,
        "duration_ms": round(duration_ms, 2),
        "data_source_errors": data_source_errors,
    }

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# DATA_SOURCES table（與 PRIORITIES 同構 table-driven）
# ---------------------------------------------------------------------------

# 每筆 (state_field, source_name, reader, fallback, extractor)：
#   state_field: 寫入 collected dict 的 key（供主函式組裝 state 使用）
#   source_name: SAFE_CALL 用的 source 識別字串（errors/pending 追蹤用）
#   reader(root) -> Any：資料來源讀取函式（接受 project_root）
#   fallback: SAFE_CALL 失敗時 fallback 值
#   extractor(raw) -> Any：將 reader 回傳值正規化為 state 欄位值
#     （預設恆等；dispatch-active 回 (count, dict) 需取 [0]）
DATA_SOURCES: List[
    Tuple[str, str, Callable[[Path], Any], Any, Callable[[Any], Any]]
] = [
    (
        "uncommitted_files",
        "git-status",
        _read_git_status,
        None,
        lambda r: r,
    ),
    (
        "active_agents",
        "dispatch-active",
        _read_dispatch_active,
        (0, {}),
        lambda r: r[0],
    ),
    (
        "active_handoff",
        "handoff-pending",
        _read_handoff_pending,
        None,
        lambda r: r,
    ),
    (
        "in_progress_tickets",
        "ticket-query",
        _query_in_progress_tickets,
        [],
        lambda r: r,
    ),
    (
        "unmerged_worktrees",
        "git-worktree",
        _read_git_worktrees,
        [],
        lambda r: r,
    ),
]


# ---------------------------------------------------------------------------
# View functions（Phase 4 L10 重構：view 與 state 解耦，便於 i18n 擴展）
# ---------------------------------------------------------------------------


def format_phase_label(state: CheckpointState) -> str:
    """回傳 state 對應的人類可讀 phase label（如 "C3 流程完成"）。

    從 CheckpointState 抽出的 view function，不持有於 dataclass 欄位上，
    便於未來 i18n 擴展（傳入 locale 參數切換語言）。
    """

    _phase, label, _action = _derive_checkpoint(state)
    return label


def format_next_action(state: CheckpointState) -> str:
    """回傳 state 對應的人類可讀 next_action 建議訊息。

    從 CheckpointState 抽出的 view function，不持有於 dataclass 欄位上，
    便於未來 i18n 擴展。
    """

    _phase, _label, action = _derive_checkpoint(state)
    return action


# ---------------------------------------------------------------------------
# checkpoint_state() 主函式（Phase 3a §1.2 整合）
# ---------------------------------------------------------------------------


def checkpoint_state(
    ticket_id: Optional[str] = None,
    *,
    log_metrics: bool = True,
    caller: Optional[CheckpointCaller] = None,
    project_root: Optional[Path] = None,
) -> CheckpointState:
    """整合 5 層 SAFE_CALL 資料收集 → _derive_checkpoint → metrics log。

    Args:
        ticket_id: 當前 ticket 識別（None = 使用 in_progress 推導）。
        log_metrics: False 時不寫 metrics log（單元測試隔離）。
        caller: 呼叫端識別（"snapshot"/"handoff-ready"/"checkpoint-status"），寫入 log caller 欄位。
        project_root: 測試注入用；預設呼叫 get_project_root()。

    Returns:
        CheckpointState（已填完所有欄位 + computed_at + data_sources）。
    """

    start = time.perf_counter()
    root = project_root or get_project_root()

    errors: Dict[str, str] = {}
    pending: List[PendingCheck] = []

    # Step 1：5 層 fail-open 資料收集（table-driven，與 PRIORITIES 同構）
    collected: Dict[str, Any] = {}
    for field_name, source, reader, fallback, extractor in DATA_SOURCES:
        raw = SAFE_CALL(
            lambda r=reader: r(root),
            errors, pending, source, fallback=fallback,
        )
        collected[field_name] = extractor(raw)

    # Step 2：先組半成品 state 讓 _derive_checkpoint 可查
    state = CheckpointState(
        current_phase="",
        ready_for_clear=False,
        pending_checks=pending,
        active_agents=collected["active_agents"],
        unmerged_worktrees=collected["unmerged_worktrees"],
        active_handoff=collected["active_handoff"],
        in_progress_tickets=collected["in_progress_tickets"],
        data_sources=dict(errors),
        computed_at=_utc_now_iso(),
        uncommitted_files=collected["uncommitted_files"],
        _ticket_id=ticket_id,
    )

    # Step 3：推導 Checkpoint phase（view 字串由 format_* 函式按需產生）
    phase, _label, _action = _derive_checkpoint(state)
    state.current_phase = phase

    # Step 4：ready_for_clear
    state.ready_for_clear = (
        phase in {"2", "3"}
        and all(not c.auto_detectable for c in pending)
    )

    duration_ms = (time.perf_counter() - start) * 1000.0

    # Step 5：觀測 log（fail-open；規則 4 stderr + log 雙通道）
    if log_metrics:
        try:
            _write_metrics_log(state, caller, duration_ms, errors, project_root=root)
        except (OSError, json.JSONDecodeError, TypeError) as e:
            # fail-open 邊界；規則 4 stderr 保留可見性
            # whitelist 對齊 SAFE_CALL IO_ERRORS 哲學（檔案 I/O + JSON + 序列化）
            sys.stderr.write(
                f"[checkpoint_state] metrics log write failed: "
                f"{type(e).__name__}: {e}\n"
            )

    return state


# 公開 API 只含外部呼叫端需要的符號。
# 私有符號（_ 前綴）仍可透過明確 import 名稱存取（供測試直接測試），
# 但不會在 `from checkpoint_state import *` 時被匯出，避免過度暴露。
__all__ = [
    "checkpoint_state",
    "CheckpointState",
    "PendingCheck",
    "CheckpointCaller",
    "format_phase_label",
    "format_next_action",
    "DATA_SOURCES",
    "PRIORITIES",
    "PriorityRule",
    "FallbackRule",
]
