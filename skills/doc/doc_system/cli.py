"""CLI 入口模組 — 定義 /doc 的 argparse 結構和子命令路由。"""

import argparse
import os
import sys
from pathlib import Path

if not __package__:
    # 以 python3 <path>/cli.py 直接執行時 sys.path[0] 是 doc_system/ 本身，
    # 套件名 doc_system 不可匯入；補上 skill 根目錄，使下方絕對匯入成立。
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from doc_system.commands import query, list_cmd, nav, domain, status, test_map, create, update, batch_init, uc, validate, schema


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
        choices=["proposal", "spec", "usecase", "data-contract", "event"],
        help="文件類型",
    )
    create_parser.add_argument("id", nargs="?", default=None, help="文件 ID（省略則自動分配下一個序號）")
    create_parser.add_argument("--title", default=None, help="文件標題")
    create_parser.add_argument(
        "--domain",
        default=None,
        help="spec/data-contract/event 的 domain 子目錄（僅需要 domain 的類型需要）",
    )

    # next-id
    next_id_parser = subparsers.add_parser("next-id", help="唯讀查詢下一個可分配的 ID（不建立檔案）")
    next_id_parser.add_argument(
        "type",
        choices=["proposal", "spec", "usecase", "data-contract", "event"],
        help="文件類型",
    )
    next_id_parser.add_argument(
        "--domain",
        default=None,
        help="event 型別為 domain-scoped 配號，必填",
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

    # validate
    validate_parser = subparsers.add_parser(
        "validate", help="依 frontmatter subdomain 分派章節 schema 驗證"
    )
    validate_parser.add_argument("doc_id", help="文件 ID（如 SPEC-002）")

    # validate-paths
    subparsers.add_parser(
        "validate-paths",
        help="檢查全部 DomainBundle path_patterns 與 docs/non-domain-paths.yaml（供 CI）",
    )

    # validate-filenames
    subparsers.add_parser(
        "validate-filenames",
        help="掃描各 doc type 目錄，驗證檔名是否符合配號器慣例（防重號盲區）",
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

    # schema（子命令群組：export）
    schema_parser = subparsers.add_parser(
        "schema", help="圖譜型別表機器可讀匯出（SSOT 為 tracking_schema.py）"
    )
    schema_subparsers = schema_parser.add_subparsers(dest="schema_command")

    schema_export_parser = schema_subparsers.add_parser(
        "export", help="從 tracking_schema.py 產生圖譜型別表 JSON"
    )
    schema_export_parser.add_argument(
        "--json",
        action="store_true",
        help="印出 JSON 至 stdout（不寫檔）；省略則寫入 tracking_schema.json 並印出路徑",
    )

    return parser


COMMAND_HANDLERS = {
    "query": query.execute,
    "list": list_cmd.execute,
    "nav": nav.execute,
    "domain": domain.execute,
    "status": status.execute,
    "test-map": test_map.execute,
    "create": create.execute,
    "next-id": create.execute_next_id,
    "batch-init": batch_init.execute,
    "update": update.execute,
    "uc": uc.execute,
    "validate": validate.execute,
    "validate-filenames": validate.execute_filenames,
    "validate-paths": validate.execute_paths,
    "schema": schema.execute,
}


CALLER_CWD_ENV = "SKILL_CLI_CALLER_CWD"


def restore_caller_cwd() -> None:
    """還原呼叫者的 cwd，使相對路徑引數與專案根目錄以呼叫者所在目錄解析。

    shim 以 `uv run --directory <skill_dir>` 啟動，行程 cwd 被改為 skill 目錄
    （PWD 也被 uv 改寫，不可信）。shim 在切換前把呼叫者 cwd 放進
    SKILL_CLI_CALLER_CWD，此處讀回；未設定（非 shim 啟動）時不動 cwd。
    值無效（非絕對路徑或非目錄）時寫 stderr 警告並保持現有 cwd。
    本函式在 ticket、worktree、doc 三個 skill 內嵌同一份，行為由測試鎖定一致。
    """
    caller = os.environ.pop(CALLER_CWD_ENV, None)  # 讀一次即移除，避免子行程繼承
    if not caller:
        return
    if os.path.isabs(caller) and os.path.isdir(caller):
        os.chdir(caller)
        return
    sys.stderr.write(
        f"[Warning] {CALLER_CWD_ENV}={caller!r} 無效（需為存在的絕對目錄），"
        f"改用目前目錄 {os.getcwd()}\n"
    )


def main() -> None:
    """CLI 主入口。無子命令時預設執行 status。"""
    restore_caller_cwd()
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


if __name__ == "__main__":
    main()
