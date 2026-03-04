#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Handoff 交接檔案自動清理 Hook

在 ticket track complete 命令執行成功後，自動清理對應 Ticket ID 的交接檔案。

功能:
1. 監聽 PostToolUse Hook (Bash 工具)
2. 識別 'ticket track complete' 成功的執行
3. 解析被完成的 Ticket ID
4. 清理 pending/ 和 archive/ 中的對應交接檔案
5. 記錄清理結果到日誌

輸入格式:
    PostToolUse Hook 提供的 JSON (stdin)
    - tool_name: "Bash"
    - tool_input: {"command": "..."}
    - tool_response: {"stdout": "...", "stderr": "..."}

環境變數:
    CLAUDE_PROJECT_DIR: 專案根目錄
    HOOK_DEBUG: 啟用詳細日誌 (true/false)

使用方式:
    PostToolUse Hook 自動觸發，或手動測試:
    echo '{"tool_name":"Bash","tool_input":{"command":"ticket track complete 0.31.0-W7-012"},"tool_response":{"stdout":"[OK] 已完成 Ticket 0.31.0-W7-012"}}' | python3 .claude/hooks/handoff-cleanup-hook.py
"""

import sys
import json
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# 全域常數
EXIT_SUCCESS = 0
EXIT_ERROR = 1

# Ticket ID 格式正則 (支援子任務格式：0.31.0-W7-012.1.2)
TICKET_ID_PATTERN = r'\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*'

def get_project_root() -> Path:
    """
    取得專案根目錄

    Returns:
        Path - 專案根目錄
    """
    import os

    project_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if project_dir:
        return Path(project_dir)

    # Fallback: 使用 git 查找
    try:
        result = __import__("subprocess").run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except Exception:
        return Path.cwd()

def is_complete_command_success(input_data: Dict[str, Any], logger) -> bool:
    """
    判斷是否為 'ticket track complete' 命令成功執行

    PostToolUse Hook 會提供的結構:
    {
        "tool_name": "Bash",
        "tool_input": {"command": "ticket track complete 0.31.0-W7-012"},
        "tool_response": {
            "stdout": "[OK] 已完成 Ticket 0.31.0-W7-012",
            "stderr": "",
            "exit_code": 0
        }
    }

    Args:
        input_data: PostToolUse Hook 的輸入資料

    Returns:
        bool - 是否為成功的 complete 命令
    """
    if not input_data:
        return False

    # 檢查工具名稱
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug(f"工具非 Bash: {tool_name}")
        return False

    # 檢查命令內容
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "ticket track complete" not in command:
        logger.debug(f"命令非 ticket track complete: {command}")
        return False

    # 檢查執行結果 (exit code 0 或輸出包含成功標記)
    tool_response = input_data.get("tool_response", {})
    stdout = tool_response.get("stdout", "")
    stderr = tool_response.get("stderr", "")
    exit_code = tool_response.get("exit_code", -1)

    # 成功判斷：exit code = 0 且輸出包含成功標記
    is_success = (exit_code == 0) and ("[OK]" in stdout or "已完成" in stdout or "completed" in stdout.lower())

    if is_success:
        logger.info(f"檢測到成功的 complete 命令")
        return True

    logger.debug(f"命令未成功: exit_code={exit_code}, stdout={stdout}")
    return False

def extract_ticket_ids(input_data: Dict[str, Any], logger) -> List[str]:
    """
    從輸入資料中提取 Ticket ID

    嘗試從命令和輸出中提取所有可能的 Ticket ID

    Args:
        input_data: PostToolUse Hook 的輸入資料

    Returns:
        list - 找到的 Ticket ID 清單
    """
    ticket_ids = set()

    if not input_data:
        return list(ticket_ids)

    # 從命令中提取
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")
    logger.debug(f"掃描命令: {command}")
    matches = re.findall(TICKET_ID_PATTERN, command)
    ticket_ids.update(matches)

    # 從輸出中提取
    tool_response = input_data.get("tool_response", {})
    stdout = tool_response.get("stdout", "")
    stderr = tool_response.get("stderr", "")

    logger.debug(f"掃描輸出 stdout: {stdout[:200]}")
    matches = re.findall(TICKET_ID_PATTERN, stdout)
    ticket_ids.update(matches)

    if stderr:
        logger.debug(f"掃描輸出 stderr: {stderr[:200]}")
        matches = re.findall(TICKET_ID_PATTERN, stderr)
        ticket_ids.update(matches)

    logger.info(f"提取到 {len(ticket_ids)} 個 Ticket ID: {ticket_ids}")
    return sorted(list(ticket_ids))

def cleanup_handoff_files(project_root: Path, ticket_id: str, logger) -> Tuple[bool, Dict[str, Any]]:
    """
    清理指定 Ticket ID 的交接檔案

    檢查並清理以下路徑中的檔案:
    - .claude/handoff/pending/{ticket_id}.json
    - .claude/handoff/archive/{ticket_id}.json

    Args:
        project_root: 專案根目錄
        ticket_id: Ticket ID (e.g., "0.31.0-W7-012")

    Returns:
        tuple - (成功標誌, 清理結果字典)
    """
    result = {
        "ticket_id": ticket_id,
        "pending_cleaned": False,
        "archive_cleaned": False,
        "pending_path": None,
        "archive_path": None,
        "errors": []
    }

    try:
        # 檢查並清理 pending 檔案
        pending_file = project_root / ".claude" / "handoff" / "pending" / f"{ticket_id}.json"
        if pending_file.exists():
            try:
                pending_file.unlink()
                result["pending_cleaned"] = True
                result["pending_path"] = str(pending_file)
                logger.info(f"已清理 pending 檔案: {pending_file}")
            except Exception as e:
                error_msg = f"刪除 pending 檔案失敗 ({pending_file}): {e}"
                logger.warning(error_msg)
                result["errors"].append(error_msg)
        else:
            logger.debug(f"pending 檔案不存在: {pending_file}")

        # 檢查並清理 archive 檔案
        archive_file = project_root / ".claude" / "handoff" / "archive" / f"{ticket_id}.json"
        if archive_file.exists():
            try:
                archive_file.unlink()
                result["archive_cleaned"] = True
                result["archive_path"] = str(archive_file)
                logger.info(f"已清理 archive 檔案: {archive_file}")
            except Exception as e:
                error_msg = f"刪除 archive 檔案失敗 ({archive_file}): {e}"
                logger.warning(error_msg)
                result["errors"].append(error_msg)
        else:
            logger.debug(f"archive 檔案不存在: {archive_file}")

        is_success = result["pending_cleaned"] or result["archive_cleaned"]
        if is_success:
            logger.info(f"成功清理 Ticket {ticket_id} 的交接檔案")
        else:
            logger.info(f"Ticket {ticket_id} 沒有交接檔案需要清理")

        return True, result

    except Exception as e:
        error_msg = f"清理 Ticket {ticket_id} 的交接檔案時發生錯誤: {e}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
        return False, result

def generate_hook_output(cleanup_results: List[Dict[str, Any]], logger) -> Dict[str, Any]:
    """
    生成 Hook 輸出格式

    清理完成後，不顯示詳細資訊給用戶，只在日誌中記錄

    Args:
        cleanup_results: 清理結果列表

    Returns:
        dict - Hook 輸出 JSON
    """
    # 統計清理結果
    total_cleaned = sum(1 for r in cleanup_results if r["pending_cleaned"] or r["archive_cleaned"])
    total_errors = sum(len(r["errors"]) for r in cleanup_results)

    logger.info(f"清理完成: {total_cleaned} 個 Ticket 的交接檔案已清理, {total_errors} 個錯誤")

    # 返回靜默輸出（不打擾用戶）
    return {
        "suppressOutput": True
    }

def generate_summary_log(project_root: Path, cleanup_results: List[Dict[str, Any]], logger) -> None:
    """
    生成清理摘要日誌

    在 hook-logs/handoff-cleanup/ 目錄中產生詳細的清理報告

    Args:
        project_root: 專案根目錄
        cleanup_results: 清理結果列表
    """
    log_dir = project_root / ".claude" / "hook-logs" / "handoff-cleanup"

    # 產生詳細報告檔案
    report_file = log_dir / f"cleanup-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_tickets": len(cleanup_results),
                    "cleaned": sum(1 for r in cleanup_results if r["pending_cleaned"] or r["archive_cleaned"]),
                    "errors": sum(len(r["errors"]) for r in cleanup_results)
                },
                "details": cleanup_results
            }, f, ensure_ascii=False, indent=2)

        logger.debug(f"清理報告已保存: {report_file}")
    except Exception as e:
        logger.warning(f"保存清理報告失敗: {e}")

def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化日誌
    2. 讀取 JSON 輸入（PostToolUse Hook）
    3. 判斷是否為 complete 命令成功
    4. 若是，提取 Ticket ID
    5. 為每個 Ticket ID 清理交接檔案
    6. 產生 Hook 輸出
    7. 輸出 JSON 結果

    Returns:
        int - Exit code (0 = 成功)
    """
    logger = setup_hook_logging("handoff-cleanup")
    try:
        # 步驟 1: 初始化日誌
        logger.info("Handoff 清理 Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)

        # 步驟 3: 判斷是否為 complete 命令成功
        if not is_complete_command_success(input_data, logger):
            logger.debug("本次執行不觸發清理邏輯")
            return EXIT_SUCCESS  # 靜默返回

        # 步驟 4: 取得專案根目錄
        project_root = get_project_root()
        logger.info(f"專案根目錄: {project_root}")

        # 步驟 5: 提取 Ticket ID
        ticket_ids = extract_ticket_ids(input_data, logger)
        if not ticket_ids:
            logger.warning("無法從命令輸出中提取 Ticket ID")
            return EXIT_SUCCESS

        logger.info(f"待清理的 Ticket: {ticket_ids}")

        # 步驟 6: 清理交接檔案
        cleanup_results = []
        for ticket_id in ticket_ids:
            success, result = cleanup_handoff_files(project_root, ticket_id, logger)
            cleanup_results.append(result)

        # 步驟 7: 產生摘要報告
        generate_summary_log(project_root, cleanup_results, logger)

        # 步驟 8: 產生 Hook 輸出
        hook_output = generate_hook_output(cleanup_results, logger)

        # 步驟 9: 輸出 JSON 結果
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        logger.info("Handoff 清理 Hook 執行完成")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        # 錯誤時也靜默跳過（非阻塊）
        print(json.dumps({
            "suppressOutput": True
        }, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS

if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "handoff-cleanup"))
