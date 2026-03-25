"""
TDD 序列建議模組

根據任務類型或關鍵字建議合適的 TDD Phase 順序，幫助分析人員和開發者
快速確定該任務應該遵循的開發流程。

核心功能：
1. 識別任務類型（實作、重構、修復、文件等）
2. 根據任務類型建議 TDD Phase 順序
3. 驗證 Phase 前置條件（例：Phase 3b 需先完成 Phase 2）
"""
# 防止直接執行此模組
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    from .constants import TDD_PHASES, TICKET_TYPES
except ImportError:
    # 用於獨立測試或直接執行時的備用匯入
    TDD_PHASES = ["phase1", "phase2", "phase3a", "phase3b", "phase4"]
    TICKET_TYPES = {}


# ============================================================
# 型別定義
# ============================================================


@dataclass
class TDDSequenceResult:
    """TDD 順序建議結果。

    Attributes:
        phases: 建議的 Phase 順序清單
        task_type: 識別出的任務類型代碼（IMP/ADJ/RES 等）
        description: 順序說明（為什麼建議這個順序）
        rationale: 決策理由（用於分析）
    """

    phases: List[str]
    task_type: str
    description: str
    rationale: str


@dataclass
class PhasePrerequisiteResult:
    """Phase 前置條件驗證結果。

    Attributes:
        valid: 是否可以進入該 Phase
        missing_prerequisites: 缺失的前置 Phase 清單
        error_message: 驗證失敗的錯誤訊息（若有）
    """

    valid: bool
    missing_prerequisites: List[str]
    error_message: Optional[str] = None


# ============================================================
# 常數定義
# ============================================================

# 任務類型關鍵字對照表
TASK_TYPE_KEYWORDS: dict[str, tuple[str, List[str]]] = {
    # 新功能實作：包含創建、新增、實作相關詞彙
    "IMP": (
        "新功能",
        [
            "實作",
            "新增",
            "建立",
            "implement",
            "add",
            "create",
            "feature",
        ],
    ),
    # 調整/修復：重構、優化、修復相關詞彙
    "ADJ": (
        "調整/修復",
        [
            "重構",
            "優化",
            "修復",
            "調整",
            "refactor",
            "optimize",
            "fix",
            "adjust",
        ],
    ),
    # 文件：文件、更新、記錄相關詞彙
    "DOC": (
        "文件",
        [
            "文件",
            "文檔",
            "documentation",
            "doc",
            "記錄",
            "更新文檔",
        ],
    ),
    # 研究：研究、探索、評估相關詞彙
    "RES": (
        "研究",
        [
            "研究",
            "探索",
            "評估",
            "research",
            "explore",
            "evaluate",
        ],
    ),
    # 分析：分析、調查相關詞彙
    "ANA": (
        "分析",
        [
            "分析",
            "調查",
            "analyze",
            "investigate",
        ],
    ),
}

# 各任務類型的 TDD Phase 順序建議
TASK_TYPE_TDD_SEQUENCES: dict[str, List[str]] = {
    # 新功能需要完整的 TDD 流程
    "IMP": ["phase1", "phase2", "phase3a", "phase3b", "phase4"],
    # 調整/修復通常跳過 Phase 1（功能已定義）
    "ADJ": ["phase2", "phase3a", "phase3b", "phase4"],
    # 文件不需要 TDD 流程
    "DOC": [],
    # 研究和分析不需要 TDD 流程（屬於前置工作）
    "RES": [],
    "ANA": [],
    "INV": [],
}

# Phase 前置條件對應表
# 例：Phase 3b 需要 Phase 2 和 Phase 3a 都已完成
PHASE_PREREQUISITES: dict[str, List[str]] = {
    "phase1": [],  # 無前置條件
    "phase2": ["phase1"],  # Phase 2 需要 Phase 1 完成
    "phase3a": ["phase2"],  # Phase 3a 需要 Phase 2 完成
    "phase3b": ["phase3a"],  # Phase 3b 需要 Phase 3a 完成
    "phase4": ["phase3b"],  # Phase 4 需要 Phase 3b 完成
}

