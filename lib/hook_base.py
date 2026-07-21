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
import sys
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

def _linked_worktree_root() -> Path | None:
    """偵測當前 cwd 是否位於 git 的「linked worktree」（git worktree add 建立），
    若是則回傳該 worktree 的根目錄；否則回傳 None。

    判據（git-native）：linked worktree 的 `--git-dir`（worktree 私有 .git 目錄）
    與 `--git-common-dir`（主 repo 共享 .git）不同；主 repo 本身兩者相同。
    此判據精確區分「真的在 worktree 中」與「只是 cwd 在主 repo」，
    避免誤把主 repo 當 worktree 而覆蓋 CLAUDE_PROJECT_DIR（與
    .claude/skills/ticket/ticket_system/lib/paths.py 同判據，
    Hook 層 worktree 洩漏修復，0.38.1-W2-020）。

    Returns:
        Path | None: linked worktree 根目錄；非 worktree / git 不可用時回傳 None
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir", "--git-common-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TOPLEVEL_TIMEOUT
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # git 不可用 / 超時：無法判斷，視為非 worktree
        return None

    if result.returncode != 0:
        return None

    lines = result.stdout.strip().split("\n")
    if len(lines) < 2:
        return None

    # git 可能一個回絕對路徑、另一個回相對路徑（取決於 cwd 在 repo 的深度），
    # 兩者可能指向同一目錄。必須 resolve 為真實絕對路徑再比較，否則
    # 主 repo 子目錄會因字串不同被誤判為 linked worktree。
    git_dir = Path(lines[0].strip()).resolve()
    git_common_dir = Path(lines[1].strip()).resolve()
    # 主 repo：git_dir == git_common_dir；linked worktree：兩者不同
    if git_dir == git_common_dir:
        return None

    try:
        toplevel_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TOPLEVEL_TIMEOUT
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if toplevel_result.returncode != 0:
        return None

    return Path(toplevel_result.stdout.strip())


def _find_project_root() -> Path:
    """查詢專案根目錄

    優先順序：
    1. worktree 感知：當前位於 git linked worktree 時，優先用該 worktree
       的根目錄，避免 CLAUDE_PROJECT_DIR 恆指向主 repo 導致 worktree 內
       的 Hook 動作（append-log 等）洩漏到主 repo（0.38.1-W2-020）
    2. 環境變數 CLAUDE_PROJECT_DIR
    3. git rev-parse --show-toplevel（git-native，支援 worktree）
    4. 從 cwd 向上搜尋 CLAUDE.md（最多 5 層）
    5. Path.cwd() fallback（永不失敗）

    Returns:
        Path: 專案根目錄路徑
    """
    # 優先級 1：worktree 感知（優先於 CLAUDE_PROJECT_DIR）
    worktree_root = _linked_worktree_root()
    if worktree_root is not None:
        return worktree_root

    # 優先級 2：環境變數
    env_dir = os.getenv(ENV_PROJECT_DIR)
    if env_dir:
        return Path(env_dir)

    # 優先級 3：git rev-parse --show-toplevel（worktree 修復的關鍵）
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TOPLEVEL_TIMEOUT
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # git 命令不存在或超時，進入 fallback
        pass

    # 優先級 4：搜尋 CLAUDE.md（從 cwd 向上）
    current_dir = Path.cwd()
    for _ in range(CLAUDE_MD_SEARCH_DEPTH):
        if (current_dir / "CLAUDE.md").exists():
            return current_dir

        # 檢查是否已到達檔案系統根目錄
        parent = current_dir.parent
        if parent == current_dir:
            break

        current_dir = parent

    # 優先級 5：Fallback 到 cwd
    return Path.cwd()


# ============================================================================
# 公開 API
# ============================================================================

def ensure_utf8_io() -> None:
    """強制 Hook 的 stdin/stdout/stderr 使用 UTF-8 編碼。

    跨平台必要性（Windows 特別關鍵）：
    - Windows 預設 console codepage 為 cp950（繁中）/ cp936（簡中）/ cp437（英文）
    - Python 未強制 UTF-8 時，stdin/stdout/stderr 用 locale codepage
    - 導致 Hook 解析 Claude Code 傳入的 UTF-8 JSON 失敗，或中文輸出亂碼
    - 更嚴重：異常寫 stderr 時若 stderr 也是 cp950，可能二次失敗產生空輸出
      （「Failed with non-blocking status code: No stderr output」）

    此函式於 Hook 入口呼叫一次即可。使用 Python 3.7+ 的 reconfigure API。
    若平台/版本不支援 reconfigure，則靜默略過（避免因編碼設定失敗阻斷 Hook 執行）。

    Note:
        此函式不拋出例外。呼叫失敗時預設行為不變。
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, AttributeError):
            # 某些環境（如 pytest 捕獲的 stream、已設定的 stream）不支援 reconfigure
            continue


def get_project_root() -> Path:
    """取得專案根目錄

    優先順序：
    1. worktree 感知：當前位於 git linked worktree 時，優先用該 worktree 根目錄
    2. 環境變數 CLAUDE_PROJECT_DIR
    3. git rev-parse --show-toplevel（git-native，支援 worktree）
    4. 從 cwd 向上搜尋 CLAUDE.md（最多 5 層）
    5. Path.cwd() fallback（永不失敗）

    Returns:
        Path: 專案根目錄路徑

    Note:
        此函式不拋出例外。所有失敗情況均有 fallback。
        worktree 環境下 git rev-parse 策略確保路徑正確。
    """
    return _find_project_root()
