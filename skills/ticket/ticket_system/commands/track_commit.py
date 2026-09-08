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
import json
import os
import subprocess
from typing import List, Optional, Set

from ticket_system.lib.file_conflict import files_intersect, parse_file_intent, write_files
from ticket_system.lib.git_ops import commit_files_isolated
from ticket_system.lib.messages import ErrorMessages, format_error
from ticket_system.lib.paths import get_ticket_state_root
from ticket_system.lib.project_root import resolve_project_cwd
from ticket_system.lib.ticket_loader import load_ticket


def _resolve_repo_root(worktree: Optional[str]) -> Optional[str]:
    """解析本次提交操作的 repo root。

    ``--worktree`` 未指定時沿用既有行為（``resolve_project_cwd()``，即
    process cwd 所屬 repo；agent 慣例於主 repo cwd 執行 ticket CLI，故此
    路徑恆解析為主 repo）。``--worktree`` 指定時改以該路徑對應的 git
    repo root 為準，讓後續所有 git 操作（read-tree/add/diff/空 tree 比對）
    綁定在檔案實際變更所在的 linked worktree，而非主 repo working tree
    （根因：linked worktree 有獨立 working tree 與 index，主 repo
    working tree 對 worktree 內的變更零感知）。

    Returns:
        repo root 絕對路徑；``--worktree`` 指定但非合法 git 目錄時回傳
        None（呼叫端應視為錯誤並拒絕提交）。
    """
    if not worktree:
        return resolve_project_cwd()

    abs_worktree = os.path.abspath(worktree)
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=abs_worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _to_repo_relative(path: str, repo_root: str, base_dir: str) -> str:
    """將輸入路徑（可能為絕對路徑或相對於 base_dir 的相對路徑）正規化為
    repo-relative posix 路徑，供與 where.files 宣告路徑比對。
    """
    abs_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
    return os.path.relpath(os.path.abspath(abs_path), repo_root).replace(os.sep, "/")


def _out_of_scope_files(
    input_files: List[str], declared: set, repo_root: str, base_dir: str
) -> List[str]:
    """回傳 input_files 中未落在 declared（where.files 寫入子集）內的原始輸入項。

    複用 file_conflict.files_intersect 做路徑段前綴比對（非集合精確字串
    比對）：declared 內含目錄型宣告（如某測試目錄路徑）時，其下個別檔名
    視為在範圍內——精確字串比對永遠不會命中目錄字面值，是原缺陷成因。
    """
    out_of_scope = []
    for orig in input_files:
        normalized = _to_repo_relative(orig, repo_root, base_dir)
        if not any(files_intersect(normalized, d) for d in declared):
            out_of_scope.append(orig)
    return out_of_scope


def _git_status_porcelain(repo_root: str) -> str:
    """回傳 `git status --porcelain` 原始輸出，供展開目錄型宣告為具體
    變更檔案清單。獨立為模組層函式以便測試 monkeypatch。"""
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--no-renames"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def _other_ticket_declared_files(own_ticket_id: str) -> Set[str]:
    """讀取 `.claude/dispatch-active.json`，回傳除本票外其他活躍派發宣告的
    where.files 路徑集合（已剝除 `::read`／`::write` 標記）。

    目錄型宣告展開（`_expand_directory_to_changed_files`）原以
    `git status --porcelain` 取整個目錄下全部變更檔，無 session／
    where.files 歸屬過濾，並行下會把他 session 的變更一併吸入本次提交
    （Round 3 finding 3-B B1）。本函式提供排除集合：目錄展開時，凡命中
    其他活躍派發（`ticket_id` 不等於本票）宣告路徑的變更檔一律排除，
    使目錄展開只保留「未被他票宣告」的變更（本票或無人宣告皆保留，
    僅排除已知歸屬他票者，非要求逐檔正向證明歸屬本票——registry 無法
    做到後者）。

    讀取失敗（檔案不存在／JSON 格式錯誤／結構不符）一律視為無其他
    派發，回傳空集合（fail-open）：目錄展開的安全邊界仍是 where.files
    子集檢查（`_out_of_scope_files`），本過濾為並行防護的加強層，不因
    registry 讀取失敗而擋下本應正常提交。
    """
    dispatch_file = get_ticket_state_root() / ".claude" / "dispatch-active.json"
    try:
        raw = dispatch_file.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return set()

    if not isinstance(data, dict):
        return set()
    dispatches = data.get("dispatches")
    if not isinstance(dispatches, list):
        return set()

    other_files: Set[str] = set()
    for entry in dispatches:
        if not isinstance(entry, dict):
            continue
        if entry.get("ticket_id") == own_ticket_id:
            continue
        files = entry.get("files")
        if not isinstance(files, list):
            continue
        for f in files:
            path, _ = parse_file_intent(str(f))
            other_files.add(path)
    return other_files


