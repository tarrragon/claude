#!/usr/bin/env python3
"""
Hook日誌自動清理腳本 - 防止日誌無限累積
設計原則：保留近期必要日誌，清理過期檔案
"""

import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path


def log(message: str):
    """日誌函數"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")


def get_dir_size(path: Path) -> int:
    """取得目錄大小（KB）"""
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except (OSError, IOError):
        pass
    return total // 1024


def count_files(path: Path) -> int:
    """計算檔案數量"""
    try:
        return sum(1 for _ in path.rglob('*') if _.is_file())
    except (OSError, IOError):
        return 0


def cleanup_hook_logs(hook_logs_dir: Path):
    """清理 Hook 日誌"""
    log("[START] 開始Hook日誌清理作業")

    # 統計清理前狀態
    before_count = count_files(hook_logs_dir)
    before_size = get_dir_size(hook_logs_dir)

    log(f"[STAT] 清理前: {before_count} 個檔案, {before_size}KB")

    now = datetime.now()

    # 清理策略1: 刪除超過2小時的臨時日誌檔案
    for log_file in hook_logs_dir.glob('*.log'):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if now - mtime > timedelta(hours=2):
                log_file.unlink()
        except (OSError, IOError):
            pass

    # 清理策略2: 刪除超過4小時的問題追蹤檔案 (保留 issues-to-track.md)
    patterns = ['edit-issues-*.md', 'syntax-error-*.md', 'version-suggestion-*.md']
    for pattern in patterns:
        for file in hook_logs_dir.glob(pattern):
            try:
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if now - mtime > timedelta(hours=4):
                    file.unlink()
            except (OSError, IOError):
                pass

    # 清理策略3: 刪除超過24小時的所有時間戳檔案
    import re
    timestamp_pattern = re.compile(r'202[0-9]{5}_')
    for file in hook_logs_dir.iterdir():
        if file.is_file() and timestamp_pattern.search(file.name):
            try:
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if now - mtime > timedelta(days=1):
                    file.unlink()
            except (OSError, IOError):
                pass

    # 統計清理後狀態
    after_count = count_files(hook_logs_dir)
    after_size = get_dir_size(hook_logs_dir)
    cleaned_count = before_count - after_count

    log(f"[STAT] 清理後: {after_count} 個檔案, {after_size}KB")
    log(f"[RESULT] 已清理: {cleaned_count} 個檔案")

    # 如果檔案數量仍然過多，執行緊急清理
    if after_count > 50:
        log(f"[WARNING] 檔案數量過多 ({after_count})，執行緊急清理")
        emergency_cleanup(hook_logs_dir)


def emergency_cleanup(hook_logs_dir: Path):
    """緊急清理函數"""
    log("[ALERT] 執行緊急清理模式")

    now = datetime.now()

    # 僅保留最近30分鐘的檔案和重要檔案
    for file in hook_logs_dir.iterdir():
        if file.is_file() and file.name != 'issues-to-track.md':
            try:
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if now - mtime > timedelta(minutes=30):
                    file.unlink()
            except (OSError, IOError):
                pass

    final_count = count_files(hook_logs_dir)
    log(f"[RESULT] 緊急清理完成，剩餘檔案: {final_count}")


def check_disk_usage(hook_logs_dir: Path):
    """檢查磁碟使用情況"""
    dir_size = get_dir_size(hook_logs_dir)

    # 如果超過5MB，執行強制清理
    if dir_size > 5120:
        log(f"[WARNING] Hook日誌目錄過大 ({dir_size}KB > 5MB)，執行強制清理")
        emergency_cleanup(hook_logs_dir)


def main():
    # 設定路徑
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    hook_logs_dir = project_root / '.claude' / 'hook-logs'

    if not hook_logs_dir.exists():
        log("[INFO] Hook日誌目錄不存在，無需清理")
        sys.exit(0)

    cleanup_hook_logs(hook_logs_dir)
    check_disk_usage(hook_logs_dir)

    log("[OK] Hook日誌清理作業完成")


if __name__ == "__main__":
    main()
