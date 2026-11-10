#!/usr/bin/env python3
"""
cleanup 附帶清理：移除 WorkspacePath 指向已刪 worktree 的 Xcode DerivedData 目錄

Xcode 為每個 workspace 在 DerivedData 下建一個目錄，並在其 info.plist 記錄 WorkspacePath。
worktree 移除後該目錄不會被 Xcode 回收（iOS 專案每個約 400MB）。只刪 WorkspacePath 位於
該 worktree 內者；其他目錄、非 macOS、DerivedData 不存在時一律不動。
"""

import os
import plistlib
import shutil
import sys
from pathlib import Path

# 兩者皆為測試注入點：cleanup 呼叫時不帶參數，測試替換模組屬性
DERIVED_DATA_ROOT = Path.home() / "Library" / "Developer" / "Xcode" / "DerivedData"
PLATFORM = sys.platform
_INFO_PLIST = "info.plist"
_WORKSPACE_KEY = "WorkspacePath"


def _path_forms(path: str) -> set:
    """路徑的絕對形式與解析符號連結後的形式（macOS 的 /tmp 實為 /private/tmp）。"""
    return {os.path.abspath(path), os.path.realpath(path)}


def _is_inside(candidate: str, roots: set) -> bool:
    forms = _path_forms(candidate)
    return any(f == r or f.startswith(r + os.sep) for f in forms for r in roots)


def _workspace_path(entry: Path):
    """讀 entry/info.plist 的 WorkspacePath；不是 Xcode 產生或讀不到時回 None。"""
    try:
        with open(entry / _INFO_PLIST, "rb") as fh:
            value = plistlib.load(fh).get(_WORKSPACE_KEY)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None  # CompilationCache.noindex 等無 info.plist 的目錄：不屬比對對象，略過
    return value if isinstance(value, str) else None


def find_derived_data_for(worktree_path: str, root: Path = None) -> list:
    """回傳 WorkspacePath 位於 worktree_path 內的 DerivedData 目錄（不跟隨符號連結）。"""
    root = DERIVED_DATA_ROOT if root is None else root
    if not root.is_dir():
        return []
    roots = _path_forms(worktree_path)
    matches = []
    for entry in sorted(root.iterdir()):
        if entry.is_symlink() or not entry.is_dir():
            continue
        workspace = _workspace_path(entry)
        if workspace and _is_inside(workspace, roots):
            matches.append(entry)
    return matches


def remove_derived_data_for(worktree_path: str, root: Path = None, platform: str = None) -> list:
    """刪除比對成功的 DerivedData 目錄，回傳給使用者的結果行；無對象時回空 list。

    刪除失敗只回報、不影響 cleanup 結果：worktree 與分支已移除，DerivedData 屬附帶清理。
    """
    if (platform or PLATFORM) != "darwin":
        return []
    lines = []
    for entry in find_derived_data_for(worktree_path, root):
        try:
            shutil.rmtree(entry)
            lines.append(f"  已移除 DerivedData：{entry}")
        except OSError as exc:
            sys.stderr.write(f"[WARNING] DerivedData 移除失敗：{entry}（{exc}）\n")
            lines.append(f"  [WARNING] DerivedData 未移除：{entry}（{exc}）")
    return lines
