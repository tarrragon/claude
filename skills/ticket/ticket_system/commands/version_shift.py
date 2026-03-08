"""
版本遷移命令模組

負責將整個版本的 Ticket 遷移至新版本號，包括目錄重命名、ID 更新、交叉引用修正等。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()


import argparse
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from ticket_system.lib.ticket_loader import (
    get_project_root,
    load_ticket,
    save_ticket,
)
from ticket_system.lib.constants import WORK_LOGS_DIR, TICKETS_DIR
from ticket_system.lib.parser import parse_frontmatter
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    WarningMessages,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_tracking_messages import (
    VersionShiftMessages,
)
from ticket_system.lib.version import normalize_version


def _validate_versions(
    from_version: str,
    to_version: str,
    project_root: Path
) -> Tuple[bool, str]:
    """
    驗證版本號有效性和存在狀態。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄

    Returns:
        (是否有效, 訊息或特殊狀態碼)
    """
    # 標準化版本號
    from_version = normalize_version(from_version)
    to_version = normalize_version(to_version)

    # 驗證格式（N.N.N）
    version_pattern = r"^\d+\.\d+\.\d+$"
    if not re.match(version_pattern, from_version):
        return (False, VersionShiftMessages.ERROR_INVALID_VERSION_FORMAT.format(version=from_version))

    if not re.match(version_pattern, to_version):
        return (False, VersionShiftMessages.ERROR_INVALID_VERSION_FORMAT.format(version=to_version))

    # 驗證不相同
    if from_version == to_version:
        return (True, "SAME_VERSION")

    # 驗證 from_version 存在
    from_dir = project_root / WORK_LOGS_DIR / f"v{from_version}"
    if not from_dir.exists():
        return (False, VersionShiftMessages.ERROR_FROM_VERSION_NOT_EXISTS.format(version=from_version))

    # 驗證 to_version 不存在
    to_dir = project_root / WORK_LOGS_DIR / f"v{to_version}"
    if to_dir.exists():
        return (False, VersionShiftMessages.ERROR_TO_VERSION_EXISTS.format(version=to_version))

    return (True, "OK")


def _backup_version_dir(from_version: str, project_root: Path) -> Tuple[bool, Optional[Path]]:
    """
    備份整個 worklog 目錄至 .claude/migration-backups/{timestamp}/。

    Args:
        from_version: 來源版本號
        project_root: 專案根目錄

    Returns:
        (成功, 備份路徑)
    """
    # 準備備份路徑
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_base = project_root / ".claude" / "migration-backups" / timestamp
    backup_base.mkdir(parents=True, exist_ok=True)

    source_dir = project_root / WORK_LOGS_DIR / f"v{from_version}"
    backup_dest = backup_base / f"v{from_version}"

    try:
        shutil.copytree(source_dir, backup_dest, dirs_exist_ok=False)
        return (True, backup_dest)
    except (IOError, OSError) as e:
        print(format_warning(f"備份失敗: {str(e)}"))
        return (False, None)


def _shift_version_in_references(ticket: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
    """
    更新 Ticket 中所有 from_version 前綴的引用。

    Args:
        ticket: Ticket 資料字典
        from_version: 來源版本號
        to_version: 目標版本號

    Returns:
        更新後的 Ticket 字典
    """
    version_prefix_old = f"{from_version}-"
    version_prefix_new = f"{to_version}-"

    # 需要更新的欄位
    fields_to_update = [
        "blockedBy",
        "parent_id",
        "children",
        "relatedTo",
        "spawned_tickets",
        "source_ticket",
    ]

    for field_name in fields_to_update:
        if field_name not in ticket or not ticket[field_name]:
            continue

        value = ticket[field_name]

        # 列表型欄位
        if isinstance(value, list):
            for i, element in enumerate(value):
                if isinstance(element, str) and element.startswith(version_prefix_old):
                    value[i] = version_prefix_new + element[len(version_prefix_old):]
                elif isinstance(element, dict) and "id" in element:
                    if element["id"].startswith(version_prefix_old):
                        element["id"] = version_prefix_new + element["id"][len(version_prefix_old):]

        # 字串型欄位
        elif isinstance(value, str) and value.startswith(version_prefix_old):
            ticket[field_name] = version_prefix_new + value[len(version_prefix_old):]

    # 特殊處理 chain 結構（巢狀 dict）
    if "chain" in ticket and isinstance(ticket["chain"], dict):
        chain = ticket["chain"]
        for chain_field in ["root", "parent"]:
            if chain_field in chain and isinstance(chain[chain_field], str):
                if chain[chain_field].startswith(version_prefix_old):
                    chain[chain_field] = version_prefix_new + chain[chain_field][len(version_prefix_old):]

    return ticket


def _shift_single_ticket(
    ticket_path: Path,
    from_version: str,
    to_version: str
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    更新單一 Ticket 的所有版本欄位和內部引用。

    Args:
        ticket_path: Ticket 檔案路徑
        from_version: 來源版本號
        to_version: 目標版本號

    Returns:
        (成功, 更新後的 Ticket 字典)
    """
    try:
        # 從檔案路徑解析 ticket_id
        ticket_id = ticket_path.stem
        ticket = load_ticket(from_version, ticket_id)
        if ticket is None:
            return (False, None)

        # 提取舊 ID 並驗證
        old_id = ticket.get("id")
        if not old_id:
            return (False, None)

        # 解析 ID 元件
        match = re.match(r"^(\d+\.\d+\.\d+)-W(\d+)-(.+)$", old_id)
        if not match:
            return (False, None)

        wave = match.group(2)
        sequence = match.group(3)

        # 更新 ID 和 version 欄位
        new_id = f"{to_version}-W{wave}-{sequence}"
        ticket["id"] = new_id
        ticket["version"] = to_version

        # 更新內部交叉引用
        ticket = _shift_version_in_references(ticket, from_version, to_version)

        # 保存更新（save_ticket 接受 Path）
        save_ticket(ticket, ticket_path)
        return (True, ticket)

    except Exception as e:
        return (False, None)