# Phase 中文名稱對應表（用於訊息輸出）
#
# ⚠️ 同步契約：此映射為 constants.py 中 TDD_PHASE_DISPLAY 的子集
#   - 此映射僅包含核心 TDD 流程的 phase1-phase4 標籤
#   - 用於 TDD 序列建議、Phase 前置條件驗證等內部邏輯
#   - 當修改此映射時，必須同時檢查並更新 TDD_PHASE_DISPLAY：
#     1. 修改 phase1-phase4 的標籤文字時，TDD_PHASE_DISPLAY 中的對應值須同步
#     2. 禁止在此映射中新增 phase0/phase4a/phase4b/phase4c（屬於 TDD_PHASE_DISPLAY 獨有）
#   - 修改前必須確認影響範圍：_generate_sequence_description/PHASE_PREREQUISITES
#   - 詳見 .claude/rules/core/decision-tree.md（第五層 TDD 階段判斷）和 constants.py
#
PHASE_LABELS: dict[str, str] = {
    "phase1": "Phase 1（功能設計）",
    "phase2": "Phase 2（測試設計）",
    "phase3a": "Phase 3a（策略規劃）",
    "phase3b": "Phase 3b（實作執行）",
    "phase4": "Phase 4（重構優化）",
}


# ============================================================
# 核心函式
# ============================================================


def identify_task_type(
    task_type: Optional[str] = None, keywords: Optional[List[str]] = None
) -> str:
    """
    識別任務類型。

    根據明確指定的 task_type 或關鍵字清單識別任務類型。
    若同時指定了 task_type，優先使用；否則根據關鍵字逐一檢查。

    演算法：
    1. Guard Clause 1：若有明確指定的 task_type，直接返回
    2. Guard Clause 2：若未提供任何資訊，返回預設類型 IMP
    3. 遍歷關鍵字進行匹配，返回第一個符合的類型

    Args:
        task_type: 明確指定的任務類型代碼（IMP/ADJ/DOC 等）
        keywords: 關鍵字清單（如：["實作", "新增"]）

    Returns:
        str: 識別出的任務類型代碼（如 "IMP"）
             若無法識別，返回預設值 "IMP"

    Examples:
        >>> identify_task_type(task_type="ADJ")
        'ADJ'
        >>> identify_task_type(keywords=["修復", "優化"])
        'ADJ'
        >>> identify_task_type(keywords=["文件", "更新"])
        'DOC'
        >>> identify_task_type()
        'IMP'
    """
    # Guard Clause 1：明確指定的 task_type
    if task_type:
        return task_type

    # Guard Clause 2：無任何資訊，返回預設類型
    if not keywords:
        return "IMP"

    # 根據關鍵字進行匹配
    return _match_task_type_by_keywords(keywords)


def _match_task_type_by_keywords(keywords: List[str]) -> str:
    """
    根據關鍵字清單匹配任務類型。

    遍歷所有任務類型，檢查輸入的關鍵字是否符合。
    支援不分大小寫的匹配。

    Args:
        keywords: 關鍵字清單

    Returns:
        str: 匹配到的任務類型，若無符合則返回 "IMP"

    Examples:
        >>> _match_task_type_by_keywords(["修復"])
        'ADJ'
    """
    for type_code, (_, type_keywords) in TASK_TYPE_KEYWORDS.items():
        # 檢查輸入的 keywords 中是否有任何一個符合
        for keyword in keywords:
            # 轉換為小寫以支援不分大小寫的匹配
            if keyword.lower() in [kw.lower() for kw in type_keywords]:
                return type_code

    # 預設返回 IMP
    return "IMP"


def suggest_tdd_sequence(
    task_type: Optional[str] = None, keywords: Optional[List[str]] = None
) -> TDDSequenceResult:
    """
    根據任務類型建議 TDD Phase 順序。

    輸入任務類型或關鍵字，返回建議的 TDD Phase 順序和說明。

    Args:
        task_type: 明確指定的任務類型代碼（IMP/ADJ/DOC 等）
        keywords: 關鍵字清單（如：["實作", "新增"]）

    Returns:
        TDDSequenceResult: 包含 phases、task_type、description、rationale

    Examples:
        >>> result = suggest_tdd_sequence(task_type="IMP")
        >>> result.phases
        ['phase1', 'phase2', 'phase3a', 'phase3b', 'phase4']
    """
    # 識別任務類型
    identified_type = identify_task_type(task_type=task_type, keywords=keywords)

    # 查詢 Phase 順序並產生說明
    phases = TASK_TYPE_TDD_SEQUENCES.get(identified_type, [])
    description = _generate_sequence_description(identified_type, phases)
    rationale = _generate_sequence_rationale(identified_type)

    return TDDSequenceResult(
        phases=phases, task_type=identified_type, description=description, rationale=rationale
    )


