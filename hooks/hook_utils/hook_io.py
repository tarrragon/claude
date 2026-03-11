#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook I/O 操作模組

提供 git 命令執行、stdin JSON 讀取、資料提取和輸入驗證等 I/O 相關功能。

核心 API：
- run_git(args, cwd, timeout, logger)
- read_json_from_stdin(logger)
- extract_tool_input(input_data, logger)
- extract_tool_response(input_data, logger)
- is_handoff_recovery_mode(logger)
- validate_hook_input(input_data, logger, required_fields)
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any


def _extract_field(
    input_data: "dict | None",
    field_name: str,
    logger: "logging.Logger | None" = None
) -> dict:
    """安全提取 input_data 中指定欄位的通用邏輯

    處理三種情況：
    1. input_data 為 None 或空值 → 返回 {}
    2. 指定欄位缺失或為 None → 返回 {}
    3. 欄位為有效的 dict → 返回該 dict

    Args:
        input_data: Hook 輸入資料（dict 或 None）
        field_name: 要提取的欄位名稱（如 "tool_input" 或 "tool_response"）
        logger: 可選 Logger 實例，用於記錄詳細資訊

    Returns:
        dict: 提取出的欄位值（始終返回 dict，無欄位時返回空 dict）
    """
    if input_data is None:
        if logger:
            logger.debug("input_data 為 None，返回空 dict")
        return {}

    if not isinstance(input_data, dict):
        if logger:
            logger.warning("input_data 非 dict 類型，返回空 dict: {}".format(type(input_data)))
        return {}

    field_value = input_data.get(field_name)

    # 欄位為 None 或不存在時返回 {}
    if field_value is None:
        if logger:
            logger.debug("{} 欄位為 None 或不存在，返回空 dict".format(field_name))
        return {}

    # 欄位應為 dict，但可能是其他型別
    if not isinstance(field_value, dict):
        if logger:
            logger.warning("{} 非 dict 類型，返回空 dict: {}".format(field_name, type(field_value)))
        return {}

    if logger:
        logger.debug("成功提取 {}，欄位數: {}".format(field_name, len(field_value)))

    return field_value


