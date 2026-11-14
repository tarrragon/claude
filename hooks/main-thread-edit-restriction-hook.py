#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Main Thread Edit Restriction Hook - PreToolUse Hook

限制主線程的 Edit/Write 工具使用，防止直接編輯程式碼（預設拒絕安全策略）。
路徑模式定義和權限判斷邏輯見 lib/path_permission.py。

觸發時機: 執行 Edit/Write 工具時
行為: 允許 → exit 0, 拒絕 → exit 2

修改紀錄:
- 新增 feat/* 分支偵測，開發分支跳過限制
- 路徑權限邏輯提取至 lib/path_permission.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))   # .claude/       (lib.*)

from lib import setup_hook_logging, run_hook_safely, get_project_root, save_check_log, read_json_from_stdin, is_subagent_environment, emit_hook_output
# get_project_root（上行，來自 lib/hook_base）用於跨專案放行的 project
# boundary 判斷，worktree 感知是刻意設計。dispatch-active.json 為跨
# worktree 全域狀態，語意不同，改用 git_utils 版本並顯式命名區分
# （見 ARCH-BAL-020）
from lib.git_utils import get_current_branch, is_allowed_branch, find_target_repo, get_target_root, get_project_root as get_dispatch_project_root
from lib.hook_messages import GateMessages
from lib.dispatch_tracker import is_file_under_dispatch
from lib.path_permission import check_file_permission
from lib.checkout_identity import common_dir, is_absolute_path, owning_checkout_root, strip_root_prefix

# Exit Code
EXIT_ALLOW = 0
EXIT_BLOCK = 2

# 受檢的檔案寫入工具（settings.json 對三者各有 matcher 註冊）
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")


def _linked_worktree_root(file_path: str) -> Optional[str]:
    """目標檔案所屬 linked worktree 的根；非 linked worktree 回 None。

    判定：所屬 checkout 根的 .git 為 gitlink 檔，且 common dir 解析到
    另一個主 .git。主 checkout（.git 為目錄）、submodule（無 commondir）、
    相對路徑、解析失敗一律回 None（不套用分支放行，交由 path_permission）。
    回傳根而非檔案目錄：目標檔案的上層目錄可能尚未建立（Write 新目錄）。
    """
    if not is_absolute_path(file_path):
        return None
    root = owning_checkout_root(file_path)
    if root is None or not Path(root, ".git").is_file():
        return None
    common = common_dir(root)
    if common is None or Path(common) == Path(root, ".git").resolve():
        return None
    return root


def _allow_and_exit(logger, reason: str) -> int:
    """輸出允許結果並返回 EXIT_ALLOW"""
    emit_hook_output("PreToolUse", permission_decision="allow", permission_decision_reason=reason)
    return EXIT_ALLOW


def _safe_target_root(file_path: str, payload, original_root, logger):
    """get_target_root 的失效隔離：例外時回 None（沿用原根，判定同修改前），
    同時寫 stderr 與日誌；避免本守衛因新增的解析步驟拋例外而 fail-open。"""
    try:
        return get_target_root(file_path, payload, original_root)
    except Exception as e:
        sys.stderr.write(f"[main-thread-edit-restriction] get_target_root 失敗，沿用原根: {e}\n")
        logger.error(f"get_target_root 失敗，沿用原根: {e}")
        return None


def _check_dispatch_warning(file_path: str, logger, payload: Optional[Dict[str, Any]] = None) -> str:
    """
    檢查檔案是否正在被背景代理人處理，回傳警告訊息或空字串

    業務規則：當檔案允許編輯但正在被背景代理人處理時，
    應發出警告避免主線程和代理人同時修改同一檔案。
    """
    if not file_path:
        return ""

    project_root = get_dispatch_project_root()
    rel_path = file_path
    if is_absolute_path(file_path):
        # 相對化以目標檔所屬 checkout 為根；派發紀錄仍以 project_root 查
        rel_root = _safe_target_root(file_path, payload, project_root, logger) or project_root
        relative = strip_root_prefix(file_path, str(rel_root))
        if relative is not None:
            rel_path = relative

    dispatch = is_file_under_dispatch(project_root, rel_path)
    if not dispatch:
        return ""

    warning = (
        f"[WARNING] 此檔案正在被背景代理人處理 "
        f"(agent: {dispatch.get('agent_description', '?')}, "
        f"ticket: {dispatch.get('ticket_id', '?')})"
    )
    logger.info("Dispatch 衝突警告: %s -> %s", file_path, warning)
    return warning


def main() -> int:
    """
    主入口點

    流程: 初始化 → 讀取輸入 → 工具/分支過濾 → 權限檢查 → dispatch 警告 → 輸出
    """
    logger = setup_hook_logging("main-thread-edit-restriction")

    try:
        logger.info("Main Thread Edit Restriction Hook 啟動")

        # 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)
        if not input_data:
            logger.debug("輸入為空或解析失敗，返回預設允許")
            return _allow_and_exit(logger, "輸入為空，預設允許")

        logger.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False)[:200]}...")

        # 只檢查檔案寫入工具；NotebookEdit 的路徑欄位是 notebook_path
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        if tool_name not in WRITE_TOOLS:
            logger.debug(f"跳過: 工具類型 {tool_name} 不在檢查範圍內")
            return _allow_and_exit(logger, f"工具 {tool_name} 不在檢查範圍")

        # Subagent 跳過：此 Hook 僅限制主線程
        if is_subagent_environment(input_data):
            logger.info(f"subagent 環境（agent_id={input_data.get('agent_id')}），跳過編輯限制")
            return _allow_and_exit(logger, "subagent 不受主線程編輯限制")

        file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        logger.info(f"檢查工具: {tool_name}, 檔案: {file_path}")

        # 開發分支跳過（feat/*, fix/* 等）：僅限目標檔案位於 linked worktree。
        # 主 checkout 開分支不放行——parallel-dispatch 禁止在共用主工作樹切換
        # 或建立分支，若主 checkout 的開發分支也放行，等於鼓勵該繞法。
        worktree_root = _linked_worktree_root(file_path)
        if worktree_root:
            current_branch = get_current_branch(cwd=worktree_root)
            if current_branch and is_allowed_branch(current_branch):
                logger.info(f"linked worktree 的開發分支 '{current_branch}' 上，跳過主線程編輯限制")
                return _allow_and_exit(logger, f"linked worktree 的開發分支 '{current_branch}' 不受主線程編輯限制")

        # 跨專案放行：path_permission 是本專案內部約定（保護 src/ 等）
        # 對外部 repo 套用語意不合理；branch-verify-hook 仍會獨立檢查目標 repo 分支
        if is_absolute_path(file_path):
            target_repo = find_target_repo(file_path)
            try:
                current_root = str(Path(get_project_root()).resolve())
            except Exception:
                current_root = get_project_root()
            if target_repo and target_repo != current_root:
                logger.info(
                    f"跨專案編輯（target_repo={target_repo} != current={current_root}），"
                    f"skip path_permission 檢查"
                )
                return _allow_and_exit(
                    logger,
                    f"跨專案編輯（{target_repo}），不適用本專案 path_permission",
                )

        # 檢查編輯權限
        target_root = _safe_target_root(file_path, input_data, None, logger)
        is_allowed, reason = check_file_permission(
            file_path, logger, str(target_root) if target_root else None
        )

        # Dispatch 衝突警告（僅在允許編輯時檢查）
        decision = "allow" if is_allowed else "deny"
        dispatch_warning = None
        if is_allowed:
            dispatch_warning = _check_dispatch_warning(file_path, logger, input_data) or None

        emit_hook_output(
            "PreToolUse",
            additional_context=dispatch_warning,
            permission_decision=decision,
            permission_decision_reason=reason,
        )

        # 儲存日誌
        log_entry = f"""[{datetime.now().isoformat()}]
  FilePath: {file_path}
  Permission: {"ALLOWED" if is_allowed else "BLOCKED"}
  Reason: {reason}

"""
        save_check_log("main-thread-edit-restriction", log_entry, logger)

        exit_code = EXIT_ALLOW if is_allowed else EXIT_BLOCK
        logger.info(f"Hook 檢查完成，exit code: {exit_code}")
        return exit_code

    except Exception as e:
        logger.error(f"Hook 執行錯誤: {e}")
        emit_hook_output(
            "PreToolUse",
            permission_decision="allow",
            permission_decision_reason=f"Hook 執行錯誤：{str(e)}",
        )
        return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "main-thread-edit-restriction"))
