"""
Ticket System 共用工具庫

提供 Ticket 系統中各 SKILL 共用的工具函式，消除重複程式碼。

模組結構：
- constants: 常數定義（狀態、路徑、TDD Phase）
- ticket_loader: Ticket 載入和解析
- ticket_validator: Ticket 格式驗證
- ticket_formatter: Ticket 格式化輸出
- tdd_sequence: TDD 序列建議和驗證
"""

from .constants import (
    TICKET_STATUS,
    TICKET_ID_PATTERN,
    TICKET_PATHS,
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_BLOCKED,
)
from .ticket_loader import (
    get_project_root,
    get_current_version,
    get_tickets_dir,
    get_ticket_path,
    load_ticket,
    parse_frontmatter,
    save_ticket,
    list_tickets,
    get_chain_index,
)
from .ticket_chain_index import TicketChainIndex
from .ticket_validator import (
    validate_ticket_id,
    validate_ticket_fields,
)
from .ticket_formatter import (
    format_status_icon,
    format_ticket_summary,
    format_ticket_tree,
)
from .tdd_sequence import (
    TDDSequenceResult,
    PhasePrerequisiteResult,
    identify_task_type,
    suggest_tdd_sequence,
    validate_phase_prerequisite,
)
from .wave_calculator import (
    WaveCalculationResult,
    WaveCalculator,
)
from .critical_path import (
    CriticalPathResult,
    CriticalPathAnalyzer,
)

__all__ = [
    # constants
    "TICKET_STATUS",
    "TICKET_ID_PATTERN",
    "TICKET_PATHS",
    "STATUS_PENDING",
    "STATUS_IN_PROGRESS",
    "STATUS_COMPLETED",
    "STATUS_BLOCKED",
    # ticket_loader
    "get_project_root",
    "get_current_version",
    "get_tickets_dir",
    "get_ticket_path",
    "load_ticket",
    "parse_frontmatter",
    "save_ticket",
    "list_tickets",
    "get_chain_index",
    # ticket_chain_index
    "TicketChainIndex",
    # ticket_validator
    "validate_ticket_id",
    "validate_ticket_fields",
    # ticket_formatter
    "format_status_icon",
    "format_ticket_summary",
    "format_ticket_tree",
    # tdd_sequence
    "TDDSequenceResult",
    "PhasePrerequisiteResult",
    "identify_task_type",
    "suggest_tdd_sequence",
    "validate_phase_prerequisite",
    # wave_calculator
    "WaveCalculationResult",
    "WaveCalculator",
    # critical_path
    "CriticalPathResult",
    "CriticalPathAnalyzer",
]
