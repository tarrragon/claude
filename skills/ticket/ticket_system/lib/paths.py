"""
路徑管理模組

提供專案根目錄、Tickets 目錄和 Ticket 檔案路徑的取得功能。
"""
# 防止直接執行此模組
import os
import subprocess
from pathlib import Path

from .constants import WORK_LOGS_DIR, TICKETS_DIR
from .ui_constants import VERSION_PREFIX, VERSION_PREFIX_LENGTH

# git rev-parse 執行超時時限（秒）
GIT_TOPLEVEL_TIMEOUT = 5


def _git_toplevel() -> Path | None:
    """
    執行 git rev-parse --show-toplevel 取得當前 cwd 所屬的 git 工作樹根目錄。

    在 worktree 環境下回傳 worktree 自己的根目錄（git 標準行為），
    供 get_project_root() 偵測「當前是否在 worktree 中」。

    Returns:
        Path | None: git 工作樹根目錄；git 不可用 / 超時 / 失敗時回傳 None
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=GIT_TOPLEVEL_TIMEOUT
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # git 命令不存在或超時，視為無法取得 git root
        pass
    return None


def _linked_worktree_root() -> Path | None:
    """
    偵測當前 cwd 是否位於 git 的「linked worktree」（git worktree add 建立），
    若是則回傳該 worktree 的根目錄；否則回傳 None。

    判據（git-native）：linked worktree 的 `--git-dir`（worktree 私有 .git 目錄）
    與 `--git-common-dir`（主 repo 共享 .git）不同；主 repo 本身兩者相同。
    此判據精確區分「真的在 worktree 中」與「只是 cwd 在主 repo」，
    避免誤把主 repo 當 worktree 而覆蓋 CLAUDE_PROJECT_DIR（W3-008 根因 1 修復，
    且不破壞「CLAUDE_PROJECT_DIR 為主 repo 內測試 fixture」的既有契約）。

    Returns:
        Path | None: linked worktree 根目錄；非 worktree / git 不可用時回傳 None
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=GIT_TOPLEVEL_TIMEOUT
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # git 不可用 / 超時：無法判斷，視為非 worktree
        return None

    if result.returncode != 0:
        return None

    lines = result.stdout.strip().split("\n")
    if len(lines) < 2:
        return None

    # git 可能一個回絕對路徑、另一個回相對路徑（取決於 cwd 在 repo 的深度），
    # 兩者可能指向同一目錄。必須 resolve 為真實絕對路徑再比較，否則
    # 主 repo 子目錄會因字串不同被誤判為 linked worktree（W3-010 實證）。
    git_dir = Path(lines[0].strip()).resolve()
    git_common_dir = Path(lines[1].strip()).resolve()
    # 主 repo：git_dir == git_common_dir；linked worktree：兩者不同
    if git_dir == git_common_dir:
        return None

    return _git_toplevel()


def get_project_root() -> Path:
    """
    取得專案根目錄

    搜尋優先級：
    1. worktree 感知：當前位於 git linked worktree（git worktree add 建立）時，
       優先用該 worktree 的根目錄。避免 worktree 內的 ticket CRUD / append-log /
       auto-commit 因 CLAUDE_PROJECT_DIR 恆指向主 repo 而洩漏到主 repo（W3-008 根因 1）。
    2. CLAUDE_PROJECT_DIR 環境變數（非 worktree 場景，維持原行為）
    3. git rev-parse --show-toplevel（git-native，未設環境變數時）
    4. 向上搜尋 CLAUDE.md（通用框架標準入口，支援 Go/混合型專案）
    5. 向上搜尋 go.mod（Go 專案）
    6. 向上搜尋 pubspec.yaml（Flutter 專案）
    7. fallback: Path.cwd()

    Returns:
        Path: 專案根目錄路徑

    Examples:
        >>> root = get_project_root()
        >>> (root / "CLAUDE.md").exists() or (root / "go.mod").exists() or (root / "pubspec.yaml").exists()
        True
    """
    # 1. worktree 感知（優先於 CLAUDE_PROJECT_DIR）：
    #    僅在「git linked worktree」中才覆蓋，主 repo（即使 cwd 在主 repo）不觸發。
    worktree_root = _linked_worktree_root()
    if worktree_root is not None:
        return worktree_root

    # 2. 環境變數優先（非 worktree 場景，維持原行為）
    claude_project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if claude_project_dir:
        return Path(claude_project_dir)

    # 3. git rev-parse --show-toplevel（git-native，支援 worktree）
    git_root = _git_toplevel()
    if git_root is not None:
        return git_root

    # 向上搜尋標記檔案（依通用性排序）
    markers = ["CLAUDE.md", "go.mod", "pubspec.yaml"]
    current = Path.cwd()
    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                return current
        current = current.parent

    return Path.cwd()


def get_tickets_dir(version: str) -> Path:
    """
    取得 Tickets 目錄路徑

    支援階層式目錄結構：docs/work-logs/v{major}/v{major}.{minor}/v{version}/tickets/

    Args:
        version: 版本號（可以帶 v 前綴，可以不帶）

    Returns:
        Path: Tickets 目錄路徑

    Examples:
        >>> tickets_dir = get_tickets_dir("0.31.0")
        >>> tickets_dir.name
        'tickets'
    """
    root = get_project_root()

    # 標準化版本號（去掉 v 前綴再加回）
    bare_version = version.lstrip("v").lstrip(VERSION_PREFIX)
    versioned = f"{VERSION_PREFIX}{bare_version}"

    # 解析 major.minor 用於階層路徑。
    # W14-052：新建 ticket 一律三層（避免未存在主版本建在 flat 造成殘留 +
    #   與三層規則不一致）。
    # W9-006.1 / issue #1 問題4：補既有 flat 結構（docs/work-logs/v{version}/
    #   tickets/）的「讀取」相容——hierarchical 存在用之；否則 flat 實際存在
    #   才回 flat（讀既有）；兩者皆不存在時 default hierarchical。新版本（flat
    #   不存在）仍一律三層，W14-052 不變式不破。
    parts = bare_version.split(".")
    if len(parts) >= 2:
        major = parts[0]
        minor = f"{parts[0]}.{parts[1]}"
        hierarchical = root / WORK_LOGS_DIR / f"v{major}" / f"v{minor}" / versioned / TICKETS_DIR
        if hierarchical.exists():
            return hierarchical
        flat = root / WORK_LOGS_DIR / versioned / TICKETS_DIR
        if flat.exists():
            return flat
        return hierarchical

    # 最終 safety net：版本字串無法解析 major.minor 時使用 flat 結構
    flat = root / WORK_LOGS_DIR / versioned / TICKETS_DIR
    return flat


def get_ticket_path(version: str, ticket_id: str) -> Path:
    """
    取得 Ticket 檔案路徑

    優先傳回存在的 .md 檔案，次選 .yaml 檔案。
    若都不存在，預設傳回 .md 路徑。

    Args:
        version: 版本號
        ticket_id: Ticket ID（不含副檔名）

    Returns:
        Path: Ticket 檔案路徑

    Examples:
        >>> path = get_ticket_path("0.31.0", "0.31.0-W4-001")
        >>> path.suffix
        '.md'
    """
    tickets_dir = get_tickets_dir(version)

    md_path = tickets_dir / f"{ticket_id}.md"
    yaml_path = tickets_dir / f"{ticket_id}.yaml"

    if md_path.exists():
        return md_path
    if yaml_path.exists():
        return yaml_path

    # 預設返回 .md 路徑
    return md_path


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
