#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///

"""
派發計數驗證 Hook - PostToolUse 和 UserPromptSubmit 雙重觸發

功能: 偵測 PM 敘述多人派發（「三人組」「多視角」等關鍵字）但實際派發數量不足的情況。
      防止 PC-020 錯誤模式（派發計數不一致）。

觸發時機:
  1. PostToolUse（Agent tool call）：偵測關鍵字，初始化/更新派發計數
  2. UserPromptSubmit（用戶下一次輸入）：驗證派發計數，輸出警告

計數器存放: /tmp/claude-dispatch-batch-{session_id}.json（session_id 取自 hook 輸入）
失敗語意: fail-open——取不到 session_id 時略過計數與驗證，不阻擋
格式:
  {
    "expected": 3,
    "actual": 1,
    "keywords": ["三人組"],
    "batch_started_at": "ISO timestamp",
    "PostToolUse_call_count": 0
  }

工作流程:
  1. Agent tool call（POST）
     ├─ 偵測關鍵字？
     ├─ 是 → 解析期望派發數量 → 建立/更新狀態檔
     └─ 遞增 actual 計數

  2. 用戶下一次輸入（SUBMIT）
     ├─ 讀取狀態檔
     ├─ actual < expected？
     ├─ 是 → 輸出 WARNING 到 stderr + 日誌
     └─ 清理狀態檔

行為: 不阻擋（exit 0），僅在不一致時輸出警告

相關錯誤模式：PC-020 — 派發計數敘述-執行不一致
"""

import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output
from lib.session_state_key import session_state_path
from lib.constants import (
    DISPATCH_MULTI_KEYWORDS,
    DISPATCH_BATCH_STATE_TEMPLATE,
    DISPATCH_BATCH_STATE_TIMEOUT_SECS,
    EXIT_SUCCESS,
)

# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "dispatch-count-guard"

# 關鍵字到期望派發數量的映射
KEYWORD_TO_COUNT = {
    "三人組": 3,
    "多視角": 3,
    "固定三人組": 3,
    "parallel-evaluation": 3,
    "並行評估": 3,
    "Agent Teams": 2,
    "3-4x": 3,
    "double-track": 2,
    "dual-track": 2,
}

# 否定修飾判定（與 agent-dispatch-validation 的收尾指示判定同一語意）：
# 以子句為單位；子句內命中前、最近一個逗號之後出現否定詞，視為否定，不計入期望數
_CLAUSE_SPLIT = re.compile(r"[。；;\n]")
_NEGATION_PATTERN = re.compile(
    r"不要|不得|不可|不必|不需|不用|不派|不走|不採|不是|不做|無需|沒有|禁止|勿|避免|"
    r"\bnever\b|\bdo not\b|\bdon't\b|\bnot\b|\bno\b|\bwithout\b",
    re.IGNORECASE,
)

# 警告中附列的命中原句上限（避免長 prompt 灌爆警告）
MAX_MATCHED_CLAUSES = 3
MATCHED_CLAUSE_MAX_CHARS = 120

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}


# ============================================================================
# 狀態檔管理
# ============================================================================

def get_batch_state_file(input_data: Dict[str, Any], logger=None) -> Optional[Path]:
    """取得派發批次狀態檔路徑（以 hook 輸入的 session_id 識別；取不到回傳 None）"""
    return session_state_path(DISPATCH_BATCH_STATE_TEMPLATE, input_data, logger)


def is_state_file_expired(file_path: Path) -> bool:
    """檢查狀態檔是否過期"""
    try:
        if not file_path.exists():
            return True

        stat = file_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime)
        now = datetime.now()
        elapsed = (now - mtime).total_seconds()

        return elapsed > DISPATCH_BATCH_STATE_TIMEOUT_SECS
    except Exception:
        return True


def read_batch_state(file_path: Path, logger) -> Optional[Dict[str, Any]]:
    """讀取派發批次狀態"""
    if not file_path.exists():
        return None

    if is_state_file_expired(file_path):
        logger.debug(f"狀態檔已過期（5 分鐘），清理: {file_path}")
        try:
            file_path.unlink()
        except Exception:
            pass
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"讀取狀態檔失敗: {e}")
        return None


