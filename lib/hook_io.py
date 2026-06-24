#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook 輸入輸出處理（SSOT）

提供統一的 Hook JSON 輸入讀取、git 命令執行、資料提取、輸入驗證和輸出生成功能。
消除各 Hook 檔案中的重複程式碼。

本模組為 lib/ 與 hook_utils/hook_io 整併後的單一 SSOT（0.37.0-W6-005）：
保留 lib 既有的 read_hook_input / create_* 輸出建構函式，並吸收 hook_utils
獨有的 git / 提取 / 驗證 / 輸出生成函式；同名 read_json_from_stdin 採 hook_utils 版。

主要功能:
- read_hook_input / read_json_from_stdin: 從 stdin 讀取 Hook 輸入
- run_git: 執行 git 命令
- extract_tool_input / extract_tool_response: 安全提取欄位
- validate_hook_input / validate_tool_input: 輸入驗證
- write_hook_output / generate_hook_output / emit_hook_output: 輸出生成
- create_pretooluse_output / create_posttooluse_output / create_simple_output: 輸出建構
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.hook_base import get_project_root


_VALID_EFFORT_LEVELS = ("low", "medium", "high")


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


def read_json_from_stdin(logger: logging.Logger) -> Optional[dict]:
    """從 stdin 讀取 JSON 輸入（SSOT，採 hook_utils 版）

    與 read_hook_input 的差異：本函式以 logger 記錄解析失敗，並在空輸入 / 解析
    失敗時回傳 None（read_hook_input 回傳空 dict）。供需要區分「無輸入」與「空
    物件」的 hook script 使用（如 markdown_formatter 以 None 短路 sys.exit(0)）。

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
        logger.info("JSON 解析跳過（stdin 含控制字元）: {}".format(e))
        return None
    except Exception as e:
        logger.info("讀取 stdin 跳過: {}".format(e))
        return None


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


# ============================================================================
# 快取變數（模組級，用於效能改善）
# ============================================================================

_handoff_recovery_cache: Optional[bool] = None
"""Process-level 快取：is_handoff_recovery_mode() 的結果（同一 session 內快取）"""


def clear_handoff_recovery_cache() -> None:
    """清空 Handoff 恢復模式快取（測試輔助函式）

    將 _handoff_recovery_cache 重設為 None，
    供測試隔離或其他需要重新掃描的場景使用。

    生產環境不應呼叫此函式。
    """
    global _handoff_recovery_cache
    _handoff_recovery_cache = None


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


def get_effort_level(
    payload: "dict | None" = None,
    default: str = "medium",
) -> str:
    """取得當前 effort level（v2.1.133+ effort 感知）

    優先序：payload['effort']['level'] > $CLAUDE_EFFORT > default

    回傳值正規化為 low / medium / high，未知值降為 default。

    Args:
        payload: hook stdin JSON payload（可為 None）
        default: 預設值，當無訊號時使用

    Returns:
        str: "low" / "medium" / "high"
    """
    level: Optional[str] = None
    if isinstance(payload, dict):
        effort = payload.get("effort")
        if isinstance(effort, dict):
            raw = effort.get("level")
            if isinstance(raw, str) and raw.strip():
                level = raw.strip().lower()

    if level is None:
        env_val = os.environ.get("CLAUDE_EFFORT")
        if env_val and env_val.strip():
            level = env_val.strip().lower()

    if level not in _VALID_EFFORT_LEVELS:
        return default if default in _VALID_EFFORT_LEVELS else "medium"
    return level


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
    """檢查是否處於 Handoff 恢復模式（快取版本）

    Handoff 恢復時，Claude 自動讀取 Ticket 和派發代理人，
    這些操作應被豁免，允許恢復流程正常進行。

    本函式使用 Process-level 快取：
    - 首次呼叫：執行 glob 掃描，快取結果
    - 後續呼叫：直接返回快取結果，避免重複 I/O

    Args:
        logger: 可選 Logger 實例，用於記錄詳細資訊

    Returns:
        bool: 是否處於 Handoff 恢復模式

    Handoff 恢復模式判斷：
    - 檢查 .claude/handoff/pending 目錄是否存在
    - 目錄內是否有任何 .json 檔案
    """
    global _handoff_recovery_cache

    # 快取命中：直接返回快取結果
    if _handoff_recovery_cache is not None:
        if logger:
            logger.debug("使用快取的 Handoff 恢復模式結果: {}".format(_handoff_recovery_cache))
        return _handoff_recovery_cache

    project_root = get_project_root()

    handoff_pending_dir = project_root / ".claude" / "handoff" / "pending"

    try:
        # 檢查目錄是否存在且包含 JSON 檔案
        if handoff_pending_dir.exists() and handoff_pending_dir.is_dir():
            # 使用 glob 檢查是否有任何 .json 檔案
            if any(handoff_pending_dir.glob("*.json")):
                if logger:
                    logger.info("檢測到 Handoff 恢復模式")
                _handoff_recovery_cache = True
                return True

        if logger:
            logger.debug("未檢測到 Handoff 恢復模式")
        _handoff_recovery_cache = False
        return False

    except Exception as e:
        if logger:
            logger.warning("檢查 Handoff 恢復模式時發生錯誤: {}".format(e))
        # 錯誤時快取 False（安全預設）
        _handoff_recovery_cache = False
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
    - 此函式統一處理 None 防護問題
    - 各 Hook 可根據需要指定檢查的欄位
    """
    # 第一步：None 防護
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


