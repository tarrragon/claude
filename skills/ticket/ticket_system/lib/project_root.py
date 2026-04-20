"""專案根目錄解析工具（Ticket 0.18.0-W11-001.1.1）。

提供跨命令共用的 ``resolve_project_cwd`` helper，解析 Git 倉庫根目錄；
當 Git 指令不可用（非 git 倉庫、git 未安裝、權限問題等）時，fallback
到當前工作目錄。

設計理由：
    claim 命令的 AC 驗證 subprocess 需固定 cwd 為專案根，避免因呼叫者
    所在目錄影響 shell 命令（例如 ``npm test`` 需在專案根執行）。
    本 helper 提升至 ``lib/`` 便於未來其他命令共用（saffron 建議）。
"""
from __future__ import annotations

import os
import subprocess


# git 查詢專案根的指令（保留為模組常數方便測試 patch 對齊）
_GIT_TOPLEVEL_CMD = ["git", "rev-parse", "--show-toplevel"]


def resolve_project_cwd() -> str:
    """解析專案根目錄。

    優先使用 ``git rev-parse --show-toplevel`` 取得 Git 倉庫根；若 Git
    呼叫失敗（非 git 倉庫、git 未安裝、subprocess 錯誤等），fallback 到
    ``os.getcwd()``。

    Returns:
        專案根目錄的絕對路徑字串（已 strip 尾端換行）。
    """
    try:
        result = subprocess.run(
            _GIT_TOPLEVEL_CMD,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        # git 不可用時 fallback 到當前工作目錄
        return os.getcwd()
