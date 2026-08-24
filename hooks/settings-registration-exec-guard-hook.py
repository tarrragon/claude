#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Settings Registration Exec Guard - PostToolUse Hook（2026-08-22 降級版）

前身兩版沿革：
  1. 初版以 PreToolUse 解析 settings.json 編輯前後差集，只驗證新增註冊項，
     覆蓋範圍有攔截點層級問題（先寫註冊、後建立檔案的順序下漏檢）。
  2. 攔截面改版（本檔案名沿用至今）改以「hook 檔案落地事件」為監控對象，
     偵測到 .claude/hooks/ 頂層或 .claude/skills/<skill>/hooks/ 下的 .py/.sh
     經 Edit/Write/MultiEdit 落地且缺可執行位時，自動 chmod +x 修復。設計前提：
     settings.json 若以裸路徑（`$CLAUDE_PROJECT_DIR/.claude/hooks/foo.py`）
     註冊，Claude Code 依 shebang 直接執行該檔，缺可執行位會使該 hook 全期
     零效力。

本版降級理由（2026-08-22）：settings.json 全部 hook 註冊已改為顯式解譯器
形式（`uv run --quiet <path>` 或 `python3 <path>`，實測無裸路徑殘留），可
執行位不再是 hook 被 runtime 呼叫的前提——`uv run` 與 `python3` 皆以直譯器
讀檔執行，不依賴檔案本身的 exec bit。舊版描述的失效模式（裸路徑 shebang
執行 + 無 exec bit -> Permission denied）在此前提下不再成立。

本版行為：保留 PostToolUse Edit/Write/MultiEdit 三個 matcher 的既有註冊
（本次降級執行環境無法變更 settings.json 註冊內容，完全停用需另行由具
足夠權限的操作者移除註冊，已另行追蹤，不在本次變更範圍內處理）。偵測邏輯
保留（沿用 `is_monitored_hook_path` 判斷落地檔案是否屬 hook 範圍），但不
再 chmod、不再印出 WARNING——因為「缺可執行位」在顯式解譯器前提下已非會
導致 hook 失效的問題，維持原本的自動修復語意會製造假急迫性（可見性要求
應對應真實失敗，非已消除根因的歷史徵狀）。偵測結果改以 `logger.info` 記錄，
供未來稽核仍可能產生 644 hook 檔案的路徑（如跨平台 mode 遺失）是否重現，
不寫 stderr、不變更檔案。

Hook Event: PostToolUse
Matcher: Edit, Write, MultiEdit
Decision: 恆常 EXIT_ALLOW（PostToolUse 觸發時寫入已完成，無操作可逆轉；
降級後不再有任何檔案系統副作用）。

覆蓋範圍（沿用攔截面改版邏輯，未變更）：
  - .claude/hooks/ 頂層 .py / .sh（非遞迴。tests/、acceptance_checkers/、
    archived/ 等子目錄檔案從不被直譯器直接執行，維持排除）
  - .claude/skills/<skill>/hooks/ 下遞迴 .py / .sh（略過 __pycache__、
    .venv、node_modules、.git 等快取/虛擬環境目錄）

不覆蓋（刻意，非遺漏）：
  - NotebookEdit：僅操作 .ipynb，不會落地 .py/.sh hook 檔案。
  - Bash 直接建立/移動檔案、git checkout / merge / pull 落地：本 hook 只
    掛 Edit/Write/MultiEdit 三個工具事件。

對應規則：.claude/rules/core/quality-baseline.md 規則 3（設計問題立即修正）
"""

import logging
import os
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
    /相對路徑比對邏輯）；這是刻意行為，非遺漏——本 hook 觀察的是「實際會被
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


def main() -> int:
    """主入口。只在 Edit/Write/MultiEdit 落地監控範圍內的 hook 檔案時介入。

    降級版：偵測到缺可執行位時僅記錄 info 日誌供稽核，不再 chmod、不再印出
    stderr WARNING——顯式解譯器註冊已消除「缺可執行位導致 hook 失效」的
    前提，維持舊版自動修復語意會製造假急迫性。恆常回傳 EXIT_ALLOW
    （PostToolUse 事件不可逆轉，本版亦無任何副作用）。
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

    if resolved.is_file() and not os.access(resolved, os.X_OK):
        logger.info(
            f"[SettingsRegistrationExecGuard] 偵測到 hook 檔案缺可執行位（僅記錄，"
            f"不自動修復，因 settings.json 皆以顯式解譯器呼叫，可執行位非執行"
            f"前提）: {resolved}"
        )
    else:
        logger.debug(f"{resolved} 已具可執行位或不存在，無需處理")

    return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "settings-registration-exec-guard"))
