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
    # 嵌套深度上限（W1-056.5 協議 v2 D3）
    "MAX_TICKET_DEPTH",
    # 子票扇出 warning 閾值（W5-005.11 D11）
    "MAX_CHILDREN_WARNING_THRESHOLD",
    # 路徑
    "WORK_LOGS_DIR",
    "TICKETS_DIR",
    "TICKET_PATHS",
    "HANDOFF_DIR",
    "HANDOFF_PENDING_SUBDIR",
    "HANDOFF_ARCHIVE_SUBDIR",
    # Ticket 類型 & 優先級
    "TICKET_TYPES",
    "LEGACY_TICKET_TYPES",
    "PRIORITY_LEVELS",
    # 枚舉寫入驗證白名單（寫入邊界收斂）
    "VALID_TICKET_TYPES",
    "VALID_PRIORITIES",
    "VALID_STATUSES",
    "STATUS_TRANSITIONS",
    # Body 章節正典（單一序列來源）
    "CANONICAL_BODY_SECTIONS",
    "APPEND_LOG_EXTRA_SECTIONS",
    # 枚舉驗證閘模式
    "ENUM_GATE_MODE",
    # 預設值
    "DEFAULT_PRIORITY",
    "DEFAULT_HOW_TASK_TYPE",
    "DEFAULT_UNDEFINED_VALUE",
    # Context Bundle (W17-002.1)
    "CONTEXT_BUNDLE_PLACEHOLDER_VALUES",
    "CONTEXT_BUNDLE_MAX_TOTAL_CHARS",
    "CONTEXT_BUNDLE_MAX_ITEMS_PER_FIELD",
    "CONTEXT_BUNDLE_OPT_OUT_KEY",
    "CONTEXT_BUNDLE_OPT_OUT_VALUE_MANUAL",
    "CONTEXT_BUNDLE_UC_INJECTION_KEY",
    "CONTEXT_BUNDLE_UC_INJECTION_MODE_AUTO",
    "CONTEXT_BUNDLE_UC_INJECTION_MODE_MANUAL",
    "CONTEXT_BUNDLE_UC_INJECTION_MODE_OFF",
    "CONTEXT_BUNDLE_UC_INJECTION_MODES",
    "CONTEXT_BUNDLE_SOURCE_KINDS",
    "CONTEXT_BUNDLE_EXTRACT_STATUSES",
    "CONTEXT_BUNDLE_SKIP_REASONS",
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
    # SPEC 引用驗證（0.4.1-W2-001）
    "SPEC_REFERENCE_PATTERN",
    # 重複偵測
    "DUPLICATE_DETECTION_THRESHOLD",
    "DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS",
    "DUPLICATE_BLOCK_THRESHOLD",
    "DUPLICATE_BLOCK_WINDOW_MINUTES",
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

# 寫入驗證白名單（save 閘 / 審計消費；skipped 等語料化石不在正典，
# 其語意由 closed + close_reason 承載）
VALID_STATUSES: frozenset = frozenset(TICKET_STATUS.values())

# 狀態轉移矩陣（lifecycle 兜底驗證消費；claim/complete/release/close 的
# per-command guard 為語意層，本矩陣為落盤前最後防線）。
# 邊集依現行 CLI 語意定稿：claim 接受 pending/blocked（blocked 可重新認領）、
# complete 僅 in_progress、release 依 blockedBy 退 pending 或 blocked、
# close 接受三個非終態。completed 唯一出邊為 superseded（被後繼票取代）——
# 現行 CLI 無寫入 superseded 的命令（grep 實證），此邊為前瞻保留；warn 期
# 出現其他 completed 出邊即為異常訊號。closed / superseded 為終態無出邊。
STATUS_TRANSITIONS: Dict[str, frozenset] = {
    STATUS_PENDING: frozenset({STATUS_IN_PROGRESS, STATUS_BLOCKED, STATUS_CLOSED}),
    STATUS_IN_PROGRESS: frozenset(
        {STATUS_COMPLETED, STATUS_PENDING, STATUS_BLOCKED, STATUS_CLOSED}
    ),
    STATUS_BLOCKED: frozenset({STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_CLOSED}),
    STATUS_COMPLETED: frozenset({STATUS_SUPERSEDED}),
    STATUS_SUPERSEDED: frozenset(),
    STATUS_CLOSED: frozenset(),
}

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
# 嵌套派發深度上限（W1-056.5 協議 v2 D3）
# ============================================================
# 深度 = 沿 parent_id 鏈回溯到根的邊數 + 1（根 = depth 1）。
# 保守設計：平台 5 層 - 1 層 PM - 1 層安全邊距 = 3 層 agent 可用。
# 此常數為 can_descend() 的唯一深度判準來源（DRY，linux F2 修正）。
MAX_TICKET_DEPTH: int = 3

