#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Settings Registration Exec Guard - PostToolUse Hook（攔截面改版）

前身設計以 PreToolUse 監控 settings.json 的 Edit/Write，解析編輯前後的
hooks.*[].hooks[].command 差集，只驗證新增註冊項的可執行位。後續多視角
審查一致判定攔截點選錯層級：

  - 「先寫 settings.json 註冊、後建立 hook 檔案」的合法操作順序下，寫入
    settings.json 當下目標檔案尚不存在，走 fail-open 放行；隨後 Write 建
    立該檔以 100644 落地，完全不受任何檢查（動機事故原狀在此順序下完整
    重現，見底部「動機」段落）。
  - MultiEdit / NotebookEdit 寫入 settings.json 的路徑不受重建編輯前後
    文字的函式覆蓋（該函式的 catch-all 分支對未知 tool_name 靜默回傳
    unchanged，等同放行），而 settings.json 只註冊 Edit 與 Write 兩個
    matcher，MultiEdit 完全無防護。
  - skill hooks（.claude/skills/<skill>/hooks/）既不在 SessionStart 全量
    掃描範圍，也不會被本 hook 複查（差集視為既有項），構成雙方都不管的
    缺口。

本版改以「hook 檔案本身的落地事件」為監控對象，取代「解析 settings.json
差集推導」——不論註冊與建檔的先後順序，只要目標檔案（頂層 .claude/hooks/
或 .claude/skills/<skill>/hooks/ 下的 .py/.sh）透過 Edit/Write/MultiEdit
落地，落地當下即檢查並自動修復可執行位，使前述兩個攔截點問題與範圍缺口
同時消失：settings.json 是否註冊、以何種工具編輯，都不再是判斷依據。此
設計與 hook-completeness-check.py 既有的 `_check_and_fix_permissions`
哲學一致（皆以目錄層級界定監控範圍而非解析 settings.json，避開「已註冊
但本輪尚未 chmod 就被執行」的競態，即權限修復類 hook 共通防護的原始
失效模式）。

Hook Event: PostToolUse
Matcher: Edit, Write, MultiEdit
Decision: 無 deny——PostToolUse 觸發時寫入已完成，無法逆轉本次操作；偵測
到監控範圍內的檔案缺可執行位時直接 chmod +x 自動修復並記錄，取代「事後
才在下個 session 由 SessionStart 掃描修復」的延遲窗口。

覆蓋範圍：
  - .claude/hooks/ 頂層 .py / .sh（非遞迴。tests/、acceptance_checkers/、
    archived/ 等子目錄檔案從不被 shell 直接執行，維持排除——與
    hook-completeness-check.py `_check_and_fix_permissions` 的排除範圍
    一致）
  - .claude/skills/<skill>/hooks/ 下遞迴 .py / .sh（略過 __pycache__、
    .venv、node_modules、.git 等快取/虛擬環境目錄）

不覆蓋（刻意，非遺漏）：
  - NotebookEdit：僅操作 .ipynb，不會落地 .py/.sh hook 檔案，排除不影響
    涵蓋率。
  - Bash 直接建立/移動檔案、git checkout / merge / pull 落地：本 hook 只
    掛 Edit/Write/MultiEdit 三個工具事件，涵蓋 Claude 內建寫檔路徑；shell
    層與 git 層落地仍由 hook-completeness-check.py 的 SessionStart 掃描
    延遲一輪兜底，故非零防護。

動機（一次「守衛註冊即零效力」事故實測）：一個新註冊的 guard hook 自建立
起以 100644（無可執行位）存在，runtime 無法啟動它，事故當下該守衛全期
零效力；而 SessionStart 的 chmod 修復要到下個 session 才被採用。本 hook
使這類缺失在檔案落地的當下即暴露並自動修復，不再遺留至下個 session，且
不受註冊/建檔操作順序影響。

