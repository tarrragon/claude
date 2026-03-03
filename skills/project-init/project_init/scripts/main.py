#!/usr/bin/env python3
"""project-init CLI — 環境初始化工具入口點.

提供兩個子指令：
- check：掃描環境狀態（唯讀）
- setup：完整安裝/更新環境
"""

import argparse
import sys
from pathlib import Path

from project_init.commands.check import run_check
from project_init.commands.setup import run_setup

__version__ = "1.0.0"


def main() -> int:
    """主入口點 — 解析指令並派發到子指令.

    Returns:
        int: 結束代碼（0 = 成功，1 = 失敗）
    """
    parser = _create_parser()
    args = parser.parse_args()

    # 處理 --version 旗標
    if args.version:
        print(f"project-init {__version__}")
        return 0

    # 確定專案根目錄（當前工作目錄或環境變數）
    project_root = Path.cwd()

    # 派發到子指令
    try:
        if args.command == "check":
            result = run_check(project_root)
            return 0 if result.all_ok else 1
        elif args.command == "setup":
            result = run_setup(project_root)
            return 0 if result.all_ok else 1
        else:
            # 不應該到達此處（argparse 會強制指令）
            parser.print_help()
            return 1
    except Exception as e:
        print(f"錯誤: {e}", file=sys.stderr)
        return 1


def _create_parser() -> argparse.ArgumentParser:
    """建立 argparse 解析器.

    Returns:
        argparse.ArgumentParser: 設定完成的解析器。
    """
    parser = argparse.ArgumentParser(
        prog="project-init",
        description="環境初始化工具 — 檢查和設定開發環境",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  project-init --version          輸出版本號
  project-init check              掃描環境狀態
  project-init setup              完整安裝/更新環境
        """.strip(),
    )

    # 全域旗標
    parser.add_argument(
        "--version",
        action="store_true",
        help="輸出版本號並結束",
    )

    # 子指令
    subparsers = parser.add_subparsers(
        dest="command",
        help="子指令",
    )

    # check 子指令
    subparsers.add_parser(
        "check",
        help="掃描環境狀態（唯讀檢查，不修改任何東西）",
    )

    # setup 子指令
    subparsers.add_parser(
        "setup",
        help="完整安裝/更新環境（檢查並執行必要的操作）",
    )

    return parser


if __name__ == "__main__":
    sys.exit(main())
