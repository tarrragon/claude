#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
統一 Ticket 系統入口腳本

提供統一的命令入口，整合 create、track、handoff、resume、migrate 五個子命令。

支援兩種使用方式：
1. 全局安裝（推薦）:
    uv tool install .claude/skills/ticket
    ticket create --version X --wave Y --action Z --target T
    ticket track summary
    ticket track query <id>

2. 局部執行（不安裝）:
    cd .claude/skills/ticket
    uv run ticket create --version X --wave Y --action Z --target T
    uv run ticket track summary
    uv run ticket track query <id>
"""

import sys
import shutil
import argparse
import os
from pathlib import Path

from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY

# 導入所有子命令（含環境檢測）
try:
    from ticket_system.commands import (
        create_register,
        track_register,
        handoff_register,
        resume_register,
        migrate_register,
        generate_register,
        batch_create_register,
        show_register,
    )
    from ticket_system.commands.version_shift import register as version_shift_register
except ModuleNotFoundError:
    print(SEPARATOR_PRIMARY)
    print("[ERROR] 套件未正確安裝")
    print(SEPARATOR_PRIMARY)
    print()
    print("推薦方式：全局安裝（只需執行一次）")
    print("  cd .claude/skills/ticket")
    print("  uv tool install .")
    print("  # 之後在任何目錄執行：")
    print("  ticket track summary")
    print()
    print("替代方式：局部執行（不安裝）")
    print("  cd .claude/skills/ticket")
    print("  uv sync")
    print("  uv run ticket track summary")
    print()
    print("或透過 Claude 使用 /ticket 指令")
    print(SEPARATOR_PRIMARY)
    sys.exit(1)


def detect_installation_type() -> tuple[bool, str]:
    """
    偵測 ticket 的安裝方式。

    Returns:
        (is_global_install, mode_description) - 是否為全局安裝，以及模式描述
    """
    # 檢查是否為全局安裝：嘗試用 which 找 ticket 命令
    ticket_path = shutil.which("ticket")

    if ticket_path:
        # 全局安裝了
        return (True, "全局安裝")
    else:
        # 未全局安裝
        return (False, "局部執行（uv run）")


def check_installation() -> None:
    """
    檢查並提示安裝狀態。
    """
    is_global, mode = detect_installation_type()

    # 全局安裝情況下不需要提示
    if is_global:
        return

    # 未全局安裝時檢查是否在正確目錄
    current_dir = Path.cwd()
    ticket_system_dir = Path(__file__).parent.parent.parent

    # 檢查是否在 ticket 目錄或其子目錄中
    try:
        current_dir.relative_to(ticket_system_dir)
        # 在 ticket 目錄中，不需要提示
        return
    except ValueError:
        # 不在 ticket 目錄中，提示全局安裝
        print(SEPARATOR_PRIMARY)
        print("[INFO] 為了在任何目錄執行 ticket 指令，建議全局安裝")
        print(SEPARATOR_PRIMARY)
        print()
        print("執行以下命令進行全局安裝（只需執行一次）：")
        print()
        print("  cd .claude/skills/ticket")
        print("  uv tool install .")
        print()
        print("安裝完成後可在任何目錄執行：")
        print("  ticket track summary")
        print("  ticket track query 0.31.0-W4-001")
        print()
        print(SEPARATOR_PRIMARY)
        print()


def main() -> int:
    """主程式入口"""
    # 檢查安裝狀態並提示（如果未全局安裝且不在正確目錄）
    check_installation()

    parser = argparse.ArgumentParser(
        description="統一 Ticket 系統 - 整合建立、追蹤、交接、恢復、遷移功能",
        epilog="查詢子命令詳細用法：ticket <command> -h\n"
               "  （例如 ticket show -h、ticket track -h）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 建立子命令解析器
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="可用命令",
    )

    # 註冊所有子命令
    create_register(subparsers)
    track_register(subparsers)
    handoff_register(subparsers)
    resume_register(subparsers)
    migrate_register(subparsers)
    generate_register(subparsers)
    batch_create_register(subparsers)
    version_shift_register(subparsers)
    show_register(subparsers)

    # 解析命令行參數
    args = parser.parse_args()

    # 執行對應的命令
    if hasattr(args, "func"):
        rc = args.func(args)
    else:
        parser.print_help()
        return 1

    # CLI 安全收尾：非阻塞收割殘留 stale *.md.lock（W8-017）
    # active lock 永不被誤刪（reap_stale_locks 用 LOCK_NB 試鎖判定 stale）。
    _reap_stale_locks_quietly()
    return rc


def _reap_stale_locks_quietly() -> None:
    """於 CLI 收尾收割 stale lock；任何失敗皆靜默跳過（不阻斷主流程）。"""
    try:
        from ticket_system.lib.file_lock import reap_stale_locks
        from ticket_system.lib.paths import get_project_root
        from ticket_system.lib.constants import WORK_LOGS_DIR

        reap_stale_locks(get_project_root() / WORK_LOGS_DIR)
    except Exception:
        # 收割屬清理性質，失敗不應影響已完成的主命令結果（返回碼已決定）
        pass


if __name__ == "__main__":
    sys.exit(main())
