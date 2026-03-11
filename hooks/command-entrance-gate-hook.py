#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Command Entrance Gate Hook - 阻塞式驗證

在接收開發/測試/調整命令時進行嚴格驗證，阻止無效的操作。

功能：
- 識別開發/測試/調整命令（行為分離原則）
- 驗證 Ticket 是否存在且已認領
- 驗證 Ticket 是否包含決策樹欄位
- 優先掃描當前活躍版本（來自 todolist.yaml 的 current_version）
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
    echo '{"prompt":"執行測試"}' | python3 command-entrance-gate-hook.py
    echo '{"prompt":"修復測試失敗"}' | python3 command-entrance-gate-hook.py

環境變數:
    HOOK_DEBUG: 啟用詳細日誌（true/false）

命令類型識別（v3.3.0 更新）：
- 開發類 (IMP): 實作、建立、新增、重構、設計、規劃
- 測試類 (TST): 測試、驗證、檢查、執行測試、run test
- 調整類 (ADJ): 調整、修正、修復、fix、優化
- 探索類 (不阻攔): 分析、調查、研究、探索、評估（管理白名單）

驗證規則：
1. 只對「開發/測試/調整命令」進行驗證（包含 DEVELOPMENT_KEYWORDS）
   分析/探索類命令不阻攔（與決策樹第二層一致）
2. 如果是開發命令，必須存在 pending 或 in_progress 的 Ticket
3. 如果 Ticket 狀態為 pending，必須先認領（claim）
4. 如果 Ticket 已認領，必須包含決策樹欄位（decision_tree_path 或 ## 決策樹）
5. 所有驗證通過才允許執行

版本過濾（v3.4.0 更新）：
- 優先掃描當前活躍版本的 Ticket（來自 docs/todolist.yaml 的 current_version 欄位）
- 若 current_version 讀取失敗或目錄不存在，fallback 到掃描所有版本目錄

HOOK_METADATA (JSON):
{
  "event_type": "UserPromptSubmit",
  "timeout": 5000,
  "description": "命令入口閘門 - 驗證開發命令的 Ticket 前置條件",
  "dependencies": [],
  "version": "3.4.0"
}
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    validate_ticket_has_decision_tree,
    find_ticket_files,
    get_current_version_from_todolist,
    save_check_log,
    validate_hook_input,
)
from lib.hook_messages import GateMessages, CoreMessages, format_message

# ============================================================================
# 常數定義
# ============================================================================

# 開發類命令關鍵字（IMP 類型）
IMPLEMENT_KEYWORDS = [
    "實作", "建立", "新增", "重構",
    "轉換", "設計", "規劃", "實現"
]

# 測試類命令關鍵字（TST 類型）- 新增
TEST_KEYWORDS = [
    "測試", "驗證", "檢查", "執行測試",
    "run test", "test", "verify"
]

# 調整類命令關鍵字（ADJ 類型）- 新增
ADJUSTMENT_KEYWORDS = [
    "調整", "修正", "修復", "fix",
    "處理", "修改", "優化", "改進", "升級"
]

# 分析類命令關鍵字（ANA/RES/INV 類型）
ANALYSIS_KEYWORDS = [
    "分析", "調查", "研究", "追蹤"
]

# 刪除類命令關鍵字
DELETE_KEYWORDS = [
    "刪除", "移除", "remove", "delete"
]

# 合併所有開發命令關鍵字（需要 Ticket 驗證）
# 注意：ANALYSIS_KEYWORDS 不納入，分析/探索是建立 Ticket 的前置行為
# 與決策樹第二層一致：分析類走「問題處理流程」，非「命令處理流程」
DEVELOPMENT_KEYWORDS = (
    IMPLEMENT_KEYWORDS +
    TEST_KEYWORDS +
    ADJUSTMENT_KEYWORDS +
    DELETE_KEYWORDS
)

# ============================================================================
# is_management_operation 函式的白名單常數
# ============================================================================

# 短回答白名單（確認、同意等，長度 <= 15 字元）
SHORT_ANSWER_PATTERNS = frozenset([
    # 肯定
    "是", "好", "確認", "同意", "ok", "yes", "y",
    "對", "沒錯", "没错",
    # 否定
    "否", "不", "取消", "cancel", "no", "n",
    "不要", "不用",
    # 理解確認
    "了解", "知道了", "收到", "明白", "got it",
    # 數字選擇（0-20）
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
])

