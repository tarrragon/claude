#!/usr/bin/env python3
"""
pre-commit-hook.py
PreToolUse Hook: Git commit 前自動執行檢查
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

def get_script_dir():
    return str(Path(__file__).parent.absolute())

def get_project_root():
    script_dir = get_script_dir()
    return str(Path(script_dir).parent.parent)

def setup_logging():
    project_root = get_project_root()
    log_dir = Path(project_root) / ".claude" / "hook-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pre-commit-{timestamp}.log"
    return str(log_file), project_root

def log_message(message, log_file):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_entry + "\n")

def main():
    log_file, project_root = setup_logging()
    os.chdir(project_root)

    log_message("[START] PreToolUse Hook (Git Commit): 開始執行提交前檢查", log_file)

    # 1. 執行工作日誌檢查
    log_message("[INFO] 執行工作日誌檢查", log_file)
    check_worklog_script = Path(project_root) / "scripts" / "check-work-log.sh"
    if check_worklog_script.exists():
        log_message("[START] 執行 check-work-log.sh", log_file)
        result = subprocess.run(["bash", str(check_worklog_script)], cwd=project_root)
        if result.returncode != 0:
            log_message(f"[WARNING] 工作日誌檢查發現問題 (退出碼: {result.returncode})", log_file)
        else:
            log_message("[OK] 工作日誌檢查通過", log_file)
    else:
        log_message("[WARNING] check-work-log.sh 腳本不存在", log_file)

    # 2. 強制問題追蹤檢查
    log_message("[CHECK] 強制問題追蹤檢查", log_file)

    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        cwd=project_root
    )

    staged_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
    if staged_files:
        log_message("[INFO] 暫存區檔案:", log_file)
        for file in staged_files:
            if file:
                log_message(f"  - {file}", log_file)

        # 檢查 TODO 等標記
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            cwd=project_root
        )

        debt_markers = ["TODO", "FIXME", "HACK", "XXX"]
        debt_count = sum(result.stdout.count(marker) for marker in debt_markers)

        if debt_count > 0:
            log_message(f"[WARNING] 暫存區發現 {debt_count} 個技術債務標記", log_file)
            reminder_file = Path(project_root) / ".claude" / "hook-logs" / f"commit-issues-{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(reminder_file, 'w') as f:
                f.write(f"## [WARNING] 提交中發現的問題 - {datetime.now()}\n")
                f.write("### 技術債務標記\n")
                for line in result.stdout.split('\n'):
                    if any(marker in line for marker in debt_markers):
                        f.write(f"{line}\n")
                f.write("\n**影響評估**: Medium\n")
                f.write("**建議行動**: 確認這些標記是否需要立即處理或加入todolist.md追蹤\n")
            log_message(f"[INFO] 已生成問題追蹤報告: {reminder_file}", log_file)

    # 3. 檢查是否包含工作日誌更新
    log_message("[STAT] 檢查工作日誌更新狀態", log_file)
    if any("docs/work-logs/" in f for f in staged_files):
        log_message("[OK] 提交包含工作日誌更新", log_file)
    else:
        log_message("[INFO] 提醒: 提交中未包含工作日誌更新", log_file)

    # 4. Flutter 程式碼檢查
    log_message("[START] Flutter 程式碼品質檢查", log_file)

    flutter_path = shutil.which("flutter")
    if flutter_path:
        result = subprocess.run(
            ["flutter", "analyze", "--no-fatal-infos", "--no-fatal-warnings"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        if result.returncode == 0:
            log_message("[OK] Flutter analyze 檢查通過", log_file)
        else:
            log_message("[WARNING] Flutter analyze 發現問題，建議修復後再提交", log_file)
    else:
        log_message("[WARNING] Flutter 未安裝，跳過分析", log_file)

    # 5. 版本同步檢查
    log_message("[START] 版本同步檢查", log_file)
    version_check_script = Path(project_root) / "scripts" / "check-version-sync.sh"
    if version_check_script.exists():
        result = subprocess.run(["bash", str(version_check_script)], cwd=project_root)
        if result.returncode != 0:
            log_message("[WARNING] 版本同步檢查發現問題", log_file)
        else:
            log_message("[OK] 版本同步檢查通過", log_file)

    log_message("[OK] PreToolUse Hook (Git Commit) 檢查完成", log_file)
    return 0

if __name__ == "__main__":
    sys.exit(main())
