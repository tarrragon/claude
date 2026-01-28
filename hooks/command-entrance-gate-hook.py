#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Command Entrance Gate Hook - 阻塞式驗證

在接收開發/修改命令時進行嚴格驗證，阻止無效的開發操作。

功能：
- 識別開發/修改命令
- 驗證 Ticket 是否存在且已認領
- 驗證 Ticket 是否包含決策樹欄位
- 無效時阻止執行（exit code 2）
- 有效時允許執行（exit code 0）

Exit Code：
- 0 (EXIT_SUCCESS): 命令允許執行（非開發命令或 Ticket 驗證通過）
- 2 (EXIT_BLOCK): 阻止執行（開發命令但 Ticket 驗證失敗）
- 1 (EXIT_ERROR): Hook 執行錯誤

Hook 類型: UserPromptSubmit
觸發時機: 接收用戶命令時

使用方式:
    UserPromptSubmit Hook 自動觸發，或手動測試:
    echo '{"prompt":"實作新功能"}' | python3 command-entrance-gate-hook.py

環境變數:
    HOOK_DEBUG: 啟用詳細日誌（true/false）

驗證規則：
1. 只對「開發/修改命令」進行驗證（包含 DEVELOPMENT_KEYWORDS）
2. 如果是開發命令，必須存在 pending 或 in_progress 的 Ticket
3. 如果 Ticket 狀態為 pending，必須先認領（claim）
4. 如果 Ticket 已認領，必須包含決策樹欄位（decision_tree_path 或 ## 決策樹）
5. 所有驗證通過才允許執行
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

# 開發命令關鍵字
DEVELOPMENT_KEYWORDS = [
    "實作", "建立", "修復", "處理", "重構",
    "轉換", "新增", "刪除", "修改", "優化",
    "改進", "升級", "設計", "規劃", "實現"
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
    log_dir = project_dir / ".claude" / "hook-logs" / "command-entrance-gate"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "command-entrance-gate.log"

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
    # UserPromptSubmit Hook 至少需要 prompt 欄位
    if "prompt" not in input_data:
        logging.error("缺少必要欄位: prompt")
        return False

    return True


# ============================================================================
# 開發命令識別
# ============================================================================

def is_development_command(prompt: str) -> bool:
    """
    判斷是否為開發/修改命令

    Args:
        prompt: 用戶提示文本

    Returns:
        bool - 是否為開發/修改命令
    """
    if not prompt:
        return False

    # 轉換為小寫以進行不區分大小寫的匹配
    prompt_lower = prompt.lower()

    # 檢查是否包含開發命令關鍵字
    for keyword in DEVELOPMENT_KEYWORDS:
        if keyword.lower() in prompt_lower:
            logging.info(f"識別開發命令關鍵字: {keyword}")
            return True

    logging.debug(f"未識別為開發命令: {prompt[:50]}...")
    return False


# ============================================================================
# Ticket 檢查
# ============================================================================

def find_ticket_files() -> List[Path]:
    """
    尋找所有 Ticket 檔案

    Returns:
        list - Ticket 檔案路徑清單
    """
    import os

    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))

    # 搜尋位置：.claude/tickets/ 和 docs/work-logs/*/tickets/
    ticket_locations = [
        project_dir / ".claude" / "tickets",
        project_dir / "docs" / "work-logs"
    ]

    all_tickets = []

    # 搜尋 .claude/tickets/
    if ticket_locations[0].exists():
        all_tickets.extend(ticket_locations[0].glob("*.md"))

    # 搜尋 docs/work-logs/*/tickets/
    for version_dir in ticket_locations[1].glob("v*"):
        tickets_dir = version_dir / "tickets"
        if tickets_dir.exists():
            all_tickets.extend(tickets_dir.glob("*.md"))

    logging.debug(f"找到 {len(all_tickets)} 個 Ticket 檔案")
    return all_tickets


def extract_ticket_status(file_path: Path) -> Tuple[Optional[str], Optional[str], str]:
    """
    從 Ticket 檔案提取 ID、狀態和完整內容

    Args:
        file_path: Ticket 檔案路徑

    Returns:
        tuple - (ticket_id, status, content) 或 (None, None, "")
    """
    try:
        content = file_path.read_text(encoding="utf-8")

        # 嘗試從檔案名稱提取 ID
        ticket_id = file_path.stem

        # 從 YAML frontmatter 提取 status
        status = None
        if content.startswith("---"):
            frontmatter_end = content.find("---", 3)
            if frontmatter_end > 0:
                frontmatter = content[:frontmatter_end]
                # 尋找 status: 行
                status_match = re.search(r"status:\s*(\S+)", frontmatter)
                if status_match:
                    status = status_match.group(1)

        return ticket_id, status, content
    except Exception as e:
        logging.debug(f"無法提取 Ticket 狀態 {file_path}: {e}")
        return None, None, ""


