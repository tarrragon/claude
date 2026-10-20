"""
進行中 git 操作偵測（merge／cherry-pick／revert／rebase）

自 hooks/bare-commit-guard-hook.py 依職責抽出，供需要判斷「目前 checkout
是否有他方可能待收尾的操作」的守衛共用。本模組只負責偵測，不產生任何
阻擋或提醒訊息（訊息在 hooks/bare_commit_guard/messages.py）。

失敗語意（fail-open）：偵測用的 git 子程序不存在、逾時、rc 非預期時，
回傳「無進行中操作」並雙通道回報（stderr 讓用戶看到守衛本次未生效、
logger 保留細節），不阻擋命令。與「確認無進行中操作」以 stderr 訊息區分。

偵測目錄語意：狀態檔（MERGE_HEAD 等）是各 worktree 獨立的，`git commit`
實際作用在 lib 解析的 effective_dir，故偵測目錄由 `_resolve_detect_dirs`
依解析結果決定；目標不可信時 payload cwd 與 project root 兩處都查。
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .git_command_parse import GitInvocation


def _base_dir(payload_cwd: Optional[str], project_root: Path) -> str:
    """命令開始執行的目錄：payload `cwd`，缺則 project root。"""
    return payload_cwd or str(project_root)


def _resolve_detect_dirs(
    payload_cwd: Optional[str],
    invocation: Optional[GitInvocation],
    project_root: Path,
) -> List[str]:
    """進行中狀態的偵測目錄清單（有序去重）。

    狀態檔（MERGE_HEAD 等）是各 worktree 獨立的，`git commit` 實際作用在
    lib 解析的 effective_dir（已含 `cd`、全部 `-C`、`~`、`..`）。目錄可知時
    只查該處；`dir_unknown` 為真（變數、命令替換、`cd -` 等）或無 invocation
    時目標不可信，payload cwd 與 project root 兩處都查，任一處有進行中
    狀態就擋。
    """
    if invocation is not None and not invocation.dir_unknown and invocation.effective_dir:
        return [invocation.effective_dir]
    return list(dict.fromkeys([_base_dir(payload_cwd, project_root), str(project_root)]))


def _git_dir_overrides(invocation: GitInvocation) -> "tuple[List[str], List[str]]":
    """子命令之前的 GIT_DIR／GIT_WORK_TREE 前綴（含 env 包裝）與
    --git-dir／--work-tree 選項值，回 (git_dirs, work_trees)。"""
    toks = invocation.statement[:invocation.subcommand_index]
    git_dirs: List[str] = []
    work_trees: List[str] = []
    for i, tok in enumerate(toks):
        name, eq, val = tok.partition("=")
        if name in ("GIT_DIR", "--git-dir"):
            target = git_dirs
        elif name in ("GIT_WORK_TREE", "--work-tree"):
            target = work_trees
        else:
            continue
        if not eq:
            if not name.startswith("--") or i + 1 >= len(toks):
                continue
            val = toks[i + 1]
        target.append(val)
    return git_dirs, work_trees


# 覆寫目標含變數或 ~ 而無法靜態解析時，偵測目錄清單中的標記（非真實路徑）
_UNRESOLVABLE_OVERRIDE = "<unresolvable-override>"


def _is_dynamic(path: str) -> bool:
    return any(c in path for c in "$`") or path.startswith("~")


def _follow_gitlink(path: str) -> str:
    """覆寫值是 gitlink 檔（worktree 的 `.git`，首行 `gitdir: <path>`）時
    回其指向的 git dir，否則原樣回傳。

    git 接受 gitlink 檔當 `--git-dir`，commit 實際落在指向的 git dir，
    MERGE_HEAD 等狀態檔也在那裡。相對指向以 gitlink 檔所在目錄為基準。
    讀不到或格式不符回 `_UNRESOLVABLE_OVERRIDE`（保守阻擋，不 fail-open）。
    """
    p = Path(path)
    if not p.is_file():
        return path
    try:
        first = p.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError) as exc:
        sys.stderr.write(f"[bare-commit-guard] gitlink 讀取失敗，保守阻擋：{path} ({exc})\n")
        return _UNRESOLVABLE_OVERRIDE
    prefix = "gitdir:"
    if not first.startswith(prefix) or not first[len(prefix):].strip():
        sys.stderr.write(f"[bare-commit-guard] gitlink 格式不符，保守阻擋：{path}\n")
        return _UNRESOLVABLE_OVERRIDE
    return str(p.parent / first[len(prefix):].strip())


def _override_dirs(
    payload_cwd: Optional[str], invocation: GitInvocation, project_root: Path
) -> Optional[List[str]]:
    """帶 git-dir 類覆寫的呼叫其偵測目錄；無覆寫回 None。

    git dir 本身即狀態檔所在（MERGE_HEAD 等直接位於其下），work tree
    也一併列入。路徑相對於該呼叫的 effective_dir（缺則 payload cwd／root）；
    含變數或 `~` 的覆寫值無法可信解析：除 cwd 與 root 兩處外加入
    `_UNRESOLVABLE_OVERRIDE` 標記，由 `_pending_operation_in_dirs` 保守阻擋。
    """
    git_dirs, work_trees = _git_dir_overrides(invocation)
    if not git_dirs and not work_trees:
        return None
    base = invocation.effective_dir or _base_dir(payload_cwd, project_root)
    dirs: List[str] = []
    for raw in git_dirs + work_trees:
        if _is_dynamic(raw):
            dirs.extend([_base_dir(payload_cwd, project_root), str(project_root)])
            dirs.append(_UNRESOLVABLE_OVERRIDE)
        else:
            dirs.append(_follow_gitlink(str(Path(base) / raw)))
    return dirs


def _pending_operation_in_git_dir(git_dir: str) -> Optional[str]:
    """目錄本身即 git dir（狀態檔直接位於其下）時的判別；純檔案檢查。"""
    g = Path(git_dir)
    if (g / "MERGE_HEAD").is_file():
        return _OP_MERGE
    if (g / "CHERRY_PICK_HEAD").is_file():
        return _OP_CHERRY_PICK
    if (g / "REVERT_HEAD").is_file():
        return _OP_REVERT
    if (g / "rebase-merge").is_dir() or (g / "rebase-apply").is_dir():
        if (g / "rebase-merge" / "amend").is_file():
            return _OP_REBASE_EDIT
        return _OP_REBASE
    return None


def _resolve_detect_dirs_multi(
    payload_cwd: Optional[str],
    invocations: Optional[List[GitInvocation]],
    project_root: Path,
) -> List[str]:
    """所有 commit 目標的偵測目錄聯集（有序去重）。

    每筆呼叫各自推導（含 git-dir 類覆寫目標）；無呼叫時等同
    `_resolve_detect_dirs(cwd, None, root)`。
    """
    if not invocations:
        return _resolve_detect_dirs(payload_cwd, None, project_root)
    dirs: List[str] = []
    for inv in invocations:
        override = _override_dirs(payload_cwd, inv, project_root)
        dirs.extend(override or _resolve_detect_dirs(payload_cwd, inv, project_root))
    return list(dict.fromkeys(dirs))


_TARGET_MERGE = "MERGE_HEAD"
_TARGET_OTHER = "cherry-pick／revert／rebase 狀態"


def _report_detect_failure(
    detect_dir, reason: str, logger, target: str = "MERGE_HEAD"
) -> None:
    """偵測失敗雙通道可見（品質基線規則 4）：stderr 讓用戶看到守衛本次未生效，
    log 保留細節。fail-open 放行不變。`target` 標示偵測對象，
    讓 MERGE_HEAD 與其他進行中狀態的失敗可分辨。"""
    scope = "合併狀態" if target == _TARGET_MERGE else "該狀態"
    sys.stderr.write(
        f"[bare-commit-guard] {target} 偵測失敗，本次未檢查{scope}："
        f"dir={detect_dir}, 原因={reason}\n"
    )
    if logger is not None:
        logger.warning(
            "%s 偵測失敗（%s），fail-open 放行：dir=%s", target, reason, detect_dir
        )


def _note_detect_failure(detect_dir, reason: str, logger, target: str, failures) -> None:
    """`failures` 為 list 時只收集原因（由呼叫端合併回報一次），否則立即回報。"""
    if failures is not None:
        failures.append(reason)
        return
    _report_detect_failure(detect_dir, reason, logger, target)


def _merge_in_progress(detect_dir, logger=None, failures=None) -> bool:
    """`MERGE_HEAD` 可解析即有未收尾的合併；此時裸 commit 會把合併收尾成
    merge commit（可能是他方的合併）。

    rev-parse -q --verify：rc 0 = 有合併；rc 1 = 無此 ref（正常，不寫 log）；
    其他 rc、逾時、git 不存在 = 偵測失敗，fail-open 放行但寫 warning
    （與「無合併」區分，否則偵測失效不可見）。
    """
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            cwd=str(detect_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        _note_detect_failure(
            detect_dir, f"{type(exc).__name__}: {exc}", logger, _TARGET_MERGE, failures
        )
        return False
    if result.returncode == 0:
        return True
    if result.returncode != 1:
        _note_detect_failure(
            detect_dir,
            f"rc={result.returncode}, stderr={(result.stderr or '').strip()}",
            logger, _TARGET_MERGE, failures,
        )
    return False


# 進行中操作的狀態種類（_other_operation_state 回傳值）
_OP_CHERRY_PICK = "cherry-pick"
_OP_REVERT = "revert"
_OP_REBASE = "rebase"
_OP_REBASE_EDIT = "rebase-edit"
_OP_MERGE = "merge"
# 一律擋裸 commit 的種類（rebase-edit 只警告）
_OP_UNRESOLVABLE = "unresolvable-override"
_BLOCKING_OPS = (_OP_MERGE, _OP_CHERRY_PICK, _OP_REVERT, _OP_REBASE, _OP_UNRESOLVABLE)

_GIT_PATH_NAMES = (
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "rebase-merge",
    "rebase-apply",
    "rebase-merge/amend",
)


def _other_operation_state(detect_dir, logger=None, failures=None) -> Optional[str]:
    """判別 cherry-pick／revert／rebase 進行中狀態（MERGE_HEAD 另由
    `_merge_in_progress` 處理）。

    狀態檔路徑以 `git rev-parse --git-path` 取得（worktree 的 git dir 不同，
    不可手拼 `.git/`），相對路徑以 detect_dir 為基準。判別：
    CHERRY_PICK_HEAD 存在 -> cherry-pick；REVERT_HEAD 存在 -> revert；
    rebase-merge 或 rebase-apply 目錄存在 -> rebase，其中 rebase-merge/amend
    也存在 -> rebase-edit（edit 停下，已提交完畢等待修改）。
    偵測失敗（git 不存在、rc 非 0、逾時）fail-open 回 None，並雙通道回報。
    """
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "rev-parse"]
            + [a for n in _GIT_PATH_NAMES for a in ("--git-path", n)],
            cwd=str(detect_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        _note_detect_failure(
            detect_dir, f"{type(exc).__name__}: {exc}", logger, _TARGET_OTHER, failures
        )
        return None
    lines = (result.stdout or "").splitlines()
    if result.returncode != 0 or len(lines) != len(_GIT_PATH_NAMES):
        _note_detect_failure(
            detect_dir,
            f"rc={result.returncode}, stderr={(result.stderr or '').strip()}",
            logger, _TARGET_OTHER, failures,
        )
        return None
    paths = {
        name: (Path(detect_dir) / line)  # 絕對路徑會覆蓋 detect_dir
        for name, line in zip(_GIT_PATH_NAMES, lines)
    }
    if paths["CHERRY_PICK_HEAD"].is_file():
        return _OP_CHERRY_PICK
    if paths["REVERT_HEAD"].is_file():
        return _OP_REVERT
    if paths["rebase-merge"].is_dir() or paths["rebase-apply"].is_dir():
        if paths["rebase-merge/amend"].is_file():
            return _OP_REBASE_EDIT
        return _OP_REBASE
    return None


def _pending_operation(detect_dir, logger=None) -> Optional[str]:
    """合併優先，其次 cherry-pick／revert／rebase；皆無回 None。

    MERGE_HEAD 偵測失敗代表 git 整體不可用，第二次偵測必同樣失敗：
    此時合併回報一次（標示兩個偵測對象）並略過第二次呼叫，fail-open。
    """
    failures: list = []
    if _merge_in_progress(detect_dir, logger, failures):
        return _OP_MERGE
    if failures:
        _report_detect_failure(
            detect_dir, failures[0], logger, f"{_TARGET_MERGE} 與{_TARGET_OTHER}"
        )
        return None
    return _other_operation_state(detect_dir, logger)


def _pending_operation_in_dirs(detect_dirs, logger=None) -> Optional[str]:
    """多個偵測目錄：任一處有阻擋型進行中狀態就回該狀態，其次 rebase-edit。"""
    found = []
    for d in detect_dirs:
        if d == _UNRESOLVABLE_OVERRIDE:
            found.append(_OP_UNRESOLVABLE)
            continue
        # d 可能是 work tree，也可能是覆寫指定的 git dir 本身，兩種都查
        op = _pending_operation(d, logger) or _pending_operation_in_git_dir(d)
        if op:
            found.append(op)
    for op in found:
        if op in _BLOCKING_OPS:
            return op
    return found[0] if found else None
