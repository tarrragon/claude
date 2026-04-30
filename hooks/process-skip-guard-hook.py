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
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    is_subagent_environment,
    generate_hook_output,
    read_json_from_stdin,
)
from lib.hook_messages import (
    AskUserQuestionMessages,
    ProcessSkipMessages,
    format_message,
)
from lib.frontmatter_parser import parse_frontmatter

# Type/phase guard 規則：SKIP_SA_REVIEW 在以下 ticket 上下文應靜音
# - DOC / ANA type：全面靜音（非實作任務無 SA 前置審查需求）
# - IMP type + Phase 4：靜音（重構非新功能）
SA_GUARD_SILENCE_TYPES = {"DOC", "ANA"}
SA_GUARD_IMP_SILENCE_PHASE = "Phase 4"

EXIT_SUCCESS = 0

# ============================================================================
# 省略模式定義：6 類流程省略意圖
# ============================================================================

SKIP_PATTERNS = {
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
    "SKIP_PARALLEL_EVAL": {
        "pairs": [
            ("跳過", "審核"),
            ("不需要", "評估"),
            ("跳過", "parallel"),
            ("直接", "派發"),
            ("不用", "評估"),
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


def detect_skip_intent(user_input: str) -> Tuple[Optional[str], Optional[dict]]:
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
        root = _find_repo_root()
        if root is None:
            return False
        path = root / ".claude" / "dispatch-active.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            dispatches = data.get("dispatches", [])
        elif isinstance(data, list):
            # 兼容舊格式（裸陣列）
            dispatches = data
        else:
            return False
        return bool(dispatches)
    except (json.JSONDecodeError, OSError, Exception):
        # JSON 損毀 / 讀取失敗 → 視為無 active dispatch（不阻擋 hook）
        return False


def _find_repo_root() -> Optional[Path]:
    """向上尋找含 docs/work-logs 的祖先目錄（hook 隨 worktree/主 repo 走皆成立）"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "work-logs").exists():
            return parent
    return None


def get_active_in_progress_ticket() -> Optional[dict]:
    """
    掃描 docs/work-logs/**/tickets/*.md 找 status=in_progress ticket

    Returns:
        {"type": ..., "current_phase": ...} 若找到；None 若無或讀取失敗
        多個 in_progress 時取 started_at 最新者
    """
    try:
        root = _find_repo_root()
        if root is None:
            return None
        in_progress = []
        for path in root.glob("docs/work-logs/**/tickets/*.md"):
            try:
                fm = parse_frontmatter(path.read_text(encoding="utf-8"))
                if fm.get("status") == "in_progress":
                    in_progress.append((str(fm.get("started_at") or ""), fm))
            except Exception:
                # 單一檔案解析失敗不影響其他 ticket 掃描
                continue
        if not in_progress:
            return None
        in_progress.sort(key=lambda x: x[0], reverse=True)
        fm = in_progress[0][1]
        return {
            "type": fm.get("type"),
            "current_phase": fm.get("current_phase"),
        }
    except Exception:
        return None


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


def generate_skip_reminder(skip_type: str, pattern_info: dict) -> str:
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
        print(json.dumps(generate_hook_output("UserPromptSubmit"), ensure_ascii=False, indent=2))
        return EXIT_SUCCESS

    if input_data is None:
        print(json.dumps(generate_hook_output("UserPromptSubmit"), ensure_ascii=False, indent=2))
        return EXIT_SUCCESS

    # 偵測 subagent 環境：agent_id 僅在 subagent 中出現
    if is_subagent_environment(input_data):
        logger.info("偵測到 subagent 環境（agent_id=%s），跳過流程省略提醒", input_data.get("agent_id"))
        # 輸出基本 JSON（無省略意圖）
        print(json.dumps(generate_hook_output("UserPromptSubmit"), ensure_ascii=False, indent=2))
        return EXIT_SUCCESS

    user_input = input_data.get("prompt", "")

    if not user_input:
        # 無使用者輸入，輸出基本 JSON
        print(json.dumps(generate_hook_output("UserPromptSubmit"), ensure_ascii=False, indent=2))
        return EXIT_SUCCESS

    skip_type, pattern_info = detect_skip_intent(user_input)

    # Active-dispatch guard（cold path：偵測到 skip intent 才查 dispatch-active.json）
    # 代理人執行中時用戶輸入易誤觸驗收/省略偵測，靜默避免誤報（W11-004.3）
    if skip_type:
        try:
            if has_active_dispatch():
                logger.info(f"偵測到 active dispatch，靜音 {skip_type} 提醒")
                print(json.dumps(generate_hook_output("UserPromptSubmit"), ensure_ascii=False, indent=2))
                return EXIT_SUCCESS
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
            print(json.dumps(generate_hook_output("UserPromptSubmit"), ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

    if skip_type and pattern_info:
        logger.info(f"偵測到流程省略意圖: {skip_type}")
        reminder = generate_skip_reminder(skip_type, pattern_info)

        # 輸出 Hook 協定 JSON 到 stdout（包含提醒訊息）
        hook_output = generate_hook_output("UserPromptSubmit", reminder)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 同時輸出提醒訊息到 stderr（雙通道要求）
        print(reminder, file=sys.stderr)
        logger.info(f"省略意圖詳情: {pattern_info['description']}")
    else:
        # 未偵測到省略意圖，輸出基本 JSON
        print(json.dumps(generate_hook_output("UserPromptSubmit"), ensure_ascii=False, indent=2))

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "process-skip-guard"))