def write_batch_state(file_path: Path, state: Dict[str, Any], logger) -> bool:
    """寫入派發批次狀態"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logger.debug(f"狀態檔已寫入: {file_path}")
        return True
    except IOError as e:
        logger.warning(f"寫入狀態檔失敗: {e}")
        return False


# ============================================================================
# 關鍵字偵測
# ============================================================================

def _is_negated(clause: str, start: int) -> bool:
    """子句內位於 start 的關鍵字是否被否定修飾。

    否定詞只看命中前、最近一個逗號之後的分句尾段；頓號（列舉）不切，
    「不需要三人組、多視角」的兩個關鍵字都受否定涵蓋，
    「不改規則，改走三人組」的三人組不受影響。
    """
    head = re.split(r"[，,]", clause[:start])[-1]
    return bool(_NEGATION_PATTERN.search(head))


def detect_dispatch_keywords(
    text: str, logger
) -> Optional[tuple[list[str], int, list[str]]]:
    """
    偵測派發相關關鍵字和期望派發數量；被否定修飾的出現不計入

    Returns:
        tuple - (detected_keywords, expected_count, matched_clauses)，
        matched_clauses 為計入的命中原句（去重、保序）；若無計入的關鍵字則回傳 None
    """
    if not text:
        return None

    detected = []
    clauses_hit: list[str] = []
    max_expected = 0

    for clause in _CLAUSE_SPLIT.split(text):
        lowered = clause.lower()
        for keyword in DISPATCH_MULTI_KEYWORDS:
            start = lowered.find(keyword.lower())
            if start < 0:
                continue
            if _is_negated(clause, start):
                logger.debug(f"關鍵字 {keyword} 被否定修飾，不計入: {clause.strip()}")
                continue
            if keyword not in detected:
                detected.append(keyword)
            if clause.strip() not in clauses_hit:
                clauses_hit.append(clause.strip())
            max_expected = max(max_expected, KEYWORD_TO_COUNT.get(keyword, 2))

    if detected:
        logger.debug(f"偵測到派發關鍵字: {detected}, 期望派發數: {max_expected}")
        return (detected, max_expected, clauses_hit)

    return None


# ============================================================================
# PostToolUse 邏輯
# ============================================================================

def handle_post_tool_use(input_data: Dict[str, Any], logger) -> int:
    """
    PostToolUse Hook：偵測 Agent dispatch 關鍵字，初始化或遞增計數

    [Background 模式語意備註]
    本 Hook 計數的語意是「PM 已派發的 Agent 數」，而非「已完成的 Agent 數」。
    PostToolUse(Agent) 對 run_in_background=true 在「啟動完成」時觸發，
    此時 agentId 已返回，等同於「派發完成」，因此計數於此時點正確無誤。
    不需要套用 is_background_dispatch early-return（與其他 early-return 路徑 P-2 / P-3 不同）。
    """
    # 只處理 Agent tool
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Agent":
        logger.debug(f"非 Agent tool，跳過: {tool_name}")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 提取 Agent prompt/description
    tool_input = input_data.get("tool_input") or {}
    prompt = tool_input.get("prompt", "")
    description = tool_input.get("description", "")

    # 換行接合：prompt 與 description 各自成句，否定判定不跨欄位
    combined_text = f"{prompt}\n{description}"

    # 偵測關鍵字
    detection = detect_dispatch_keywords(combined_text, logger)
    if not detection:
        logger.debug("未偵測到派發關鍵字")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    keywords, expected_count, matched_clauses = detection

    # 初始化或更新狀態檔
    state_file = get_batch_state_file(input_data, logger)
    if state_file is None:
        # fail-open：取不到 session_id 就略過計數（警告型 hook，不阻擋）
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS
    state = read_batch_state(state_file, logger) or {
        "expected": expected_count,
        "keywords": keywords,
        "matched_clauses": matched_clauses,
        "actual": 0,
        "batch_started_at": datetime.now().isoformat(),
        "PostToolUse_call_count": 0,
    }

    # 遞增計數（表示派發了一個 Agent）
    state["actual"] += 1
    state["PostToolUse_call_count"] = state.get("PostToolUse_call_count", 0) + 1

    write_batch_state(state_file, state, logger)

    logger.info(f"派發計數: {state['actual']}/{state['expected']} (關鍵字: {keywords})")

    print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
    return EXIT_SUCCESS


# ============================================================================
# UserPromptSubmit 邏輯
# ============================================================================

def _format_matched_clauses(clauses: list[str]) -> str:
    """命中原句區塊：最多 MAX_MATCHED_CLAUSES 句，每句截至 MATCHED_CLAUSE_MAX_CHARS 字。"""
    if not clauses:
        return ""
    lines = []
    for clause in clauses[:MAX_MATCHED_CLAUSES]:
        text = clause if len(clause) <= MATCHED_CLAUSE_MAX_CHARS else clause[:MATCHED_CLAUSE_MAX_CHARS] + "…"
        lines.append(f"  - {text}")
    return "命中原句:\n" + "\n".join(lines) + "\n"


def build_count_mismatch_warning(
    expected: int, actual: int, keywords: list[str], matched_clauses: Optional[list[str]] = None
) -> str:
    """建立派發計數不一致警告訊息（附命中原句，供判斷是否為誤計）"""
    return (
        f"============================================================\n"
        f"[Dispatch Count Guard] 派發計數警告（PC-020）\n"
        f"============================================================\n"
        f"\n"
        f"敘述中提及: {', '.join(keywords)}\n"
        f"{_format_matched_clauses(matched_clauses or [])}"
        f"期望派發數量: {expected}\n"
        f"實際派發數量: {actual}\n"
        f"\n"
        f"[WARN] 派發計數不一致！\n"
        f"\n"
        f"核心原則（PC-020）：派發敘述與執行必須一致。\n"
        f"- 若計畫派 3 人，務必執行 3 個 Agent dispatch\n"
        f"- 若實際只派 1 人，應在敘述中明確說明原因\n"
        f"\n"
        f"建議:\n"
        f"1. 檢查派發指令是否完整\n"
        f"2. 若有特殊原因未派足數量，請更新敘述\n"
        f"3. 建立 Ticket 追蹤此次派發計數問題\n"
        f"============================================================"
    )


def handle_user_prompt_submit(input_data: Dict[str, Any], logger) -> int:
    """
    UserPromptSubmit Hook：驗證派發計數，若不一致輸出警告
    """
    state_file = get_batch_state_file(input_data, logger)
    if state_file is None:
        # fail-open：取不到 session_id 就略過驗證
        return EXIT_SUCCESS
    state = read_batch_state(state_file, logger)

    if not state:
        logger.debug("無派發計數狀態檔，跳過驗證")
        return EXIT_SUCCESS

    expected = state.get("expected", 0)
    actual = state.get("actual", 0)
    keywords = state.get("keywords", [])

    # 清理狀態檔
    try:
        state_file.unlink()
        logger.debug(f"清理狀態檔: {state_file}")
    except Exception as e:
        logger.debug(f"清理狀態檔失敗: {e}")

    # 驗證計數
    if actual < expected:
        warning = build_count_mismatch_warning(
            expected, actual, keywords, state.get("matched_clauses", [])
        )

        # 雙通道輸出：stderr + 日誌
        sys.stderr.write(warning + "\n")
        logger.warning(f"派發計數不一致: {actual}/{expected} (關鍵字: {keywords})")

        # 派發計數警告為 PM-only：統一出口過濾 subagent 觸發（PC-V1-004 防護 C）
        emit_hook_output(
            "UserPromptSubmit",
            additional_context=warning,
            audience="pm_only",
            input_data=input_data,
        )
    else:
        logger.info(f"派發計數驗證通過: {actual}/{expected}")

    return EXIT_SUCCESS


# ============================================================================
# 主要邏輯
# ============================================================================

def main() -> int:
    """
    主入口點

    根據 Hook 觸發時機分別執行：
    - PostToolUse：偵測關鍵字，初始化/更新派發計數
    - UserPromptSubmit：驗證派發計數，輸出警告
    """
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)
        if not input_data:
            logger.debug("無有效輸入，跳過")
            return EXIT_SUCCESS

        # 判斷觸發時機
        hook_event_name = input_data.get("hook_event_name", "")

        if hook_event_name == "PostToolUse":
            logger.debug("PostToolUse 觸發")
            return handle_post_tool_use(input_data, logger)

        elif hook_event_name == "UserPromptSubmit":
            logger.debug("UserPromptSubmit 觸發")
            return handle_user_prompt_submit(input_data, logger)

        else:
            logger.debug(f"未知的 Hook 事件: {hook_event_name}")
            return EXIT_SUCCESS

    except Exception as e:
        logger.error(f"Hook 執行錯誤: {e}", exc_info=True)
        # 不阻擋流程
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False))
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
