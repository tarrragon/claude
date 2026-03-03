#!/usr/bin/env python3
"""
test-summary.py - 測試摘要腳本
功能: 執行 flutter test 並生成簡潔摘要
解決 flutter test 輸出過大問題 (4.6MB+ → <50KB)

使用: python3 test-summary.py [可選測試路徑]
      例如: python3 test-summary.py test/unit/
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

def get_script_dir():
    """獲取腳本所在目錄"""
    return str(Path(__file__).parent.absolute())

def get_project_root():
    """獲取專案根目錄"""
    script_dir = get_script_dir()
    project_root = os.environ.get('CLAUDE_PROJECT_DIR')
    if not project_root:
        project_root = str(Path(script_dir).parent.parent)
    return project_root

def setup_logging():
    """設定日誌目錄"""
    project_root = get_project_root()
    log_dir = Path(project_root) / ".claude" / "hook-logs" / "test-summary"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"execution-{timestamp}.log"
    return str(log_file), project_root

def log_message(message, log_file):
    """記錄執行開始"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_entry + "\n")

def main():
    log_file, project_root = setup_logging()
    test_path = sys.argv[1] if len(sys.argv) > 1 else "test/"

    log_message("[START] 測試摘要執行開始", log_file)
    log_message(f"  專案根目錄: {project_root}", log_file)
    log_message(f"  測試路徑: {test_path}", log_file)

    # 驗證專案根目錄
    pubspec_path = Path(project_root) / "pubspec.yaml"
    if not pubspec_path.exists():
        error_msg = f"""[ERROR] 錯誤: 無法定位 Flutter 專案根目錄

當前路徑: {project_root}
預期檔案: {pubspec_path}

修復建議:
1. 確認 CLAUDE_PROJECT_DIR 環境變數是否設定正確
2. 或在專案根目錄執行此腳本
3. 驗證 pubspec.yaml 是否存在

詳細日誌: {log_file}
"""
        print(error_msg)
        log_message(f"[ERROR] 專案根目錄驗證失敗", log_file)
        return 2

    # 切換到專案目錄
    os.chdir(project_root)

    # 執行測試並捕獲輸出
    log_message("[START] 執行 flutter test 命令", log_file)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        temp_json = tmp.name

    try:
        result = subprocess.run(
            ["flutter", "test", "--reporter", "json", test_path],
            stdout=open(temp_json, 'w'),
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_root
        )

        if result.returncode != 0:
            log_message(f"[WARNING] flutter test 命令執行失敗 (exit code: {result.returncode})", log_file)
            if result.stderr:
                log_message(f"stderr: {result.stderr}", log_file)

        # 驗證臨時檔案
        temp_path = Path(temp_json)
        if not temp_path.exists() or temp_path.stat().st_size == 0:
            error_msg = f"""[ERROR] 錯誤: 測試輸出檔案未生成

臨時檔案: {temp_json}

修復建議:
1. 檢查 flutter test 命令是否安裝
2. 檢查測試路徑是否正確
3. 檢查專案是否能正常構建

詳細日誌: {log_file}
"""
            print(error_msg)
            log_message(f"[ERROR] 測試輸出檔案驗證失敗", log_file)
            return 2

        file_size = temp_path.stat().st_size
        log_message(f"[INFO] 測試輸出大小: {file_size} bytes", log_file)

        # 調用 Python 解析器
        log_message("[START] 調用 Python 解析器生成摘要", log_file)

        parser_script = Path(get_script_dir()) / "parse-test-json.py"
        result = subprocess.run(
            ["python3", str(parser_script), temp_json],
            cwd=project_root
        )

        if result.returncode != 0:
            error_msg = f"""[ERROR] 錯誤: 測試結果解析失敗

Python 解析器: {parser_script}
輸入檔案: {temp_json}

修復建議:
1. 確認 parse-test-json.py 存在且可執行
2. 檢查 Python 版本 (需要 3.6+)
3. 檢查臨時檔案是否有效的 JSON

詳細日誌: {log_file}
"""
            print(error_msg)
            log_message(f"[ERROR] 測試結果解析失敗", log_file)
            return 2

        log_message("[OK] 測試摘要執行完成", log_file)
        return 0

    finally:
        # 清理臨時檔案
        try:
            Path(temp_json).unlink()
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())