def validate_tool_input(
    tool_input: dict,
    logger: "logging.Logger | None" = None,
    required_fields: "Tuple[str, ...] | None" = None
) -> bool:
    """驗證 tool_input 的必要欄位

    呼叫前應確保 tool_input 已由 validate_hook_input() 驗證存在。
    此函式只檢查 tool_input 內的子欄位。

    Args:
        tool_input: tool_input dict（已驗證存在）
        logger: 可選 Logger 實例，允許 None（靜默模式）
        required_fields: tool_input 必須包含的欄位清單，如 ("file_path", "content")
                        預設為 None，表示只做存在性確認（寬鬆驗證）

    Returns:
        bool: tool_input 子欄位驗證是否通過

    Examples:
        # 使用流程：先驗證頂層欄位，再驗證 tool_input 子欄位
        >>> if not validate_hook_input(input_data, logger, ("tool_name", "tool_input")):
        ...     return False
        >>> tool_input = input_data["tool_input"]
        >>> if not validate_tool_input(tool_input, logger, ("file_path", "content")):
        ...     return False
    """
    # 防禦性檢查：tool_input 本身
    if not isinstance(tool_input, dict):
        if logger:
            logger.error("tool_input 非 dict 型別: {}".format(type(tool_input)))
        return False

    # 欄位驗證
    if required_fields:
        for field in required_fields:
            if field not in tool_input:
                if logger:
                    logger.error("tool_input 缺少必要欄位: {}".format(field))
                return False
            if tool_input.get(field) is None:
                if logger:
                    logger.error("tool_input 欄位值為 None: {}".format(field))
                return False

    if logger:
        logger.debug("tool_input 驗證通過")
    return True


def is_subagent_environment(input_data: "dict | None") -> bool:
    """檢查是否為 subagent 環境

    subagent 執行時，Hook 會在 input_data 中包含 agent_id 欄位。
    此函式用於 Hook 的早期跳過邏輯，避免在 subagent 中輸出 AskUserQuestion 提醒。

    Args:
        input_data: Hook 收到的 input_data dict

    Returns:
        bool: 如果 input_data 包含 agent_id（非空），返回 True；否則返回 False

    Examples:
        >>> if is_subagent_environment(input_data):
        ...     logger.info("偵測到 subagent 環境，跳過 AskUserQuestion 提醒")
        ...     print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        ...     return EXIT_SUCCESS
    """
    if input_data is None:
        return False
    return bool(input_data.get("agent_id"))


def is_background_dispatch(tool_input: "dict | None") -> bool:
    """檢查是否為背景代理人派發（run_in_background=true）

    背景代理人的 PostToolUse(Agent) 在代理人「啟動完成」（agentId 返回）時觸發，
    而非「工作完成」時。所有依賴「工作完成」語義的 PostToolUse(Agent) 類 Hook
    必須使用此 helper 在背景路徑跳過完成判定邏輯，避免誘發 PM 誤判（PC-070 根因）。

    真正的完成訊號應由 task-notification 事件（或對應 Hook event）處理。

    Args:
        tool_input: PostToolUse 的 tool_input dict（來自 input_data["tool_input"]）

    Returns:
        bool: 若 tool_input.run_in_background 為 truthy，回傳 True；否則 False。

    Examples:
        >>> tool_input = extract_tool_input(input_data, logger)
        >>> if is_background_dispatch(tool_input):
        ...     logger.info("背景代理人啟動，跳過完成判定邏輯")
        ...     return EXIT_SUCCESS

    相關 Ticket：0.18.0-W10-024（active-dispatch-tracker-hook 首例）、
    0.18.0-W10-060（其他 PostToolUse(Agent) Hook 套用）
    """
    if not tool_input:
        return False
    return bool(tool_input.get("run_in_background", False))


