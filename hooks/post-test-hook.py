#!/usr/bin/env python3
"""
post-test-hook.py
PostToolUse Hook: 測試執行後結果分析和問題追蹤
"""

import os
import sys
import subprocess
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
    log_file = log_dir / f"post-test-{timestamp}.log"
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

    log_message("[START] PostToolUse Hook (Test): 開始執行測試後分析", log_file)

    # 1. 檢查測試結果狀態
    log_message("[STAT] 檢查測試結果狀態", log_file)

    test_output_file = None
    coverage_private = Path(project_root) / "coverage-private"
    if (coverage_private / "latest-test-output.log").exists():
        test_output_file = "coverage-private/latest-test-output.log"
    elif Path(project_root / "test-output.log").exists():
        test_output_file = "test-output.log"

    test_status = "unknown"
    if test_output_file:
        log_message(f"[INFO] 分析測試輸出: {test_output_file}", log_file)
        with open(test_output_file, 'r', encoding='utf-8') as f:
            content = f.read()

        if "failed" in content.lower():
            import re
            match = re.search(r'(\d+)\s+failed', content)
            if match:
                failed_count = match.group(1)
                log_message(f"[ERROR] 發現 {failed_count} 個測試失敗", log_file)
            test_status = "fail"
        elif "passed" in content.lower() or "All tests passed" in content:
            log_message("[OK] 所有測試通過", log_file)
            test_status = "pass"
        else:
            log_message("[WARNING] 無法確定測試狀態", log_file)

        coverage_private.mkdir(exist_ok=True)
        with open(coverage_private / "test-status.txt", 'w') as f:
            f.write(test_status)
    else:
        log_message("[WARNING] 未找到測試輸出檔案", log_file)

    # 2. 三大鐵律檢查 - 100% 測試通過率
    log_message("[CHECK] 三大鐵律檢查 - 100% 測試通過率", log_file)

    coverage_private.mkdir(exist_ok=True)
    status_file = coverage_private / "test-status.txt"
    test_status = status_file.read_text().strip() if status_file.exists() else "unknown"

    if test_status != "pass":
        log_message(f"[ERROR] 違反測試通過率鐵律! 當前狀態: {test_status}", log_file)

        critical_issue = Path(project_root) / ".claude" / "hook-logs" / f"critical-test-failure-{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(critical_issue, 'w') as f:
            f.write(f"## [ERROR] CRITICAL: 違反測試通過率鐵律 - {datetime.now()}\n\n")
            f.write("- [ERROR] **[測試失敗] 測試通過率不是100%**\n")
            f.write("  - 發現位置: 測試執行結果\n")
            f.write("  - 影響評估: Critical\n")
            f.write("  - 預期修復時間: 立即\n")
            f.write(f"  - 當前狀態: {test_status}\n\n")
            f.write("**CLAUDE.md 鐵律**: 任何測試失敗 = 立即修正，其他工作全部暫停\n")

        log_message(f"[INFO] 已生成關鍵問題追蹤: {critical_issue}", log_file)
        log_message("[WARNING] 根據CLAUDE.md鐵律，必須立即修正測試問題!", log_file)
    else:
        log_message("[OK] 測試通過率鐵律檢查通過", log_file)

    # 3. 測試覆蓋率分析
    log_message("[INFO] 測試覆蓋率分析", log_file)

    coverage_dir = None
    if (Path(project_root) / "coverage").exists():
        coverage_dir = "coverage"
    elif coverage_private.exists():
        coverage_dir = "coverage-private"

    if coverage_dir:
        coverage_report = Path(project_root) / coverage_dir / "lcov-report" / "index.html"
        if coverage_report.exists():
            log_message(f"[INFO] 覆蓋率報告可用: {coverage_dir}/lcov-report/index.html", log_file)

    log_message("[OK] PostToolUse Hook (Test) 分析完成", log_file)
    return 0

if __name__ == "__main__":
    sys.exit(main())
