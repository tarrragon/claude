#!/usr/bin/env python3
"""
簡易測試執行器（不依賴 pytest）

用途: 在沒有 pytest 的環境中執行測試
執行方式: python3 run_tests.py
"""

import sys
from pathlib import Path

# 加入 parsers 模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers import (
    Language,
    LanguageParser,
    Function,
    ParserFactory,
    DartParser,
    JavaScriptParser,
)


def test_language_detection():
    """測試語言檢測功能"""
    print("\n=== 測試語言檢測 ===")

    tests = [
        ('lib/main.dart', Language.DART),
        ('src/app.js', Language.JAVASCRIPT),
        ('src/app.ts', Language.TYPESCRIPT),
        ('components/Button.jsx', Language.JAVASCRIPT),
        ('components/Button.tsx', Language.TYPESCRIPT),
        ('module.mjs', Language.JAVASCRIPT),
        ('file.xyz', Language.UNKNOWN),
        ('Main.DART', Language.DART),  # 大小寫不敏感
    ]

    passed = 0
    failed = 0

    for file_path, expected_language in tests:
        detected = ParserFactory.detect_language(file_path)
        if detected == expected_language:
            print(f"✅ {file_path} → {detected}")
            passed += 1
        else:
            print(f"❌ {file_path} → 預期 {expected_language}，實際 {detected}")
            failed += 1

    return passed, failed


def test_parser_creation():
    """測試 Parser 創建功能"""
    print("\n=== 測試 Parser 創建 ===")

    tests = [
        (Language.DART, DartParser),
        (Language.JAVASCRIPT, JavaScriptParser),
        (Language.TYPESCRIPT, JavaScriptParser),  # TypeScript 使用 JavaScriptParser
    ]

    passed = 0
    failed = 0

    for language, expected_class in tests:
        parser = ParserFactory.create_parser(language)
        if isinstance(parser, expected_class):
            print(f"✅ {language} → {parser.__class__.__name__}")
            passed += 1
        else:
            print(f"❌ {language} → 預期 {expected_class.__name__}，實際 {parser.__class__.__name__}")
            failed += 1

    # 測試根據檔案路徑創建
    files = [
        ('lib/main.dart', DartParser),
        ('src/app.js', JavaScriptParser),
        ('src/app.ts', JavaScriptParser),
    ]

    for file_path, expected_class in files:
        parser = ParserFactory.create_parser_for_file(file_path)
        if isinstance(parser, expected_class):
            print(f"✅ {file_path} → {parser.__class__.__name__}")
            passed += 1
        else:
            print(f"❌ {file_path} → 預期 {expected_class.__name__}，實際 {parser.__class__.__name__}")
            failed += 1

    return passed, failed


def test_unified_interface():
    """測試統一介面"""
    print("\n=== 測試統一介面 ===")

    passed = 0
    failed = 0

    # 測試 DartParser 實作介面
    dart_parser = DartParser()
    if isinstance(dart_parser, LanguageParser):
        print("✅ DartParser 繼承 LanguageParser")
        passed += 1
    else:
        print("❌ DartParser 未繼承 LanguageParser")
        failed += 1

    # 測試 JavaScriptParser 實作介面
    js_parser = JavaScriptParser()
    if isinstance(js_parser, LanguageParser):
        print("✅ JavaScriptParser 繼承 LanguageParser")
        passed += 1
    else:
        print("❌ JavaScriptParser 未繼承 LanguageParser")
        failed += 1

    # 測試屬性
    if dart_parser.language_name == 'Dart':
        print("✅ DartParser language_name = 'Dart'")
        passed += 1
    else:
        print(f"❌ DartParser language_name = '{dart_parser.language_name}'")
        failed += 1

    if js_parser.language_name == 'JavaScript/TypeScript':
        print("✅ JavaScriptParser language_name = 'JavaScript/TypeScript'")
        passed += 1
    else:
        print(f"❌ JavaScriptParser language_name = '{js_parser.language_name}'")
        failed += 1

    if '.dart' in dart_parser.file_extensions:
        print("✅ DartParser file_extensions 包含 .dart")
        passed += 1
    else:
        print("❌ DartParser file_extensions 不包含 .dart")
        failed += 1

    if '.js' in js_parser.file_extensions and '.ts' in js_parser.file_extensions:
        print("✅ JavaScriptParser file_extensions 包含 .js 和 .ts")
        passed += 1
    else:
        print("❌ JavaScriptParser file_extensions 不完整")
        failed += 1

    return passed, failed


def test_function_data_structure():
    """測試 Function 資料結構"""
    print("\n=== 測試 Function 資料結構 ===")

    passed = 0
    failed = 0

    # 測試基本欄位
    func = Function(name='test', line_number=1, has_comment=True)
    if func.name == 'test' and func.line_number == 1 and func.has_comment:
        print("✅ Function 基本欄位正常")
        passed += 1
    else:
        print("❌ Function 基本欄位異常")
        failed += 1

    # 測試預設值
    if func.return_type is None and func.is_async is False and func.function_type == 'function':
        print("✅ Function 預設值正確")
        passed += 1
    else:
        print("❌ Function 預設值錯誤")
        failed += 1

    # 測試 Dart 特定欄位
    dart_func = Function(name='build', line_number=10, has_comment=True, return_type='Widget')
    if dart_func.return_type == 'Widget':
        print("✅ Dart 特定欄位（return_type）可用")
        passed += 1
    else:
        print("❌ Dart 特定欄位異常")
        failed += 1

    # 測試 JavaScript 特定欄位
    js_func = Function(name='fetchData', line_number=15, has_comment=True, is_async=True, function_type='arrow')
    if js_func.is_async and js_func.function_type == 'arrow':
        print("✅ JavaScript 特定欄位（is_async, function_type）可用")
        passed += 1
    else:
        print("❌ JavaScript 特定欄位異常")
        failed += 1

    # 測試跨語言相容性
    functions = [dart_func, js_func]
    if len(functions) == 2 and all(isinstance(f, Function) for f in functions):
        print("✅ 跨語言相容（可放在同一列表）")
        passed += 1
    else:
        print("❌ 跨語言相容性異常")
        failed += 1

    return passed, failed


