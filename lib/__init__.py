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

from .git_utils import (
    run_git_command,
    get_current_branch,
    get_project_root,
    get_worktree_list,
    is_protected_branch,
    is_allowed_branch,
)

from .hook_logging import setup_hook_logging

from .hook_io import (
    read_hook_input,
    write_hook_output,
    create_pretooluse_output,
    create_posttooluse_output,
)

from .config_loader import (
    load_config,
    load_agents_config,
    load_quality_rules,
    clear_config_cache,
)

__all__ = [
    # git_utils
    "run_git_command",
    "get_current_branch",
    "get_project_root",
    "get_worktree_list",
    "is_protected_branch",
    "is_allowed_branch",
    # hook_logging
    "setup_hook_logging",
    # hook_io
    "read_hook_input",
    "write_hook_output",
    "create_pretooluse_output",
    "create_posttooluse_output",
    # config_loader
    "load_config",
    "load_agents_config",
    "load_quality_rules",
    "clear_config_cache",
]

__version__ = "0.28.0"
