#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
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
from typing import Dict, Any

# 設置 sys.path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from hook_utils import setup_hook_logging, run_hook_safely, get_project_root, save_check_log, read_json_from_stdin, is_subagent_environment, emit_hook_output
from git_utils import get_current_branch, is_allowed_branch
from lib.hook_messages import GateMessages
from lib.dispatch_tracker import is_file_under_dispatch
from lib.path_permission import check_file_permission

# Exit Code
EXIT_ALLOW = 0
EXIT_BLOCK = 2


def _allow_and_exit(logger, reason: str) -> int:
    """輸出允許結果並返回 EXIT_ALLOW"""
    emit_hook_output("PreToolUse", permission_decision="allow", permission_decision_reason=reason)
    return EXIT_ALLOW


def _check_dispatch_warning(file_path: str, logger) -> str:
    """
    檢查檔案是否正在被背景代理人處理，回傳警告訊息或空字串

    業務規則：當檔案允許編輯但正在被背景代理人處理時，
    應發出警告避免主線程和代理人同時修改同一檔案。
    """
    if not file_path:
        return ""

    project_root = get_project_root()
    rel_path = file_path
    if file_path.startswith("/"):
        try:
            rel_path = str(Path(file_path).relative_to(project_root))
        except ValueError:
            pass

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

        # 只檢查 Edit 和 Write 工具
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        if tool_name not in ["Edit", "Write"]:
            logger.debug(f"跳過: 工具類型 {tool_name} 不在檢查範圍內")
            return _allow_and_exit(logger, f"工具 {tool_name} 不在檢查範圍")

        # Subagent 跳過：此 Hook 僅限制主線程
        if is_subagent_environment(input_data):
            logger.info(f"subagent 環境（agent_id={input_data.get('agent_id')}），跳過編輯限制")
            return _allow_and_exit(logger, "subagent 不受主線程編輯限制")

        file_path = tool_input.get("file_path", "")
        logger.info(f"檢查工具: {tool_name}, 檔案: {file_path}")

        # 開發分支跳過（feat/*, fix/* 等）
        file_dir = str(Path(file_path).parent) if file_path and file_path.startswith("/") else None
        current_branch = get_current_branch(cwd=file_dir)
        if current_branch and is_allowed_branch(current_branch):
            logger.info(f"開發分支 '{current_branch}' 上，跳過主線程編輯限制")
            return _allow_and_exit(logger, f"開發分支 '{current_branch}' 不受主線程編輯限制")

        # 檢查編輯權限
        is_allowed, reason = check_file_permission(file_path, logger)

        # Dispatch 衝突警告（僅在允許編輯時檢查）
        decision = "allow" if is_allowed else "deny"
        dispatch_warning = None
        if is_allowed:
            dispatch_warning = _check_dispatch_warning(file_path, logger) or None

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