對應規則：.claude/rules/core/quality-baseline.md 規則 3（設計問題立即修正）
"""

import logging
import os
import stat
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))  # .claude/       (lib.*)

try:
    from lib import (
        get_project_root,
        read_json_from_stdin,
        run_hook_safely,
        setup_hook_logging,
    )
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)

EXIT_ALLOW = 0

_MONITORED_TOOL_NAMES = ("Edit", "Write", "MultiEdit")
_HOOK_SCRIPT_SUFFIXES = (".py", ".sh")
_SKILL_HOOK_SKIP_DIRS = frozenset({"__pycache__", ".venv", "node_modules", ".git"})


def _is_top_level_hook_file(resolved: Path, project_root: Path) -> bool:
    """判斷 resolved 是否為 .claude/hooks/ 頂層的 .py/.sh（非遞迴）。

    以父目錄相等判斷，天然排除 tests/、acceptance_checkers/、archived/
    等子目錄——與 hook-completeness-check.py 的非遞迴 glob 排除機制一致。
    """
    hooks_dir = (project_root / ".claude" / "hooks").resolve()
    return resolved.parent == hooks_dir and resolved.suffix in _HOOK_SCRIPT_SUFFIXES


def _is_skill_hook_file(resolved: Path, project_root: Path) -> bool:
    """判斷 resolved 是否位於 .claude/skills/<skill>/hooks/ 下（遞迴，略過快取目錄）。"""
    if resolved.suffix not in _HOOK_SCRIPT_SUFFIXES:
        return False
    skills_dir = (project_root / ".claude" / "skills").resolve()
    try:
        rel_parts = resolved.relative_to(skills_dir).parts
    except ValueError:
        # 控制流轉換，非異常：resolved 不在 skills_dir 之下是絕大多數呼叫的
        # 預期結果（監控範圍外的一般檔案），非執行期錯誤。不記錄日誌——
        # 逐檔記錄會在正常操作中產生大量噪音，且此路徑不代表任何缺陷。
        return False
    # 至少需要 <skill>/hooks/<file> 三段
    if len(rel_parts) < 3 or rel_parts[1] != "hooks":
        return False
    if any(part in _SKILL_HOOK_SKIP_DIRS for part in rel_parts):
        return False
    return True


def is_monitored_hook_path(
    file_path: str, project_root: Path, logger: Optional[logging.Logger] = None
) -> Optional[Path]:
    """判斷 file_path 是否落在監控範圍，是則回傳解析後絕對路徑，否則 None。

    resolve() 會跟隨符號連結至其真實目標——若 .claude/hooks/ 下的檔案是
    指向監控範圍外的符號連結，resolved.parent 將不等於 hooks_dir，判定為
    不受監控（見 `_is_top_level_hook_file`/`_is_skill_hook_file` 的父目錄
    /相對路徑比對邏輯）；這是刻意行為，非遺漏——本 hook 修復的是「實際會被
    runtime 執行的檔案」，符號連結解析後的真實目標才是該檔案。

    logger 為選填：直接呼叫本函式做單元測試時可省略；main() 呼叫時應傳入
    真實 logger，使 resolve() 失敗（見下方 except）能被記錄。
    """
    if not file_path:
        return None
    try:
        resolved = Path(file_path).resolve()
    except OSError as exc:
        # 真實例外（如符號連結解析失敗、系統呼叫層級錯誤），非預期控制流，
        # 依 observability-rules 規則 1 記錄；無 logger 時（如單元測試直接
        # 呼叫）靜默略過，不強制呼叫端一定要傳 logger。
        if logger:
            logger.warning(f"解析路徑失敗，略過本次監控判斷: {file_path} ({exc})")
        return None
    if _is_top_level_hook_file(resolved, project_root) or _is_skill_hook_file(
        resolved, project_root
    ):
        return resolved
    return None


def fix_missing_exec_bit(resolved: Path) -> bool:
    """resolved 存在但缺可執行位時 chmod +x，回傳是否實際執行了修復。

    不存在或已具可執行位（含目錄本身，理論上不會發生但防禦性檢查）一律
    回傳 False，呼叫端據此判斷是否需要記錄與提示。

    chmod() 失敗（如唯讀檔案系統、權限不足）時的 OSError 刻意不在此處
    捕捉——本函式與 main() 皆不吞例外，交由 `run_hook_safely` 的頂層
    例外處理統一記錄 traceback 與 stderr（quality-baseline 規則 4 雙
    通道），避免本函式與 run_hook_safely 各自維護一份錯誤處理邏輯。
    """
    if not resolved.is_file():
        return False
    if os.access(resolved, os.X_OK):
        return False
    current_mode = resolved.stat().st_mode
    resolved.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def main() -> int:
    """主入口。只在 Edit/Write/MultiEdit 落地監控範圍內的 hook 檔案時介入。

    PostToolUse 事件觸發時寫入已完成，本 hook 不 deny（無操作可逆轉），
    僅在偵測到缺可執行位時自動修復並記錄，恆常回傳 EXIT_ALLOW。
    """
    logger = setup_hook_logging("settings-registration-exec-guard")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        logger.debug("輸入為空或解析失敗，無動作")
        return EXIT_ALLOW

    tool_name = input_data.get("tool_name", "")
    if tool_name not in _MONITORED_TOOL_NAMES:
        logger.debug(f"工具 {tool_name} 不在監控範圍（僅 Edit/Write/MultiEdit），無動作")
        return EXIT_ALLOW

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")

    project_root = get_project_root()
    resolved = is_monitored_hook_path(file_path, project_root, logger)
    if resolved is None:
        logger.debug(f"{file_path} 不在 hook 檔案監控範圍，無動作")
        return EXIT_ALLOW

    if fix_missing_exec_bit(resolved):
        msg = (
            f"[SettingsRegistrationExecGuard] 落地當下偵測到 hook 檔案缺可執行位，"
            f"已自動修復: {resolved}"
        )
        logger.warning(msg)
        print(msg, file=sys.stderr)
    else:
        logger.debug(f"{resolved} 已具可執行位或不存在，無需修復")

    return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "settings-registration-exec-guard"))
