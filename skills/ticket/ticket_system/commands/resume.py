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
import sys
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List

from ticket_system.lib.constants import (
    HANDOFF_DIR,
    HANDOFF_PENDING_SUBDIR,
    HANDOFF_ARCHIVE_SUBDIR,
    STATUS_COMPLETED,
)
from ticket_system.commands.exceptions import HandoffSchemaError, HandoffDirectionUnknownError
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
from ticket_system.lib.handoff_utils import (
    extract_direction_target_id,
    is_ticket_completed,
    is_task_chain_direction,
    is_ticket_in_progress_or_completed,
    is_valid_direction,
    scan_pending_handoffs,
)
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY


# W7-004：定義 handoff 列表結果型別（從函式屬性改為明確的返回值）
# 包含有效 handoff 清單、過濾計數和格式錯誤計數
HandoffListResult = namedtuple("HandoffListResult", ["handoffs", "stale_count", "schema_error_count"])




def _get_handoff_dir(subdir: str = HANDOFF_PENDING_SUBDIR) -> Path:
    """
    取得 handoff 目錄

    Args:
        subdir: 子目錄名 ("pending" 或 "archive")

    Returns:
        Path: handoff 目錄路徑
    """
    root = get_project_root()
    handoff_dir = root / HANDOFF_DIR / subdir
    return handoff_dir