# ============================================================================
# Hook 輸出生成
# ============================================================================


def generate_hook_output(
    hook_event_name: str,
    additional_context: Optional[str] = None,
    permission_decision: Optional[str] = None,
    permission_decision_reason: Optional[str] = None,
) -> dict:
    """生成符合 Hook 協定的輸出 JSON

    統一的 Hook 輸出生成函式，用於各種 Hook 的協定遵循。

    Hook 協定格式：
    - 基本輸出：{"hookSpecificOutput": {"hookEventName": "<事件名>"}}
    - 帶額外上下文：增加 "additionalContext" 欄位
    - 帶權限決策：增加 "permissionDecision" 和 "permissionDecisionReason" 欄位

    Args:
        hook_event_name: Hook 事件名稱，如 "UserPromptSubmit", "PreToolUse"
        additional_context: 可選的額外上下文訊息（如警告、提醒等）
        permission_decision: 可選的權限決策，"allow" / "deny" / "block"
        permission_decision_reason: 可選的權限決策理由

    Returns:
        dict: 符合 Hook 協定的輸出結構

    Examples:
        >>> generate_hook_output("UserPromptSubmit")
        {'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit'}}

        >>> generate_hook_output("PreToolUse", permission_decision="allow",
        ...     permission_decision_reason="工具不在檢查範圍")
        {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
            'permissionDecision': 'allow',
            'permissionDecisionReason': '工具不在檢查範圍'}}
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": hook_event_name
        }
    }

    if additional_context:
        output["hookSpecificOutput"]["additionalContext"] = additional_context

    if permission_decision:
        output["hookSpecificOutput"]["permissionDecision"] = permission_decision

    if permission_decision_reason:
        output["hookSpecificOutput"]["permissionDecisionReason"] = permission_decision_reason

    return output


_VALID_AUDIENCES = ("all", "pm_only")
"""emit_hook_output 的合法受眾枚舉：all（雙方可見）/ pm_only（僅 PM 主線程）"""


PM_ONLY_PREFIX = "[PM-ONLY] "
"""PM 專屬 hook 注入訊息的受眾標記前綴（PC-V1-004 防護 C 規則層契約）。

單一來源（ARCH-020）：所有 PM-only 注入訊息的前綴一律引用本常數，
禁止各 hook 自行複製字串字面，避免拼字漂移使 AGENT_PRELOAD 的
忽略規則失去比對錨點。

用途分兩層：
1. emit_hook_output(audience="pm_only")：主線程觸發時自動加前綴（本模組單點實作）
2. Stop 類 hook（systemMessage / decision-reason 等 emit_hook_output 無法
   覆蓋的輸出 shape）：import 本常數自行前置。Stop event 無 agent_id，
   程式層無法過濾，前綴是該盲區唯一的受眾標記手段，
   由 AGENT_PRELOAD 規則層教 subagent 忽略。
