#!/usr/bin/env python3
"""
cleanup 子命令：三閘門安全清理 worktree

cmd_cleanup 為入口；Level 1（未 commit）、Level 2（未推送）、Level 3（未合併）閘門、
鎖處理、逾時移除與半刪收尾皆在本模組。共用的 worktree 查找與 git 包裝自 worktree_manager 匯入。
WORKTREE_REMOVE_TIMEOUT_SECONDS 是測試注入點，只在本模組替換。
"""

import os
import re
import shlex
import time
from typing import Optional

try:
    from .constants import BRANCH_FORCE_DELETE_FLAG, CLEANUP_OUTPUT_WIDTH, DEFAULT_BASE_BRANCH
    from .messages import CleanupMessages
    from .merge_gate import emit_gate_line
    from .worktree_manager import (
        _check_working_tree_clean, _extract_ticket_id_from_worktree, _validate_and_find_worktree,
        get_project_root, get_worktree_list, is_protected_branch, is_valid_ticket_id, run_git_command,
    )
except ImportError:
    # Fallback when running with scripts/ on sys.path (test 與直接執行情境)
    from constants import BRANCH_FORCE_DELETE_FLAG, CLEANUP_OUTPUT_WIDTH, DEFAULT_BASE_BRANCH
    from messages import CleanupMessages
    from merge_gate import emit_gate_line
    from worktree_manager import (
        _check_working_tree_clean, _extract_ticket_id_from_worktree, _validate_and_find_worktree,
        get_project_root, get_worktree_list, is_protected_branch, is_valid_ticket_id, run_git_command,
    )


def _is_branch_merged_to_base(branch: str, base: str = DEFAULT_BASE_BRANCH) -> bool:
    """
    判斷分支是否已合併到 base 分支

    使用 git merge-base --is-ancestor <branch> <base>，只看結束碼，
    不解析 git branch --merged 的輸出（worktree 已 checkout 的分支帶「+ 」前綴）。
    分支不存在與未合併皆回傳非零，判為未合併。

    Args:
        branch: 分支名稱
        base: 基礎分支，預設 "main"

    Returns:
        bool: True 表示已合併，False 表示未合併或無法判斷
    """
    success, _ = run_git_command(["merge-base", "--is-ancestor", branch, base])
    return success


def _is_branch_pushed(branch: str) -> bool:
    """
    判斷本地分支 tip 是否已在任一遠端 ref 上

    feat／agent 分支從不推送同名分支，合併後只推 main；故不比對 origin 同名分支，
    改問「哪些遠端 ref 含此 tip」（for-each-ref --contains，--format 輸出無行首標記）。
    分支不存在時 git 回非零，判為未推送。

    Args:
        branch: 分支名稱（短名稱）

    Returns:
        bool: True 表示至少一個遠端 ref 含此分支 tip，False 表示未推送或無法判斷
    """
    success, output = run_git_command(
        ["for-each-ref", f"--contains=refs/heads/{branch}",
         "--format=%(refname)", "refs/remotes"]
    )
    return success and bool(output.strip())


def _cleanup_check_level1(worktree_path: str) -> tuple[bool, int]:
    """
    Level 1 閘門：檢查未 commit 變更（永不可繞過）

    Args:
        worktree_path: worktree 絕對路徑

    Returns:
        tuple[bool, int]:
            - bool: True 表示通過（無未 commit 變更）
            - int: 未 commit 變更數量
    """
    clean, count = _check_working_tree_clean(worktree_path)
    if clean:
        return True, count
    # 半刪 worktree（status 全為 tracked 刪除且 HEAD 為 main 祖先）改走收尾路徑，
    # 判定重用 _recovery_unmet_conditions；有 untracked 或 modified 照樣擋下
    if not _recovery_unmet_conditions(worktree_path):
        return True, count
    return False, count


def _cleanup_check_level2(branch: str) -> tuple[bool, str]:
    """
    Level 2 閘門：檢查未 push 狀態（可被 --force 略過）

    透過比較 branch 和 origin/branch 的 commit 差距判斷是否已 push。
    若 origin 無對應分支（尚未 push 過），視為未 push。

    Args:
        rule8-exempt: relocation:自 .claude/skills/worktree/scripts/worktree_manager.py 逐字搬移
        branch: 分支名稱（如 "feat/0.1.1-W9-002"）

    Returns:
        tuple[bool, str]:
            - bool: True 表示通過（已 push 或無 origin）
            - str: 若 False，包含警告說明訊息
    """
    if _is_branch_pushed(branch):
        return True, ""

    warning_msg = CleanupMessages.LEVEL2_WARNING.format(branch=branch)
    return False, warning_msg