def _shift_ticket_files(
    from_version: str,
    to_version: str,
    project_root: Path
) -> Tuple[int, List[str]]:
    """
    遍歷所有 Ticket，更新版本欄位。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄

    Returns:
        (更新計數, 跳過的檔案清單)
    """
    tickets_dir = project_root / WORK_LOGS_DIR / f"v{from_version}" / TICKETS_DIR

    if not tickets_dir.exists():
        return (0, [])

    update_count = 0
    skipped_files = []

    # 遍歷所有 .md 檔案
    for ticket_file in sorted(tickets_dir.glob("*.md")):
        success, _ = _shift_single_ticket(ticket_file, from_version, to_version)
        if success:
            update_count += 1
        else:
            skipped_files.append(ticket_file.name)

    return (update_count, skipped_files)


def _find_auxiliary_files(from_version: str, project_root: Path) -> List[Path]:
    """
    識別附屬檔案（以 Ticket ID 開頭但非主 Ticket 的 .md 檔）。

    Args:
        from_version: 來源版本號
        project_root: 專案根目錄

    Returns:
        附屬檔案路徑清單
    """
    tickets_dir = project_root / WORK_LOGS_DIR / f"v{from_version}" / TICKETS_DIR

    if not tickets_dir.exists():
        return []

    # 列出所有主 Ticket 的 ID（無後綴）
    main_ticket_ids = set()
    for filename in tickets_dir.glob("*.md"):
        match = re.match(r"^(\d+\.\d+\.\d+)-W(\d+)-([0-9.]+)\.md$", filename.name)
        if match and match.group(1) == from_version:
            main_ticket_ids.add(f"{match.group(1)}-W{match.group(2)}-{match.group(3)}")

    # 找出附屬檔案
    auxiliary_files = []
    for filename in tickets_dir.glob("*.md"):
        match = re.match(r"^(\d+\.\d+\.\d+)-W(\d+)-([0-9.]+)-(.+)\.md$", filename.name)
        if match and match.group(1) == from_version:
            prefix_id = f"{match.group(1)}-W{match.group(2)}-{match.group(3)}"
            if prefix_id in main_ticket_ids:
                auxiliary_files.append(filename)

    return auxiliary_files


