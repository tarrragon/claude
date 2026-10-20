"""寫入範圍判定共用模組（ticket track commit / move-lines 共用）。

兩命令對「哪些路徑可寫」使用同一判準：路徑落在 ticket where.files 寫入
子集內、解 symlink 後仍在 repo 內且本身不是 symlink、``--worktree`` 屬於
本 repo 的 ``git worktree list``。任何查詢失敗一律拒絕（保守一側）。
"""
import os
import subprocess
from typing import List, Optional, Set

from ticket_system.lib.file_conflict import files_intersect


def to_repo_relative(path: str, repo_root: str, base_dir: str) -> str:
    """將輸入路徑（絕對或相對 base_dir）正規化為 repo-relative posix 路徑。"""
    abs_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
    return os.path.relpath(os.path.abspath(abs_path), repo_root).replace(os.sep, "/")


def out_of_scope_files(
    input_files: List[str], declared: set, repo_root: str, base_dir: str
) -> List[str]:
    """回傳 input_files 中未落在 declared 內的原始輸入項。

    以 file_conflict.files_intersect 做路徑段前綴比對：目錄型宣告涵蓋其下
    個別檔名（精確字串比對永遠不會命中目錄字面值）。
    """
    return [
        orig for orig in input_files
        if not any(
            files_intersect(to_repo_relative(orig, repo_root, base_dir), d)
            for d in declared
        )
    ]


def unsafe_paths(input_files: List[str], repo_root: str, base_dir: str) -> List[str]:
    """回傳解 symlink 後會逸出 repo、或本身是 symlink 的原始輸入項。

    abspath 比對看不出 symlink：宣告檔若是 symlink，寫入會把連結換成一般
    檔；宣告目錄下的 symlink 子目錄指向 repo 外時，寫入會落到 repo 外。
    """
    root_real = os.path.realpath(repo_root)
    bad = []
    for orig in input_files:
        rel = to_repo_relative(orig, repo_root, base_dir)
        abs_path = os.path.join(repo_root, rel)
        real = os.path.realpath(abs_path)
        inside = real == root_real or real.startswith(root_real + os.sep)
        if os.path.islink(abs_path) or not inside:
            bad.append(orig)
    return bad


def _git_stdout(args: List[str], cwd: str) -> Optional[str]:
    """執行 git 並回傳 stdout；失敗（含無法執行）回傳 None。"""
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _repo_worktree_roots(main_root: str) -> Optional[Set[str]]:
    """本 repo 全部 worktree 的 realpath 集合；查詢失敗回傳 None。"""
    out = _git_stdout(["worktree", "list", "--porcelain"], main_root)
    if out is None:
        return None
    return {
        os.path.realpath(line[len("worktree "):])
        for line in out.splitlines()
        if line.startswith("worktree ")
    }


def resolve_repo_root(worktree: Optional[str], main_root: str) -> Optional[str]:
    """解析寫入操作的 repo root。

    未指定 ``worktree`` 回傳 ``main_root``。指定時回傳該路徑的 git toplevel，
    且 toplevel 須出現在 ``main_root`` 的 ``git worktree list --porcelain``
    內；非 git 目錄、不屬本 repo、或查詢失敗皆回傳 None（呼叫端拒絕）。
    """
    if not worktree:
        return main_root
    top = _git_stdout(["rev-parse", "--show-toplevel"], os.path.abspath(worktree))
    if top is None:
        return None
    top = top.strip()
    roots = _repo_worktree_roots(main_root)
    if roots is None or os.path.realpath(top) not in roots:
        return None
    return top
