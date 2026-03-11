#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Ticket ID 驗證 Hook

驗證 Ticket 檔案中的 ID 格式是否符合規範。

功能：
- 驗證 Ticket ID 格式符合正則表達式: ^(\\d+\\.\\d+\\.\\d+)-W(\\d+)-(\\d+(?:\\.\\d+)*)$
- 驗證 Ticket ID 版本與檔案所在目錄版本一致
- 驗證波次號在合理範圍（1-10）
- 格式錯誤時輸出警告訊息

Hook 類型: PostToolUse（非阻塞）
Matcher: Write
監控路徑: `docs/work-logs/*/tickets/*.md` 或 `.claude/tickets/*.md`

使用方式:
    PostToolUse Hook 自動觸發，或手動測試:
    echo '{"tool_name":"Write","tool_input":{"file_path":".claude/tickets/0.31.0-W5-001.md"}}' | python3 ticket-id-validator-hook.py

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
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging, run_hook_safely, read_json_from_stdin,
    get_project_root, save_check_log, validate_hook_input
)

# ============================================================================
# 常數定義
# ============================================================================

# Ticket ID 正規表達式：^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)$
# 範例：0.31.0-W5-001, 0.31.0-W5-001.1, 0.31.0-W5-001.1.2
TICKET_ID_REGEX = r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)$"

# Ticket ID 在檔案中可能出現的位置
TICKET_ID_MARKERS = [
    r"^ticket_id:\s*[\"']?(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)[\"']?",  # YAML frontmatter
    r"^id:\s*[\"']?(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)[\"']?",  # 備選 YAML 欄位
    r"^# [\[\#]?(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)[\]\:]?",  # Markdown 標題
]

# Wave 合理範圍
# 設定為 999 以容許任意大小的 Wave 號
# （實際專案現已執行到 W37，舊的 WAVE_MAX=10 會導致 W10+ 的 Ticket 誤判為無效）
WAVE_MIN = 1
WAVE_MAX = 999

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2

# ============================================================================
# 輸入讀取和驗證
# ============================================================================

# validate_input 已遷移至 hook_utils.validate_hook_input

# ============================================================================
# 檔案路徑檢查
# ============================================================================

def is_ticket_file(file_path: str, logger) -> bool:
    """
    判斷檔案是否為 Ticket 檔案

    Args:
        file_path: 檔案路徑
        logger: Logger 實例

    Returns:
        bool - 是否為 Ticket 檔案
    """
    path = Path(file_path)
    path_str = str(path)

    # 檢查路徑是否符合 Ticket 檔案模式
    return (
        ("docs/work-logs/" in path_str and "/tickets/" in path_str and path_str.endswith(".md")) or
        (".claude/tickets/" in path_str and path_str.endswith(".md"))
    )

def get_directory_version(file_path: str, logger) -> Optional[str]:
    """
    從檔案所在目錄提取版本號

    Args:
        file_path: 檔案路徑
        logger: Logger 實例

    Returns:
        str - 版本號（如 "0.31.0"），或 None 如無法提取

    範例：
    - docs/work-logs/v0.31.0/tickets/0.31.0-W5-001.md -> "0.31.0"
    - .claude/tickets/0.31.0-W5-001.md -> 無版本目錄，返回 None
    """
    path = Path(file_path)

    # 模式 1: docs/work-logs/v{version}/tickets/{id}.md
    if "docs/work-logs/" in str(path):
        parts = path.parts
        for i, part in enumerate(parts):
            if part.startswith("v") and part[1:].replace(".", "").isdigit():
                version = part[1:]  # 移除 'v' 前綴
                logger.debug(f"從目錄提取版本: {version}")
                return version

    # 模式 2: .claude/tickets/{id}.md
    # 此模式中無法從目錄提取版本，需要從 ID 中提取
    return None

# ============================================================================
# Ticket ID 提取和驗證
# ============================================================================