def _rename_ticket_files_in_dir(
    from_version: str,
    to_version: str,
    project_root: Path
) -> int:
    """
    重新命名 tickets 目錄中的所有 .md 檔案。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄

    Returns:
        重命名的檔案數量
    """
    tickets_dir = project_root / WORK_LOGS_DIR / f"v{from_version}" / TICKETS_DIR

    if not tickets_dir.exists():
        return 0

    rename_count = 0
    old_prefix = f"{from_version}-"
    new_prefix = f"{to_version}-"

    for ticket_file in sorted(tickets_dir.glob("*.md")):
        if old_prefix in ticket_file.name:
            new_filename = ticket_file.name.replace(old_prefix, new_prefix)
            new_path = tickets_dir / new_filename

            try:
                ticket_file.rename(new_path)
                rename_count += 1
            except Exception as e:
                print(format_warning(f"重命名失敗 {ticket_file.name}: {str(e)}"))

    return rename_count


def _process_ticket_for_cross_refs(
    ticket_file: Path,
    version_name_str: str,
    from_version: str,
    to_version: str,
    old_prefix: str,
) -> bool:
    """
    檢查並更新單一 Ticket 的跨版本引用。

    Args:
        ticket_file: Ticket 檔案路徑
        version_name_str: 版本號（無 v 前綴）
        from_version: 來源版本號
        to_version: 目標版本號
        old_prefix: 舊版本前綴

    Returns:
        是否更新成功
    """
    try:
        ticket_id = ticket_file.stem
        ticket = load_ticket(version_name_str, ticket_id)
        if ticket is None:
            return False

        # 檢查是否包含舊版本的引用
        fields_to_check = ["blockedBy", "relatedTo", "children", "parent_id", "spawned_tickets", "source_ticket"]

        contains_old_ref = False
        for field_name in fields_to_check:
            if field_name not in ticket:
                continue

            field_value = ticket[field_name]
            if isinstance(field_value, str) and old_prefix in field_value:
                contains_old_ref = True
                break
            elif isinstance(field_value, list) and old_prefix in str(field_value):
                contains_old_ref = True
                break

        if contains_old_ref:
            ticket = _shift_version_in_references(ticket, from_version, to_version)
            save_ticket(ticket, ticket_file)
            return True

        return False

    except Exception:
        return False


def _update_cross_version_refs(
    from_version: str,
    to_version: str,
    project_root: Path
) -> int:
    """
    掃描其他版本的 Ticket，更新對 from_version 的引用。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄

    Returns:
        更新的檔案數量
    """
    work_logs_root = project_root / WORK_LOGS_DIR
    updated_count = 0
    old_prefix = f"{from_version}-"

    if not work_logs_root.exists():
        return 0

    # 遍歷所有版本目錄
    for version_dir in sorted(work_logs_root.glob("v*")):
        version_name = version_dir.name
        if version_name in (f"v{from_version}", f"v{to_version}"):
            continue  # 跳過已處理的版本

        tickets_dir = version_dir / "tickets"
        if not tickets_dir.exists():
            continue

        # 遍歷該版本的所有 Ticket
        version_name_str = version_name.lstrip("v")
        for ticket_file in sorted(tickets_dir.glob("*.md")):
            if _process_ticket_for_cross_refs(
                ticket_file, version_name_str, from_version, to_version, old_prefix
            ):
                updated_count += 1

    return updated_count


def _rename_worklog_dir(from_version: str, to_version: str, project_root: Path) -> bool:
    """
    重命名整個 worklog 目錄。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄

    Returns:
        是否成功
    """
    from_dir = project_root / WORK_LOGS_DIR / f"v{from_version}"
    to_dir = project_root / WORK_LOGS_DIR / f"v{to_version}"

    try:
        from_dir.rename(to_dir)
        return True
    except Exception:
        return False


def _update_version_field(todolist: Dict[str, Any], from_version: str, to_version: str) -> int:
    """
    更新 todolist.yaml 中的版本欄位（current_version, previous_version）。

    Args:
        todolist: todolist 資料字典
        from_version: 來源版本號
        to_version: 目標版本號

    Returns:
        更新計數
    """
    count = 0
    if todolist.get("current_version") == from_version:
        todolist["current_version"] = to_version
        count += 1

    if todolist.get("previous_version") == from_version:
        todolist["previous_version"] = to_version
        count += 1

    return count


