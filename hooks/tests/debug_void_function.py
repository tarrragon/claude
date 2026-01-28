#!/usr/bin/env python3
import sys
from pathlib import Path

hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

from parsers.dart_parser import DartParser

code_void = """
void testFunction() {
    print('test');
}
"""

print("測試 void 函式:")
print(code_void)

parser = DartParser()

# 測試正則表達式
import re
match = parser.function_pattern.search("void testFunction() {")
if match:
    print(f"正則匹配成功!")
    print(f"  group(1): {match.group(1)}")  # 泛型
    print(f"  group(2): {match.group(2)}")  # 內建類型
    print(f"  group(3): {match.group(3)}")  # 自定義類別
    print(f"  group(4): {match.group(4)}")  # 函式名稱
else:
    print("正則匹配失敗")

print()

functions = parser.extract_functions(code_void)
print(f"識別到的函式數量: {len(functions)}")
if functions:
    for func in functions:
        print(f"  - {func.name} (回傳: {func.return_type})")
else:
    print("  (無函式識別)")
