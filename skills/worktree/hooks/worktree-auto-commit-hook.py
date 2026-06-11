#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Worktree Auto-Commit Hook - Stop

功能: 代理人在 worktree 環境結束時，自動 commit 未提交的變更。
防止 Claude Code 內建清理邏輯因「無 commit」而刪除 worktree，導致工作遺失。

觸發時機: Stop event（主 session 每次 turn 結束 + session 終止時皆觸發）
行為: 不阻擋（exit 0），僅在「worktree 環境 + 有未提交變更 + 無活躍背景代理人」時自動 commit

根因修復（W1-062）: Stop event 在主 session 每 turn 結束觸發，PM 以 user worktree 為
cwd + 背景代理人共用同一 cwd 時，原本的 `git add -A` 會搶先代捕代理人 in-flight WIP
（1.0.0-W1-059 實證 221fb53b），導致代理人自身 ticket-referenced commit 被跳過、
commit 訊息無 ticket 語意。三道修正：
  (1) 防 race：偵測活躍背景代理人（dispatch-active.json）時跳過代捕，讓代理人自行
      commit；僅在無活躍代理人時兜底。stale entry 先以 cleanup_expired 清理，避免
      異常終止的代理人記錄永久癱瘓安全網。
  (2) 訊息富化：代捕時從變更檔案路徑匹配 in_progress ticket 的 where.files 推斷
      ticket ID 寫入訊息；無法推斷時附檔案摘要。
  (3) git add -A 與 --no-verify 取捨顯性結論（見下）。

git add -A 取捨結論（保留）:
  此 hook 的本職是「防工作遺失」安全網——worktree 被清理前必須把所有未追蹤 / 未提交
  變更保全。縮小搜刮範圍（例如只 add 已追蹤檔）會讓 untracked 新檔在 worktree 清理時
  遺失，違反原始威脅防護。race 風險已由修正 (1) 從源頭消除（有活躍代理人即不搶先），
  故 add -A 在「無活躍代理人」前提下是安全且必要的。結論：保留 git add -A。

--no-verify 取捨結論（保留）:
  此為保全性兜底 commit。若 pre-commit lint 失敗會阻擋 commit，導致 worktree 清理時
  工作遺失——「遺失工作」的代價遠高於「一個未過 lint 的 auto-commit」。auto-commit 為
  暫存性質，後續由代理人 / PM 正式 commit 時仍會經 lint 把關。結論：保留 --no-verify，
  但僅在無活躍代理人的兜底路徑使用（修正 (1) 已避免搜刮到 src/ 進行中變更）。
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_CLAUDE_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_CLAUDE_DIR / "hooks"))
sys.path.insert(0, str(_CLAUDE_DIR / "hooks" / "lib"))

from hook_utils import setup_hook_logging, run_hook_safely

# dispatch_tracker / find_ticket_files 為訊息富化與防 race 用；缺失時降級而非崩潰
try:
    from dispatch_tracker import get_active_dispatches, cleanup_expired
except ImportError:  # pragma: no cover - 僅在 lib 缺失時走降級
    get_active_dispatches = None
    cleanup_expired = None

try:
    from hook_utils import find_ticket_files, parse_ticket_frontmatter
    from hook_utils import extract_where_files_from_frontmatter
except ImportError:  # pragma: no cover
    find_ticket_files = None
    parse_ticket_frontmatter = None
    extract_where_files_from_frontmatter = None

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "worktree-auto-commit"
GIT_TIMEOUT = 10
# 活躍派發超時時數：超過此時數的派發記錄視為 stale（代理人異常終止未清除），
# 不再阻止兜底代捕。與 dispatch_tracker.cleanup_expired 預設一致。
DISPATCH_MAX_AGE_HOURS = 1
ACTIVE_STATUSES = {"in_progress"}


# ============================================================================
# 核心邏輯
# ============================================================================


def is_worktree_environment(logger) -> bool:
    """偵測當前是否在 git worktree 環境中。

    Worktree 的 .git 是一個檔案（內含 gitdir 指向），而非目錄。
    """
    # 方法 1: 檢查 .git 是否為檔案
    cwd = Path.cwd()
    git_path = cwd / ".git"
    if git_path.is_file():
        logger.info("偵測到 worktree 環境（.git 為檔案）: %s", cwd)
        return True

    # 方法 2: 用 git rev-parse 確認
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
                # 在 worktree 中，git-dir 和 git-common-dir 不同
                if Path(common_dir).resolve() != Path(git_dir).resolve():
                    logger.info("偵測到 worktree 環境（git-dir != common-dir）")
                    return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git rev-parse 執行失敗")

    return False


