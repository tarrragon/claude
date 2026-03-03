"""
Ticket resume 命令模組

負責恢復任務功能，從 handoff 交接檔案讀取工作內容。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

from ticket_system.lib.ticket_loader import resolve_version, load_ticket, get_project_root
from ticket_system.lib.messages import (
    ErrorMessages,
    WarningMessages,
    InfoMessages,
    SectionHeaders,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_lifecycle_messages import (
    ResumeMessages,
    format_msg,
)


def _get_handoff_dir(subdir: str = "pending") -> Path:
    """
    取得 handoff 目錄

    Args:
        subdir: 子目錄名 ("pending" 或 "archive")

    Returns:
        Path: handoff 目錄路徑
    """
    root = get_project_root()
    handoff_dir = root / ".claude" / "handoff" / subdir
    return handoff_dir


def _find_handoff_file(ticket_id: str, subdir: str = "pending") -> Optional[tuple[Path, str]]:
    """
    尋找 handoff 檔案，返回 (路徑, 格式)

    Args:
        ticket_id: Ticket ID
        subdir: 子目錄名 ("pending" 或 "archive")

    Returns:
        tuple[Path, str] | None: (檔案路徑, "json" | "markdown") 或 None
    """
    dir_path = _get_handoff_dir(subdir)

    # 優先檢查 JSON 格式
    json_file = dir_path / f"{ticket_id}.json"
    if json_file.exists():
        return (json_file, "json")

    # 其次檢查 Markdown 格式
    md_file = dir_path / f"{ticket_id}.md"
    if md_file.exists():
        return (md_file, "markdown")

    return None


def list_pending_handoffs() -> List[Dict[str, Any]]:
    """
    列出所有待恢復的 handoff 檔案

    Returns:
        List[Dict]: handoff 資料列表
    """
    pending_dir = _get_handoff_dir("pending")

    if not pending_dir.exists():
        return []

    handoffs = []

    # 同時掃描 .json 和 .md 檔案
    for handoff_file in sorted(pending_dir.glob("*.json")) + sorted(pending_dir.glob("*.md")):
        try:
            if handoff_file.suffix == ".json":
                with open(handoff_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    handoffs.append(data)
            elif handoff_file.suffix == ".md":
                # Markdown 格式的 handoff 檔案也支援
                # 提取檔名作為 ticket_id
                ticket_id = handoff_file.stem
                handoffs.append({
                    "ticket_id": ticket_id,
                    "format": "markdown",
                    "path": str(handoff_file.relative_to(get_project_root()))
                })
        except (IOError, json.JSONDecodeError):
            # 略過無法讀取的檔案
            pass

    return handoffs


def load_handoff_file(ticket_id: str) -> Optional[Dict[str, Any]]:
    """
    載入特定的 handoff 檔案

    Args:
        ticket_id: Ticket ID

    Returns:
        Optional[Dict]: handoff 資料，或 None 如果不存在
    """
    file_info = _find_handoff_file(ticket_id, "pending")
    if not file_info:
        return None

    file_path, file_format = file_info

    try:
        if file_format == "json":
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:  # markdown
            content = file_path.read_text(encoding="utf-8")
            return {
                "ticket_id": ticket_id,
                "format": "markdown",
                "content": content,
                "path": str(file_path.relative_to(get_project_root()))
            }
    except (IOError, json.JSONDecodeError):
        pass

    return None


def mark_handoff_as_resumed(ticket_id: str) -> bool:
    """
    標記 handoff 檔案為已接手（更新 resumed_at 時間戳）

    Args:
        ticket_id: Ticket ID

    Returns:
        bool: 成功返回 True，失敗返回 False
    """
    file_info = _find_handoff_file(ticket_id, "pending")
    if not file_info:
        return False

    file_path, file_format = file_info

    if file_format != "json":
        # Markdown 格式無法更新，移到 archive
        return archive_handoff_file(ticket_id)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["resumed_at"] = datetime.now().isoformat()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return True
    except (IOError, json.JSONDecodeError, OSError):
        return False


def archive_handoff_file(ticket_id: str) -> bool:
    """
    將 handoff 檔案移動到 archive 目錄

    Args:
        ticket_id: Ticket ID

    Returns:
        bool: 成功返回 True，失敗返回 False
    """
    file_info = _find_handoff_file(ticket_id, "pending")
    if not file_info:
        return False

    file_path, _ = file_info
    archive_dir = _get_handoff_dir("archive")
    archive_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path.rename(archive_dir / file_path.name)
        return True
    except (IOError, OSError):
        return False


def _print_basic_info(handoff: Dict[str, Any]) -> None:
    """列印基本資訊（Ticket ID、標題、狀態、方向、時間）"""
    ticket_id = handoff.get("ticket_id")

    print(SectionHeaders.BASIC_INFO)
    print(f"  Ticket ID: {ticket_id}")

    if "title" in handoff:
        print(f"  標題: {handoff.get('title', '?')}")

    if "from_status" in handoff:
        print(f"  前狀態: {handoff.get('from_status', '?')}")

    if "direction" in handoff:
        print(f"  交接方向: {handoff.get('direction', 'auto')}")

    if "timestamp" in handoff:
        print(f"  交接時間: {handoff.get('timestamp')}")

    print()


def _print_5w1h_info(handoff: Dict[str, Any]) -> None:
    """列印 5W1H 任務描述"""
    if "what" in handoff:
        print(SectionHeaders.TASK_DESCRIPTION)
        print(f"  {handoff.get('what')}")
        print()


def _print_chain_info(handoff: Dict[str, Any]) -> None:
    """列印任務鏈資訊"""
    if "chain" not in handoff or not handoff["chain"]:
        return

    chain = handoff["chain"]
    print(SectionHeaders.TASK_CHAIN_INFO)
    print(f"  Root: {chain.get('root', 'N/A')}")
    print(f"  Parent: {chain.get('parent', 'N/A')}")
    print(f"  Depth: {chain.get('depth', 0)}")

    if "sequence" in chain:
        sequence_str = ".".join(map(str, chain["sequence"]))
        print(f"  序列: {sequence_str}")

    print()


def _print_markdown_content(handoff: Dict[str, Any]) -> None:
    """列印 Markdown 格式的完整內容"""
    if handoff.get("format") != "markdown" or "content" not in handoff:
        return

    print(SectionHeaders.FULL_CONTENT)
    print(handoff["content"])
    print()


def _print_ticket_info(ticket: Dict[str, Any]) -> None:
    """列印 Ticket 系統資訊"""
    print(SectionHeaders.TICKET_SYSTEM_INFO)
    print(f"  狀態: {ticket.get('status', 'unknown')}")

    for key in ["assignee", "priority", "type"]:
        if key in ticket:
            print(f"  {key.capitalize()}: {ticket.get(key)}")

    print()


def _print_handoff_info(handoff: Dict[str, Any], ticket: Optional[Dict[str, Any]] = None) -> None:
    """
    列印 handoff 交接資訊

    Args:
        handoff: handoff 資料
        ticket: Ticket 資料（可選）
    """
    ticket_id = handoff.get("ticket_id")

    print("=" * 60)
    print(f"[Resume] {ticket_id}")
    print("=" * 60)
    print()

    _print_basic_info(handoff)
    _print_5w1h_info(handoff)
    _print_chain_info(handoff)
    _print_markdown_content(handoff)

    if ticket:
        _print_ticket_info(ticket)


def _execute_list() -> int:
    """執行 --list 子命令"""
    handoffs = list_pending_handoffs()

    if not handoffs:
        print(ResumeMessages.NO_PENDING_RESUMPTIONS)
        return 0

    print("=" * 60)
    print(SectionHeaders.PENDING_RESUME_LIST)
    print("=" * 60)
    print()

    for idx, handoff in enumerate(handoffs, 1):
        ticket_id = handoff.get("ticket_id", "unknown")
        title = handoff.get("title", "")
        timestamp = handoff.get("timestamp", "")

        print(f"{idx}. {ticket_id}")
        if title:
            print(f"   標題: {title}")
        if timestamp:
            print(f"   時間: {timestamp}")
        print()

    print(f"總計: {len(handoffs)} 個待恢復任務")
    print()
    print(ResumeMessages.RESUME_INSTRUCTIONS)
    print(ResumeMessages.RESUME_EXAMPLE_CMD)

    return 0


def _validate_args(args: argparse.Namespace) -> Optional[str]:
    """
    驗證參數，返回錯誤訊息或 None
    """
    ticket_id = getattr(args, "ticket_id", None)
    if not ticket_id:
        return format_error(ErrorMessages.MISSING_TICKET_ID)
    return None


def _print_args_error(error_msg: str) -> None:
    """列印參數錯誤和使用說明"""
    print(error_msg)
    print()
    print(ResumeMessages.RESUME_USAGE)
    print(ResumeMessages.RESUME_EXAMPLE_CMD)
    print(ResumeMessages.RESUME_LIST_CMD)
    print()
    print(ResumeMessages.RESUME_EXAMPLES)
    print(ResumeMessages.RESUME_EXAMPLE_ID)
    print(ResumeMessages.RESUME_LIST_CMD)


def _execute_resume(ticket_id: str, version: Optional[str]) -> int:
    """
    執行恢復單一 Ticket 的邏輯

    Args:
        ticket_id: Ticket ID
        version: 版本號（可選）

    Returns:
        int: 返回碼（0=成功, 1=失敗）
    """
    handoff = load_handoff_file(ticket_id)
    if not handoff:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=ticket_id))
        print()
        print(ResumeMessages.AVAILABLE_RESUMPTIONS)
        print(ResumeMessages.RESUME_LIST_CMD)
        return 1

    # 嘗試從 Ticket 系統載入對應的 Ticket 資訊
    ticket = None
    if version:
        resolved_version = resolve_version(version)
        if resolved_version:
            ticket = load_ticket(resolved_version, ticket_id)

    # 列印 handoff 資訊
    _print_handoff_info(handoff, ticket)

    # 標記為已接手（更新 resumed_at 時間戳）
    if not mark_handoff_as_resumed(ticket_id):
        print(format_warning(WarningMessages.INVALID_OPERATION))
        print(WarningMessages.HANDOFF_UPDATE_FAILED)
        return 1

    print("=" * 60)
    print(SectionHeaders.COMPLETION)
    print(InfoMessages.HANDOFF_RESUMED)
    print("=" * 60)
    return 0


def execute(args: argparse.Namespace) -> int:
    """執行 resume 命令"""
    if getattr(args, "list", False):
        return _execute_list()

    # 驗證參數
    error_msg = _validate_args(args)
    if error_msg:
        _print_args_error(error_msg)
        return 1

    # 執行恢復邏輯
    ticket_id = getattr(args, "ticket_id", None)
    version = getattr(args, "version", None)
    return _execute_resume(ticket_id, version)


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 resume 子命令"""
    parser = subparsers.add_parser("resume", help=ResumeMessages.HELP_TEXT)
    parser.add_argument("ticket_id", nargs="?", help=ResumeMessages.ARG_TICKET_ID_HELP)
    parser.add_argument("--list", action="store_true", help=ResumeMessages.ARG_LIST_HELP)
    parser.add_argument("--version", help=ResumeMessages.ARG_VERSION_HELP)
    parser.set_defaults(func=execute)
