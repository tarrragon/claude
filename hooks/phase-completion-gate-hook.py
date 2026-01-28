#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Phase Completion Gate Hook

在 Phase 完成時驗證報告是否正確上報到 worklog。

功能：
- 監控 Write/Edit 到 docs/work-logs/ 的操作
- 識別 Phase 完成報告
- 檢查 worklog 更新
- 檢查 /ticket-track complete 執行狀態
- 輸出警告或允許繼續

Hook 類型: PostToolUse
觸發時機: Write/Edit 工具執行後

使用方式:
    PostToolUse Hook 自動觸發，或手動測試:
    echo '{"tool_name":"Write","tool_input":{"file_path":"/path/docs/work-logs/v0.30.0/0.30.0-W2-003.md"}}' | python3 phase-completion-gate-hook.py

環境變數:
    HOOK_DEBUG: 啟用詳細日誌（true/false）
"""

import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List


# ============================================================================
# 常數定義
# ============================================================================

# Phase 完成標記
PHASE_COMPLETION_KEYWORDS = [
    "Phase 3b",
    "Phase 4",
    "Phase 完成",
    "實作執行完成",
    "重構優化完成",
    "測試全部通過",
    "改善報告",
    "評估報告"
]

# worklog 相關路徑
WORKLOG_PATTERNS = [
    r"docs/work-logs/v[\d.]+",
    r"docs/work-logs/",
]

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2


# ============================================================================
# 日誌設置
# ============================================================================

def setup_logging() -> None:
    """初始化日誌系統"""
    import os

    log_level = logging.DEBUG if os.getenv("HOOK_DEBUG") == "true" else logging.INFO

    # 建立日誌目錄
    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs" / "phase-completion-gate"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "phase-completion-gate.log"

    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr)
        ]
    )


# ============================================================================
# 輸入讀取和驗證
# ============================================================================

def read_json_from_stdin() -> Dict[str, Any]:
    """
    從 stdin 讀取 JSON 輸入

    Returns:
        dict - 解析後的 JSON 資料

    Raises:
        ValueError: JSON 格式錯誤
    """
    try:
        input_data = json.load(sys.stdin)
        logging.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False, indent=2)}")
        return input_data
    except json.JSONDecodeError as e:
        logging.error(f"JSON 解析錯誤: {e}")
        raise ValueError(f"Invalid JSON input: {e}")


def validate_input(input_data: Dict[str, Any]) -> bool:
    """
    驗證輸入格式

    Args:
        input_data: Hook 輸入資料

    Returns:
        bool - 輸入格式是否正確
    """
    # PostToolUse Hook 需要 tool_name 和 tool_input
    if "tool_name" not in input_data or "tool_input" not in input_data:
        logging.error("缺少必要欄位: tool_name 或 tool_input")
        return False

    return True


# ============================================================================
# 工具操作識別
# ============================================================================

def is_worklog_write_operation(tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """
    判斷是否為 worklog 檔案的寫入操作

    Args:
        tool_name: 工具名稱
        tool_input: 工具輸入

    Returns:
        bool - 是否為 worklog 寫入操作
    """
    # 只監控 Write 和 Edit 工具
    if tool_name not in ["Write", "Edit"]:
        logging.debug(f"工具不在監控範圍: {tool_name}")
        return False

    # 檢查檔案路徑
    file_path = tool_input.get("file_path", "")
    if not file_path:
        logging.debug("缺少 file_path")
        return False

    # 檢查是否為 worklog 檔案
    for pattern in WORKLOG_PATTERNS:
        if pattern in file_path:
            logging.info(f"識別到 worklog 寫入操作: {file_path}")
            return True

    logging.debug(f"檔案路徑不符合 worklog 模式: {file_path}")
    return False


def extract_file_content_from_input(tool_input: Dict[str, Any]) -> Optional[str]:
    """
    從工具輸入中提取檔案內容

    Args:
        tool_input: 工具輸入

    Returns:
        str - 檔案內容或 None
    """
    # Write 工具：content 欄位包含要寫入的內容
    content = tool_input.get("content")
    if content:
        logging.debug("從 Write 工具提取內容")
        return content

    # Edit 工具：tool_response 中可能包含檔案內容
    # 但通常 Edit 只是修改現有檔案，我們應該直接讀取檔案
    return None


# ============================================================================
# Phase 完成識別
# ============================================================================

def is_phase_completion_report(file_path: str, content: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    判斷是否為 Phase 完成報告

    Args:
        file_path: 檔案路徑
        content: 檔案內容（如果可用）

    Returns:
        tuple - (is_completion, phase_type)
    """
    # 首先檢查檔案名稱中是否包含 Phase 標記
    for keyword in PHASE_COMPLETION_KEYWORDS:
        if keyword in file_path:
            logging.info(f"從檔案名稱識別 Phase 完成: {keyword}")
            return True, keyword

    # 如果提供了內容，檢查內容中的 Phase 標記
    if content:
        for keyword in PHASE_COMPLETION_KEYWORDS:
            if keyword.lower() in content.lower():
                logging.info(f"從內容識別 Phase 完成: {keyword}")
                return True, keyword

        # 檢查標題中是否包含評估或完成相關詞彙
        title_patterns = [
            r"## Phase \d+ 評估",
            r"## Phase 完成",
            r"## 重構評估",
            r"## 實作執行結果",
        ]
        for pattern in title_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                logging.info(f"從內容模式識別 Phase 完成: {pattern}")
                return True, "Phase Complete"

    logging.debug(f"未識別為 Phase 完成報告: {file_path}")
    return False, None


