#!/usr/bin/env python3
"""
Hook 系統通用函數庫
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def get_project_root() -> Optional[Path]:
    """透過 CLAUDE.md 位置動態定位專案根目錄"""
    current_dir = Path.cwd()

    # 從當前目錄開始往上搜尋 CLAUDE.md
    while current_dir != current_dir.parent:
        if (current_dir / "CLAUDE.md").exists():
            return current_dir
        current_dir = current_dir.parent

    return None


def setup_project_environment() -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """設定專案根目錄和相關環境變數

    Returns:
        Tuple of (project_dir, hooks_dir, logs_dir) or (None, None, None) if failed
    """
    project_dir = get_project_root()
    if project_dir is None:
        print("錯誤: 找不到 CLAUDE.md，無法確定專案根目錄", file=sys.stderr)
        return None, None, None

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
        "docs/todolist.md",
        ".claude/tdd-collaboration-flow.md"
    ]

    missing_files = 0
    for file in key_files:
        if not (project_root / file).exists():
            print(f"[WARNING] 關鍵檔案缺失: {file}", file=sys.stderr)
            missing_files += 1

    return missing_files