def _cleanup_check_level3(branch: str, base: str = DEFAULT_BASE_BRANCH) -> tuple[bool, str]:
    """
    Level 3 閘門：檢查分支是否已合併到 base（可被 --force 略過）

    透過 git branch --merged 判斷分支是否已被合併。

    Args:
        rule8-exempt: relocation:自 .claude/skills/worktree/scripts/worktree_manager.py 逐字搬移
        branch: 分支名稱（如 "feat/0.1.1-W9-002"）
        base: 基礎分支，預設 "main"

    Returns:
        tuple[bool, str]:
            - bool: True 表示通過（已合併到 base）
            - str: 若 False，包含警告說明訊息
    """
    if _is_branch_merged_to_base(branch, base):
        return True, ""

    warning_msg = CleanupMessages.LEVEL3_WARNING.format(branch=branch, base=base)
    return False, warning_msg


# worktree remove 逐檔刪除，大型工作樹（數千檔）在高負載下遠超 git_utils 預設 10 秒；
# 逾時殺掉 git 會留下全量 tracked 刪除的半刪 worktree
WORKTREE_REMOVE_TIMEOUT_SECONDS = 300


def _parse_worktree_lock(porcelain: str, worktree_path: str) -> Optional[str]:
    """從 `git worktree list --porcelain` 輸出取得指定 worktree 的鎖原因；未鎖回 None（無原因的鎖回空字串）。"""
    target = os.path.realpath(worktree_path)
    for block in porcelain.split("\n\n"):
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("worktree "):
            continue
        if os.path.realpath(lines[0][len("worktree "):]) != target:
            continue
        for line in lines[1:]:
            if line == "locked" or line.startswith("locked "):
                return line[len("locked"):].strip()
    return None


def _lock_holder_alive(reason: str) -> str:
    """從鎖原因擷取 pid 並判斷存活；回傳訊息用字串。"""
    match = re.search(r"pid (\d+)", reason)
    if not match:
        return "原因未含 pid，無法判斷存活"
    pid = int(match.group(1))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return f"pid {pid} 已不存在"
    except PermissionError:
        return f"pid {pid} 存活（屬其他使用者）"
    return f"pid {pid} 存活"


def _cleanup_handle_lock(worktree_path: str, unlock: bool) -> tuple[bool, str]:
    """移除前處理 worktree 鎖。回傳 (可繼續, 停手說明)；鎖可能屬仍在使用的代理人，未明示 --unlock 不解鎖。"""
    ok, porcelain = run_git_command(["worktree", "list", "--porcelain"])
    reason = _parse_worktree_lock(porcelain, worktree_path) if ok else None
    if reason is None:
        return True, ""
    holder = _lock_holder_alive(reason)
    if not unlock:
        return False, CleanupMessages.REMOVE_LOCKED.format(reason=reason or "（無原因）", holder=holder)
    ok, output = run_git_command(["worktree", "unlock", worktree_path])
    if not ok:
        return False, CleanupMessages.UNLOCK_FAILED.format(error=output)
    return True, ""


def _timed_git_remove(worktree_path: str, extra_args: list[str]) -> tuple[bool, str]:
    """以 WORKTREE_REMOVE_TIMEOUT_SECONDS 執行 worktree remove，實際耗時寫入 worktree-merge.log。"""
    started = time.monotonic()
    ok, output = run_git_command(
        ["worktree", "remove", *extra_args, worktree_path], timeout=WORKTREE_REMOVE_TIMEOUT_SECONDS
    )
    elapsed = time.monotonic() - started
    result = "成功" if ok else "失敗"
    flags = "".join(f" {arg}" for arg in extra_args)
    emit_gate_line(
        str(get_project_root()),
        f"[清理移除]worktree remove{flags}｜target {worktree_path}"
        f"｜耗時 {elapsed:.1f}s｜上限 {WORKTREE_REMOVE_TIMEOUT_SECONDS}s｜結果 {result}",
    )
    return ok, output


