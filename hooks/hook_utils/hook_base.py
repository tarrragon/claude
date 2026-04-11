#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook 基礎設施層模組

提供 Hook 系統的基礎設施，包括專案根目錄探測等。
此模組是基礎層，不依賴其他 hook_utils 子模組。

核心 API：
- get_project_root() -> Path
"""

import os
import subprocess
from pathlib import Path

# ============================================================================
# 常數定義
# ============================================================================

# 環境變數名稱
ENV_PROJECT_DIR = "CLAUDE_PROJECT_DIR"

# 搜尋深度（從 cwd 向上搜尋 CLAUDE.md 的最大層數）
CLAUDE_MD_SEARCH_DEPTH = 5

# git rev-parse 執行超時時限（秒）
GIT_TOPLEVEL_TIMEOUT = 5


# ============================================================================
# 內部輔助函式
# ============================================================================

def _find_project_root() -> Path:
    """查詢專案根目錄

    優先順序：
    1. 環境變數 CLAUDE_PROJECT_DIR
    2. git rev-parse --show-toplevel（git-native，支援 worktree）
    3. 從 cwd 向上搜尋 CLAUDE.md（最多 5 層）
    4. Path.cwd() fallback（永不失敗）

    Returns:
        Path: 專案根目錄路徑
    """
    # 優先級 1：環境變數
    env_dir = os.getenv(ENV_PROJECT_DIR)
    if env_dir:
        return Path(env_dir)

    # 優先級 2：git rev-parse --show-toplevel（worktree 修復的關鍵）
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=GIT_TOPLEVEL_TIMEOUT
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # git 命令不存在或超時，進入 fallback
        pass

    # 優先級 3：搜尋 CLAUDE.md（從 cwd 向上）
    current_dir = Path.cwd()
    for _ in range(CLAUDE_MD_SEARCH_DEPTH):
        if (current_dir / "CLAUDE.md").exists():
            return current_dir

        # 檢查是否已到達檔案系統根目錄
        parent = current_dir.parent
        if parent == current_dir:
            break

        current_dir = parent

    # 優先級 4：Fallback 到 cwd
    return Path.cwd()


# ============================================================================
# 公開 API
# ============================================================================

def get_project_root() -> Path:
    """取得專案根目錄

    優先順序：
    1. 環境變數 CLAUDE_PROJECT_DIR
    2. git rev-parse --show-toplevel（git-native，支援 worktree）
    3. 從 cwd 向上搜尋 CLAUDE.md（最多 5 層）
    4. Path.cwd() fallback（永不失敗）

    Returns:
        Path: 專案根目錄路徑

    Note:
        此函式不拋出例外。所有失敗情況均有 fallback。
        worktree 環境下 git rev-parse 策略確保路徑正確。
    """
    return _find_project_root()
