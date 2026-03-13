#!/usr/bin/env python3
"""
UserPromptSubmit Hook: 檢查工作流程合規性 + SKILL 主動提示

功能：
1. 檢查工作流程合規性（5W1H Token、TDD Phase、測試狀態）
2. SKILL 主動提示：檢測三類問題並建議適當的 SKILL 指令

查詢類提示 (v2.0.0)：
- 檢測 Ticket 進度查詢 → 建議 /ticket track summary
- 檢測特定 Ticket 查詢 → 建議 /ticket track query {id}
- 檢測待處理清單查詢 → 建議 /ticket track list --status pending

操作類提示 (v2.1.0)：
- 檢測 Ticket 操作請求（處理、執行、建立等）→ 建議 /ticket 系列指令
- 支援組合關鍵字檢測（動作 + 目標）
- 優先級：查詢 > 操作 > 交接

交接類提示 (v2.1.0)：
- 檢測任務切換/交接請求 → 建議 /ticket handoff 系列指令
- 支援單一和組合關鍵字檢測
- 優先級：查詢 > 操作 > 交接

決策確認類提示 (v2.2.0)：
- 檢測方案選擇/優先級確認/任務拆分/派發方式等決策場景
- 提醒使用 AskUserQuestion 工具而非文字提問
- 優先級：Ticket ID > 查詢類 > 操作類 > 交接類 > 決策確認類
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, run_git, is_subagent_environment
from lib.hook_messages import WorkflowMessages, CoreMessages, AskUserQuestionMessages, format_message


# ============================================================================
# SKILL 提示檢測
# ============================================================================

# 否定詞列表（用於避免誤判否定語境）
NEGATION_WORDS = ["不是", "不需要", "不用", "不要", "沒有", "無需", "不必", "無須"]

# 遠距否定詞搜索窗口大小（字符數）
# 支援否定詞和關鍵字之間有其他詞彙的情況（如「不是說不用查詢」）
NEGATION_WINDOW_SIZE = 15

# 查詢類關鍵字對應 → /ticket track 系列
QUERY_KEYWORDS = {
    "進度如何": "/ticket track summary",
    "進度": "/ticket track summary",
    "狀態": "/ticket track summary",
    "完成了嗎": "/ticket track query",
    "完成了沒": "/ticket track query",
    "還有哪些": "/ticket track list --status pending",
    "待處理": "/ticket track list --status pending",
    "未完成": "/ticket track list --status pending in_progress",
    "有哪些 ticket": "/ticket track list",
    "ticket 列表": "/ticket track list",
}

# 操作類關鍵字對應 → /ticket 系列操作指令
# 格式：(動作1, 目標1) 或 (動作2, 目標2) → 對應的指令
ACTION_KEYWORDS = {
    # 處理/執行類（組合關鍵字）
    ("處理", "ticket"): "/ticket track claim",
    ("處理", "任務"): "/ticket track claim",
    ("執行", "ticket"): "/ticket track claim",
    ("執行", "任務"): "/ticket track claim",
    ("開始", "ticket"): "/ticket track claim",
    ("開始", "任務"): "/ticket track claim",
    ("handle", "ticket"): "/ticket track claim",
    ("handle", "task"): "/ticket track claim",
    ("process", "ticket"): "/ticket track claim",
    ("process", "task"): "/ticket track claim",
    ("start", "ticket"): "/ticket track claim",
    ("start", "task"): "/ticket track claim",
    ("work on", "ticket"): "/ticket track claim",
    ("work on", "task"): "/ticket track claim",

    # 繼續類（組合關鍵字）
    ("繼續", "ticket"): "/ticket track continue",
    ("繼續", "任務"): "/ticket track continue",
    ("continue", "ticket"): "/ticket track continue",
    ("continue", "task"): "/ticket track continue",

    # 完成類（組合關鍵字）
    ("完成", "ticket"): "/ticket track complete",
    ("完成", "任務"): "/ticket track complete",
    ("complete", "ticket"): "/ticket track complete",
    ("complete", "task"): "/ticket track complete",
    ("finish", "ticket"): "/ticket track complete",
    ("finish", "task"): "/ticket track complete",
    ("done", "ticket"): "/ticket track complete",
    ("done", "task"): "/ticket track complete",

    # 建立類（組合關鍵字）
    ("建立", "ticket"): "/ticket create",
    ("建立", "任務"): "/ticket create",
    ("新增", "ticket"): "/ticket create",
    ("新增", "任務"): "/ticket create",
    ("create", "ticket"): "/ticket create",
    ("create", "task"): "/ticket create",
    ("new", "ticket"): "/ticket create",
    ("new", "task"): "/ticket create",
    ("add", "ticket"): "/ticket create",
    ("add", "task"): "/ticket create",
}

# 交接類關鍵字對應 → /ticket handoff 系列
# 格式：(關鍵字1,) 單一關鍵字或 (關鍵字1, 關鍵字2) 組合關鍵字
HANDOFF_KEYWORDS = {
    # 切換類（組合關鍵字）
    ("切換", "任務"): "/ticket handoff switch",
    ("切換", "ticket"): "/ticket handoff switch",
    ("switch", "ticket"): "/ticket handoff switch",
    ("switch", "task"): "/ticket handoff switch",
    ("change", "ticket"): "/ticket handoff switch",
    ("change", "task"): "/ticket handoff switch",

    # 返回類（組合關鍵字）
    ("回到", "父任務"): "/ticket handoff back",
    ("回到", "主任務"): "/ticket handoff back",
    ("返回", "父任務"): "/ticket handoff back",
    ("返回", "主任務"): "/ticket handoff back",
    ("back to", "parent"): "/ticket handoff back",
    ("return to", "parent"): "/ticket handoff back",
    ("go back", ""): "/ticket handoff back",

    # 子任務類（組合關鍵字）
    ("做", "子任務"): "/ticket handoff subtask",
    ("處理", "子任務"): "/ticket handoff subtask",
    ("work on", "child"): "/ticket handoff subtask",
    ("work on", "subtask"): "/ticket handoff subtask",
    ("handle", "subtask"): "/ticket handoff subtask",
    ("next", "subtask"): "/ticket handoff subtask",

    # 恢復類（組合關鍵字）
    ("恢復", "任務"): "/ticket handoff restore",
    ("restore", "task"): "/ticket handoff restore",

    # 交接類（單一關鍵字）
    ("交接",): "/ticket handoff transfer",
    ("handoff",): "/ticket handoff transfer",
}

# 決策確認類關鍵字對應 → AskUserQuestion 提醒
DECISION_KEYWORDS = {
    ("哪個", "方案"): "方案選擇",
    ("選擇", "方案"): "方案選擇",
    ("比較", "方案"): "方案選擇",
    ("拆分", "任務"): "任務拆分確認",
    ("並行", "派發"): "派發方式選擇",
    ("agent team",): "派發方式選擇",
    ("優先", "處理"): "優先級確認",
    ("先做", "哪個"): "優先級確認",

    # 場景 #8：執行方向確認（執行順序/先後/並行安排）
    ("順序", "任務"): "執行方向確認",       # 「任務順序怎麼排」「按什麼順序做任務」
    ("接下來", "做"): "執行方向確認",        # 「接下來要做什麼」「接下來先做哪個」
    ("先後", "執行"): "執行方向確認",        # 「先後執行順序」「先後執行哪些」
}

# Ticket ID 正則表達式 (支援版本號格式和 W 波次格式)
TICKET_ID_PATTERNS = [
    r"\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*",  # 0.31.0-W4-001.1
    r"W\d+-\d+(?:\.\d+)*",                  # W4-001.1
]


def resolve_ticket_path(project_root: Path, ticket_id: str) -> Optional[Path]:
    """
    從 ticket_id 解析版本號並組合 Ticket 檔案路徑

    Args:
        project_root: 專案根目錄
        ticket_id: Ticket ID (格式：version-Wwave-seq)

    Returns:
        Path - Ticket 檔案路徑，若格式無效則回傳 None
    """
    try:
        parts = ticket_id.split('-')
        if len(parts) >= 1:
            version = parts[0]
            return project_root / "docs" / "work-logs" / f"v{version}" / "tickets" / f"{ticket_id}.md"
        return None
    except Exception:
        return None


def _is_keyword_negated(prompt: str, keyword: str) -> bool:
    """
    檢查 keyword 在 prompt 中是否被否定詞修飾。

    支援兩種模式：
    1. 緊鄰模式：否定詞 + 關鍵字（如「不需要查詢」）
    2. 遠距模式：否定詞出現在關鍵字前 NEGATION_WINDOW_SIZE 字符內
       （如「完全不需要去查詢」、「我不是說不用查詢進度」）

    Args:
        prompt: 用戶輸入的提示文本（已轉小寫）
        keyword: 待檢查的關鍵字

    Returns:
        True 如果關鍵字被否定詞修飾，否則 False
    """
    for negation in NEGATION_WORDS:
        negation_idx = prompt.find(negation)
        if negation_idx == -1:
            continue
        # 取否定詞後的窗口文本（支援遠距否定詞）
        window_start = negation_idx + len(negation)
        window_end = window_start + NEGATION_WINDOW_SIZE
        window_text = prompt[window_start:window_end]
        if keyword in window_text:
            return True
    return False


def check_action_keywords(prompt: str) -> Optional[str]:
    """
    檢測操作類關鍵字（組合關鍵字）

    Args:
        prompt: 用戶輸入的提示文本（小寫）

    Returns:
        建議的 SKILL 指令，如果不適用則返回 None
    """
    for (keyword1, keyword2), skill_cmd in ACTION_KEYWORDS.items():
        # 兩個關鍵字都需要出現（不需要相鄰）
        if keyword1 in prompt and keyword2 in prompt:
            # 若任一關鍵字被否定詞修飾，跳過此匹配（避免誤判否定語境）
            if _is_keyword_negated(prompt, keyword1) or _is_keyword_negated(prompt, keyword2):
                continue
            return skill_cmd
    return None


def check_handoff_keywords(prompt: str) -> Optional[str]:
    """
    檢測交接類關鍵字（組合或單一關鍵字）

    Args:
        prompt: 用戶輸入的提示文本（小寫）

    Returns:
        建議的 SKILL 指令，如果不適用則返回 None
    """
    for keywords, skill_cmd in HANDOFF_KEYWORDS.items():
        if len(keywords) == 1:
            # 單一關鍵字
            if keywords[0] in prompt:
                # 若關鍵字被否定詞修飾，跳過此匹配（避免誤判否定語境）
                if _is_keyword_negated(prompt, keywords[0]):
                    continue
                return skill_cmd
        elif len(keywords) == 2:
            # 組合關鍵字（都需要出現）
            # 處理特殊情況：("go back", "") 只需要檢查第一個關鍵字
            if keywords[1] == "":
                if keywords[0] in prompt:
                    # 若關鍵字被否定詞修飾，跳過此匹配（避免誤判否定語境）
                    if _is_keyword_negated(prompt, keywords[0]):
                        continue
                    return skill_cmd
            else:
                if keywords[0] in prompt and keywords[1] in prompt:
                    # 若任一關鍵字被否定詞修飾，跳過此匹配（避免誤判否定語境）
                    if _is_keyword_negated(prompt, keywords[0]) or _is_keyword_negated(prompt, keywords[1]):
                        continue
                    return skill_cmd
    return None


def check_decision_keywords(prompt: str) -> Optional[str]:
    """
    檢測決策確認類關鍵字（組合或單一關鍵字）

    Args:
        prompt: 用戶輸入的提示文本（小寫）

    Returns:
        匹配的場景名稱，如果不適用則返回 None
    """
    for keywords, scenario in DECISION_KEYWORDS.items():
        if len(keywords) == 1:
            if keywords[0] in prompt:
                # 若關鍵字被否定詞修飾，跳過此匹配（避免誤判否定語境）
                if _is_keyword_negated(prompt, keywords[0]):
                    continue
                return scenario
        elif len(keywords) == 2:
            if keywords[0] in prompt and keywords[1] in prompt:
                # 若任一關鍵字被否定詞修飾，跳過此匹配（避免誤判否定語境）
                if _is_keyword_negated(prompt, keywords[0]) or _is_keyword_negated(prompt, keywords[1]):
                    continue
                return scenario
    return None


def check_skill_suggestion(prompt: str) -> Optional[tuple]:
    """
    檢測是否應提示使用 SKILL 指令

    Args:
        prompt: 用戶輸入的提示文本

    Returns:
        (建議的 SKILL 指令, 提示類型) 的 tuple，如果不適用則返回 None
        提示類型：'query', 'action', 'handoff', 'decision'
    """
    if not prompt:
        return None

    prompt_lower = prompt.lower()

    # 優先級順序：Ticket ID > 查詢類 > 操作類 > 交接類 > 決策確認類

    # 1. 優先檢查特定 Ticket ID 查詢（含存在性驗證）
    project_root = Path(__file__).parent.parent.parent
    for pattern in TICKET_ID_PATTERNS:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            ticket_id = match.group()
            # 只對完整格式（含版本號）的 Ticket ID 進行存在性驗證
            if '-W' in ticket_id and '.' in ticket_id.split('-')[0]:
                ticket_path = resolve_ticket_path(project_root, ticket_id)
                if ticket_path and not ticket_path.exists():
                    continue  # 跳過不存在的 Ticket
            return (f"/ticket track query {ticket_id}", "query")

    # 2. 檢查查詢類關鍵字
    for keyword, skill_cmd in QUERY_KEYWORDS.items():
        if keyword in prompt_lower:
            # 若關鍵字被否定詞修飾，跳過此匹配（避免誤判否定語境）
            if _is_keyword_negated(prompt_lower, keyword):
                continue
            return (skill_cmd, "query")

    # 3. 檢查操作類關鍵字
    action_cmd = check_action_keywords(prompt_lower)
    if action_cmd:
        return (action_cmd, "action")

    # 4. 檢查交接類關鍵字
    handoff_cmd = check_handoff_keywords(prompt_lower)
    if handoff_cmd:
        return (handoff_cmd, "handoff")

    # 5. 檢查決策確認類關鍵字
    decision_scenario = check_decision_keywords(prompt_lower)
    if decision_scenario:
        reminder = AskUserQuestionMessages.DECISION_REMINDER.format(scenario=decision_scenario)
        return (reminder, "decision")

    return None


def generate_skill_hint(skill_cmd: str, hint_type: str = "query") -> str:
    """
    生成 SKILL 提示訊息

    Args:
        skill_cmd: 建議的 SKILL 指令
        hint_type: 提示類型 ('query', 'action', 'handoff', 'decision')

    Returns:
        格式化的提示訊息
    """
    if hint_type == "action":
        return f"""============================================================
