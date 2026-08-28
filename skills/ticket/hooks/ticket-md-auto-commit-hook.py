#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Ticket MD Auto-Commit Hook - Stop

功能: 主 repo（非 worktree）環境下，每個 turn 結束時自動 commit 未提交的
ticket md（docs/work-logs/**/tickets/*.md），範圍嚴格限 ticket md，不觸及
其他檔案。

觸發時機: Stop event（主 session 每次 turn 結束）
行為: 不阻擋（exit 0），僅在「非 worktree 環境 + 有未提交的 ticket md +
無活躍背景代理人」時自動 commit。

背景: PC-019 守衛要求全 repo tracked 乾淨，但 create/claim 之後、下次
append-log 之前存在空窗——ticket CLI 已 auto-stage 卻未 auto-commit，
claim/release/set-*/手動 Edit 等路徑皆會留下未提交的 ticket md 殘留，累積
跨 session 使守衛近乎恆常觸發。逐命令加 auto-commit 會加劇噪音（實測近期
commit 有九成以上為 chore auto-commit），改採 Stop 事件單點收尾：每 turn
至多一筆，涵蓋所有無 auto-commit 的路徑而噪音更低。

與既有 uncommitted-ticket-md-reminder-hook（PreToolUse）的並存理由：
兩者覆蓋的時刻不同。reminder 在 git commit 前即時警告，讓使用者在同一 turn
內、有意排除 ticket md 的部分提交場景下仍能即時得知風險；本 hook 則在
turn 結束時無條件兜底提交，確保即使使用者忽略 reminder 或未觸發任何 git
commit，ticket md 也不會遺留到下個 turn。reminder 降級的觸發風險已由本
hook 縮小為「最長一個 turn」，但其即時提醒的價值不因此歸零，故保留不變更。

與 worktree-auto-commit-hook 的分工：該 hook 僅在 worktree 環境生效
（`git add -A` 代捕全部變更）；本 hook 僅在非 worktree（主 repo）環境生效
且僅提交 ticket md，兩者互斥觸發，不重疊代捕範圍。

防 race 設計比照 worktree-auto-commit-hook：有活躍背景代理人時跳過代捕，
避免搶先代捕代理人 in-flight WIP；stale entry（超過 DISPATCH_MAX_AGE_HOURS）
先清理，避免異常終止的代理人記錄永久癱瘓安全網。

隔離提交完整性三要件（見 `.claude/references/bash-tool-usage-details.md`
「規則七詳細」）原僅涵蓋「清單來源需獨立於共用 index」一維；本 hook 額外
補上第二維——**清單來源亦須獨立於工作區的其他 session**：`get_uncommitted_files`
讀 `git status --porcelain`，反映的是整個工作區，多 PM session（各自獨立
視窗/terminal）並行時必然包含他人 session 尚在撰寫、未完成的 ticket md。
`has_active_background_agents()`（防 race 檢查）只擋「本 hook 觸發當下，
`dispatch-active.json` 仍有未過期的背景代理人派發記錄」這一種情境；
另一 session 透過自身直接 CLI 呼叫（非經派發追蹤）撰寫中的 ticket md，
或已完成派發但尚未輪到自身 turn-end 的情境，皆不在該檢查涵蓋範圍。

修法：`get_changed_ticket_md_files` 改以 `.claude/lib/pm_registry.py`
的 `sessions[<本 session_id>].tickets`（claim/complete/release/reclaim
生命週期維護的認領清單）為正歸屬判準，只納入「ticket_id 現正被本 session
認領」的 ticket md；不在此清單者一律排除（保守策略：漏提交可由下次
turn-end 補上，誤提交他人在途工作不可逆）。選用 pm-registry 而非
`dispatch-active.json` 的 `session_id` 欄位：後者僅追蹤「PM 派發了哪些
背景代理人」，對 PM 自身直接 CLI 撰寫（未經派發）的 ticket md 無記錄；
pm-registry 的 `tickets` 是「本 session 目前認領哪些 ticket」的權威清單，
不論該票是由 PM 直接操作或由本 session 派發的代理人操作，只要仍在認領中
即會出現在此清單，涵蓋面完整覆蓋本 hook 需要的歸屬判準。