# ============================================================
# 子票扇出 warning 閾值（W5-005 F7/D11）
# ============================================================
# 普查分佈：巨型父票 top4 = 18/16/14/13 子；全語料 67% 無子票。
# 閾值 10 覆蓋 top4 全部超標案例，同時不干擾一般使用。
MAX_CHILDREN_WARNING_THRESHOLD: int = 10

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

# 正典 4 型（寫入邊界收斂裁定：TST/RES 全語料零使用移除——TST 職能由
# tdd_phase 欄位承載、RES/INV 由 ANA 承載）
TICKET_TYPES: Dict[str, str] = {
    "IMP": "Implementation (實作)",
    "ADJ": "Adjustment (調整/修復)",
    "ANA": "Analysis (分析)",
    "DOC": "Documentation (文件)",
}

# 歷史化石容忍集：讀取/審計路徑接受、寫入路徑拒絕。
# 語料現存 type: INV 共 3 筆（TST/RES 零使用），不回填不遷移。
LEGACY_TICKET_TYPES: frozenset = frozenset({"TST", "RES", "INV"})

# 寫入驗證白名單（argparse choices / save 閘消費）
VALID_TICKET_TYPES: frozenset = frozenset(TICKET_TYPES)

PRIORITY_LEVELS: List[str] = ["P0", "P1", "P2", "P3"]
VALID_PRIORITIES: frozenset = frozenset(PRIORITY_LEVELS)

# ============================================================
# 預設值
# ============================================================

DEFAULT_PRIORITY: str = "P2"
DEFAULT_HOW_TASK_TYPE: str = "Implementation"
DEFAULT_UNDEFINED_VALUE: str = "待定義"

# ============================================================
# Context Bundle 抽取（W17-002 / W17-002.1）
# ============================================================
#
# placeholder 清單：_is_placeholder 用於判定 source ticket 欄位是否已填入有效內容。
# 擴為 list（W17-002.1 acceptance #10）涵蓋常見未填值：DEFAULT_UNDEFINED_VALUE
# 為系統官方佔位，其餘為人工撰寫常見變體。
CONTEXT_BUNDLE_PLACEHOLDER_VALUES: tuple = (
    DEFAULT_UNDEFINED_VALUE,
    "TBD",
    "tbd",
    "TODO",
    "todo",
    "待填寫",
    "(待填寫)",
    "（待填寫）",
    "N/A",
    "n/a",
)

# 規模限制
#
# MAX_TOTAL_CHARS rationale（W17-002.1 acceptance #2）：
#   - 2000 字元約 1000 中文 token，對應典型 ticket body 中 Context Bundle section
#     的 10-15% 體積，不致於淹沒 PM 認知負擔。
#   - Phase 1 多視角審查以「PM 可於 10 秒內掃完」為錨，實測 2000 字元約 8-12 秒。
#   - 超過此上限的來源，應由 PM 人工裁切重點，自動抽取退為截斷模式（非丟棄）。
CONTEXT_BUNDLE_MAX_TOTAL_CHARS: int = 2000
CONTEXT_BUNDLE_MAX_ITEMS_PER_FIELD: int = 5

# opt-out 標記（W17-002.1 acceptance #9）：
#   frontmatter 含 `context-bundle: manual` 時，自動抽取不覆寫 section，僅輸出略過訊息。
CONTEXT_BUNDLE_OPT_OUT_KEY: str = "context_bundle"
CONTEXT_BUNDLE_OPT_OUT_VALUE_MANUAL: str = "manual"

# UC 自動注入控制開關（0.38.1-W1-066.4）：
#   frontmatter `context_bundle_uc_injection` 控制 target ticket what/why/acceptance
#   中 UC-XX 引用是否自動注入 UC Context 子章節。auto=偵測到就注入（預設）；
#   manual=偵測到但略過並提示；off=靜默略過（不偵測）。
CONTEXT_BUNDLE_UC_INJECTION_KEY: str = "context_bundle_uc_injection"
CONTEXT_BUNDLE_UC_INJECTION_MODE_AUTO: str = "auto"
CONTEXT_BUNDLE_UC_INJECTION_MODE_MANUAL: str = "manual"
CONTEXT_BUNDLE_UC_INJECTION_MODE_OFF: str = "off"
CONTEXT_BUNDLE_UC_INJECTION_MODES: tuple = (
    CONTEXT_BUNDLE_UC_INJECTION_MODE_AUTO,
    CONTEXT_BUNDLE_UC_INJECTION_MODE_MANUAL,
    CONTEXT_BUNDLE_UC_INJECTION_MODE_OFF,
)

