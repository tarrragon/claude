"""
並行派發範圍判定（派發登記讀取、並行期目標過濾）

自 hooks/bare-commit-guard-hook.py 依職責抽出，供需要「只計入與本次 commit
同一 checkout 的活躍派發」的守衛共用。涵蓋三件事：

1. 派發登記讀取：活躍派發記錄、宣告範圍以票面現行 where.files 為準。
2. 擁有者 session 已結束（orphan_confirmed）條目的排除。
3. commit 目標 checkout 推導與派發條目過濾（-C／cd／GIT_DIR 類覆寫）。

失敗語意：
- 讀登記失敗：`_get_active_dispatches_safe` 回空清單（fail-open，呼叫端降級為
  非並行期 WARN）。
- 讀票面 where.files 失敗：退回派發快照並寫 warning，不新增放行或阻擋路徑。
- 讀 pm-registry 失敗：fail-closed（全數條目維持佔用，不把讀不到當成 session
  已結束）。
- 目標 checkout 無法判定、或 commit 帶 GIT_DIR／--git-dir 類覆寫：回 None，
  呼叫端不過濾、全數計入（保守方向，避免放寬判定開出繞過）。
- `git rev-parse --show-toplevel` 異常（非 128 的 rc、逾時）：fail-open 不過濾，
  並雙通道回報。
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .dispatch_tracker import filter_dispatches_for_checkout, get_active_dispatches
from .git_command_parse import GitInvocation
from .git_operation_state import _report_detect_failure
from .pm_registry import (
    DEGRADED_READ_KEY,
    classify_ownership,
    get_registry_paths,
    read_registry,
)


def _get_active_dispatches_safe(project_root: Path) -> List[Dict]:
    """取得目前活躍派發完整記錄，讀取失敗時保守回傳空清單（fail-open，降級為 WARN）。"""
    try:
        return get_active_dispatches(project_root)
    except Exception:
        return []


def _read_ticket_where_files(ticket_id: str, project_root: Path) -> List[str]:
    """讀票面現行 where.files；票檔找不到或 frontmatter 解析不出時拋
    ValueError（呼叫端據此退回快照）。可讀但 where.files 為空則回傳 []。
    """
    from lib.hook_ticket import extract_where_files

    return extract_where_files(ticket_id, project_root, raise_on_missing=True)


def _with_live_declared_files(
    dispatches: List[Dict], project_root: Path, logger
) -> List[Dict]:
    """回傳宣告範圍以票面現行 where.files 為準的派發記錄副本。

    派發記錄的 `files` 是派發當下的快照，派發後 set-where／補入／手改票面
    不會同步回記錄。ticket_id 為空、票不存在或解析失敗時退回快照並寫
    warning（行為與修前相同，不新增 fail-open／fail-closed 路徑）。
    """
    resolved: List[Dict] = []
    for dispatch in dispatches:
        ticket_id = dispatch.get("ticket_id") or ""
        if not ticket_id:
            logger.warning("派發記錄無 ticket_id，宣告範圍退回派發快照")
            resolved.append(dispatch)
            continue
        try:
            live_files = _read_ticket_where_files(ticket_id, project_root)
        except Exception as exc:
            logger.warning(
                "讀取票面 where.files 失敗（%s），宣告範圍退回派發快照：%s",
                ticket_id, exc,
            )
            resolved.append(dispatch)
            continue
        resolved.append({**dispatch, "files": live_files})
    return resolved


def _read_registry_sessions(project_root: Path, logger) -> "tuple[Dict, bool]":
    """回傳 (sessions, available)。任何讀取失敗一律 available=False
    （fail-closed：不得把讀不到當成 session 已結束）。"""
    try:
        paths = get_registry_paths(cwd=str(project_root), logger=logger)
        if paths is None:
            return {}, False
        data = read_registry(paths[0], logger=logger)
    except Exception as exc:
        logger.warning("讀取 pm-registry 失敗，派發條目全數維持佔用：%s", exc)
        return {}, False
    if data.get(DEGRADED_READ_KEY, False):
        return {}, False
    return data.get("sessions", {}) or {}, True


def _exclude_orphan_confirmed(
    dispatches: List[Dict], project_root: Path, self_session_id: str, logger
) -> List[Dict]:
    """九修正：排除擁有者 session 已結束（orphan_confirmed）的派發條目。

    背景代理人隨擁有者 session 程序結束，該 session 已 graceful release
    後其條目不可能再有人寫檔。僅排除 orphan_confirmed；orphan_suspected、
    unknown_owner、registry_unavailable、self、cross_session_alive 維持
    佔用。registry 讀取失敗為 fail-closed（全數維持佔用）。
    不改登記檔，只改本守衛的佔用判定。
    """
    if not any(d.get("session_id") for d in dispatches):
        return dispatches
    sessions, available = _read_registry_sessions(project_root, logger)
    kept: List[Dict] = []
    for dispatch in dispatches:
        ownership = classify_ownership(
            dispatch.get("session_id") or "", self_session_id, sessions, available
        )
        if ownership == "orphan_confirmed":
            logger.warning(
                "排除擁有者 session 已結束的派發條目：ticket_id=%s session_id=%s",
                dispatch.get("ticket_id"), dispatch.get("session_id"),
            )
            continue
        kept.append(dispatch)
    return kept


_GIT_DIR_ENV_NAMES = ("GIT_DIR=", "GIT_WORK_TREE=")
_GIT_DIR_OPTIONS = ("--git-dir", "--work-tree")


def _overrides_git_dir(inv: GitInvocation) -> bool:
    """commit 呼叫是否以 GIT_DIR／GIT_WORK_TREE（環境變數前綴或 env 包裝）
    或 --git-dir／--work-tree 選項改寫目標；子命令之前的 token 即涵蓋三者。
    """
    for tok in inv.statement[:inv.subcommand_index]:
        if tok.startswith(_GIT_DIR_ENV_NAMES):
            return True
        if tok.split("=", 1)[0] in _GIT_DIR_OPTIONS:
            return True
    return False


def _commit_target_checkouts(
    invocations: Optional[List[GitInvocation]], logger
) -> Optional[List[Path]]:
    """全部 commit 呼叫的目標 checkout 聯集；任一呼叫無法判定或帶 git-dir
    類覆寫則回 None（呼叫端不過濾，全數計入，保守方向）。
    """
    if not invocations:
        return None
    targets: List[Path] = []
    for inv in invocations:
        if _overrides_git_dir(inv):
            logger.info("commit 帶 GIT_DIR／--git-dir 類覆寫，不依工作位置過濾")
            return None
        target = _commit_target_checkout([inv], logger)
        if target is None:
            return None
        targets.append(target)
    return targets


def _filter_dispatches_for_targets(
    dispatches: List[Dict], targets: Optional[List[Path]]
) -> List[Dict]:
    """條目工作位置等於任一目標即保留（依原順序、不重複）。"""
    if targets is None:
        return dispatches
    kept_ids = set()
    for target in targets:
        for d in filter_dispatches_for_checkout(dispatches, target):
            kept_ids.add(id(d))
    return [d for d in dispatches if id(d) in kept_ids]


def _commit_target_checkout(
    invocations: Optional[List[GitInvocation]], logger
) -> Optional[Path]:
    """commit 實際作用的 checkout 根；無法判定回 None（呼叫端不過濾，保守計入）。

    沿用 `_resolve_detect_dirs` 的目錄語意：目錄可知時取 effective_dir
    （含 -C、cd）；無解析結果或 dir_unknown 時不猜，回 None。
    rev-parse 失敗時 fail-open 並雙通道回報。
    """
    if not invocations:
        return None
    inv = invocations[0]
    if inv.dir_unknown or not inv.effective_dir:
        return None
    if not Path(inv.effective_dir).is_dir():
        # 目錄不存在：git 本身也會失敗，屬預期情境，僅記 log、不過濾
        logger.info("commit 目標目錄不存在，不依工作位置過濾：%s", inv.effective_dir)
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", inv.effective_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        top = proc.stdout.strip()
        if proc.returncode == 0 and top:
            return Path(top)
        if proc.returncode == 128:
            # 非 git repo：commit 本身也無從作用，預期情境，僅記 log、不過濾
            logger.info("commit 目標目錄非 git repo，不依工作位置過濾：%s", inv.effective_dir)
            return None
        reason = "rev-parse rc={}".format(proc.returncode)
    except (OSError, subprocess.SubprocessError) as exc:
        reason = str(exc)
    _report_detect_failure(inv.effective_dir, reason, logger, target="checkout 根")
    return None
