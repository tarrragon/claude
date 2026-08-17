"""共用 `.claude/lib/` 動態載入與 git toplevel 解析工具。

收斂五處近乎相同的複本（`lease.py` 與 `track_activity.py` /
`track_onboard.py` / `track_sessions.py` / `track_conflicts.py` /
`track_hook_health.py`）：各自維護一份 `_find_claude_dir()` + `_load_*()`
lazy import pair，僅檢查的 marker 檔名與載入的模組名稱不同。本模組抽出
共用實作，呼叫端只需傳入欲載入的模組名稱；marker 預設為
`f"{module_name}.py"`（載入前驗證該檔案自身存在，語意上比原本部分複本
「檢查另一個不相關模組的檔名」更直接）。

快取以 `(marker, module_name)` 為 key，跨呼叫端共用同一 sys.path 插入與
importlib 快取，避免重複 I/O 與重複插入 sys.path。

`resolve_toplevel` 額外抽出 git toplevel 字串解析的核心算法（git
rev-parse --show-toplevel + Path(...).resolve() + str()），供已有自己的
git 執行 callable（供既有測試 mock 邊界延續）的呼叫端（如
`track_sessions.py` 的 `_run_git`）復用；無既有 callable 的呼叫端可直接用
`current_project_root()`（自帶 git_utils 優先、subprocess 降級的預設執行器）。
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

_MODULE_CACHE: Dict[Tuple[str, str], Any] = {}

DEFAULT_MARKER = "pm_registry.py"


def find_claude_dir(marker: str = DEFAULT_MARKER) -> Optional[Path]:
    """依優先序定位 .claude/ 目錄：

    1. `CLAUDE_PROJECT_DIR` 環境變數
    2. cwd 向上搜尋
    3. 開發環境 fallback（本檔位於
       `.claude/skills/ticket/ticket_system/lib/claude_lib_loader.py`，
       `parents[4]` 回推至 `.claude/`；`commands/` 下的呼叫端與 `lib/`
       同深度，故此 fallback 對兩者皆正確，與各複本原有的
       `Path(__file__).resolve().parents[4]` 語意一致）

    Args:
        marker: 候選目錄下 `lib/{marker}` 是否存在的驗證檔名。任何確定
            共同存在於 `.claude/lib/` 的檔案皆可作為存在性驗證信號，不
            要求與後續實際載入的模組同名（`load_claude_lib` 預設會傳入
            `f"{module_name}.py"`，兩者通常一致）。
    """
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        candidate = Path(env_root) / ".claude"
        if (candidate / "lib" / marker).is_file():
            return candidate

    for d in [Path.cwd(), *Path.cwd().parents]:
        candidate = d / ".claude"
        if (candidate / "lib" / marker).is_file():
            return candidate

    try:
        dev_candidate = Path(__file__).resolve().parents[4]
        if (dev_candidate / "lib" / marker).is_file():
            return dev_candidate
    except (IndexError, OSError):
        pass

    return None


def load_claude_lib(module_name: str, marker: Optional[str] = None) -> Optional[Any]:
    """Lazy 載入 `.claude/lib/<module_name>.py`（首次呼叫時 import + 快取）。

    找不到 .claude/ 目錄時回傳 None，呼叫端負責降級（不阻擋主流程，與各
    複本原有降級語意一致）。

    Args:
        module_name: 欲載入的 `.claude/lib/` 模組名稱（不含 `.py`）。
        marker: 存在性驗證檔名；預設 `f"{module_name}.py"`（驗證即將載入
            的檔案自身存在）。
    """
    effective_marker = marker or f"{module_name}.py"
    cache_key = (effective_marker, module_name)
    if cache_key in _MODULE_CACHE:
        return _MODULE_CACHE[cache_key]

    claude_dir = find_claude_dir(effective_marker)
    if claude_dir is None:
        return None

    if str(claude_dir) not in sys.path:
        sys.path.insert(0, str(claude_dir))

    module = importlib.import_module(f"lib.{module_name}")
    _MODULE_CACHE[cache_key] = module
    return module


# ---------------------------------------------------------------------------
# git toplevel 解析（收斂 lease.py / track_sessions.py 原本各自實作的
# 「取得當前 git toplevel 絕對路徑字串」helper；`resolve_toplevel` 為核心
# 算法，`current_project_root` 為自帶預設執行器的便利入口）
# ---------------------------------------------------------------------------


def resolve_toplevel(run_git: Callable[..., Optional[str]]) -> Optional[str]:
    """給定一個「執行 git 命令並回傳 trimmed stdout 或 None」的 callable，
    解析 git toplevel 絕對路徑字串（同 Registry Schema 契約 v1「project:
    <git toplevel 絕對路徑>」欄位語意，供同專案篩選 / FRESH session 比對
    使用）。

    呼叫端各自決定「如何執行 git 命令」（既有測試 mock 邊界不變——如
    session 清單命令的 `_current_project_root` 改為
    `resolve_toplevel(_run_git)`，`_run_git` 本身維持既有實作與既有測試
    直接 patch 該名稱的能力）。
    """
    toplevel = run_git("rev-parse", "--show-toplevel")
    if not toplevel:
        return None
    return str(Path(toplevel).resolve())


def _default_run_git(*args: str, timeout: int = 5) -> Optional[str]:
    """預設 git 執行器：優先透過 `git_utils.run_git_command`（帶
    `--no-optional-locks`，避免與並行 PM session 競爭 `.git/index.lock`）；
    `.claude/lib/` 不可用時降級為原生 `subprocess.run`（同既有 fallback
    設計，維持不強制依賴 `.claude/lib/` 的韌性）。
    """
    git_utils = load_claude_lib("git_utils")
    if git_utils is not None:
        ok, output = git_utils.run_git_command(list(args), timeout=timeout)
        return output.strip() if ok else None

    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def current_project_root() -> Optional[str]:
    """取得當前 git toplevel 絕對路徑字串，自帶預設 git 執行器
    （`_default_run_git`）。供無既有 git 執行 callable 可注入的呼叫端
    直接使用。

    刻意不採 `ticket_system.lib.paths.get_project_root()`——後者
    `CLAUDE_PROJECT_DIR` 優先於 git toplevel 的解析順序，會使比對鍵與
    其他純 git-toplevel 語意的呼叫端分歧（registry `project` 欄位比對
    需逐字一致，見 Registry Schema 契約 v1）。
    """
    return resolve_toplevel(_default_run_git)


# ---------------------------------------------------------------------------
# registry 空骨架工廠（收斂三處相同字面：registry 讀取失敗時的降級 fallback）
# ---------------------------------------------------------------------------


def empty_registry_skeleton() -> Dict[str, Any]:
    """回傳全新的空 registry 骨架字典（`schema_version=0, sessions={}`）。

    每次呼叫回傳新物件（非共用可變狀態的模組常數），供 registry 讀取失敗 /
    不可用時的降級 fallback 使用，避免呼叫端意外共享同一個可變 dict 造成
    跨呼叫污染。
    """
    return {"schema_version": 0, "sessions": {}}


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
