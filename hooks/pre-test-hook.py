#!/usr/bin/env python3
"""
pre-test-hook.py
PreToolUse Hook: 測試執行前環境檢查
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
    log_file = log_dir / f"pre-test-{timestamp}.log"
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

    log_message("[START] PreToolUse Hook (Test): 開始執行測試前環境檢查", log_file)

    # 1. 檢查測試環境準備
    log_message("[CHECK] 檢查測試環境準備", log_file)

    pubspec_lock = Path(project_root) / "pubspec.lock"
    if pubspec_lock.exists():
        log_message("[OK] pubspec.lock 存在，依賴項已解析", log_file)
    else:
        log_message("[ERROR] pubspec.lock 不存在，測試可能失敗", log_file)
        log_message("[INFO] 建議執行: flutter pub get", log_file)

    pubspec_yaml = Path(project_root) / "pubspec.yaml"
    dart_tool = Path(project_root) / ".dart_tool"
    if pubspec_yaml.exists() and dart_tool.exists():
        log_message("[OK] Flutter 測試環境已準備", log_file)
    else:
        log_message("[WARNING] Flutter 測試環境未完全準備", log_file)

    # 2. 檢查測試檔案狀態
    log_message("[INFO] 檢查測試檔案狀態", log_file)

    test_dir = Path(project_root) / "test"
    unit_test_count = 0
    integration_test_count = 0

    if test_dir.exists():
        unit_test_count = len(list(test_dir.glob("*/*_test.dart")))
        integration_dir = test_dir / "integration"
        if integration_dir.exists():
            integration_test_count = len(list(integration_dir.glob("*_test.dart")))

    log_message(f"[STAT] 單元測試檔案: {unit_test_count} 個", log_file)
    log_message(f"[STAT] 整合測試檔案: {integration_test_count} 個", log_file)

    if unit_test_count == 0 and integration_test_count == 0:
        log_message("[WARNING] 未找到測試檔案", log_file)

    # 3. 檢查是否有未提交的測試變更
    log_message("[INFO] 檢查未提交的測試變更", log_file)

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=project_root
    )

    test_changes = 0
    if result.stdout:
        test_changes = len([line for line in result.stdout.split('\n') if '_test.dart' in line])

    if test_changes > 0:
        log_message(f"[WARNING] 發現 {test_changes} 個未提交的測試檔案變更", log_file)

    # 4. 檢查上次測試結果
    log_message("[INFO] 檢查上次測試結果", log_file)

    coverage_private = Path(project_root) / "coverage-private"
    status_file = coverage_private / "test-status.txt"
    if status_file.exists():
        last_status = status_file.read_text().strip()
        log_message(f"[STAT] 上次測試狀態: {last_status}", log_file)
        if last_status != "pass":
            log_message("[WARNING] 上次測試未通過，本次測試需要特別關注", log_file)
    else:
        log_message("[INFO] 未找到上次測試狀態記錄", log_file)

    # 5. 建立測試狀態追蹤
    log_message("[INFO] 建立測試狀態追蹤", log_file)

    coverage_private.mkdir(parents=True, exist_ok=True)
    with open(coverage_private / "test-start-time.txt", 'w') as f:
        f.write(str(int(datetime.now().timestamp())))
    with open(coverage_private / "test-status.txt", 'w') as f:
        f.write("starting")

    # 6. 檢查系統資源
    log_message("[INFO] 檢查系統資源", log_file)

    # 7. 環境變數檢查
    log_message("[INFO] 環境變數檢查", log_file)

    node_path = shutil.which("node")
    if node_path:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        log_message(f"[INFO] Node.js 版本: {result.stdout.strip()}", log_file)
    else:
        log_message("[ERROR] Node.js 未安裝", log_file)

    npm_path = shutil.which("npm")
    if npm_path:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        log_message(f"[INFO] npm 版本: {result.stdout.strip()}", log_file)

    log_message("[OK] PreToolUse Hook (Test) 環境檢查完成", log_file)
    return 0

if __name__ == "__main__":
    sys.exit(main())
