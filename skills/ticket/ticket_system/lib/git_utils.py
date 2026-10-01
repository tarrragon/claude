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

import os
import time
from pathlib import Path
from typing import Dict, Optional, Sequence

from .git_ops import (
    _is_cas_rejection,
    _is_lock_contention,
    _lock_paths_from_error,
    _run_git,
    commit_files_isolated,
)
from .lease import resolve_current_session_id

# ``ticket create`` 建票成功但 auto-commit 最終失敗時的專用 exit code。取 75
# （sysexits EX_TEMPFAIL：暫時性失敗，稍後可重試），與建票失敗（1）、用法錯誤（2）區分。
EXIT_AUTO_COMMIT_FAILED = 75

# git_ops._stale_lock_diagnosis 附在過期殘骸鎖錯誤文字內的標記；出現即不重試。
_STALE_DIAGNOSIS_MARK = "[殘骸診斷]"

# 暫時性鎖競爭的退避重試：等待（sleep）總和上限 5 秒，依序等 0.5、1、2 秒，其後每次 2 秒，
# 超出預算即停；預算只計 sleep，不含 git 嘗試本身耗時。
_COMMIT_RETRY_BUDGET_SECONDS = 5.0
# 重試等待的接縫：測試只替換此名稱，不改寫全域 ``time.sleep``
# （後者會被 subprocess 輪詢呼叫，污染測試假時鐘）。
_sleep = time.sleep
_COMMIT_RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
# 可重試失敗至少重試的次數，不受牆鐘影響（高負載下單次嘗試可耗時數秒，
# 若牆鐘先用盡會在零重試下放棄）。
_COMMIT_MIN_RETRIES = 3
# 最少重試次數之外的額外重試，其牆鐘（自首次嘗試起算）上限；須遠小於呼叫端 hook timeout（30 秒）。
_COMMIT_RETRY_WALL_CAP_SECONDS = 20.0
# 時鐘接縫：測試可注入假時鐘，使重試判定不受 git 子程序實際耗時影響。
_clock = time.monotonic

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
    path: str,
    ticket_id: str,
    section: str,
    operation: str = "append-log",
    extra_paths: Optional[Sequence[str]] = None,
    append_lines: Optional[Dict[str, str]] = None,
    result_out: Optional[dict] = None,
) -> str:
    """精確路徑 auto-commit 單一 ticket md。

    ``result_out`` 給定時以 ``commit_files_isolated`` 的完整結果（含 ``error``）
    填入，供呼叫端輸出失敗原因；回傳值語意不變。目錄非 git repo 時回傳
    ``"not_git_repo"``（無 repo 可提交，與提交失敗區分）。

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
        extra_paths: 同一提交要一併整檔納入的旁路寫入檔（如 create 的
            ``--source-ticket`` 來源票）。預設 None，既有呼叫端不變。
        append_lines: 路徑 -> 本次追加文字，該檔以「HEAD 版本 + 追加文字」
            提交而非整檔（如 topic-assignments.txt 這類多寫入者 append-only
            檔，整檔提交會吸入他人未提交的行）。預設 None。

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

    paths = [str(md_path), *(extra_paths or ())]
    # append_lines 僅在有值時才傳入，既有呼叫端的 commit_files_isolated 呼叫形態不變
    extra_kwargs = {"append_lines": append_lines} if append_lines else {}
    result = commit_files_isolated(paths, message, cwd=cwd, **extra_kwargs)
    if result_out is not None:
        result_out.update(result)
    status = _STATUS_MAP[result["status"]]
    if status == "git_failed" and "not a git repository" in (result.get("error") or "").lower():
        return "not_git_repo"
    return status


def _is_retryable_commit_failure(error: str) -> bool:
    """暫時性競爭（鎖或 HEAD 前進的 CAS 拒絕）才值得重試；殘骸鎖重試只是空等。"""
    if _STALE_DIAGNOSIS_MARK in error:
        return False
    return _is_lock_contention(error) or _is_cas_rejection(error)


_RETRY_LOG_DIR = os.path.join(".claude", "hook-logs", "ticket-commit-retry")


def _failure_reason(error: str) -> str:
    """日誌用失敗原因：CAS 拒絕與鎖名分開記，供統計並行失敗率。"""
    if _is_cas_rejection(error):
        return "cas_rejected"
    locks = _lock_paths_from_error(error)
    return "lock:" + ",".join(os.path.basename(p) for p in locks) if locks else "other"


def _log_commit_event(
    ticket_path: str, event: str, ticket_id: str, attempt: int, waited_s: float, error: str
) -> None:
    """重試／最終失敗寫入檔案日誌；寫入失敗只寫 stderr，不影響提交結果。"""
    import sys

    cwd = str(Path(ticket_path).parent)
    ticket_file_exists = Path(ticket_path).is_file()

    detail = (error or "").splitlines()[0] if error else ""
    line = (
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {event} ticket={ticket_id} "
        f"attempt={attempt} waited_s={waited_s:.2f} reason={_failure_reason(error)} "
        f"detail={detail}\n"
    )
    try:
        # 票檔不存在或解析不到 repo root 時不退回 process cwd（會寫進無關 repo
        # 的日誌），只寫 stderr
        ok, root, _err = _run_git(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
        if not (ticket_file_exists and ok and root.strip()):
            sys.stderr.write(f"[WARNING] 提交重試日誌未寫檔（無法解析 repo）：{line}")
            return
        base = root.strip()
        log_dir = os.path.join(base, _RETRY_LOG_DIR)
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "retry-" + time.strftime("%Y%m%d") + ".log")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        sys.stderr.write(f"[WARNING] 提交重試日誌寫入失敗：{exc}\n")


def auto_commit_ticket_md_with_retry(*args, **kwargs) -> Dict[str, object]:
    """呼叫 ``_auto_commit_ticket_md``，git_failed 且屬暫時性競爭時退避重試。

    重試預算語意：前 ``_COMMIT_MIN_RETRIES`` 次重試必做，不受牆鐘與等待預算限制；
    其後的額外重試須同時滿足「累計 sleep 不超過 ``_COMMIT_RETRY_BUDGET_SECONDS``」
    （只計等待，不含 git 嘗試耗時）與「自首次嘗試起的牆鐘不超過
    ``_COMMIT_RETRY_WALL_CAP_SECONDS``」。
    絕不移除任何鎖檔。每次重試與最終失敗各寫一筆檔案日誌。回傳
    ``{"status", "error", "attempts"}``；``error`` 僅在最終 status 為
    git_failed 時有值，供呼叫端輸出失敗原因。
    """
    start = _clock()
    attempts = 0
    waited = 0.0
    ticket_id = str(args[1]) if len(args) > 1 else str(kwargs.get("ticket_id", ""))
    log_cwd = str(args[0] if args else kwargs["path"])
    while True:
        detail: Dict[str, Optional[str]] = {}
        status = _auto_commit_ticket_md(*args, result_out=detail, **kwargs)
        attempts += 1
        if status != "git_failed":
            return {"status": status, "error": None, "attempts": attempts}
        error = detail.get("error") or ""
        delay = _COMMIT_RETRY_BACKOFF_SECONDS[
            min(attempts - 1, len(_COMMIT_RETRY_BACKOFF_SECONDS) - 1)
        ]
        within_extra_budget = (
            waited + delay <= _COMMIT_RETRY_BUDGET_SECONDS
            and _clock() - start + delay <= _COMMIT_RETRY_WALL_CAP_SECONDS
        )
        may_retry = attempts <= _COMMIT_MIN_RETRIES or within_extra_budget
        if not _is_retryable_commit_failure(error) or not may_retry:
            _log_commit_event(log_cwd, "final_failure", ticket_id, attempts, waited, error)
            return {"status": status, "error": error, "attempts": attempts}
        _log_commit_event(log_cwd, "retry", ticket_id, attempts, delay, error)
        _sleep(delay)
        waited += delay


def format_write_command_commit_failure(
    label: str, ticket_path: str, ticket_id: str, section: str,
    operation: str, error: str, attempts: int,
    extra_paths: Sequence[str] = (),
) -> str:
    """寫入命令 auto-commit 最終失敗的可見警告：原因、鎖檔路徑、補救指令。

    與 create 的警告同形（見 ``create._format_commit_failure_warning``），差別是
    寫入已落在 working tree 的既有票檔，補救指令的 commit message 依 operation 組出。
    多票命令以 ``extra_paths`` 傳入其餘票檔，補救指令的 ``git add`` 會列出全部路徑。
    """
    from .git_ops import _lock_paths_from_error

    lines = [
        f"[WARNING] [{label}] {ticket_id} 已寫入 working tree 但 auto-commit 失敗"
        f"（嘗試 {attempts} 次）；尚未入庫，exit code {EXIT_AUTO_COMMIT_FAILED}。",
        f"失敗原因：{error or '（git 未回報原因）'}",
    ]
    lock_paths = _lock_paths_from_error(error, str(Path(ticket_path).parent))
    if lock_paths:
        lines.append("鎖檔路徑：" + "；".join(lock_paths))
        lines.append(
            "鎖檔處置：工具不會自動刪除鎖。先確認沒有任何 git 行程在執行"
            "（例如 `pgrep -lf git`），再依鎖檔內容與時間判斷是否為殘骸，"
            "確認後才可手動移除。"
        )
    lines.append(
        f"補救指令（鎖排除後）：git add {' '.join([ticket_path, *extra_paths])} && "
        f"git commit -m \"chore({ticket_id}): {operation} {section}\""
        "（或 `ticket track commit` 以隔離索引提交）"
    )
    return "\n".join(lines) + "\n"


def commit_ticket_md_reporting(
    label: str, ticket_path: str, ticket_id: str, section: str,
    operation: str = "append-log", **kwargs,
) -> bool:
    """寫入命令共用的 auto-commit 收尾：提交、重試、失敗時輸出 WARNING。

    多票寫入請用 ``commit_ticket_mds_reporting``（單一 commit）。

    Returns:
        True 表最終失敗（git_failed 或例外），呼叫端應以 ``EXIT_AUTO_COMMIT_FAILED``
        結束。``not_git_repo`` 印 skipped 訊息但不算失敗（無 repo 可提交）。
    """
    import sys

    extra_paths = tuple(kwargs.get("extra_paths") or ())
    try:
        result = auto_commit_ticket_md_with_retry(
            ticket_path, ticket_id, section, operation=operation, **kwargs
        )
    except Exception as exc:
        sys.stderr.write(format_write_command_commit_failure(
            label, ticket_path, ticket_id, section, operation,
            f"{type(exc).__name__}: {exc}", 1, extra_paths,
        ))
        return True
    status = result["status"]
    if status == "not_git_repo":
        sys.stderr.write(
            f"[{label}] auto-commit skipped（not_git_repo，非致命）；"
            "body 已保留 working tree，可手動 git commit 持久化。\n"
        )
        return False
    if status == "git_failed":
        sys.stderr.write(format_write_command_commit_failure(
            label, ticket_path, ticket_id, section, operation,
            str(result.get("error") or ""), int(result.get("attempts") or 1),
            extra_paths,
        ))
        return True
    return False


def commit_ticket_mds_reporting(
    label: str, ticket_paths: Sequence[str], ticket_id: str, section: str,
    operation: str = "append-log", **kwargs,
) -> bool:
    """多票寫入命令的 auto-commit 收尾：所有票檔以單一 commit 提交。

    ``ticket_paths`` 去重、略過空字串並保留順序；第一個路徑為主票（決定 commit
    訊息的 ``ticket_id`` 與 git cwd），其餘走 ``extra_paths`` 併入同一提交。
    空清單視為無事可做（回 False，不產生 commit）。回傳語意同
    ``commit_ticket_md_reporting``。

    為何單一 commit：多票寫入是一個邏輯操作（如 set-parent 同時改舊父、新父、
    子三張），拆成逐票提交會讓中途失敗留下半套關係於歷史，也放大鎖競爭窗口。
    """
    paths = list(dict.fromkeys(str(p) for p in ticket_paths if p))
    if not paths:
        return False
    merged_extra = [*paths[1:], *(kwargs.pop("extra_paths", None) or ())]
    return commit_ticket_md_reporting(
        label, paths[0], ticket_id, section, operation=operation,
        extra_paths=list(dict.fromkeys(merged_extra)), **kwargs,
    )
