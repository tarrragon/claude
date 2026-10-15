#!/usr/bin/env python3
"""
Worktree Manager - /worktree SKILL 的核心邏輯

提供 create 和 status 子命令，支援從 Ticket ID 自動推導分支名和 worktree 路徑。

主要功能:
- cmd_create: 建立新 worktree
- cmd_status: 查看 worktree 狀態
- 輔助函式：Ticket ID 驗證、推導、反推等
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, ContextManager
import contextlib

try:
    from .constants import (
        FEAT_PREFIX,
        FEAT_PREFIX_LEN,
        TICKET_ID_PATTERN,
        WORKTREE_STATUS_OUTPUT_WIDTH,
        DEFAULT_BASE_BRANCH,
        TICKET_QUERY_TIMEOUT,
        TICKET_COMPLETED_STATUS,
        CLEANUP_OUTPUT_WIDTH,
        BRANCH_FORCE_DELETE_FLAG,
        MACOS_XCCONFIG_TEMPLATES,
    )
    from .messages import MergeMessages, CleanupMessages, CommonMessages, CreateMessages
    from .merge_gate import (
        GATE_MAX_RETRIES, GATE_ABORTED, GATE_REFUSED, GATE_WRITTEN, MergeGate, SlotWaitRefused, SuiteRunner,
        emit_gate_line, gate_line, gate_result_label,
    )
except ImportError:
    # Fallback when running with scripts/ on sys.path (test 與直接執行情境)
    from constants import (
        FEAT_PREFIX,
        FEAT_PREFIX_LEN,
        TICKET_ID_PATTERN,
        WORKTREE_STATUS_OUTPUT_WIDTH,
        DEFAULT_BASE_BRANCH,
        TICKET_QUERY_TIMEOUT,
        TICKET_COMPLETED_STATUS,
        CLEANUP_OUTPUT_WIDTH,
        BRANCH_FORCE_DELETE_FLAG,
        MACOS_XCCONFIG_TEMPLATES,
    )
    from messages import MergeMessages, CleanupMessages, CommonMessages, CreateMessages
    from merge_gate import (
        GATE_MAX_RETRIES, GATE_ABORTED, GATE_REFUSED, GATE_WRITTEN, MergeGate, SlotWaitRefused, SuiteRunner,
        emit_gate_line, gate_line, gate_result_label,
    )

# 動態定位專案根目錄（W1-118 修復：方案 D 雙策略 fallback）
#
# 背景：worktree skill 安裝為 uv tool 後，__file__ 位於 uv tool venv，
#       原本的 `Path(__file__).parent * 5` 推導會指向 uv tool root 而非專案根目錄，
#       導致 git_utils 找不到、所有 git 操作失敗、誤判「基礎分支不存在 main」。
#
# 策略：
#   1. 優先讀 CLAUDE_PROJECT_DIR 環境變數（Claude Code 慣例）
#   2. Fallback：subprocess git rev-parse --show-toplevel 從 cwd 上溯
#   3. 雙雙失敗才報錯（保留明確錯誤訊息）
def _resolve_project_root() -> Path:
    """雙策略定位專案根目錄。

    Returns:
        Path: 專案根目錄絕對路徑

    Raises:
        RuntimeError: 環境變數未設且 git rev-parse 失敗
    """
    # 策略 1：CLAUDE_PROJECT_DIR 環境變數
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        candidate = Path(env_root).resolve()
        if candidate.exists():
            return candidate

    # 策略 2：git rev-parse --show-toplevel 從 cwd 上溯
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            timeout=5,
        )
        if result.returncode == 0:
            toplevel = result.stdout.strip()
            if toplevel:
                return Path(toplevel).resolve()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[Warning] git rev-parse --show-toplevel 失敗: {e}", file=sys.stderr)

    raise RuntimeError(
        "無法定位專案根目錄。請設定環境變數 CLAUDE_PROJECT_DIR，"
        "或在 git 工作目錄中執行 worktree 命令。"
    )


try:
    project_root = _resolve_project_root()
    sys.path.insert(0, str(project_root / ".claude"))
except RuntimeError as e:
    print(f"[Warning] {e}", file=sys.stderr)
    print("[Warning] Worktree SKILL may not function properly", file=sys.stderr)
    project_root = Path(os.getcwd())  # 保底，後續 git_utils import 也會 fallback

try:
    from lib.git_utils import (
        run_git_command,
        get_project_root,
        get_current_branch,
        get_worktree_list,
        is_protected_branch,
        is_allowed_branch,
    )
except ImportError as e:
    # #4 修復：ImportError 應寫入 stderr 和日誌，但不中斷程式
    # 改為優雅降級：寫 stderr 提示，但允許程式繼續執行
    import sys
    print(f"[Warning] Failed to import git_utils: {e}", file=sys.stderr)
    print(f"[Warning] Worktree SKILL may not function properly", file=sys.stderr)

    # Fallback 模式下的保護分支和允許模式定義
    _fallback_protected_branches = ["main", "master", "develop", "release"]
    _fallback_allowed_patterns = ["feat/", "feature/", "fix/", "hotfix/", "bugfix/", "chore/", "docs/", "refactor/", "test/"]

    # 定義 fallback 函式，但在呼叫時輸出警告並返回安全預設值
    def run_git_command(args: list[str], cwd: Optional[str] = None, timeout: int = 10) -> tuple[bool, str]:
        """Fallback: 執行 git 命令（降級模式）"""
        return False, "git_utils unavailable"

    def get_project_root() -> str:
        """Fallback: 獲取專案根目錄（降級模式）"""
        return os.getcwd()

    def get_current_branch() -> Optional[str]:
        """Fallback: 獲取當前分支（降級模式）"""
        return None

    def get_worktree_list() -> list[dict]:
        """Fallback: 獲取 worktree 列表（降級模式）"""
        return []

    def is_protected_branch(branch: str) -> bool:
        """Fallback: 檢查保護分支（降級模式）"""
        return branch in _fallback_protected_branches

    def is_allowed_branch(branch: str) -> bool:
        """Fallback: 檢查允許編輯分支（降級模式）"""
        return any(branch.startswith(p) for p in _fallback_allowed_patterns)


# ===== 核心函式 =====


def is_valid_ticket_id(ticket_id: str) -> bool:
    """
    驗證 Ticket ID 格式是否合法

    Args:
        ticket_id: Ticket ID 字串

    Returns:
        bool: 格式合法返回 True，否則 False

    Example:
        is_valid_ticket_id("0.1.1-W9-002.1")  # True
        is_valid_ticket_id("my-feature")      # False
    """
    return bool(re.match(TICKET_ID_PATTERN, ticket_id))




def derive_branch_name(ticket_id: str) -> str:
    """
    從 Ticket ID 推導分支名稱

    Args:
        ticket_id: 合法格式的 Ticket ID

    Returns:
        str: 分支名稱 (feat/{ticket_id})

    Example:
        derive_branch_name("0.1.1-W9-002.1")  # "feat/0.1.1-W9-002.1"
    """
    return f"feat/{ticket_id}"


def derive_worktree_path(ticket_id: str) -> str:
    """
    從 Ticket ID 推導 worktree 絕對路徑

    Args:
        ticket_id: 合法格式的 Ticket ID

    Returns:
        str: worktree 絕對路徑

    Example:
        derive_worktree_path("0.1.1-W9-002.1")
        # "{worktree 父目錄}/ccsession-0.1.1-W9-002.1"
    """
    project_root = get_project_root()
    project_name = os.path.basename(project_root)
    parent_dir = os.path.dirname(project_root)
    return os.path.join(parent_dir, f"{project_name}-{ticket_id}")


def check_branch_exists(branch: str) -> bool:
    """
    檢查分支是否存在

    Args:
        branch: 分支名稱

    Returns:
        bool: 分支存在返回 True
    """
    success, _ = run_git_command(["rev-parse", "--verify", branch])
    return success


def extract_ticket_id_from_branch(branch: str) -> Optional[str]:
    """
    從分支名稱反推 Ticket ID

    Args:
        branch: 分支名稱（如 "feat/0.1.1-W9-002.1"）

    Returns:
        str | None: Ticket ID，或 None 如果無法辨識

    Example:
        extract_ticket_id_from_branch("feat/0.1.1-W9-002.1")  # "0.1.1-W9-002.1"
        extract_ticket_id_from_branch("main")                  # None
    """
    if not branch.startswith(FEAT_PREFIX):
        return None

    # #10 修復：使用常數 FEAT_PREFIX_LEN 而非魔法數字 5
    potential_ticket_id = branch[FEAT_PREFIX_LEN:]

    if is_valid_ticket_id(potential_ticket_id):
        return potential_ticket_id

    return None


def get_worktree_ahead_behind(branch: str, base: str = DEFAULT_BASE_BRANCH) -> tuple[int, int]:
    """
    計算分支相對於 base 的 ahead/behind commit 數

    Args:
        branch: 分支名稱（短名稱，如 "feat/0.1.1-W9-002.1"）
        base: 基礎分支，預設為 DEFAULT_BASE_BRANCH

    Returns:
        tuple[int, int]: (ahead, behind)
            - ahead: branch 比 base 多幾個 commit
            - behind: base 比 branch 多幾個 commit

    Example:
        ahead, behind = get_worktree_ahead_behind("feat/0.1.1-W9-002.1", "main")
        # 如果 branch 領先 3 commit，落後 0 commit：(3, 0)
    """
    try:
        # 計算 branch 超前 base 的 commit 數
        ahead_result = run_git_command(["rev-list", "--count", f"{base}..{branch}"])
        ahead = int(ahead_result[1]) if ahead_result[0] else 0

        # 計算 branch 落後 base 的 commit 數
        behind_result = run_git_command(["rev-list", "--count", f"{branch}..{base}"])
        behind = int(behind_result[1]) if behind_result[0] else 0

        return (ahead, behind)
    except Exception as e:
        # H3 修復：加入 stderr 輸出符合 quality-baseline 規則 4 雙通道要求
        # 原因：ahead/behind 計算失敗時仍降級返回 (0, 0) 是合理的（保守行為）
        print(f"[Warning] Failed to calculate ahead/behind for {branch}: {e}", file=sys.stderr)
        return (0, 0)


def get_worktree_uncommitted_count(worktree_path: str) -> int:
    """
    計算 worktree 中未 commit 的變更數

    Args:
        worktree_path: worktree 絕對路徑

    Returns:
        int: 未 commit 變更的行數

    Example:
        count = get_worktree_uncommitted_count("/path/to/ccsession-0.1.1-W9-002.1")
    """
    try:
        success, output = run_git_command(
            ["status", "--porcelain"],
            cwd=worktree_path
        )
        if not success:
            return 0

        lines = output.strip().split('\n') if output.strip() else []
        return len([line for line in lines if line])
    except Exception as e:
        # H3 修復：加入 stderr 輸出符合 quality-baseline 規則 4 雙通道要求
        # 原因：未 commit 計數失敗時仍降級返回 0 是合理的（保守行為，不影響流程）
        print(f"[Warning] Failed to count uncommitted changes in {worktree_path}: {e}", file=sys.stderr)
        return 0


# ===== 子命令函式 =====


def _cmd_create_dry_run(ticket_id: str, branch_name: str, worktree_path: str, base: str) -> int:
    """
    create 子命令的 dry-run 模式（#13 修復：從 cmd_create 拆分出來）

    Args:
        ticket_id: Ticket ID
        branch_name: 推導的分支名
        worktree_path: 推導的 worktree 路徑
        base: 基礎分支

    Returns:
        int: exit code (0)
    """
    git_cmd = ["worktree", "add", "-b", branch_name, worktree_path, base]
    print("[Dry Run] 將要執行的操作：")
    print()
    print(f"  git {' '.join(git_cmd)}")
    print()
    print("實際執行請移除 --dry-run 參數。")
    return 0


def _cmd_create_validate_preconditions(
    base: str,
    branch_name: str,
    worktree_path: str
) -> tuple[bool, str]:
    """
    驗證 create 前置條件（M1 修復：從 _cmd_create_validate_and_execute 拆分）

    Args:
        base: 基礎分支
        branch_name: 推導的分支名
        worktree_path: 推導的 worktree 路徑

    Returns:
        tuple[bool, str]: (驗證通過, 錯誤訊息或空字串)
    """
    # 驗證基礎分支存在
    if not check_branch_exists(base):
        return False, f"[錯誤] 基礎分支不存在：{base}\n\n請確認分支名稱，或省略 --base 參數使用預設的 {DEFAULT_BASE_BRANCH}"

    # 檢查分支已存在
    if check_branch_exists(branch_name):
        return False, f"[錯誤] 分支已存在：{branch_name}\n\n如需重新建立，請先刪除分支：\n  git branch -d {branch_name}"

    # 檢查 worktree 路徑已存在
    if os.path.exists(worktree_path):
        return False, f"[錯誤] 目錄已存在：{worktree_path}\n\n如需重新建立，請先移除目錄或使用其他 ticket-id"

    return True, ""


def _cmd_create_print_success(
    ticket_id: str,
    branch_name: str,
    base: str,
    worktree_path: str
) -> None:
    """
    輸出 worktree 建立成功訊息（M1 修復：從 _cmd_create_validate_and_execute 拆分）

    Args:
        ticket_id: Ticket ID
        branch_name: 推導的分支名
        base: 基礎分支
        worktree_path: 推導的 worktree 路徑
    """
    print("正在建立 worktree...")
    print(f"  Ticket: {ticket_id}")
    print(f"  分支:   {branch_name}")
    print(f"  基礎:   {base}")
    print(f"  路徑:   {worktree_path}")
    print()
    print("建立成功。")
    print()
    print("下一步：")
    print(f"  cd {worktree_path}")


def _extract_version_from_ticket_id(ticket_id: str) -> Optional[str]:
    """
    從 Ticket ID 提取版本號

    Args:
        ticket_id: Ticket ID（如 "0.16.2-W5-001.3"）

    Returns:
        str | None: 版本號（如 "0.16.2"），或 None
    """
    match = re.match(r"^(\d+\.\d+\.\d+)-W", ticket_id)
    if match:
        return match.group(1)
    return None


def _find_ticket_file(ticket_id: str) -> Optional[str]:
    """
    根據 Ticket ID 找到對應的 Ticket 檔案路徑

    Ticket 檔案位於 docs/work-logs/v{version}/tickets/{ticket-id}.md

    Args:
        ticket_id: Ticket ID

    Returns:
        str | None: 檔案絕對路徑，或 None 表示找不到
    """
    version = _extract_version_from_ticket_id(ticket_id)
    if version is None:
        return None

    ticket_path = os.path.join(
        project_root,
        "docs", "work-logs", f"v{version}", "tickets", f"{ticket_id}.md"
    )

    if os.path.exists(ticket_path):
        return ticket_path
    return None


def _parse_ticket_blocked_by(ticket_id: str) -> list[str]:
    """
    解析 Ticket 檔案的 blockedBy 欄位

    讀取 Ticket Markdown 的 YAML frontmatter，提取 blockedBy 列表。

    Args:
        ticket_id: Ticket ID

    Returns:
        list[str]: blockedBy Ticket ID 列表（可為空）
    """
    ticket_path = _find_ticket_file(ticket_id)
    if ticket_path is None:
        return []

    try:
        with open(ticket_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 解析 YAML frontmatter（--- 區塊）
        if not content.startswith("---"):
            return []

        end_index = content.index("---", 3)
        frontmatter = content[3:end_index].strip()

        # 簡易 YAML 解析：找 blockedBy 欄位
        blocked_by = []
        in_blocked_by = False
        for line in frontmatter.split("\n"):
            if line.startswith("blockedBy:"):
                # 檢查行內列表格式：blockedBy: [a, b]
                value = line[len("blockedBy:"):].strip()
                if value.startswith("["):
                    # 行內列表
                    inner = value.strip("[]").strip()
                    if inner:
                        blocked_by = [item.strip().strip("'\"") for item in inner.split(",")]
                    return blocked_by
                # 若值為空，後續行可能是 YAML 列表項
                in_blocked_by = True
                continue

            if in_blocked_by:
                if line.startswith("- "):
                    blocked_by.append(line[2:].strip())
                else:
                    # 遇到其他欄位，結束 blockedBy 解析
                    break

        return blocked_by
    except Exception as e:
        print(CreateMessages.TICKET_FILE_PARSE_ERROR.format(error=str(e)), file=sys.stderr)
        return []


def _merge_main_baseline(worktree_path: str, base: str) -> bool:
    """worktree 建立後確定性同步 main（issue #77 決議 A：治本）。

    共享 .git 下 local main 為全機單一事實來源；`git worktree add` 的 base
    解析與 worktree 實際可用之間存在時間差——其他 worktree 在此視窗內對
    main 的併行 commit 不會反映在新 worktree 的分支起點。明確在新 worktree
    內執行一次 `git merge main`，消除此視窗（無新變更時為 no-op fast-forward，
    不影響正常流程）。合併目標固定為 main（非 create 的 `--base` 參數）——
    即使以其他分支為 base 建立 worktree，仍應與 main 這個 SSOT 同步。

    衝突時明確停下並輸出後果與下一步，不自動解（不執行 `git merge --abort`
    或自動選邊）——worktree 已存在於磁碟，僅標記為需要人工介入。main 分支
    不存在時視為無可合併對象，靜默略過（比照 `_merge_blocked_by_branches`
    對不存在分支的降級處理）；`base == main` 時該存在性已於
    `_cmd_create_validate_preconditions` 驗證過，不重複檢查。

    Args:
        worktree_path: 新建 worktree 的路徑（合併於此目錄下執行）
        base: create 子命令實際使用的 base 分支（用於判斷是否需重新檢查
            main 存在性；main 本身固定為合併目標，不受此參數影響）

    Returns:
        bool: True 表示已同步（成功合併、無新變更、或 main 不存在無需同步）；
            False 表示衝突或合併失敗，訊息已輸出，呼叫端應中止後續流程
            （不疊加 blockedBy 合併，避免在已衝突的 working tree 上繼續操作）。
    """
    if base != DEFAULT_BASE_BRANCH and not check_branch_exists(DEFAULT_BASE_BRANCH):
        return True

    print(CreateMessages.MAIN_MERGE_HEADER.format(base=DEFAULT_BASE_BRANCH))
    success, output = run_git_command(
        ["merge", DEFAULT_BASE_BRANCH, "--no-edit"], cwd=worktree_path
    )
    if success:
        if "up to date" in output.lower() or not output.strip():
            print(CreateMessages.MAIN_MERGE_UP_TO_DATE.format(base=DEFAULT_BASE_BRANCH))
        else:
            print(CreateMessages.MAIN_MERGE_SUCCESS.format(base=DEFAULT_BASE_BRANCH))
        return True

    if "conflict" in output.lower():
        print(CreateMessages.MAIN_MERGE_CONFLICT.format(
            base=DEFAULT_BASE_BRANCH, worktree_path=worktree_path, output=output
        ))
        return False

    print(CreateMessages.MAIN_MERGE_FAILED.format(
        base=DEFAULT_BASE_BRANCH, error=output, worktree_path=worktree_path
    ))
    return False


def _sync_macos_xcconfig(worktree_path: str) -> None:
    """補齊 gitignored 的 macOS xcconfig 建置檔案。

    macos/Flutter/*.xcconfig 被 .gitignore 的 /macos/ 規則排除，git worktree
    add 建立的新 worktree 不會帶有這兩個檔案，導致 flutter build macos /
    flutter test -d macos 找不到 include 檔而失敗。內容為固定的 Flutter
    樣板（僅 #include 相對路徑，無機器相依內容），故用固定內容寫入補齊。

    僅在 worktree 內確實存在 macos/Flutter/ 目錄（即本次 worktree 涵蓋
    macOS 平台）時才動作，避免對不需要 macOS 建置的 worktree 產生無意義
    輸出。已存在的檔案不覆寫，保留使用者可能的本機自訂內容。

    CocoaPods（Pods/ 目錄）刻意不在此自動執行 pod install：該操作需要
    網路且耗時，多數 worktree 不會跑 macOS build，預設路徑不應為少數
    案例支付全體成本；改為輸出提示，需要時由使用者自行執行。

    Args:
        worktree_path: 新建 worktree 的路徑
    """
    macos_flutter_dir = os.path.join(worktree_path, "macos", "Flutter")
    if not os.path.isdir(macos_flutter_dir):
        return

    written = []
    for filename, content in MACOS_XCCONFIG_TEMPLATES.items():
        target_path = os.path.join(macos_flutter_dir, filename)
        if os.path.exists(target_path):
            continue
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(filename)

    if written:
        print(CreateMessages.MACOS_XCCONFIG_SYNCED.format(files="、".join(written)))

    if not os.path.isdir(os.path.join(worktree_path, "macos", "Pods")):
        print(CreateMessages.MACOS_PODS_HINT.format(worktree_path=worktree_path))


def _merge_blocked_by_branches(ticket_id: str, worktree_path: str) -> None:
    """
    合併 blockedBy 依賴的 feat 分支到新建的 worktree

    對每個 blockedBy ticket：
    1. 檢查該 ticket 是否已完成（透過查詢 ticket 檔案的 status）
    2. 檢查對應的 feat/{ticket-id} 分支是否存在
    3. 若存在且已完成，自動執行 git merge

    Args:
        ticket_id: 當前 Ticket ID
        worktree_path: 新建 worktree 的路徑（用於在其中執行 git merge）
    """
    blocked_by_ids = _parse_ticket_blocked_by(ticket_id)
    if not blocked_by_ids:
        return

    print()
    print(CreateMessages.DEPENDENCY_SECTION_HEADER)

    for dep_id in blocked_by_ids:
        dep_branch = derive_branch_name(dep_id)

        # 檢查 feat 分支是否存在
        if not check_branch_exists(dep_branch):
            # 靜默跳過不存在的分支
            continue

        # 檢查依賴 Ticket 是否已完成（透過檔案 status 欄位）
        dep_status = _query_ticket_file_status(dep_id)
        if dep_status is not None and dep_status.lower() != TICKET_COMPLETED_STATUS:
            print(f"  {CreateMessages.DEPENDENCY_TICKET_NOT_COMPLETED.format(ticket_id=dep_id, status=dep_status)}")
            continue

        # 執行 git merge（在 worktree 目錄下）
        success, output = run_git_command(
            ["merge", dep_branch, "--no-edit"],
            cwd=worktree_path
        )

        if success:
            print(f"  {CreateMessages.DEPENDENCY_MERGED.format(branch=dep_branch)}")
        else:
            print(f"  {CreateMessages.DEPENDENCY_MERGE_FAILED.format(branch=dep_branch)}")


def _query_ticket_file_status(ticket_id: str) -> Optional[str]:
    """
    從 Ticket 檔案讀取 status 欄位

    直接解析檔案 frontmatter，不依賴 ticket CLI。

    Args:
        ticket_id: Ticket ID

    Returns:
        str | None: status 值（如 "completed"），或 None 表示無法讀取
    """
    ticket_path = _find_ticket_file(ticket_id)
    if ticket_path is None:
        return None

    try:
        with open(ticket_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.startswith("---"):
            return None

        end_index = content.index("---", 3)
        frontmatter = content[3:end_index].strip()

        for line in frontmatter.split("\n"):
            if line.startswith("status:"):
                return line[len("status:"):].strip()

        return None
    except Exception:
        return None


def _cmd_create_validate_and_execute(
    ticket_id: str,
    branch_name: str,
    worktree_path: str,
    base: str
) -> int:
    """
    create 子命令的實際執行邏輯（#13 修復：從 cmd_create 拆分出來）

    Args:
        ticket_id: Ticket ID
        branch_name: 推導的分支名
        worktree_path: 推導的 worktree 路徑
        base: 基礎分支

    Returns:
        int: exit code (0 成功，1 失敗)
    """
    # 驗證前置條件
    passed, error_msg = _cmd_create_validate_preconditions(base, branch_name, worktree_path)
    if not passed:
        print(error_msg)
        return 1

    # 構建 git 命令並執行
    git_cmd = ["worktree", "add", "-b", branch_name, worktree_path, base]
    success, output = run_git_command(git_cmd)
    if not success:
        print(f"[錯誤] 建立 worktree 失敗：{output}")
        return 1

    # 成功輸出
    _cmd_create_print_success(ticket_id, branch_name, base, worktree_path)

    # 補齊 gitignored 的 macOS 建置前置檔案（xcconfig）
    _sync_macos_xcconfig(worktree_path)

    # 確定性同步 main（issue #77 決議 A）：衝突時中止，不疊加後續合併
    if not _merge_main_baseline(worktree_path, base):
        return 1

    # 自動合併 blockedBy 依賴的 feat 分支
    _merge_blocked_by_branches(ticket_id, worktree_path)

    return 0


def cmd_create(ticket_id: str, base: str = DEFAULT_BASE_BRANCH, dry_run: bool = False) -> int:
    """
    create 子命令 - 建立新 worktree

    Args:
        ticket_id: Ticket ID
        base: 基礎分支，預設 "main"
        dry_run: 如果為 True，只顯示操作不執行

    Returns:
        int: exit code (0 成功，1 失敗)
    """
    # Step 1: 驗證 Ticket ID 格式
    if not is_valid_ticket_id(ticket_id):
        print(CommonMessages.INVALID_TICKET_ID_FORMAT.format(ticket_id=ticket_id))
        return 1

    # Step 2: 推導分支名和 worktree 路徑
    branch_name = derive_branch_name(ticket_id)
    worktree_path = derive_worktree_path(ticket_id)

    # Step 3: 區分 dry-run 和實際執行
    if dry_run:
        return _cmd_create_dry_run(ticket_id, branch_name, worktree_path, base)
    else:
        return _cmd_create_validate_and_execute(ticket_id, branch_name, worktree_path, base)


def _get_feature_branch_metrics(branch: str) -> tuple[str, int, int]:
    """
    取得 feature 分支的 Ticket ID 和 ahead/behind metrics

    W16 修復：認知負擔指數 = 8 (<= 10)

    Args:
        branch: 分支名稱

    Returns:
        tuple[str, int, int]: (ticket_label, ahead, behind)
    """
    ticket_label = extract_ticket_id_from_branch(branch) or "無法辨識"
    ahead, behind = get_worktree_ahead_behind(branch, DEFAULT_BASE_BRANCH)
    return ticket_label, ahead, behind


def _determine_ticket_label_and_metrics(
    branch: str,
    is_detached: bool,
    is_main: bool
) -> tuple[str, int, int]:
    """
    判定 ticket label 和 commit metrics (ahead/behind)

    根據 branch 類型判定 label：
    - detached HEAD: "detached"
    - 保護分支（主倉庫）: "主倉庫"
    - feature 分支: Ticket ID 或 "無法辨識"

    W16 修復：認知負擔指數 = 5 (<= 10)

    Args:
        branch: 分支名稱
        is_detached: 是否 detached HEAD
        is_main: 是否保護分支

    Returns:
        tuple[str, int, int]: (ticket_label, ahead, behind)
    """
    if is_detached:
        return "detached", 0, 0
    if is_main:
        return "主倉庫", 0, 0
    return _get_feature_branch_metrics(branch)


def _build_worktree_display_info(wt: dict) -> dict:
    """
    將單個 worktree 轉換為顯示用資訊字典

    W16 修復：認知負擔指數 = 5 (<= 10)

    Args:
        wt: worktree 資訊字典

    Returns:
        dict: 顯示用資訊字典
    """
    path = wt.get("path", "")
    branch = wt.get("branch", "")
    is_detached = wt.get("detached", False)

    # M3 修復：前置計算 uncommitted，消除三處重複呼叫
    uncommitted = get_worktree_uncommitted_count(path)

    # H2 修復：改用 is_protected_branch() 函式，消除定義不同步
    is_main = is_protected_branch(branch) if not is_detached else False

    # W16 修復：拆分狀態判定邏輯至 _determine_ticket_label_and_metrics
    ticket_label, ahead, behind = _determine_ticket_label_and_metrics(
        branch, is_detached, is_main
    )

    return {
        "label": ticket_label,
        "path": path,
        "branch": branch if not is_detached else "detached",
        "ahead": ahead,
        "behind": behind,
        "uncommitted": uncommitted,
        "is_main": is_main,
        "is_detached": is_detached
    }


def _collect_worktree_info(worktrees: list[dict]) -> list[dict]:
    """
    收集 worktree 資訊（#7 修復：從 cmd_status 拆分出來降低認知負擔）

    W16 修復：認知負擔指數 = 3 (<= 10)
    拆分出：_build_worktree_display_info(指數 5), _determine_ticket_label_and_metrics(指數 5),
    _get_feature_branch_metrics(指數 8)

    Args:
        worktrees: worktree 列表

    Returns:
        list[dict]: 包含顯示用資訊的字典列表
    """
    return [_build_worktree_display_info(wt) for wt in worktrees]


def _print_worktree_status(display_info: list[dict]) -> None:
    """
    格式化輸出 worktree 狀態（#7 修復：從 cmd_status 拆分出來）

    Args:
        display_info: 包含顯示用資訊的字典列表
    """
    print(f"Worktree 狀態（共 {len(display_info)} 個）")
    print("━" * WORKTREE_STATUS_OUTPUT_WIDTH)
    print()

    for i, info in enumerate(display_info):
        print(f"[{info['label']}]")
        print(f"  路徑：   {info['path']}")
        print(f"  分支：   {info['branch']}")

        if not info['is_main']:
            # H3 修復：behind 不應加 + 前綴，only ahead（領先）加 + 符合 git 慣例
            ahead_str = f"+{info['ahead']}" if info['ahead'] > 0 else f"{info['ahead']}"
            behind_str = str(info['behind'])  # behind 不需要 + 號
            print(f"  領先：   {ahead_str} commits ahead of main")
            print(f"  落後：   {behind_str} commits behind main")

        print(f"  變更：   {info['uncommitted']} 個未 commit")

        if i < len(display_info) - 1:
            print()


def _extract_ticket_id_from_worktree(worktree: dict) -> Optional[str]:
    """
    從 worktree 字典中提取 Ticket ID

    共用函式，用於從 worktree 列表中提取 Ticket ID。
    避免重複的 extract_ticket_id_from_branch() 呼叫邏輯。

    Args:
        worktree: worktree 資訊字典

    Returns:
        str | None: 提取的 Ticket ID，或 None
    """
    # H4 修復：detached HEAD 沒有 branch 欄位，先檢查以避免傳空字串給 extract_ticket_id_from_branch
    if worktree.get("detached", False):
        return None
    branch = worktree.get("branch", "")
    return extract_ticket_id_from_branch(branch)


def _find_target_worktree(worktrees: list[dict], ticket_id: str) -> Optional[dict]:
    """
    在 worktree 列表中查詢特定 Ticket 對應的 worktree（#7 修復：從 cmd_status 拆分出來）

    Args:
        worktrees: worktree 列表
        ticket_id: 欲查詢的 Ticket ID

    Returns:
        dict | None: 找到的 worktree，或 None
    """
    for wt in worktrees:
        extracted_id = _extract_ticket_id_from_worktree(wt)
        if extracted_id == ticket_id:
            return wt
    return None


def cmd_status(ticket_id: Optional[str] = None) -> int:
    """
    status 子命令 - 查看 worktree 狀態

    Args:
        ticket_id: 可選，指定查詢特定 Ticket

    Returns:
        int: exit code (0 成功，1 失敗)
    """
    # Step 1: 取得全部 worktree 列表
    worktrees = get_worktree_list()

    # Step 2: 如果指定 ticket_id，進行篩選
    if ticket_id is not None:
        target_worktree = _find_target_worktree(worktrees, ticket_id)

        if target_worktree is None:
            print(f"[錯誤] 找不到 Ticket {ticket_id} 對應的 worktree。")
            print()

            # H7 修復：統一使用 _print_existing_worktrees() 消除重複邏輯
            _print_existing_worktrees()
            print()

            print("建立此 Ticket 的 worktree：")
            print(f"  /worktree create {ticket_id}")
            return 1

        worktrees = [target_worktree]

    # Step 3: 如果無任何 worktree（除主倉庫外）
    if ticket_id is None and len(worktrees) <= 1:
        print("目前沒有任何 worktree（除主倉庫外）。")
        print()
        print("建立新的 worktree：")
        print("  /worktree create <ticket-id>")
        return 0

    # Step 4: 收集 worktree 資訊
    display_info = _collect_worktree_info(worktrees)

    # Step 5: 格式化輸出
    _print_worktree_status(display_info)

    return 0


# ===== merge 子命令相關函式 =====


def _query_ticket_status(ticket_id: str) -> Optional[str]:
    """
    查詢 Ticket 的 status 欄位

    透過 subprocess 呼叫 ticket track query，解析 status 欄位回傳。
    若 CLI 不可用或查詢失敗，回傳 None（呼叫端依 None 決定是否降級）。

    Args:
        ticket_id: Ticket ID

    Returns:
        str | None: Ticket 狀態字串（如 "completed"），或 None 表示查詢失敗
    """
    try:
        result = subprocess.run(
            ["ticket", "track", "query", ticket_id],
            capture_output=True,
            text=True,
            timeout=TICKET_QUERY_TIMEOUT
        )
        if result.returncode == 0:
            # 簡單解析：從輸出中找 "status: completed" 之類的行
            for line in result.stdout.split('\n'):
                if 'status' in line.lower():
                    # 嘗試提取狀態值
                    parts = line.split(':')
                    if len(parts) >= 2:
                        return parts[1].strip()
        return None
    except subprocess.TimeoutExpired:
        # H4 修復：補充 stderr 輸出，符合 quality-baseline.md 規則 4 雙通道要求
        # 原因：TimeoutExpired 是非預期的事件，應警告用戶
        print(f"[Warning] Ticket status query timed out after {TICKET_QUERY_TIMEOUT}s", file=sys.stderr)
        return None
    except FileNotFoundError:
        # ticket CLI 不可用是正常降級場景（本地環境可能未安裝 ticket CLI）
        # 不需要 stderr 警告，呼叫端依 None 返回值降級為警告
        return None


def _is_branch_merged_to_base(branch: str, base: str = DEFAULT_BASE_BRANCH) -> bool:
    """
    判斷分支是否已合併到 base 分支

    使用 git branch --merged <base> 並檢查 branch 是否在結果中。

    Args:
        branch: 分支名稱
        base: 基礎分支，預設 "main"

    Returns:
        bool: True 表示已合併，False 表示未合併或無法判斷
    """
    success, output = run_git_command(["branch", "--merged", base])
    if not success:
        return False
    merged_branches = [b.strip() for b in output.split('\n')]
    return branch in merged_branches


def _is_branch_pushed(branch: str) -> bool:
    """
    判斷本地分支是否已 push 到 origin

    比較本地和 origin 分支的 HEAD commit 是否相同。
    若兩者 commit 相同，表示已 push 且同步；否則未 push 或不同步。

    Args:
        branch: 分支名稱（短名稱，不含 origin/ 前綴）

    Returns:
        bool: True 表示已 push（origin 存在且與本地同步），False 表示未 push
    """
    # H6 修復：消除重複的 rev-parse --verify 呼叫（合併為單次 rev-parse）
    # 只需查詢兩個 commit 值進行比較，若 origin/branch 不存在 rev-parse 會自動返回 False
    success_local, local_commit = run_git_command(["rev-parse", branch])
    success_remote, remote_commit = run_git_command(["rev-parse", f"origin/{branch}"])

    return success_local and success_remote and local_commit == remote_commit


def _merge_validate_ticket_status(ticket_id: str) -> tuple[bool, str]:
    """
    驗證 Ticket 狀態是否為 completed

    透過 ticket track query 查詢狀態，若 CLI 不可用則降級為警告。

    Args:
        ticket_id: Ticket ID

    Returns:
        tuple[bool, str]:
            - bool: True 表示可繼續（狀態為 completed 或查詢失敗降級）
            - str: 若 False，包含阻擋原因；若 True，可能含降級警告訊息
    """
    status = _query_ticket_status(ticket_id)

    if status is None:
        # 查詢失敗，降級為警告
        return True, MergeMessages.TICKET_STATUS_UNAVAILABLE

    if status.lower() == TICKET_COMPLETED_STATUS:
        return True, ""

    # Ticket 未完成，阻擋
    return False, MergeMessages.TICKET_NOT_COMPLETED.format(ticket_id=ticket_id, status=status)




def _merge_build_output(
    ticket_id: str,
    branch_name: str,
    ahead: int,
    behind: int,
    warnings: list[str]
) -> None:
    """
    輸出驗證結果和相關提示訊息

    Args:
        ticket_id: Ticket ID
        branch_name: 分支名稱（如 "feat/0.1.1-W9-002"）
        ahead: 分支領先 main 的 commit 數
        behind: 分支落後 main 的 commit 數
        warnings: 需要顯示的警告訊息列表（可為空）
    """
    print(MergeMessages.VERIFICATION_IN_PROGRESS)
    print()
    print(MergeMessages.VERIFICATION_TICKET_STATUS)
    print(MergeMessages.VERIFICATION_WORKING_TREE)
    print(f"  領先 main：{ahead} 個 commit")
    print(f"  落後 main：{behind} 個 commit")
    print()

    # 輸出任何警告
    for warning in warnings:
        print(warning)
        print()


def _print_existing_worktrees() -> None:
    """
    格式化列出所有現有的 worktree（含 Ticket ID）

    遍歷所有 worktree，提取 Ticket ID 並輸出清單。
    主要用於錯誤訊息（找不到指定 Ticket）。
    """
    existing_worktrees = get_worktree_list()
    existing = []
    for wt in existing_worktrees:
        extracted_id = _extract_ticket_id_from_worktree(wt)
        if extracted_id:
            branch = wt.get("branch", "")
            existing.append(f"  - {extracted_id} ({branch})")

    if existing:
        print("目前存在的 worktree：")
        for item in existing:
            print(item)


def _merge_build_warnings_list(ahead: int, behind: int, status_msg: str) -> list[str]:
    """
    根據 metrics 和狀態訊息構建警告清單

    W16 修復：認知負擔指數 = 7 (<= 10)

    Args:
        ahead: branch 領先 main 的 commit 數
        behind: branch 落後 main 的 commit 數
        status_msg: Ticket 狀態訊息（可為空）

    Returns:
        list[str]: 警告訊息列表
    """
    warnings = []
    if status_msg:
        warnings.append(status_msg)
    if ahead == 0:
        warnings.append(MergeMessages.NO_NEW_COMMITS.format(base=DEFAULT_BASE_BRANCH))
    return warnings


def _merge_collect_warnings_for_branch(branch_name: str, ticket_id: str) -> tuple[int, int, list[str]]:
    """
    計算 ahead/behind 並根據 metrics 收集警告訊息

    W16 修復：認知負擔指數 = 6 (<= 10)

    Args:
        branch_name: 分支名稱
        ticket_id: Ticket ID

    Returns:
        tuple[int, int, list[str]]: (ahead, behind, warnings)
    """
    ahead, behind = get_worktree_ahead_behind(branch_name, DEFAULT_BASE_BRANCH)

    # 檢查 Ticket 狀態降級警告
    _, status_msg = _merge_validate_ticket_status(ticket_id)

    warnings = _merge_build_warnings_list(ahead, behind, status_msg or "")
    return ahead, behind, warnings


def _merge_validate_preconditions(
    ticket_id: str,
    worktree_path: str
) -> bool:
    """
    驗證 merge 前置條件（Ticket 狀態和 working tree 乾淨）

    W16 修復：認知負擔指數 = 9 (<= 10)

    Args:
        ticket_id: Ticket ID
        worktree_path: worktree 絕對路徑

    Returns:
        bool: 驗證通過

    若驗證失敗，會直接 print 錯誤訊息
    """
    # 驗證 Ticket 狀態
    can_continue, msg = _merge_validate_ticket_status(ticket_id)
    if not can_continue:
        print(msg)
        return False

    # 檢查 working tree 乾淨
    is_clean, uncommitted = _check_working_tree_clean(worktree_path)
    if not is_clean:
        print(MergeMessages.DIRTY_WORKING_TREE.format(count=uncommitted))
        return False

    return True


def _merge_find_by_branch(branch: str) -> Optional[dict]:
    """以分支名查詢合併對象：有 worktree 回傳其 dict；無 worktree 但分支存在回傳 path=None；皆無回傳 None。"""
    for wt in get_worktree_list():
        if wt.get("branch") == branch:
            return wt
    ok, _ = run_git_command(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"])
    return {"path": None, "branch": branch} if ok else None


def _merge_log_pre_acceptance(label: str, reason: str, tag: str = "合併前驗收") -> None:
    """旗標與理由輸出並追加到 .claude/logs/worktree-merge.log（合併前驗收、略過合併前測試共用）。"""
    line = f"[{tag}] target={label} reason={reason}"
    print(line)
    try:
        log_dir = Path(get_project_root()) / ".claude" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "worktree-merge.log", "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
    except OSError as exc:
        sys.stderr.write(f"[WARNING] worktree-merge 日誌寫入失敗：{exc}\n")


def _merge_resolve_target(
    ticket_id: Optional[str], branch: Optional[str], pre_acceptance_reason: Optional[str]
) -> Optional[tuple[dict, str, str]]:
    """解析合併對象並做前置驗證。回傳 (worktree, branch_name, label)；驗證失敗回傳 None（訊息已輸出）。"""
    if branch:
        worktree = _merge_find_by_branch(branch)
        if worktree is None:
            print(f"[阻擋] 找不到分支 {branch}")
            return None
        if worktree.get("path"):
            clean, count = _check_working_tree_clean(worktree["path"])
            if not clean:
                print(MergeMessages.DIRTY_WORKING_TREE.format(count=count))
                return None
        return worktree, branch, branch

    worktree = _validate_and_find_worktree(ticket_id)
    if worktree is None:
        return None
    if pre_acceptance_reason:
        clean, count = _check_working_tree_clean(worktree["path"])
        if not clean:
            print(MergeMessages.DIRTY_WORKING_TREE.format(count=count))
            return None
    elif not _merge_validate_preconditions(ticket_id, worktree["path"]):
        return None
    return worktree, worktree.get("branch", f"feat/{ticket_id}"), ticket_id


def cmd_merge(
    ticket_id: Optional[str],
    pre_merge_check: "Optional[PreMergeCheck]" = None,
    *,
    branch: Optional[str] = None,
    pre_acceptance_reason: Optional[str] = None,
    skip_gate_reason: Optional[str] = None,
    gate_runner: "Optional[SuiteRunner]" = None,
    message: Optional[str] = None,
    ticket: Optional[str] = None,
) -> int:
    """
    merge 子命令 — 前置驗證後以隔離索引 CAS 直接完成合併

    合併 commit 訊息：message 非空時原文使用（含換行與 trailer）；否則在預設訊息
    `Merge branch '<分支>'` 後附 `(<票號>)`，票號取 ticket 參數，缺省為 ticket_id；
    兩者皆無時維持預設訊息。

    對象由 ticket_id 或 branch 指定（branch 用於萃取不到 ticket ID 的 worktree-agent-<id>，
    不查票狀態）。預設要求票 completed 且 working tree 乾淨；pre_acceptance_reason 非空時
    允許票未 completed（合併前驗收），旗標與理由寫入日誌。落後 base 僅提示，不阻擋；
    衝突由 merge_branch_cas 中止且 ref 不變。pre_merge_check 為可注入的合併前檢查掛點；
    未注入時預設掛上合併前全套件閘門（merge_gate.MergeGate，gate_runner 可替換套件執行器），
    skip_gate_reason 非空時略過閘門，旗標與理由寫入日誌。

    Returns:
        int: exit code（0 合併成功，1 驗證失敗或合併中止）
    """
    target = _merge_resolve_target(ticket_id, branch, pre_acceptance_reason)
    if target is None:
        return 1
    _worktree, branch_name, label = target

    ahead, behind = get_worktree_ahead_behind(branch_name, DEFAULT_BASE_BRANCH)
    warnings = _merge_build_warnings_list(ahead, behind, "")
    if pre_acceptance_reason:
        _merge_log_pre_acceptance(label, pre_acceptance_reason)
    elif ticket_id and not branch:
        _, status_msg = _merge_validate_ticket_status(ticket_id)
        warnings = _merge_build_warnings_list(ahead, behind, status_msg or "")
    if behind > 0:
        warnings.append(
            f"[提示] 分支落後 {DEFAULT_BASE_BRANCH} {behind} 個 commit，"
            "由三方合併處理；衝突時將中止且 ref 不變。"
        )

    _merge_build_output(label, branch_name, ahead, behind, warnings)
    print()
    print(MergeMessages.MERGE_EXECUTING.format(branch=branch_name, base=DEFAULT_BASE_BRANCH))
    merge_message = _compose_merge_message(branch_name, message, ticket or ticket_id)
    max_retries = None
    if pre_merge_check is None:
        if skip_gate_reason is not None:
            if not skip_gate_reason.strip():
                print(MergeMessages.SKIP_GATE_NEEDS_REASON)
                return 1
            _merge_log_pre_acceptance(label, skip_gate_reason, tag="略過合併前測試")
        else:
            pre_merge_check = MergeGate(get_project_root(), runner=gate_runner)
            max_retries = GATE_MAX_RETRIES
    if isinstance(pre_merge_check, MergeGate):
        return _merge_through_gate(pre_merge_check, branch_name, label, max_retries, merge_message)
    outcome = merge_branch_cas(branch_name, pre_merge_check=pre_merge_check, max_retries=max_retries,
                               message=merge_message)
    return _print_merge_outcome(outcome, label)


def _compose_merge_message(branch_name: str, message: Optional[str], ticket: Optional[str]) -> Optional[str]:
    """決定合併 commit 訊息：明示 message 優先；否則有票號時附在預設訊息後；皆無回傳 None。"""
    if message and message.strip():
        return message
    if ticket:
        return f"Merge branch '{branch_name}' ({ticket})"
    return None


def _merge_through_gate(
    gate: MergeGate, branch_name: str, label: str, max_retries: Optional[int],
    message: Optional[str] = None,
) -> int:
    """經合併閘門合併，並在閘門開始與結束各記一行（stdout 與 worktree-merge.log）。

    名額未取得（預估拒絕、等待逾時、訊號）是預期內結果：說明行已由名額閘門輸出，這裡只回傳
    其結束碼（拒絕／逾時為 125）；其餘例外記一行「中止」後原樣再拋，保留 traceback。
    """
    root = get_project_root()
    ok, base_head = _git_out(["rev-parse", DEFAULT_BASE_BRANCH], root)
    base_head = base_head if ok else "未知"

    def record(phase: str, commit: str, result: Optional[str] = None) -> None:
        emit_gate_line(root, gate_line(phase, DEFAULT_BASE_BRANCH, branch_name, commit, result))

    record("開始", base_head)
    try:
        outcome = merge_branch_cas(branch_name, pre_merge_check=gate, max_retries=max_retries,
                                   message=message, hold=gate.hold(branch_name, DEFAULT_BASE_BRANCH))
    except SlotWaitRefused as refused:
        record("結束", base_head, GATE_REFUSED if refused.exit_code == 125 else GATE_ABORTED)
        return refused.exit_code
    except BaseException:  # 非預期例外與中斷：留一行紀錄後原樣再拋
        record("結束", base_head, GATE_ABORTED)
        raise
    if outcome.ok:
        record("結束", outcome.commit_sha, GATE_WRITTEN)
    else:
        record("結束", base_head, gate_result_label(outcome.error))
    return _print_merge_outcome(outcome, label)


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


def _prepare_candidate(branch: str, base: str, repo: str, message: str):
    """計算待合併 commit（只寫物件）。回傳 (merge_commit, old_head, 中止說明)。"""
    ok, old_head = _resolve_commit(f"refs/heads/{base}", repo)
    ok2, branch_sha = _resolve_commit(f"refs/heads/{branch}", repo)
    if not (ok and ok2):
        return None, "", MergeMessages.CAS_REF_UNRESOLVED.format(base=base, branch=branch)
    if _git_raw(["merge-base", "--is-ancestor", branch_sha, old_head], repo).returncode == 0:
        return None, "", MergeMessages.CAS_ALREADY_MERGED.format(base=base, branch=branch)
    ok, tree = _compute_merge_tree(old_head, branch_sha, repo)
    if not ok:
        return None, "", tree
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
    repo = repo or get_project_root()
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


def _print_merge_outcome(outcome: MergeOutcome, ticket_id: str) -> int:
    if not outcome.ok:
        print(MergeMessages.MERGE_FAILED.format(error=outcome.error))
        return 1
    bad = _verify_three_planes(get_project_root(), outcome.synced, outcome.commit_sha)
    print(MergeMessages.CAS_RESULT.format(
        commit=outcome.commit_sha, attempts=outcome.attempts, synced=len(outcome.synced), bad=len(bad)))
    for path in outcome.skipped:
        print(MergeMessages.CAS_SKIPPED_FILE.format(path=path))
    for path in bad:
        print(MergeMessages.CAS_PLANE_MISMATCH.format(path=path))
    print(MergeMessages.MERGE_SUCCESS.format(ticket_id=ticket_id))
    return 0


# ===== 共用驗證函式 =====


def _validate_and_find_worktree(ticket_id: str) -> Optional[dict]:
    """
    驗證 Ticket ID 格式並查詢對應的 worktree

    此函式提取 cmd_merge 和 cmd_cleanup 中的共同驗證模式。
    若驗證失敗，會直接輸出錯誤訊息；若 worktree 不存在，也會輸出錯誤訊息並列出現有 worktree。

    Args:
        ticket_id: Ticket ID 字串

    Returns:
        Optional[dict]: 若驗證成功且 worktree 存在，返回 worktree dict；
                       若驗證失敗或 worktree 不存在，返回 None（錯誤訊息已輸出）
    """
    # Step 1: 驗證 Ticket ID 格式
    if not is_valid_ticket_id(ticket_id):
        print(CommonMessages.INVALID_TICKET_ID_FORMAT.format(ticket_id=ticket_id))
        return None

    # Step 2: 查詢對應的 worktree
    worktree = _find_target_worktree(get_worktree_list(), ticket_id)
    if worktree is None:
        print(CommonMessages.WORKTREE_NOT_FOUND.format(ticket_id=ticket_id))
        print()
        _print_existing_worktrees()
        return None

    return worktree


# ===== cleanup 子命令相關函式 =====


def _check_working_tree_clean(worktree_path: str) -> tuple[bool, int]:
    """
    檢查 worktree 的 working tree 是否乾淨

    共用檢查函式，用於 merge 和 cleanup 子命令。

    Args:
        worktree_path: worktree 絕對路徑

    Returns:
        tuple[bool, int]:
            - bool: True 表示乾淨（無未 commit 變更），False 表示有變更
            - int: 未 commit 變更數量
    """
    uncommitted = get_worktree_uncommitted_count(worktree_path)
    return (uncommitted == 0, uncommitted)


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
    return _check_working_tree_clean(worktree_path)


def _cleanup_check_level2(branch: str) -> tuple[bool, str]:
    """
    Level 2 閘門：檢查未 push 狀態（可被 --force 略過）

    透過比較 branch 和 origin/branch 的 commit 差距判斷是否已 push。
    若 origin 無對應分支（尚未 push 過），視為未 push。

    Args:
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


def _cleanup_execute(worktree_path: str, branch: str) -> tuple[bool, str]:
    """
    執行 worktree 清理（移除 worktree 目錄和分支）

    依序執行：
    1. git worktree remove <path>
    2. git branch -d <branch>（-d 要求已合併，若失敗則提示 -D）

    Args:
        worktree_path: worktree 絕對路徑
        branch: 分支名稱

    Returns:
        tuple[bool, str]:
            - bool: True 表示 worktree 和分支均已清理
            - str: 結果說明（成功訊息或部分失敗提示）
    """
    # 移除 worktree
    success, output = run_git_command(["worktree", "remove", worktree_path])
    if not success:
        error_msg = CleanupMessages.REMOVE_FAILED.format(error=output)
        return False, error_msg

    # 刪除分支
    success, output = run_git_command(["branch", "-d", branch])
    if not success:
        partial_msg = CleanupMessages.BRANCH_DELETE_FAILED.format(
            branch=branch,
            force_flag=BRANCH_FORCE_DELETE_FLAG
        )
        return True, partial_msg  # 部分成功

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
    branch: str
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
    success, result_msg = _cleanup_execute(path, branch)
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
    force: bool
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
    return _cleanup_execute_and_report(path, branch)


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
            print(f"    {CleanupMessages.SCAN_CLEANUP_HINT.format(ticket_id=ticket_id)}")
        print()

    # 警告
    if warnings:
        print(CleanupMessages.SCAN_WARNING)
        for ticket_id, branch, reason in warnings:
            print(f"  - {ticket_id} ({branch})  [{reason}]")
            print(f"    {CleanupMessages.SCAN_FORCE_HINT.format(ticket_id=ticket_id)}")
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


def cmd_cleanup(ticket_id: Optional[str] = None, force: bool = False) -> int:
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
    # 無參數：掃描模式
    if ticket_id is None:
        return _cleanup_scan_all()

    # 有參數：精確模式

    # Step 1-2: 驗證 Ticket ID 格式並查詢 worktree（共用函式）
    worktree = _validate_and_find_worktree(ticket_id)
    if worktree is None:
        return 1

    # Step 3: 執行清理
    return _cleanup_single(worktree, ticket_id, force)


# ===== 主程式入口 =====


def main():
    """主程式入口 - 支援 create 和 status 子命令"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Git Worktree 管理工具 - 從 Ticket ID 自動推導分支名和路徑"
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # create 子命令
    create_parser = subparsers.add_parser(
        "create",
        help="建立新 worktree"
    )
    create_parser.add_argument(
        "ticket_id",
        help="Ticket ID (例如：0.1.1-W9-002.1)"
    )
    create_parser.add_argument(
        "--base",
        default=DEFAULT_BASE_BRANCH,
        help=f"基礎分支，預設為 {DEFAULT_BASE_BRANCH}"
    )
    create_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只顯示操作，不執行"
    )

    # status 子命令
    status_parser = subparsers.add_parser(
        "status",
        help="查看 worktree 狀態"
    )
    status_parser.add_argument(
        "ticket_id",
        nargs="?",
        help="可選：指定查詢特定 Ticket ID"
    )

    # merge 子命令
    merge_parser = subparsers.add_parser(
        "merge",
        help="前置驗證並輸出 git merge 指令"
    )
    merge_parser.add_argument(
        "ticket_id",
        nargs="?",
        help="Ticket ID (例如：0.1.1-W9-002)；與 --branch 擇一"
    )
    merge_parser.add_argument(
        "--branch",
        help="以分支名指定合併對象（如 worktree-agent-<id>），不查票狀態"
    )
    merge_parser.add_argument(
        "--skip-gate",
        metavar="REASON",
        help="略過合併前全套件閘門（須帶理由，理由寫入日誌）"
    )
    merge_parser.add_argument(
        "--message", "-m",
        help="合併 commit 訊息（原文使用，可含換行與 trailer）；省略則用預設訊息"
    )
    merge_parser.add_argument(
        "--ticket",
        metavar="TICKET_ID",
        help="票號：預設訊息附上 (<票號>)；以 <ticket-id> 合併時自動帶入；--message 優先"
    )
    merge_parser.add_argument(
        "--pre-acceptance",
        metavar="REASON",
        help="合併前驗收：票未 completed 也允許合併，理由寫入日誌"
    )

    # cleanup 子命令
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="三閘門安全清理 worktree"
    )
    cleanup_parser.add_argument(
        "ticket_id",
        nargs="?",
        help="可選：指定清理特定 Ticket（若省略則掃描所有 worktree）"
    )
    cleanup_parser.add_argument(
        "--force",
        action="store_true",
        help="略過 Level 2（未 push）和 Level 3（未合併）警告（Level 1 永不可繞過）"
    )

    args = parser.parse_args()

    if args.command == "create":
        return cmd_create(
            args.ticket_id,
            base=args.base,
            dry_run=args.dry_run
        )
    elif args.command == "status":
        return cmd_status(args.ticket_id)
    elif args.command == "merge":
        if bool(args.ticket_id) == bool(args.branch):
            print("[錯誤] merge 需指定 <ticket-id> 或 --branch 其中之一")
            return 1
        return cmd_merge(
            args.ticket_id, branch=args.branch, pre_acceptance_reason=args.pre_acceptance,
            skip_gate_reason=args.skip_gate, message=args.message, ticket=args.ticket,
        )
    elif args.command == "cleanup":
        return cmd_cleanup(args.ticket_id, force=args.force)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
