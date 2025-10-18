#!/usr/bin/env python3
"""
除錯 Dart Parser - 檢查 if 關鍵字問題
"""

import sys
from pathlib import Path

hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

from parsers.dart_parser import DartParser

# 測試 if 關鍵字
code = """
if (condition) {
    print('test');
}
"""

print("測試程式碼:")
print(code)
print()

parser = DartParser()
functions = parser.extract_functions(code)

print(f"識別到的函式數量: {len(functions)}")
if functions:
    for func in functions:
        print(f"  - 函式名稱: {func.name}")
        print(f"    行號: {func.line_number}")
        print(f"    回傳類型: {func.return_type}")
else:
    print("  (無函式識別)")

print()

# 檢查行處理邏輯
lines = code.split('\n')
for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped:
        continue
    print(f"行 {i+1}: '{stripped}'")

    first_word = stripped.split()[0] if stripped.split() else ''
    print(f"  第一個詞: '{first_word}'")
    print(f"  移除括號後: '{first_word.rstrip('(')}'")
    print(f"  是否為關鍵字: {first_word.rstrip('(') in parser.keywords}")

    # 測試正則匹配
    match = parser.function_pattern.search(stripped)
    if match:
        print(f"  正則匹配成功:")
        print(f"    回傳類型: {match.group(1)}")
        print(f"    函式名稱: {match.group(2)}")
    else:
        print(f"  正則匹配失敗")

    print()
