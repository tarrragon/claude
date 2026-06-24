"""
Claude Hooks 共用程式庫

提供 Hook 腳本共用的工具函式，消除程式碼重複。

模組結構:
- git_utils: Git 操作工具（分支、worktree、專案根目錄）
- hook_logging: Hook 日誌系統
- hook_io: Hook 輸入輸出處理

使用方式:
    from lib.git_utils import get_current_branch, run_git_command
    from lib.hook_logging import setup_hook_logging
    from lib.hook_io import read_hook_input, write_hook_output
"""

from .hook_base import ensure_utf8_io, get_project_root

from .git_utils import (
    run_git_command,
    get_current_branch,
    get_worktree_list,
    is_protected_branch,
    is_allowed_branch,
)

from .hook_logging import (
    setup_hook_logging,
    save_check_log,
    run_hook_safely,
    get_hook_log_dir,
)

from .hook_io import (
    read_hook_input,
    read_json_from_stdin,
    write_hook_output,
    create_pretooluse_output,
    create_posttooluse_output,
    create_simple_output,
    run_git,
    get_effort_level,
    extract_tool_input,
    extract_tool_response,
    is_handoff_recovery_mode,
    clear_handoff_recovery_cache,
    validate_hook_input,
    validate_tool_input,
    is_subagent_environment,
    is_background_dispatch,
    generate_hook_output,
    emit_hook_output,
    PM_ONLY_PREFIX,
    get_claude_code_version,
    supports_subagent_stop_additional_context,
    build_subagent_stop_output,
)

from .config_loader import (
    load_config,
    load_agents_config,
    load_quality_rules,
    clear_config_cache,
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
    extract_where_files,
    extract_where_files_from_frontmatter,
    extract_wave_from_ticket_id,
    validate_ticket_has_decision_tree,
    validate_ticket_unified,
    find_active_in_progress_ticket,
)

__all__ = [
    # hook_base
    "ensure_utf8_io",
    "get_project_root",
    # git_utils
    "run_git_command",
    "get_current_branch",
    "get_worktree_list",
    "is_protected_branch",
    "is_allowed_branch",
    # hook_logging
    "setup_hook_logging",
    "save_check_log",
    "run_hook_safely",
    "get_hook_log_dir",
    # hook_io
    "read_hook_input",
    "read_json_from_stdin",
    "write_hook_output",
    "create_pretooluse_output",
    "create_posttooluse_output",
    "create_simple_output",
    "run_git",
    "get_effort_level",
    "extract_tool_input",
    "extract_tool_response",
    "is_handoff_recovery_mode",
    "clear_handoff_recovery_cache",
    "validate_hook_input",
    "validate_tool_input",
    "is_subagent_environment",
    "is_background_dispatch",
    "generate_hook_output",
    "emit_hook_output",
    "PM_ONLY_PREFIX",
    "get_claude_code_version",
    "supports_subagent_stop_additional_context",
    "build_subagent_stop_output",
    # config_loader
    "load_config",
    "load_agents_config",
    "load_quality_rules",
    "clear_config_cache",
    # hook_ticket
    "parse_ticket_frontmatter",
    "parse_ticket_date",
    "check_error_patterns_changed",
    "clear_error_pattern_mtime_cache",
    "get_current_version_from_todolist",
    "scan_ticket_files_by_version",
    "find_ticket_files",
    "find_ticket_file",
    "extract_version_from_ticket_id",
    "extract_where_files",
    "extract_where_files_from_frontmatter",
    "extract_wave_from_ticket_id",
    "validate_ticket_has_decision_tree",
    "validate_ticket_unified",
    "find_active_in_progress_ticket",
]

__version__ = "0.28.0"