def test_integration():
    """測試整合流程"""
    print("\n=== 測試整合流程 ===")

    passed = 0
    failed = 0

    # Dart 完整流程
    try:
        language = ParserFactory.detect_language('lib/main.dart')
        parser = ParserFactory.create_parser(language)
        code = "void main() { print('Hello'); }"
        functions = parser.extract_functions(code)

        if len(functions) == 1 and functions[0].name == 'main':
            print("✅ Dart 完整流程正常")
            passed += 1
        else:
            print(f"❌ Dart 完整流程異常（提取到 {len(functions)} 個函式）")
            failed += 1
    except Exception as e:
        print(f"❌ Dart 完整流程異常: {e}")
        failed += 1

    # JavaScript 完整流程
    try:
        parser = ParserFactory.create_parser_for_file('src/app.js')
        code = "function handleClick() { console.log('clicked'); }"
        functions = parser.extract_functions(code)

        if len(functions) == 1 and functions[0].name == 'handleClick':
            print("✅ JavaScript 完整流程正常")
            passed += 1
        else:
            print(f"❌ JavaScript 完整流程異常（提取到 {len(functions)} 個函式）")
            failed += 1
    except Exception as e:
        print(f"❌ JavaScript 完整流程異常: {e}")
        failed += 1

    # 混合語言處理
    try:
        files = [
            ('lib/main.dart', 'void main() { }'),
            ('src/app.js', 'function main() { }'),
            ('src/utils.ts', 'async function fetchData() { }')
        ]

        all_functions = []
        for file_path, code in files:
            if ParserFactory.is_supported(file_path):
                parser = ParserFactory.create_parser_for_file(file_path)
                functions = parser.extract_functions(code)
                all_functions.extend(functions)

        if len(all_functions) == 3:
            print("✅ 混合語言處理正常（提取到 3 個函式）")
            passed += 1
        else:
            print(f"❌ 混合語言處理異常（提取到 {len(all_functions)} 個函式）")
            failed += 1
    except Exception as e:
        print(f"❌ 混合語言處理異常: {e}")
        failed += 1

    return passed, failed


def test_error_handling():
    """測試錯誤處理"""
    print("\n=== 測試錯誤處理 ===")

    passed = 0
    failed = 0

    # 測試不支援的語言
    try:
        ParserFactory.create_parser(Language.UNKNOWN)
        print("❌ 應拋出 ValueError（不支援的語言）")
        failed += 1
    except ValueError as e:
        if "不支援的語言" in str(e):
            print("✅ 正確拋出 ValueError（不支援的語言）")
            passed += 1
        else:
            print(f"❌ 錯誤訊息不正確: {e}")
            failed += 1

    # 測試不支援的檔案
    try:
        ParserFactory.create_parser_for_file('file.xyz')
        print("❌ 應拋出 ValueError（不支援的檔案類型）")
        failed += 1
    except ValueError as e:
        if "不支援的檔案類型" in str(e):
            print("✅ 正確拋出 ValueError（不支援的檔案類型）")
            passed += 1
        else:
            print(f"❌ 錯誤訊息不正確: {e}")
            failed += 1

    # 測試空程式碼處理
    try:
        parser = ParserFactory.create_parser(Language.DART)
        functions = parser.extract_functions('')
        if functions == []:
            print("✅ 空程式碼返回空列表")
            passed += 1
        else:
            print(f"❌ 空程式碼應返回空列表，實際: {functions}")
            failed += 1
    except Exception as e:
        print(f"❌ 空程式碼處理異常: {e}")
        failed += 1

    # 測試 is_supported
    if ParserFactory.is_supported('lib/main.dart'):
        print("✅ is_supported('lib/main.dart') = True")
        passed += 1
    else:
        print("❌ is_supported('lib/main.dart') = False")
        failed += 1

    if not ParserFactory.is_supported('file.xyz'):
        print("✅ is_supported('file.xyz') = False")
        passed += 1
    else:
        print("❌ is_supported('file.xyz') = True")
        failed += 1

    return passed, failed


def main():
    """執行所有測試"""
    print("=" * 60)
    print("Parser Factory 測試套件")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    # 執行所有測試
    tests = [
        test_language_detection,
        test_parser_creation,
        test_unified_interface,
        test_function_data_structure,
        test_integration,
        test_error_handling,
    ]

    for test_func in tests:
        passed, failed = test_func()
        total_passed += passed
        total_failed += failed

    # 統計結果
    print("\n" + "=" * 60)
    print(f"測試結果: {total_passed} 通過, {total_failed} 失敗")
    print("=" * 60)

    if total_failed == 0:
        print("🎉 所有測試通過！")
        return 0
    else:
        print(f"⚠️  有 {total_failed} 個測試失敗")
        return 1


if __name__ == '__main__':
    sys.exit(main())
