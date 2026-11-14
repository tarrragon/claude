"""checkout 身分判定共用模組（不呼叫 git 子行程）。

由 bash-write-boundary-guard-hook、agent-dispatch-validation-hook、
lib/path_permission 與 ticket-file-access-guard-hook 共用；根前綴比對
一律經 strip_root_prefix（分隔符、磁碟機代號大小寫、目錄邊界）。
解析失敗一律回傳 None / False，呼叫端據此落在阻擋側。
"""

import os
from typing import Optional


def common_dir(checkout_root: str) -> Optional[str]:
    """checkout 的 git common dir（不呼叫 git 子行程）；無法解析回傳 None。

    .git 為目錄 → 該目錄；.git 為 gitlink 檔 → 讀 gitdir 指向的目錄，
    其 commondir 檔（相對該目錄）回到主 .git。
    """
    dot_git = os.path.join(checkout_root, ".git")
    try:
        if os.path.isdir(dot_git):
            return os.path.realpath(dot_git)
        with open(dot_git, encoding="utf-8") as fh:
            first = fh.readline().strip()
        if not first.startswith("gitdir:"):
            return None
        gitdir = first[len("gitdir:"):].strip()
        if not os.path.isabs(gitdir):
            gitdir = os.path.join(checkout_root, gitdir)
        gitdir = os.path.realpath(gitdir)
        with open(os.path.join(gitdir, "commondir"), encoding="utf-8") as fh:
            common = fh.readline().strip()
        common = common if os.path.isabs(common) else os.path.join(gitdir, common)
        common = os.path.realpath(common)
        return common if os.path.isdir(common) else None
    except OSError:
        return None  # 解析失敗：視為不同 repo（呼叫端落在阻擋側）


def same_repo(root_a: str, root_b: str) -> bool:
    """兩個 checkout 根目錄是否屬同一 repository（common dir 相同且可解析）。"""
    a = common_dir(root_a)
    return a is not None and a == common_dir(root_b)


def _is_drive_path(path: str) -> bool:
    """已統一為正斜線的 Windows 磁碟機絕對路徑（如 C:/...）。"""
    return len(path) > 2 and path[0].isalpha() and path[1:3] == ":/"


def is_absolute_path(path: str) -> bool:
    """POSIX 絕對路徑或 Windows 磁碟機絕對路徑（反斜線先統一為正斜線）。

    取代各呼叫點的 startswith("/")：後者把 C:/... 當成相對路徑，使目標 repo
    與所在分支的偵測在 Windows 上全數略過。
    """
    if not isinstance(path, str) or not path:
        return False
    normalized = path.replace("\\", "/")
    return normalized.startswith("/") or _is_drive_path(normalized)


def strip_root_prefix(path: str, root: str) -> Optional[str]:
    """path 位於 root 之下時回傳相對路徑（正斜線、無開頭斜線），否則回傳 None。

    三件事同時處理，避免各呼叫點各自 startswith 而漏掉其中一項：
    - 分隔符：兩側反斜線一律轉為正斜線。
    - 磁碟機代號：任一側為磁碟機路徑時比對前折疊大小寫（Claude Code 與 git
      回傳的代號大小寫可能不同）；POSIX 路徑逐字比對。
    - 目錄邊界：root 之後須為字串結尾或 "/"，`/a/proj2/x` 不在 `/a/proj` 之下。
    path 等於 root 時回傳空字串。root 為空或非字串時回傳 None（不在根之下），
    由呼叫端既有的預設分支處理。
    """
    if not isinstance(path, str) or not isinstance(root, str):
        return None
    norm_path = path.replace("\\", "/")
    norm_root = root.replace("\\", "/").rstrip("/")
    if not norm_root:
        return None
    if _is_drive_path(norm_path) or _is_drive_path(norm_root + "/"):
        cmp_path, cmp_root = norm_path.lower(), norm_root.lower()
    else:
        cmp_path, cmp_root = norm_path, norm_root
    if cmp_path == cmp_root:
        return ""
    if not cmp_path.startswith(cmp_root + "/"):
        return None
    return norm_path[len(norm_root) + 1:].lstrip("/")


def strip_same_repo_checkout_prefix(path: str, project_root: str) -> Optional[str]:
    """path 落在與 project_root 同 repo 的另一個 checkout（如相鄰 worktree）時，
    回傳相對該 checkout 根的路徑；不同 repo、找不到 checkout 或解析失敗回傳 None。

    供「依專案相對路徑樣式判定」的守衛使用：主 checkout session 對相鄰
    worktree 內檔案的操作，應與對主 checkout 內同一相對路徑的操作同樣判定。
    """
    if not isinstance(path, str) or not path or not project_root:
        return None
    try:
        owner = owning_checkout_root(path)
        if owner is None or not same_repo(owner, str(project_root)):
            return None
    except (OSError, ValueError):
        # 純檔案系統查詢，不呼叫 git、無逾時；路徑含非法字元等解析失敗
        # 一律視為不同 repo（回 None），與找不到 checkout 同一側
        return None
    return strip_root_prefix(path, owner)


def owning_checkout_root(abs_path: str) -> Optional[str]:
    """目標路徑所屬 checkout 根：自 dirname 向上找第一個存在的祖先，再找含 .git 者。"""
    cur = os.path.dirname(abs_path)
    while not os.path.isdir(cur):
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