# Literal 枚舉（W17-002.1 acceptance #3：Python 慣例對齊）
# 將 SourceKind / ExtractStatus / SkipReason 的合法值集中於 constants，
# 方便其他模組（test、metric hook）引用而不依賴 extractor 內部私有符號。
CONTEXT_BUNDLE_SOURCE_KINDS: tuple = ("source_ticket", "blocked_by", "related_to")
CONTEXT_BUNDLE_EXTRACT_STATUSES: tuple = (
    "no_source",
    "all_sources_missing",
    "partial",
    "success",
    "self_reference",
    "opt_out",
)
CONTEXT_BUNDLE_SKIP_REASONS: tuple = (
    "source_missing",
    "source_field_undefined",
    "self_reference",
    "opt_out",
)

# ============================================================
# Body 章節正典（單一序列來源）
# ============================================================
# H2 章節正典順序：ticket_builder 缺失章節自動補建定位（SCHEMA_H2_SECTIONS）
# 與 append-log 白名單（VALID_SECTIONS）自此衍生，消除兩清單各自維護的漂移
# （章節名漂移語料實測 77 筆的寫入端防護）。順序即 body 物理順序權威。
CANONICAL_BODY_SECTIONS: tuple = (
    "Task Summary",
    "Problem Analysis",
    "重現實驗結果",
    "Solution",
    "Test Results",
    "Context Bundle",
    "NeedsContext",
    "Exit Status",
    "Spawn Requests",
    "Completion Info",
)

# Execution Log 為 body 的 H1 容器標題（非 H2 章節），僅 append-log 白名單額外接受
APPEND_LOG_EXTRA_SECTIONS: tuple = ("Execution Log",)

# ============================================================
# 枚舉驗證閘模式
# ============================================================
# warn：違規寫入 stderr 警告 + enum-gate.log 記錄後照常落盤（量測期預設）
# deny：違規拒絕落盤。切換 deny 須經 warn 期誤報率量測裁定，禁時間式延後
ENUM_GATE_MODE: str = "deny"

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
# SPEC 引用驗證常數（0.4.1-W2-001，F1：SPEC-008 誤植跨票傳染防護）
# ============================================================

# 比對 --why/--what/--where 等欄位中的 SPEC-NNN 引用；NNN 位數不限（避免
# 未來三位數以上編號被截斷）。
SPEC_REFERENCE_PATTERN: str = r"SPEC-\d+"

# ============================================================
# 重複偵測常數
# ============================================================

DUPLICATE_DETECTION_THRESHOLD: float = 0.3
DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS: int = 7

# Tier 2 阻擋層常數（1.0.0-W1-040.1）
#
# 阻擋層在 Tier 1 警告層之上加「高相似 + 短窗口」雙條件交集，鎖定 ghost
# 雙執行流同 turn（數分鐘內）重複 spawn 同語意票的簽名。
#
# 量測依據（parent 1.0.0-W1-040 重現實驗，五場景 Jaccard 實測）：
#   TP 逐字相同 1.000 / TP 近似改寫 0.688（阻擋目標）
#   FP 兄弟票真實標題 0.031 / 0.069（不阻擋）
#   FP batch 同質模板 0.400（不阻擋，僅 Tier 1 警告）
# TP 下界 0.688 與最高 FP 0.400 之間有 0.28 分隔帶，0.6 可分離兩者。
# 0.6 為工程判斷；若後續樣本顯示分隔帶不足，可調整本值並同步更新本註解。
DUPLICATE_BLOCK_THRESHOLD: float = 0.6

# 短時間窗（分鐘）：候選票建立時間在此窗口內才納入阻擋判定。
# 60 分鐘對應 ghost 同 turn 重複 spawn 的時間尺度（數分鐘級），
# 同時排除「長存 pending 與新票偶然高相似」的合法情境。
DUPLICATE_BLOCK_WINDOW_MINUTES: int = 60

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
