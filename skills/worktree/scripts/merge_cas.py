#!/usr/bin/env python3
"""
隔離索引 CAS 合併引擎

merge_branch_cas 是合併主流程的唯一入口；CheckResult／PreMergeCheck 為合併前檢查掛點的型別，
MergeOutcome 為結果。_sleep／_clock 是測試接縫，只在本模組替換，不 re-export。
"""

import contextlib
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, ContextManager, Optional

try:
    from .constants import DEFAULT_BASE_BRANCH
    from .messages import MergeMessages
except ImportError:
    # Fallback when running with scripts/ on sys.path (test 與直接執行情境)
    from constants import DEFAULT_BASE_BRANCH
    from messages import MergeMessages

# ===== 隔離索引 CAS 合併 =====
#
# 為何不用 `git merge`：它先寫共用 index 與工作區、最後才 update_ref；HEAD 被並行推進時
# update_ref 失敗，留下 MERGE_HEAD 與 staged 結果。此處全程只寫物件庫，ref 以 CAS 一步推進，
# 成功之後才碰共用 index。合併結果由 `git merge-tree --write-tree` 計算（不使用任何 index），
# 檔案清單一律走 NUL 分隔輸出，不經 shell 字詞切分。

_NUL = b"\0"
_ZERO_SHA_CHAR = "0"
_SHA_HEX_LEN = 40
_GIT_TIMEOUT_SECONDS = 60
_CONFLICT_DETAIL_MAX_CHARS = 500
# 重試預算複製自 .claude/skills/ticket/ticket_system/lib/git_utils.py 的
# retry_commit_attempt（worktree 套件以檔案路徑載入，無法 import ticket_system）：
# 前 _RETRY_MIN 次必做；其後額外重試須累計等待 <= _RETRY_BUDGET_SECONDS 且牆鐘 <= _RETRY_WALL_CAP_SECONDS。
_RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
_RETRY_MIN = 3
_RETRY_BUDGET_SECONDS = 5.0
_RETRY_WALL_CAP_SECONDS = 20.0
_RETRYABLE_MARKERS = ("index.lock", "cannot lock ref", "is at", "reference already exists")
# 測試接縫：只替換這兩個名稱，不改寫全域 time
_sleep = time.sleep
_clock = time.monotonic
_ISOLATED_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")


@dataclass(frozen=True)
class CheckResult:
    """合併前檢查的回傳值。passed 為 False 時 reason 會被印出，合併中止且不寫任何 ref。"""

    passed: bool
    reason: str = ""


# 簽名：(merge_commit_sha, target_ref, expected_old_sha, attempt) -> CheckResult
# 時機：commit-tree 之後、update-ref 之前，每次 CAS 嘗試都呼叫（attempt 從 1 起算）。
# commit 已在物件庫但無 ref 指向，檢查端可 `git worktree add --detach <path> <merge_commit_sha>`。
PreMergeCheck = Callable[[str, str, str, int], CheckResult]


@dataclass
class MergeOutcome:
    """merge_branch_cas 的結果。ok=False 時 HEAD 未動、未留任何 ref/MERGE_HEAD。"""

    ok: bool
    error: str = ""
    commit_sha: str = ""
    synced: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    attempts: int = 0


def _git_raw(args: list, repo: str, input_bytes: Optional[bytes] = None):
    """在 repo 執行 git，回傳 CompletedProcess（bytes）。"""
    env = {k: v for k, v in os.environ.items() if k not in _ISOLATED_ENV_DROP}
    return subprocess.run(
        ["git", *args], cwd=repo, input=input_bytes, capture_output=True,
        env=env, timeout=_GIT_TIMEOUT_SECONDS,
    )


def _git_out(args: list, repo: str) -> tuple[bool, str]:
    """執行 git，回傳 (成功, stdout 去尾端空白 或 stderr)。"""
    proc = _git_raw(args, repo)
    if proc.returncode == 0:
        return True, proc.stdout.decode("utf-8", "replace").strip()
    return False, proc.stderr.decode("utf-8", "replace").strip()


def _is_retryable(error: str) -> bool:
    return any(marker in error for marker in _RETRYABLE_MARKERS)


def _retry_delay_allowed(attempts: int, waited: float, delay: float, start: float) -> bool:
    if attempts <= _RETRY_MIN:
        return True
    return waited + delay <= _RETRY_BUDGET_SECONDS and _clock() - start + delay <= _RETRY_WALL_CAP_SECONDS


