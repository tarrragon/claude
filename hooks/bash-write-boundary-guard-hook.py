#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Bash Write Boundary Guard Hook - PreToolUse Hook

main-thread-edit-restriction-hook.py 僅註冊於 PreToolUse 的 Edit/Write/MultiEdit
matcher，禁止主線程（PM）寫入 test/、lib/、*.dart。該限制可被 Bash 寫入操作
（heredoc / cat > / cat >> / tee / sed -i / python 內嵌腳本 open() / cp / mv）
完全繞過，繞過後無留痕、無法事後偵測（來源分析結論：職責邊界執法類 guard，
繞過後不可事後偵測，須以 PreToolUse 層攔截，不能靠事後補救）。本 hook 是該
缺口的補網。

觸發時機: 執行 Bash 工具時
行為: 偵測到明確寫入 test/、lib/、*.dart 的 Bash 語法 → 轉呼
      lib/path_permission.check_file_permission() 判斷 → 不允許則 DENY（exit 2）；
      未偵測到明確寫入目標 → 一律 ALLOW（保守白名單策略，fail-open）。

範圍與 main-thread-edit-restriction-hook.py 部分一致：
- Subagent 環境跳過（此限制僅約束主線程）
- 開發分支（feat/*、fix/* 等）跳過
- 不含跨專案判斷：Bash command 無單一 file_path，無法用
  find_target_repo() 判斷目標 repo；candidate path 皆以當前
  CLAUDE_PROJECT_DIR 正規化，跨專案 Bash 寫入若剛好命中
  test/lib/dart pattern 仍會被攔（已知的偏保守行為，優先度低於
  漏放）

偵測形態：
- cat > path / cat >> path（含 heredoc 重導向 `cat > path <<'EOF' ... EOF`）
- tee path / tee -a path
- sed -i ... path / sed --in-place ... path（原地編輯目標）
- python -c / python3 heredoc 內嵌腳本中的 open('path', ...) 呼叫
- cp src dst / mv src dst（目的地路徑）
- 一般輸出重導向 > path / >> path（排除檔案描述符重導向 2>、&>）

FP 邊界（fail-open，保守白名單原則）：
路徑抽取為正則啟發式，非完整 shell parse。抽出候選路徑後僅在正規化後
命中 test/、lib/、*.dart 才轉呼判斷邏輯；未命中或無法辨識寫入語法一律
放行，不做「default deny」。此舉刻意犧牲部分漏網率換取低誤判率——本
hook 目標是補網主線程職責邊界（僅 test/、lib/、*.dart 這條缺口），不是
取代 check_file_permission 的完整權限判斷。
"""

import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))   # .claude/       (lib.*)

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, is_subagent_environment, emit_hook_output
from lib.git_utils import get_current_branch, is_allowed_branch
from lib.path_permission import check_file_permission, normalize_path

EXIT_ALLOW = 0
EXIT_BLOCK = 2


# ============================================================================
# 候選寫入目標路徑抽取（正則啟發式，非完整 shell parse）
# ============================================================================

# 一般輸出重導向：> path / >> path，排除檔案描述符重導向（2>、&>、>&）
# 箭頭本身用 non-capturing group，維持與其他 pattern 一致的 group(2)=path 慣例
_REDIRECT_PATTERN = re.compile(r'(?<![\d&])(?:>{1,2})(?!&)\s*([\'"]?)([^\s\'"|&;)<]+)\1')

# tee [-a] path
_TEE_PATTERN = re.compile(r'\btee\s+(?:-a\s+)?([\'"]?)([^\s\'"|&;)]+)\1')

# sed -i / --in-place ... path（跳過可選的空引號參數與 s/// 表達式，取下一個 token）
_SED_I_PATTERN = re.compile(
    r"sed\s+(?:-i|--in-place)(?:\s*'')?\s+(?:'[^']*'|\"[^\"]*\"|\S+)\s+"
    r"([\'\"]?)([^\s\'\"|&;)]+)\1"
)

# cp / mv src dst（簡化：取緊接在來源後的下一個 token 作目的地，不處理多來源/遞迴旗標的複雜排列）
_CP_MV_PATTERN = re.compile(
    r'\b(?:cp|mv)\b(?:\s+-\S+)*\s+\S+\s+([\'"]?)([^\s\'"|&;)]+)\1'
)

# python open('path', ...) / open("path", ...)
_OPEN_CALL_PATTERN = re.compile(r"open\(\s*(['\"])([^'\"]+)\1")


def _extract_candidate_paths(command: str) -> List[str]:
    """
    從 Bash 命令抽取所有候選寫入目標路徑（正則啟發式）。

    刻意不排除 heredoc body / 引號內容——python 內嵌腳本的 open() 呼叫、
    heredoc 傳入的 shell 腳本本身就是要偵測的寫入路徑，落在這些區段內
    的候選路徑必須納入掃描（與 bash-edit-guard-hook.py 的裸 cd 偵測邏輯
    相反：那邊要排除腳本內容，這裡要包含）。

    Returns:
        List[str] - 候選路徑清單（未去重、未正規化）
    """
    candidates: List[str] = []
    for pattern in (
        _REDIRECT_PATTERN,
        _TEE_PATTERN,
        _SED_I_PATTERN,
        _CP_MV_PATTERN,
        _OPEN_CALL_PATTERN,
    ):
        for match in pattern.finditer(command):
            candidates.append(match.group(2))
    return candidates


def _find_boundary_violation(command: str, logger) -> Optional[str]:
    """
    掃描命令的所有候選寫入路徑，回傳第一個命中 test/、lib/、*.dart 且
    check_file_permission 判定不允許的正規化路徑；無命中回傳 None。

    Args:
        command: Bash 命令
        logger: hook logger

    Returns:
        Optional[str] - 命中的正規化路徑，或 None
    """
    for raw_path in _extract_candidate_paths(command):
        normalized = normalize_path(raw_path)

        # 窄化門檻：僅 test/、lib/、*.dart 才進一步判斷（本票範圍，
        # 避免抽取雜訊觸發 check_file_permission 的 default-deny 分支）
        is_target_scope = (
            normalized.startswith("test/")
            or normalized.startswith("lib/")
            or normalized.endswith(".dart")
        )
        if not is_target_scope:
            continue

        is_allowed, reason = check_file_permission(raw_path, logger)
        if not is_allowed:
            logger.warning(
                "偵測到 Bash 寫入職責邊界違規: path=%s reason=%s command=%s",
                normalized, reason, command,
            )
            return normalized

    return None


def _allow_and_exit(logger, reason: str) -> int:
    emit_hook_output("PreToolUse", permission_decision="allow", permission_decision_reason=reason)
    return EXIT_ALLOW


def main() -> int:
    """
    主入口點

    流程: 初始化 → 讀取輸入 → 工具/subagent/分支/跨專案過濾 → 候選路徑抽取
          → 命中則轉呼 check_file_permission → 輸出
    """
    logger = setup_hook_logging("bash-write-boundary-guard")

    logger.info("Bash Write Boundary Guard Hook 啟動")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        logger.debug("輸入為空或解析失敗，返回預設允許")
        return _allow_and_exit(logger, "輸入為空，預設允許")

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    if tool_name != "Bash":
        logger.debug(f"跳過: 工具類型 {tool_name} 不是 Bash")
        return _allow_and_exit(logger, f"工具 {tool_name} 不在檢查範圍")

    # Subagent 跳過：此 Hook 是 main-thread-edit-restriction 的 Bash 補網，
    # 僅限制主線程
    if is_subagent_environment(input_data):
        logger.info(f"subagent 環境（agent_id={input_data.get('agent_id')}），跳過 Bash 寫入邊界限制")
        return _allow_and_exit(logger, "subagent 不受主線程 Bash 寫入邊界限制")

    command = tool_input.get("command", "")
    if not command:
        return _allow_and_exit(logger, "command 為空，允許")

    # 開發分支跳過（feat/*, fix/* 等），與 main-thread-edit-restriction 一致
    current_branch = get_current_branch()
    if current_branch and is_allowed_branch(current_branch):
        logger.info(f"開發分支 '{current_branch}' 上，跳過 Bash 寫入邊界限制")
        return _allow_and_exit(logger, f"開發分支 '{current_branch}' 不受主線程 Bash 寫入邊界限制")

    violation_path = _find_boundary_violation(command, logger)

    if violation_path is None:
        logger.debug("未偵測到明確的 test/lib/dart 寫入目標，允許（fail-open）")
        return _allow_and_exit(logger, "未偵測到職責邊界違規的 Bash 寫入形態")

    reason = (
        f"偵測到 Bash 寫入職責邊界違規（path={violation_path}）。"
        "主線程禁止透過 Bash（cat/tee/sed -i/python open()/cp/mv/heredoc 等）"
        "寫入 test/、lib/、*.dart，等同繞過 main-thread-edit-restriction-hook.py "
        "的職責邊界執法。請改派代理人執行此寫入。"
    )
    emit_hook_output(
        "PreToolUse",
        permission_decision="deny",
        permission_decision_reason=reason,
    )
    logger.info("Hook 檢查完成，exit code: %d", EXIT_BLOCK)
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "bash-write-boundary-guard"))
