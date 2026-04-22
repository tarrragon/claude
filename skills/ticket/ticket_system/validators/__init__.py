"""Ticket frontmatter validators (shared by hook and CLI).

模組供以下使用者共用：
- .claude/hooks/ticket-frontmatter-validator-hook.py (PostToolUse 事後警告)
- ticket_system CLI set-acceptance / status update 子命令 
"""

from .frontmatter_validator import (
    ValidationIssue,
    validate_frontmatter,
    validate_status,
    validate_completed_at,
    validate_acceptance,
    validate_who,
)

__all__ = [
    "ValidationIssue",
    "validate_frontmatter",
    "validate_status",
    "validate_completed_at",
    "validate_acceptance",
    "validate_who",
]