# ============================================================================
# worklog 驗證
# ============================================================================

def read_file_content(file_path: str) -> Optional[str]:
    """
    讀取檔案內容

    Args:
        file_path: 檔案路徑

    Returns:
        str - 檔案內容或 None
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logging.debug(f"成功讀取檔案: {file_path}")
        return content
    except Exception as e:
        logging.warning(f"無法讀取檔案 {file_path}: {e}")
        return None


def check_worklog_structure(file_path: str, content: str) -> Tuple[bool, List[str]]:
    """
    檢查 worklog 檔案結構

    Args:
        file_path: 檔案路徑
        content: 檔案內容

    Returns:
        tuple - (is_complete, missing_items)
    """
    missing_items = []

    # 必需的部分
    required_sections = [
        (r"## Problem Analysis", "問題分析部分"),
        (r"## Solution", "解決方案部分"),
        (r"## Test Results", "測試結果部分"),
    ]

    for pattern, section_name in required_sections:
        if not re.search(pattern, content):
            logging.warning(f"缺少 {section_name}")
            missing_items.append(section_name)

    # 檢查是否有實際內容（而不是空白的 TODO）
    has_problem_analysis = bool(re.search(r"## Problem Analysis\n\n(?!<!-- To be filled|-->\s*$)", content, re.MULTILINE))
    if not has_problem_analysis:
        logging.warning("Problem Analysis 部分缺少實際內容")
        missing_items.append("Problem Analysis 實際內容")

    has_solution = bool(re.search(r"## Solution\n\n(?!<!-- To be filled|-->\s*$)", content, re.MULTILINE))
    if not has_solution:
        logging.warning("Solution 部分缺少實際內容")
        missing_items.append("Solution 實際內容")

    is_complete = len(missing_items) == 0
    return is_complete, missing_items


def check_ticket_completion_status(project_dir: str, ticket_id: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    檢查 Ticket 是否已標記為完成

    Args:
        project_dir: 專案目錄
        ticket_id: Ticket ID（如果可以從檔案名稱提取）

    Returns:
        tuple - (has_completed_record, message)
    """
    # 查找最新的 Ticket 完成記錄
    # 通常通過查看 Ticket 檔案中的 status 欄位
    # 但在 Hook 中，我們只能根據操作的上下文來推斷

    # 如果我們無法直接驗證，則建議用戶檢查
    message = None
    if ticket_id:
        message = f"Ticket {ticket_id} 的完成狀態需要手動驗證"
    else:
        message = "無法自動驗證 Ticket 完成狀態"

    return False, message


def get_project_root() -> str:
    """取得專案根目錄"""
    import os
    project_root = os.getenv("CLAUDE_PROJECT_DIR", str(Path.cwd()))
    return project_root


# ============================================================================
# 報告生成和儲存
# ============================================================================

def generate_completion_report(
    file_path: str,
    is_phase_completion: bool,
    phase_type: Optional[str],
    worklog_complete: bool,
    missing_items: List[str],
    ticket_msg: Optional[str]
) -> Dict[str, Any]:
    """
    生成 Phase 完成驗證報告

    Args:
        file_path: worklog 檔案路徑
        is_phase_completion: 是否為 Phase 完成報告
        phase_type: Phase 類型
        worklog_complete: worklog 是否完整
        missing_items: 缺少的項目列表
        ticket_msg: Ticket 相關訊息

    Returns:
        dict - 報告內容
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "file_path": file_path,
        "is_phase_completion": is_phase_completion,
        "phase_type": phase_type,
        "worklog_complete": worklog_complete,
        "missing_items": missing_items,
        "ticket_msg": ticket_msg,
    }

    return report


def save_completion_report(project_dir: str, report: Dict[str, Any]) -> str:
    """
    儲存 Phase 完成驗證報告

    Args:
        project_dir: 專案目錄
        report: 報告內容

    Returns:
        str - 報告檔案路徑
    """
    log_dir = Path(project_dir) / ".claude" / "hook-logs" / "phase-completion-gate"
    log_dir.mkdir(parents=True, exist_ok=True)

    report_file = log_dir / f"completion-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logging.debug(f"報告已儲存: {report_file}")
        return str(report_file)
    except Exception as e:
        logging.warning(f"儲存報告失敗: {e}")
        return ""


# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    is_phase_completion: bool,
    worklog_complete: bool,
    missing_items: List[str],
    ticket_msg: Optional[str]
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        is_phase_completion: 是否為 Phase 完成報告
        worklog_complete: worklog 是否完整
        missing_items: 缺少的項目列表
        ticket_msg: Ticket 相關訊息

    Returns:
        dict - Hook 輸出 JSON
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
        }
    }

    # 如果是 Phase 完成報告但 worklog 不完整，輸出警告
    if is_phase_completion and not worklog_complete:
        warning_msg = f"""警告：Phase 完成報告缺少必要內容