def find_project_root(logger) -> "Path | None":
    """解析存放 dispatch-active.json / ticket 檔案的專案根目錄。

    來源優先序（W1-062 dogfood 修正）:
      (1) cwd（worktree）內若已有 `.claude/dispatch-active.json` → 優先採用。
          PM / 背景代理人以 worktree 為 cwd 工作時，dispatch 狀態檔由 PM 寫在 cwd 的
          .claude/，而非主 repo。原本只取 git-common-dir 會讀到主 repo 的空檔案，
          漏判活躍代理人造成搶先代捕（本 ticket 要修的 race 本身）。
      (2) fallback 至 git-common-dir 上一層（主 repo root），涵蓋 dispatch 狀態
          集中於主 repo 的配置。

    回傳 None 時呼叫端降級（不查 dispatch / 不富化訊息）。
    """
    # (1) cwd 自身即 dispatch 狀態所在
    cwd = Path.cwd()
    if (cwd / ".claude" / "dispatch-active.json").exists():
        logger.debug("dispatch 狀態檔位於 cwd: %s", cwd)
        return cwd

    # (2) fallback：主 repo root（git-common-dir 上一層）
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
            common_dir = Path(result.stdout.strip()).resolve()
            # git-common-dir 通常為 <repo>/.git；上一層即 repo root
            root = common_dir.parent
            logger.debug("dispatch 狀態檔 fallback 至主 repo root: %s", root)
            return root
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("解析 project root 失敗: %s", e)
    return None