def extract_ticket_id_from_file(file_path: str, logger) -> Optional[str]:
    """
    從 Ticket 檔案中提取 ID

    Args:
        file_path: 檔案路徑
        logger: Logger 實例

    Returns:
        str - Ticket ID，或 None 如無法提取
    """
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"檔案不存在: {file_path}")
            return None

        content = path.read_text(encoding="utf-8")
        logger.debug(f"讀取檔案: {file_path}")

        # 嘗試從檔案內容中提取 ID
        for pattern in TICKET_ID_MARKERS:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                ticket_id = match.group(1)
                logger.info(f"從檔案內容提取 Ticket ID: {ticket_id}")
                return ticket_id

        logger.warning(f"無法從檔案中提取 Ticket ID: {file_path}")
        return None

    except Exception as e:
        logger.error(f"讀取檔案失敗 {file_path}: {e}")
        return None

def validate_ticket_id_format(ticket_id: str, logger) -> Tuple[bool, str]:
    """
    驗證 Ticket ID 格式

    Args:
        ticket_id: Ticket ID
        logger: Logger 實例

    Returns:
        tuple - (is_valid, error_message)
            - is_valid: 格式是否正確
            - error_message: 錯誤訊息（如有）
    """
    if not ticket_id:
        return False, "Ticket ID 為空"

    # 檢查正則表達式匹配
    match = re.match(TICKET_ID_REGEX, ticket_id)
    if not match:
        msg = (
            f"Ticket ID 格式錯誤: {ticket_id}\n"
            f"正規表達式: {TICKET_ID_REGEX}\n"
            f"範例: 0.31.0-W5-001, 0.31.0-W5-001.1"
        )
        logger.error(msg)
        return False, msg

    # 提取版本和波次
    version = match.group(1)
    wave = int(match.group(2))

    logger.info(f"Ticket ID 格式正確: {ticket_id}")
    logger.debug(f"  版本: {version}, 波次: {wave}")

    # 驗證波次在合理範圍
    if not (WAVE_MIN <= wave <= WAVE_MAX):
        msg = (
            f"Wave 號不在合理範圍: {wave}\n"
            f"允許範圍: {WAVE_MIN}-{WAVE_MAX}"
        )
        logger.warning(msg)
        return False, msg

    return True, ""

def validate_ticket_id_version_consistency(
    ticket_id: str,
    directory_version: Optional[str],
    logger
) -> Tuple[bool, str]:
    """
    驗證 Ticket ID 版本與目錄版本一致

    Args:
        ticket_id: Ticket ID
        directory_version: 目錄中提取的版本號
        logger: Logger 實例

    Returns:
        tuple - (is_consistent, warning_message)
            - is_consistent: 版本是否一致
            - warning_message: 警告訊息（如有）
    """
    if not directory_version:
        logger.debug("無法從目錄提取版本，跳過版本一致性檢查")
        return True, ""

    # 從 Ticket ID 中提取版本
    match = re.match(TICKET_ID_REGEX, ticket_id)
    if not match:
        return False, "無法從 Ticket ID 中提取版本"

    id_version = match.group(1)

    if id_version != directory_version:
        msg = (
            f"Ticket ID 版本與目錄版本不一致\n"
            f"  Ticket ID 版本: {id_version}\n"
            f"  目錄版本: {directory_version}\n"
            f"  建議: 確認 Ticket ID 和檔案位置是否正確"
        )
        logger.warning(msg)
        return False, msg

    logger.info(f"版本一致: {id_version}")
    return True, ""

def validate_ticket_id(file_path: str, ticket_id: str, logger) -> Tuple[bool, str]:
    """
    完整的 Ticket ID 驗證

    Args:
        file_path: 檔案路徑
        ticket_id: Ticket ID
        logger: Logger 實例

    Returns:
        tuple - (is_valid, error_message)
            - is_valid: Ticket ID 是否有效
            - error_message: 錯誤訊息（如有）
    """
    # 步驟 1: 驗證格式
    is_valid, error_msg = validate_ticket_id_format(ticket_id, logger)
    if not is_valid:
        return False, error_msg

    # 步驟 2: 驗證版本一致性
    directory_version = get_directory_version(file_path, logger)
    is_consistent, warning_msg = validate_ticket_id_version_consistency(
        ticket_id,
        directory_version,
        logger
    )

    if not is_consistent:
        return False, warning_msg

    return True, ""

# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    is_valid: bool,
    file_path: str,
    ticket_id: Optional[str] = None,
    warning_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        is_valid: Ticket ID 是否有效
        file_path: 檔案路徑
        ticket_id: Ticket ID（如有）
        warning_message: 警告訊息（如有）

    Returns:
        dict - Hook 輸出 JSON

    PostToolUse Hook 不阻塊，只提供警告訊息。
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse"
        }
    }

    if not is_valid and warning_message:
        output["hookSpecificOutput"]["additionalContext"] = (
            f"Ticket ID 驗證警告\n\n{warning_message}\n\n"
            f"詳細日誌: .claude/hook-logs/ticket-id-validator/"
        )

    # 記錄檢查結果
    output["check_result"] = {
        "is_valid": is_valid,
        "file_path": file_path,
        "ticket_id": ticket_id,
        "warning_message": warning_message,
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
    1. 初始化 logger
    2. 讀取 JSON 輸入
    3. 驗證輸入格式
    4. 判斷是否為 Ticket 檔案
    5. 提取 Ticket ID
    6. 驗證 Ticket ID
    7. 生成 Hook 輸出
    8. 儲存日誌

    Returns:
        int - Exit code (0=success, 1=error)
    """
    logger = setup_hook_logging("ticket-id-validator")

    try:
        # 步驟 1: 讀取 JSON 輸入
        logger.info("Ticket ID 驗證 Hook 啟動")
        input_data = read_json_from_stdin(logger)

        # 步驟 2: 驗證輸入格式
        if not validate_hook_input(input_data, logger, ("tool_input",)):
            logger.debug("輸入格式不完整，跳過檢查")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "PostToolUse"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        tool_input = input_data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        logger.info(f"檢查檔案: {file_path}")

        # 步驟 3: 判斷是否為 Ticket 檔案
        if not is_ticket_file(file_path, logger):
            logger.debug("不是 Ticket 檔案，跳過檢查")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "PostToolUse"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        logger.info(f"檢測到 Ticket 檔案: {file_path}")

        # 步驟 4: 提取 Ticket ID
        ticket_id = extract_ticket_id_from_file(file_path, logger)
        if not ticket_id:
            logger.warning(f"無法從檔案提取 Ticket ID")
            warning_msg = f"無法從檔案 {file_path} 中提取 Ticket ID"
            hook_output = generate_hook_output(
                is_valid=False,
                file_path=file_path,
                ticket_id=None,
                warning_message=warning_msg
            )
            print(json.dumps(hook_output, ensure_ascii=False, indent=2))
            status = "INVALID"
            log_entry = f"""[{datetime.now().isoformat()}]
  FilePath: {file_path}
  TicketID: None
  Status: {status}
  Warning: {warning_msg or "None"}

"""
            save_check_log("ticket-id-validator", log_entry, logger)
            return EXIT_SUCCESS

        # 步驟 5: 驗證 Ticket ID
        is_valid, error_msg = validate_ticket_id(file_path, ticket_id, logger)

        logger.info(f"Ticket ID 驗證: is_valid={is_valid}, ticket_id={ticket_id}")

        # 步驟 6: 生成 Hook 輸出
        hook_output = generate_hook_output(
            is_valid=is_valid,
            file_path=file_path,
            ticket_id=ticket_id,
            warning_message=error_msg if not is_valid else None
        )
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 7: 儲存日誌
        status = "VALID" if is_valid else "INVALID"
        log_entry = f"""[{datetime.now().isoformat()}]
  FilePath: {file_path}
  TicketID: {ticket_id}
  Status: {status}
  Warning: {error_msg if not is_valid else "None"}

"""
        save_check_log("ticket-id-validator", log_entry, logger)

        logger.info("Ticket ID 驗證 Hook 完成")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/ticket-id-validator/"
            },
            "error": {
                "type": type(e).__name__,
                "message": str(e)
            }
        }
        print(json.dumps(error_output, ensure_ascii=False, indent=2))
        return EXIT_ERROR

if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "ticket-id-validator"))
