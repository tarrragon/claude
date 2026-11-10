"""框架檔案執行權限判定（sync-pull / sync-push 共用）。

判準：檔案首兩個位元組為 `#!`（shebang）即視為可執行檔，應帶 +x；
非 shebang 檔案的權限一律不動。

Why：舊判準以目錄名（hooks/）加 settings.json 反查為邊界，hooks/ 外的
shebang 腳本（scripts/、skills/<name>/scripts/ 等）在上游以 100644 追蹤時，
pull 後失去執行權限，以 ./script 呼叫即 permission denied（tarrragon/claude#21）。
shebang 是檔案自身宣告「要被直接執行」的唯一來源，不依賴目錄慣例或註冊清單。

pull 與 push 匯入同一判定函式，兩端判準不會漂移。

匯入方式（呼叫端需先把 .claude/ 加入 sys.path）：

    from lib.executable_bits import iter_shebang_files, restore_shebang_exec_bits
"""

from __future__ import annotations

import os
from pathlib import Path

from lib.sync_exclude_manifest import should_exclude

SHEBANG_PREFIX = b"#!"

# 走訪時一律跳過的目錄名：git 中繼資料（push 端的 root 是 clone 的 repo 根）
_ALWAYS_SKIP_DIR_NAMES = frozenset({".git"})


def has_shebang(path: Path) -> bool:
    """判斷檔案首兩個位元組是否為 shebang（`#!`）。

    參數:
        path: 檔案路徑

    傳回:
        bool: 首兩個位元組為 `#!` 時為 True；讀取失敗視為 False
    """
    try:
        with path.open("rb") as handle:
            return handle.read(len(SHEBANG_PREFIX)) == SHEBANG_PREFIX
    except OSError:
        # 讀不到的檔案不屬判定對象（不改其權限），略過
        return False


def _is_skipped(item: Path, rel: Path) -> bool:
    return item.name in _ALWAYS_SKIP_DIR_NAMES or item.is_symlink() or should_exclude(rel)


def iter_shebang_files(root: Path):
    """走訪 root 下同步範圍內、首行為 shebang 的一般檔案。

    排除規則（下探前剪枝）：.git、符號連結、should_exclude 命中者
    （hook-logs、.venv、__pycache__ 等 local-only 內容不屬同步範圍）。

    參數:
        root: 掃描根目錄（pull 端為 .claude，push 端為待推送的 repo 樹）

    產出:
        Path: 每個首行為 shebang 的檔案絕對路徑
    """
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        dirnames[:] = [
            name for name in dirnames
            if not _is_skipped(base / name, (base / name).relative_to(root))
        ]
        for filename in filenames:
            path = base / filename
            if _is_skipped(path, path.relative_to(root)) or not path.is_file():
                continue
            if has_shebang(path):
                yield path


def restore_shebang_exec_bits(root: Path) -> int:
    """對 root 下所有 shebang 檔案加上 +x（u/g/o 皆加），非 shebang 檔案不動。

    參數:
        root: 掃描根目錄

    傳回:
        int: 實際變更 mode 的檔案數（已可執行者不計）
    """
    count = 0
    for path in iter_shebang_files(root):
        mode = path.stat().st_mode
        new_mode = mode | 0o111
        if new_mode != mode:
            path.chmod(new_mode)
            count += 1
    return count
