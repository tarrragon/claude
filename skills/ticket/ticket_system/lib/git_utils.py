"""Ticket md auto-commit 薄封裝（W7-001）。

承接 1.0.0-W7-001 / W1-017 ANA：ticket body 經 append-log 寫入後若停留於
未 commit 的 working tree，會被 ``git checkout -- <file>`` / ``git reset --hard``
/ ``git stash`` 還原回 create commit 的 placeholder 版本而遺失。

根因解：append-log 寫入後立即 auto-commit ticket md，使 body 即時進 commit
歷史，三種 git 還原全失效。

本模組僅提供薄封裝（便於測試 patch），不含 append-log 主邏輯。

提交機制由「精確路徑 add + pathspec commit」改為委派
``ticket_system.lib.git_ops.commit_files_isolated``（GIT_INDEX_FILE 全程隔離
共用 index，與 ``ticket-md-auto-commit-hook.py``、``lifecycle.complete()``
共用同一實作）。原本自帶的 ``_run_git`` / 重試 / timeout 常數已隨此改動
移除——提交機制的 git 呼叫、重試、timeout 全由 ``git_ops`` 負責，測試涵蓋
移至 ``test_git_ops.py``。本模組保留的職責收斂為：commit message 組裝
（含 session trailer）與狀態字串轉譯。
"""
from __future__ import annotations

from pathlib import Path

from .git_ops import commit_files_isolated
from .lease import resolve_current_session_id

# git_ops.commit_files_isolated 回傳的 status（committed/empty/failed）轉譯為
# 本模組既有呼叫端（ticket_system.commands.*）慣用的狀態字串。「not_git_repo」
# 與「git_failed」在 git_ops 的回傳裡已無法區分（皆為 "failed"）——查證所有
# 呼叫端（grep `commit_status in`）皆以 `("not_git_repo", "git_failed")` 群組
# 判斷，從未單獨比對 "not_git_repo"，故此收斂不改變任何呼叫端行為。
_STATUS_MAP = {
    "committed": "committed",
    "empty": "no_change",
    "failed": "git_failed",
}


def _auto_commit_ticket_md(
    path: str, ticket_id: str, section: str, operation: str = "append-log"
) -> str:
    """精確路徑 auto-commit 單一 ticket md。

    設計（改用隔離索引 CAS）：
    - 提交機制委派 ``git_ops.commit_files_isolated``：``GIT_INDEX_FILE`` 指向
      獨立臨時 index，全程不觸碰共用 index，提交內容只由本函式傳入的單一
      路徑決定，不受共用 index 任何並行寫入影響（舊版「add 後再 pathspec
      commit」在 add 與 commit 之間仍有 TOCTOU 窗口——並行寫入者可在此窗口
      覆寫共用 index 中本路徑的 entry，使提交後共用 index 停在過期快照）。
    - commit message 格式：``chore(<ticket_id>): <operation> <section>``；
      session_id 可解析時附加 git trailer ``Session: <id>``（空白行分隔，
      多 PM session 協調層落地：commit author 同名無法歸屬 session，
      trailer 提供機械可讀的歸屬欄位）。無法解析時完全省略此段，不虛構
      session_id。``%s``（subject）不受影響，僅 body 新增此段。
    - 空 commit 防護：``commit_files_isolated`` 內建「write-tree 結果與
      HEAD tree 相同」短路（狀態 ``empty``），不產生空 commit、不報錯。
    - 不使用 ``--no-verify``（``commit_files_isolated`` 走 plumbing
      commit-tree，天然不觸發任何 pre-commit/commit-msg hook——非刻意繞過，
      guard 存在的目的是攔截「範圍不明的裸 commit」，此路徑以提交前後的
      自我驗證取代 guard 的把關角色，見 ``git_ops`` 模組 docstring）。

    cwd 採 ticket md 所在目錄，讓 git 自動解析其所屬 repo（worktree 場景下
    commit 進 worktree 分支，complete merge 帶回 main）。

    0.2.1-W3-257：新增 operation 參數取代原硬編 "append-log" 字面，避免
    add-spawn-request / resolve-spawn-request 等非 append-log 呼叫端的
    commit 訊息被誤標。預設值維持 "append-log"，既有呼叫端（未傳此參數）
    的 commit 訊息格式逐字不變（向後相容）。

    Args:
        path: ticket md 絕對路徑
        ticket_id: 主 ticket id（用於 commit message）
        section: 寫入的 section 名稱（用於 commit message）
        operation: 實際呼叫端操作名（用於 commit message，預設
            "append-log" 保留既有呼叫端行為不變）

    Returns:
        其中一個狀態字串：
        - ``"committed"``  已產生 commit
        - ``"no_change"``  body 無變更，graceful skip（不產生空 commit；正常情況，呼叫端不警告）
        - ``"git_failed"`` git 操作失敗（含目錄非 git repo、add/commit 步驟失敗、
          提交範圍自我驗證不符、HEAD 並行移動導致 CAS 放棄），graceful skip
          （呼叫端應警告）。改用 ``git_ops.commit_files_isolated`` 前另有獨立的
          ``"not_git_repo"`` 狀態；改用後兩者在底層已無法區分（皆回傳
          "failed"），故收斂為單一狀態——既有呼叫端一律以
          ``in ("not_git_repo", "git_failed")`` 群組判斷，行為不受影響。

    Raises:
        本函式不主動拋例外；呼叫端仍應以 try/except 包圍以涵蓋
        subprocess 環境級異常（如 git 未安裝 OSError），符合 graceful degrade。
    """
    md_path = Path(path)
    cwd = str(md_path.parent)

    message = f"chore({ticket_id}): {operation} {section}"
    session_id = resolve_current_session_id()
    if session_id:
        # git trailer 慣例：空白行 + "Key: Value"；session_id 無法解析
        # 時完全省略此段，不虛構值（規則 4 可觀測性的反面：寧缺不假）。
        message = f"{message}\n\nSession: {session_id}"

    result = commit_files_isolated([str(md_path)], message, cwd=cwd)
    return _STATUS_MAP[result["status"]]
