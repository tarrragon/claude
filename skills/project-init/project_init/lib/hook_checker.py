"""Hook 完整性檢查共享邏輯模組.

此模組提取自 hook_verifier.py 與 hook-completeness-check.py 的共享邏輯，
消除兩者之間約 70-80% 的重複實作。

兩個使用端：
- project_init/lib/hook_verifier.py：作為 library 供 project-init onboard 呼叫
- .claude/hooks/hook-completeness-check.py：作為 SessionStart Hook 執行
"""

import fnmatch
import json
from pathlib import Path
from typing import Optional


def load_json_file(file_path: Path, logger=None) -> Optional[dict]:
    """載入並解析 JSON 檔案.

    Args:
        file_path: JSON 檔案路徑。
        logger: 可選的 logger，若提供則寫入日誌。

    Returns:
        dict: 解析後的 JSON 物件，或 None 若檔案不存在或解析失敗。
    """
    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log_output = f"[HookCheck] Error parsing {file_path}: {e}"
        print(log_output)
        if logger:
            logger.info(log_output)
        return None


def get_exclude_patterns(exclude_list: Optional[dict]) -> tuple[set[str], set[str]]:
    """從 hook-exclude-list.json 提取要排除的檔案清單和模式.

    Args:
        exclude_list: 從 hook-exclude-list.json 解析的 dict，或 None。

    Returns:
        tuple[set[str], set[str]]: (確切檔名集合, 模式集合)
    """
    if exclude_list is None:
        # 預設排除清單（對應 hook-exclude-list.json 的常見內容）
        exact_excludes = {
            "common_functions.py",
            "frontmatter_parser.py",
            "hook_utils.py",
            "markdown_formatter.py",
            "parse-test-json.py",
        }
        patterns = {"*-backup.py"}
        return exact_excludes, patterns

    exact_excludes = set(exclude_list.get("exclude", []))
    patterns = set(exclude_list.get("exclude_patterns", []))
    return exact_excludes, patterns


def should_exclude_file(
    filename: str, exact_excludes: set[str], patterns: set[str]
) -> bool:
    """判斷檔案是否應被排除.

    Args:
        filename: 要檢查的檔名。
        exact_excludes: 確切檔名集合。
        patterns: 模式集合（支援 fnmatch）。

    Returns:
        bool: 是否應被排除。
    """
    if filename in exact_excludes:
        return True

    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True

    return False


def scan_hooks_directory(
    hooks_dir: Path, exact_excludes: set[str], patterns: set[str]
) -> set[str]:
    """掃描 .claude/hooks/ 目錄找到所有 .py 檔案（排除 exclude list）.

    Args:
        hooks_dir: Hook 目錄路徑。
        exact_excludes: 確切檔名集合（要排除的）。
        patterns: 模式集合（要排除的）。

    Returns:
        set[str]: Hook 檔名集合。
    """
    hook_files: set[str] = set()

    if not hooks_dir.exists():
        return hook_files

    for file_path in hooks_dir.glob("*.py"):
        filename = file_path.name
        if should_exclude_file(filename, exact_excludes, patterns):
            continue
        hook_files.add(filename)

    return hook_files


def extract_registered_hooks(settings: dict) -> set[str]:
    """從 settings.json 提取所有已登記的 Hook 檔名.

    掃描 hooks 配置中所有事件類型（PreToolUse、PostToolUse 等），
    從 command 欄位提取 .claude/hooks/ 後的檔名。

    Args:
        settings: settings.json 解析後的 dict。

    Returns:
        set[str]: 已登記的 Hook 檔名集合。
    """
    registered: set[str] = set()
    hooks_config = settings.get("hooks", {})

    for _event_type, event_hooks in hooks_config.items():
        if isinstance(event_hooks, list):
            for hook_group in event_hooks:
                if isinstance(hook_group, dict):
                    for hook in hook_group.get("hooks", []):
                        if isinstance(hook, dict):
                            command = hook.get("command", "")
                            # 從 command 提取檔名
                            # e.g.: "$CLAUDE_PROJECT_DIR/.claude/hooks/hook-name.py" -> "hook-name.py"
                            if ".claude/hooks/" in command:
                                filename = command.split(".claude/hooks/")[-1]
                                # 移除尾部參數
                                filename = filename.split()[0] if filename else ""
                                if filename.endswith(".py"):
                                    registered.add(filename)

    return registered
