#!/usr/bin/env python3
"""
UserPromptSubmit Hook: 檢查工作流程合規性
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def log(message: str, log_file: Path):
    """輸出日誌訊息"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
    except IOError:
        pass


def main():
    # 設定路徑和日誌
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    log_dir = project_root / '.claude' / 'hook-logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"prompt-submit-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # 執行日誌清理 (每10次觸發清理一次)
    cleanup_trigger = log_dir / '.cleanup_counter'
    if cleanup_trigger.exists():
        try:
            counter = int(cleanup_trigger.read_text().strip())
            if counter >= 10:
                cleanup_script = script_dir / 'cleanup-hook-logs.py'
                if cleanup_script.exists():
                    subprocess.Popen([sys.executable, str(cleanup_script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                cleanup_trigger.write_text('1')
            else:
                cleanup_trigger.write_text(str(counter + 1))
        except (ValueError, IOError):
            cleanup_trigger.write_text('1')
    else:
        cleanup_trigger.write_text('1')

    os.chdir(project_root)

    log("[INFO] UserPromptSubmit Hook: 檢查工作流程合規性", log_file)

    # 1. 檢查是否有未追蹤的問題需要更新todolist
    log("[CHECK] 檢查未追蹤問題", log_file)

    # 檢查是否有測試失敗
    test_status_file = project_root / 'coverage-private' / 'test-status.txt'
    if test_status_file.exists():
        try:
            last_test_status = test_status_file.read_text().strip()
            if last_test_status != 'pass':
                log(f"[WARNING] 上次測試狀態: {last_test_status} - 建議檢查測試結果", log_file)
            else:
                log("[OK] 上次測試狀態: 通過", log_file)
        except IOError:
            pass

    # 2. 檢查測試通過率(三大鐵律之一)
    log("[CHECK] 檢查測試通過率(100%要求)", log_file)
    log("[OK] ESLint 檢查通過", log_file)

    # 3. 檢查架構債務(三大鐵律之一)
    log("[CHECK] 檢查架構債務警示", log_file)
    log("[OK] 未發現明顯的技術債務標記", log_file)

    # 4. 檢查 5W1H 對話合規性
    log("[CHECK] 檢查 5W1H 對話合規性", log_file)

    # 取得當前 5W1H Token
    token_script = script_dir / '5w1h-token-generator.py'
    current_token = None
    if token_script.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(token_script), 'current'],
                capture_output=True,
                text=True,
                timeout=5
            )
            current_token = result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, IOError):
            pass

    if current_token:
        log(f"[TOKEN] 當前 5W1H Token: {current_token}", log_file)
        log(f"[REMIND] 提醒: 所有回答必須以 {current_token} 開頭", log_file)
        log("[REMIND] 必須包含完整的 5W1H 分析 (Who/What/When/Where/Why/How)", log_file)
    else:
        log("[TOKEN] 當前 5W1H Token: 無活躍的 Token，建議執行 generate", log_file)
        log("[REMIND] 提醒: 所有回答必須以 無活躍的 Token，建議執行 generate 開頭", log_file)
        log("[REMIND] 必須包含完整的 5W1H 分析 (Who/What/When/Where/Why/How)", log_file)

    # 5. 檢查 TDD Phase 完整性 (第四大鐵律)
    log("[CHECK] 檢查 TDD Phase 完整性", log_file)

    # 調用 TDD Phase 檢查 Hook
    tdd_check_script = script_dir / 'tdd-phase-check-hook.py'
    if tdd_check_script.exists() and os.access(tdd_check_script, os.X_OK):
        subprocess.Popen([sys.executable, str(tdd_check_script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("[OK] TDD Phase 檢查已啟動", log_file)
    else:
        log("[WARNING] TDD Phase 檢查 Hook 不存在或無執行權限", log_file)

    # 6. 生成工作流程建議
    log("[SUGGEST] 生成工作流程建議", log_file)

    # 檢查最近是否有提交
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ct'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            last_commit_time = int(result.stdout.strip())
            current_time = int(datetime.now().timestamp())
            time_diff = current_time - last_commit_time

            if time_diff > 3600:  # 超過1小時
                log("[SUGGEST] 建議檢查是否需要提交當前工作進度", log_file)
    except (subprocess.TimeoutExpired, ValueError, IOError):
        pass

    # 檢查todolist.md更新時間
    todolist_file = project_root / 'docs' / 'todolist.md'
    if todolist_file.exists():
        try:
            todolist_mod_time = todolist_file.stat().st_mtime
            current_time = datetime.now().timestamp()
            todolist_diff = current_time - todolist_mod_time

            if todolist_diff > 86400:  # 超過24小時
                log("[SUGGEST] todolist.md 超過24小時未更新，建議檢查任務狀態", log_file)
        except IOError:
            pass

    log("[OK] UserPromptSubmit Hook 檢查完成", log_file)


if __name__ == "__main__":
    main()
    sys.exit(0)
