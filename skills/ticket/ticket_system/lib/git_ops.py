"""共用隔離索引提交。

``commit_files_isolated`` 供 ``ticket-md-auto-commit-hook.py`` 與
``lifecycle.complete()`` 共用：以 ``GIT_INDEX_FILE`` 指向獨立臨時 index，
全程不觸碰共用 index，提交內容只由呼叫端傳入的 ``paths`` 決定，不受共用
index 任何並行寫入影響（僅核對 --cached 範圍再裸 commit 仍有 TOCTOU 窗口，
實測命中過）。

隔離提交完整性三要件（見 ``.claude/references/bash-tool-usage-details.md``
「規則七詳細」）：
1. 檔案清單來源獨立於共用 index —— 呼叫端必須自帶 ``paths``（如 ticket md
   絕對路徑、worklog 路徑），禁止以 ``git diff --cached --name-only`` 產生
   清單。GIT_INDEX_FILE 只隔離「寫入端」，清單來源若改讀共用 index 的
   staged 狀態，隔離會在入口就已經漏掉。
2. 寫入端使用 ``GIT_INDEX_FILE`` 指向獨立臨時 index。
3. 提交前以 ``git diff --name-only`` 自檢實際變更範圍恰為 ``paths``，
   不符即放棄提交（不 update-ref）。

因不經過 ``git commit``，此路徑不會觸發任何 pre-commit/commit-msg hook
（含 bare-commit-guard-hook）——這是 plumbing 命令的固有行為，非刻意繞過。
guard 存在的目的是攔截「範圍不明的裸 commit」；本函式以自我驗證取代 guard
的把關角色：提交範圍由程式碼結構保證且提交後即時核驗，不依賴 guard 事後
攔截，故豁免 guard 不削弱其防護意圖。

GIT_INDEX_FILE 作用域（查驗結論）：``env`` 為 ``dict(os.environ)`` 的
區域複本，``env["GIT_INDEX_FILE"] = temp_index_path`` 只寫入此複本，從未
寫回 ``os.environ`` 本身，故不存在需要「unset」的全域狀態——僅
read-tree/add/write-tree 三步驟顯式傳入該 ``env``；
commit-tree/diff（自我驗證）/update-ref/後續共用 index 同步皆不帶
``env`` 參數（預設 ``None``），對應行程預設環境與共用 index，範圍分離
不依賴任何時間點的「unset」動作。

update-ref 成功後（HEAD 已推進），以 ``_sync_shared_index_after_commit``
將本次 ``paths`` 同步至共用 index（以新 HEAD 的 tree 為準，逐路徑
``update-index --index-info`` / ``--force-remove``），避免共用 index 對
這些路徑停留在舊 HEAD 狀態並隨時間累積凍結——凍結後任何後續裸 commit
會把這些路徑一併回退。此同步步驟失敗只 WARNING，不影響已完成的提交
（commit 與 HEAD 推進已成功，不應因收尾步驟失敗而讓呼叫端誤判並重試
造成重複提交）；僅動本次 ``paths`` 涉及項目，不做全量 read-tree（避免
覆蓋共用 index 中其他未提交的 staged 內容）。錯誤處理分支
（read-tree/add/write-tree/commit-tree/自我驗證不符/update-ref CAS 失敗）
在 ``_sync_shared_index_after_commit`` 呼叫之前即 ``return``，共用 index
不被觸碰。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from typing import Dict, List, Optional, Tuple

_GIT_TIMEOUT = 10
_MAX_RETRIES = 2
_RETRY_WAIT_SECONDS = 1


def _run_git(
    args: List[str],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout: int = _GIT_TIMEOUT,
    input_text: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """執行單次 git 命令，回傳 (success, stdout, stderr)。"""
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            input=input_text,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"git {' '.join(args[1:2])} 逾時"
    except FileNotFoundError:
        return False, "", "找不到 git"

    if result.returncode == 0:
        return True, result.stdout, ""
    return False, result.stdout, result.stderr.strip()


def _run_git_with_lock_retry(
    args: List[str],
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout: int = _GIT_TIMEOUT,
    max_retries: int = _MAX_RETRIES,
    wait_seconds: int = _RETRY_WAIT_SECONDS,
    input_text: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """遇 index.lock 競爭時等待重試一次（禁止刪除 lock 檔）。"""
    ok, out, err = _run_git(args, cwd=cwd, env=env, timeout=timeout, input_text=input_text)
    attempt = 1
    while not ok and "index.lock" in err and attempt < max_retries:
        time.sleep(wait_seconds)
        ok, out, err = _run_git(args, cwd=cwd, env=env, timeout=timeout, input_text=input_text)
        attempt += 1
    return ok, out, err


def _sync_shared_index_after_commit(
    paths: List[str], tree_sha: str, cwd: str
) -> None:
    """提交成功（update-ref 已推進 HEAD）後，將本次 ``paths`` 同步至共用
    index，內容取自新 HEAD 的 ``tree_sha``，避免共用 index 對這些路徑停留
    在舊 HEAD 狀態（凍結累積），日後任何裸 commit 回退這些路徑。

    僅動共用 index 中本次 ``paths`` 涉及的項目，不做全量 read-tree（避免
    覆蓋共用 index 中其他未提交的 staged 內容）。

    失敗只記錄 WARNING、不回傳錯誤——commit 與 update-ref 已成功，此步驟
    失敗不應讓呼叫端誤判整體提交失敗（那會導致重試造成重複提交）。
    此函式全程不帶 ``GIT_INDEX_FILE``（env 用行程預設環境），寫入對象即
    共用 index。
    """
    ok, ls_out, err = _run_git_with_lock_retry(
        ["git", "ls-tree", tree_sha, "--"] + paths, cwd=cwd
    )
    if not ok:
        print(f"[WARNING] 共用 index 同步失敗（ls-tree）：{err}", file=sys.stderr)
        return

    present: Dict[str, str] = {}
    for line in ls_out.splitlines():
        meta, _, path = line.partition("\t")
        if not path:
            continue
        parts = meta.split()
        if len(parts) < 3:
            continue
        mode, _obj_type, blob_sha = parts[0], parts[1], parts[2]
        present[path] = f"{mode} {blob_sha} 0\t{path}\n"

    index_info = "".join(present[p] for p in paths if p in present)
    if index_info:
        ok, _, err = _run_git_with_lock_retry(
            ["git", "update-index", "--index-info"], cwd=cwd, input_text=index_info
        )
        if not ok:
            print(f"[WARNING] 共用 index 同步失敗（update-index）：{err}", file=sys.stderr)

    missing = [p for p in paths if p not in present]
    if missing:
        ok, _, err = _run_git_with_lock_retry(
            ["git", "update-index", "--force-remove", "--"] + missing, cwd=cwd
        )
        if not ok:
            print(f"[WARNING] 共用 index 同步失敗（force-remove）：{err}", file=sys.stderr)


def commit_files_isolated(
    paths: List[str], message: str, cwd: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """在獨立臨時 index 中精確 stage ``paths`` 後以 plumbing 提交。

    Args:
        paths: 欲提交的檔案路徑清單，須獨立於共用 index（見 module docstring
            要件 1），呼叫端自帶（如 ticket md 絕對路徑）。
        message: commit message。
        cwd: git 命令執行目錄，預設為目前工作目錄所屬 repo。

    Returns:
        dict，含三個鍵：

        - ``status``：``"committed"``（已產生 commit）/
          ``"empty"``（paths 內容與 HEAD 相同，空 tree 短路，未提交）/
          ``"failed"``（任一步驟失敗或範圍自我驗證不符，未提交）
        - ``commit_sha``：``status == "committed"`` 時為新 commit SHA，否則 None
        - ``error``：``status == "failed"`` 時為失敗原因，否則 None
    """
    raw_deduped: List[str] = list(dict.fromkeys(p for p in paths if p))
    if not raw_deduped:
        return {"status": "empty", "commit_sha": None, "error": None}

    ok, root_out, err = _run_git_with_lock_retry(
        ["git", "rev-parse", "--show-toplevel"], cwd=cwd
    )
    if not ok:
        return {"status": "failed", "commit_sha": None, "error": err or "取得 repo root 失敗"}
    repo_root = root_out.strip()
    # git diff --name-only 一律回傳 repo-relative 路徑；呼叫端傳入的
    # paths 可能是絕對路徑（如 lifecycle.complete() 傳入 ticket_path 絕對
    # 路徑），此處統一正規化為 repo-relative，讓提交範圍自我驗證（要件 3）
    # 得以正確比對，避免絕對路徑輸入下恆判定不符而 commit 恆失敗。
    base_dir = cwd or os.getcwd()

    def _to_repo_relative(path: str) -> str:
        abs_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
        return os.path.relpath(os.path.abspath(abs_path), repo_root).replace(os.sep, "/")

    deduped: List[str] = list(dict.fromkeys(_to_repo_relative(p) for p in raw_deduped))
    cwd = repo_root

    ok, old_head_out, err = _run_git_with_lock_retry(
        ["git", "rev-parse", "HEAD"], cwd=cwd
    )
    if not ok:
        return {"status": "failed", "commit_sha": None, "error": err or "rev-parse HEAD 失敗"}
    old_head = old_head_out.strip()

    fd, temp_index_path = tempfile.mkstemp(prefix="ticket-commit-isolated-index-")
    os.close(fd)
    os.remove(temp_index_path)  # read-tree 會依需要建立獨立 index 檔
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = temp_index_path

    try:
        ok, _, err = _run_git_with_lock_retry(
            ["git", "read-tree", old_head], cwd=cwd, env=env
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}

        ok, _, err = _run_git_with_lock_retry(
            ["git", "add", "--"] + deduped, cwd=cwd, env=env
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}

        ok, tree_out, err = _run_git_with_lock_retry(
            ["git", "write-tree"], cwd=cwd, env=env
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}
        tree_sha = tree_out.strip()

        # 空 tree 短路：write-tree 產出的 tree 與 HEAD 現有 tree 相同，代表
        # deduped 內容與 HEAD 無差異，不產生空 commit。
        ok, old_tree_out, _err = _run_git_with_lock_retry(
            ["git", "rev-parse", f"{old_head}^{{tree}}"], cwd=cwd
        )
        if ok and old_tree_out.strip() == tree_sha:
            return {"status": "empty", "commit_sha": None, "error": None}

        ok, commit_out, err = _run_git_with_lock_retry(
            ["git", "commit-tree", tree_sha, "-p", old_head, "-m", message],
            cwd=cwd,
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}
        commit_sha = commit_out.strip()

        # 提交範圍自我驗證（要件 3）：不符即放棄，不 update-ref。
        ok, diff_out, err = _run_git_with_lock_retry(
            ["git", "diff", "--name-only", old_head, commit_sha], cwd=cwd
        )
        if not ok:
            return {"status": "failed", "commit_sha": None, "error": err}
        changed = {line for line in diff_out.splitlines() if line.strip()}
        if changed != set(deduped):
            return {
                "status": "failed",
                "commit_sha": None,
                "error": (
                    f"提交範圍自我驗證失敗，預期 {sorted(deduped)} 實得 "
                    f"{sorted(changed)}"
                ),
            }

        ok, _, err = _run_git_with_lock_retry(
            ["git", "update-ref", "HEAD", commit_sha, old_head], cwd=cwd
        )
        if not ok:
            return {
                "status": "failed",
                "commit_sha": None,
                "error": err or "HEAD 於提交期間被並行移動",
            }

        _sync_shared_index_after_commit(deduped, tree_sha, cwd)
        return {"status": "committed", "commit_sha": commit_sha, "error": None}
    finally:
        try:
            if os.path.exists(temp_index_path):
                os.remove(temp_index_path)
        except OSError:
            pass
