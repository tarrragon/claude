"""
Ticket 遷移命令模組

負責 Ticket ID 遷移功能，支援單一 Ticket 遷移和批量遷移。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
import json
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY
from ticket_system.lib.constants import WORK_LOGS_DIR, TICKETS_DIR
from ticket_system.lib.ticket_loader import (
    get_project_root,
    get_ticket_path,
    get_tickets_dir,
    load_ticket,
    save_ticket,
    resolve_version,
)
from ticket_system.lib.parser import parse_frontmatter
from ticket_system.lib.ticket_validator import validate_ticket_id
from ticket_system.lib.id_parser import (
    extract_id_components,
    parse_sequence,
    format_sequence,
    calculate_chain_info,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    MigrationMessages,
    WarningMessages,
    InfoMessages,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_tracking_messages import (
    MigrateMessages,
)
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
)


def _update_ticket_id_references(ticket: Dict[str, Any], old_id: str, new_id: str) -> None:
    """
    更新 Ticket 中所有對舊 ID 的引用

    Args:
        ticket: Ticket 資料
        old_id: 舊 Ticket ID
        new_id: 新 Ticket ID
    """
    # 更新 blockedBy 引用
    if "blockedBy" in ticket and ticket["blockedBy"]:
        ticket["blockedBy"] = [new_id if ref == old_id else ref for ref in ticket["blockedBy"]]

    # 更新 children 中的 ID
    if "children" in ticket and ticket["children"]:
        for child in ticket["children"]:
            if isinstance(child, dict) and "id" in child and child["id"] == old_id:
                child["id"] = new_id

    # 更新 source_ticket
    if "source_ticket" in ticket and ticket["source_ticket"] == old_id:
        ticket["source_ticket"] = new_id


def _update_cross_references(old_id: str, new_id: str) -> int:
    """
    搜尋所有 Ticket 文件並更新對舊 ID 的交叉引用

    掃描所有版本目錄下的 tickets 資料夾，查找並更新以下欄位中
    對舊 ID 的引用：
    - blockedBy: 阻塞依賴列表
    - relatedTo: 相關 Ticket 列表
    - children: 子 Ticket 列表（支援字串和 dict 形式）
    - source_ticket: 來源 Ticket
    - parent_id: 父 Ticket ID
    - spawned_tickets: 衍生 Ticket 列表

    Args:
        old_id: 舊 Ticket ID
        new_id: 新 Ticket ID

    Returns:
        int: 更新的檔案數量
    """
    updated_count = 0
    work_logs_root = get_project_root() / "docs" / "work-logs"

    # 掃描所有版本目錄下的 tickets 資料夾
    for tickets_dir in sorted(work_logs_root.glob("v*/tickets")):
        for ticket_file in sorted(tickets_dir.glob("*.md")):
            # 跳過剛遷移的 Ticket 本身及其子 Ticket
            if ticket_file.stem.startswith(new_id):
                continue

            # 載入 Ticket
            ticket = _load_ticket_from_path(ticket_file)
            if not ticket:
                continue

            # 檢查是否包含舊 ID 的引用
            updated = False

            # 更新 blockedBy
            if "blockedBy" in ticket and ticket.get("blockedBy"):
                if isinstance(ticket["blockedBy"], list):
                    for i, ref in enumerate(ticket["blockedBy"]):
                        if ref == old_id:
                            ticket["blockedBy"][i] = new_id
                            updated = True

            # 更新 relatedTo
            if "relatedTo" in ticket and ticket.get("relatedTo"):
                if isinstance(ticket["relatedTo"], list):
                    for i, ref in enumerate(ticket["relatedTo"]):
                        if ref == old_id:
                            ticket["relatedTo"][i] = new_id
                            updated = True

            # 更新 children（支援字串和 dict 形式）
            if "children" in ticket and ticket.get("children"):
                if isinstance(ticket["children"], list):
                    for i, child in enumerate(ticket["children"]):
                        if isinstance(child, str) and child == old_id:
                            ticket["children"][i] = new_id
                            updated = True
                        elif isinstance(child, dict) and child.get("id") == old_id:
                            child["id"] = new_id
                            updated = True

            # 更新 source_ticket
            if "source_ticket" in ticket and ticket.get("source_ticket") == old_id:
                ticket["source_ticket"] = new_id
                updated = True

            # 更新 parent_id
            if "parent_id" in ticket and ticket.get("parent_id") == old_id:
                ticket["parent_id"] = new_id
                updated = True

            # 更新 spawned_tickets
            if "spawned_tickets" in ticket and ticket.get("spawned_tickets"):
                if isinstance(ticket["spawned_tickets"], list):
                    for i, ref in enumerate(ticket["spawned_tickets"]):
                        if ref == old_id:
                            ticket["spawned_tickets"][i] = new_id
                            updated = True

            # 儲存修改
            if updated:
                try:
                    save_ticket(ticket, ticket_file)
                    updated_count += 1
                except (IOError, OSError) as e:
                    print(format_warning(
                        WarningMessages.FILE_UPDATE_FAILED,
                        path=str(ticket_file),
                        error=str(e)
                    ))

    return updated_count


def _load_ticket_from_path(ticket_path: Path) -> Optional[Dict[str, Any]]:
    """
    從檔案路徑載入 Ticket

    Args:
        ticket_path: Ticket 檔案路徑

    Returns:
        Dict: Ticket 資料，或 None 如果載入失敗
    """
    if not ticket_path.exists():
        return None

    try:
        with open(ticket_path, "r", encoding="utf-8") as f:
            content = f.read()
        # parse_frontmatter 返回 (frontmatter_dict, body_text)
        ticket, _ = parse_frontmatter(content)
        return ticket if ticket else None
    except Exception:
        # 捕獲所有異常，包括 YAMLParseError 和其他解析錯誤
        # 無法載入的檔案將被跳過，不影響整個遷移流程
        return None


def _backup_ticket(version: str, ticket_id: str) -> Optional[Path]:
    """
    備份 Ticket 檔案

    Args:
        version: 版本號
        ticket_id: Ticket ID

    Returns:
        Path: 備份檔案路徑，或 None 如果備份失敗
    """
    root = get_project_root()
    backup_dir = root / ".claude" / "migration-backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    original_path = get_ticket_path(version, ticket_id)
    if not original_path.exists():
        return None

    backup_path = backup_dir / original_path.name
    try:
        shutil.copy2(original_path, backup_path)
        return backup_path
    except (IOError, OSError) as e:
        print(format_warning(WarningMessages.BACKUP_FAILED, error=str(e)))
        return None


def _migrate_single_ticket(
    version: str,
    source_id: str,
    target_id: str,
    dry_run: bool = False,
    backup: bool = True,
) -> int:
    """
    遷移單一 Ticket

    Args:
        version: 版本號
        source_id: 來源 Ticket ID
        target_id: 目標 Ticket ID
        dry_run: 預覽模式
        backup: 是否備份

    Returns:
        int: exit code (0 成功, 1 失敗, 2 來源 Ticket 不存在)
    """
    # 驗證 ID 格式
    if not validate_ticket_id(source_id) or not validate_ticket_id(target_id):
        print(MigrateMessages.INVALID_TICKET_ID_FORMAT)
        return 1

    # 從 source_id 提取版本號，支援跨版本遷移
    source_components = extract_id_components(source_id)
    source_version = source_components["version"] if source_components else version

    # 載入來源 Ticket
    ticket, error = load_and_validate_ticket(source_version, source_id)
    if error:
        return 2

    # 預覽模式
    if dry_run:
        print(format_info(MigrateMessages.DRY_RUN_HEADER, source_id=source_id, target_id=target_id))
        print(f"{MigrateMessages.DRY_RUN_TITLE_PREFIX} {ticket.get('title', 'N/A')}")
        print(f"{MigrateMessages.DRY_RUN_STATUS_PREFIX} {ticket.get('status', 'N/A')}")
        return 0

    # 執行備份
    backup_path = None
    if backup:
        backup_path = _backup_ticket(source_version, source_id)
        if backup_path:
            print(format_info(InfoMessages.FILE_BACKED_UP, path=str(backup_path)))
        else:
            print(format_warning(WarningMessages.BACKUP_SKIPPED))

    # 更新 Ticket 資料
    old_id = ticket.get("id")
    ticket["id"] = target_id

    # 更新 wave
    components = extract_id_components(target_id)
    if components:
        ticket["version"] = components["version"]
        ticket["wave"] = components["wave"]

        # 更新 chain 資訊
        chain_info = calculate_chain_info(target_id)
        if chain_info:
            ticket["chain"] = chain_info

        # 更新 parent_id
        if chain_info.get("parent"):
            ticket["parent_id"] = chain_info["parent"]

    # 更新所有引用
    _update_ticket_id_references(ticket, old_id, target_id)

    # 取得原始檔案路徑
    source_path = get_ticket_path(source_version, source_id)

    # 提取目標版本（從目標 ID 中）以支援跨版本遷移
    target_components = extract_id_components(target_id)
    target_version = target_components["version"] if target_components else version
    target_path = get_ticket_path(target_version, target_id)

    # 確保目錄存在
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # 儲存到新位置
        save_ticket(ticket, target_path)
        print(format_info(InfoMessages.TICKET_MIGRATED, source_id=source_id, target_id=target_id))

        # 刪除舊檔案
        if source_path != target_path and source_path.exists():
            source_path.unlink()
            print(format_info(InfoMessages.FILE_DELETED, path=str(source_path)))

        # 更新其他 Ticket 中的交叉引用
        cross_ref_count = _update_cross_references(old_id, target_id)
        if cross_ref_count > 0:
            print(format_info(MigrateMessages.CROSS_REFERENCES_UPDATED, count=cross_ref_count))

        return 0

    except (IOError, OSError) as e:
        print(format_error(ErrorMessages.FILE_CREATION_FAILED, error=str(e)))
        if backup_path:
            print(format_info(MigrationMessages.BACKUP_LOCATION, path=str(backup_path)))
        return 1


def _load_migration_config(config_file: str) -> Optional[List[Dict[str, str]]]:
    """
    載入遷移配置檔案

    Args:
        config_file: 配置檔案路徑

    Returns:
        List[Dict]: 遷移清單，或 None 如果載入失敗
    """
    config_path = Path(config_file)

    if not config_path.exists():
        print(f"{MigrateMessages.CONFIG_FILE_NOT_FOUND} {config_file}")
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            if config_file.endswith(".yaml") or config_file.endswith(".yml"):
                data = yaml.safe_load(f)
            elif config_file.endswith(".json"):
                data = json.load(f)
            else:
                print(MigrateMessages.CONFIG_FORMAT_NOT_SUPPORTED)
                return None

        if not isinstance(data, dict) or "migrations" not in data:
            print(MigrateMessages.CONFIG_FORMAT_INVALID)
            return None

        migrations = data["migrations"]
        if not isinstance(migrations, list):
            print(MigrateMessages.MIGRATIONS_FIELD_NOT_LIST)
            return None

        return migrations

    except (IOError, OSError, yaml.YAMLError, json.JSONDecodeError) as e:
        print(f"{MigrateMessages.CONFIG_LOAD_FAILED} {e}")
        return None


def _batch_migrate(
    version: str,
    config_file: str,
    dry_run: bool = False,
    backup: bool = True,
) -> int:
    """
    批量遷移 Tickets

    Args:
        version: 版本號
        config_file: 配置檔案路徑
        dry_run: 預覽模式
        backup: 是否備份

    Returns:
        int: exit code (0 全部成功, 1 部分失敗, 2 全部失敗)
    """
    migrations = _load_migration_config(config_file)
    if not migrations:
        return 1

    print(format_info(MigrationMessages.LOAD_MIGRATIONS, count=len(migrations)))

    success_count = 0
    fail_count = 0
    skip_count = 0

    for migration in migrations:
        if not isinstance(migration, dict):
            print(format_warning(WarningMessages.INVALID_MIGRATION_ITEM))
            skip_count += 1
            continue

        source_id = migration.get("from")
        target_id = migration.get("to")

        if not source_id or not target_id:
            print(format_warning(WarningMessages.MIGRATION_ITEM_INCOMPLETE))
            skip_count += 1
            continue

        print()
        result = _migrate_single_ticket(version, source_id, target_id, dry_run, backup)

        if result == 0:
            success_count += 1
        elif result == 2:
            skip_count += 1
        else:
            fail_count += 1

    # 輸出摘要
    print()
    print(SEPARATOR_PRIMARY)
    print(format_info(MigrateMessages.MIGRATION_SUMMARY))
    print(format_info(MigrationMessages.SUCCESS_COUNT, count=success_count))
    print(format_info(MigrationMessages.FAIL_COUNT, count=fail_count))
    print(format_info(MigrationMessages.SKIP_COUNT, count=skip_count))
    print(SEPARATOR_PRIMARY)

    if fail_count > 0:
        return 1 if success_count > 0 else 2
    return 0


def execute(args: argparse.Namespace) -> int:
    """執行 migrate 命令"""
    # 使用共用 API 解析版本（自動標準化移除 v 前綴）
    version = resolve_version(getattr(args, "version", None))
    if not version:
        print(format_error(ErrorMessages.VERSION_NOT_DETECTED))
        return 1

    # 檢查是否為批量遷移
    if getattr(args, "config", None):
        dry_run = getattr(args, "dry_run", False)
        backup = not getattr(args, "no_backup", False)
        return _batch_migrate(version, args.config, dry_run, backup)

    # 單一 Ticket 遷移
    source_id = getattr(args, "source_id", None)
    target_id = getattr(args, "target_id", None)

    if not source_id or not target_id:
        print(format_error(ErrorMessages.MISSING_PARAMETERS))
        return 1

    dry_run = getattr(args, "dry_run", False)
    backup = not getattr(args, "no_backup", False)

    return _migrate_single_ticket(version, source_id, target_id, dry_run, backup)


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 migrate 子命令"""
    parser = subparsers.add_parser(
        "migrate",
        help=MigrateMessages.HELP_MIGRATE
    )

    # 位置參數（用於單一遷移）
    parser.add_argument(
        "source_id",
        nargs="?",
        help=MigrateMessages.ARG_SOURCE_ID
    )
    parser.add_argument(
        "target_id",
        nargs="?",
        help=MigrateMessages.ARG_TARGET_ID
    )

    # 選項
    parser.add_argument(
        "--config",
        metavar="FILE",
        help=MigrateMessages.ARG_CONFIG
    )
    parser.add_argument(
        "--version",
        help=MigrateMessages.ARG_VERSION
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=MigrateMessages.ARG_DRY_RUN
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help=MigrateMessages.ARG_BACKUP
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help=MigrateMessages.ARG_NO_BACKUP
    )

    parser.set_defaults(func=execute)


