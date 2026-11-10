#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook 基礎設施層模組

提供 Hook 系統的基礎設施，包括專案根目錄探測等。
此模組是基礎層，不依賴其他 hook_utils 子模組。

核心 API：
- get_project_root() -> Path
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ============================================================================
# 常數定義
# ============================================================================

# 環境變數名稱
ENV_PROJECT_DIR = "CLAUDE_PROJECT_DIR"

# 搜尋深度（從 cwd 向上搜尋 CLAUDE.md 的最大層數）
CLAUDE_MD_SEARCH_DEPTH = 5

# git rev-parse 執行超時時限（秒）
GIT_TOPLEVEL_TIMEOUT = 5

# 測試隔離逃生艙旗標：同語意/同命名慣例於 ticket_system/lib/paths.py 的
# TICKET_SYSTEM_TEST_ISOLATION，此處為 .claude/lib 套件獨立維護的對應旗標，
# 避免兩個不同套件共用同一旗標名稱造成語意混淆（互不相依，各自套件內生效）。
# 僅供測試 fixture 使用，見 .claude/hooks/tests/conftest.py 的
# hook_project_env fixture。
ENV_HOOK_TEST_ISOLATION = "HOOK_TEST_ISOLATION"

# 專案根解析的行程內快取：(cwd, CLAUDE_PROJECT_DIR, HOOK_TEST_ISOLATION) -> 根目錄
_PROJECT_ROOT_CACHE: dict[tuple[str, str | None, str | None], Path] = {}

# 共用狀態根（linked worktree 時的主倉庫根）解析快取：cwd -> 主倉庫根或 None。
# 與 _PROJECT_ROOT_CACHE 獨立，不影響 get_project_root 的快取行為。
_MAIN_REPO_ROOT_CACHE: dict = {}


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


def clear_project_root_cache() -> None:
    """清除專案根解析快取（測試用：同鍵下替換暫存 repo 或替身後須重算）。"""
    _PROJECT_ROOT_CACHE.clear()
    _MAIN_REPO_ROOT_CACHE.clear()


def _find_project_root() -> Path:
    """行程內快取版專案根解析。

    Why：單一 hook 行程內 setup_hook_logging 與 mark_hook_entry 多次解析專案根，
    每次都起 git 子程序（實測每行程 3 次 rev-parse）；同行程內 cwd 與環境變數
    不變時結果恆定。鍵含 cwd、CLAUDE_PROJECT_DIR、HOOK_TEST_ISOLATION，任一改變即重算。
    """
    try:
        cwd = os.getcwd()
    except OSError:
        # cwd 已被刪除：無法組鍵，不快取，維持原解析行為
        return _resolve_project_root()
    key = (
        cwd,
        os.environ.get(ENV_PROJECT_DIR),
        os.environ.get(ENV_HOOK_TEST_ISOLATION),
    )
    cached = _PROJECT_ROOT_CACHE.get(key)
    if cached is None:
        cached = _resolve_project_root()
        _PROJECT_ROOT_CACHE[key] = cached
    return cached


def _resolve_project_root() -> Path:
    """查詢專案根目錄（未快取）

    優先順序：
    0. 測試隔離逃生艙（HOOK_TEST_ISOLATION=1 時）：直接採用
       CLAUDE_PROJECT_DIR，略過 worktree 偵測。僅供測試 fixture 使用（見
       .claude/hooks/tests/conftest.py 的 hook_project_env fixture），
       生產路徑不設此旗標故不受影響。
    1. worktree 感知：當前位於 git linked worktree 時，優先用該 worktree
       的根目錄，避免 CLAUDE_PROJECT_DIR 恆指向主 repo 導致 worktree 內
       的 Hook 動作（append-log 等）洩漏到主 repo（0.38.1-W2-020）
    2. 環境變數 CLAUDE_PROJECT_DIR
    3. git rev-parse --show-toplevel（git-native，支援 worktree）
    4. 從 cwd 向上搜尋 CLAUDE.md（最多 5 層）
    5. Path.cwd() fallback（永不失敗）

    Why（步驟 0 新增背景）：pytest 進程本身在 git linked worktree 內執行時
    （如 agent 在自己的 ticket worktree 內跑整套 hooks 測試），步驟 1 的
    worktree 偵測會蓋過測試刻意注入的 CLAUDE_PROJECT_DIR 隔離（monkeypatch /
    subprocess env 覆寫皆同受影響），使依賴 CLAUDE_PROJECT_DIR 隔離的測試
    誤讀到真實 worktree 根目錄而斷言失敗。與
    ticket_system/lib/paths.py._resolve_project_root() 的步驟 0 同一根因、
    同一修法，唯旗標名稱各自獨立（見 ENV_HOOK_TEST_ISOLATION 常數說明）。

    Returns:
        Path: 專案根目錄路徑
    """
    # 優先級 0：測試隔離逃生艙，僅供 conftest 的 fixture 使用
    if os.environ.get(ENV_HOOK_TEST_ISOLATION) == "1":
        isolated_dir = os.environ.get(ENV_PROJECT_DIR)
        if isolated_dir:
            return Path(isolated_dir)

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
    0. 測試隔離逃生艙（HOOK_TEST_ISOLATION=1 時，僅供測試 fixture 使用）
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


