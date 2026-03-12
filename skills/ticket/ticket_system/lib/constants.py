"""
Ticket System 常數定義

定義系統中使用的常數，包含狀態、ID 格式、路徑等。
"""
# 防止直接執行此模組
import re
from typing import Dict, List

# ============================================================
# 狀態常數
# ============================================================

STATUS_PENDING: str = "pending"
STATUS_IN_PROGRESS: str = "in_progress"
STATUS_COMPLETED: str = "completed"
STATUS_BLOCKED: str = "blocked"

TICKET_STATUS: Dict[str, str] = {
    "PENDING": STATUS_PENDING,
    "IN_PROGRESS": STATUS_IN_PROGRESS,
    "COMPLETED": STATUS_COMPLETED,
    "BLOCKED": STATUS_BLOCKED,
}

# 狀態的中文描述
STATUS_LABELS: Dict[str, str] = {
    STATUS_PENDING: "待處理",
    STATUS_IN_PROGRESS: "進行中",
    STATUS_COMPLETED: "已完成",
    STATUS_BLOCKED: "被阻塞",
}

# ============================================================
# Ticket ID 正則表達式
# ============================================================

# 支援無限深度子任務的正則表達式，以及描述性後綴
# 格式: {version}-W{wave}-{seq[.seq...]}[-description]
# 範例: 0.31.0-W3-001 (根任務)
#      0.31.0-W3-001.1 (第一層子任務)
#      0.31.0-W3-001.1.1 (第二層子任務)
#      0.1.0-W11-004-phase1-design (TDD Phase 文件)
#      0.1.0-W25-005-analysis (分析文件)
#
# 後綴規則：
#   - 以 "-" 開頭
#   - 只包含小寫字母、數字、連字號
#   - 不以 "-W" 開頭（避免與 wave 格式混淆）
#   - 長度 1-60 字元
#
# ⚠️ 維護重點：此正則表達式被以下模組引用，修改時須同步更新：
#   1. .claude/hooks/ticket-id-validator-hook.py (第 54 行 TICKET_ID_REGEX)
#   2. 新增後綴時：同時更新 KNOWN_TICKET_SUFFIXES 清單
#   詳見 .claude/rules/core/ticket-id-conventions.md (Ticket ID 命名規範)
TICKET_ID_PATTERN: str = r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)(-[a-z0-9][a-z0-9-]{0,59})?$"

# 預編譯正則表達式，避免重複編譯提升效能
# 使用此常數而非每次都 re.compile(TICKET_ID_PATTERN)
TICKET_ID_RE = re.compile(TICKET_ID_PATTERN)

# ============================================================
# 已知的描述性後綴模式（用於命名規範和 Hook 驗證）
# ============================================================

# 標準後綴清單，定義於 .claude/rules/core/ticket-id-conventions.md
# Hook 驗證時使用此清單區分已知 vs 未知後綴
#
# ⚠️ 維護重點：此清單被以下模組引用，修改時須同步更新：
#   1. .claude/hooks/ticket-id-validator-hook.py (第 57-66 行 KNOWN_TICKET_SUFFIXES)
#   2. 修改 TICKET_ID_PATTERN 時：同時更新此清單
#   詳見 .claude/rules/core/ticket-id-conventions.md (已知的描述性後綴模式)
KNOWN_TICKET_SUFFIXES: List[str] = [
    "-phase1-design",
    "-phase2-test-design",
    "-phase3a-strategy",
    "-phase3b-execution-report",
    "-analysis",
    "-test-cases",
    "-test-cases-quick-reference",
    "-feature-spec",
]

# ============================================================
# 路徑常數
# ============================================================

# 工作日誌目錄名稱
WORK_LOGS_DIR: str = "docs/work-logs"

# Tickets 子目錄名稱
TICKETS_DIR: str = "tickets"

# Ticket 檔案搜尋路徑列表
# 唯一允許的 Ticket 存放位置：docs/work-logs/v{version}/tickets/
# 注意：禁止使用其他路徑（如 .claude/tickets/）
TICKET_PATHS: List[str] = [
    f"{WORK_LOGS_DIR}/v{{version}}/{TICKETS_DIR}/",
]

# Handoff 交接檔案目錄
HANDOFF_DIR: str = ".claude/handoff"
HANDOFF_PENDING_SUBDIR: str = "pending"
HANDOFF_ARCHIVE_SUBDIR: str = "archive"

# ============================================================
# Ticket 類型
# ============================================================

TICKET_TYPES: Dict[str, str] = {
    "IMP": "Implementation (實作)",
    "TST": "Test (測試)",
    "ADJ": "Adjustment (調整/修復)",
    "RES": "Research (研究)",
    "ANA": "Analysis (分析)",
    "INV": "Investigation (調查)",
    "DOC": "Documentation (文件)",
}

# ============================================================
# 優先級
# ============================================================

PRIORITY_LEVELS: List[str] = ["P0", "P1", "P2", "P3"]

# ============================================================
# Handoff Direction 常數
# ============================================================

# 任務鏈 direction 類型（來源 ticket completed 時應保留）
TASK_CHAIN_DIRECTION_TYPES: tuple = ("to-sibling", "to-parent", "to-child")

# 非任務鏈 direction 類型（來源 ticket completed 時應過濾為 stale）
NON_CHAIN_DIRECTION_TYPES: tuple = ("context-refresh",)

# ============================================================
# TDD 階段
# ============================================================

TDD_PHASES: List[str] = ["phase1", "phase2", "phase3a", "phase3b", "phase4"]

# ============================================================
# 必填欄位列表
# ============================================================

# 基本 Ticket 的必填欄位
REQUIRED_FIELDS: List[str] = [
    "id",
    "title",
    "status",
    "what",
]

# 帶有決策樹的 Ticket 必填欄位（用於 handoff）
HANDOFF_REQUIRED_FIELDS: List[str] = REQUIRED_FIELDS + [
    "decision_tree_path",
    "acceptance",
    "dependencies",
]


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