def has_active_background_agents(project_root, logger) -> bool:
    """檢查是否有活躍（未超時）的背景代理人派發記錄。

    防 race 核心：有活躍代理人共用 cwd 時，其 in-flight WIP 不應被本 hook 搶先代捕，
    應讓代理人自行 commit（ticket-referenced）。先 cleanup_expired 清掉 stale entry，
    避免異常終止的代理人記錄永久癱瘓兜底安全網。

    project_root 為 None 或 dispatch_tracker 不可用時回傳 False（降級為原始兜底行為）。
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


def get_changed_files(logger) -> "list[str]":
    """回傳未提交變更的檔案路徑清單（含 untracked）。"""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning("git status 失敗: %s", result.stderr.strip())
            return []
        files = []
        for line in result.stdout.splitlines():
            if len(line) < 4:
                continue
            # porcelain 格式：XY <path>（rename 為 'old -> new'，取 new）
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            # 去除可能的引號（含特殊字元路徑）
            path = path.strip('"')
            if path:
                files.append(path)
        return files
    except subprocess.TimeoutExpired:
        logger.warning("git status 逾時")
        return []
    except FileNotFoundError:
        logger.warning("找不到 git")
        return []


def infer_ticket_ids(project_root, changed_files, logger) -> "list[str]":
    """從變更檔案路徑匹配 in_progress ticket 的 where.files 推斷 ticket ID。

    回傳推斷出的 ticket ID 清單（去重、排序）。無法推斷時回傳空清單。
    """
    if (
        project_root is None
        or find_ticket_files is None
        or parse_ticket_frontmatter is None
        or extract_where_files_from_frontmatter is None
    ):
        logger.debug("ticket 推斷依賴不可用，跳過富化")
        return []

    if not changed_files:
        return []

    changed_set = {_normalize(f) for f in changed_files}
    matched = set()
    try:
        ticket_files = find_ticket_files(project_root, logger=logger)
    except (OSError, ValueError) as e:
        logger.warning("掃描 ticket 檔案失敗: %s", e)
        return []

    for ticket_file in ticket_files:
        try:
            fm = parse_ticket_frontmatter(ticket_file, logger)
        except (OSError, ValueError):
            continue
        if not fm or fm.get("status") not in ACTIVE_STATUSES:
            continue
        ticket_id = fm.get("id")
        if not ticket_id:
            continue
        where_files = extract_where_files_from_frontmatter(fm) or []
        for wf in where_files:
            if _normalize(wf) in changed_set:
                matched.add(ticket_id)
                break

    return sorted(matched)


def _normalize(path: str) -> str:
    """規範化路徑供集合比對（去前後空白、去 ./ 前綴）。"""
    p = (path or "").strip().strip('"')
    if p.startswith("./"):
        p = p[2:]
    return p


def build_commit_message(project_root, changed_files, logger) -> str:
    """組裝富化後的 commit 訊息。

    優先嵌入推斷出的 ticket ID；無法推斷時附檔案摘要，保留可檢索性。
    """
    base = "auto: worktree agent work preserved"
    ticket_ids = infer_ticket_ids(project_root, changed_files, logger)
    if ticket_ids:
        ids = ", ".join(ticket_ids)
        logger.info("代捕訊息嵌入推斷 ticket ID: %s", ids)
        return f"auto({ids}): worktree uncommitted changes preserved"

    # 無法推斷 ticket：附檔案摘要
    count = len(changed_files)
    if count:
        preview = ", ".join(changed_files[:3])
        if count > 3:
            preview += f", +{count - 3} more"
        logger.info("代捕訊息附檔案摘要（%d 檔，無法推斷 ticket）", count)
        return f"{base} ({count} files: {preview})"
    return base


def has_uncommitted_changes(logger) -> bool:
    """檢查是否有未 commit 的變更（含 untracked 檔案）。"""
    return len(get_changed_files(logger)) > 0


def auto_commit(message, logger) -> bool:
    """執行 git add -A && git commit。回傳是否成功。

    遇 index.lock（主線程並行 git 活動）時等待數秒重試，禁止刪除 lock 檔。
    """
    if not _git_add_all_with_retry(logger):
        return False

    commit_ok = _git_commit_with_retry(message, logger)
    if commit_ok:
        logger.info("自動 commit 成功: %s", message)
    return commit_ok


def _run_git_with_lock_retry(args, logger, action_label, max_retries=3, wait_seconds=2):
    """執行 git 命令，遇 index.lock 競爭時等待重試（禁止刪除 lock 檔）。

    回傳 (success: bool, returncode: int, stderr: str)。
    """
    import time

    last_stderr = ""
    last_rc = 1
    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            logger.error("git %s 逾時", action_label)
            sys.stderr.write(f"[{HOOK_NAME}] git {action_label} 逾時\n")
            return False, 1, "timeout"
        except FileNotFoundError:
            logger.error("找不到 git")
            sys.stderr.write(f"[{HOOK_NAME}] 找不到 git\n")
            return False, 1, "git not found"

        if result.returncode == 0:
            return True, 0, ""

        last_stderr = result.stderr.strip()
        last_rc = result.returncode
        if "index.lock" in last_stderr and attempt < max_retries:
            logger.info(
                "git %s 遇 index.lock（主線程並行活動），%d 秒後重試 (%d/%d)",
                action_label, wait_seconds, attempt, max_retries,
            )
            time.sleep(wait_seconds)
            continue
        break

    logger.error("git %s 失敗: %s", action_label, last_stderr)
    sys.stderr.write(f"[{HOOK_NAME}] git {action_label} 失敗: {last_stderr}\n")
    return False, last_rc, last_stderr


def _git_add_all_with_retry(logger) -> bool:
    success, _, _ = _run_git_with_lock_retry(
        ["git", "add", "-A"], logger, "add"
    )
    return success


def _git_commit_with_retry(message, logger) -> bool:
    success, _, _ = _run_git_with_lock_retry(
        ["git", "commit", "-m", message, "--no-verify"], logger, "commit"
    )
    return success


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging(HOOK_NAME)
    logger.info("Stop hook 開始執行")

    # 僅在 worktree 環境中執行
    if not is_worktree_environment(logger):
        logger.debug("非 worktree 環境，跳過")
        return 0

    # 檢查是否有未提交變更
    changed_files = get_changed_files(logger)
    if not changed_files:
        logger.debug("worktree 中無未提交變更，跳過")
        return 0
    logger.info("偵測到 %d 個未提交的變更", len(changed_files))

    project_root = find_project_root(logger)

    # 防 race：有活躍背景代理人時不搶先代捕，讓代理人自行 ticket-referenced commit
    if has_active_background_agents(project_root, logger):
        sys.stderr.write(
            f"[{HOOK_NAME}] 偵測到活躍背景代理人，跳過代捕（由代理人自行 commit）\n"
        )
        return 0

    # 無活躍代理人：執行兜底代捕，保留工作成果（訊息富化）
    logger.info("無活躍代理人，執行兜底自動 commit")
    message = build_commit_message(project_root, changed_files, logger)
    success = auto_commit(message, logger)

    if success:
        sys.stderr.write(
            f"[{HOOK_NAME}] worktree 未提交變更已自動 commit 保留\n"
        )
    else:
        sys.stderr.write(
            f"[{HOOK_NAME}] [WARNING] 自動 commit 失敗，worktree 變更可能遺失\n"
        )

    # 不論成功或失敗都回傳 0，不阻擋退出
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
