"""
Ticket generate 命令模組

負責將 Plan 檔案轉換為 Atomic Tickets。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()


import argparse
from pathlib import Path
from typing import Optional

from ticket_system.lib.plan_parser import parse_plan
from ticket_system.lib.ticket_generator import generate, GeneratedTicket
from ticket_system.lib.ticket_loader import get_tickets_dir, save_ticket, get_ticket_path
from ticket_system.lib.messages import (
    ErrorMessages,
    WarningMessages,
    InfoMessages,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_tracking_messages import (
    GenerateMessages,
)
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY


def execute(args: argparse.Namespace) -> int:
    """執行 generate 命令"""
    # 驗證 Plan 檔案路徑
    plan_file = Path(args.plan_file)
    if not plan_file.exists():
        print(format_error(ErrorMessages.FILE_NOT_FOUND, path=str(plan_file)))
        return 1

    # 驗證版本
    version = args.version
    if not version:
        print(format_error(ErrorMessages.VERSION_NOT_DETECTED))
        return 1

    # 驗證 Wave
    wave = args.wave
    if not wave or wave < 1:
        print(format_error(ErrorMessages.MISSING_WAVE_PARAMETER))
        return 1

    # 解析 Plan 檔案
    parse_result = parse_plan(plan_file)
    if not parse_result.success:
        print(
            format_error(
                ErrorMessages.FILE_NOT_FOUND,
                path=f"{GenerateMessages.PLAN_PARSE_FAILED} {parse_result.error_message}",
            )
        )
        return 1

    # 生成 Tickets
    dry_run = args.dry_run if hasattr(args, "dry_run") else False
    gen_result = generate(parse_result, version, wave, dry_run=dry_run)

    if not gen_result.success:
        print(format_error(ErrorMessages.FILE_CREATION_FAILED, error=gen_result.error_message))
        return 1

    # 顯示生成摘要
    _print_generation_summary(gen_result, plan_file)

    # 若非預演模式，保存 Tickets
    if not dry_run:
        saved_count = _save_tickets(gen_result, version)
        print()
        print(format_info(GenerateMessages.TICKETS_SAVED_FORMAT, saved=saved_count, total=gen_result.total))

    return 0


def _print_generation_summary(gen_result, plan_file: Path) -> None:
    """顯示生成摘要。

    Args:
        gen_result: GenerationResult 物件
        plan_file: Plan 檔案路徑
    """
    print()
    print(SEPARATOR_PRIMARY)
    print(format_info(GenerateMessages.GENERATION_SUMMARY_TITLE))
    print(SEPARATOR_PRIMARY)
    print()
    print(f"{GenerateMessages.SUMMARY_PLAN_FILE_PREFIX} {plan_file}")
    print(f"{GenerateMessages.SUMMARY_GENERATED_COUNT_PREFIX} {gen_result.total}{GenerateMessages.SUMMARY_GENERATED_COUNT_SUFFIX}")
    mode = GenerateMessages.SUMMARY_MODE_DRY_RUN if gen_result.dry_run else GenerateMessages.SUMMARY_MODE_NORMAL
    print(f"{GenerateMessages.SUMMARY_MODE_PREFIX} {mode}")
    print()

    if gen_result.tickets:
        print(GenerateMessages.SUMMARY_TICKETS_LIST_TITLE)
        for ticket in gen_result.tickets:
            if ticket.tdd_phases:
                phases_str = ", ".join(ticket.tdd_phases)
            else:
                phases_str = GenerateMessages.SUMMARY_TICKET_DETAILS_NO_TDD
            print(f"{GenerateMessages.SUMMARY_TICKET_FORMAT.format(id=ticket.id, title=ticket.title)}")
            print(f"{GenerateMessages.SUMMARY_TICKET_DETAILS_FORMAT.format(wave=ticket.wave, phases=phases_str)}")
        print()


def _save_tickets(gen_result, version: str) -> int:
    """保存生成的 Tickets 到檔案。

    Args:
        gen_result: GenerationResult 物件
        version: 版本號

    Returns:
        成功保存的 Ticket 數量
    """
    saved_count = 0
    tickets_dir = get_tickets_dir(version)
    tickets_dir.mkdir(parents=True, exist_ok=True)

    for ticket in gen_result.tickets:
        try:
            # 從 content 中提取 frontmatter 和 body
            parts = ticket.content.split("---\n", 2)
            if len(parts) < 3:
                continue

            # 解析 YAML frontmatter
            import yaml

            yaml_str = parts[1]
            frontmatter = yaml.safe_load(yaml_str) or {}
            body = parts[2] if len(parts) > 2 else ""

            # 新增 body 到 frontmatter
            frontmatter["_body"] = body

            # 保存 Ticket
            ticket_path = get_ticket_path(version, ticket.id)
            save_ticket(frontmatter, ticket_path)
            saved_count += 1

        except Exception as e:
            print(format_warning(WarningMessages.BACKUP_FAILED, error=str(e)))
            continue

    return saved_count


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 generate 子命令"""
    parser = subparsers.add_parser(
        "generate",
        help=GenerateMessages.HELP_GENERATE,
    )

    parser.add_argument(
        "plan_file",
        help=GenerateMessages.ARG_PLAN_FILE,
    )
    parser.add_argument(
        "--version",
        required=True,
        help=GenerateMessages.ARG_VERSION,
    )
    parser.add_argument(
        "--wave",
        type=int,
        required=True,
        help=GenerateMessages.ARG_WAVE,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=GenerateMessages.ARG_DRY_RUN,
    )

    parser.set_defaults(func=execute)


