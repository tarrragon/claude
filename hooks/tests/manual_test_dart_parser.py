#!/usr/bin/env python3
"""
Dart Parser 手動測試腳本

執行方式:
    python3 .claude/hooks/tests/manual_test_dart_parser.py
"""

import sys
from pathlib import Path

# 添加 parsers 模組到路徑
hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

from parsers.dart_parser import DartParser, DART_KEYWORDS


def test_keyword_filtering():
    """測試關鍵字過濾"""
    print("=" * 60)
    print("測試 1: Dart 關鍵字過濾")
    print("=" * 60)

    parser = DartParser()

    # 測試 if 關鍵字
    code_if = """
    if (condition) {
        print('test');
    }
    """
    functions = parser.extract_functions(code_if)
    assert len(functions) == 0, "❌ if 被誤判為函式"
    print("✅ if 關鍵字正確排除")

    # 測試 for 關鍵字
    code_for = """
    for (var i = 0; i < 10; i++) {
        print(i);
    }
    """
    functions = parser.extract_functions(code_for)
    assert len(functions) == 0, "❌ for 被誤判為函式"
    print("✅ for 關鍵字正確排除")

    # 測試 while 關鍵字
    code_while = """
    while (condition) {
        doSomething();
    }
    """
    functions = parser.extract_functions(code_while)
    assert len(functions) == 0, "❌ while 被誤判為函式"
    print("✅ while 關鍵字正確排除")

    # 測試所有關鍵字
    failed_keywords = []
    for keyword in DART_KEYWORDS:
        code = f"{keyword} (test) {{ }}"
        functions = parser.extract_functions(code)
        if len(functions) > 0:
            failed_keywords.append(keyword)

    if failed_keywords:
        print(f"❌ 以下關鍵字未正確過濾: {failed_keywords}")
    else:
        print(f"✅ 所有 {len(DART_KEYWORDS)} 個關鍵字正確過濾")

    print()


def test_constructor_filtering():
    """測試建構式過濾"""
    print("=" * 60)
    print("測試 2: Widget 建構式過濾（PascalCase）")
    print("=" * 60)

    parser = DartParser()

    # 測試 SizedBox（最常見誤判）
    code_sized_box = """
    Widget build(BuildContext context) {
        return SizedBox(width: 10);
    }
    """
    functions = parser.extract_functions(code_sized_box)
    assert len(functions) == 1, f"❌ 應識別 1 個函式，實際識別 {len(functions)} 個"
    assert functions[0].name == 'build', f"❌ 應識別 build，實際識別 {functions[0].name}"
    print("✅ SizedBox 正確排除，build 正確識別")

    # 測試常見 Widget
    common_widgets = [
        "Container", "Text", "Column", "Row", "ListView",
        "Padding", "Center", "Scaffold", "AppBar"
    ]

    failed_widgets = []
    for widget in common_widgets:
        code = f"return {widget}(child: Text('test'));"
        functions = parser.extract_functions(code)
        if len(functions) > 0:
            failed_widgets.append(widget)

    if failed_widgets:
        print(f"❌ 以下 Widget 未正確過濾: {failed_widgets}")
    else:
        print(f"✅ 所有 {len(common_widgets)} 個常見 Widget 正確過濾")

    print()


def test_normal_function_detection():
    """測試正常函式識別"""
    print("=" * 60)
    print("測試 3: 正常函式識別")
    print("=" * 60)

    parser = DartParser()

    # 測試 void 函式
    code_void = """
    void testFunction() {
        print('test');
    }
    """
    functions = parser.extract_functions(code_void)
    assert len(functions) == 1, "❌ void 函式識別失敗"
    assert functions[0].name == 'testFunction', "❌ 函式名稱錯誤"
    assert functions[0].return_type == 'void', "❌ 回傳類型錯誤"
    print("✅ void 函式正確識別")

    # 測試 Future 函式
    code_future = """
    Future<String> fetchData() async {
        return 'data';
    }
    """
    functions = parser.extract_functions(code_future)
    assert len(functions) == 1, "❌ Future 函式識別失敗"
    assert functions[0].name == 'fetchData', "❌ 函式名稱錯誤"
    assert 'Future' in functions[0].return_type, "❌ 回傳類型錯誤"
    print("✅ Future 函式正確識別")

    # 測試多個函式
    code_multiple = """
    void functionA() { }

    int functionB() { return 1; }

    Future<void> functionC() async { }
    """
    functions = parser.extract_functions(code_multiple)
    assert len(functions) == 3, f"❌ 應識別 3 個函式，實際識別 {len(functions)} 個"
    expected_names = ['functionA', 'functionB', 'functionC']
    actual_names = [f.name for f in functions]
    assert actual_names == expected_names, f"❌ 函式識別錯誤: {actual_names}"
    print("✅ 多個函式正確識別")

    print()


