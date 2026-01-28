#!/usr/bin/env python3
"""
stop-hook.py
Stop Hook: 主要代理完成回應時執行版本推進檢查
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def get_script_dir():
    """獲取腳本所在目錄"""
    return str(Path(__file__).parent.absolute())

def get_project_root():
    """獲取專案根目錄"""
    script_dir = get_script_dir()
    return str(Path(script_dir).parent.parent)

def setup_logging():
    """設定日誌目錄"""
    project_root = get_project_root()
    log_dir = Path(project_root) / ".claude" / "hook-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"stop-{timestamp}.log"
    return str(log_file)

def log(message, log_file):
    """寫入日誌並打印到控制台"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_message + "\n")

def main():
    log_file = setup_logging()
    project_root = get_project_root()

    log("[START] Stop Hook: 開始執行版本推進檢查", log_file)

    try:
        os.chdir(project_root)

        # 1. 檢查是否有程式碼變更
        log("[CHECK] 檢查版本推進檢查條件", log_file)

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=project_root
        )

        git_changes = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

        if git_changes > 0:
            log(f"[INFO] 偵測到 {git_changes} 個檔案變更", log_file)
        else:
            log("[INFO] 未偵測到檔案變更，跳過版本推進檢查", log_file)
            log("[OK] Stop Hook 版本推進檢查完成", log_file)
            return 0

        # 2. 檢查版本推進檢查腳本
        log("[INFO] 執行智能版本推進檢查", log_file)

        version_check_script = Path(project_root) / "scripts" / "version-progression-check.sh"

        if version_check_script.exists():
            log("[CHECK] 執行 version-progression-check.sh", log_file)
            result = subprocess.run(
                ["bash", str(version_check_script)],
                capture_output=True,
                text=True,
                cwd=project_root
            )

            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write(result.stderr)

            if result.returncode == 0:
                log("[OK] 版本推進檢查完成", log_file)
            else:
                log(f"[WARNING] 版本推進檢查發現問題 (退出碼: {result.returncode})", log_file)
        else:
            log("[WARNING] version-progression-check.sh 腳本不存在，執行簡化檢查", log_file)

            # 簡化版本檢查
            log("[STAT] 執行簡化版本狀態檢查", log_file)

            # 檢查當前版本
            pubspec_path = Path(project_root) / "pubspec.yaml"
            if pubspec_path.exists():
                with open(pubspec_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('version:'):
                            version = line.replace('version:', '').strip()
                            log(f"[INFO] 當前版本: {version}", log_file)
                            break

        # 3. 檢查 todolist.md 狀態
        log("[INFO] 檢查 todolist.md 狀態", log_file)

        todolist_path = Path(project_root) / "docs" / "todolist.md"
        if todolist_path.exists():
            with open(todolist_path, 'r', encoding='utf-8') as f:
                content = f.read()
                completed_tasks = content.count('[x]')
                pending_tasks = content.count('[ ]')

            log(f"[STAT] 任務統計: {completed_tasks} 已完成, {pending_tasks} 待處理", log_file)

            if completed_tasks > 0 and pending_tasks == 0:
                log("[INFO] 所有 todolist 任務已完成，建議考慮中版本推進", log_file)
        else:
            log("[WARNING] todolist.md 檔案不存在", log_file)

        log("[OK] Stop Hook 版本推進檢查完成", log_file)
        return 0

    except Exception as e:
        log(f"[ERROR] 發生錯誤: {str(e)}", log_file)
        return 1

if __name__ == "__main__":
    sys.exit(main())
