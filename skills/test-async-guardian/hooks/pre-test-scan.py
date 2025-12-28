#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Pre-Test Scan Hook - 在執行測試前掃描異步資源問題

這是一個 PreToolUse Hook，在 Claude Code 執行 flutter test 或 dart test 前觸發。
如果發現問題，會阻止測試執行並顯示修復建議。

Hook 輸入格式（JSON）：
{
    "tool_name": "Bash",
    "tool_input": {
        "command": "flutter test test/unit/..."
    }
}
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    # 讀取 Hook 輸入
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return 0

        data = json.loads(input_data)
    except json.JSONDecodeError:
        # 如果不是 JSON，直接通過
        return 0

    # 檢查是否為 Bash 工具
    tool_name = data.get('tool_name', '')
    if tool_name != 'Bash':
        return 0

    # 獲取命令
    command = data.get('tool_input', {}).get('command', '')
    if not command:
        return 0

    # 檢查是否為測試命令
    if 'flutter test' not in command and 'dart test' not in command:
        return 0

    # 提取測試路徑
    test_path = _extract_test_path(command)
    if not test_path:
        # 無法確定路徑，預設掃描整個 test 目錄
        test_path = 'test/'

    # 確認路徑存在
    path = Path(test_path)
    if not path.exists():
        # 路徑不存在，讓測試命令自己報錯
        return 0

    # 調用掃描腳本
    script_dir = Path(__file__).parent.parent / 'scripts'
    scanner_script = script_dir / 'async_resource_scanner.py'

    if not scanner_script.exists():
        print(f"⚠️  掃描腳本不存在: {scanner_script}")
        return 0

    # 執行掃描（嚴格模式）
    cmd = ['uv', 'run', str(scanner_script), str(path)]
    if path.is_dir():
        cmd.append('--recursive')

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            cwd=os.getcwd()
        )
        return result.returncode
    except Exception as e:
        print(f"⚠️  執行掃描腳本失敗: {e}")
        return 0


def _extract_test_path(command: str) -> str:
    """從測試命令中提取測試路徑"""
    parts = command.split()

    # 跳過命令本身
    skip_next = False
    for i, part in enumerate(parts):
        if skip_next:
            skip_next = False
            continue

        # 跳過選項和其參數
        if part.startswith('-'):
            if part in ('-t', '--tags', '--exclude-tags', '--name', '--plain-name'):
                skip_next = True
            continue

        # 跳過 flutter/dart test 命令
        if part in ('flutter', 'dart', 'test', 'timeout', '&&', '||'):
            continue

        # 檢查是否為路徑
        if part.endswith('.dart') or part.startswith('test/'):
            return part

    return ''


if __name__ == '__main__':
    sys.exit(main())
