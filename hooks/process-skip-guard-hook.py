#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Process Skip Guard Hook

偵測用戶輸入中的流程省略意圖，輸出 AskUserQuestion 場景 12 提醒。
防止主線程自行省略流程步驟。

Hook 類型: UserPromptSubmit
觸發時機: 用戶提交任何 prompt 時

6 個省略模式定義（每個模式需要 2 個關鍵字同時出現）：
1. SKIP_AGENT_DISPATCH - 不派發代理人
2. SKIP_ACCEPTANCE - 跳過驗收
3. SKIP_TDD_PHASE - 跳過 TDD 步驟
4. SKIP_PARALLEL_EVAL - 跳過 parallel-evaluation
5. SKIP_SA_REVIEW - 跳過 SA 審查
6. SKIP_PHASE4 - 跳過 Phase 4 重構

代理人應透過此 Hook 的提醒來防止流程省略違規。
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, TypedDict

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    is_subagent_environment,
    generate_hook_output,
    read_json_from_stdin,
    get_project_root,
    find_active_in_progress_ticket,
)
from lib.hook_messages import (
    AskUserQuestionMessages,
    ProcessSkipMessages,
    format_message,
)

# Type/phase guard 規則：SKIP_SA_REVIEW 在以下 ticket 上下文應靜音
# - DOC / ANA type：全面靜音（非實作任務無 SA 前置審查需求）
# - IMP type + Phase 4：靜音（重構非新功能）
SA_GUARD_SILENCE_TYPES = {"DOC", "ANA"}
SA_GUARD_IMP_SILENCE_PHASE = "Phase 4"

EXIT_SUCCESS = 0


# ============================================================================
# 型別定義（W11-022 thyme 視角）：pattern_info 抽 TypedDict
# ============================================================================

class SkipPatternInfo(TypedDict):
    """SKIP_PATTERNS 字典值結構。

    - pairs: 兩個關鍵字 pair 列表；兩字皆出現於 user_input 時視為命中
    - description: 提醒訊息中描述此省略類型的短句
    - full_process: 提醒訊息中描述完整流程要求的長句
    """
    pairs: List[Tuple[str, str]]
    description: str
    full_process: str


# ============================================================================
# 省略模式定義：6 類流程省略意圖
# ============================================================================

SKIP_PATTERNS: dict[str, SkipPatternInfo] = {
    # 優先級 1：最具體的 Phase 4 模式
    "SKIP_PHASE4": {
        "pairs": [
            ("跳過", "phase 4"),
            ("不需要", "重構"),
            ("省略", "重構"),
            ("不用", "重構"),
            ("已完美", "不用評估"),
        ],
        "description": ProcessSkipMessages.SKIP_PHASE4_DESCRIPTION,
        "full_process": ProcessSkipMessages.SKIP_PHASE4_FULL_PROCESS,
    },
    # 優先級 2：SA 審查（需要在通用 Phase 檢查前）
    # 註：移除 ("不做","架構審查") — 與一般「這次不做架構審查改良」討論重疊（高 FP，W11-004.2）
    "SKIP_SA_REVIEW": {
        "pairs": [
            ("不需要", "sa"),
            ("跳過", "sa"),
            ("不需要", "審查"),
            ("跳過", "系統分析"),
        ],
        "description": ProcessSkipMessages.SKIP_SA_REVIEW_DESCRIPTION,
        "full_process": ProcessSkipMessages.SKIP_SA_REVIEW_FULL_PROCESS,
    },
    # 優先級 3：派發相關（需要在通用關鍵字前）
    "SKIP_AGENT_DISPATCH": {
        "pairs": [
            ("不需要", "派發"),
            ("自行", "處理"),
            ("不用", "代理人"),
            ("我自己", "做"),
            ("主線程", "處理"),
        ],
        "description": ProcessSkipMessages.SKIP_AGENT_DISPATCH_DESCRIPTION,
        "full_process": ProcessSkipMessages.SKIP_AGENT_DISPATCH_FULL_PROCESS,
    },
    # 優先級 4：驗收相關
    # 註：移除 ("直接","完成") 與 ("不做","審查") — 高假陽性 pair（W11-004.2）
    # 「直接修復後完成」「這次不做審查」是合法措辭，且 ("不做","審查") 語意屬 SA 而非驗收
    "SKIP_ACCEPTANCE": {
        "pairs": [
            ("不需要", "驗收"),
            ("跳過", "驗收"),
            ("省略", "驗收"),
        ],
        "description": ProcessSkipMessages.SKIP_ACCEPTANCE_DESCRIPTION,
        "full_process": ProcessSkipMessages.SKIP_ACCEPTANCE_FULL_PROCESS,
    },
    # 優先級 5：並行評估
    # 註：移除 ("不用","評估") — 與 ("不需要","評估") 語意重複（同為「否定+評估」結構，W11-022）
    "SKIP_PARALLEL_EVAL": {
        "pairs": [
            ("跳過", "審核"),
            ("不需要", "評估"),
            ("跳過", "parallel"),
            ("直接", "派發"),
        ],
        "description": ProcessSkipMessages.SKIP_PARALLEL_EVAL_DESCRIPTION,
        "full_process": ProcessSkipMessages.SKIP_PARALLEL_EVAL_FULL_PROCESS,
    },
    # 優先級 6：通用 Phase 檢查（最後，因為最通用）
    "SKIP_TDD_PHASE": {
        "pairs": [
            ("跳過", "phase"),
            ("省略", "phase"),
            ("不需要", "phase"),
            ("跳過", "測試"),
            ("直接", "實作"),
        ],
        "description": ProcessSkipMessages.SKIP_TDD_PHASE_DESCRIPTION,
        "full_process": ProcessSkipMessages.SKIP_TDD_PHASE_FULL_PROCESS,
    },
}


