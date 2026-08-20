"""Lease 生命週期管理（multi-PM 協調層 Phase 3：claim/complete/release/reclaim）。

claim/complete/release 對稱寫入 `.claude/lib/pm_registry.py` 的 lease 欄位
（session entry 的 tickets/files），並提供 `ticket track reclaim` 所需的
reclaim 前 ghost 鑑識三查（PC-166 防護 D 同款）。

層級邊界：本模組刻意不 import `ticket_system.commands.*`（lib 依賴方向單向
朝下，commands 依賴 lib，不可反向）。交集判定（`files_intersect` /
`where_files`）改為 import 同層 `ticket_system.lib.file_conflict`（AC-3
共用實作，Phase 4 審查修正：先前本模組自帶一份簡化複本，與
`track_conflicts.py` 邏輯有分裂風險，已刪除改為單一來源）。

registry 讀寫一律經 `.claude/lib/pm_registry` 動態載入（lazy import 經
`ticket_system.lib.claude_lib_loader` 共用實作）；git 查詢
（branch/status）一律經 `.claude/lib/git_utils.run_git_command`（已內建
`--no-optional-locks`，避免與並行 PM session 競爭 `.git/index.lock`）。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ticket_system.constants import STATUS_IN_PROGRESS, STATUS_PENDING
from ticket_system.lib.claude_lib_loader import (
    empty_registry_skeleton,
    load_claude_lib,
    resolve_toplevel,
)
from ticket_system.lib.file_conflict import files_intersect, where_files, write_files
from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.section_locator import find_section
from ticket_system.lib.ticket_loader import get_ticket_path, load_ticket, save_ticket
from ticket_system.lib.ticket_ops import load_and_validate_ticket, resolve_ticket_path
from ticket_system.lib.ticket_validator import (
    _is_placeholder,
    extract_version_from_ticket_id,
)

# 與 .claude/lib/hook_logging.py 的 ENV_SESSION_ID 一致。
ENV_SESSION_ID = "CLAUDE_CODE_SESSION_ID"


# ============================================================================
# Lib 載入：lazy import `.claude/lib/{pm_registry,git_utils}`
# （收斂自五處近乎相同複本，共用實作見 ticket_system.lib.claude_lib_loader）
# ============================================================================


def _load_pm_registry():
    """Lazy 載入 `.claude/lib/pm_registry`（薄封裝，保留模組內名稱供既有
    測試 `monkeypatch.setattr(lease, "_load_pm_registry", ...)` 直接覆寫）。"""
    return load_claude_lib("pm_registry")


def _load_git_utils():
    """Lazy 載入 `.claude/lib/git_utils`（薄封裝，同 `_load_pm_registry`）。"""
    return load_claude_lib("git_utils")


def _run_git_lines(args: List[str], cwd: Optional[str] = None) -> Optional[List[str]]:
    """執行 git 命令並回傳 stdout 行清單。

    查詢本身失敗（git_utils 模組不可用，或 `run_git_command` 回傳失敗）時
    回傳 `None`——不可與「查詢成功但無輸出」的空清單 `[]` 混為一談。Phase 4
    審查修正 1：舊版兩種情形皆回傳 `[]`，使 ghost 鑑識把「查不到」與「查詢
    失敗」都當「無命中」，查詢失敗時反而放行（安全方向錯誤——失敗應偏向
    拒絕，非偏向通過）。呼叫端（`run_ghost_forensics`）須依 `None` 標記
    對應檢查項為「無法判定」，`reclaim_ticket` 的 `--confirm` 路徑遇任一
    「無法判定」即拒絕。
    """
    git_utils = _load_git_utils()
    if git_utils is None:
        return None
    ok, output = git_utils.run_git_command(args, cwd=cwd)
    if not ok:
        return None
    if not output:
        return []
    return output.splitlines()


# ============================================================================
# 路徑判定
# ============================================================================


def _current_project_root() -> Optional[str]:
    """取得當前 git toplevel 絕對路徑字串，供 registry `project` 欄位比對。
    核心解析算法（git rev-parse --show-toplevel + 路徑正規化）收斂至
    `ticket_system.lib.claude_lib_loader.resolve_toplevel`；本模組繼續
    提供 `_run_git_lines` 包裝為執行 callable，既有測試對 `_run_git_lines`
    的直接 patch 不受影響。
    """
    def _run_git(*args: str) -> Optional[str]:
        lines = _run_git_lines(list(args))
        return lines[0].strip() if lines else None

    return resolve_toplevel(_run_git)


# ============================================================================
# session_id 解析
# ============================================================================


def _resolve_session_id(
    pm_registry, registry: Dict[str, Any], project_root: str, now: datetime
) -> Optional[str]:
    """解析當前 CLI 呼叫所屬 session_id。

    優先序：
    1. `CLAUDE_CODE_SESSION_ID` 環境變數（CC runtime 對所有子行程曝露）。
    2. registry 內與當前專案相符的唯一 FRESH session（找不到、或找到多筆
       同專案 FRESH session 時無法唯一判定，回傳 None）。

    兩者皆缺時回傳 None，呼叫端 stderr 告知並跳過 registry 寫入
    （不可虛構 session_id，Context Bundle 明文約束）。
    """
    env_value = os.environ.get(ENV_SESSION_ID, "").strip()
    if env_value:
        return env_value

    sessions = registry.get("sessions")
    if not isinstance(sessions, dict):
        return None

    matches = [
        sid
        for sid, data in sessions.items()
        if isinstance(data, dict)
        and data.get("project") == project_root
        and pm_registry.is_fresh(data.get("heartbeat_ts"), now)
    ]
    return matches[0] if len(matches) == 1 else None


def _find_lease_owner(registry: Dict[str, Any], ticket_id: str) -> Optional[str]:
    """回傳持有 ticket_id lease 的 session_id；registry 未追蹤該票時回傳 None。"""
    sessions = registry.get("sessions")
    if not isinstance(sessions, dict):
        return None
    for session_id, data in sessions.items():
        if not isinstance(data, dict):
            continue
        if ticket_id in (data.get("tickets") or []):
            return session_id
    return None


def load_registry_snapshot() -> Tuple[Dict[str, Any], Any]:
    """讀取當前 registry 快照，供 `sessions` / `runqueue` 等顯示層一次性載入
    （避免每筆列都各自觸發模組載入 + 檔案讀取）。

    Returns:
        (registry_dict, pm_registry_module_or_None) —— registry 不可用（模組
        載入失敗 / 非 git 環境）時回傳空骨架 + None，呼叫端應視為「無法判定，
        不標記 reclaimable」而非報錯（保守降級：無法判定時不標記，同
        Registry Schema 契約既有語意）。
    """
    pm_registry = _load_pm_registry()
    if pm_registry is None:
        return empty_registry_skeleton(), None
    paths = pm_registry.get_registry_paths()
    if paths is None:
        return empty_registry_skeleton(), None
    registry = pm_registry.read_registry(paths[0])
    return registry, pm_registry


# 顯示層 lease 三態（`dashboard` In Progress 標記用，CQ-001 防護：公開入口
# 供跨模組呼叫，避免呼叫端直接 import 本模組的 `_find_lease_owner` 私有函式）。
LEASE_STATE_LIVE = "live"
LEASE_STATE_RECLAIMABLE = "reclaimable"
LEASE_STATE_UNTRACKED = "untracked"


def determine_lease_state(
    registry: Dict[str, Any], ticket_id: Optional[str], pm_registry, now: datetime
) -> str:
    """顯示層通用判定：ticket_id 的 lease 三態。

    判準與 `is_lease_reclaimable` 同源（`_find_lease_owner` + `pm_registry.is_fresh`），
    僅將其布林結果拆為三態：registry 不可用或未追蹤該票 -> LEASE_STATE_UNTRACKED；
    owner 為 FRESH session -> LEASE_STATE_LIVE（不可接手）；owner 為 STALE
    session -> LEASE_STATE_RECLAIMABLE（走 reclaim 鑑識）。降級語意對齊
    `is_lease_reclaimable`——無法判定時不標記，不宣稱可接手。
    """
    if pm_registry is None or not ticket_id:
        return LEASE_STATE_UNTRACKED
    owner = _find_lease_owner(registry, ticket_id)
    if owner is None:
        return LEASE_STATE_UNTRACKED
    owner_data = (registry.get("sessions") or {}).get(owner) or {}
    if pm_registry.is_fresh(owner_data.get("heartbeat_ts"), now):
        return LEASE_STATE_LIVE
    return LEASE_STATE_RECLAIMABLE


def is_lease_reclaimable(
    registry: Dict[str, Any], ticket_id: str, pm_registry, now: datetime
) -> bool:
    """顯示層輕量判定（`sessions` / `runqueue` 用）：ticket_id 是否被 registry
    中某已知 STALE session 持有。

    僅檢查 heartbeat 新鮮度（父票設計要點 2 的判準），不含 `reclaim_ticket`
    實際執行前的 ghost 鑑識三查——鑑識涉及 git 呼叫，不適合逐票渲染表格時
    觸發。`pm_registry` 不可用或 registry 未追蹤該票時回傳 False（保守：
    僅標示已知確定為 STALE 的持票，不臆測）。
    """
    owner = _find_lease_owner(registry, ticket_id)
    if owner is None or pm_registry is None:
        return False
    owner_data = (registry.get("sessions") or {}).get(owner) or {}
    return not pm_registry.is_fresh(owner_data.get("heartbeat_ts"), now)


def resolve_current_session_id() -> Optional[str]:
    """通用 session_id 解析入口，供 claim/reclaim 情境之外的呼叫端複用
    （例如 ticket md auto-commit 的 Session trailer 歸屬）。

    解析順序與 `claim_lease` 內部呼叫的 `_resolve_session_id` 一致：
    `CLAUDE_CODE_SESSION_ID` 環境變數優先，其次 registry 內與當前專案
    相符的唯一 FRESH session。任一步驟不可用（模組載入失敗 / 非 git
    環境 / 無法唯一判定）一律回傳 `None`，呼叫端不可虛構 session_id
    （同 claim_lease 契約）。
    """
    env_value = os.environ.get(ENV_SESSION_ID, "").strip()
    if env_value:
        return env_value

    registry, pm_registry = load_registry_snapshot()
    if pm_registry is None:
        return None
    project_root = _current_project_root()
    if project_root is None:
        return None
    now = datetime.now(timezone.utc)
    return _resolve_session_id(pm_registry, registry, project_root, now)


def _make_files_loader(fallback_version: str):
    """建立 `pm_registry.recompute_lease` 所需的 files_loader 閉包。

    files 欄位是 tickets 的推導物化值（非獨立累積狀態，設計裁決見團隊
    裁示）：每次 lease 事件皆以「調整後 tickets 清單當下的 write 集合
    聯集」整組重算覆蓋（並行安全判定改用 write 集合，ANA 型全唯讀宣告
    不再計入 registry.files），不做增量 append/merge——票面 where.files
    改窄後重跑 claim，registry.files 需同步縮窄，否則 track_conflicts 的
    registry/票面交叉比對會產生假陰性。

    `fallback_version` 供 ticket_id 無法從自身格式解析版本時使用（理論上
    不應發生，tickets 皆為 `{version}-W{wave}-{seq}` 格式，仍防禦）。
    """

    def _loader(ticket_id: str) -> List[str]:
        version = extract_version_from_ticket_id(ticket_id) or fallback_version
        ticket = load_ticket(version, ticket_id)
        if ticket is None:
            return []
        return write_files(ticket)

    return _loader


# ============================================================================
# claim 前置衝突警告（Phase 2 缺口 1、2 落地：僅比對 FRESH，不硬擋）
# ============================================================================


def _warn_fresh_conflicts(
    pm_registry,
    registry: Dict[str, Any],
    self_session_id: str,
    ticket_files: List[str],
    project_root: str,
    now: datetime,
) -> None:
    """claim 前置衝突檢查：比對其他 FRESH session 已宣告的 files，命中僅
    輸出警告，不阻擋 claim（父票設計要點 1）。
    """
    sessions = registry.get("sessions")
    if not isinstance(sessions, dict) or not ticket_files:
        return

    for session_id, data in sessions.items():
        if session_id == self_session_id or not isinstance(data, dict):
            continue
        if data.get("project") != project_root:
            continue
        if not pm_registry.is_fresh(data.get("heartbeat_ts"), now):
            continue

        other_files = data.get("files") or []
        matched = sorted({
            (tf if tf == of else f"{tf} ~ {of}")
            for tf in ticket_files
            for of in other_files
            if files_intersect(tf, of)
        })
        if matched:
            sys.stderr.write(
                f"[lease] 檔案宣告與 session {session_id} 的 FRESH lease 有交集："
                f"{', '.join(matched)}（僅警告，不阻擋 claim）\n"
            )


# ============================================================================
# claim / release 公開入口
# ============================================================================


def claim_lease(version: str, ticket_id: str) -> None:
    """claim 成功後呼叫：寫入 registry lease（自身 session tickets 加入本票，
    files 依調整後 tickets 清單整組重算覆蓋，非增量併入）+ FRESH session
    前置衝突警告。

    任何一步不可用（模組載入失敗 / 非 git 環境 / session_id 無法解析 /
    registry 無對應 entry）一律 stderr 告知並跳過，不影響已完成的 claim
    主流程——lease 寫入是 claim 的附加動作而非前提，契約降級語意與
    Phase 1/2 registry 讀寫一致。
    """
    ticket = load_ticket(version, ticket_id)
    if ticket is None:
        return
    ticket_files = write_files(ticket)

    pm_registry = _load_pm_registry()
    if pm_registry is None:
        sys.stderr.write("[lease] pm_registry 模組不可用，跳過 lease 寫入\n")
        return

    paths = pm_registry.get_registry_paths()
    if paths is None:
        sys.stderr.write("[lease] 非 git 環境，跳過 lease 寫入\n")
        return
    registry_file, lock_file = paths

    now = datetime.now(timezone.utc)
    registry = pm_registry.read_registry(registry_file)
    project_root = _current_project_root()
    if project_root is None:
        sys.stderr.write("[lease] 無法解析 git toplevel，跳過 lease 寫入\n")
        return

    session_id = _resolve_session_id(pm_registry, registry, project_root, now)
    if session_id is None:
        sys.stderr.write(
            "[lease] 無法判定當前 session_id（CLAUDE_CODE_SESSION_ID 未設定，"
            "且 registry 無法唯一匹配 FRESH session），跳過 lease 寫入\n"
        )
        return

    _warn_fresh_conflicts(pm_registry, registry, session_id, ticket_files, project_root, now)

    ok = pm_registry.recompute_lease(
        registry_file,
        lock_file,
        session_id,
        add_ticket_id=ticket_id,
        files_loader=_make_files_loader(version),
    )
    if not ok:
        sys.stderr.write(
            f"[lease] registry 無 session {session_id} 的 entry，跳過 lease 寫入\n"
        )


def release_lease(version: str, ticket_id: str) -> None:
    """complete/release 成功後呼叫：從 registry 移除本票 lease（tickets 移除
    + files 依剩餘 tickets 整組重算覆蓋，非增量移除）。

    找不到持有本票的 session 時視為無 lease 可清（正常情況，例如 claim
    時 lease 寫入已因故降級跳過），靜默返回，不視為錯誤。
    """
    pm_registry = _load_pm_registry()
    if pm_registry is None:
        return
    paths = pm_registry.get_registry_paths()
    if paths is None:
        return
    registry_file, lock_file = paths
    registry = pm_registry.read_registry(registry_file)

    owner = _find_lease_owner(registry, ticket_id)
    if owner is None:
        return

    pm_registry.recompute_lease(
        registry_file,
        lock_file,
        owner,
        remove_ticket_id=ticket_id,
        files_loader=_make_files_loader(version),
    )


def check_release_guard(ticket_id: str, now: Optional[datetime] = None) -> Tuple[bool, str]:
    """`ticket track release` 前置閘門：ticket_id 由「非自身」FRESH session
    持有時拒絕，呼叫端須依 `--force-release-others` 顯式旁路。

    release 先前對任何 in_progress 票不查 lease owner/FRESH 即轉 pending
    並清 registry lease，可完全繞過 reclaim 三道防線（STALE 判定 + ghost
    鑑識三查 + `--confirm`），並行 PM 誤操作會清掉活 session 的 lease。
    本函式補上與 `claim_lease` 對稱的前置檢查。

    fail-open 設計（與 `check_reclaimable` 的 fail-closed 方向相反，是刻意
    的）：release 是常用命令，lease 僅為附加防護層，任一步驟不可用（模組
    載入失敗 / 非 git 環境 / session_id 無法解析 / registry 未追蹤此票）
    一律放行，不阻塞正常釋放流程。`check_reclaimable` 操作的是「他人持有」
    的票，本質是破門而入，寧可誤拒也不可誤放；兩者防護方向依操作語意各自
    獨立設計，非共用同一保守原則。

    Args:
        now: 供測試注入固定時間點（同 `reclaim_ticket` 的 `now` 慣例），
            預設 None 時採用真實 UTC 現在時刻。

    Returns:
        (allowed, reason) —— allowed=False 時 reason 為警告文字，供呼叫端
        輸出並要求顯式 `--force-release-others`；allowed=True 時 reason
        附放行原因（供除錯與測試斷言）。
    """
    registry, pm_registry = load_registry_snapshot()
    if pm_registry is None:
        return True, f"{ticket_id}: pm_registry 模組不可用，無法判定 lease owner，允許 release"

    owner = _find_lease_owner(registry, ticket_id)
    if owner is None:
        return True, f"{ticket_id}: registry 未追蹤此票 lease，允許 release"

    now = now or datetime.now(timezone.utc)
    project_root = _current_project_root()
    self_session_id = (
        _resolve_session_id(pm_registry, registry, project_root, now)
        if project_root is not None
        else None
    )
    if self_session_id is not None and owner == self_session_id:
        return True, f"{ticket_id}: 由自身 session 持有，允許 release"

    owner_data = (registry.get("sessions") or {}).get(owner) or {}
    if not pm_registry.is_fresh(owner_data.get("heartbeat_ts"), now):
        return True, f"{ticket_id}: 持有 session {owner} 已逾時（STALE），允許 release"

    return (
        False,
        f"{ticket_id} 由其他存活中的 session {owner}（FRESH）持有，"
        "release 會清除其 lease、可能繞過 reclaim 三道防線；"
        "如確認要強制釋放，請加 --force-release-others",
    )


# ============================================================================
# reclaim：ghost 鑑識三查
# ============================================================================


@dataclass
class GhostReport:
    """reclaim 前 ghost 鑑識三查結果（PC-166 防護 D 同款：任一命中即拒絕；
    Phase 4 審查修正 1：查詢本身失敗的「無法判定」亦視為拒絕，不與「查詢
    成功且無命中」的通過混淆——見 `unmerged_branch_unknown` /
    `dirty_intersection_unknown`）。
    """

    unmerged_branch: bool = False
    unmerged_branch_names: List[str] = field(default_factory=list)
    unmerged_branch_unknown: bool = False
    dirty_intersection: bool = False
    dirty_files: List[str] = field(default_factory=list)
    dirty_intersection_unknown: bool = False
    exit_status_missing: bool = False

    @property
    def clean(self) -> bool:
        return not (
            self.unmerged_branch
            or self.dirty_intersection
            or self.exit_status_missing
            or self.unmerged_branch_unknown
            or self.dirty_intersection_unknown
        )


def _dirty_file_paths(status_lines: List[str]) -> List[str]:
    """由已取得的 `git status --porcelain` 行清單解出路徑（rename 取新
    路徑），複用 `.claude/lib/git_utils.FileStatus` 的欄位切分常數
    （`GIT_STATUS_CODE_LEN`），不重寫解析邏輯（Phase 4 審查修正 7）。

    `git_utils` 不可用時退回原生切片長度 2（porcelain 格式恆定，同
    `GIT_STATUS_CODE_LEN` 現行值），僅為極端降級路徑防禦。
    """
    git_utils = _load_git_utils()
    code_len = git_utils.GIT_STATUS_CODE_LEN if git_utils is not None else 2

    paths: List[str] = []
    for line in status_lines:
        if len(line) < code_len + 1:
            continue
        file_path = line[code_len + 1:]
        if " -> " in file_path:
            file_path = file_path.split(" -> ", 1)[1].strip()
        file_path = file_path.strip('"')
        if file_path:
            paths.append(file_path)
    return paths


def run_ghost_forensics(ticket_id: str, ticket_files: List[str], body: str) -> GhostReport:
    """執行 reclaim 前 ghost 鑑識三查：

    1. 未合併分支：`git branch --no-merged` 中存在含 ticket_id 的分支名。
    2. 髒檔交集：`git status --porcelain` 路徑與 ticket_files 有交集。
    3. 缺 Exit Status：票面 Exit Status 章節仍為佔位符 / 未找到。

    第 1、2 查依賴 git 查詢，查詢本身失敗（`_run_git_lines` 回傳 `None`）
    時標記對應 `*_unknown` 欄位為 `True`（無法判定，非「無命中」，見
    `GhostReport.clean`）。第 3 查為純票面內容比對，不受此影響。
    """
    report = GhostReport()

    branch_lines = _run_git_lines(["branch", "--no-merged"])
    if branch_lines is None:
        report.unmerged_branch_unknown = True
    else:
        for line in branch_lines:
            name = line.strip().lstrip("* ").strip()
            if ticket_id in name:
                report.unmerged_branch = True
                report.unmerged_branch_names.append(name)

    if ticket_files:
        status_lines = _run_git_lines(["status", "--porcelain"])
        if status_lines is None:
            report.dirty_intersection_unknown = True
        else:
            for dirty_path in _dirty_file_paths(status_lines):
                for tf in ticket_files:
                    if files_intersect(dirty_path, tf):
                        report.dirty_intersection = True
                        report.dirty_files.append(dirty_path)
                        break

    section = find_section(body or "", "Exit Status")
    if not section.found or _is_placeholder(section.content):
        report.exit_status_missing = True

    return report


def _check_status_label(hit: bool, unknown: bool) -> str:
    """三查單項狀態標籤：無法判定優先於命中/通過（查詢失敗時不可宣稱通過）。"""
    if unknown:
        return "無法判定（git 查詢失敗）"
    return "命中" if hit else "通過"


def render_ghost_report(ticket_id: str, report: GhostReport) -> str:
    lines = [f"=== Ghost 鑑識報告: {ticket_id} ==="]
    branch_detail = f"（{', '.join(report.unmerged_branch_names)}）" if report.unmerged_branch_names else ""
    branch_status = _check_status_label(report.unmerged_branch, report.unmerged_branch_unknown)
    lines.append(f"  1. 未合併分支: {branch_status}{branch_detail}")
    dirty_detail = f"（{', '.join(report.dirty_files)}）" if report.dirty_files else ""
    dirty_status = _check_status_label(report.dirty_intersection, report.dirty_intersection_unknown)
    lines.append(f"  2. 髒檔交集: {dirty_status}{dirty_detail}")
    lines.append(f"  3. Exit Status 章節: {'缺失/佔位符' if report.exit_status_missing else '已填寫'}")
    lines.append(f"  結論: {'鑑識通過，允許 reclaim' if report.clean else '鑑識未通過，拒絕 reclaim'}")
    return "\n".join(lines)


def check_reclaimable(
    ticket: Dict[str, Any],
    ticket_id: str,
    registry: Dict[str, Any],
    pm_registry,
    now: datetime,
) -> Tuple[bool, str, Optional[str]]:
    """判定票是否可 reclaim。

    Returns:
        (reclaimable, reason, owner_session_id) —— owner_session_id 為 None
        代表 registry 未追蹤此票 lease（無 FRESH session 佐證資料），仍允許
        依 ghost 三查判定（registry 缺失非阻擋條件，見 Registry Schema 契約
        「損毀/缺檔處置」降級語意）。
    """
    if ticket.get("status") != STATUS_IN_PROGRESS:
        return False, f"{ticket_id} 非 in_progress 狀態，無法 reclaim", None

    owner = _find_lease_owner(registry, ticket_id)
    if owner is None:
        return (
            True,
            "registry 未追蹤此票 lease（無 FRESH session 佐證），允許依 ghost 鑑識判定",
            None,
        )

    if pm_registry is not None:
        owner_data = (registry.get("sessions") or {}).get(owner) or {}
        if pm_registry.is_fresh(owner_data.get("heartbeat_ts"), now):
            return False, f"{ticket_id} 持有 session {owner} 仍存活（FRESH），無需 reclaim", owner

    return True, f"{ticket_id} 持有 session {owner} 已逾時（STALE），可 reclaim", owner


def _apply_reclaim(version: str, ticket_id: str) -> Optional[str]:
    """三查通過 + --confirm 後：票面轉回 pending，清 started_at/assigned。

    Returns:
        Optional[str]: 成功回傳 None；失敗回傳 `load_and_validate_ticket`
            的原始錯誤訊息（供呼叫端 stderr 輸出，Phase 4 審查修正 10：
            舊版僅回傳 bool，錯誤原因被吞掉）。
    """
    lock_target = Path(get_ticket_path(version, ticket_id))
    with file_lock(lock_target):
        ticket, error = load_and_validate_ticket(version, ticket_id)
        if error:
            return error
        ticket["status"] = STATUS_PENDING
        ticket["assigned"] = False
        ticket["started_at"] = None
        ticket_path = resolve_ticket_path(ticket, version, ticket_id)
        save_ticket(ticket, ticket_path)
    return None


def reclaim_ticket(
    version: str, ticket_id: str, *, confirm: bool, now: Optional[datetime] = None
) -> int:
    """`ticket track reclaim` 主邏輯。

    僅接受 reclaimable 票（in_progress 且無 FRESH session 佐證，或
    registry 未追蹤）；強制 ghost 鑑識三查，任一命中或無法判定即拒絕。
    預設 dry-run 僅印鑑識報告；`--confirm` 且三查全過才轉回 pending 並清
    registry lease。

    外層流程跨兩把獨立鎖，非單一原子操作（Phase 4 審查修正 3，誠實記載
    非改架構）：`check_reclaimable` 讀取 registry（無鎖快照）→ ghost 鑑識
    （純讀取，無鎖）→ `_apply_reclaim` 持 ticket md 的 `file_lock` → 之後
    才呼叫 `recompute_lease` 持 registry 的 `_registry_lock`。STALE 判定
    讀取與票面/registry 落地之間存在窄視窗：理論上 owner session 可能在
    此視窗內恢復心跳，但視窗內完成的 reclaim 已通過鑑識（無在途工作跡證），
    影響侷限於「STALE 誤判為短暫失聯的 session 遺失一張已無在途工作證據
    的票」，非資料損毀風險。

    Args:
        now: 供測試注入固定時間點（同 track_sessions.py 的 `_now` 慣例），
            預設 None 時採用真實 UTC 現在時刻。

    Returns:
        int: exit code（0 成功或 dry-run 完成，1 拒絕）
    """
    ticket = load_ticket(version, ticket_id)
    if ticket is None:
        sys.stderr.write(f"[reclaim] 找不到 Ticket: {ticket_id}\n")
        return 1

    pm_registry = _load_pm_registry()
    now = now or datetime.now(timezone.utc)
    registry: Dict[str, Any] = empty_registry_skeleton()
    registry_paths = None
    if pm_registry is not None:
        registry_paths = pm_registry.get_registry_paths()
        if registry_paths is not None:
            registry = pm_registry.read_registry(registry_paths[0])

    reclaimable, reason, owner = check_reclaimable(ticket, ticket_id, registry, pm_registry, now)
    print(f"[reclaim] {ticket_id}: {reason}")
    if not reclaimable:
        return 1

    ticket_files = where_files(ticket)
    body = ticket.get("_body", "")
    report = run_ghost_forensics(ticket_id, ticket_files, body)
    print(render_ghost_report(ticket_id, report))

    if not report.clean:
        print(
            f"[reclaim] {ticket_id}: 鑑識未通過，拒絕 reclaim"
            "（命中項代表可能存在 ghost 工作，先對帳未合併分支/髒檔再重試）"
        )
        return 1

    if not confirm:
        print(f"[reclaim] {ticket_id}: dry-run 完成，鑑識通過；加 --confirm 執行實際 reclaim")
        return 0

    apply_error = _apply_reclaim(version, ticket_id)
    if apply_error is not None:
        sys.stderr.write(f"[reclaim] {ticket_id}: 票面更新失敗：{apply_error}\n")
        return 1

    if owner is not None and pm_registry is not None and registry_paths is not None:
        registry_file, lock_file = registry_paths
        pm_registry.recompute_lease(
            registry_file,
            lock_file,
            owner,
            remove_ticket_id=ticket_id,
            files_loader=_make_files_loader(version),
        )

    print(f"[reclaim] {ticket_id}: 已轉回 pending，registry lease 已清除")
    return 0


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
