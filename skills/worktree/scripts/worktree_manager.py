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
import shlex
import sys
from pathlib import Path
from typing import Optional
import subprocess
import time

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
    from .merge_cas import (
        CheckResult, MergeOutcome, PreMergeCheck, _git_out, _verify_three_planes, merge_branch_cas,
        precheck_merge_conflict,
    )
    from .merge_gate import (
        GATE_MAX_RETRIES, GATE_ABORTED, GATE_PRECHECK_CLEAR, GATE_PRECHECK_CONFLICT, GATE_REFUSED, GATE_WRITTEN, MergeGate,
        SlotWaitRefused, SuiteRunner,
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
    from merge_cas import (
        CheckResult, MergeOutcome, PreMergeCheck, _git_out, _verify_three_planes, merge_branch_cas,
        precheck_merge_conflict,
    )
    from merge_gate import (
        GATE_MAX_RETRIES, GATE_ABORTED, GATE_PRECHECK_CLEAR, GATE_PRECHECK_CONFLICT, GATE_REFUSED, GATE_WRITTEN, MergeGate,
        SlotWaitRefused, SuiteRunner,
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


def merge_suggestion_command(branch: str) -> str:
    """分支名轉為經合併閘門的 `/worktree merge` 建議字串（供 hook 提示使用）。

    feat/<ticket-id> 印 ticket 形式，其餘分支印 `--branch <quoted>`。
    """
    ticket_id = extract_ticket_id_from_branch(branch)
    if ticket_id:
        return f"/worktree merge {ticket_id}"
    return f"/worktree merge --branch {shlex.quote(branch)}"


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


WORKTREE_ADD_TIMEOUT_SECONDS = 120


def _cleanup_failed_create(branch_name: str, worktree_path: str) -> None:
    """add 失敗或逾時後，清掉本次自建的 worktree 與分支。

    前置驗證已確保分支與路徑在 add 前不存在，故兩者若存在皆為本次所建。
    """
    root = str(get_project_root())
    # 逾時被殺的 worktree 會停在 locked initializing，需雙 --force 才能移除
    _run_cleanup_step(root, "worktree remove", worktree_path,
                      ["worktree", "remove", "--force", "--force", worktree_path])
    _run_cleanup_step(root, "worktree prune", worktree_path, ["worktree", "prune"])
    if check_branch_exists(branch_name):
        ok = _run_cleanup_step(root, "branch -D", branch_name, ["branch", "-D", branch_name])
        if not ok:
            print(f"[警告] 清理分支 {branch_name} 失敗，見 worktree-merge.log", file=sys.stderr)


def _run_cleanup_step(root: str, step: str, target: str, git_args: list[str]) -> bool:
    """執行一個清理步驟，結果（成功或失敗＋git 輸出摘要）寫入 worktree-merge.log。"""
    ok, output = run_git_command(git_args)
    result = "成功" if ok else "失敗"
    summary = output.replace("\n", " ")[:200]
    detail = f"｜輸出 {summary}" if (not ok and summary) else ""
    emit_gate_line(root, f"[建立清理]{step}｜target {target}｜結果 {result}{detail}")
    return ok


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
    success, output = run_git_command(git_cmd, timeout=WORKTREE_ADD_TIMEOUT_SECONDS)
    if not success:
        _cleanup_failed_create(branch_name, worktree_path)
        reason = "逾時" if "timed out" in output else "失敗"
        print(f"[錯誤] 建立 worktree {reason}：{output}")
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
    outcome = merge_branch_cas(branch_name, repo=get_project_root(), pre_merge_check=pre_merge_check,
                               max_retries=max_retries, message=merge_message)
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
        conflict = precheck_merge_conflict(branch_name, DEFAULT_BASE_BRANCH, root)
        if conflict:  # 排隊前即知必敗：不占名額佇列
            print(MergeMessages.MERGE_FAILED.format(error=conflict))
            record("結束", base_head, GATE_PRECHECK_CONFLICT)
            return 1
        record("預檢", base_head, GATE_PRECHECK_CLEAR)
        outcome = merge_branch_cas(branch_name, repo=root, pre_merge_check=gate, max_retries=max_retries,
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


# ===== cleanup 子命令（實作在 cleanup_command） =====
#
# cleanup_command 自本模組匯入共用函式，本模組若在頂層匯入它會形成循環匯入，
# 故以模組層 __getattr__（PEP 562）延遲轉出：`worktree_manager.<名稱>` 與
# `from worktree_manager import <名稱>` 仍可取得。轉出只保住取用，保不住 patch：
# 測試要替換 cleanup 的函式或它查找的名稱，patch cleanup_command。
# WORKTREE_REMOVE_TIMEOUT_SECONDS 是測試注入點，只留在 cleanup_command，不轉出。

_CLEANUP_REEXPORTS = frozenset({
    "_cleanup_check_level1",
    "_cleanup_check_level2",
    "_cleanup_check_level2_and_3",
    "_cleanup_check_level3",
    "_cleanup_classify_worktrees",
    "_cleanup_execute",
    "_cleanup_execute_and_report",
    "_cleanup_filter_feature_worktrees",
    "_cleanup_find_by_branch",
    "_cleanup_handle_lock",
    "_cleanup_print_initial_header",
    "_cleanup_print_scan_report",
    "_cleanup_recover",
    "_cleanup_scan_all",
    "_cleanup_single",
    "_cleanup_target_arg",
    "_cleanup_verify_all_gates",
    "_is_branch_merged_to_base",
    "_is_branch_pushed",
    "_lock_holder_alive",
    "_parse_worktree_lock",
    "_recovery_unmet_conditions",
    "_timed_git_remove",
    "cmd_cleanup",
})


def _load_cleanup_command():
    """載入 cleanup_command（套件與 scripts 目錄兩種執行情境）。"""
    try:
        from . import cleanup_command
    except ImportError:
        import cleanup_command
    return cleanup_command


def __getattr__(name: str):
    if name in _CLEANUP_REEXPORTS:
        return getattr(_load_cleanup_command(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
        "--branch",
        help="以分支名指定清理對象（如 worktree-agent-<id>），與 ticket_id 擇一"
    )
    cleanup_parser.add_argument(
        "--force",
        action="store_true",
        help="略過 Level 2（未 push）和 Level 3（未合併）警告（Level 1 永不可繞過）"
    )

    cleanup_parser.add_argument(
        "--unlock",
        action="store_true",
        help="worktree 被鎖時解鎖後再移除（預設遇鎖停手；鎖可能屬仍在使用的代理人）"
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
        if args.ticket_id and args.branch:
            print("[錯誤] cleanup 的 <ticket-id> 與 --branch 擇一，不可同時指定")
            return 1
        return _load_cleanup_command().cmd_cleanup(
            args.ticket_id, force=args.force, branch=args.branch, unlock=args.unlock
        )
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
