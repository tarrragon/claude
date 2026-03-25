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
STATUS_SUPERSEDED: str = "superseded"
STATUS_CLOSED: str = "closed"

TICKET_STATUS: Dict[str, str] = {
    "PENDING": STATUS_PENDING,
    "IN_PROGRESS": STATUS_IN_PROGRESS,
    "COMPLETED": STATUS_COMPLETED,
    "BLOCKED": STATUS_BLOCKED,
    "SUPERSEDED": STATUS_SUPERSEDED,
    "CLOSED": STATUS_CLOSED,
}

# 狀態的中文描述
STATUS_LABELS: Dict[str, str] = {
    STATUS_PENDING: "待處理",
    STATUS_IN_PROGRESS: "進行中",
    STATUS_COMPLETED: "已完成",
    STATUS_BLOCKED: "被阻塞",
    STATUS_SUPERSEDED: "已取代",
    STATUS_CLOSED: "已關閉",
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
    # TDD Phase 標準後綴（Phase 1-3）
    "-phase1-design",
    "-phase2-test-design",
    "-phase3a-strategy",
    "-phase3b-execution-report",
    # Phase 4 重構相關後綴
    "-phase4-evaluation",
    "-refactor",
    "-refactoring-report",
    # Phase 3b 測試報告
    "-phase3b-test-report",
    "-phase3b-execution-log",
    # 分析和測試相關後綴
    "-analysis",
    "-test-cases",
    "-test-cases-quick-reference",
    "-test-case-design",
    "-test-design",
    # 設計和規格相關後綴
    "-feature-spec",
    "-feature-design",
    "-phase1-feature-spec",
    # Use Case 和評估後綴
    "-uc-analysis",
    "-evaluation-report",
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
# Ticket 建立預設值
# ============================================================

DEFAULT_PRIORITY: str = "P2"
DEFAULT_HOW_TASK_TYPE: str = "Implementation"
DEFAULT_UNDEFINED_VALUE: str = "待定義"

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

# TDD Phase 顯示名稱映射（包含代理人名稱）
#
# ⚠️ 同步契約：此映射與 ticket_system/lib/tdd_sequence.py 中的 PHASE_LABELS 有同步關係
#   - PHASE_LABELS 的鍵集必須是 TDD_PHASE_DISPLAY 的子集
#   - 當修改此映射時，必須檢查 PHASE_LABELS 是否需要同步：
#     1. 若新增/刪除 phase1-phase4 的條目，必須同時更新 PHASE_LABELS
#     2. 若新增 phase0/phase4a/phase4b/phase4c，可不更新 PHASE_LABELS（非核心 TDD 序列）
#   - 修改 phase1-phase4 的顯示文字時，PHASE_LABELS 中的對應值可保持簡潔
#   - 詳見 .claude/rules/core/decision-tree.md（第五層 TDD 階段判斷）和 tdd_sequence.py
#
TDD_PHASE_DISPLAY: Dict[str, str] = {
    "phase0": "Phase 0 SA 前置審查",
    "phase1": "Phase 1 - 功能設計 (lavender)",
    "phase2": "Phase 2 - 測試設計 (sage)",
    "phase3a": "Phase 3a - 策略規劃 (pepper)",
    "phase3b": "Phase 3b - 實作執行 (parsley)",
    "phase4": "Phase 4 - 重構優化 (cinnamon)",
    "phase4a": "Phase 4a 多視角分析",
    "phase4b": "Phase 4b 重構執行",
    "phase4c": "Phase 4c 多視角再審核",
}

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

# ============================================================
# 驗收條件含糊詞彙清單
# ============================================================

# 驗收條件中的模糊詞彙（需要配合量化指標）
VAGUE_ACCEPTANCE_WORDS: List[str] = [
    "完成", "通過", "合理", "適當", "正常", "足夠",
    "良好", "改善", "優化", "確保", "驗證",
    "妥善", "恰當", "滿足", "實現", "達成",
]

# ============================================================
# 認知負擔評估閾值
# ============================================================

# 修改檔案數閾值（超過此數則警告）
COGNITIVE_LOAD_FILE_THRESHOLD: int = 5

# ============================================================
# SRP（單一職責原則）偵測常數
# ============================================================

# what 欄位多目標偵測：並列連接詞清單
# 偵測到這些連接詞時，疑似 Ticket 包含多個獨立目標
SRP_WHAT_CONJUNCTIONS: List[str] = [
    "和",
    "與",
    "及",
    "並",
    "同時",
]

# 驗收條件跨模組偵測：不同模組數量閾值
# 超過此閾值時，疑似驗收條件指向不相關模組
SRP_ACCEPTANCE_MODULE_THRESHOLD: int = 2

# ============================================================
# 重複偵測常數
# ============================================================

# Jaccard 相似度閾值：用於判斷兩個 Ticket 標題/描述是否相似
# 0.3 表示 30% 的詞彙重疊即視為相似，觸發警告提示
# Phase 4 可根據實際誤報率調整此值
DUPLICATE_DETECTION_THRESHOLD: float = 0.3

# 重複偵測時間窗口（天數）：只掃描 N 天內完成的 completed Ticket
# 防止大量歷史 Ticket 造成效能衰減和警告泛濫
DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS: int = 7


# ============================================================
# Protocol Version 常數（v0.1.2 新增）
# ============================================================

# 當前協議版本（新 ticket 使用）
PROTOCOL_VERSION_CURRENT: str = "2.0"

# 舊 ticket 推斷版本（無 protocol_version 欄位時的預設值）
PROTOCOL_VERSION_DEFAULT: str = "1.0"

# 支援的協議版本清單
PROTOCOL_VERSIONS_SUPPORTED: List[str] = ["1.0", "2.0"]

# 協議版本格式：Major.Minor（例如 "2.0", "1.0"）
# 格式說明：
#   - Major：非負整數，代表主版本號（破壞性改變時遞增）
#   - Minor：非負整數，代表次版本號（向後相容新增時遞增）
#   - 分隔符：英文句號 "."
PROTOCOL_VERSION_PATTERN: str = r"^\d+\.\d+$"

# 預編譯協議版本正則表達式，避免重複編譯
PROTOCOL_VERSION_RE = re.compile(PROTOCOL_VERSION_PATTERN)

# 協議版本遷移鏈（支援未來擴展）
# 定義版本之間的遷移規則和相容性
PROTOCOL_VERSION_MIGRATIONS: Dict[str, Dict] = {
    "1.0": {
        "target": "2.0",
        "handler": "migrate_v1_to_v2",
        "breaking_changes": False,  # v1→v2 向後相容
    },
    # 未來可擴展：
    # "2.0": {
    #     "target": "3.0",
    #     "handler": "migrate_v2_to_v3",
    #     "breaking_changes": True,
    # }
}


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