def _expand_directory_to_changed_files(
    directory: str, repo_root: str, exclude: Optional[Set[str]] = None
) -> List[str]:
    """將目錄型宣告展開為該目錄底下、working tree 對 HEAD 有變更（含未
    追蹤）的具體檔案清單。

    commit_files_isolated 的自我驗證比對 `git diff --name-only` 的實際
    變更檔案，目錄字面值永遠不會出現在該輸出中，直接傳目錄本身必然自我
    驗證失敗。在呼叫端先展開為具體檔案，讓 commit_files_isolated 恆收到
    與其自我驗證邏輯同構的輸入，不改動該函式既有的精確比對契約（隔離
    索引 CAS 三要件之一）。

    `exclude`：其他活躍派發宣告的路徑集合（見 `_other_ticket_declared_files`），
    命中則跳過，避免並行下把他 session 的變更一併展開進本次提交
    （3-B B1）。為 None 時等同空集合（既有行為不變）。
    """
    status_out = _git_status_porcelain(repo_root)
    exclude = exclude or set()
    changed = []
    for line in status_out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if not files_intersect(path, directory):
            continue
        if any(files_intersect(path, other) for other in exclude):
            continue
        changed.append(path)
    return changed


def _expand_directories(
    input_files: List[str], repo_root: str, base_dir: str, own_ticket_id: str
) -> List[str]:
    """將 input_files 中屬目錄的項目展開為具體變更檔案，其餘項目原樣
    保留。回傳恆為具體檔案路徑清單（可能為空，呼叫端需另行判斷）。

    `_other_ticket_declared_files` 僅在確實需要展開目錄時才呼叫一次
    （lazy，非目錄型輸入不觸發 registry 讀取），排除結果套用至本次呼叫
    中所有目錄型宣告的展開。
    """
    exclude: Optional[Set[str]] = None
    expanded: List[str] = []
    for orig in input_files:
        normalized = _to_repo_relative(orig, repo_root, base_dir)
        abs_path = os.path.join(repo_root, normalized)
        if os.path.isdir(abs_path):
            if exclude is None:
                exclude = _other_ticket_declared_files(own_ticket_id)
            expanded.extend(
                _expand_directory_to_changed_files(normalized, repo_root, exclude)
            )
        else:
            expanded.append(normalized)
    return expanded


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

    worktree = getattr(args, "worktree", None)
    repo_root = _resolve_repo_root(worktree)
    if repo_root is None:
        print(
            f"[ERROR] --worktree {worktree} 不是合法的 git 目錄（"
            "git rev-parse --show-toplevel 失敗），拒絕提交"
        )
        return 1

    declared = set(write_files(ticket))
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
        message = (
            f"[ERROR] Ticket {args.ticket_id} 的 where.files 未宣告任何寫入路徑，"
            "無法判斷提交範圍是否合法，拒絕提交"
        )
        if ticket.get("type") == "ANA":
            # ANA 型 where.files 預設全為唯讀（file_conflict._default_intent），
            # 逐檔未標 ::write 時 write_files() 恆回空集合——即使檔案清單本身
            # 非空。不補這段說明，讀者看到「未宣告任何寫入路徑」會誤判為 CLI
            # bug（本 session 已有兩個代理人各自誤判並繞道）。
            message += (
                "\n[NOTE] 本票為 ANA 型，where.files 預設唯讀（用於標記影響面，"
                "非寫入意圖）；若確有寫入需求，請於該路徑後加 ::write 標記，"
                "例如：path/to/file.py::write"
            )
        print(message)
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

    # 目錄型輸入展開為具體變更檔案：commit_files_isolated 的自我驗證比對
    # 精確檔案清單，目錄字面值不會出現在該比對結果中（見
    # _expand_directory_to_changed_files docstring）。展開後恆為具體檔案。
    normalized_input = _expand_directories(
        args.files, repo_root, base_dir, args.ticket_id
    )
    if not normalized_input:
        print(
            "[ERROR] 宣告範圍內的目錄底下無任何變更檔案，無可提交內容，拒絕提交：\n"
            + "\n".join(f"  - {f}" for f in args.files)
        )
        return 1

    result = commit_files_isolated(normalized_input, args.message, cwd=repo_root)
    status = result["status"]
    if status == "committed":
        print(f"[OK] 已提交 {result['commit_sha']}")
        for p in normalized_input:
            print(f"  - {p}")
        return 0
    if status == "empty":
        # 3-H 案 3：主倉庫 cwd 對 linked worktree 內的變更零感知，未帶
        # --worktree 時空 tree 短路與「內容真的與 HEAD 相同」同形，僅憑
        # exit code 0 無法區分。明確在 stdout 提示，避免代理人把此 exit 0
        # 誤判為「已提交」（危險答案：exit 0 判定成功 -> complete -> worktree
        # 分支零 commit）。
        print(
            "[INFO] 檔案內容與 HEAD 相同，無需提交（空 tree 短路）。"
            "若變更實際發生在 linked worktree 但未帶 --worktree，"
            "本命令對該變更零感知；請確認已加 --worktree <worktree 絕對路徑>。"
        )
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
        "--worktree",
        dest="worktree",
        default=None,
        help=(
            "檔案實際變更所在的 linked worktree 絕對路徑。ticket CLI 慣例於"
            "主 repo cwd 執行，若變更發生在 linked worktree（而非主 repo），"
            "必須指定此參數，否則 git 操作會綁定在主 repo working tree，對"
            "worktree 內的新檔/修改一律讀不到（新檔無法 add、已修改檔誤判"
            "空 tree 短路）"
        ),
    )
    p_commit.add_argument(
        "files",
        nargs="+",
        help="欲提交的檔案路徑（須為 ticket where.files 寫入子集，超出範圍拒絕提交）",
    )