# 短回答正則模式（長度 <= 15 的特殊格式，需完整匹配整個字串）
SHORT_ANSWER_REGEX_PATTERNS = [
    r"^\d{1,2}(,\s*\d{1,2})*$",  # 組合多選：如 "2, 4" 或 "1,3,5"
    r"^phase\s+\d+[a-z]?$",        # Phase 選項標籤：如 "Phase 4a"、"phase 3b"
    r"^[a-z]$",                     # 單字母選項：如 "a"、"b"
]

# Ticket 管理相關模式
TICKET_PATTERNS = [
    "ticket", "/ticket",
    "建立 ticket", "新增 ticket", "建 ticket",
    "認領", "claim",
]

# Hook / 系統管理相關模式
MANAGEMENT_PATTERNS = [
    "hook", "暫停", "停用", "啟用",
    "設定", "配置", "config",
    "/commit", "/version-release",
    "/pre-fix-eval", "/tech-debt",
    "/manager",
    "commit",  # 不帶 / 的 commit 指令
    "plan",    # Plan Mode 相關操作
    "記錄",    # 記錄狀況、記錄筆記（非開發行為）
    # 提交和 Git 操作
    "提交",    # 中文 commit（git 提交）
    "git",     # Git 操作前綴（push, pull, status 等）
    "push",    # git push
    # 查詢和摘要操作
    "查詢",    # 查詢操作（非開發）
    "摘要",    # 摘要操作（非開發）
    "summary", # 英文摘要
    "列出",    # 列出操作
    "查看",    # 查看操作
    "顯示",    # 顯示操作
]

# PM 調度/派發相關模式
DISPATCH_PATTERNS = [
    "派發", "並行", "繼續", "序列",
    "開始處理", "恢復", "接手",
    "開始",    # 「W25-006 開始」等 Ticket 生命週期指令
    "完成",    # 「W25-006 完成」等 Ticket 生命週期指令
    # 工作流延續
    "接著",    # 「接著處理下一個」工作流延續
    "然後",    # 「然後測試」工作流延續
    "下一步",  # 工作流延續
    "next",    # 英文工作流延續
]

# 探索 / 分析模式（前置行為，非開發命令）
# 與決策樹第二層一致：分析類走「問題處理流程」
EXPLORATION_PATTERNS = [
    "分析",    # 分析程式碼/架構/結構
    "研究",    # 研究文章/方案
    "調查",    # 調查問題原因
    "探索",    # 探索程式碼庫
    "評估",    # 評估方案/風險
    "追蹤",    # 追蹤問題/進度
    "閱讀",    # 閱讀文章/文件
    "瀏覽",    # 瀏覽程式碼
    "了解",    # 了解架構/現況
    "比較",    # 比較方案
    "review",  # Code review / 文件 review
    "analyze", # 英文分析
    "explore", # 英文探索
    "investigate", # 英文調查
]

# 問題 / 討論模式（非指令性）
DISCUSSION_PATTERNS = [
    "為什麼", "怎麼", "如何", "是什麼",
    "可以嗎", "應該", "建議", "說明",
    "幫我", "請問", "?", "？",
    # 追問和選擇
    "什麼",    # 「這是什麼」等問句
    "哪個",    # 「哪個方案」等問句
    "多少",    # 「多少個」等問句
    # 英文禮貌和問句
    "please",  # 英文禮貌用語
    "can you", # 英文問句
    "could",   # 英文問句
    "would",   # 英文問句
    "what",    # 英文問句
    "how",     # 英文問句
    "why",     # 英文問句
]

# 管理操作白名單合併（is_management_operation 使用）
ALL_BYPASS_PATTERNS = (
    TICKET_PATTERNS + MANAGEMENT_PATTERNS + DISPATCH_PATTERNS +
    EXPLORATION_PATTERNS + DISCUSSION_PATTERNS
)

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2

# validate_input 已遷移至 hook_utils.validate_hook_input

# ============================================================================
# 開發命令識別
# ============================================================================

