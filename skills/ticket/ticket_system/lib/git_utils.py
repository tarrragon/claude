"""Ticket md auto-commit 薄封裝（W7-001）。

承接 1.0.0-W7-001 / W1-017 ANA：ticket body 經 append-log 寫入後若停留於
未 commit 的 working tree，會被 ``git checkout -- <file>`` / ``git reset --hard``
/ ``git stash`` 還原回 create commit 的 placeholder 版本而遺失。

根因解：append-log 寫入後立即 auto-commit ticket md，使 body 即時進 commit
歷史，三種 git 還原全失效。

本模組僅提供薄封裝（便於測試 patch），不含 append-log 主邏輯。
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

# 快命令（rev-parse / add / diff）預設逾時：git hang（等認證 / index.lock）時
# 不無限等待。commit 含 pre-commit husky，呼叫端另傳較長值。
_FAST_GIT_TIMEOUT = 5
_COMMIT_GIT_TIMEOUT = 30

# index.lock 並行競爭重試（W8-006）：commit 失敗且 stderr 含 index.lock 時，
# sleep 此秒數後重試一次。W8-001 ANA：一次 retry 將並行 degrade 率由約 10% 降至 <1%。
_INDEX_LOCK_RETRY_SLEEP = 1


def _run_git(
    cwd: str, *args: str, timeout: int = _FAST_GIT_TIMEOUT
) -> subprocess.CompletedProcess:
    """在指定 cwd 執行 git 命令並回傳結果（不拋例外，由呼叫端判 returncode）。

    timeout 預設 5s（rev-parse / add / diff 等快命令）；commit 含 pre-commit
    husky 較慢，呼叫端傳 ``_COMMIT_GIT_TIMEOUT``。逾時拋 subprocess.TimeoutExpired，
    由呼叫端 try/except 涵蓋（graceful degrade，不無限等待 git hang）。
    """
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _auto_commit_ticket_md(path: str, ticket_id: str, section: str) -> str:
    """精確路徑 auto-commit 單一 ticket md。

    設計（W7-001 新設計）：
    - 精確路徑 ``git add <path>``（無 ./、-A、--all），不夾帶 PM/agent 其他變更。
    - commit message 格式：``chore(<ticket_id>): append-log <section>``。
    - 空 commit 防護：若 add 後 index 對該檔無變更（內容與 HEAD 相同），graceful
      skip（不產生空 commit、不報錯）。
    - 不使用 ``--no-verify``（維持 pre-commit hook 把關；ticket md 非 JS，
      husky lint-staged 無匹配，開銷輕微）。

    cwd 採 ticket md 所在目錄，讓 git 自動解析其所屬 repo（worktree 場景下
    commit 進 worktree 分支，complete merge 帶回 main）。

    Args:
        path: ticket md 絕對路徑
        ticket_id: 主 ticket id（用於 commit message）
        section: append-log 寫入的 section 名稱（用於 commit message）

    Returns:
        其中一個狀態字串：
        - ``"committed"``  已產生 commit
        - ``"no_change"``  body 無變更，graceful skip（不產生空 commit；正常情況，呼叫端不警告）
        - ``"not_git_repo"`` 所在目錄非 git repo，graceful skip（呼叫端應警告）
        - ``"git_failed"`` git add/commit 命令失敗，graceful skip（呼叫端應警告）

    Raises:
        本函式不主動拋例外；呼叫端仍應以 try/except 包圍以涵蓋
        subprocess 環境級異常（如 git 未安裝 OSError），符合 graceful degrade。
    """
    md_path = Path(path)
    cwd = str(md_path.parent)

    # 1. 確認所在目錄屬於 git repo（非 git repo → graceful skip + 警告）
    toplevel = _run_git(cwd, "rev-parse", "--show-toplevel")
    if toplevel.returncode != 0:
        return "not_git_repo"

    # 2. 精確路徑 add（僅該 ticket md）
    add_result = _run_git(cwd, "add", "--", str(md_path))
    if add_result.returncode != 0:
        return "git_failed"

    # 3. 空 commit 防護：staged 區對該檔無變更 → skip
    #    git diff --cached --quiet <path>：returncode 0 表示無差異
    diff_result = _run_git(cwd, "diff", "--cached", "--quiet", "--", str(md_path))
    if diff_result.returncode == 0:
        # 無 staged 變更，不產生空 commit（正常情況，非錯誤）
        return "no_change"

    # 4. 精確路徑 commit（僅該 ticket md，避免夾帶 index 內其他 staged 變更）
    message = f"chore({ticket_id}): append-log {section}"
    commit_result = _run_git(
        cwd, "commit", "-m", message, "--", str(md_path),
        timeout=_COMMIT_GIT_TIMEOUT,
    )
    if commit_result.returncode != 0:
        # index.lock 並行競爭（W8-006）：唯一中頻 degrade 觸發源。sleep 1s 後
        # 重試一次（並行 commit 多在 1s 內釋放 .git/index.lock）；非 index.lock
        # 失敗不重試（沿用現有 degrade）。重試仍失敗回 git_failed。
        if "index.lock" in (commit_result.stderr or ""):
            time.sleep(_INDEX_LOCK_RETRY_SLEEP)
            commit_result = _run_git(
                cwd, "commit", "-m", message, "--", str(md_path),
                timeout=_COMMIT_GIT_TIMEOUT,
            )
            if commit_result.returncode != 0:
                return "git_failed"
            return "committed"
        return "git_failed"

    return "committed"
