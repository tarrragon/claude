#!/usr/bin/env python3
import sys
from pathlib import Path

hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

from parsers.dart_parser import DartParser

code = """
void testFunction() {
    print('test');
}
"""

parser = DartParser()
lines = code.split('\n')

print("逐行掃描分析:")
for i, line in enumerate(lines):
    print(f"\n行 {i+1}: '{line}'")
    stripped = line.strip()
    print(f"  stripped: '{stripped}'")

    if not stripped or stripped.startswith('//'):
        print(f"  → 跳過（空行或註解）")
        continue

    # 檢查是否以關鍵字開頭
    first_word = stripped.split()[0] if stripped.split() else ''
    print(f"  first_word: '{first_word}'")
    print(f"  first_word.rstrip('('): '{first_word.rstrip('(')}'")
    print(f"  是否為關鍵字: {first_word.rstrip('(') in parser.keywords}")

    if first_word.rstrip('(') in parser.keywords:
        print(f"  → 跳過（關鍵字）")
        continue

    # 檢查正則匹配
    match = parser.function_pattern.search(stripped)
    if match:
        print(f"  → 正則匹配成功!")
        return_type = match.group(1) or match.group(2) or match.group(3)
        func_name = match.group(4)
        print(f"    return_type: {return_type}")
        print(f"    func_name: {func_name}")

        # 檢查是否為關鍵字
        if func_name in parser.keywords:
            print(f"    → 過濾（函式名為關鍵字）")
        # 檢查是否為建構式
        elif func_name[0].isupper():
            print(f"    → 過濾（PascalCase 建構式）")
        else:
            print(f"    → ✅ 應該加入函式列表")
    else:
        print(f"  → 正則匹配失敗")
