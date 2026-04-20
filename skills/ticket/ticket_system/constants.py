"""
Ticket System 常數定義（Canonical Location）

定義系統中使用的常數，包含狀態、ID 格式、路徑等。

設計背景（W14-016）：
    本模組原位於 ticket_system/lib/constants.py，因 lib/__init__.py 會 eager-import
    ticket_loader → parser → yaml，導致 hook 在系統 Python（無 yaml）環境下觸發
    ModuleNotFoundError。將 constants 上移至 package 頂層後，hook 可用
    `from ticket_system.constants import X` 直接 import，不觸發 lib/__init__
    eager-import 鏈。

    Skill 內部既有 `from ticket_system.lib.constants import X` 路徑透過
    lib/constants.py 的 shim 繼續可用，避免大量使用處同步修改。
"""
# 防止直接執行此模組
import re
from typing import Dict, List

# ============================================================
# __all__：明確宣告 public API（供 lib/constants.py shim 使用 `from ... import *`）
# ============================================================

__all__ = [
    # 狀態常數
    "STATUS_PENDING",
    "STATUS_IN_PROGRESS",
    "STATUS_COMPLETED",
    "STATUS_BLOCKED",
    "STATUS_SUPERSEDED",
    "STATUS_CLOSED",
    "TICKET_STATUS",
    "STATUS_LABELS",
    "TERMINAL_STATUSES",
    # Close reason 枚舉（PC-090 / W15-024 C1）
    "CLOSE_REASONS",
    "CLOSE_REASON_RETROSPECTIVE_UNKNOWN",
    # Ticket ID
    "TICKET_ID_PATTERN",
    "TICKET_ID_RE",
    "KNOWN_TICKET_SUFFIXES",
    # 路徑
    "WORK_LOGS_DIR",
    "TICKETS_DIR",
    "TICKET_PATHS",
    "HANDOFF_DIR",
    "HANDOFF_PENDING_SUBDIR",
    "HANDOFF_ARCHIVE_SUBDIR",
    # Ticket 類型 & 優先級
    "TICKET_TYPES",
    "PRIORITY_LEVELS",
    # 預設值
    "DEFAULT_PRIORITY",
    "DEFAULT_HOW_TASK_TYPE",
    "DEFAULT_UNDEFINED_VALUE",
    # Handoff direction
    "TASK_CHAIN_DIRECTION_TYPES",
    "NON_CHAIN_DIRECTION_TYPES",
    # TDD
    "TDD_PHASES",
    "TDD_PHASE_DISPLAY",
    # 必填欄位
    "REQUIRED_FIELDS",
    "HANDOFF_REQUIRED_FIELDS",
    # 驗收
    "VAGUE_ACCEPTANCE_WORDS",
    # 認知負擔
    "COGNITIVE_LOAD_FILE_THRESHOLD",
    # SRP
    "SRP_WHAT_CONJUNCTIONS",
    "SRP_ACCEPTANCE_MODULE_THRESHOLD",
    # 重複偵測
    "DUPLICATE_DETECTION_THRESHOLD",
    "DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS",
    # Protocol version
    "PROTOCOL_VERSION_CURRENT",
    "PROTOCOL_VERSION_DEFAULT",
    "PROTOCOL_VERSIONS_SUPPORTED",
    "PROTOCOL_VERSION_PATTERN",
    "PROTOCOL_VERSION_RE",
    "PROTOCOL_VERSION_MIGRATIONS",
]

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

STATUS_LABELS: Dict[str, str] = {
    STATUS_PENDING: "待處理",
    STATUS_IN_PROGRESS: "進行中",
    STATUS_COMPLETED: "已完成",
    STATUS_BLOCKED: "被阻塞",
    STATUS_SUPERSEDED: "已取代",
    STATUS_CLOSED: "已關閉",
}

# Terminal（終止）狀態集合：視為任務已結案的狀態
#
# 單一真實來源（W14-004 整併 + W14-016 上移至 package 頂層）：
#   - skill: ticket_system/commands/lifecycle.py 的 spawned 檢查
#   - hook: .claude/hooks/acceptance_checkers/children_checker.py 的子任務檢查
#   兩邊都從此處 import，避免雙邊宣告與語意飄移。
# frozenset 保證不可變、支援 `in` 運算；與先前使用 set/tuple 的呼叫端完全相容。
TERMINAL_STATUSES: frozenset = frozenset({STATUS_COMPLETED, STATUS_CLOSED})