def validate_ticket_has_decision_tree(ticket_content: str) -> bool:
    """
    驗證 Ticket 是否包含決策樹欄位

    檢查 Ticket 是否在 YAML frontmatter 中包含 decision_tree_path 欄位，
    或在內容中包含「## 決策樹」區段。

    Args:
        ticket_content: Ticket 檔案內容

    Returns:
        bool - 是否包含決策樹欄位
    """
    if not ticket_content:
        logging.debug("Ticket 內容為空")
        return False

    # 檢查 YAML frontmatter 中的 decision_tree_path 欄位
    if "decision_tree_path:" in ticket_content:
        logging.debug("在 YAML frontmatter 中找到 decision_tree_path 欄位")
        return True

    # 檢查內容中的「## 決策樹」區段（多個變體）
    decision_tree_markers = [
        "## 決策樹",
        "## Decision Tree",
        "## 決策樹路徑",
        "## 決策流程",
    ]

    for marker in decision_tree_markers:
        if marker in ticket_content:
            logging.debug(f"在內容中找到決策樹標記: {marker}")
            return True

    logging.debug("未在 Ticket 中找到決策樹欄位")
    return False


def get_latest_pending_ticket() -> Optional[Tuple[str, str, str]]:
    """
    取得最新的待處理 Ticket

    Returns:
        tuple - (ticket_id, status, content) 或 None
    """
    tickets = find_ticket_files()

    # 按修改時間排序（最新優先）
    sorted_tickets = sorted(tickets, key=lambda p: p.stat().st_mtime, reverse=True)

    for ticket_file in sorted_tickets:
        ticket_id, status, content = extract_ticket_status(ticket_file)
        if ticket_id and status in ["pending", "in_progress"]:
            logging.info(f"找到待處理 Ticket: {ticket_id} (status={status})")
            return ticket_id, status, content

    logging.debug("未找到待處理 Ticket")
    return None


def check_ticket_status() -> Tuple[bool, Optional[str], Optional[str]]:
    """
    檢查 Ticket 狀態（阻塞式）

    此函式執行兩層驗證：
    1. Ticket 是否存在且已認領
    2. Ticket 是否包含必要的決策樹欄位

    Returns:
        tuple - (is_valid, error_message, ticket_id)
            - is_valid: Ticket 是否有效（存在、已認領、包含決策樹）
            - error_message: 如果無效，説明問題和建議操作；如果有效，為 None
            - ticket_id: Ticket ID（如果找到）
    """
    ticket_info = get_latest_pending_ticket()

    # 驗證 1：Ticket 是否存在且已認領
    if ticket_info is None:
        msg = """錯誤：未找到待處理的 Ticket

為什麼阻止執行：
  開發命令必須有對應的 Ticket，確保工作可追蹤和驗收。

建議操作:
  1. 執行 `/ticket-create` 建立新 Ticket
  2. 或執行 `/ticket-track claim {id}` 認領現有 Ticket

詳見: .claude/rules/core/decision-tree.md
詳見: .claude/rules/forbidden/skip-gate.md"""

        logging.warning("未找到待處理 Ticket - 阻止執行")
        return False, msg, None

    ticket_id, status, content = ticket_info

    if status == "pending":
        msg = f"""錯誤：Ticket {ticket_id} 尚未認領

為什麼阻止執行：
  Ticket 必須被認領後才能開始工作，這確保任務責任清晰。

建議操作:
  1. 執行 `/ticket-track claim {ticket_id}` 認領 Ticket
  2. 使用 `/ticket-track query {ticket_id}` 查看詳細資訊

詳見: .claude/rules/core/decision-tree.md
詳見: .claude/rules/forbidden/skip-gate.md"""

        logging.warning(f"Ticket {ticket_id} 未被認領 - 阻止執行")
        return False, msg, ticket_id

    # 驗證 2：Ticket 是否包含決策樹欄位
    if status == "in_progress":
        if not validate_ticket_has_decision_tree(content):
            msg = f"""錯誤：Ticket {ticket_id} 缺少決策樹欄位

為什麼阻止執行：
  Ticket 必須包含決策樹路徑或決策過程，確保決策可追蹤。

建議操作:
  1. 編輯 Ticket 檔案，添加決策樹資訊：
     - 在 YAML frontmatter 中添加 decision_tree_path 欄位，或
     - 在內容中添加「## 決策樹」區段
  2. 使用 `/ticket-track query {ticket_id}` 查看當前 Ticket
  3. 完成編輯後重新執行命令

詳見: .claude/rules/core/decision-tree.md
詳見: .claude/rules/forbidden/skip-gate.md"""

            logging.warning(f"Ticket {ticket_id} 缺少決策樹欄位 - 阻止執行")
            return False, msg, ticket_id

        # 所有驗證通過
        logging.info(f"Ticket {ticket_id} 驗證通過，允許繼續")
        return True, None, ticket_id

    # 未知狀態
    msg = f"""錯誤：Ticket {ticket_id} 狀態不明 ({status})

為什麼阻止執行：
  Ticket 狀態應為 pending 或 in_progress，其他狀態不可執行操作。

建議操作:
  使用 `/ticket-track query {ticket_id}` 查看詳細資訊，
  或聯繫專案管理員。

詳見: .claude/rules/flows/ticket-lifecycle.md"""

    logging.warning(f"Ticket {ticket_id} 狀態不明 ({status}) - 阻止執行")
    return False, msg, ticket_id


# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    prompt: str,
    is_dev_cmd: bool,
    is_valid: bool,
    error_msg: Optional[str],
    ticket_id: Optional[str]
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        prompt: 用戶提示文本
        is_dev_cmd: 是否為開發命令
        is_valid: Ticket 驗證是否通過
        error_msg: 如果驗證失敗，提供的錯誤訊息
        ticket_id: Ticket ID

    Returns:
        dict - Hook 輸出 JSON
    """
    # 決定是否阻止
    should_block = is_dev_cmd and not is_valid

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit"
        }
    }

    # 添加額外上下文（如果有錯誤訊息）
    if error_msg:
        output["hookSpecificOutput"]["additionalContext"] = error_msg

    # 記錄檢查結果
    output["check_result"] = {
        "is_development_command": is_dev_cmd,
        "ticket_validation_passed": is_valid,
        "ticket_id": ticket_id,
        "should_block": should_block,
        "exit_code": "EXIT_BLOCK" if should_block else "EXIT_SUCCESS",
        "timestamp": datetime.now().isoformat()
    }

    return output


def save_check_log(
    prompt: str,
    is_dev_cmd: bool,
    is_valid: bool,
    ticket_id: Optional[str]
) -> None:
    """
    儲存檢查日誌

    Args:
        prompt: 用戶提示文本
        is_dev_cmd: 是否為開發命令
        is_valid: Ticket 驗證是否通過
        ticket_id: Ticket ID
    """
    import os

    project_dir = Path(os.getenv("CLAUDE_PROJECT_DIR", Path.cwd()))
    log_dir = project_dir / ".claude" / "hook-logs" / "command-entrance-gate"
    log_dir.mkdir(parents=True, exist_ok=True)

    report_file = log_dir / f"checks-{datetime.now().strftime('%Y%m%d')}.log"

    try:
        should_block = is_dev_cmd and not is_valid
        status = "BLOCKED" if should_block else "ALLOWED"

        log_entry = f"""[{datetime.now().isoformat()}]
  Prompt: {prompt[:100]}...
  IsDevelopmentCommand: {is_dev_cmd}
  TicketValidationPassed: {is_valid}
  TicketID: {ticket_id}
  Status: {status}

"""
        with open(report_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logging.debug(f"檢查日誌已儲存: {report_file}")
    except Exception as e:
        logging.warning(f"儲存檢查日誌失敗: {e}")


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
    4. 識別是否為開發命令
    5. 如果是開發命令，驗證 Ticket 狀態和決策樹欄位
    6. 生成 Hook 輸出
    7. 儲存日誌
    8. 決定 exit code（阻塞式）

    Returns:
        int - Exit code (EXIT_SUCCESS, EXIT_BLOCK, 或 EXIT_ERROR)
    """
    try:
        # 步驟 1: 初始化日誌
        setup_logging()
        logging.info("Command Entrance Gate Hook 啟動（阻塞式）")

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin()

        # 步驟 3: 驗證輸入格式
        if not validate_input(input_data):
            logging.error("輸入格式錯誤")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        prompt = input_data.get("prompt", "")

        # 步驟 4: 識別開發命令
        is_dev_cmd = is_development_command(prompt)
        logging.info(f"開發命令識別: {is_dev_cmd}")

        # 步驟 5: 驗證 Ticket 狀態（包含決策樹欄位驗證）
        is_valid = True
        error_msg = None
        ticket_id = None

        if is_dev_cmd:
            is_valid, error_msg, ticket_id = check_ticket_status()
            logging.info(f"Ticket 驗證結果: is_valid={is_valid}, ticket_id={ticket_id}")

        # 步驟 6: 生成 Hook 輸出
        hook_output = generate_hook_output(
            prompt, is_dev_cmd, is_valid, error_msg, ticket_id
        )
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 7: 儲存日誌
        save_check_log(prompt, is_dev_cmd, is_valid, ticket_id)

        # 步驟 8: 決定 exit code（阻塞式）
        if is_dev_cmd and not is_valid:
            logging.warning("Command Entrance Gate Hook：開發命令驗證失敗，阻止執行")
            return EXIT_BLOCK

        logging.info("Command Entrance Gate Hook 檢查完成：允許執行")
        return EXIT_SUCCESS

    except Exception as e:
        logging.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        error_output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "Hook 執行錯誤，詳見日誌: .claude/hook-logs/command-entrance-gate/"
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
