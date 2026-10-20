"""checkout 身分判定共用模組（不呼叫 git 子行程）。

由 bash-write-boundary-guard-hook 與 agent-dispatch-validation-hook 共用。
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