def _recovery_unmet_conditions(worktree_path: str) -> list[str]:
    """半刪收尾的兩條件：status 全為 tracked 刪除、HEAD 為 main 祖先。回傳不成立項（空表示可收尾）。"""
    unmet = []
    ok, status = run_git_command(["status", "--porcelain"], cwd=worktree_path, timeout=WORKTREE_REMOVE_TIMEOUT_SECONDS)
    lines = [line for line in status.splitlines() if line] if ok else []
    others = [line for line in lines if not line.startswith(" D")]
    if not ok:
        unmet.append(f"無法讀取 status：{status}")
    elif not lines:
        unmet.append("status 無任何 tracked 刪除（不是半刪狀態）")
    elif others:
        unmet.append(f"status 含非 tracked 刪除項 {len(others)} 筆（untracked 或 modified），例：{others[0]}")
    ancestor_ok, _ = run_git_command(
        ["merge-base", "--is-ancestor", "HEAD", DEFAULT_BASE_BRANCH], cwd=worktree_path
    )
    if not ancestor_ok:
        unmet.append(f"HEAD 不是 {DEFAULT_BASE_BRANCH} 的祖先（有未併入的 commit）")
    return unmet


def _cleanup_recover(worktree_path: str, original_error: str) -> tuple[bool, str]:
    """remove 失敗後的收尾：兩條件皆成立才 remove --force 並 prune，否則停手並列出不成立項。"""
    unmet = _recovery_unmet_conditions(worktree_path)
    if unmet:
        return False, CleanupMessages.RECOVER_REFUSED.format(
            error=original_error, unmet="\n".join(f"  - {item}" for item in unmet)
        )
    ok, output = _timed_git_remove(worktree_path, ["--force"])
    if not ok:
        return False, CleanupMessages.REMOVE_FAILED.format(error=output)
    run_git_command(["worktree", "prune"])
    return True, ""


def _cleanup_execute(worktree_path: str, branch: str, unlock: bool = False) -> tuple[bool, str]:
    """
    執行 worktree 清理（移除 worktree 目錄和分支）

    依序執行：
    1. 讀鎖：有鎖停手回報，--unlock 才解鎖
    2. git worktree remove <path>（逾時 WORKTREE_REMOVE_TIMEOUT_SECONDS）；
       失敗時若為可證明安全的半刪狀態則 --force 收尾並 prune
    3. git branch -d <branch>；失敗視為清理未完成（回傳 False，rc 非 0）

    Returns:
        tuple[bool, str]: (worktree 與分支均已清理, 結果說明)
    """
    can_continue, lock_msg = _cleanup_handle_lock(worktree_path, unlock)
    if not can_continue:
        return False, lock_msg

    success, output = _timed_git_remove(worktree_path, [])
    if not success:
        success, output = _cleanup_recover(worktree_path, output)
        if not success:
            return False, output

    success, output = run_git_command(["branch", "-d", branch])
    if not success:
        return False, CleanupMessages.BRANCH_DELETE_FAILED.format(
            branch=branch,
            force_flag=BRANCH_FORCE_DELETE_FLAG
        )

    success_msg = CleanupMessages.CLEANUP_SUCCESS.format(path=worktree_path, branch=branch)
    return True, success_msg


def _cleanup_check_level2_and_3(branch: str, force: bool) -> tuple[bool, int]:
    """
    執行 Level 2/3 驗證並輸出結果（M2 修復：從 _cleanup_single 拆分）

    Args:
        branch: 分支名稱
        force: 是否略過警告

    Returns:
        tuple[bool, int]: (驗證通過, exit_code)
            - 若 exit_code != 0 表示被阻擋，應立即返回
            - 若 exit_code == 0 表示通過或被 --force 略過
    """
    # Level 2: 未 push 檢查
    passed, warning_msg = _cleanup_check_level2(branch)
    if not passed:
        print(f"  Level 2 檢查：失敗")
        print()
        print(warning_msg)
        if not force:
            return False, 1
        print()
        print("[警告] 使用 --force 略過此警告，繼續清理")
    else:
        print(f"  Level 2 檢查：通過（已 push 到 origin）")

    # Level 3: 未合併檢查
    passed, warning_msg = _cleanup_check_level3(branch)
    if not passed:
        print(f"  Level 3 檢查：失敗")
        print()
        print(warning_msg)
        if not force:
            return False, 1
        print()
        print("[警告] 使用 --force 略過此警告，繼續清理")
    else:
        print(f"  Level 3 檢查：通過（已合併到 main）")

    return True, 0


def _cleanup_print_initial_header(ticket_id: str) -> None:
    """
    輸出清理操作的開始標題

    W16 修復：認知負擔指數 = 2 (<= 10)

    Args:
        ticket_id: Ticket ID
    """
    print(f"正在清理 Ticket {ticket_id} 的 worktree...")
    print()