def is_system_internal_message(prompt: str, logger) -> bool:
    """
    判斷是否為系統內部訊息（非用戶手動輸入）

    Claude Code 會透過 UserPromptSubmit 事件傳送內部訊息，
    例如 Task agent 完成通知、系統提醒等。這些訊息不應被視為
    開發命令，需要跳過驗證。

    Args:
        prompt: 提示文本
        logger: 日誌物件

    Returns:
        bool - 是否為系統內部訊息
    """
    if not prompt:
        return False

    # 去除前後空白
    stripped = prompt.strip()

    # 檢查常見的系統內部訊息標記
    system_markers = [
        "<task-notification>",
        "<system-reminder>",
        "<tool-result>",
        "<task-id>",
    ]

    for marker in system_markers:
        if marker in stripped:
            logger.debug(f"偵測到系統內部訊息標記: {marker}")
            return True

    return False

def is_management_operation(prompt: str, logger) -> bool:
    """
    判斷是否為管理操作（永遠不阻攔）

    管理操作包括 Ticket 管理、Hook 管理、討論、提問等。
    這些操作即使包含開發關鍵字（如「新增 ticket」中的「新增」），
    也不應該被視為開發命令而阻攔。

    判斷邏輯：白名單優先於開發關鍵字匹配。

    Args:
        prompt: 用戶提示文本
        logger: 日誌物件

    Returns:
        bool - 是否為管理操作
    """
    if not prompt:
        return False

    prompt_lower = prompt.lower()
    prompt_stripped = prompt.strip()

    # Slash 命令白名單（所有 /xxx 都是 SKILL 呼叫，非開發命令）
    # 必須最先檢查，避免含開發關鍵字的 SKILL（如 /test-progress）被誤攔
    if prompt_stripped.startswith("/"):
        logger.info(f"識別為 SKILL 指令（/ 前綴）: {prompt_stripped[:30]}")
        return True

    # 檢查短回答：長度 <= 15 且完全匹配白名單或正則模式
    if len(prompt_stripped) <= 15:
        if prompt_stripped.lower() in SHORT_ANSWER_PATTERNS:
            logger.info(f"識別為短回答（白名單）: {prompt}")
            return True
        for pattern in SHORT_ANSWER_REGEX_PATTERNS:
            if re.match(pattern, prompt_stripped.lower()):
                logger.info(f"識別為短回答（正則模式 {pattern}）: {prompt}")
                return True

    # 檢查管理操作白名單
    for pattern in ALL_BYPASS_PATTERNS:
        if pattern in prompt_lower:
            logger.info(f"識別為管理/討論操作（白名單）: {pattern}")
            return True

    return False

def is_development_command(prompt: str, logger) -> bool:
    """
    判斷是否為開發/測試/調整命令

    根據行為分離原則，識別以下類型的命令：
    - 開發類 (IMP): 實作、建立、新增、重構
    - 測試類 (TST): 測試、驗證、檢查、執行測試
    - 調整類 (ADJ): 調整、修正、修復、fix
    - 分析類 (ANA/RES/INV): 分析、調查、研究

    注意：此函式應在 is_management_operation() 之後呼叫，
    管理操作已在前一步被排除。

    Args:
        prompt: 用戶提示文本
        logger: 日誌物件

    Returns:
        bool - 是否為需要 Ticket 驗證的命令
    """
    if not prompt:
        return False

    # 轉換為小寫以進行不區分大小寫的匹配
    prompt_lower = prompt.lower()

    # 檢查是否包含開發命令關鍵字
    for keyword in DEVELOPMENT_KEYWORDS:
        if keyword.lower() in prompt_lower:
            logger.info(f"識別開發命令關鍵字: {keyword}")
            return True

    logger.debug(f"未識別為開發命令: {prompt[:50]}...")
    return False

# ============================================================================
# Ticket 檢查
# ============================================================================