已知殘留（設計上接受，非本次修復範圍）：ticket 剛完成（`complete`）時，
`recompute_lease` 立即將其自 `tickets` 移除；若該次 complete 自身的
auto-commit 恰好失敗（極端邊界），此 ticket md 在下一次 turn-end 時已不
再認領中，會被排除而非兜底提交。此情形發生機率低（complete 自身已有
獨立的 auto-commit 嘗試）且與「漏提交可由下次互動補上」的既定保守策略
方向一致，故不視為缺陷。
"""

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_CLAUDE_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_CLAUDE_DIR))
# .claude/skills/ticket 加入 sys.path：匯入 ticket_system.lib.git_ops（隔離索引
# 提交，與 ticket_system.lib.git_utils._auto_commit_ticket_md、
# lifecycle.complete() 共用同一實作）。git_ops.py 模組層級僅 stdlib 依賴（無
# filelock/pyyaml），與本 hook 的 uv run --script 輕量 PEP 723 環境相容。
_TICKET_SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_TICKET_SKILL_DIR))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    get_uncommitted_files,
    FileStatus,
    ENV_SESSION_ID,
)
from lib.pm_registry import get_registry_paths, read_registry, DEGRADED_READ_KEY
from ticket_system.lib import git_ops

try:
    from lib.dispatch_tracker import get_active_dispatches, cleanup_expired
except ImportError:  # pragma: no cover - 僅在 lib 缺失時走降級
    get_active_dispatches = None
    cleanup_expired = None

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "ticket-md-auto-commit"
GIT_TIMEOUT = 10
DISPATCH_MAX_AGE_HOURS = 1

# ticket md 路徑特徵，與 uncommitted-ticket-md-reminder-hook 一致
# （docs/work-logs/.../tickets/*.md，涵蓋階層與扁平結構）
_TICKET_MD_PATTERN = re.compile(r"docs/work-logs/.*/tickets/[^/]+\.md$")


# ============================================================================
# 核心邏輯
# ============================================================================


def is_worktree_environment(logger) -> bool:
    """偵測當前是否在 git worktree 環境中（worktree 的 .git 是檔案非目錄）。

    本 hook 僅在非 worktree（主 repo）環境生效；worktree 環境已由
    worktree-auto-commit-hook 覆蓋全部變更（含 ticket md）。
    """
    cwd = Path.cwd()
    git_path = cwd / ".git"
    if git_path.is_file():
        logger.debug("偵測到 worktree 環境（.git 為檔案）: %s", cwd)
        return True

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT,
        )
        if result.returncode == 0:
            common_dir = result.stdout.strip()
            git_dir_result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_TIMEOUT,
            )
            if git_dir_result.returncode == 0:
                git_dir = git_dir_result.stdout.strip()
                if Path(common_dir).resolve() != Path(git_dir).resolve():
                    logger.debug("偵測到 worktree 環境（git-dir != common-dir）")
                    return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git rev-parse 執行失敗")

    return False


def is_ticket_md_path(file_path: str) -> bool:
    """判斷檔案路徑是否為 ticket md（docs/work-logs/**/tickets/*.md）。"""
    if not file_path:
        return False
    return bool(_TICKET_MD_PATTERN.search(file_path))


def _ticket_id_from_ticket_md_path(file_path: str) -> "str | None":
    """從 ticket md 路徑萃取 ticket_id（檔名去除 .md 副檔名，慣例即 ticket_id）。"""
    stem = Path(file_path).stem
    return stem or None


def get_session_claimed_ticket_ids(logger) -> "set[str] | None":
    """讀 `.claude/lib/pm_registry.py` 的 pm-registry.json，回傳本 session
    （`CLAUDE_CODE_SESSION_ID`）目前認領（lease）中的 ticket_id 集合。

    Returns:
        `set[str]`：本 session 現正認領的 ticket_id 集合（可能為空集合，
            代表本 session 合法地未認領任何票，非「無法判定」）。
        `None`：歸屬判定來源不可用（`CLAUDE_CODE_SESSION_ID` 未設定、非
            git 環境無法解析 registry 路徑、registry 檔案損毀降級讀取）。
            呼叫端應視為「無法判定歸屬」，採保守策略排除全部候選。
    """
    session_id = os.environ.get(ENV_SESSION_ID, "").strip()
    if not session_id:
        logger.warning("CLAUDE_CODE_SESSION_ID 未設定，無法判定 session 歸屬")
        return None

    paths = get_registry_paths(logger=logger)
    if paths is None:
        logger.warning("pm-registry 路徑無法解析（非 git 環境？），無法判定 session 歸屬")
        return None
    registry_file, _lock_file = paths

    data = read_registry(registry_file, logger=logger)
    if data.get(DEGRADED_READ_KEY):
        logger.warning("pm-registry 讀取降級（缺檔/損毀），無法判定 session 歸屬")
        return None

    entry = data.get("sessions", {}).get(session_id)
    if entry is None:
        return set()
    return set(entry.get("tickets") or [])


def get_changed_ticket_md_files(logger) -> "list[str]":
    """回傳未提交變更中屬於 ticket md 的檔案路徑清單（含 untracked），
    並依 session 歸屬過濾——僅納入本 session 現正認領中的 ticket。

    `git status --porcelain` 反映整個工作區，多 PM session 並行時必然
    包含他人 session 尚在撰寫的 ticket md（見本檔 module docstring「隔離
    提交完整性三要件」補述）。歸屬判定來源不可用時（`None`）保守排除
    全部候選；候選存在但不在認領清單中者逐一記錄排除理由（規則 4
    可觀測性：排除須留痕，不可靜默丟失）。
    """
    try:
        file_statuses = get_uncommitted_files()
    except subprocess.TimeoutExpired:
        logger.warning("git status 逾時")
        return []
    except FileNotFoundError:
        logger.warning("找不到 git")
        return []

    candidates = []
    for fs in file_statuses:
        path = fs.file_path.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        path = path.strip('"')
        if path and is_ticket_md_path(path):
            candidates.append(path)

    if not candidates:
        return []

    claimed = get_session_claimed_ticket_ids(logger)
    if claimed is None:
        logger.warning(
            "session 歸屬判定來源不可用，保守排除全部候選（%d 個）: %s",
            len(candidates), candidates,
        )
        return []

    included = []
    excluded = []
    for path in candidates:
        ticket_id = _ticket_id_from_ticket_md_path(path)
        if ticket_id and ticket_id in claimed:
            included.append(path)
        else:
            excluded.append(path)

    if excluded:
        logger.info(
            "排除 %d 個非本 session 現正認領的 ticket md（可能屬他 session"
            "在途工作或本 session 已完成釋放認領）: %s",
            len(excluded), excluded,
        )

    return included


def find_project_root(logger) -> "Path | None":
    """解析 dispatch-active.json 所在的專案根目錄（主 repo cwd 本身）。"""
    cwd = Path.cwd()
    if (cwd / ".claude" / "dispatch-active.json").exists():
        return cwd
    if (cwd / ".claude").is_dir():
        # 主 repo 下即使尚無 dispatch-active.json，cwd 仍是正確根目錄
        return cwd
    logger.debug("找不到 .claude 目錄，無法解析 project root")
    return None


def has_active_background_agents(project_root, logger) -> bool:
    """檢查是否有活躍（未超時）的背景代理人派發記錄。

    防 race 核心：有活躍代理人時不搶先代捕，讓代理人自行 commit。
    """
    if project_root is None or get_active_dispatches is None:
        logger.debug("無法查詢 dispatch 狀態，降級為兜底行為")
        return False

    try:
        if cleanup_expired is not None:
            removed = cleanup_expired(project_root, max_age_hours=DISPATCH_MAX_AGE_HOURS)
            if removed:
                logger.info("清理 %d 筆 stale 派發記錄", removed)
        dispatches = get_active_dispatches(project_root)
    except (OSError, ValueError) as e:
        logger.warning("讀取 dispatch-active.json 失敗，降級為兜底行為: %s", e)
        return False

    active = [d for d in dispatches if not _is_dispatch_stale(d, logger)]
    if active:
        descs = ", ".join(
            d.get("agent_description", "?") or d.get("agent_id", "?") for d in active
        )
        logger.info("偵測到 %d 個活躍背景代理人，跳過代捕: %s", len(active), descs)
        return True
    return False


def _is_dispatch_stale(dispatch, logger) -> bool:
    """判斷單筆派發是否已超時（解析失敗視為 stale，不阻止兜底）。"""
    ts = dispatch.get("dispatched_at", "")
    try:
        dispatched_at = datetime.fromisoformat(ts)
        if dispatched_at.tzinfo is None:
            dispatched_at = dispatched_at.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - dispatched_at).total_seconds() / 3600
        return age_hours > DISPATCH_MAX_AGE_HOURS
    except (ValueError, TypeError):
        logger.debug("派發時間解析失敗，視為 stale: %s", ts)
        return True


def build_commit_message(ticket_md_files) -> str:
    """組裝 commit 訊息（附 ticket md 檔名摘要，保留可檢索性）。"""
    count = len(ticket_md_files)
    preview = ", ".join(Path(f).stem for f in ticket_md_files[:3])
    if count > 3:
        preview += f", +{count - 3} more"
    return f"auto(ticket-md): turn-end commit ({count} files: {preview})"


def auto_commit_ticket_md(ticket_md_files, message, logger) -> bool:
    """委派 ``ticket_system.lib.git_ops.commit_files_isolated`` 提交。

    提交機制（GIT_INDEX_FILE 隔離索引 + write-tree/commit-tree/update-ref
    CAS + 提交範圍自我驗證 + 成功後同步共用 index 中本次 paths）已於
    ``git_ops.commit_files_isolated`` 完整實作並經 ``test_git_ops.py``
    涵蓋，與 ``lifecycle.complete()``、``ticket_system.lib.git_utils.
    _auto_commit_ticket_md`` 共用同一份實作，本函式僅轉接回傳型別（dict
    -> bool）以維持 ``main()`` 呼叫端介面不變。

    不使用 `git commit`：裸 commit 提交的是共用 index 的整體內容，`git add`
    精確指定路徑與「commit 提交範圍」是兩件事——add 之後、commit 之前的窗口
    中，其他並行程序（背景代理人、PM）仍可能 stage 自己的變更進同一個共用
    index，使裸 commit 連帶提交進去（PC-BAL-008 實證五：先核對 index 再
    commit 仍有 TOCTOU 窗口，本 session 實測命中）——這正是
    ``commit_files_isolated`` 全程使用獨立臨時 index、不觸碰共用 index 所
    避免的風險類別。

    清單來源條件（隔離提交完整性三要件之一，見
    `.claude/references/bash-tool-usage-details.md`「規則七詳細」）：本函式
    的 `ticket_md_files` 引數由呼叫端 `get_changed_ticket_md_files`（基於
    `git status --porcelain`，非讀取共用 index 目前 staged 狀態）產生，現行
    這一點是正確的，但這份正確性目前屬巧合——沒有機制強制禁止未來把清單來
    源改為 `git diff --cached --name-only`。GIT_INDEX_FILE 只隔離「寫入
    端」，若清單來源改讀共用 index 的 staged 狀態，隔離會在入口就已經漏
    掉：其餘步驟仍會「正確地」執行完畢，但提交範圍整體仍是錯的（真實案例見
    上述文件的反例段落）。修改本函式或 `get_changed_ticket_md_files` 時，
    清單來源必須維持獨立於共用 index，不可改用 `--cached` 或任何讀取共用
    index 目前 staged 狀態的命令。
    """
    result = git_ops.commit_files_isolated(ticket_md_files, message)

    if result["status"] == "committed":
        commit_sha = result["commit_sha"] or ""
        logger.info("自動 commit 成功: %s (%s)", message, commit_sha[:8])
        return True
    if result["status"] == "empty":
        logger.debug("無變更需要提交（empty，graceful skip）")
        return True

    logger.error("git_ops.commit_files_isolated 失敗: %s", result.get("error"))
    sys.stderr.write(
        f"[{HOOK_NAME}] auto-commit 失敗: {result.get('error')}\n"
    )
    return False


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging(HOOK_NAME)
    logger.info("Stop hook 開始執行")

    # 僅在主 repo（非 worktree）環境中執行；worktree 已由
    # worktree-auto-commit-hook 覆蓋（含 ticket md）
    if is_worktree_environment(logger):
        logger.debug("worktree 環境，跳過（由 worktree-auto-commit-hook 覆蓋）")
        return 0

    ticket_md_files = get_changed_ticket_md_files(logger)
    if not ticket_md_files:
        logger.debug("無未提交的 ticket md，跳過")
        return 0
    logger.info("偵測到 %d 個未提交的 ticket md", len(ticket_md_files))

    project_root = find_project_root(logger)

    # 防 race：有活躍背景代理人時不搶先代捕，讓代理人自行 commit
    if has_active_background_agents(project_root, logger):
        sys.stderr.write(
            f"[{HOOK_NAME}] 偵測到活躍背景代理人，跳過代捕（由代理人自行 commit）\n"
        )
        return 0

    message = build_commit_message(ticket_md_files)
    success = auto_commit_ticket_md(ticket_md_files, message, logger)

    if success:
        sys.stderr.write(
            f"[{HOOK_NAME}] {len(ticket_md_files)} 個未提交 ticket md 已自動 commit\n"
        )
    else:
        sys.stderr.write(
            f"[{HOOK_NAME}] [WARNING] 自動 commit 失敗，ticket md 變更可能遺留至下個 turn\n"
        )

    # 不論成功或失敗都回傳 0，不阻擋退出
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
