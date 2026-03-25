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


def get_project_root() -> Path:
    """
    取得專案根目錄

    搜尋優先級：
    1. CLAUDE_PROJECT_DIR 環境變數
    2. git rev-parse --show-toplevel（git-native，支援 worktree 環境）
    3. 向上搜尋 CLAUDE.md（通用框架標準入口，支援 Go/混合型專案）
    4. 向上搜尋 go.mod（Go 專案）
    5. 向上搜尋 pubspec.yaml（Flutter 專案）
    6. fallback: Path.cwd()

    Returns:
        Path: 專案根目錄路徑

    Examples:
        >>> root = get_project_root()
        >>> (root / "CLAUDE.md").exists() or (root / "go.mod").exists() or (root / "pubspec.yaml").exists()
        True
    """
    # 1. 環境變數優先
    claude_project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if claude_project_dir:
        return Path(claude_project_dir)

    # 2. git rev-parse --show-toplevel（git-native，支援 worktree）
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
        # git 命令不存在或超時，進入 fallback
        pass

    # 3-5. 向上搜尋標記檔案（依通用性排序）
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

    # 標準化版本號
    if not version.startswith(VERSION_PREFIX):
        version = f"{VERSION_PREFIX}{version}"

    return root / WORK_LOGS_DIR / version / TICKETS_DIR


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