def _run_with_retry(attempt: Callable[[], tuple[str, str]]) -> tuple[str, str, int]:
    """attempt 回傳 (status, error)；status 為 'retry' 且錯誤屬暫時性競爭時退避重試。

    回傳 (最終 status, error, 嘗試次數)。絕不移除任何鎖檔。
    """
    start, waited, attempts = _clock(), 0.0, 0
    while True:
        status, error = attempt()
        attempts += 1
        if status != "retry":
            return status, error, attempts
        delay = _RETRY_BACKOFF_SECONDS[min(attempts - 1, len(_RETRY_BACKOFF_SECONDS) - 1)]
        if not _is_retryable(error) or not _retry_delay_allowed(attempts, waited, delay, start):
            return "abort", error, attempts
        _sleep(delay)
        waited += delay


def _resolve_commit(ref: str, repo: str) -> tuple[bool, str]:
    return _git_out(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], repo)


def _compute_merge_tree(old_head: str, branch_sha: str, repo: str) -> tuple[bool, str]:
    """三方合併得到 tree；文字衝突或其他失敗回傳 (False, 說明)。不碰任何 index。"""
    proc = _git_raw(["merge-tree", "--write-tree", "-z", old_head, branch_sha], repo)
    parts = proc.stdout.split(_NUL)
    if proc.returncode == 0:
        return True, parts[0].decode()
    if proc.returncode == 1:
        detail = " ".join(p.decode("utf-8", "replace") for p in parts[1:] if p)
        return False, MergeMessages.CAS_CONFLICT.format(detail=detail[:_CONFLICT_DETAIL_MAX_CHARS])
    return False, proc.stderr.decode("utf-8", "replace").strip() or MergeMessages.CAS_MERGE_TREE_FAILED


def _run_pre_merge_check(
    check: Optional[PreMergeCheck], commit: str, ref: str, expected_old: str, attempt: int
) -> str:
    """回傳空字串表示通過，否則為中止理由。檢查回傳失敗或拋例外皆視為不通過。"""
    if check is None:
        return ""
    try:
        result = check(commit, ref, expected_old, attempt)
    except Exception as exc:  # 檢查端故障不可放行合併；理由經 MergeOutcome.error 輸出
        return MergeMessages.CAS_CHECK_RAISED.format(error=exc)
    return "" if result.passed else (result.reason or MergeMessages.CAS_CHECK_FAILED)


def _trial_merge(branch: str, base: str, repo: str):
    """解析兩端並試算三方合併 tree（只寫物件）。回傳 (old_head, branch_sha, tree, 中止說明, 是否良性)。

    良性＝「已合併」與「ref 解析失敗」：都不是文字衝突，預檢放行，由取得名額後的既有路徑判定。
    """
    ok, old_head = _resolve_commit(f"refs/heads/{base}", repo)
    ok2, branch_sha = _resolve_commit(f"refs/heads/{branch}", repo)
    if not (ok and ok2):
        return "", "", "", MergeMessages.CAS_REF_UNRESOLVED.format(base=base, branch=branch), True
    if _git_raw(["merge-base", "--is-ancestor", branch_sha, old_head], repo).returncode == 0:
        return "", "", "", MergeMessages.CAS_ALREADY_MERGED.format(base=base, branch=branch), True
    ok, tree = _compute_merge_tree(old_head, branch_sha, repo)
    if not ok:
        return "", "", "", tree, False
    return old_head, branch_sha, tree, "", False


def precheck_merge_conflict(branch: str, base: str, repo: str) -> str:
    """進場排隊前的預檢：空字串＝可進場（含已合併、空合併、ref 解析失敗），否則為文字衝突說明。"""
    _, _, _, why, benign = _trial_merge(branch, base, repo)
    return "" if benign else why


def _prepare_candidate(branch: str, base: str, repo: str, message: str):
    """計算待合併 commit（只寫物件）。回傳 (merge_commit, old_head, 中止說明)。"""
    old_head, branch_sha, tree, why, _ = _trial_merge(branch, base, repo)
    if why:
        return None, "", why
    _, old_tree = _git_out(["rev-parse", f"{old_head}^{{tree}}"], repo)
    if tree == old_tree:
        return None, "", MergeMessages.CAS_EMPTY_MERGE
    ok, commit = _git_out(["commit-tree", tree, "-p", old_head, "-p", branch_sha, "-m", message], repo)
    if not ok:
        return None, "", MergeMessages.CAS_COMMIT_TREE_FAILED.format(error=commit)
    return commit, old_head, ""


