#!/usr/bin/env python3
"""
除錯 build 函式識別問題
"""

import sys
from pathlib import Path

hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

from parsers.dart_parser import DartParser

# 測試 build 函式
code = """
Widget build(BuildContext context) {
    return SizedBox(width: 10);
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
        print(f"    回傳類型: {func.return_type}")
else:
    print("  (無函式識別)")

print()
print("原因分析:")
print("  'Widget' 不在正則表達式的回傳類型列表中")
print("  目前支援的回傳類型: Future, Stream, OperationResult, void, bool, int, String, double, List, Map")
print("  需要擴展回傳類型模式以支援自定義類別")