缺少的部分:
{chr(10).join(f'- {item}' for item in missing_items)}

建議:
1. 補充上述缺少的部分
2. 確保提供完整的問題分析、解決方案和測試結果
3. 執行 /ticket-track complete {{ticket-id}} 標記 Ticket 完成

詳見: .claude/rules/flows/tdd-flow.md"""

        output["hookSpecificOutput"]["additionalContext"] = warning_msg
        logging.warning("檢測到 Phase 完成報告不完整")

    # 如果無法驗證 Ticket 完成狀態，提供提醒
    if is_phase_completion and ticket_msg:
        ticket_reminder = f"\n\n提醒: {ticket_msg}"
        if "additionalContext" in output["hookSpecificOutput"]:
            output["hookSpecificOutput"]["additionalContext"] += ticket_reminder
        else:
            output["hookSpecificOutput"]["additionalContext"] = ticket_reminder

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
    4. 識別是否為 worklog 寫入操作
    5. 如果是，讀取檔案內容並檢查是否為 Phase 完成報告
    6. 檢查 worklog 結構完整性
    7. 生成 Hook 輸出
    8. 儲存報告日誌
    9. 決定 exit code

    Returns:
        int - Exit code
    """
    try:
        # 步驟 1: 初始化日誌
        setup_logging()
        logging.info("Phase Completion Gate Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin()

        # 步驟 3: 驗證輸入格式
        if not validate_input(input_data):
            logging.error("輸入格式錯誤")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "PostToolUse"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # 步驟 4: 識別是否為 worklog 寫入操作
        is_worklog_op = is_worklog_write_operation(tool_name, tool_input)

        # 初始化標誌
        is_phase_completion = False
        worklog_complete = True
        missing_items = []
        ticket_msg = None
        phase_type = None

        # 如果是 worklog 寫入操作，進行後續檢查
        if is_worklog_op:
            file_path = tool_input.get("file_path", "")
            logging.info(f"處理 worklog 檔案: {file_path}")

            # 步驟 5: 讀取檔案內容
            content = extract_file_content_from_input(tool_input)

            # 如果從工具輸入無法提取內容，嘗試直接讀取檔案
            if not content and tool_name == "Edit":
                content = read_file_content(file_path)

            # 步驟 6: 識別是否為 Phase 完成報告
            is_phase_completion, phase_type = is_phase_completion_report(file_path, content)

            if is_phase_completion:
                logging.info(f"識別到 Phase 完成報告: {phase_type}")

                # 步驟 7: 檢查 worklog 結構完整性
                if content:
                    worklog_complete, missing_items = check_worklog_structure(file_path, content)
                    logging.info(f"worklog 完整性檢查: complete={worklog_complete}, missing={len(missing_items)}")
                else:
                    logging.warning("無法讀取檔案內容進行完整性檢查")
                    worklog_complete = False
                    missing_items = ["無法讀取檔案內容進行驗證"]

                # 檢查 Ticket 完成狀態
                project_root = get_project_root()
                _, ticket_msg = check_ticket_completion_status(project_root, None)

        # 步驟 8: 生成 Hook 輸出
        hook_output = generate_hook_output(
            is_phase_completion, worklog_complete, missing_items, ticket_msg
        )
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 9: 儲存報告日誌
        if is_phase_completion:
            project_root = get_project_root()
            report = generate_completion_report(
                file_path, is_phase_completion, phase_type,
                worklog_complete, missing_items, ticket_msg
            )
            save_completion_report(project_root, report)

        logging.info("Phase Completion Gate Hook 檢查完成")
        return EXIT_SUCCESS

    except Exception as e:
        logging.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/phase-completion-gate/"
            },
            "error": {
                "type": type(e).__name__,
                "message": str(e)
            }
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