def _find_handoff_file(ticket_id: str, subdir: str = HANDOFF_PENDING_SUBDIR) -> Optional[tuple[Path, str]]:
    """
    尋找 handoff 檔案，返回 (路徑, 格式)

    支援兩種查詢方式：
    1. 直接匹配：尋找以 ticket_id 命名的檔案（來源 ticket）
    2. 反向匹配（僅 pending）：掃描 direction 欄位，找出指向目標 ticket 的 handoff

    Args:
        ticket_id: Ticket ID
        subdir: 子目錄名 ("pending" 或 "archive")

    Returns:
        tuple[Path, str] | None: (檔案路徑, "json" | "markdown") 或 None
    """
    dir_path = _get_handoff_dir(subdir)

    # 優先檢查 JSON 格式（直接匹配）
    json_file = dir_path / f"{ticket_id}.json"
    if json_file.exists():
        return (json_file, "json")

    # 其次檢查 Markdown 格式（直接匹配）
    md_file = dir_path / f"{ticket_id}.md"
    if md_file.exists():
        return (md_file, "markdown")

    # Fallback：僅在 pending 目錄掃描，透過 direction 欄位反向查找
    # 例：找 0.1.0-W9-001 時，也會找到指向它的 handoff（direction: "to-sibling:0.1.0-W9-001"）
    if subdir == HANDOFF_PENDING_SUBDIR:
        for json_candidate in sorted(dir_path.glob("*.json")):
            try:
                with open(json_candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                direction = data.get("direction", "")
                if direction:
                    if extract_direction_target_id(direction) == ticket_id:
                        return (json_candidate, "json")
            except (json.JSONDecodeError, IOError):
                # 略過無法解析的檔案
                continue

    return None


def list_pending_handoffs() -> HandoffListResult:
    """
    列出所有待恢復的 handoff 檔案

    過濾規則：已 completed 的 Ticket 對應的 handoff 條目不顯示（stale handoff）

    使用 scan_pending_handoffs() 進行共用掃描邏輯，並應用呼叫端特定的錯誤處理
    （計數並輸出 stderr 警告）。

    Returns:
        HandoffListResult: 包含有效 handoff 清單、stale 計數、格式錯誤計數
    """
    records = scan_pending_handoffs()

    if not records:
        return HandoffListResult(handoffs=[], stale_count=0, schema_error_count=0)

    handoffs = []
    stale_count = 0
    schema_error_count = 0

    for record in records:
        # 處理解析錯誤（JSON 讀取失敗）
        if record.parse_error:
            # 略過無法讀取的檔案（不計數，保持原行為）
            continue

        # 處理格式錯誤（必填欄位缺失）
        if record.schema_error:
            schema_error_count += 1
            print(f"[WARNING] 跳過格式錯誤的 handoff：{record.file_path.name}（{record.schema_error}）", file=sys.stderr)
            continue

        # 驗證 direction（僅 JSON 格式有此欄位）
        if record.format == "json":
            direction = record.direction
            if not is_valid_direction(direction):
                # W9-001：改為逐檔案處理，不中斷整個迴圈
                schema_error_count += 1
                print(f"[WARNING] 跳過未知 direction 的 handoff：{record.file_path.name}（direction={direction!r}）", file=sys.stderr)
                continue

            # 過濾 stale handoff：
            # Handoff 是 stale 當且僅當：
            # 1. 來源 Ticket 已 completed（status: completed）
            # 2. 且 Handoff 是從非 completed 狀態創建的（from_status != "completed"）
            #
            # 特殊情況（保留）：
            # - 任務鏈 handoff（to-sibling/to-parent/to-child），即使 completed 也保留
            # - Handoff 本身是從 completed 狀態創建的，不算 stale
            if record.ticket_id and is_ticket_completed(record.ticket_id):
                # Ticket 已 completed，檢查 handoff 狀態
                if is_task_chain_direction(direction):
                    # 任務鏈 handoff：進一步檢查目標 ticket 是否已啟動
                    target_id = extract_direction_target_id(direction)
                    if target_id and is_ticket_in_progress_or_completed(target_id):
                        # 目標已啟動，此 handoff 為 stale（W4-002 計數）
                        stale_count += 1
                        continue
                    # 目標未啟動或無 target_id，保留
                    handoffs.append(record.data)
                    continue

                # 非任務鏈：只有當 from_status 不是 completed 時才過濾為 stale
                if record.from_status != "completed":
                    # Stale handoff，跳過（W4-002 計數）
                    stale_count += 1
                    continue

            handoffs.append(record.data)

        elif record.format == "markdown":
            # Markdown 格式：根據 ticket_id 檢查是否 completed
            if record.ticket_id and is_ticket_completed(record.ticket_id):
                stale_count += 1  # W4-002 計數
                continue  # 跳過 stale 條目

            handoffs.append(record.data)

    # W7-004：改為返回 namedtuple，取代函式屬性機制
    # 明確的返回值提高程式碼清晰度和類型安全性
    return HandoffListResult(
        handoffs=handoffs,
        stale_count=stale_count,
        schema_error_count=schema_error_count
    )


def load_handoff_file(ticket_id: str) -> Optional[Dict[str, Any]]:
    """
    載入特定的 handoff 檔案

    Args:
        ticket_id: Ticket ID

    Returns:
        Optional[Dict]: handoff 資料，或 None 如果不存在
    """
    file_info = _find_handoff_file(ticket_id, HANDOFF_PENDING_SUBDIR)
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
    file_info = _find_handoff_file(ticket_id, HANDOFF_PENDING_SUBDIR)
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
    file_info = _find_handoff_file(ticket_id, HANDOFF_PENDING_SUBDIR)
    if not file_info:
        return False

    file_path, _ = file_info
    archive_dir = _get_handoff_dir(HANDOFF_ARCHIVE_SUBDIR)
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
        direction = handoff.get("direction", "auto")
        print(f"  交接方向: {direction}")

        # Context refresh 額外說明
        if direction == "context-refresh":
            print(f"    （Context 刷新：在新 session 中以乾淨環境繼續此任務）")

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

    print(SEPARATOR_PRIMARY)
    print(f"[Resume] {ticket_id}")
    print(SEPARATOR_PRIMARY)
    print()

    _print_basic_info(handoff)
    _print_5w1h_info(handoff)
    _print_chain_info(handoff)
    _print_markdown_content(handoff)

    if ticket:
        _print_ticket_info(ticket)


def _execute_list() -> int:
    """執行 --list 子命令"""
    try:
        result = list_pending_handoffs()
    except HandoffDirectionUnknownError as e:
        # W9-001：安全網，正常情況不會觸發（未知 direction 已改為 per-file 處理）
        # 此 exception 保留供未來邊界情況使用
        print(f"[WARNING] 未預期的 direction 異常：{e}", file=sys.stderr)
        if e.guidance:
            print(f"  指引：{e.guidance}", file=sys.stderr)
        return 0

    # W7-004：從 namedtuple 提取 handoff 清單和 stale 計數
    handoffs = result.handoffs
    stale_count = result.stale_count
    if not handoffs:
        print(ResumeMessages.NO_PENDING_RESUMPTIONS)
        if stale_count > 0:
            print()
            print(f"[提示] 已過濾 {stale_count} 個 stale handoff（來源 ticket 已完成）")
            print(f"  執行 ticket handoff gc --dry-run 可查看詳細清單")
        return 0

    print(SEPARATOR_PRIMARY)
    print(SectionHeaders.PENDING_RESUME_LIST)
    print(SEPARATOR_PRIMARY)
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
    # W4-002: 顯示 stale 過濾計數（有結果時也提示是否有被過濾）
    if stale_count > 0:
        print(f"[提示] 另有 {stale_count} 個 stale handoff 已自動過濾（執行 ticket handoff gc --dry-run 查看）")
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


def _print_resume_checkpoint(ticket_id: str) -> None:
    """Resume 後標準化 Checkpoint 引導（接手流程路由）。"""
    print()
    print(SEPARATOR_PRIMARY)
    print(SectionHeaders.SUGGESTED_NEXT_STEP)
    print(SEPARATOR_PRIMARY)
    print()
    print(ResumeMessages.CHECKPOINT_HEADER)
    print(ResumeMessages.CHECKPOINT_SCOPE_VERIFY)
    print(ResumeMessages.CHECKPOINT_CLAIM_LABEL)
    print(format_msg(ResumeMessages.CHECKPOINT_CLAIM_CMD, ticket_id=ticket_id))
    print(ResumeMessages.CHECKPOINT_CHAIN_LABEL)
    print(format_msg(ResumeMessages.CHECKPOINT_CHAIN_CMD, ticket_id=ticket_id))
    print()


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
        # 檢查 Ticket 是否存在，以提供更準確的錯誤訊息
        ticket_exists = False
        try:
            # 從 ticket_id 提取版本並嘗試載入 Ticket
            version_from_id = extract_version_from_ticket_id(ticket_id)
            if version_from_id:
                ticket = load_ticket(version_from_id, ticket_id)
                ticket_exists = ticket is not None
        except Exception:
            pass

        # 根據 Ticket 是否存在顯示對應的錯誤訊息
        if ticket_exists:
            print(format_error(ErrorMessages.NO_HANDOFF_FILE, ticket_id=ticket_id))
        else:
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

    # 將 handoff 檔案從 pending/ 移動到 archive/
    # 注意：mark_handoff_as_resumed() 已自動歸檔 Markdown 格式，所以這裡只會歸檔 JSON
    if not archive_handoff_file(ticket_id):
        # 歸檔失敗不應該視為 resume 失敗（核心功能已完成），只發出警告
        print(format_warning(WarningMessages.INVALID_OPERATION))
        print(WarningMessages.HANDOFF_ARCHIVE_FAILED)

    print(SEPARATOR_PRIMARY)
    print(SectionHeaders.COMPLETION)
    print(InfoMessages.HANDOFF_RESUMED)
    print(SEPARATOR_PRIMARY)

    _print_resume_checkpoint(ticket_id)
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