def _cas_attempt(branch: str, base: str, repo: str, check: Optional[PreMergeCheck], message: str, box: dict):
    """單次嘗試：算 commit → 合併前檢查 → update-ref CAS。回傳 (status, error)。"""
    box["attempt"] = box.get("attempt", 0) + 1
    limit = box.get("max_retries")
    if limit is not None and box["attempt"] > limit + 1:
        return "abort", MergeMessages.CAS_RETRY_LIMIT.format(limit=limit, error=box.get("last_retry_error", ""))
    commit, old_head, why = _prepare_candidate(branch, base, repo, message)
    if commit is None:
        return "abort", why
    ref = f"refs/heads/{base}"
    reason = _run_pre_merge_check(check, commit, ref, old_head, box["attempt"])
    if reason:
        return "abort", reason
    proc = _git_raw(["update-ref", ref, commit, old_head], repo)
    if proc.returncode != 0:
        box["last_retry_error"] = proc.stderr.decode("utf-8", "replace").strip()
        return "retry", box["last_retry_error"]
    box["commit"], box["old_head"] = commit, old_head
    return "done", ""


def _parse_raw_diff(raw: bytes) -> list:
    """解析 `diff-tree -r -z --raw --no-renames` 為 [(舊 mode, 新 mode, 舊 sha, 新 sha, 狀態, 路徑)]。"""
    tokens = raw.split(_NUL)
    entries = []
    for meta, path in zip(tokens[0::2], tokens[1::2]):
        f = meta.decode().lstrip(":").split(" ")
        entries.append((f[0], f[1], f[2], f[3], f[4][:1], path.decode("utf-8", "surrogateescape")))
    return entries


def _worktree_sha(repo: str, path: str) -> Optional[str]:
    if not os.path.lexists(os.path.join(repo, path)):
        return None
    ok, sha = _git_out(["hash-object", "--", path], repo)
    return sha if ok else "?"


def _index_entries(repo: str) -> dict:
    """共用 index：路徑 -> (mode, sha)（stage 0）；有衝突 stage 的路徑為 None。"""
    proc = _git_raw(["ls-files", "-s", "-z"], repo)
    table = {}
    for rec in proc.stdout.split(_NUL):
        if not rec:
            continue
        meta, _, path = rec.decode("utf-8", "surrogateescape").partition("\t")
        mode, sha, stage = meta.split(" ")
        table[path] = (mode, sha) if stage == "0" else None
    return table


def _unchanged_since(entry: tuple, index: dict, repo: str) -> bool:
    """index 與工作區皆等於舊 HEAD 的該路徑才可同步。"""
    old_mode, _, old_sha, _, _, path = entry
    if set(old_sha) == {_ZERO_SHA_CHAR}:  # 新增檔：舊 HEAD 不存在，index 與工作區也須不存在
        return path not in index and _worktree_sha(repo, path) is None
    return index.get(path) == (old_mode, old_sha) and _worktree_sha(repo, path) == old_sha


def _apply_sync(repo: str, to_sync: list) -> tuple[str, str]:
    """把新 HEAD 的內容寫入共用 index 與工作區。回傳 (status, error)，供重試包裝。"""
    lines = []
    for _, new_mode, _, new_sha, status, path in to_sync:
        if status == "D":
            lines.append(f"0 {_ZERO_SHA_CHAR * _SHA_HEX_LEN}\t{path}")
        else:
            lines.append(f"{new_mode} {new_sha}\t{path}")
    payload = _NUL.join(line.encode("utf-8", "surrogateescape") for line in lines) + _NUL
    proc = _git_raw(["update-index", "-z", "--index-info"], repo, payload)
    if proc.returncode != 0:
        return "retry", proc.stderr.decode("utf-8", "replace").strip()
    for path in (e[5] for e in to_sync if e[4] == "D"):
        if os.path.lexists(os.path.join(repo, path)):
            os.remove(os.path.join(repo, path))
    present = [e[5] for e in to_sync if e[4] != "D"]
    if present:
        data = _NUL.join(p.encode("utf-8", "surrogateescape") for p in present) + _NUL
        proc = _git_raw(["checkout-index", "-f", "-z", "--stdin"], repo, data)
        if proc.returncode != 0:
            return "retry", proc.stderr.decode("utf-8", "replace").strip()
    return "done", ""