def _update_tech_debt_items(todolist: Dict[str, Any], from_version: str, to_version: str) -> int:
    """
    更新 todolist.yaml 中的技術債務陣列。

    Args:
        todolist: todolist 資料字典
        from_version: 來源版本號
        to_version: 目標版本號

    Returns:
        更新計數
    """
    count = 0
    if "tech_debt" not in todolist or not isinstance(todolist["tech_debt"], list):
        return count

    for item in todolist["tech_debt"]:
        if not isinstance(item, dict):
            continue

        # source_version 有 v 前綴
        if item.get("source_version") == f"v{from_version}":
            item["source_version"] = f"v{to_version}"
            count += 1

        # source_ticket 無 v 前綴
        source_ticket = item.get("source_ticket", "")
        if isinstance(source_ticket, str) and source_ticket.startswith(f"{from_version}-"):
            item["source_ticket"] = f"{to_version}-" + source_ticket[len(f"{from_version}-"):]
            count += 1

    return count


def _update_todolist_yaml(from_version: str, to_version: str, project_root: Path) -> int:
    """
    更新 todolist.yaml 中與版本相關的欄位。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄

    Returns:
        更新的欄位數量
    """
    todolist_path = project_root / "docs" / "todolist.yaml"

    if not todolist_path.exists():
        return 0

    try:
        with open(todolist_path, "r", encoding="utf-8") as f:
            todolist = yaml.safe_load(f)
    except Exception:
        return 0

    if not todolist or not isinstance(todolist, dict):
        return 0

    # 更新版本欄位和技術債務
    count = _update_version_field(todolist, from_version, to_version)
    count += _update_tech_debt_items(todolist, from_version, to_version)

    # 保存更新
    try:
        with open(todolist_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(todolist, f, allow_unicode=True, default_flow_style=False)
        return count
    except Exception:
        return 0


def _generate_dry_run_preview(
    from_version: str,
    to_version: str,
    project_root: Path
) -> str:
    """
    生成 dry-run 預覽輸出。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄

    Returns:
        預覽輸出字串
    """
    lines = []
    lines.append(VersionShiftMessages.DRY_RUN_HEADER)
    lines.append("")
    lines.append(VersionShiftMessages.DRY_RUN_PLAN_TITLE)
    lines.append(VersionShiftMessages.DRY_RUN_FROM.format(version=from_version))
    lines.append(VersionShiftMessages.DRY_RUN_TO.format(version=to_version))
    lines.append("")

    # 掃描 Ticket 和附屬檔案
    tickets_dir = project_root / WORK_LOGS_DIR / f"v{from_version}" / TICKETS_DIR
    if tickets_dir.exists():
        main_tickets = []
        auxiliary_files = []

        for filename in sorted(tickets_dir.glob("*.md")):
            match = re.match(r"^(\d+\.\d+\.\d+)-W(\d+)-([0-9.]+)\.md$", filename.name)
            if match and match.group(1) == from_version:
                main_tickets.append(filename.name)
            elif f"{from_version}-W" in filename.name:
                auxiliary_files.append(filename.name)

        # 顯示 Ticket 預覽
        lines.append(VersionShiftMessages.DRY_RUN_TICKETS_PREVIEW.format(count=len(main_tickets)))
        for i, filename in enumerate(main_tickets[:10]):
            new_filename = filename.replace(from_version, to_version)
            lines.append(f"  {filename} → {new_filename}")

        if len(main_tickets) > 10:
            lines.append(VersionShiftMessages.DRY_RUN_PREVIEW_ELLIPSIS.format(count=len(main_tickets) - 10))

        lines.append("")

        # 顯示附屬檔案
        if auxiliary_files:
            lines.append(VersionShiftMessages.DRY_RUN_AUXILIARY_PREVIEW)
            for filename in auxiliary_files:
                new_filename = filename.replace(from_version, to_version)
                lines.append(f"  {filename} → {new_filename}")
            lines.append("")

    lines.append(VersionShiftMessages.DRY_RUN_DIRECTORY_OPERATION)
    lines.append(f"  docs/work-logs/v{from_version}/ → docs/work-logs/v{to_version}/")
    lines.append("")
    lines.append(VersionShiftMessages.DRY_RUN_TODOLIST_PREVIEW)
    lines.append(f"  current_version: {from_version} → {to_version}")
    lines.append("  (...)（共 N 個欄位）")
    lines.append("")
    lines.append(VersionShiftMessages.DRY_RUN_BACKUP)
    lines.append("")
    lines.append(VersionShiftMessages.DRY_RUN_FOOTER)

    return "\n".join(lines)


def _execute_processing_steps(
    from_version: str,
    to_version: str,
    project_root: Path,
) -> Dict[str, int]:
    """
    執行版本遷移的處理步驟（Ticket 更新、檔案重命名、交叉引用更新）。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄

    Returns:
        計數字典（tickets, auxiliary, cross_refs）
    """
    # [Step 2] 更新 Ticket 版本欄位
    print(VersionShiftMessages.STEP_UPDATE_TICKETS)
    ticket_count, skipped = _shift_ticket_files(from_version, to_version, project_root)
    print(VersionShiftMessages.TICKETS_UPDATED.format(count=ticket_count))

    # [Step 3] 重新命名 Ticket 檔案
    print(VersionShiftMessages.STEP_RENAME_TICKETS)
    _rename_ticket_files_in_dir(from_version, to_version, project_root)
    auxiliary_files_list = _find_auxiliary_files(from_version, project_root)
    auxiliary_count = len(auxiliary_files_list)
    print(VersionShiftMessages.AUXILIARY_FILES_UPDATED.format(count=auxiliary_count))

    # [Step 4] 更新跨版本交叉引用
    print(VersionShiftMessages.STEP_CROSS_REFS)
    cross_ref_count = _update_cross_version_refs(from_version, to_version, project_root)
    print(VersionShiftMessages.CROSS_REFS_UPDATED.format(count=cross_ref_count))

    return {
        "tickets": ticket_count,
        "auxiliary": auxiliary_count,
        "cross_refs": cross_ref_count,
        "skipped": len(skipped),
    }


def _execute_finalization_steps(
    from_version: str,
    to_version: str,
    project_root: Path,
    skip_todolist: bool,
) -> int:
    """
    執行版本遷移的最後步驟（目錄重命名、todolist 更新）。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        project_root: 專案根目錄
        skip_todolist: 是否跳過 todolist 更新

    Returns:
        todolist 更新計數
    """
    # [Step 5] 重新命名 worklog 目錄
    print(VersionShiftMessages.STEP_RENAME_DIR)
    success = _rename_worklog_dir(from_version, to_version, project_root)
    if not success:
        print(format_error("目錄重命名失敗"))
        raise RuntimeError("目錄重命名失敗")
    print(VersionShiftMessages.DIRECTORY_RENAMED.format(from_version=from_version, to_version=to_version))

    # [Step 6] 更新 todolist.yaml
    print(VersionShiftMessages.STEP_UPDATE_TODOLIST)
    todolist_count = 0
    if not skip_todolist:
        todolist_count = _update_todolist_yaml(from_version, to_version, project_root)
        print(VersionShiftMessages.TODOLIST_FIELDS_UPDATED.format(count=todolist_count))
    else:
        print("跳過 todolist.yaml 更新")

    return todolist_count


def _generate_summary(
    from_version: str,
    to_version: str,
    backup_path: Optional[Path],
    counts: Dict[str, int]
) -> str:
    """
    生成執行完成摘要。

    Args:
        from_version: 來源版本號
        to_version: 目標版本號
        backup_path: 備份路徑
        counts: 計數字典

    Returns:
        摘要字串
    """
    lines = []
    lines.append(VersionShiftMessages.SUMMARY_TITLE)
    lines.append(VersionShiftMessages.SUMMARY_FROM_VERSION.format(version=from_version))
    lines.append(VersionShiftMessages.SUMMARY_TO_VERSION.format(version=to_version))
    if backup_path:
        lines.append(VersionShiftMessages.SUMMARY_BACKUP_LOCATION.format(path=str(backup_path)))
    lines.append("")
    lines.append(VersionShiftMessages.SUMMARY_RESULTS)
    lines.append(VersionShiftMessages.SUMMARY_TICKETS_UPDATED.format(count=counts.get("tickets", 0)))
    lines.append(VersionShiftMessages.SUMMARY_AUXILIARY_UPDATED.format(count=counts.get("auxiliary", 0)))
    lines.append(VersionShiftMessages.SUMMARY_CROSS_REFS_UPDATED.format(count=counts.get("cross_refs", 0)))
    lines.append(VersionShiftMessages.SUMMARY_TODOLIST_UPDATED.format(count=counts.get("todolist", 0)))
    if counts.get("skipped", 0) > 0:
        lines.append(VersionShiftMessages.SUMMARY_FILES_SKIPPED.format(count=counts["skipped"]))
    lines.append("")
    lines.append(VersionShiftMessages.SUMMARY_DIR_OPERATION)
    lines.append(f"  docs/work-logs/v{from_version}/ → docs/work-logs/v{to_version}/")
    lines.append("")
    lines.append(VersionShiftMessages.SUMMARY_SEPARATOR)

    return "\n".join(lines)


def execute(args: argparse.Namespace) -> int:
    """
    執行 version-shift 命令。

    Args:
        args: 命令列參數

    Returns:
        終止碼（0 成功，1 失敗）
    """
    project_root = get_project_root()
    if project_root is None:
        print(format_error(ErrorMessages.PROJECT_ROOT_NOT_FOUND))
        return 1

    # 提取參數
    from_version = normalize_version(args.from_version)
    to_version = normalize_version(args.to_version)
    dry_run = args.dry_run
    no_backup = args.no_backup
    skip_todolist = args.skip_todolist

    # [Step 0] 前置驗證
    print(VersionShiftMessages.STEP_VALIDATE)
    valid, msg = _validate_versions(from_version, to_version, project_root)

    if msg == "SAME_VERSION":
        print(format_info(VersionShiftMessages.INFO_SAME_VERSION.format(version=from_version)))
        return 0

    if not valid:
        print(format_error(msg))
        return 1

    # Dry-run 模式
    if dry_run:
        preview = _generate_dry_run_preview(from_version, to_version, project_root)
        print(preview)
        return 0

    # [Step 1] 備份
    print(VersionShiftMessages.STEP_BACKUP)
    backup_path = None
    if not no_backup:
        success, backup_path = _backup_version_dir(from_version, project_root)
        if not success:
            print(format_error(VersionShiftMessages.ERROR_BACKUP_FAILED.format(error="I/O error")))
            return 1
        print(VersionShiftMessages.BACKUP_SUCCESS.format(path=str(backup_path)))
    else:
        print(VersionShiftMessages.BACKUP_SKIP)

    try:
        # 執行處理步驟
        counts = _execute_processing_steps(from_version, to_version, project_root)

        # 執行最後步驟
        todolist_count = _execute_finalization_steps(
            from_version, to_version, project_root, skip_todolist
        )
        counts["todolist"] = todolist_count

        # [Step 7] 輸出摘要
        print(VersionShiftMessages.STEP_SUMMARY)
        summary = _generate_summary(from_version, to_version, backup_path, counts)
        print(summary)

        return 0

    except RuntimeError as e:
        return 1


def register(subparsers: argparse._SubParsersAction) -> None:
    """
    註冊 version-shift 子命令到 argparse。

    Args:
        subparsers: argparse subparsers 物件
    """
    parser = subparsers.add_parser(
        "version-shift",
        help=VersionShiftMessages.HELP_VERSION_SHIFT
    )

    # 位置參數
    parser.add_argument(
        "from_version",
        help=VersionShiftMessages.ARG_FROM_VERSION
    )
    parser.add_argument(
        "to_version",
        help=VersionShiftMessages.ARG_TO_VERSION
    )

    # 選項
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=VersionShiftMessages.ARG_DRY_RUN
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help=VersionShiftMessages.ARG_NO_BACKUP
    )
    parser.add_argument(
        "--skip-todolist",
        action="store_true",
        help=VersionShiftMessages.ARG_SKIP_TODOLIST
    )

    parser.set_defaults(func=execute)