"""


def emit_hook_output(
    hook_event_name: str,
    additional_context: Optional[str] = None,
    permission_decision: Optional[str] = None,
    permission_decision_reason: Optional[str] = None,
    *,
    audience: str = "all",
    input_data: "dict | None" = None,
) -> None:
    """一步完成 Hook JSON stdout 輸出 — 統一格式 + 受眾過濾單點（ARCH-V1-001）

    組合 generate_hook_output + json.dumps + print，確保輸出格式正確。

    受眾過濾（PC-V1-004 防護 C）：audience="pm_only" 且觸發方為 subagent
    （input_data 含 agent_id）時，丟棄 additional_context，輸出退化為
    無訊息的基本結構（沿用 W1-071 既有跳過慣例）。過濾邏輯只存在於
    本函式，各 hook 禁止自行複製判斷（ARCH-020）。

    受眾標記前綴（PC-V1-004 防護 C 規則層）：audience="pm_only" 且觸發方為
    主線程時，additional_context 自動加上 PM_ONLY_PREFIX，供 AGENT_PRELOAD
    忽略規則比對。

    已知盲區：Stop event 無 agent_id（CC runtime 硬約束），
    is_subagent_environment 對其永遠返回 False；該盲區由
    [PM-ONLY] 前綴 + AGENT_PRELOAD 忽略規則補位。

    Args:
        hook_event_name: Hook 事件名稱
        additional_context: 可選的額外上下文訊息
        permission_decision: 可選的權限決策
        permission_decision_reason: 可選的權限決策理由
        audience: 訊息受眾，"all"（預設，向後相容既有呼叫）或 "pm_only"
        input_data: Hook stdin JSON；audience="pm_only" 時應傳入，
                    供 is_subagent_environment 判定觸發方（None 視為 PM）

    Raises:
        ValueError: audience 不在合法枚舉內（開發期錯誤，測試階段即暴露，
                    避免拼字錯誤造成 PM-only 訊息靜默洩漏給 subagent）
    """
    if audience not in _VALID_AUDIENCES:
        raise ValueError(
            "audience 必須為 {} 之一，收到: {!r}".format(
                "/".join(_VALID_AUDIENCES), audience
            )
        )

    if audience == "pm_only" and is_subagent_environment(input_data):
        # subagent 觸發：丟棄 PM-only 訊息；permission 欄位屬功能性決策不過濾
        additional_context = None
    elif audience == "pm_only" and additional_context:
        # 主線程觸發：加受眾標記前綴（PC-V1-004 防護 C）。程式層過濾涵蓋不到的
        # 環境（如 Stop event 無 agent_id）由 AGENT_PRELOAD 忽略規則依此前綴補位。
        additional_context = PM_ONLY_PREFIX + additional_context

    output = generate_hook_output(
        hook_event_name, additional_context,
        permission_decision, permission_decision_reason,
    )
    print(json.dumps(output, ensure_ascii=False))


# ============================================================================
# SubagentStop additionalContext 輸出（含版本相容 graceful fallback）
# ============================================================================

# CC 2.1.163 #4 解除 SubagentStop event schema 對
# hookSpecificOutput.additionalContext 的限制（W17-159 / W17-160 當時被迫
# 改用 top-level systemMessage）。低於此版本的 runtime 仍會拒絕
# additionalContext，故以版本偵測決定輸出 shape，舊版 graceful fallback
# 回 systemMessage。
SUBAGENT_STOP_ADDITIONAL_CONTEXT_MIN_VERSION = (2, 1, 163)

# 偵測結果快取（單次 hook 進程內只解析一次，避免重複 subprocess）。
_cc_version_cache: "Optional[Tuple[int, ...]]" = None
_cc_version_resolved = False


def _parse_version_tuple(raw: str) -> "Optional[Tuple[int, ...]]":
    """從 `claude --version` 輸出解析 (major, minor, patch) 整數 tuple。

    範例輸入: "2.1.163 (Claude Code)" -> (2, 1, 163)
    無法解析時回 None。
    """
    import re

    match = re.search(r"(\d+)\.(\d+)\.(\d+)", raw or "")
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def get_claude_code_version(
    logger: "Optional[logging.Logger]" = None,
) -> "Optional[Tuple[int, ...]]":
    """偵測當前 Claude Code runtime 版本，回 (major, minor, patch) tuple。

    透過 `claude --version` 取得；偵測失敗（binary 不在 PATH、subprocess
    逾時、輸出格式異常）時回 None，由呼叫端決定 fallback 行為。
    結果於進程內快取。
    """
    global _cc_version_cache, _cc_version_resolved
    if _cc_version_resolved:
        return _cc_version_cache

    _cc_version_resolved = True
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        _cc_version_cache = _parse_version_tuple(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        if logger:
            logger.debug("無法偵測 Claude Code 版本（fallback）: %s", exc)
        _cc_version_cache = None
    return _cc_version_cache


def supports_subagent_stop_additional_context(
    logger: "Optional[logging.Logger]" = None,
) -> bool:
    """判定當前 runtime 是否支援 SubagentStop additionalContext。

    版本 >= 2.1.163 回 True；低於則回 False。
    版本偵測失敗時採「樂觀預設」回 True——CC 2.1.163 為向後新基線，
    偵測失敗多發生於 sandbox/測試環境，採新 schema 可避免長期沿用
    過時 workaround；舊版實際拒絕時僅退化為一次 hook error（非致命）。
    """
    version = get_claude_code_version(logger)
    if version is None:
        return True
    return version >= SUBAGENT_STOP_ADDITIONAL_CONTEXT_MIN_VERSION


def build_subagent_stop_output(
    context: str,
    logger: "Optional[logging.Logger]" = None,
) -> dict:
    """為 SubagentStop event 建構輸出 JSON，含版本相容 graceful fallback。

    - CC >= 2.1.163: hookSpecificOutput.additionalContext（正確機制）
    - CC < 2.1.163 : top-level systemMessage（降級 workaround）

    Args:
        context: 要注入 PM 主線程的訊息文字。
        logger: 可選 logger，用於記錄版本偵測 fallback。

    Returns:
        dict: 對應 runtime 版本的輸出結構。
    """
    if supports_subagent_stop_additional_context(logger):
        return {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStop",
                "additionalContext": context,
            }
        }
    return {"systemMessage": context}