def run_git(
    args: List[str],
    cwd: "str | None" = None,
    timeout: int = 5,
    logger: "logging.Logger | None" = None,
) -> "str | None":
    """執行 git 命令並回傳 stdout

    Args:
        args: git 子命令和參數，如 ["log", "-1", "--format=%ct"]
        cwd: 工作目錄（預設為當前目錄）
        timeout: 執行超時秒數（預設 5）
        logger: 可選日誌物件，失敗時記錄 warning

    Returns:
        stdout 輸出（stripped），或 None 若執行失敗
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            if logger:
                logger.warning("git 命令失敗: {} (exit code: {})".format(
                    " ".join(args), result.returncode
                ))
            return None
    except subprocess.TimeoutExpired:
        if logger:
            logger.warning("git 命令超時: {}".format(" ".join(args)))
        return None
    except FileNotFoundError:
        if logger:
            logger.warning("git 命令未找到")
        return None
    except OSError as e:
        if logger:
            logger.warning("執行 git 命令失敗: {}".format(e))
        return None


def read_json_from_stdin(logger: logging.Logger) -> Optional[dict]:
    """從 stdin 讀取 JSON 輸入

    處理三種情況：
    1. 空輸入（SessionStart 等事件無輸入）
    2. JSON 解析失敗
    3. 有效的 JSON 物件

    Args:
        logger: Logger 實例

    Returns:
        dict: 解析後的 JSON，或 None（空輸入或解析失敗）
    """
    try:
        input_text = sys.stdin.read().strip()

        # 空輸入：直接返回 None
        if not input_text:
            return None

        # 解析 JSON
        return json.loads(input_text)

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: {}".format(e))
        return None
    except Exception as e:
        logger.error("讀取 stdin 失敗: {}".format(e))
        return None


def extract_tool_input(
    input_data: "dict | None",
    logger: "logging.Logger | None" = None
) -> dict:
    """安全提取 input_data 中的 tool_input 欄位

    處理三種情況：
    1. input_data 為 None 或空值 → 返回 {}
    2. tool_input 欄位缺失或為 None → 返回 {}
    3. tool_input 為有效的 dict → 返回該 dict

    Args:
        input_data: Hook 輸入資料（dict 或 None）
        logger: 可選 Logger 實例，用於記錄詳細資訊

    Returns:
        dict: 提取出的 tool_input（始終返回 dict，無欄位時返回空 dict）

    Examples:
        >>> extract_tool_input({"tool_input": {"file_path": "test.py"}})
        {'file_path': 'test.py'}

        >>> extract_tool_input({"other": "value"})
        {}

        >>> extract_tool_input(None)
        {}
    """
    return _extract_field(input_data, "tool_input", logger)


def extract_tool_response(
    input_data: "dict | None",
    logger: "logging.Logger | None" = None
) -> dict:
    """安全提取 input_data 中的 tool_response 欄位

    處理三種情況：
    1. input_data 為 None 或空值 → 返回 {}
    2. tool_response 欄位缺失或為 None → 返回 {}
    3. tool_response 為有效的 dict → 返回該 dict

    Args:
        input_data: Hook 輸入資料（dict 或 None）
        logger: 可選 Logger 實例，用於記錄詳細資訊

    Returns:
        dict: 提取出的 tool_response（始終返回 dict，無欄位時返回空 dict）

    Examples:
        >>> extract_tool_response({"tool_response": {"stdout": "OK", "exit_code": 0}})
        {'stdout': 'OK', 'exit_code': 0}

        >>> extract_tool_response({"other": "value"})
        {}

        >>> extract_tool_response(None)
        {}
    """
    return _extract_field(input_data, "tool_response", logger)


# ============================================================================
# Handoff 和輸入驗證
# ============================================================================


def is_handoff_recovery_mode(
    logger: "logging.Logger | None" = None
) -> bool:
    """檢查是否處於 Handoff 恢復模式

    Handoff 恢復時，Claude 自動讀取 Ticket 和派發代理人，
    這些操作應被豁免，允許恢復流程正常進行。

    Args:
        logger: 可選 Logger 實例，用於記錄詳細資訊

    Returns:
        bool: 是否處於 Handoff 恢復模式

    Handoff 恢復模式判斷：
    - 檢查 .claude/handoff/pending 目錄是否存在
    - 目錄內是否有任何 .json 檔案
    """
    try:
        # 嘗試從環境變數或尋找 CLAUDE.md 取得專案根目錄
        from .hook_logging import get_project_root as _get_project_root
        project_root = _get_project_root()
    except Exception:
        # Fallback：使用當前工作目錄
        project_root = Path.cwd()

    handoff_pending_dir = project_root / ".claude" / "handoff" / "pending"

    try:
        # 檢查目錄是否存在且包含 JSON 檔案
        if handoff_pending_dir.exists() and handoff_pending_dir.is_dir():
            # 使用 glob 檢查是否有任何 .json 檔案
            if any(handoff_pending_dir.glob("*.json")):
                if logger:
                    logger.info("檢測到 Handoff 恢復模式")
                return True

        if logger:
            logger.debug("未檢測到 Handoff 恢復模式")
        return False

    except Exception as e:
        if logger:
            logger.warning("檢查 Handoff 恢復模式時發生錯誤: {}".format(e))
        return False


def validate_hook_input(
    input_data: "dict | None",
    logger: "logging.Logger | None" = None,
    required_fields: "Tuple[str, ...] | None" = None
) -> bool:
    """統一的 Hook 輸入驗證函式

    提供通用的 None 防護和欄位檢查，各 Hook 可指定自己的必要欄位。

    Args:
        input_data: Hook 輸入資料
        logger: 可選 Logger 實例
        required_fields: 必要欄位清單（如 ("tool_name", "tool_input")）
                        預設為空，表示只檢查 None 防護

    Returns:
        bool: 輸入是否有效

    Examples:
        # PreToolUse Hook（需要 tool_name 和 tool_input）
        >>> validate_hook_input(input_data, logger, ("tool_name", "tool_input"))

        # UserPromptSubmit Hook（需要 prompt）
        >>> validate_hook_input(input_data, logger, ("prompt",))

        # 只檢查 None 防護
        >>> validate_hook_input(input_data, logger)

    説明：
    - 此函式統一處理 W34-002 修復的 None 防護問題
    - 各 Hook 可根據需要指定檢查的欄位
    """
    # 第一步：None 防護（W34-002 修復）
    if input_data is None:
        if logger:
            logger.error("輸入資料為 None")
        return False

    if not isinstance(input_data, dict):
        if logger:
            logger.error("輸入資料非 dict 型別: {}".format(type(input_data)))
        return False

    # 第二步：欄位檢查（預設無額外欄位要求）
    if required_fields:
        for field in required_fields:
            if field not in input_data:
                if logger:
                    logger.error("缺少必要欄位: {}".format(field))
                return False

            # 欄位不能為 None
            if input_data.get(field) is None:
                if logger:
                    logger.error("欄位為 None: {}".format(field))
                return False

    if logger:
        logger.debug("輸入驗證通過")
    return True