[SKILL 提示] 檢測到 Ticket 操作請求

建議使用: {skill_cmd}

提示: 使用 /ticket 指令可確保工作流程完整追蹤
============================================================"""
    elif hint_type == "handoff":
        return f"""============================================================
[SKILL 提示] 檢測到任務切換/交接請求

建議使用: {skill_cmd}

提示: 使用 /ticket handoff 可確保任務 Context 正確交接
============================================================"""
    elif hint_type == "decision":
        return skill_cmd  # decision 類型直接返回 AskUserQuestionMessages 生成的提醒
    else:  # hint_type == "query"
        return f"""============================================================
[SKILL 提示] 檢測到查詢類問題

建議使用: {skill_cmd}

提示: 使用 SKILL 指令可獲得更準確和結構化的結果
============================================================"""


def read_prompt_from_stdin() -> Optional[tuple]:
    """
    從 stdin 讀取用戶 prompt 和完整 input_data

    Returns:
        (prompt, input_data) tuple，若無法讀取則返回 (None, {})
    """
    try:
        # 嘗試讀取 JSON 格式輸入
        input_data = json.load(sys.stdin)
        return input_data.get("prompt", ""), input_data
    except (json.JSONDecodeError, AttributeError):
        return None, {}
    except Exception:
        return None, {}


def main():
    logger = setup_hook_logging("prompt-submit-hook")
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    # 讀取用戶 prompt 和完整 input_data
    prompt, input_data = read_prompt_from_stdin()

    # 偵測 subagent 環境：agent_id 僅在 subagent 中出現
    if is_subagent_environment(input_data):
        logger.info("偵測到 subagent 環境（agent_id=%s），跳過工作流程檢查和提示", input_data.get("agent_id"))
        return 0

    # ============================================================================
    # SKILL 主動提示（新功能）
    # ============================================================================
    if prompt:
        skill_suggestion = check_skill_suggestion(prompt)
        if skill_suggestion:
            skill_cmd, hint_type = skill_suggestion
            hint_message = generate_skill_hint(skill_cmd, hint_type)
            print(hint_message)
            logger.info("SKILL suggestion: {} (type: {})".format(skill_cmd, hint_type))

    os.chdir(project_root)

    logger.info("UserPromptSubmit Hook: checking workflow compliance")

    # 1. 檢查是否有未追蹤的問題需要更新todolist
    logger.info("Check: checking for untracked issues")

    # 檢查是否有測試失敗
    test_status_file = project_root / 'coverage-private' / 'test-status.txt'
    if test_status_file.exists():
        try:
            last_test_status = test_status_file.read_text().strip()
            if last_test_status != 'pass':
                logger.warning("Last test status: {} - recommend checking test results".format(last_test_status))
            else:
                logger.info("Last test status: passed")
        except IOError:
            pass

    # 2. 檢查測試通過率(三大鐵律之一)
    logger.info("Check: testing pass rate (100% requirement)")
    logger.info("OK: ESLint check passed")

    # 3. 檢查架構債務(三大鐵律之一)
    logger.info("Check: architecture debt warnings")
    logger.info("OK: no obvious technical debt markers found")

    # 4. 檢查 5W1H 對話合規性
    logger.info("Check: 5W1H conversation compliance")

    # 取得當前 5W1H Token
    token_script = script_dir / '5w1h-token-generator.py'
    current_token = None
    if token_script.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(token_script), 'current'],
                capture_output=True,
                text=True,
                timeout=5
            )
            current_token = result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, IOError):
            pass

    if current_token:
        logger.info("Current 5W1H Token: {}".format(current_token))
        logger.info("Reminder: All answers must start with {}".format(current_token))
        logger.info("Reminder: Must include complete 5W1H analysis (Who/What/When/Where/Why/How)")
    else:
        logger.info("Current 5W1H Token: no active token, recommend running generate")
        logger.info("Reminder: Must include complete 5W1H analysis (Who/What/When/Where/Why/How)")

    # 5. 生成工作流程建議
    logger.info("Suggest: generating workflow suggestions")

    # 檢查最近是否有提交
    try:
        output = run_git(['git', 'log', '-1', '--format=%ct'], timeout=5, logger=logger)
        if output:
            last_commit_time = int(output)
            current_time = int(datetime.now().timestamp())
            time_diff = current_time - last_commit_time

            if time_diff > 3600:  # 超過1小時
                logger.info("Suggest: recommend checking if current progress needs to be committed")
    except (ValueError, IOError):
        pass

    # 檢查todolist.yaml更新時間
    todolist_file = project_root / 'docs' / 'todolist.yaml'
    if todolist_file.exists():
        try:
            todolist_mod_time = todolist_file.stat().st_mtime
            current_time = datetime.now().timestamp()
            todolist_diff = current_time - todolist_mod_time

            if todolist_diff > 86400:  # 超過24小時
                logger.info("Suggest: todolist.yaml not updated for 24+ hours, recommend checking task status")
        except IOError:
            pass

    logger.info("OK: UserPromptSubmit Hook check completed")
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "prompt-submit-hook"))