# ============================================================
# Close reason 枚舉（PC-090 / W15-024 C1）
# ============================================================
#
# ticket close 必須填寫 close_reason 且符合以下六種合法枚舉之一。
# 推延性 close（「等之後判斷」「閘門未達先 close」）屬於反模式，
# 參見 .claude/error-patterns/process-compliance/PC-090-deferred-close-anti-pattern.md
CLOSE_REASONS: frozenset = frozenset({
    "goal_achieved",                        # 目標已達成
    "requirement_vanished",                 # 需求消失（環境變更使 ticket 無意義）
    "superseded_by",                        # 被上游 ticket 取代
    "not_executable_knowledge_captured",    # 無法執行且知識已轉移 error-pattern
    "duplicate",                            # 與既有 ticket 重複
    "cancelled_by_user",                    # 用戶明示取消
})

# 回顧式 close 專用（C4）：既有 closed ticket 補填時允許，需標記 retrospective: true
CLOSE_REASON_RETROSPECTIVE_UNKNOWN: str = "unknown"

# ============================================================
# Ticket ID 正則表達式
# ============================================================

TICKET_ID_PATTERN: str = r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)(-[a-z0-9][a-z0-9-]{0,59})?$"
TICKET_ID_RE = re.compile(TICKET_ID_PATTERN)

# ============================================================
# 已知的描述性後綴模式
# ============================================================

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

WORK_LOGS_DIR: str = "docs/work-logs"
TICKETS_DIR: str = "tickets"
TICKET_PATHS: List[str] = [
    f"{WORK_LOGS_DIR}/v{{version}}/{TICKETS_DIR}/",
]
HANDOFF_DIR: str = ".claude/handoff"
HANDOFF_PENDING_SUBDIR: str = "pending"
HANDOFF_ARCHIVE_SUBDIR: str = "archive"

# ============================================================
# Ticket 類型 & 優先級
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

PRIORITY_LEVELS: List[str] = ["P0", "P1", "P2", "P3"]

# ============================================================
# 預設值
# ============================================================

DEFAULT_PRIORITY: str = "P2"
DEFAULT_HOW_TASK_TYPE: str = "Implementation"
DEFAULT_UNDEFINED_VALUE: str = "待定義"

# ============================================================
# Handoff Direction 常數
# ============================================================

TASK_CHAIN_DIRECTION_TYPES: tuple = ("to-sibling", "to-parent", "to-child")
NON_CHAIN_DIRECTION_TYPES: tuple = ("context-refresh", "next-wave")

# ============================================================
# TDD 階段
# ============================================================

TDD_PHASES: List[str] = ["phase1", "phase2", "phase3a", "phase3b", "phase4"]

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

REQUIRED_FIELDS: List[str] = [
    "id",
    "title",
    "status",
    "what",
]

HANDOFF_REQUIRED_FIELDS: List[str] = REQUIRED_FIELDS + [
    "decision_tree_path",
    "acceptance",
    "dependencies",
]

# ============================================================
# 驗收條件含糊詞彙清單
# ============================================================

VAGUE_ACCEPTANCE_WORDS: List[str] = [
    "完成", "通過", "合理", "適當", "正常", "足夠",
    "良好", "改善", "優化", "確保", "驗證",
    "妥善", "恰當", "滿足", "實現", "達成",
]

# ============================================================
# 認知負擔評估閾值
# ============================================================

COGNITIVE_LOAD_FILE_THRESHOLD: int = 5

# ============================================================
# SRP（單一職責原則）偵測常數
# ============================================================

SRP_WHAT_CONJUNCTIONS: List[str] = [
    "和",
    "與",
    "及",
    "並",
    "同時",
]

SRP_ACCEPTANCE_MODULE_THRESHOLD: int = 2

# ============================================================
# 重複偵測常數
# ============================================================

DUPLICATE_DETECTION_THRESHOLD: float = 0.3
DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS: int = 7

# ============================================================
# Protocol Version 常數
# ============================================================

PROTOCOL_VERSION_CURRENT: str = "2.0"
PROTOCOL_VERSION_DEFAULT: str = "1.0"
PROTOCOL_VERSIONS_SUPPORTED: List[str] = ["1.0", "2.0"]
PROTOCOL_VERSION_PATTERN: str = r"^\d+\.\d+$"
PROTOCOL_VERSION_RE = re.compile(PROTOCOL_VERSION_PATTERN)

PROTOCOL_VERSION_MIGRATIONS: Dict[str, Dict] = {
    "1.0": {
        "target": "2.0",
        "handler": "migrate_v1_to_v2",
        "breaking_changes": False,
    },
}


if __name__ == "__main__":
    # __main__ guard：constants 模組不應被直接執行
    # 不 import lib.messages 以避免觸發 lib/__init__.py eager-import（W14-016）
    import sys
    print("=" * 60)
    print("此模組不可直接執行：ticket_system/constants.py")
    print("=" * 60)
    print()
    print("請使用 ticket CLI 入口：")
    print("  ticket track summary")
    print("  ticket track claim <ticket_id>")
    sys.exit(1)