def extract_ticket_status(file_path: Path, logger) -> Tuple[Optional[str], Optional[str], str]:
    """
    從 Ticket 檔案提取 ID、狀態和完整內容

    Args:
        file_path: Ticket 檔案路徑
        logger: 日誌物件

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
        logger.debug(f"無法提取 Ticket 狀態 {file_path}: {e}")
        return None, None, ""

def split_kebab_case(word: str) -> List[str]:
    """
    將 kebab-case 詞彙拆分為多個單詞

    例：
    - "command-entrance-gate-hook" → ["command", "entrance", "gate", "hook"]
    - "hello-world" → ["hello", "world"]
    - "simple" → ["simple"]

    Args:
        word: 輸入詞彙

    Returns:
        list - 拆分後的詞彙清單
    """
    # 按 hyphen 拆分
    parts = word.split("-")
    # 過濾掉空字串
    return [p for p in parts if p]

def tokenize_text(text: str) -> List[str]:
    """
    將文本分詞，支援 kebab-case 拆分

    執行步驟：
    1. 轉換為小寫
    2. 按空格分詞
    3. 對每個詞，如果包含 hyphen 則進行 kebab-case 拆分

    例：
    - "修復 command-entrance-gate-hook 問題" →
      ["修復", "command", "entrance", "gate", "hook", "問題"]

    Args:
        text: 輸入文本

    Returns:
        list - 分詞結果（不含噪音詞）
    """
    if not text:
        return []

    # 轉換為小寫並按空格分詞
    words = text.lower().split()

    # 對每個詞進行處理
    result = []
    noise_words = {"是", "的", "和", "或", "在", "了", "，", "。", "？", "！"}

    for word in words:
        # 如果包含 hyphen，進行 kebab-case 拆分
        if "-" in word:
            parts = split_kebab_case(word)
            for part in parts:
                if len(part) > 1 and part not in noise_words:
                    result.append(part)
        else:
            # 一般詞彙：過濾掉長度 <= 1 和噪音詞
            if len(word) > 1 and word not in noise_words:
                result.append(word)

    return result

def check_word_relevance(prompt_words: List[str], title_words: List[str], logger) -> bool:
    """
    檢查 prompt 詞彙與 title 詞彙的關聯性

    使用兩種匹配方式：
    1. 完全匹配：prompt 詞在 title 詞中（集合交集）
    2. 子字串匹配：prompt 詞是 title 詞的子字串

    例：
    - prompt: ["修復", "hook"] vs title: ["command", "entrance", "gate", "hook"]
      結果: True（"hook" 完全匹配）

    - prompt: ["hook", "系統"] vs title: ["command", "entrance", "gate", "hook"]
      結果: True（"hook" 完全匹配）

    Args:
        prompt_words: prompt 分詞結果
        title_words: title 分詞結果
        logger: 日誌物件

    Returns:
        bool - 是否相關
    """
    # 方式 1：完全匹配（集合交集）
    if set(prompt_words) & set(title_words):
        logger.debug(f"檢測到完全匹配關鍵字: {set(prompt_words) & set(title_words)}")
        return True

    # 方式 2：子字串匹配
    # 檢查 prompt 中的詞是否是 title 中某個詞的子字串
    for p_word in prompt_words:
        for t_word in title_words:
            # 檢查 p_word 是否是 t_word 的子字串（且長度相差不大）
            if p_word in t_word and len(p_word) >= 2:
                logger.debug(f"檢測到子字串匹配: '{p_word}' in '{t_word}'")
                return True

    return False

def check_ticket_relevance(prompt: str, ticket_id: str, ticket_content: str, logger) -> Tuple[bool, str]:
    """
    檢查 Ticket 與 prompt 的關聯性（soft check）

    此檢查是警告性質，不會阻止執行。如果 Ticket 與命令無關聯，
    將輸出警告訊息提醒用戶，但允許繼續執行。

    改進演算法（v2.0）：
    1. 支援 kebab-case 拆分（如 "command-entrance-gate-hook" → 拆分為四個詞）
    2. 支援子字串匹配（如 "hook" 匹配 "command-entrance-gate-hook"）

    Args:
        prompt: 用戶輸入的提示文本
        ticket_id: Ticket ID
        ticket_content: Ticket 檔案內容
        logger: 日誌物件

    Returns:
        tuple - (is_relevant, warning_message)
            - is_relevant: Ticket 是否與 prompt 相關
            - warning_message: 如果無關聯，返回警告訊息；否則為空字串
    """
    if not ticket_content:
        logger.debug("Ticket 內容為空，跳過關聯性檢查")
        return True, ""

    # 從 ticket_content 提取 title（從 YAML frontmatter 或 Markdown 標題）
    title = ""

    # 嘗試從 YAML frontmatter 提取 title
    title_match = re.search(r"title:\s*['\"]?(.+?)['\"]?\s*$", ticket_content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        logger.debug(f"從 YAML 提取 title: {title}")
    else:
        # 嘗試從 Markdown 標題提取
        heading_match = re.search(r"^#\s+.*?:\s*(.+)$", ticket_content, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip()
            logger.debug(f"從 Markdown 提取 title: {title}")

    if not title:
        logger.debug("無法提取 Ticket title，跳過關聯性檢查")
        return True, ""

    # 使用改進的分詞函式：支援 kebab-case 拆分
    prompt_words = tokenize_text(prompt)
    title_words = tokenize_text(title)

    logger.debug(f"Prompt 分詞: {prompt_words}")
    logger.debug(f"Title 分詞: {title_words}")

    # 檢查關聯性（支援完全匹配和子字串匹配）
    is_relevant = check_word_relevance(prompt_words, title_words, logger)

    if is_relevant:
        logger.debug("Ticket 與 prompt 相關")
        return True, ""

    # 如果無關聯，返回警告（但不阻止）
    warning = format_message(GateMessages.TICKET_RELEVANCE_WARNING, ticket_id=ticket_id, title=title)
    logger.warning(f"Ticket {ticket_id} 與 prompt 無關聯")
    return False, warning

def get_latest_pending_ticket(logger) -> Optional[Tuple[str, str, str]]:
    """
    取得最新的待處理 Ticket

    Args:
        logger: 日誌物件

    Returns:
        tuple - (ticket_id, status, content) 或 None
    """
    project_root = get_project_root()
    tickets = find_ticket_files(project_root, logger=logger)

    # 按修改時間排序（最新優先）
    sorted_tickets = sorted(tickets, key=lambda p: p.stat().st_mtime, reverse=True)

    for ticket_file in sorted_tickets:
        ticket_id, status, content = extract_ticket_status(ticket_file, logger)
        if ticket_id and status in ["pending", "in_progress"]:
            logger.info(f"找到待處理 Ticket: {ticket_id} (status={status})")
            return ticket_id, status, content

    logger.debug("未找到待處理 Ticket")
    return None

def check_ticket_status(prompt: Optional[str] = None, logger=None) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    檢查 Ticket 狀態（阻塞式）

    此函式執行三層驗證：
    1. Ticket 是否存在且已認領（阻塞式）
    2. Ticket 是否包含必要的決策樹欄位（阻塞式）
    3. Ticket 與 prompt 是否相關（soft warning，不阻塊）

    Args:
        prompt: 用戶的命令提示文本（可選，用於關聯性檢查）
        logger: 日誌物件

    Returns:
        tuple - (is_valid, error_message, ticket_id, relevance_warning)
            - is_valid: Ticket 是否有效（存在、已認領、包含決策樹）
            - error_message: 如果無效，説明問題和建議操作；如果有效，為 None
            - ticket_id: Ticket ID（如果找到）
            - relevance_warning: 關聯性檢查警告訊息（soft check，不阻塊執行）
    """
    ticket_info = get_latest_pending_ticket(logger)

    # 驗證 1：Ticket 是否存在且已認領
    if ticket_info is None:
        msg = GateMessages.TICKET_NOT_FOUND_ERROR

        logger.warning("未找到待處理 Ticket - 阻止執行")
        return False, msg, None, None

    ticket_id, status, content = ticket_info

    if status == "pending":
        msg = format_message(GateMessages.TICKET_NOT_CLAIMED_ERROR, ticket_id=ticket_id)

        logger.warning(f"Ticket {ticket_id} 未被認領 - 阻止執行")
        return False, msg, ticket_id, None

    # 驗證 2：Ticket 是否包含決策樹欄位
    if status == "in_progress":
        if not validate_ticket_has_decision_tree(content, logger):
            msg = format_message(GateMessages.DECISION_TREE_MISSING_ERROR, ticket_id=ticket_id)

            logger.warning(f"Ticket {ticket_id} 缺少決策樹欄位 - 阻止執行")
            return False, msg, ticket_id, None

        # 驗證 3：Ticket 與 prompt 的關聯性（soft check，不阻塊）
        relevance_warning = None
        if prompt:
            is_relevant, warning = check_ticket_relevance(prompt, ticket_id, content, logger)
            if not is_relevant:
                relevance_warning = warning
                logger.warning(f"Ticket {ticket_id} 與 prompt 無關聯，但允許繼續")

        # 所有驗證通過
        logger.info(f"Ticket {ticket_id} 驗證通過，允許繼續")
        return True, None, ticket_id, relevance_warning

    # 未知狀態
    msg = format_message(GateMessages.TICKET_STATUS_UNKNOWN_ERROR, ticket_id=ticket_id, status=status)

    logger.warning(f"Ticket {ticket_id} 狀態不明 ({status}) - 阻止執行")
    return False, msg, ticket_id, None

# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    prompt: str,
    is_dev_cmd: bool,
    is_valid: bool,
    error_msg: Optional[str],
    ticket_id: Optional[str],
    relevance_warning: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        prompt: 用戶提示文本
        is_dev_cmd: 是否為開發命令
        is_valid: Ticket 驗證是否通過
        error_msg: 如果驗證失敗，提供的錯誤訊息
        ticket_id: Ticket ID
        relevance_warning: 關聯性檢查警告（soft check，不阻塊）

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

    # 添加額外上下文
    context_parts = []
    if error_msg:
        context_parts.append(error_msg)
    if relevance_warning:
        context_parts.append(relevance_warning)

    if context_parts:
        output["hookSpecificOutput"]["additionalContext"] = "\n".join(context_parts)

    # 記錄檢查結果
    output["check_result"] = {
        "is_development_command": is_dev_cmd,
        "ticket_validation_passed": is_valid,
        "ticket_id": ticket_id,
        "should_block": should_block,
        "has_relevance_warning": relevance_warning is not None,
        "exit_code": "EXIT_BLOCK" if should_block else "EXIT_SUCCESS",
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
    4. 識別是否為開發命令
    5. 如果是開發命令，驗證 Ticket 狀態和決策樹欄位
    6. 生成 Hook 輸出
    7. 儲存日誌
    8. 決定 exit code（阻塞式）

    Returns:
        int - Exit code (EXIT_SUCCESS, EXIT_BLOCK, 或 EXIT_ERROR)
    """
    logger = setup_hook_logging("command-entrance-gate")
    try:
        # 步驟 1: 初始化日誌
        logger.info(GateMessages.COMMAND_GATE_START)

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)

        # 步驟 3: 驗證輸入格式
        if not validate_hook_input(input_data, logger, ("prompt",)):
            logger.error("輸入格式錯誤")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        prompt = input_data.get("prompt", "")

        # 步驟 3.5: 跳過系統內部訊息
        if is_system_internal_message(prompt, logger):
            logger.info("偵測到系統內部訊息，跳過驗證")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        # 步驟 3.6: 管理操作白名單檢查（永遠不阻攔）
        if is_management_operation(prompt, logger):
            logger.info("識別為管理/討論操作，跳過開發命令驗證")
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        # 步驟 4: 識別開發命令
        is_dev_cmd = is_development_command(prompt, logger)
        logger.info(f"開發命令識別: {is_dev_cmd}")

        # 步驟 5: 驗證 Ticket 狀態（包含決策樹欄位驗證和關聯性檢查）
        is_valid = True
        error_msg = None
        ticket_id = None
        relevance_warning = None

        if is_dev_cmd:
            is_valid, error_msg, ticket_id, relevance_warning = check_ticket_status(prompt, logger)
            logger.info(f"Ticket 驗證結果: is_valid={is_valid}, ticket_id={ticket_id}, has_warning={relevance_warning is not None}")

        # 步驟 6: 生成 Hook 輸出
        hook_output = generate_hook_output(
            prompt, is_dev_cmd, is_valid, error_msg, ticket_id, relevance_warning
        )
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 7: 儲存日誌
        should_block = is_dev_cmd and not is_valid
        status = "BLOCKED" if should_block else "ALLOWED"
        warning_status = "WITH_WARNING" if relevance_warning is not None else "OK"
        log_entry = f"""[{datetime.now().isoformat()}]
  Prompt: {prompt[:100]}...
  IsDevelopmentCommand: {is_dev_cmd}
  TicketValidationPassed: {is_valid}
  TicketID: {ticket_id}
  RelevanceWarning: {warning_status}
  Status: {status}

"""
        save_check_log("command-entrance-gate", log_entry, logger)

        # 步驟 8: 決定 exit code（阻塞式）
        if is_dev_cmd and not is_valid:
            logger.warning(GateMessages.COMMAND_GATE_BLOCKED)
            # 將錯誤訊息寫到 stderr，讓 Claude Code 能正確顯示阻擋原因
            if error_msg:
                print(error_msg, file=sys.stderr)
            return EXIT_BLOCK

        logger.info(GateMessages.COMMAND_GATE_COMPLETE)
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
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
    sys.exit(run_hook_safely(main, "command-entrance-gate"))
