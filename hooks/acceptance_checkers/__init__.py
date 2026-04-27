"""
Acceptance Checkers - acceptance-gate-hook 的模組化檢查器

每個 checker 負責單一檢查職責，由 orchestrator (acceptance-gate-hook.py) 協調呼叫。
"""

from acceptance_checkers.ticket_parser import (
    extract_children_from_frontmatter,
    get_ticket_status,
    get_ticket_type,
    is_doc_type,
    is_ana_type,
)
from acceptance_checkers.children_checker import (
    check_children_completed,
    check_children_completed_from_frontmatter,
)
from acceptance_checkers.acceptance_checker import (
    has_acceptance_record,
    verify_acceptance_record,
)
from acceptance_checkers.error_pattern_checker import (
    check_error_pattern_conflicts,
)
from acceptance_checkers.error_pattern_attribution import (
    filter_error_patterns_by_ticket_scope,
)
from acceptance_checkers.five_w1h_checker import (
    check_5w1h_completeness,
)
from acceptance_checkers.execution_log_checker import (
    check_execution_log_filled,
)
from acceptance_checkers.custom_h2_checker import (
    check_custom_h2_sections,
    find_custom_h2_sections,
)
from acceptance_checkers.ana_spawned_checker import (
    extract_spawned_tickets_from_frontmatter,
    check_ana_has_spawned_tickets,
)
from acceptance_checkers.sibling_checker import (
    find_pending_sibling_tickets,
)
from acceptance_checkers.multi_view_checker import (
    check_multi_view_status,
)
