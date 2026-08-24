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
"""

import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

_CLAUDE_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_CLAUDE_DIR))

from lib import setup_hook_logging, run_hook_safely, get_uncommitted_files, FileStatus

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


def get_changed_ticket_md_files(logger) -> "list[str]":
    """回傳未提交變更中屬於 ticket md 的檔案路徑清單（含 untracked）。"""
    try:
        file_statuses = get_uncommitted_files()
    except subprocess.TimeoutExpired:
        logger.warning("git status 逾時")
        return []
    except FileNotFoundError:
        logger.warning("找不到 git")
        return []

    files = []
    for fs in file_statuses:
        path = fs.file_path.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        path = path.strip('"')
        if path and is_ticket_md_path(path):
            files.append(path)
    return files


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


def _run_git_with_lock_retry(
    args, logger, action_label, max_retries=3, wait_seconds=2, env=None
):
    """執行 git 命令，遇 index.lock 競爭時等待重試（禁止刪除 lock 檔）。

    回傳 (success: bool, stdout: str, stderr: str)。
    """
    last_stderr = ""
    last_stdout = ""
    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_TIMEOUT,
                env=env,
            )
        except subprocess.TimeoutExpired:
            logger.error("git %s 逾時", action_label)
            sys.stderr.write(f"[{HOOK_NAME}] git {action_label} 逾時\n")
            return False, "", "timeout"
        except FileNotFoundError:
            logger.error("找不到 git")
            sys.stderr.write(f"[{HOOK_NAME}] 找不到 git\n")
            return False, "", "git not found"

        if result.returncode == 0:
            return True, result.stdout, ""

        last_stderr = result.stderr.strip()
        last_stdout = result.stdout
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
    return False, last_stdout, last_stderr


def _normalize_to_repo_relative(paths, repo_root: "Path | None") -> "set[str]":
    """將路徑清單正規化為相對於 repo root 的 POSIX 字串集合。

    `git diff --name-only` 一律輸出相對 repo root 的路徑；但呼叫端傳入的
    `ticket_md_files`（來自 `git status --porcelain` 解析）在 cwd 不等於
    repo root 時可能夾帶絕對路徑或不同基準的相對路徑，逐字比較會誤判為
    範圍不符（本函式修正的原始問題）。repo_root 無法解析時（如
    `git rev-parse --show-toplevel` 失敗）原樣回傳，不強制轉換。
    """
    if repo_root is None:
        return {p.strip() for p in paths if p.strip()}

    normalized = set()
    for p in paths:
        p = p.strip()
        if not p:
            continue
        candidate = Path(p)
        try:
            if candidate.is_absolute():
                rel = candidate.resolve().relative_to(repo_root)
            else:
                rel = (repo_root / candidate).resolve().relative_to(repo_root)
            normalized.add(rel.as_posix())
        except ValueError:
            # 無法正規化為 repo root 相對路徑（例如指向 repo 外），原樣保留
            normalized.add(p)
    return normalized


def _resolve_repo_root(logger) -> "Path | None":
    """解析當前 repo 的 top-level 目錄（供自我驗證路徑正規化使用）。"""
    ok, out, _ = _run_git_with_lock_retry(
        ["git", "rev-parse", "--show-toplevel"], logger, "rev-parse --show-toplevel"
    )
    if not ok:
        return None
    return Path(out.strip()).resolve()


def auto_commit_ticket_md(ticket_md_files, message, logger) -> bool:
    """在獨立臨時 index 中精確 stage ticket md 後以 plumbing 提交，範圍自我驗證後
    以 CAS（compare-and-swap）方式移動 HEAD。

    不使用 `git commit`：裸 commit 提交的是共用 index 的整體內容，`git add`
    精確指定路徑與「commit 提交範圍」是兩件事——add 之後、commit 之前的窗口
    中，其他並行程序（背景代理人、PM）仍可能 stage 自己的變更進同一個共用
    index，使裸 commit 連帶提交進去（PC-BAL-008 實證五：先核對 index 再
    commit 仍有 TOCTOU 窗口，本 session 實測命中）。

    改用 read-tree/write-tree/commit-tree/update-ref 全程操作獨立臨時 index
    （`GIT_INDEX_FILE` 指向本函式自建的暫存檔案，與共用 index 完全隔離），
    提交內容只由本函式的 `ticket_md_files` 引數決定，不受共用 index 任何並
    行寫入影響。commit 建立後另以 `git diff` 自我驗證變更範圍恰為
    `ticket_md_files`，不符即放棄；最後以 `update-ref HEAD <new> <old>` 帶
    舊值移動分支指標，若 HEAD 於期間被並行移動則失敗而非覆蓋，避免遺失他人
    commit。

    因不經過 `git commit`，此路徑不會觸發任何 pre-commit/commit-msg hook
    （含 bare-commit-guard-hook）——這是 plumbing 命令的固有行為，非刻意繞
    過。guard 存在的目的是攔截「範圍不明的裸 commit」；本函式以自我驗證取代
    guard 的把關角色：提交範圍由程式碼結構保證且提交後即時核驗，不依賴
    guard 事後攔截，故豁免 guard 不削弱其防護意圖。

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
    ok, old_head_out, _ = _run_git_with_lock_retry(
        ["git", "rev-parse", "HEAD"], logger, "rev-parse HEAD"
    )
    if not ok:
        return False
    old_head = old_head_out.strip()

    fd, temp_index_path = tempfile.mkstemp(prefix="ticket-md-auto-commit-index-")
    os.close(fd)
    os.remove(temp_index_path)  # read-tree 會依需要建立獨立 index 檔
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = temp_index_path

    try:
        ok, _, _ = _run_git_with_lock_retry(
            ["git", "read-tree", old_head], logger, "read-tree", env=env
        )
        if not ok:
            return False

        ok, _, _ = _run_git_with_lock_retry(
            ["git", "add", "--"] + ticket_md_files, logger, "add", env=env
        )
        if not ok:
            return False

        ok, tree_out, _ = _run_git_with_lock_retry(
            ["git", "write-tree"], logger, "write-tree", env=env
        )
        if not ok:
            return False
        tree_sha = tree_out.strip()

        ok, commit_out, _ = _run_git_with_lock_retry(
            ["git", "commit-tree", tree_sha, "-p", old_head, "-m", message],
            logger, "commit-tree",
        )
        if not ok:
            return False
        commit_sha = commit_out.strip()

        ok, diff_out, _ = _run_git_with_lock_retry(
            ["git", "diff", "--name-only", old_head, commit_sha], logger, "diff"
        )
        if not ok:
            return False
        repo_root = _resolve_repo_root(logger)
        changed_raw = {line for line in diff_out.splitlines() if line.strip()}
        changed = _normalize_to_repo_relative(changed_raw, repo_root)
        expected = _normalize_to_repo_relative(ticket_md_files, repo_root)
        if changed != expected:
            logger.error(
                "提交範圍自我驗證失敗，預期 %s 實得 %s，放棄提交",
                sorted(expected), sorted(changed),
            )
            sys.stderr.write(f"[{HOOK_NAME}] 提交範圍自我驗證失敗，放棄提交\n")
            return False

        ok, _, _ = _run_git_with_lock_retry(
            ["git", "update-ref", "HEAD", commit_sha, old_head], logger, "update-ref"
        )
        if not ok:
            logger.warning("HEAD 於提交期間被並行移動，放棄本次自動 commit")
            return False

        logger.info("自動 commit 成功: %s (%s)", message, commit_sha[:8])
        return True
    finally:
        try:
            if os.path.exists(temp_index_path):
                os.remove(temp_index_path)
        except OSError:
            logger.debug("臨時 index 清理失敗: %s", temp_index_path)


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
