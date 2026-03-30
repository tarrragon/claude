"""CLI 入口模組 — 定義 /doc 的 argparse 結構和子命令路由。"""

import argparse
import sys

from doc_system.commands import query, list_cmd, nav, domain, status, test_map


def build_parser() -> argparse.ArgumentParser:
    """建立主 parser 和 6 個 subparser。"""
    parser = argparse.ArgumentParser(
        prog="doc",
        description="需求追蹤文件系統 CLI — 管理 proposals/spec/usecases",
    )

    subparsers = parser.add_subparsers(dest="command")

    # query
    query_parser = subparsers.add_parser("query", help="依 ID 查詢文件內容")
    query_parser.add_argument("doc_id", help="文件 ID（如 PROP-001, UC01, SPEC-auth）")

    # list
    list_parser = subparsers.add_parser("list", help="列出文件清單")
    list_parser.add_argument(
        "doc_type",
        nargs="?",
        choices=["proposals", "usecases", "specs"],
        help="文件類型（省略則列出全部）",
    )

    # nav
    nav_parser = subparsers.add_parser("nav", help="導覽文件關聯")
    nav_parser.add_argument("doc_id", help="起始文件 ID")

    # domain
    domain_parser = subparsers.add_parser("domain", help="依 domain 篩選文件")
    domain_parser.add_argument(
        "domain_name",
        nargs="?",
        default=None,
        help="Domain 名稱（省略則列出全部）",
    )

    # status
    subparsers.add_parser("status", help="顯示文件系統總覽狀態")

    # test-map
    test_map_parser = subparsers.add_parser("test-map", help="顯示需求-測試對應表")
    test_map_parser.add_argument(
        "uc_id",
        nargs="?",
        default=None,
        help="UC ID（省略則顯示全部）",
    )

    return parser


COMMAND_HANDLERS = {
    "query": query.execute,
    "list": list_cmd.execute,
    "nav": nav.execute,
    "domain": domain.execute,
    "status": status.execute,
    "test-map": test_map.execute,
}


def main() -> None:
    """CLI 主入口。無子命令時預設執行 status。"""
    parser = build_parser()
    args = parser.parse_args()

    command = args.command
    if command is None:
        command = "status"

    handler = COMMAND_HANDLERS.get(command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    handler(args)