def _cleanup_execute_and_report(
    path: str,
    branch: str,
    unlock: bool = False
) -> int:
    """
    執行清理操作並輸出結果

    W16 修復：認知負擔指數 = 6 (<= 10)

    Args:
        path: worktree 絕對路徑
        branch: 分支名稱

    Returns:
        int: exit code（0 成功，1 失敗）
    """
    success, result_msg = _cleanup_execute(path, branch, unlock)
    print(result_msg)
    return 0 if success else 1


def _cleanup_verify_all_gates(
    path: str,
    branch: str,
    force: bool
) -> int:
    """
    執行三閘門驗證

    返回 0 表示全部通過（可進行清理），1 表示被阻擋。

    W16 修復：認知負擔指數 = 10 (<= 10)

    Args:
        path: worktree 絕對路徑
        branch: 分支名稱
        force: 是否略過 Level 2/3 警告

    Returns:
        int: 0 表示通過，1 表示阻擋
    """
    # Level 1: 未 commit 檢查（永不可繞過）
    passed, uncommitted_count = _cleanup_check_level1(path)
    if not passed:
        print(CleanupMessages.LEVEL1_REJECTED.format(count=uncommitted_count))
        return 1

    print(f"  Level 1 檢查：通過（無未 commit 變更）")

    # M2 修復：拆分 Level 2/3 驗證邏輯
    passed, exit_code = _cleanup_check_level2_and_3(branch, force)
    if exit_code != 0:
        return exit_code

    print()
    return 0


def _cleanup_single(
    worktree: dict,
    ticket_id: str,
    force: bool,
    unlock: bool = False
) -> int:
    """
    清理指定 worktree（精確模式核心邏輯）

    依序執行三閘門安全檢查，通過後執行 git worktree remove + git branch -d。

    W16 修復：認知負擔指數 = 8 (<= 10)
    拆分出：_cleanup_verify_all_gates(指數 10), _cleanup_execute_and_report(指數 6),
    _cleanup_print_initial_header(指數 2)

    Args:
        worktree: worktree 資訊字典（含 path, branch 等欄位）
        ticket_id: Ticket ID（用於錯誤訊息）
        force: 是否略過 Level 2/3 警告閘門

    Returns:
        int: exit code（0 成功，1 被閘門阻擋或執行失敗）
    """
    path = worktree.get("path", "")
    branch = worktree.get("branch", f"feat/{ticket_id}")

    _cleanup_print_initial_header(ticket_id)

    # 執行三閘門驗證
    if _cleanup_verify_all_gates(path, branch, force) != 0:
        return 1

    # 執行清理
    return _cleanup_execute_and_report(path, branch, unlock)


def _cleanup_filter_feature_worktrees(worktrees: list[dict]) -> list[dict]:
    """
    篩選非保護分支的 worktree

    Args:
        worktrees: 完整 worktree 列表

    Returns:
        list[dict]: 只含 feature worktree 的列表
    """
    feature_worktrees = []
    for wt in worktrees:
        branch = wt.get("branch", "")
        # H2 修復：改用 is_protected_branch() 函式，消除定義不同步
        is_protected = is_protected_branch(branch) if branch else False
        if not is_protected and not wt.get("detached", False):
            feature_worktrees.append(wt)
    return feature_worktrees


def _cleanup_classify_worktrees(feature_worktrees: list[dict]) -> tuple[list[str], list[tuple], list[tuple]]:
    """
    三閘門分類 feature worktree

    依序執行 Level 1-3 檢查，將 worktree 分類為三組：
    - safe_to_clean: 已合併、乾淨
    - warnings: 未 push 或未合併
    - unsafe: 有未 commit 變更

    Args:
        feature_worktrees: feature worktree 列表

    Returns:
        tuple[list, list, list]: (safe_to_clean, warnings, unsafe)
    """
    safe_to_clean = []
    warnings = []
    unsafe = []

    for wt in feature_worktrees:
        path = wt.get("path", "")
        branch = wt.get("branch", "")
        ticket_id = _extract_ticket_id_from_worktree(wt)

        # Level 1 檢查
        passed_l1, uncommitted = _cleanup_check_level1(path)
        if not passed_l1:
            unsafe.append((ticket_id or branch, uncommitted))
            continue

        # Level 2 檢查
        passed_l2, _ = _cleanup_check_level2(branch)
        if not passed_l2:
            warnings.append((ticket_id or branch, branch, "未 push"))
            continue

        # Level 3 檢查
        passed_l3, _ = _cleanup_check_level3(branch)
        if not passed_l3:
            warnings.append((ticket_id or branch, branch, "未合併"))
            continue

        # 都通過
        safe_to_clean.append(ticket_id or branch)

    return safe_to_clean, warnings, unsafe


