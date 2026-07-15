"""CLI 入口模組 — 定義 /doc 的 argparse 結構和子命令路由。"""

import argparse
import sys

from doc_system.commands import query, list_cmd, nav, domain, status, test_map, create, update, batch_init, uc


def build_parser() -> argparse.ArgumentParser:
    """建立主 parser 和所有 subparser。"""
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

    # create
    create_parser = subparsers.add_parser("create", help="從模板建立新文件")
    create_parser.add_argument(
        "type",
        choices=["proposal", "spec", "usecase"],
        help="文件類型",
    )
    create_parser.add_argument("id", nargs="?", default=None, help="文件 ID（省略則自動分配下一個序號）")
    create_parser.add_argument("--title", default=None, help="文件標題")
    create_parser.add_argument(
        "--domain",
        default=None,
        help="spec 的 domain 子目錄（僅 spec 類型需要）",
    )

    # batch-init
    batch_init_parser = subparsers.add_parser("batch-init", help="批量建立 spec + UC + traceability 骨架")
    batch_init_parser.add_argument("--proposals", required=True, help="提案 ID 清單（逗號分隔，如 PROP-007,PROP-008）")
    batch_init_parser.add_argument("--domain", default=None, help="spec 的 domain 子目錄")

    # update
    update_parser = subparsers.add_parser("update", help="更新文件狀態")
    update_parser.add_argument("id", help="文件 ID（如 PROP-001）")
    update_parser.add_argument(
        "--status",
        required=True,
        help="新狀態（draft/discussing/confirmed/implemented/withdrawn）",
    )

    # uc（子命令群組：list/verify/trace/context）
    uc_parser = subparsers.add_parser("uc", help="UC 編號治理：list/verify/trace/context")
    uc_subparsers = uc_parser.add_subparsers(dest="uc_command")

    uc_subparsers.add_parser("list", help="列出合法 UC 編號+標題")

    uc_verify_parser = uc_subparsers.add_parser("verify", help="驗證路徑內 UC token 是否符合白名單")
    uc_verify_parser.add_argument("path", nargs="?", default=None, help="掃描路徑（省略則掃描整個專案）")

    uc_trace_parser = uc_subparsers.add_parser("trace", help="列出指定 UC 的 code 引用位置")
    uc_trace_parser.add_argument("uc_id", help="UC 編號，如 UC-01（例：doc uc trace UC-05）")
    uc_trace_parser.add_argument(
        "--limit", type=int, default=None, help="輸出筆數上限（預設 20）"
    )
    uc_trace_parser.add_argument(
        "--all", action="store_true", help="輸出全部引用，不受 --limit 限制"
    )

    uc_context_parser = uc_subparsers.add_parser(
        "context", help="輸出 UC 編號或 ticket ID 對應的標題+spec 位置+code 引用"
    )
    uc_context_parser.add_argument("target", help="UC 編號（如 UC-01）或 ticket ID")

    uc_summary_parser = uc_subparsers.add_parser(
        "summary", help="輸出 UC 標題+spec 位置+主流程摘要（供 Context Bundle 自動注入使用）"
    )
    uc_summary_parser.add_argument("uc_id", help="UC 編號，如 UC-01")
    uc_summary_parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出")

    # fingerprint（子命令群組：update/check）
    fp_parser = uc_subparsers.add_parser(
        "fingerprint", help="UC 內容指紋漂移偵測：update/check"
    )
    fp_subparsers = fp_parser.add_subparsers(dest="fp_command")
    fp_subparsers.add_parser("update", help="計算並寫入 UC 內容指紋到 sidecar JSON")
    fp_subparsers.add_parser("check", help="比對指紋，列出漂移的 UC")

    # acceptance-check
    ac_parser = uc_subparsers.add_parser(
        "acceptance-check", help="檢查 ticket acceptance 中 UC 引用的存在性與指紋漂移"
    )
    ac_parser.add_argument("ticket_id", help="Ticket ID（如 0.38.1-W1-024）")
    ac_parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出（供 dispatch-validate 消費）")

    return parser


COMMAND_HANDLERS = {
    "query": query.execute,
    "list": list_cmd.execute,
    "nav": nav.execute,
    "domain": domain.execute,
    "status": status.execute,
    "test-map": test_map.execute,
    "create": create.execute,
    "batch-init": batch_init.execute,
    "update": update.execute,
    "uc": uc.execute,
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

    try:
        handler(args)
    except BrokenPipeError:
        # 輸出被截斷管線（如 | head）提前關閉，非程式錯誤，靜默結束
        sys.exit(0)
