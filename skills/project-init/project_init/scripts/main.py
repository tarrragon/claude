#!/usr/bin/env python3
"""project-init CLI — 環境初始化工具入口點.

提供兩個子指令：
- check：掃描環境狀態（唯讀）
- setup：完整安裝/更新環境
"""

import argparse
import subprocess
import sys
from pathlib import Path

from project_init.commands.check import run_check
from project_init.commands.onboard import run_onboard
from project_init.commands.setup import run_setup

__version__ = "1.1.0"


def _resolve_project_root() -> Path:
    """解析專案根目錄。

    優先使用 `git rev-parse --show-toplevel`；git 不可用（非 git 倉庫、
    git 未安裝、subprocess 錯誤）時 fallback 到 `Path.cwd()`。

    Why：project-init 本身納入 cwd-resolving shim（ARCH-APP-002）後，每次
    呼叫皆先被 `uv run --directory` 切到 `.claude/skills/project-init`
    再啟動 Python，此時 `Path.cwd()` 回傳的是 skill 原始碼目錄而非呼叫者
    所在的專案根目錄，導致 check/setup 誤判 Hook 目錄不存在、自製套件
    掃描落空。git toplevel 不受 cwd 位於 repo 何處影響（`.claude/skills/*`
    非巢狀 git repo），與 ticket_system 的 `resolve_project_cwd()` 同一
    做法。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return Path.cwd()


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

    # 確定專案根目錄（git toplevel，見 _resolve_project_root 說明）
    project_root = _resolve_project_root()

    # 派發到子指令
    try:
        if args.command == "check":
            result = run_check(project_root)
            return 0 if result.all_ok else 1
        elif args.command == "onboard":
            result = run_onboard(project_root)
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
  project-init onboard            框架定制引導
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

    # onboard 子指令
    subparsers.add_parser(
        "onboard",
        help="框架定制引導（偵測專案語言並建議需要的設定）",
    )

    # setup 子指令
    subparsers.add_parser(
        "setup",
        help="完整安裝/更新環境（檢查並執行必要的操作）",
    )

    return parser


if __name__ == "__main__":
    sys.exit(main())