def detect_skip_intent(user_input: str) -> Tuple[Optional[str], Optional[SkipPatternInfo]]:
    """
    偵測流程省略意圖

    Args:
        user_input: 用戶輸入的提示文本

    Returns:
        (skip_type, pattern_info) 若偵測到省略意圖
        (None, None) 若無省略意圖
    """
    if not user_input:
        return None, None

    user_input_lower = user_input.lower()

    for skip_type, pattern_info in SKIP_PATTERNS.items():
        for keyword_a, keyword_b in pattern_info["pairs"]:
            # 兩個關鍵字都需要出現在輸入中
            if keyword_a in user_input_lower and keyword_b in user_input_lower:
                return skip_type, pattern_info

    return None, None


def has_active_dispatch() -> bool:
    """
    檢查 .claude/dispatch-active.json 是否含 active dispatch

    格式：{"dispatches": [...]}（dispatches 陣列非空 → active）

    Returns:
        True 若有 active dispatch；False 若檔案缺失/損毀/dispatches 空
    """
    try:
        root = get_project_root()
        path = root / ".claude" / "dispatch-active.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            dispatches = data.get("dispatches", [])
        elif isinstance(data, list):
            # 兼容舊格式(裸陣列)
            dispatches = data
        else:
            return False
        return bool(dispatches)
    except (json.JSONDecodeError, OSError, Exception):
        # JSON 損毀 / 讀取失敗 → 視為無 active dispatch（不阻擋 hook）
        return False


def _started_at_sort_key(value) -> Tuple[int, object]:
    """ISO 8601 started_at 排序鍵（fromisoformat fallback）。

    W11-022 linux 視角：原始 W11-004.2 spec 採 started_at 字串排序，雖然
    ISO 8601 字串字典序與時序大致一致，但遇到非 ISO 格式（舊資料 / 手動編輯
    錯誤 / 缺欄位）字串排序會給出未定義結果。本 helper 統一語意：

    - 可解析 ISO 8601 → (0, datetime)：優先以時序排序
    - 不可解析 / 空 / None → (1, str(value))：退化至字串排序保留原行為

    tuple 首元素確保「可解析」永遠優於「不可解析」項；同類內部仍可比較。

    本函式為防禦性 helper：W11-021 改採 mtime 排序後 hot path 不再依賴
    started_at 字串排序，但保留此 helper 供未來 tie-break / 校驗用途，並
    記錄不可解析情況以利偵測異常資料。
    """
    if not value:
        return (1, "")
    try:
        return (0, datetime.fromisoformat(str(value)))
    except (TypeError, ValueError):
        return (1, str(value))


def get_active_in_progress_ticket() -> Optional[dict]:
    """
    找出最新 in_progress ticket（W11-021 統一入口包裝）

    委派至 hook_utils.find_active_in_progress_ticket（共用 helper，含 archive/backup
    排除與 get_project_root worktree 支援），並投影為本 hook 所需欄位。

    W11-022：對返回 ticket 的 started_at 套用 _started_at_sort_key 驗證；
    不可解析時記錄訊息但不改變返回值（避免影響 type/phase guard 行為）。

    Returns:
        {"type": ..., "current_phase": ...} 若找到；None 若無或讀取失敗

    Performance:
        共用 helper 採 mtime 排序 + short-circuit；hot path 命中第一個 in_progress
        即 return，cold path 延遲 << 100ms（W11-019）
    """
    fm = find_active_in_progress_ticket()
    if not fm:
        return None
    # 防禦性驗證 started_at：不可解析時 sort_key 返回 (1, ...) tier，不阻擋返回
    _started_at_sort_key(fm.get("started_at"))
    return {
        "type": fm.get("type"),
        "current_phase": fm.get("current_phase"),
    }


