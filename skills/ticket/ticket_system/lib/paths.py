"""
路徑管理模組

提供專案根目錄、Tickets 目錄和 Ticket 檔案路徑的取得功能。
"""
# 防止直接執行此模組
import os
from pathlib import Path

from .constants import WORK_LOGS_DIR, TICKETS_DIR
from .ui_constants import VERSION_PREFIX, VERSION_PREFIX_LENGTH


def get_project_root() -> Path:
    """
    取得專案根目錄

    通過向上搜尋 pubspec.yaml 檔案來定位專案根目錄。

    Returns:
        Path: 專案根目錄路徑

    Examples:
        >>> root = get_project_root()
        >>> (root / "pubspec.yaml").exists()
        True
    """
    # 優先使用環境變數
    claude_project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if claude_project_dir:
        return Path(claude_project_dir)

    # 向上搜尋 pubspec.yaml
    current = Path.cwd()
    while current != current.parent:
        if (current / "pubspec.yaml").exists():
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
