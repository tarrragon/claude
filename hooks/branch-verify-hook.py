#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Branch Verify Hook - PreToolUse Hook 用於編輯前檢查分支

在 Edit 或 Write 工具執行前檢查當前分支是否為保護分支。
如果是保護分支，會拒絕（deny）操作並提示用戶切換到 feature 分支。

Hook Event: PreToolUse
Matcher: Edit, Write
Decision: 不輸出（放行，交回平台權限流程） | "deny" (保護分支)

重構紀錄 (v0.28.0):
- 使用 .claude/lib/git_utils 共用模組
- 使用 .claude/lib/hook_io 共用模組
- 消除重複程式碼

重構紀錄:
- 遷移至統一日誌系統 (hook_utils)

修改紀錄:
- 將保護分支決策從 "ask" 改為 "deny"（預防 Edit 操作在保護分支上執行）
- 優化 block 訊息，包含詳細的分支切換指引
- 移除未使用的 worktree_info 變數
- 新增路徑豁免邏輯（.claude/, docs/, CLAUDE.md, README.md 在保護分支上允許編輯）
- 新增 is_exempt_path_on_protected_branch() 函式
- 在保護分支上，豁免路徑不阻止編輯
- 強化 worktree 環境支援：當檔案路徑無法推導 cwd 時，嘗試從 CLAUDE_PROJECT_DIR 推導
- 在 feat/* 分支上，所有路徑檢查均跳過（明確 early return）
- deny 訊息移除「手動 git checkout -b」二擇一，改為代理人/PM 角色分流
  並路由至 parallel-dispatch.md〈派發位置判準（強制）〉；跨專案訊息改為
  git -C <repo> worktree add。實證：二擇一措辭使代理人在共用主工作樹切分支，
  實作 commit 落到 feat 分支（下游 consumer 專案實測）。判定邏輯不變。
"""

import os
import sys
from pathlib import Path
from typing import Optional

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.git_utils import (
    get_current_branch,
    get_project_root,
    get_target_root,
    is_protected_branch,
    is_allowed_branch,
    generate_worktree_info,
    find_target_repo,
    GENERIC_EXEMPT_EXACT,
)
from lib.hook_io import (
    read_hook_input,
    write_hook_output,
    create_pretooluse_output,
)
from lib import setup_hook_logging, run_hook_safely
from lib.checkout_identity import common_dir, is_absolute_path, owning_checkout_root, strip_root_prefix

# 受檢的檔案寫入工具（settings.json 對三者各有 matcher 註冊）
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")


def _resolve_host_root(file_path: str, payload: dict) -> str:
    """host 比對與相對化的作用根。

    目標檔所屬 checkout 與原根（get_project_root）同屬一個 repo（common dir 相同，
    含 linked worktree）時，以目標檔所屬 checkout 為根；目標在他 repo 時維持原根，
    跨專案判定不變。目標不在 checkout 內時退回 get_action_root(payload)；
    payload 缺 cwd 時沿用原根（不新增 stderr）。
    """
    original = get_project_root()
    target_root = get_target_root(file_path, payload, original)
    if target_root is None:
        return str(original)
    target_common = common_dir(str(target_root))
    if target_common is not None and target_common == common_dir(str(original)):
        return str(target_root)
    if is_absolute_path(file_path) and owning_checkout_root(file_path) is not None:
        return str(original)  # 目標在他 repo：維持原根
    return str(target_root)


def _resolve_cwd_for_branch_detection(file_path: str) -> "str | None":
    """
    從檔案路徑推導用於分支偵測的工作目錄

    優先使用檔案所在目錄（支援 worktree 環境）。
    如果檔案路徑非絕對路徑，fallback 到 CLAUDE_PROJECT_DIR。

    Args:
        file_path: 被編輯的檔案路徑

    Returns:
        str | None: 用於 git 命令的工作目錄，None 表示使用預設 cwd
    """
    if is_absolute_path(file_path):
        # 如果父目錄存在，使用它；否則向上尋找存在的目錄（到達根即停）
        check_dir = Path(file_path).parent
        while not check_dir.exists() and check_dir.parent != check_dir:
            check_dir = check_dir.parent
        if check_dir.exists() and check_dir.parent != check_dir:
            return str(check_dir)

    # Fallback: 使用 CLAUDE_PROJECT_DIR（可能是 worktree 路徑）
    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if project_dir and Path(project_dir).exists():
        return project_dir

    return None


def _is_same_repo(target_repo: Optional[str], host_root: str) -> bool:
    """判斷 target_repo 是否與 host project 相同。"""
    if not target_repo:
        return True  # 無法判斷時視為同 repo（保守，套用本專案豁免）
    return os.path.realpath(target_repo) == os.path.realpath(host_root)


def _strip_root(path: str, root: str) -> "str | None":
    """
    path 位於 root 之下時回傳相對路徑，否則回傳 None。

    委派 checkout_identity.strip_root_prefix：分隔符統一、磁碟機代號大小寫折疊，
    並要求 root 之後為字串結尾或 "/"（同字首兄弟目錄如 proj-wt 不算在 proj 之下）。
    """
    return strip_root_prefix(path, root)


def is_exempt_path_on_protected_branch(
    file_path: str,
    cwd: "str | None" = None,
    target_repo: "str | None" = None,
    host_root: "str | None" = None,
) -> bool:
    """
    判斷此路徑是否在保護分支上被豁免（允許編輯）

    區分 same-repo（本專案豁免清單）vs cross-repo（通用豁免清單）

    Args:
        file_path: 要編輯的檔案路徑
        cwd: 用於 host project 偵測的 cwd
        target_repo: 目標檔案所屬的 repo 根目錄（從 find_target_repo 取得）
        host_root: 已解析的 host project 根目錄；批次呼叫端（一次判斷多個檔案）
            預先解析後傳入，避免每個檔案各付一個 git 子程序。未提供時由 cwd 解析。

    Returns:
        bool: True 表示豁免（允許編輯），False 表示不豁免
    """
    # get_project_root 回傳 Path（SSOT），本函式後續以 str 操作（startswith/len），故轉 str
    if host_root is None:
        host_root = str(get_project_root(cwd=cwd))
    same_repo = _is_same_repo(target_repo, host_root)

    # Windows：統一路徑分隔符，否則後續 startswith / lstrip("/") 前綴比對全數失效（#132）
    file_path = file_path.replace("\\", "/")
    host_root = host_root.replace("\\", "/")
    if target_repo:
        target_repo = target_repo.replace("\\", "/")
    is_absolute = is_absolute_path(file_path)

    if not same_repo:
        # 跨專案：使用通用豁免清單（不套用 .claude/、docs/ 等本專案約定）
        # 計算相對於目標 repo 的路徑
        relative = _strip_root(file_path, target_repo) if target_repo else None
        if relative is not None:
            normalized = relative
        else:
            normalized = file_path.lstrip("/") if file_path.startswith("/") else file_path
        return normalized in GENERIC_EXEMPT_EXACT

    # Same repo：使用本專案豁免清單
    exempt_prefixes = [
        ".claude/",
        "docs/",
        "scripts/experiments/",  # 實驗一次性腳本（對應 docs/experiments/ 報告）
    ]
    exempt_exact = [
        "CLAUDE.md",
        "README.md",
        "CHANGELOG.md",
        "package.json",
        "manifest.json",
        ".gitignore",  # repo 層級忽略清單
        ".gitattributes",  # repo 層級檔案屬性
    ]

    relative = _strip_root(file_path, host_root)

    # 非專案檔案（不在 host_root 內）一律豁免（保留原行為；Windows 磁碟機路徑同為絕對路徑）
    if is_absolute and relative is None:
        return True

    normalized = relative if relative is not None else file_path.lstrip("/")

    for prefix in exempt_prefixes:
        if normalized.startswith(prefix):
            return True
    # 任意層級 README.md：與 pm-role 可寫路徑、lib/path_permission 白名單一致
    if normalized.rsplit("/", 1)[-1] == "README.md":
        return True
    return normalized in exempt_exact


def build_cross_repo_deny_message(
    file_path: str,
    target_repo: str,
    target_branch: str,
    suggested_branch: str = "feat/cross-repo-edit",
) -> str:
    """跨專案保護分支 deny 訊息，附目標 repo 切換指令。"""
    return f"""保護分支編輯被阻止（跨專案）

目標檔案位於外部 repo，且該 repo 當前在保護分支：
- 檔案路徑：{file_path}
- 目標 repo：{target_repo}
- 目標 branch：{target_branch}

跨專案豁免清單僅含通用文件（README.md / CHANGELOG.md / .gitignore / .gitattributes），
此檔案不在豁免清單內，需在獨立工作樹的 feature 分支上編輯。
目標 repo 的主工作樹可能被其他 session 共用，禁止在其中切換或建立分支。

在目標 repo 另建工作樹（在另一個 terminal 執行）：

  git -C {target_repo} worktree add <路徑> -b {suggested_branch}

於新工作樹內完成編輯後重試。
派發位置判準見 .claude/pm-rules/parallel-dispatch.md〈派發位置判準（強制）〉。"""


def main() -> int:
    logger = setup_hook_logging("branch-verify")

    # 讀取輸入
    input_data = read_hook_input()
    # 放行路徑一律不輸出 decision：allow 會略過平台的權限提示，等於代用戶核可；
    # 本 hook 只負責擋保護分支上的編輯，放行時交回平台權限流程。
    # 執行期例外仍由 run_hook_safely(fail_closed=True) 處理為阻擋，不受影響。
    if not input_data:
        logger.debug("無法解析輸入，不輸出決策（交回平台權限流程）")
        return 0

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    # 只檢查檔案寫入工具；NotebookEdit 的路徑欄位是 notebook_path
    if tool_name not in WRITE_TOOLS:
        logger.debug(f"工具 {tool_name} 不需要分支檢查")
        return 0

    # 從被編輯檔案路徑推導 git repo context（支援 worktree 環境）
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    file_dir = _resolve_cwd_for_branch_detection(file_path)

    # 獲取當前分支
    current_branch = get_current_branch(cwd=file_dir)
    if not current_branch:
        logger.warning("無法獲取分支資訊，不輸出決策（交回平台權限流程）")
        return 0

    # 檢查是否為允許的分支（feat/*, fix/* 等）
    # 在開發分支上，所有路徑均允許編輯，不需要進一步檢查
    if is_allowed_branch(current_branch):
        logger.info(f"當前在 feature 分支 '{current_branch}' 上，允許編輯")
        return 0

    # 檢查是否為保護分支
    if is_protected_branch(current_branch):
        file_path = file_path or "unknown"

        # 偵測目標 repo，判斷是否跨專案
        target_repo = find_target_repo(file_path) if is_absolute_path(file_path) else None
        host_root = _resolve_host_root(file_path, input_data)
        is_cross_repo = (
            target_repo is not None
            and os.path.realpath(target_repo) != os.path.realpath(host_root)
        )

        # 檢查是否為豁免路徑（在保護分支上允許編輯）
        if is_exempt_path_on_protected_branch(
            file_path, cwd=file_dir, target_repo=target_repo, host_root=host_root
        ):
            logger.info(f"在保護分支 '{current_branch}' 上編輯豁免路徑 {file_path}，允許")
            return 0

        logger.info(f"在保護分支 '{current_branch}' 上嘗試編輯非豁免檔案 {file_path}，操作已阻止 (cross_repo={is_cross_repo})")

        if is_cross_repo:
            # 跨專案保護分支：附目標 repo 切換指令
            deny_message = build_cross_repo_deny_message(
                file_path=file_path,
                target_repo=target_repo,
                target_branch=current_branch,
            )
            output = create_pretooluse_output("deny", deny_message)
            write_hook_output(output)
            return 0

        # 同 repo 路徑判斷
        project_root = host_root
        is_project_file = (
            _strip_root(file_path, str(project_root)) is not None
            if is_absolute_path(file_path) else True
        )

        if is_project_file:
            # 專案內的檔案
            deny_message = f"""保護分支編輯被阻止

對不起，當前在保護分支 '{current_branch}' 上，無法直接編輯檔案：
{file_path}

保護分支用於穩定開發，需要在獨立分支上進行更改。

共用主工作樹禁止切換或建立分支，請依角色處理：

- 代理人：停手，於 ticket NeedsContext 記錄「在 main 被 branch-verify-hook 擋下」，
  交還 PM 以 isolation:worktree 重派；禁止自行建立或切換分支。
- PM：/worktree create <ticket-id>

豁免路徑（允許在保護分支上編輯）：
- .claude/ （規則、配置、Hook、方法論）
- docs/ （工作日誌、Ticket 檔案）
- CLAUDE.md、README.md、CHANGELOG.md

派發位置判準見 .claude/pm-rules/parallel-dispatch.md〈派發位置判準（強制）〉。"""
        else:
            # 非專案檔案（應該不會發生，但保留說明）
            deny_message = f"""保護分支編輯被阻止

對不起，當前在保護分支 '{current_branch}' 上，無法編輯檔案：
{file_path}

此操作可能涉及系統檔案或外部 auto-memory 的特殊處理。
請切換到 feature 分支後重試。"""

        output = create_pretooluse_output("deny", deny_message)
        write_hook_output(output)
        return 0

    # 其他分支，允許編輯
    logger.info(f"當前在分支 '{current_branch}' 上，允許編輯")
    return 0


if __name__ == "__main__":
    # fail_closed=True：本守衛防的是保護分支上直接開發，fail-open 代價為
    # 變更已落在錯誤分支後需額外搬移成本（不可逆），執行期異常時應保守
    # DENY（exit 2）而非放行（見 lib.hook_logging.run_hook_safely）。
    exit_code = run_hook_safely(main, "branch-verify", fail_closed=True)
    sys.exit(exit_code)
