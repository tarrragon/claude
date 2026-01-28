#!/usr/bin/env python3
"""
Hook 輸入輸出處理

提供統一的 Hook JSON 輸入讀取和輸出生成功能。
消除各 Hook 檔案中的重複程式碼。

主要功能:
- read_hook_input: 從 stdin 讀取 Hook 輸入
- write_hook_output: 輸出 Hook 結果到 stdout
- create_pretooluse_output: 建立 PreToolUse Hook 輸出
- create_posttooluse_output: 建立 PostToolUse Hook 輸出
"""

import json
import sys
from typing import Any, Optional


def read_hook_input() -> dict:
    """
    從 stdin 讀取 Hook 輸入

    Returns:
        dict: 解析後的 JSON 資料，解析失敗時返回空字典

    Example:
        input_data = read_hook_input()
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
    """
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}


def write_hook_output(output: dict, ensure_ascii: bool = False, indent: int = 2) -> None:
    """
    輸出 Hook 結果到 stdout

    Args:
        output: 要輸出的字典
        ensure_ascii: 是否確保 ASCII 編碼（預設 False 以支援中文）
        indent: JSON 縮排空格數

    Example:
        write_hook_output({"decision": "allow", "reason": "OK"})
    """
    print(json.dumps(output, ensure_ascii=ensure_ascii, indent=indent))


def create_pretooluse_output(
    decision: str,
    reason: str,
    user_prompt: Optional[str] = None,
    system_message: Optional[str] = None,
    suppress_output: bool = False
) -> dict:
    """
    建立 PreToolUse Hook 輸出格式

    Args:
        decision: 決策結果 ("allow" | "deny" | "ask")
        reason: 決策原因說明
        user_prompt: 詢問用戶的訊息（僅當 decision 為 "ask" 時使用）
        system_message: 系統訊息（可選）
        suppress_output: 是否抑制輸出（預設 False）

    Returns:
        dict: 標準 PreToolUse Hook 輸出格式

    Example:
        output = create_pretooluse_output(
            decision="ask",
            reason="在保護分支上編輯",
            user_prompt="是否繼續在 main 分支上編輯？"
        )
        write_hook_output(output)
    """
    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }

    if user_prompt:
        output["hookSpecificOutput"]["userPrompt"] = user_prompt

    if system_message:
        output["systemMessage"] = system_message

    if suppress_output:
        output["suppressOutput"] = True

    return output


def create_posttooluse_output(
    decision: str,
    reason: str,
    additional_context: Optional[str] = None
) -> dict:
    """
    建立 PostToolUse Hook 輸出格式

    Args:
        decision: 決策結果 ("allow" | "block")
        reason: 決策原因說明
        additional_context: 額外上下文資訊（可選）

    Returns:
        dict: 標準 PostToolUse Hook 輸出格式

    Example:
        output = create_posttooluse_output(
            decision="allow",
            reason="檢測通過",
            additional_context="## 檢測報告\n..."
        )
        write_hook_output(output)
    """
    output: dict[str, Any] = {
        "decision": decision,
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse"
        }
    }

    if additional_context:
        output["hookSpecificOutput"]["additionalContext"] = additional_context

    return output


def create_simple_output(decision: str, reason: str = "") -> dict:
    """
    建立簡單的 Hook 輸出格式

    Args:
        decision: 決策結果 ("approve" | "allow" | "block" | "deny")
        reason: 決策原因說明（可選）

    Returns:
        dict: 簡單的輸出格式

    Example:
        output = create_simple_output("approve")
        write_hook_output(output)
    """
    output = {"decision": decision}
    if reason:
        output["reason"] = reason
    return output