def _sync_shared_checkout(repo: str, base: str, old_head: str, new_head: str) -> tuple[list, list]:
    """只同步「index 與工作區皆等於舊 HEAD」的檔；其餘列為 skipped 不動。回傳 (synced, skipped)。"""
    ok, current = _git_out(["symbolic-ref", "-q", "--short", "HEAD"], repo)
    if not ok or current != base:
        return [], []  # 共用 checkout 不在 base 分支：其 index 與本次 ref 推進無關
    raw = _git_raw(["diff-tree", "-r", "-z", "--raw", "--no-renames", old_head, new_head], repo).stdout
    entries = _parse_raw_diff(raw)
    index = _index_entries(repo)
    to_sync = [e for e in entries if _unchanged_since(e, index, repo)]
    skipped = [e[5] for e in entries if e not in to_sync]
    if to_sync:
        status, error, _ = _run_with_retry(lambda: _apply_sync(repo, to_sync))
        if status != "done":
            return [], [e[5] for e in entries] + [MergeMessages.CAS_SYNC_FAILED.format(error=error)]
    return [e[5] for e in to_sync], skipped


def _verify_three_planes(repo: str, synced: list, new_head: str) -> list:
    """三平面核對：同步過的檔 index 與 HEAD 是否一致；回傳不一致的路徑。"""
    index = _index_entries(repo)
    bad = []
    for path in synced:
        proc = _git_raw(["ls-tree", "-z", new_head, "--", path], repo)
        head_meta = proc.stdout.decode("utf-8", "replace").split("\t")[0].split(" ")
        head_sha = head_meta[2] if len(head_meta) == 3 else None
        if (index.get(path) or (None, None))[1] != head_sha:
            bad.append(path)
    return bad


def merge_branch_cas(
    branch: str,
    repo: Optional[str] = None,
    base: str = DEFAULT_BASE_BRANCH,
    pre_merge_check: Optional[PreMergeCheck] = None,
    message: Optional[str] = None,
    max_retries: Optional[int] = None,
    hold: "Optional[ContextManager]" = None,
) -> MergeOutcome:
    """以 CAS 把 branch 合併進 base（--no-ff 等價：雙親代 commit）。合併主流程的唯一入口。

    pre_merge_check：預設 None（直接 update-ref）。簽名
    `(merge_commit_sha, target_ref, expected_old_sha, attempt) -> CheckResult`，
    在 commit-tree 之後、update-ref 之前呼叫。回傳 passed=False 或拋例外時不執行
    update-ref，ref 不變，理由放進 MergeOutcome.error 並印出。
    CAS 重試時每次嘗試依新 HEAD 產生不同 commit，因此每次嘗試都重新呼叫檢查
    （檢查成本隨重試次數倍增；是否快取或縮短由檢查端決定）。
    max_retries：預設 None（沿用 _run_with_retry 的預算）；給定時 CAS 重試超過該次數即中止，
    回報最後一次失敗原因，ref 不變、分支保留。
    hold：預設 None。給定時為 context manager，在第一次產生合併 commit 之前進入、所有嘗試
    （含 CAS 重試）結束後離開，涵蓋 update-ref 完成與各種中止路徑；合併閘門用它整段持有
    heavy 名額，使檢查窗口不含排隊時間。
    成功後共用 index/工作區只同步未被他人動過的檔。
    """
    if repo is None:
        from lib.git_utils import get_project_root  # 延後匯入：scripts 載入時 .claude 尚未進 sys.path

        repo = get_project_root()
    msg = message or f"Merge branch '{branch}'"
    box: dict = {"max_retries": max_retries}
    with (hold if hold is not None else contextlib.nullcontext()):
        status, error, attempts = _run_with_retry(
            lambda: _cas_attempt(branch, base, repo, pre_merge_check, msg, box)
        )
    if status != "done":
        return MergeOutcome(ok=False, error=error, attempts=attempts)
    synced, skipped = _sync_shared_checkout(repo, base, box["old_head"], box["commit"])
    return MergeOutcome(True, "", box["commit"], synced, skipped, attempts)