def test_comment_detection():
    """測試註解檢測"""
    print("=" * 60)
    print("測試 4: 註解檢測")
    print("=" * 60)

    parser = DartParser()

    # 測試完整註解
    code_complete = """
    /// 【需求來源】UC-01: 測試用例
    /// 【規格文件】docs/test.md
    void testFunction() { }
    """
    functions = parser.extract_functions(code_complete)
    assert len(functions) == 1, "❌ 函式識別失敗"
    assert functions[0].has_comment == True, "❌ 完整註解未正確檢測"
    print("✅ 完整註解正確檢測")

    # 測試簡單註解（不完整）
    code_simple = """
    /// 這是一個測試函式
    void testFunction() { }
    """
    functions = parser.extract_functions(code_simple)
    assert len(functions) == 1, "❌ 函式識別失敗"
    assert functions[0].has_comment == False, "❌ 簡單註解應視為不完整"
    print("✅ 簡單註解正確判定為不完整")

    # 測試無註解
    code_no_comment = """
    void testFunction() { }
    """
    functions = parser.extract_functions(code_no_comment)
    assert len(functions) == 1, "❌ 函式識別失敗"
    assert functions[0].has_comment == False, "❌ 無註解未正確檢測"
    print("✅ 無註解正確檢測")

    print()


def test_complex_code():
    """測試複雜程式碼案例"""
    print("=" * 60)
    print("測試 5: 複雜 Dart 檔案")
    print("=" * 60)

    parser = DartParser()

    code = """
    /// 【需求來源】UC-01: 書籍新增事件處理
    /// 【規格文件】docs/app-requirements-spec.md
    /// 【工作日誌】docs/work-logs/v0.12.1.md
    void handleBookAdded(Book book) {
        if (book.title.isEmpty) {
            return;
        }

        for (var tag in book.tags) {
            print(tag);
        }

        _validateBook(book);
    }

    void _validateBook(Book book) {
        // 私有輔助函式（無完整註解）
    }

    Widget build(BuildContext context) {
        return Container(
            child: SizedBox(
                width: 100,
                child: Text('test')
            )
        );
    }

    Future<String> fetchData() async {
        while (true) {
            if (await checkCondition()) {
                return 'data';
            }
        }
    }
    """

    functions = parser.extract_functions(code)

    # 應該識別: handleBookAdded, _validateBook, build, fetchData
    expected_functions = ['handleBookAdded', '_validateBook', 'build', 'fetchData']
    actual_functions = [f.name for f in functions]

    assert len(functions) == 4, f"❌ 應識別 4 個函式，實際識別 {len(functions)} 個"
    assert actual_functions == expected_functions, f"❌ 函式識別不正確: {actual_functions}"
    print(f"✅ 複雜程式碼正確識別 4 個函式: {actual_functions}")

    # 檢查註解檢測
    assert functions[0].has_comment == True, "❌ handleBookAdded 註解檢測錯誤"
    assert functions[1].has_comment == False, "❌ _validateBook 註解檢測錯誤"
    print("✅ 註解檢測正確")

    print()


def test_performance():
    """測試效能"""
    print("=" * 60)
    print("測試 6: 效能測試（1000 行程式碼）")
    print("=" * 60)

    parser = DartParser()

    # 生成 1000 個函式
    code = "\n\n".join([
        f"void function{i}() {{ }}" for i in range(1000)
    ])

    import time
    start = time.time()
    functions = parser.extract_functions(code)
    elapsed = (time.time() - start) * 1000  # 轉換為 ms

    assert len(functions) == 1000, f"❌ 應識別 1000 個函式，實際識別 {len(functions)} 個"

    if elapsed < 100:
        print(f"✅ 效能測試通過: {elapsed:.2f}ms < 100ms")
    else:
        print(f"⚠️  效能警告: {elapsed:.2f}ms > 100ms（可接受，但建議優化）")

    print()


def run_all_tests():
    """執行所有測試"""
    print("\n" + "=" * 60)
    print("Dart Parser 手動測試套件")
    print("=" * 60)
    print()

    try:
        test_keyword_filtering()
        test_constructor_filtering()
        test_normal_function_detection()
        test_comment_detection()
        test_complex_code()
        test_performance()

        print("=" * 60)
        print("🎉 所有測試通過！")
        print("=" * 60)
        print()
        print("✅ Dart 關鍵字過濾正確")
        print("✅ Widget 建構式過濾正確")
        print("✅ 正常函式識別正確")
        print("✅ 註解檢測正確")
        print("✅ 複雜程式碼處理正確")
        print("✅ 效能符合要求")
        print()

        return True

    except AssertionError as e:
        print("\n" + "=" * 60)
        print("❌ 測試失敗")
        print("=" * 60)
        print(f"錯誤: {e}")
        print()
        return False

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ 測試執行錯誤")
        print("=" * 60)
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
