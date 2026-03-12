#!/usr/bin/env python3
"""
Hook 系統通用函數庫

提供公開函式：
- hook_output: 統一輸出 Hook 結果
- read_hook_input: 從 stdin 讀取 Hook 輸入 JSON
- get_project_root: 動態定位專案根目錄

標準化 Import 防護模板：
若 hook 檔案使用本模組，應在導入時加入 try-except：

    try:
        from lib.common_functions import hook_output, read_hook_input
    except ImportError as e:
        print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
        sys.exit(1)

這樣可確保 import 失敗時向使用者明確報告，而不是靜默失敗。

註：Logging 系統已遷移至 hook_utils.py，使用 hook_utils.setup_hook_logging。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Any

# 導入統一的 get_project_root
from hook_utils import get_project_root


def setup_project_environment() -> Tuple[Path, Path, Path]:
    """設定專案根目錄和相關環境變數

    Returns:
        Tuple of (project_dir, hooks_dir, logs_dir)
    """
    project_dir = get_project_root()

    hooks_dir = project_dir / '.claude' / 'hooks'
    logs_dir = project_dir / '.claude' / 'hook-logs'

    # 確保日誌目錄存在
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 設定環境變數
    os.environ['CLAUDE_PROJECT_DIR'] = str(project_dir)
    os.environ['CLAUDE_HOOKS_DIR'] = str(hooks_dir)
    os.environ['CLAUDE_LOGS_DIR'] = str(logs_dir)

    return project_dir, hooks_dir, logs_dir


def log_with_timestamp(log_file: Optional[Path], message: str):
    """通用日誌函數"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    if log_file:
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
        except IOError:
            pass


def should_check_file(file_path: str) -> bool:
    """檢查檔案是否應該被開發流程檢查

    Returns:
        True = 應該檢查, False = 應該跳過
    """
    import re

    # 排除文件檔案（工作日誌除外）
    if file_path.endswith('.md') and not re.search(r'docs/work-logs/v\d+\.\d+\.\d+', file_path):
        return False

    # 排除測試檔案
    if re.search(r'test/|spec/|_test\.(dart|js|ts)$|_spec\.(dart|js|ts)$', file_path):
        return False

    # 排除整個 .claude 目錄
    if file_path.startswith('.claude/'):
        return False

    # 排除生成檔案
    if re.search(r'\.(g|freezed)\.dart$|/generated/', file_path):
        return False

    # 排除文檔目錄（工作日誌除外）
    if file_path.startswith('docs/') and not re.search(r'^docs/work-logs/v\d+\.\d+\.\d+', file_path):
        return False

    return True


def check_key_files(project_root: Path) -> int:
    """檢查關鍵檔案是否存在

    Returns:
        缺失檔案數量
    """
    key_files = [
        "CLAUDE.md",
        "pubspec.yaml",
        "docs/todolist.yaml",
        ".claude/tdd-collaboration-flow.md"
    ]

    missing_files = 0
    for file in key_files:
        if not (project_root / file).exists():
            print(f"[WARNING] 關鍵檔案缺失: {file}", file=sys.stdout)
            missing_files += 1

    return missing_files


def read_hook_input() -> Optional[dict[str, Any]]:
    """從 stdin 讀取 Hook 輸入 JSON

    正確處理：
    1. 空輸入（SessionStart 等事件無輸入）
    2. JSON 解析失敗
    3. 有效的 JSON 物件

    Returns:
        解析後的 JSON 物件，或 None（空輸入或解析失敗）

    Exit Code:
        - 不拋出例外，由呼叫者決定是否終止
    """
    try:
        # 從 stdin 讀取所有資料
        input_text = sys.stdin.read().strip()

        # 空輸入：直接返回 None（某些事件類型無輸入）
        if not input_text:
            return None

        # 解析 JSON
        return json.loads(input_text)

    except json.JSONDecodeError as e:
        # JSON 解析失敗：記錄錯誤並返回 None
        # 注意：不輸出到 stderr，避免觸發 "hook error"
        print(f"Hook warning: JSON decode error: {e}", file=sys.stdout)
        return None
    except Exception as e:
        # 其他異常：輸出到 stdout（而非 stderr）
        print(f"Hook warning: Failed to read input: {e}", file=sys.stdout)
        return None


def hook_output(message: str, level: str = "info") -> None:
    """統一輸出 Hook 結果

    遵循 Claude Code hook 系統規則：
    - stdout = 成功訊息、資訊（給用戶看）
    - stderr = 錯誤訊息（觸發 "hook error"，謹慎使用）

    Args:
        message: 要輸出的訊息
        level: 輸出等級 ("info"|"warning"|"error")
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted_msg = f"[{timestamp}] [{level.upper()}] {message}"

    if level == "error":
        # 錯誤訊息：輸出到 stdout（改為不觸發 "hook error"）
        print(formatted_msg, file=sys.stdout)
    else:
        # 資訊、警告：輸出到 stdout（不觸發 "hook error"）
        print(formatted_msg, file=sys.stdout)
