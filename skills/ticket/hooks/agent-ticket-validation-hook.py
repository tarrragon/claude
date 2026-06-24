#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=5.0"]
# ///
#
# 依賴說明（W1-056.9）：嵌套深度檢查複用 ticket_system.lib.depth.can_descend，
# 該模組沿 parent_id 鏈回溯需 load_ticket（pyyaml）。dependencies 顯式宣告
# pyyaml，避免 uv ephemeral env 不拉 transitive deps 的 PC-124 模式。

"""
Agent Ticket Validation Hook

驗證派發任務是否引用有效的 Ticket ID。

功能：
- 從 prompt 中提取 Ticket ID 引用
- 驗證 Ticket 是否存在
- 驗證 Ticket 是否包含決策樹欄位
- 嵌套深度檢查（W1-056.9 / 協議 v2 D3）：被引用 ticket depth 達 MAX_TICKET_DEPTH
  時禁止再以其派發嵌套 Agent（複用 ticket_system.lib.depth.can_descend）
- 無效時拒絕派發
- 支援豁免機制：特定代理人類型（如 Explore）可跳過 Ticket 與深度驗證

豁免機制：
- Explore 代理人：用於前置資訊蒐集，在建立 Ticket 之前執行
- 豁免的代理人類型定義在 TICKET_EXEMPT_AGENT_TYPES 常數中

Hook 類型: PreToolUse（阻塞式）
Matcher: Task

使用方式:
    PreToolUse Hook 自動觸發，或手動測試:
    echo '{"tool_input":{"prompt":"Ticket: 0.30.1-W2-003..."}}' | python3 agent-ticket-validation-hook.py

環境變數:
    HOOK_DEBUG: 啟用詳細日誌（true/false）
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging, run_hook_safely, read_json_from_stdin, get_project_root,
    find_ticket_files, find_ticket_file, validate_ticket_has_decision_tree, save_check_log,
    is_handoff_recovery_mode, validate_hook_input, validate_ticket_unified
)

# ----------------------------------------------------------------------------
# 嵌套深度檢查模組（W1-056.9 / 協議 v2 D3 強制層）
#
# 複用 ticket_system.lib.depth 的 can_descend / compute_depth（禁止平行實作，
# ARCH-020）。MAX_TICKET_DEPTH 為深度上限 SSOT（constants.py）。
#
# fail-open 設計（Never break userspace）：若 depth 模組無法載入（如 ticket_system
# 套件不在 sys.path、或環境缺 transitive deps），DEPTH_AVAILABLE = False，深度檢查
# 整段跳過，既有 ticket 存在性驗證行為完全不變，不阻擋任何既有派發。
# ----------------------------------------------------------------------------

# 將 skill root 加入 sys.path，使 ticket_system 套件可被 import
# __file__ = .claude/skills/ticket/hooks/agent-ticket-validation-hook.py
# parents[1] = .claude/skills/ticket（skill root，含 ticket_system/）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from ticket_system.lib.depth import can_descend, compute_depth
    from ticket_system.constants import MAX_TICKET_DEPTH
    DEPTH_AVAILABLE = True
except Exception:  # pragma: no cover - 環境缺套件時的 fail-open 分支
    # 任何 import 失敗（ModuleNotFoundError / ImportError 等）都 fail-open，
    # 深度檢查停用但既有驗證不受影響。提供 fallback 常數供日誌輸出使用。
    can_descend = None  # type: ignore[assignment]
    compute_depth = None  # type: ignore[assignment]
    MAX_TICKET_DEPTH = 3  # fallback，僅供訊息顯示；實際判斷由 DEPTH_AVAILABLE gate
    DEPTH_AVAILABLE = False

# ============================================================================
# 常數定義
# ============================================================================

# Ticket ID 引用格式（支援子任務 ID，如 0.31.0-W3-002.1.1）
TICKET_ID_PATTERNS = [
    r"Ticket:\s*(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)",
    r"#Ticket-(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)",
    r"\[Ticket\s+(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)\]"
]

# 豁免 Ticket 驗證的代理人類型
#
# 判別準則（唯讀 vs 可寫）：
# - 可豁免：agent 工具僅含唯讀（Read/Grep/Glob/WebFetch/WebSearch/Bash 查詢類），
#   用途為情報蒐集、文件查詢、分析規劃，不會產生 Edit/Write/git commit 的持久化副作用。
# - 不可豁免：agent 可 Edit/Write/git commit，用途為實作/重構/測試執行，
#   必須引用有效 Ticket ID 以確保變更可追溯（符合所有發現必須追蹤原則）。
#
# 升級路徑：
# - 當白名單長度 > 10 或誤用率升高（非白名單 agent 被誤擋頻率上升）時，
#   應升級為「讀 agent definition 的 tools 欄位自動分類」的動態機制。
# - 來源：W17-046 ANA 方案 A（白名單擴充立即解除情報蒐集類 agent 派發阻礙）。
TICKET_EXEMPT_AGENT_TYPES = [
    "Explore",                    # codebase 探索：蒐集資訊以建立 Ticket（既有）
    "claude-code-guide",          # Claude Code / SDK / API 文件查詢（唯讀）
    "general-purpose",            # 複雜問題多步驟研究（唯讀）
    "Plan",                       # 架構規劃、實作計畫（唯讀）
    "feature-dev:code-explorer",  # 既有功能深度分析（唯讀）
]

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2

# validate_input 已遷移至 hook_utils.validate_hook_input

# ============================================================================
# Ticket ID 提取
# ============================================================================

def extract_ticket_reference(prompt: str, logger) -> Optional[str]:
    """
    從 prompt 中提取 Ticket ID 引用

    Args:
        prompt: 派發提示文本
        logger: 日誌物件

    Returns:
        str - Ticket ID，或 None 如未找到

    格式範例：
    - Ticket: 0.30.1-W2-003
    - #Ticket-0.30.1-W2-003
    - [Ticket 0.30.1-W2-003]
    """
    if not prompt:
        logger.debug("prompt 為空")
        return None

    for pattern in TICKET_ID_PATTERNS:
        match = re.search(pattern, prompt)
        if match:
            ticket_id = match.group(1)
            logger.info(f"從 prompt 提取 Ticket ID: {ticket_id}")
            return ticket_id

    logger.debug(f"未在 prompt 中找到 Ticket ID 引用")
    return None

# ============================================================================
# Ticket 檔案查找和驗證
# ============================================================================

def validate_ticket(ticket_id: str, logger) -> Tuple[bool, Optional[str]]:
    """
    驗證 Ticket 的完整性（委派給 hook_utils.validate_ticket_unified）

    Args:
        ticket_id: Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (is_valid, error_message)
    """
    return validate_ticket_unified(ticket_id, project_root=None, logger=logger)

# ============================================================================
# 派發驗證
# ============================================================================

# is_handoff_recovery_mode 已遷移至 hook_utils

def is_exempt_agent_type(subagent_type: str, logger) -> bool:
    """
    檢查代理人類型是否豁免 Ticket 驗證

    Args:
        subagent_type: 代理人類型
        logger: 日誌物件

    Returns:
        bool - 是否豁免驗證

    豁免的代理人類型用於前置資訊蒐集，在建立 Ticket 之前執行。
    例如：Explore 代理人用於探索 codebase 以蒐集建立 Ticket 所需的資訊。
    """
    if not subagent_type:
        return False

    is_exempt = subagent_type in TICKET_EXEMPT_AGENT_TYPES
    if is_exempt:
        logger.info(f"代理人類型 '{subagent_type}' 豁免 Ticket 驗證（用於前置資訊蒐集）")
    return is_exempt

def check_depth_descend(ticket_id: str, logger) -> Tuple[bool, Optional[str]]:
    """
    檢查以 ticket_id 派發嵌套 Agent 是否未超出深度上限（協議 v2 D3）。

    判準（D2 條件 D-3 / D3 機制）：
        每層 agent 從 ticket depth 推算層級。被引用 ticket 的 depth 達 MAX_TICKET_DEPTH
        時，代表它已處框架允許的最深層（can_descend = False），不應再以其派發嵌套
        Agent（會嘗試 descend 到超限深度）。此時 deny 並輸出 ascend / NeedsContext 指引。

    複用 ticket_system.lib.depth.can_descend（禁止平行實作，ARCH-020）。

    Args:
        ticket_id: 被派發引用的 Ticket ID
        logger: 日誌物件

    Returns:
        tuple - (is_ok, error_message)
            - is_ok: True 表示深度合規（可 descend）或檢查不適用（fail-open）
            - error_message: 超限時的 deny 指引；合規時為 None

    fail-open：DEPTH_AVAILABLE = False 時直接回傳 (True, None)，不阻擋既有派發。
    """
    if not DEPTH_AVAILABLE:
        logger.info("深度檢查模組不可用（DEPTH_AVAILABLE=False），跳過深度檢查（fail-open）")
        return True, None

    try:
        if can_descend(ticket_id):
            logger.info(f"Ticket {ticket_id} 深度合規，允許嵌套派發")
            return True, None

        depth = compute_depth(ticket_id)
        msg = (
            f"嵌套深度超限：Ticket {ticket_id} 深度 = {depth}，"
            f"已達框架最大深度上限（MAX_TICKET_DEPTH = {MAX_TICKET_DEPTH}），"
            f"不可再以其派發嵌套 Agent（會 descend 至超限深度）。\n"
            f"建議處理方向：\n"
            f"  1. ascend 回報：以 Exit Status (status: blocked, reason: 深度上限) 將需拆分的工作回報上層 PM\n"
            f"  2. NeedsContext：在 ticket 的 NeedsContext 章節記錄需拆分的子任務，由 PM 在較淺層重新組織\n"
            f"  3. 確認任務無法在本層完成時，由 PM 評估是否調整 ticket 階層結構"
        )
        logger.warning(f"深度超限 deny: {ticket_id} (depth={depth} >= {MAX_TICKET_DEPTH})")
        return False, msg
    except Exception as e:  # pragma: no cover - 深度計算異常時 fail-open
        # 深度計算過程異常（如 ticket 載入失敗）不應阻擋既有派發，fail-open。
        logger.info(f"深度檢查過程異常，fail-open 放行: {type(e).__name__}: {e}")
        return True, None


def validate_task_dispatch(tool_input: Dict[str, Any], logger) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    驗證 Task 派發是否有效

    Args:
        tool_input: 工具輸入資料
        logger: 日誌物件

    Returns:
        tuple - (is_valid, error_message, ticket_id)
            - is_valid: 派發是否有效
            - error_message: 錯誤訊息（如有），成功時為 None
            - ticket_id: 提取的 Ticket ID，或 None（豁免/handoff 模式或未找到）

    驗證流程：
    0. 檢查是否為 Handoff 恢復模式
    1. 檢查是否為豁免的代理人類型（如 Explore）
    2. 從 prompt 提取 Ticket ID 引用
    3. 驗證 Ticket 是否存在且包含決策樹欄位
    4. 嵌套深度檢查（協議 v2 D3）：被引用 ticket depth 達上限時禁止再 descend
    """
    prompt = tool_input.get("prompt", "")
    subagent_type = tool_input.get("subagent_type", "")

    # 步驟 0: 檢查 Handoff 恢復模式
    if is_handoff_recovery_mode(logger):
        logger.info("Handoff 恢復模式: 略過 Ticket 驗證")
        return True, None, None

    # 步驟 1: 檢查豁免代理人類型
    if is_exempt_agent_type(subagent_type, logger):
        return True, None, None

    # 步驟 2: 提取 Ticket ID
    ticket_id = extract_ticket_reference(prompt, logger)
    if not ticket_id:
        msg = "派發任務必須引用有效的 Ticket ID（格式：Ticket: {id} 或 #Ticket-{id} 或 [Ticket {id}]）"
        logger.error(msg)
        return False, msg, None

    # 步驟 3: 驗證 Ticket（存在性 + 決策樹欄位）
    is_valid, error_msg = validate_ticket(ticket_id, logger)
    if not is_valid:
        return is_valid, error_msg, ticket_id

    # 步驟 4: 嵌套深度檢查（協議 v2 D3 強制層，W1-056.9）
    # ticket 有效後才檢查深度；豁免型 agent 已在步驟 1 提前 return，不會抵達此處。
    depth_ok, depth_err = check_depth_descend(ticket_id, logger)
    if not depth_ok:
        return False, depth_err, ticket_id

    return True, None, ticket_id

# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    is_valid: bool,
    error_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        is_valid: 派發是否有效
        error_message: 錯誤訊息（如有）

    Returns:
        dict - Hook 輸出 JSON

    驗證失敗時，輸出 deny 決策和錯誤原因。
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse"
        }
    }

    if not is_valid:
        output["hookSpecificOutput"]["permissionDecision"] = "deny"
        output["hookSpecificOutput"]["permissionDecisionReason"] = (
            error_message or "派發任務驗證失敗"
        )
    else:
        output["hookSpecificOutput"]["permissionDecision"] = "allow"

    # 記錄檢查結果（包在 hookSpecificOutput 內，避免頂層出現未知欄位觸發 JSON validation failed，IMP-055）
    output["hookSpecificOutput"]["checkResult"] = {
        "isValid": is_valid,
        "errorMessage": error_message,
        "timestamp": datetime.now().isoformat()
    }

    return output


# ============================================================================
# 主入口點
# ============================================================================

def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化日誌
    2. 讀取 JSON 輸入
    3. 驗證輸入格式
    4. 驗證 Task 派發有效性
    5. 生成 Hook 輸出
    6. 儲存日誌
    7. 決定 exit code

    Returns:
        int - Exit code (0=allow, 2=deny, 1=error)
    """
    logger = setup_hook_logging("agent-ticket-validation")
    try:
        # 步驟 1: 初始化日誌
        logger.info("Agent Ticket Validation Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)

        # 步驟 3: 驗證輸入格式
        if not validate_hook_input(input_data, logger, ("tool_input",)):
            logger.error("輸入格式錯誤")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "PreToolUse"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        tool_input = input_data.get("tool_input", {})

        # 步驟 4: 驗證 Task 派發有效性
        is_valid, error_message, ticket_id = validate_task_dispatch(tool_input, logger)

        logger.info(f"Task 派發驗證: is_valid={is_valid}, ticket_id={ticket_id}")

        # 步驟 5: 生成 Hook 輸出
        hook_output = generate_hook_output(is_valid, error_message if not is_valid else None)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 6: 儲存日誌
        log_entry = f"""[{datetime.now().isoformat()}]
  TicketID: {ticket_id}
  IsValid: {is_valid}
  ErrorMessage: {error_message if not is_valid else None}
  Status: {"ALLOWED" if is_valid else "DENIED"}

"""
        save_check_log("agent-ticket-validation", log_entry, logger)

        # 步驟 7: 決定 exit code
        if is_valid:
            logger.info("Agent Ticket Validation Hook 檢查通過")
            return EXIT_SUCCESS
        else:
            logger.warning("Agent Ticket Validation Hook 拒絕派發")
            # 輸出到 stderr 確保 PM 可見（品質基線規則 4）
            print(f"[Agent Ticket Validation] 派發被拒絕: {error_message}", file=sys.stderr)
            return EXIT_BLOCK

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        # error 詳情放進 hookSpecificOutput 內，避免頂層出現未知欄位觸發 JSON validation failed（IMP-055）
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/agent-ticket-validation/",
                "errorInfo": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        return EXIT_ERROR

if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "agent-ticket-validation"))
