"""
ticket track commit 子命令

代理人端以隔離索引（`git_ops.commit_files_isolated`）提交 ticket where.files
子集內的指定檔案，全程不觸碰共用 index。取代裸 `git add` + `git commit` 的
制式句路徑：裸 commit 即使遵循「精確 git add + git diff --cached
--name-only 核對」的操作紀律，仍在並行條件下反覆吸入他票內容，本命令從
工具層消除共用 index 這個風險來源，而非再依賴一次操作紀律複述。

用法：
    ticket track commit <ticket-id> -m <message> -- <exact files...>

檔案清單須為 ticket where.files（寫入意圖）宣告路徑的子集，超出宣告範圍
一律拒絕提交（不部分提交、不自動裁切清單）。
"""
if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track commit")
    sys.exit(1)


import argparse
import os
from typing import List

from ticket_system.lib.file_conflict import write_files
from ticket_system.lib.git_ops import commit_files_isolated
from ticket_system.lib.messages import ErrorMessages, format_error
from ticket_system.lib.project_root import resolve_project_cwd
from ticket_system.lib.ticket_loader import load_ticket


def _to_repo_relative(path: str, repo_root: str, base_dir: str) -> str:
    """將輸入路徑（可能為絕對路徑或相對於 base_dir 的相對路徑）正規化為
    repo-relative posix 路徑，供與 where.files 宣告路徑比對。
    """
    abs_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
    return os.path.relpath(os.path.abspath(abs_path), repo_root).replace(os.sep, "/")


def _out_of_scope_files(
    input_files: List[str], declared: set, repo_root: str, base_dir: str
) -> List[str]:
    """回傳 input_files 中未落在 declared（where.files 寫入子集）內的原始輸入項。"""
    out_of_scope = []
    for orig in input_files:
        normalized = _to_repo_relative(orig, repo_root, base_dir)
        if normalized not in declared:
            out_of_scope.append(orig)
    return out_of_scope


def execute_commit(args: argparse.Namespace, version: str) -> int:
    """`ticket track commit <ticket-id> -m <msg> -- <files>`：驗證 files
    為 where.files 寫入子集後，透過 commit_files_isolated 隔離提交。

    Returns:
        0：commit 成功或空 tree 短路（視為成功，無需提交）
        1：ticket 不存在 / where.files 未宣告 / 檔案超出宣告範圍 / 提交失敗
    """
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    declared = set(write_files(ticket))
    repo_root = resolve_project_cwd()
    # base_dir 固定為 repo_root（而非 os.getcwd()）：ticket shim 透過
    # `uv run --directory <skill_dir>` 呼叫，process 實際 cwd 會被切換到
    # skill_dir，與呼叫者鍵入指令時所在目錄（通常是 repo 根）不同。
    # where.files 宣告值本身即為 repo-root-relative 路徑，files 引數依
    # 慣例採同一格式，故兩側一律以 repo_root 為基準正規化，
    # 不依賴易被 shim 改變的 os.getcwd()。
    base_dir = repo_root
    normalized_declared = {
        _to_repo_relative(p, repo_root, repo_root) for p in declared
    }

    if not normalized_declared:
        print(
            f"[ERROR] Ticket {args.ticket_id} 的 where.files 未宣告任何寫入路徑，"
            "無法判斷提交範圍是否合法，拒絕提交"
        )
        return 1

    out_of_scope = _out_of_scope_files(args.files, normalized_declared, repo_root, base_dir)
    if out_of_scope:
        print(
            "[ERROR] 以下檔案不在 ticket where.files 宣告的寫入範圍內，拒絕提交：\n"
            + "\n".join(f"  - {f}" for f in out_of_scope)
            + "\n宣告範圍：\n"
            + "\n".join(f"  - {f}" for f in sorted(normalized_declared))
        )
        return 1

    normalized_input = [
        _to_repo_relative(p, repo_root, base_dir) for p in args.files
    ]

    result = commit_files_isolated(normalized_input, args.message, cwd=repo_root)
    status = result["status"]
    if status == "committed":
        print(f"[OK] 已提交 {result['commit_sha']}")
        for p in normalized_input:
            print(f"  - {p}")
        return 0
    if status == "empty":
        print("[INFO] 檔案內容與 HEAD 相同，無需提交（空 tree 短路）")
        return 0

    print(f"[ERROR] 提交失敗：{result['error']}")
    return 1


def register_commit_command(subparsers: "argparse._SubParsersAction") -> None:
    """註冊 commit 子命令。"""
    p_commit = subparsers.add_parser(
        "commit",
        help="以隔離索引提交 where.files 子集內的指定檔案（不觸碰共用 index）",
    )
    p_commit.add_argument("ticket_id", help="Ticket ID")
    p_commit.add_argument(
        "-m",
        "--message",
        dest="message",
        required=True,
        help="commit message",
    )
    p_commit.add_argument(
        "files",
        nargs="+",
        help="欲提交的檔案路徑（須為 ticket where.files 寫入子集，超出範圍拒絕提交）",
    )