def _cleanup_target_arg(identifier: str) -> str:
    """掃描識別字轉為 cleanup 可解析的參數：ticket ID 走 positional，其餘分支名走 --branch。"""
    if is_valid_ticket_id(identifier):
        return identifier
    return f"--branch {shlex.quote(identifier)}"


def _cleanup_print_scan_report(
    safe_to_clean: list[str],
    warnings: list[tuple],
    unsafe: list[tuple]
) -> None:
    """
    格式化輸出 cleanup 掃描報告

    Args:
        safe_to_clean: 建議清理的 ticket ID 清單
        warnings: 警告清單（ticket_id, branch, reason）
        unsafe: 不安全清單（ticket_id, uncommitted_count）
    """
    print(CleanupMessages.SCAN_HEADER)
    print("━" * CLEANUP_OUTPUT_WIDTH)
    print()

    # 建議清理
    if safe_to_clean:
        print(CleanupMessages.SCAN_SAFE_TO_CLEAN)
        for ticket_id in safe_to_clean:
            print(f"  - {ticket_id}")
            print(f"    {CleanupMessages.SCAN_CLEANUP_HINT.format(target=_cleanup_target_arg(ticket_id))}")
        print()

    # 警告
    if warnings:
        print(CleanupMessages.SCAN_WARNING)
        for ticket_id, branch, reason in warnings:
            print(f"  - {ticket_id} ({branch})  [{reason}]")
            print(f"    {CleanupMessages.SCAN_FORCE_HINT.format(target=_cleanup_target_arg(ticket_id))}")
        print()

    # 不安全
    if unsafe:
        print(CleanupMessages.SCAN_UNSAFE)
        for ticket_id, uncommitted in unsafe:
            print(f"  - {ticket_id}  [{uncommitted} 個未 commit 變更]")
            print("    請先 commit 後再清理。")
        print()


def _cleanup_scan_all() -> int:
    """
    掃描所有 worktree 並分類輸出建議（掃描模式）

    逐一評估每個 worktree 的安全狀態，輸出分類報告：
    - 建議清理（已合併、乾淨）
    - 警告（未 push 或未合併）
    - 不安全（有未 commit 變更）

    Returns:
        int: exit code（永遠返回 0，僅輸出資訊）
    """
    worktrees = get_worktree_list()

    # 篩選非主倉庫的 worktree
    feature_worktrees = _cleanup_filter_feature_worktrees(worktrees)

    if not feature_worktrees:
        print(CleanupMessages.SCAN_NO_CLEANUP_NEEDED)
        return 0

    # 分類 worktree
    safe_to_clean, warnings, unsafe = _cleanup_classify_worktrees(feature_worktrees)

    # 輸出報告
    _cleanup_print_scan_report(safe_to_clean, warnings, unsafe)

    return 0


def _cleanup_find_by_branch(branch: str) -> Optional[dict]:
    """以分支名查詢 worktree；找不到輸出訊息並回傳 None。"""
    for wt in get_worktree_list():
        if wt.get("branch") == branch:
            return wt
    print(f"[阻擋] 找不到分支 {branch} 的 worktree")
    return None


def cmd_cleanup(
    ticket_id: Optional[str] = None, force: bool = False, branch: Optional[str] = None,
    unlock: bool = False,
) -> int:
    """
    cleanup 子命令 — 三閘門安全清理 worktree

    無參數時執行掃描模式，列出可清理和需注意的 worktree。
    有 ticket_id 時執行精確模式，清理指定 worktree。
    --force 略過 Level 2 和 Level 3 警告（但 Level 1 永不可繞過）。

    Args:
        ticket_id: 可選，指定清理特定 Ticket 的 worktree
        force: 若 True，略過警告閘門直接執行

    Returns:
        int: exit code（0 成功/掃描完成，1 失敗/被阻擋）
    """
    # --branch：用於萃取不到 ticket ID 的 worktree-agent-<id>，同樣經三閘門
    if branch:
        worktree = _cleanup_find_by_branch(branch)
        if worktree is None:
            return 1
        return _cleanup_single(worktree, branch, force, unlock)

    # 無參數：掃描模式
    if ticket_id is None:
        return _cleanup_scan_all()

    # 有參數：精確模式

    # Step 1-2: 驗證 Ticket ID 格式並查詢 worktree（共用函式）
    worktree = _validate_and_find_worktree(ticket_id)
    if worktree is None:
        return 1

    # Step 3: 執行清理
    return _cleanup_single(worktree, ticket_id, force, unlock)
