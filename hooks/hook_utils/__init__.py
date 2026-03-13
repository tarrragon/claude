#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook 統一工具模組（重構後）

統一的 Python hook 工具庫，提供日誌、I/O 和 Ticket 操作等功能。
透過 re-export 保持向後相容，54 個現有 hook 無需修改 import 語句。

子模組：
- hook_logging: 日誌、基礎設施和頂層例外處理
- hook_io: I/O 操作（git、stdin JSON、資料提取）
- hook_ticket: Ticket 檔案操作（掃描、解析、驗證）
"""

from .hook_logging import (
    get_project_root,
    setup_hook_logging,
    save_check_log,
    run_hook_safely,
)
from .hook_io import (
    run_git,
    read_json_from_stdin,
    extract_tool_input,
    extract_tool_response,
    is_handoff_recovery_mode,
    clear_handoff_recovery_cache,
    validate_hook_input,
    validate_tool_input,
    is_subagent_environment,
    generate_hook_output,
)
from .hook_ticket import (
    parse_ticket_frontmatter,
    parse_ticket_date,
    check_error_patterns_changed,
    clear_error_pattern_mtime_cache,
    get_current_version_from_todolist,
    scan_ticket_files_by_version,
    find_ticket_files,
    find_ticket_file,
    extract_version_from_ticket_id,
    extract_wave_from_ticket_id,
    validate_ticket_has_decision_tree,
    validate_ticket_unified,
)

__all__ = [
    "get_project_root",
    "setup_hook_logging",
    "save_check_log",
    "run_hook_safely",
    "run_git",
    "read_json_from_stdin",
    "extract_tool_input",
    "extract_tool_response",
    "is_handoff_recovery_mode",
    "clear_handoff_recovery_cache",
    "validate_hook_input",
    "validate_tool_input",
    "is_subagent_environment",
    "generate_hook_output",
    "parse_ticket_frontmatter",
    "parse_ticket_date",
    "check_error_patterns_changed",
    "clear_error_pattern_mtime_cache",
    "get_current_version_from_todolist",
    "scan_ticket_files_by_version",
    "find_ticket_files",
    "find_ticket_file",
    "extract_version_from_ticket_id",
    "extract_wave_from_ticket_id",
    "validate_ticket_has_decision_tree",
    "validate_ticket_unified",
]