def _should_silence_sa_review(active_ticket: Optional[dict]) -> bool:
    """依 type/phase guard 規則判斷是否應靜音 SKIP_SA_REVIEW"""
    if not active_ticket:
        return False
    ticket_type = active_ticket.get("type")
    phase = active_ticket.get("current_phase")
    if ticket_type in SA_GUARD_SILENCE_TYPES:
        return True
    if ticket_type == "IMP" and phase == SA_GUARD_IMP_SILENCE_PHASE:
        return True
    return False


def generate_skip_reminder(skip_type: str, pattern_info: SkipPatternInfo) -> str:
    """
    生成流程省略提醒訊息

    Args:
        skip_type: 省略類型
        pattern_info: 模式資訊（包含 description 和 full_process）

    Returns:
        格式化的提醒訊息
    """
    return format_message(
        AskUserQuestionMessages.PROCESS_SKIP_REMINDER,
        skip_description=pattern_info["description"],
        full_process=pattern_info["full_process"],
    )


def _emit_basic() -> int:
    """輸出無提醒的基本 Hook 協定 JSON 並回傳 EXIT_SUCCESS。

    收斂 main() 中 7 處重複的 `print(json.dumps(generate_hook_output(...))) + return`
    模式（W11-020 重構）。特殊 reminder emit（含 reminder payload）保留於 main 內
    直接輸出，不經此 helper。
    """
    print(json.dumps(generate_hook_output("UserPromptSubmit"), ensure_ascii=False, indent=2))
    return EXIT_SUCCESS


def main() -> int:
    """
    Hook 主函式

    流程：
    1. 讀取 JSON 輸入
    2. 在 subagent 環境中跳過檢查，輸出基本 JSON
    3. 偵測流程省略意圖
    4. 輸出 Hook 協定 JSON 到 stdout
    5. 若偵測到省略意圖，同時輸出提醒訊息到 stderr

    Returns:
        0 (永遠允許執行，僅輸出提醒)
    """
    logger = setup_hook_logging("process-skip-guard")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, Exception):
        # 輸入解析失敗，輸出基本 JSON
        return _emit_basic()

    if input_data is None:
        return _emit_basic()

    # 偵測 subagent 環境：agent_id 僅在 subagent 中出現
    if is_subagent_environment(input_data):
        logger.info("偵測到 subagent 環境（agent_id=%s），跳過流程省略提醒", input_data.get("agent_id"))
        return _emit_basic()

    user_input = input_data.get("prompt", "")

    if not user_input:
        # 無使用者輸入，輸出基本 JSON
        return _emit_basic()

    skip_type, pattern_info = detect_skip_intent(user_input)

    # Active-dispatch guard（cold path：偵測到 skip intent 才查 dispatch-active.json）
    # 代理人執行中時用戶輸入易誤觸驗收/省略偵測，靜默避免誤報（W11-004.3）
    if skip_type:
        try:
            if has_active_dispatch():
                logger.info(f"偵測到 active dispatch，靜音 {skip_type} 提醒")
                return _emit_basic()
        except Exception as exc:
            logger.warning(f"has_active_dispatch 失敗，回退原行為: {exc}")

    # SKIP_SA_REVIEW type/phase guard（cold path：僅在偵測到 skip intent 時查詢）
    if skip_type == "SKIP_SA_REVIEW":
        try:
            active_ticket = get_active_in_progress_ticket()
        except Exception as exc:
            # 讀取例外不阻擋 hook，回退至原行為（觸發提醒）
            logger.warning(f"get_active_in_progress_ticket 失敗，回退原行為: {exc}")
            active_ticket = None

        if _should_silence_sa_review(active_ticket):
            logger.info(
                f"SKIP_SA_REVIEW 因 ticket type={active_ticket.get('type')}/"
                f"phase={active_ticket.get('current_phase')} 靜音"
            )
            return _emit_basic()

    if skip_type and pattern_info:
        logger.info(f"偵測到流程省略意圖: {skip_type}")
        reminder = generate_skip_reminder(skip_type, pattern_info)

        # 輸出 Hook 協定 JSON 到 stdout（包含提醒訊息）
        # 此處為特殊 reminder emit，含 reminder payload，不經 _emit_basic() 以保留語意
        hook_output = generate_hook_output("UserPromptSubmit", reminder)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 同時輸出提醒訊息到 stderr（雙通道要求）
        print(reminder, file=sys.stderr)
        logger.info(f"省略意圖詳情: {pattern_info['description']}")
        return EXIT_SUCCESS

    # 未偵測到省略意圖，輸出基本 JSON
    return _emit_basic()


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "process-skip-guard"))