def _main_repo_root_of_linked_worktree() -> Optional[Path]:
    """cwd 在 linked worktree 時回傳主倉庫根（git-common-dir 的父目錄），否則 None。

    非 linked worktree（含非 repo、git 不可用）回 None，屬正常情境。
    已偵測為 linked worktree 但 git-common-dir 查詢失敗時回 None 並寫 stderr
    加 log（quality-baseline 規則 4），呼叫端退回 get_project_root 語意。
    結果依 cwd 快取（每行程至多一次額外 git 子程序）。
    """
    try:
        cwd = os.getcwd()
    except OSError:
        return None
    if cwd in _MAIN_REPO_ROOT_CACHE:
        return _MAIN_REPO_ROOT_CACHE[cwd]
    result_root: Optional[Path] = None
    if _linked_worktree_root() is not None:
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_TOPLEVEL_TIMEOUT,
            )
            out = proc.stdout.strip()
            if proc.returncode == 0 and out:
                result_root = Path(out).parent
            else:
                _report_shared_root_failure("git-common-dir 查詢失敗 rc={}".format(proc.returncode))
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            _report_shared_root_failure("git-common-dir 查詢異常: {}".format(exc))
    _MAIN_REPO_ROOT_CACHE[cwd] = result_root
    return result_root


def _report_shared_root_failure(reason: str) -> None:
    """共用狀態根解析降級：stderr 加 log 雙通道（quality-baseline 規則 4）。"""
    msg = "get_shared_state_root 降級為 get_project_root: {}".format(reason)
    logging.getLogger("hook_base").warning(msg)
    sys.stderr.write(msg + "\n")


def get_shared_state_root(default_root: Optional[Path] = None) -> Path:
    """取得讀取共用狀態（ticket md、dispatch-active.json）應使用的根目錄。

    語意對齊 ticket CLI 的 get_ticket_state_root：
    - HOOK_TEST_ISOLATION=1：直接回 get_project_root()（測試隔離，同 get_project_root）。
    - cwd 在 linked worktree：回主倉庫根（git-common-dir 的父目錄）。
    - 其餘（主倉庫、非 repo、git 不可用）：回 default_root，None 時回 get_project_root()。
    - linked worktree 但 git-common-dir 查詢失敗：同上退回，並寫 stderr 加 log。

    default_root 供呼叫端傳入自己已解析（或被測試替身取代）的專案根。
    get_project_root 的行為與日誌根不受本函式影響。
    """
    fallback = default_root if default_root is not None else get_project_root()
    if os.environ.get(ENV_HOOK_TEST_ISOLATION) == "1":
        return fallback
    main_root = _main_repo_root_of_linked_worktree()
    return main_root if main_root is not None else fallback


def has_parallel_dispatch(
    default_root: Optional[Path] = None, checkout: Optional[Path] = None
) -> bool:
    """是否有活躍並行派發（讀共用狀態根的 dispatch-active.json）。

    讀取根一律經 get_shared_state_root，linked worktree 內讀主倉庫登記檔。
    讀取失敗（含匯入、JSON 損毀）保守視為非並行（fail-open，與既有兩份實作一致）。
    default_root 語意同 get_shared_state_root。
    checkout：命令實際作用的 checkout 根。給定時只計入工作位置與其相同的條目
    （無工作位置欄位的舊條目保守計入）；None（預設）表示作用目標未知，
    不過濾、全數計入。不以 cwd 推定，因 -C／cd 可讓命令作用到別的 checkout。
    """
    try:
        from .dispatch_tracker import (
            filter_dispatches_for_checkout,
            get_active_dispatches,
        )

        dispatches = get_active_dispatches(get_shared_state_root(default_root))
        return len(filter_dispatches_for_checkout(dispatches, checkout)) > 0
    except Exception:
        return False