def validate_phase_prerequisite(
    current_phase: str, completed_phases: List[str]
) -> PhasePrerequisiteResult:
    """
    驗證是否可以進入指定 Phase（檢查前置條件）。

    檢查給定的 Phase 的所有前置條件是否都已完成。
    例：若要進入 Phase 3b，必須先完成 Phase 3a。

    Args:
        current_phase: 要進入的 Phase（如 "phase3b"）
        completed_phases: 已完成的 Phase 清單（如 ["phase1", "phase2"]）

    Returns:
        PhasePrerequisiteResult: 包含 valid、missing_prerequisites、error_message

    Examples:
        >>> result = validate_phase_prerequisite("phase3b", ["phase1", "phase2", "phase3a"])
        >>> result.valid
        True
    """
    # Guard Clause 1：檢查 Phase 是否有效
    if current_phase not in PHASE_PREREQUISITES:
        return PhasePrerequisiteResult(
            valid=False,
            missing_prerequisites=[],
            error_message=f"無效的 Phase: {current_phase}",
        )

    # 查詢前置條件
    prerequisites = PHASE_PREREQUISITES.get(current_phase, [])

    # Guard Clause 2：若無前置條件，直接返回成功
    if not prerequisites:
        return PhasePrerequisiteResult(valid=True, missing_prerequisites=[])

    # 檢查前置條件並返回結果
    return _check_prerequisites_satisfied(current_phase, prerequisites, completed_phases)


def _check_prerequisites_satisfied(
    current_phase: str, prerequisites: List[str], completed_phases: List[str]
) -> PhasePrerequisiteResult:
    """
    檢查前置條件是否都已滿足。

    Args:
        current_phase: 當前 Phase
        prerequisites: 前置 Phase 清單
        completed_phases: 已完成的 Phase 清單

    Returns:
        PhasePrerequisiteResult: 驗證結果

    Examples:
        >>> _check_prerequisites_satisfied("phase3b", ["phase3a"], ["phase1", "phase2"])
        PhasePrerequisiteResult(valid=False, missing_prerequisites=['phase3a'], ...)
    """
    # 找出缺失的前置 Phase
    missing = [p for p in prerequisites if p not in completed_phases]

    # 若無缺失，返回成功
    if not missing:
        return PhasePrerequisiteResult(valid=True, missing_prerequisites=[])

    # 產生錯誤訊息
    phase_labels = ", ".join([PHASE_LABELS.get(p, p) for p in missing])
    error_msg = (
        f"無法進入 {PHASE_LABELS.get(current_phase, current_phase)}，"
        f"尚需完成：{phase_labels}"
    )

    return PhasePrerequisiteResult(
        valid=False, missing_prerequisites=missing, error_message=error_msg
    )


# ============================================================
# 輔助函式
# ============================================================


def _generate_sequence_description(task_type: str, phases: List[str]) -> str:
    """
    產生 Phase 順序的可讀說明。

    根據任務類型和 Phase 順序生成適當的中文說明，幫助使用者快速理解
    該任務應該遵循的開發流程。

    Args:
        task_type: 任務類型代碼
        phases: Phase 清單

    Returns:
        str: 可讀的說明文字

    Examples:
        >>> _generate_sequence_description("IMP", ["phase1", "phase2", "phase3a", "phase3b", "phase4"])
        '新功能需要完整的 TDD 流程：功能設計 → 測試設計 → 策略規劃 → 實作執行 → 重構優化'
    """
    # 取得任務類型的標籤
    type_label = TASK_TYPE_KEYWORDS.get(task_type, ("未知", []))[0]

    # Guard Clause：無 Phase（如文件類型）
    if not phases:
        return f"{type_label}不需要 TDD 流程"

    # 產生 Phase 標籤清單
    phase_labels = [PHASE_LABELS.get(p, p) for p in phases]

    # 連接成可讀的序列（用箭頭分隔）
    sequence_str = " → ".join(phase_labels)

    return f"{type_label}需要以下 TDD 流程：{sequence_str}"


def _generate_sequence_rationale(task_type: str) -> str:
    """
    產生 Phase 順序建議的理由。

    根據任務類型生成簡短的理由說明，幫助使用者理解為什麼選擇這個順序。

    Args:
        task_type: 任務類型代碼

    Returns:
        str: 理由說明

    Examples:
        >>> _generate_sequence_rationale("IMP")
        '新功能需要完整的 TDD 流程以確保設計合理、測試完整、品質穩定'
    """
    rationale_map = {
        "IMP": "新功能需要完整的 TDD 流程以確保設計合理、測試完整、品質穩定",
        "ADJ": "調整類任務可跳過功能設計（功能已定義），從測試設計開始",
        "DOC": "文件類任務無需 TDD 流程，直接進行編寫",
        "RES": "研究類任務作為前置工作，不進入 TDD 流程",
        "ANA": "分析類任務作為前置工作，不進入 TDD 流程",
        "INV": "調查類任務作為前置工作，不進入 TDD 流程",
    }

    return rationale_map.get(task_type, "無特定理由")


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
