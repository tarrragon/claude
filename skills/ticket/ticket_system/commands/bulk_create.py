"""
批次建立 Ticket 命令模組

負責從模板 + 目標清單快速建立多個 Ticket。
支援 --template 載入預設值，--targets 指定目標清單。
"""

if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()


import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

from ticket_system.lib.ticket_builder import (
    TicketConfig,
    format_ticket_id,
    get_next_seq,
    create_ticket_frontmatter,
    create_ticket_body,
)
from ticket_system.lib.ticket_loader import (
    get_tickets_dir,
    get_ticket_path,
    save_ticket,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    WarningMessages,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_tracking_messages import (
    BulkCreateMessages,
)


@dataclass
class BulkCreateResult:
    """批次建立結果"""
    created: List[str] = field(default_factory=list)  # 成功建立的 Ticket ID
    warned: List[Tuple[str, str]] = field(default_factory=list)  # (ticket_id, 警告訊息)
    failed: List[Tuple[str, str]] = field(default_factory=list)  # (描述, 錯誤訊息)
    skipped: List[str] = field(default_factory=list)  # 跳過的 ID
    total: int = 0
    dry_run: bool = False




def _load_template(template_name: str) -> Dict[str, any]:
    """載入 YAML 模板。

    Args:
        template_name: 模板名稱

    Returns:
        模板字典

    Raises:
        FileNotFoundError: 模板不存在
    """
    template_dir = Path(__file__).parent.parent / "templates"
    template_file = template_dir / f"{template_name}.yaml"

    if not template_file.exists():
        raise FileNotFoundError(f"模板不存在: {template_file}")

    with open(template_file, "r", encoding="utf-8") as f:
        template = yaml.safe_load(f)

    return template.get("defaults", {})


def _parse_targets(targets_str: str) -> List[str]:
    """解析目標清單字串。

    Args:
        targets_str: 逗號分隔的目標清單

    Returns:
        目標清單
    """
    return [t.strip() for t in targets_str.split(",") if t.strip()]


def _create_ticket_config(
    template_defaults: Dict[str, any],
    target: str,
    ticket_id: str,
    version: str,
    wave: int,
    parent_id: Optional[str] = None,
) -> TicketConfig:
    """建立 TicketConfig（從模板預設值 + 目標）。

    Args:
        template_defaults: 模板預設值
        target: 目標名稱
        ticket_id: Ticket ID
        version: 版本號
        wave: Wave 編號
        parent_id: 父 Ticket ID

    Returns:
        TicketConfig
    """
    config: TicketConfig = {
        "ticket_id": ticket_id,
        "version": version,
        "wave": wave,
        "title": target,
        "ticket_type": template_defaults.get("type", "IMP"),
        "priority": template_defaults.get("priority", "P2"),
        "who": template_defaults.get("who", "pending"),
        "what": BulkCreateMessages.WHAT_TEMPLATE.format(target=target),
        "when": template_defaults.get("when", "待定義"),
        "where_layer": template_defaults.get("where_layer", "Presentation"),
        "where_files": [],
        "why": template_defaults.get("why", ""),
        "how_task_type": template_defaults.get("how_task_type", "Implementation"),
        "how_strategy": template_defaults.get("how_strategy", ""),
    }

    if parent_id:
        config["parent_id"] = parent_id

    return config


def execute(args: argparse.Namespace) -> int:
    """執行 batch-create 命令"""
    # 驗證版本
    version = args.version
    if not version:
        print(format_error(ErrorMessages.VERSION_NOT_DETECTED))
        return 1

    # 驗證 Wave
    wave = args.wave
    if not wave or wave < 1:
        print(format_error(BulkCreateMessages.WAVE_INVALID))
        return 1

    # 載入模板
    try:
        template_defaults = _load_template(args.template)
    except FileNotFoundError:
        print(format_error(BulkCreateMessages.TEMPLATE_NOT_FOUND, template=args.template))
        return 1

    # 解析目標清單
    targets = _parse_targets(args.targets)
    if not targets:
        print(format_error(BulkCreateMessages.TARGETS_EMPTY))
        return 1

    # 執行批次建立
    dry_run = args.dry_run if hasattr(args, "dry_run") else False
    parent_id = args.parent if hasattr(args, "parent") else None

    result = _create_batch_tickets(
        template_defaults,
        targets,
        version,
        wave,
        dry_run=dry_run,
        parent_id=parent_id,
    )

    # 顯示摘要
    _print_batch_summary(result, args.template, version, wave)

    # 顯示結果
    _print_batch_result(result)

    return 0 if result.failed == [] else 1


def _create_batch_tickets(
    template_defaults: Dict[str, any],
    targets: List[str],
    version: str,
    wave: int,
    dry_run: bool = False,
    parent_id: Optional[str] = None,
) -> BulkCreateResult:
    """建立批次 Tickets。

    Args:
        template_defaults: 模板預設值
        targets: 目標清單
        version: 版本號
        wave: Wave 編號
        dry_run: 預演模式
        parent_id: 父 Ticket ID

    Returns:
        BulkCreateResult
    """
    result = BulkCreateResult(total=len(targets), dry_run=dry_run)

    # 初始化 wave_seq_map
    wave_seq_map: Dict[int, int] = {}

    # 建立票目錄
    if not dry_run:
        tickets_dir = get_tickets_dir(version)
        tickets_dir.mkdir(parents=True, exist_ok=True)

    # 迴圈建立各 Ticket
    for i, target in enumerate(targets, 1):
        try:
            # 分配序號（使用 wave_seq_map 避免競態）
            if wave not in wave_seq_map:
                wave_seq_map[wave] = get_next_seq(version, wave)
            else:
                wave_seq_map[wave] += 1

            seq = wave_seq_map[wave]
            ticket_id = format_ticket_id(version, wave, seq)

            # 建立 TicketConfig
            config = _create_ticket_config(
                template_defaults,
                target,
                ticket_id,
                version,
                wave,
                parent_id=parent_id,
            )

            # 產生 frontmatter 和 body
            frontmatter = create_ticket_frontmatter(config)
            body = create_ticket_body(
                frontmatter.get("what", ""),
                frontmatter.get("who", {}).get("current", "pending"),
            )

            # 寫入檔案（除非是預演模式）
            if not dry_run:
                ticket_path = get_ticket_path(version, ticket_id)
                save_ticket(frontmatter, ticket_path)

            result.created.append(ticket_id)

        except Exception as e:
            result.failed.append((target, str(e)))

    return result


def _print_batch_summary(
    result: BulkCreateResult,
    template: str,
    version: str,
    wave: int,
) -> None:
    """顯示批次建立摘要"""
    print()
    print("=" * 60)
    print(format_info(BulkCreateMessages.BATCH_CREATE_SUMMARY_TITLE))
    print("=" * 60)
    print()
    print(f"{BulkCreateMessages.SUMMARY_TEMPLATE_PREFIX} {template}")
    print(f"{BulkCreateMessages.SUMMARY_VERSION_PREFIX} {version}")
    print(f"{BulkCreateMessages.SUMMARY_WAVE_PREFIX} {wave}")
    print(f"{BulkCreateMessages.SUMMARY_TOTAL_PREFIX} {result.total}")
    mode = BulkCreateMessages.SUMMARY_MODE_DRY_RUN if result.dry_run else BulkCreateMessages.SUMMARY_MODE_NORMAL
    print(f"{BulkCreateMessages.SUMMARY_MODE_PREFIX} {mode}")
    print()

    if result.created:
        print(BulkCreateMessages.TICKETS_LIST_TITLE)
        for i, ticket_id in enumerate(result.created, 1):
            print(BulkCreateMessages.TICKET_FORMAT.format(seq=i, id=ticket_id, title=""))
        print()


def _print_batch_result(result: BulkCreateResult) -> None:
    """顯示批次建立結果"""
    print("=" * 60)
    print(format_info(BulkCreateMessages.BATCH_CREATE_COMPLETE))
    print("=" * 60)
    print()
    print(
        BulkCreateMessages.RESULT_FORMAT.format(
            created=len(result.created),
            total=result.total,
            warned=len(result.warned),
            failed=len(result.failed),
        )
    )

    if result.failed:
        print()
        print(BulkCreateMessages.FAILED_ITEMS_TITLE)
        for desc, error in result.failed:
            print(f"  - {desc}: {error}")

    if result.warned:
        print()
        print(BulkCreateMessages.WARNED_ITEMS_TITLE)
        for ticket_id, warning in result.warned:
            print(f"  - {ticket_id}: {warning}")

    print()


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 batch-create 子命令"""
    parser = subparsers.add_parser(
        "batch-create",
        help=BulkCreateMessages.HELP_BATCH_CREATE,
    )

    parser.add_argument(
        "--template",
        required=True,
        help=BulkCreateMessages.ARG_TEMPLATE,
    )
    parser.add_argument(
        "--targets",
        required=True,
        help=BulkCreateMessages.ARG_TARGETS,
    )
    parser.add_argument(
        "--version",
        help=BulkCreateMessages.ARG_VERSION,
    )
    parser.add_argument(
        "--wave",
        type=int,
        help=BulkCreateMessages.ARG_WAVE,
    )
    parser.add_argument(
        "--parent",
        help=BulkCreateMessages.ARG_PARENT,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=BulkCreateMessages.ARG_DRY_RUN,
    )

    parser.set_defaults(func=execute)
