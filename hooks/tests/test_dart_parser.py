"""
Dart Parser 測試套件

測試 DartParser 類別的所有功能:
- Dart 關鍵字過濾
- Widget 建構式過濾
- 正常函式識別
- 註解檢測
- 邊緣案例處理

執行方式:
    python -m pytest .claude/hooks/tests/test_dart_parser.py -v
"""

import pytest
import sys
from pathlib import Path

# 添加 parsers 模組到路徑
hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

from parsers.dart_parser import DartParser, Function, DART_KEYWORDS


class TestDartKeywordFiltering:
    """測試 Dart 關鍵字過濾功能"""

    @pytest.mark.parametrize("keyword", list(DART_KEYWORDS))
    def test_all_keywords_excluded(self, keyword):
        """
        測試：所有 Dart 關鍵字正確排除

        驗證所有在 DART_KEYWORDS 中定義的關鍵字都不會被識別為函式
        """
        parser = DartParser()
        code = f"{keyword} (test) {{ }}"
        functions = parser.extract_functions(code)
        assert len(functions) == 0, f"{keyword} 不應被識別為函式"

    def test_if_statement_not_function(self):
        """
        測試：if 語句不應被識別為函式

        這是最常見的誤判案例之一
        """
        code = """
        if (condition) {
            print('test');
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0, "if 不應被識別為函式"

    def test_for_loop_not_function(self):
        """測試：for 迴圈不應被識別為函式"""
        code = """
        for (var i = 0; i < 10; i++) {
            print(i);
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0

    def test_while_loop_not_function(self):
        """測試：while 迴圈不應被識別為函式"""
        code = """
        while (condition) {
            doSomething();
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0

    def test_switch_statement_not_function(self):
        """測試：switch 語句不應被識別為函式"""
        code = """
        switch (value) {
            case 1:
                break;
            default:
                break;
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0


class TestWidgetConstructorFiltering:
    """測試 Widget 建構式過濾功能"""

    def test_sized_box_not_function(self):
        """
        測試：SizedBox 不應被識別為函式

        這是第二常見的誤判案例
        """
        code = """
        Widget build(BuildContext context) {
            return SizedBox(width: 10);
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        # 應該只識別 build，不識別 SizedBox
        assert len(functions) == 1, "應該只識別 build 函式"
        assert functions[0].name == 'build', "識別的函式應該是 build"

    @pytest.mark.parametrize("widget_name", [
        "Container", "Text", "Column", "Row", "ListView",
        "SizedBox", "Padding", "Center", "Scaffold", "AppBar",
        "FloatingActionButton", "IconButton", "TextField"
    ])
    def test_common_widgets_excluded(self, widget_name):
        """
        測試：常見 Widget 建構式正確排除

        驗證 PascalCase 命名的 Widget 建構式不會被誤判
        """
        code = f"return {widget_name}(child: Text('test'));"
        parser = DartParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0, f"{widget_name} 不應被識別為函式"

    def test_custom_widget_class_not_function(self):
        """測試：自定義 Widget 類別不被識別為函式"""
        code = """
        class MyCustomWidget extends StatelessWidget {
            @override
            Widget build(BuildContext context) {
                return Container();
            }
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        # 應該只識別 build，不識別 MyCustomWidget
        assert len(functions) == 1
        assert functions[0].name == 'build'


class TestNormalFunctionDetection:
    """測試正常函式識別功能"""

    def test_void_function_detected(self):
        """測試：void 函式正確識別"""
        code = """
        void testFunction() {
            print('test');
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'testFunction'
        assert functions[0].return_type == 'void'

    def test_future_function_detected(self):
        """測試：Future 函式正確識別"""
        code = """
        Future<String> fetchData() async {
            return 'data';
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'fetchData'
        assert 'Future' in functions[0].return_type

    def test_stream_function_detected(self):
        """測試：Stream 函式正確識別"""
        code = """
        Stream<int> countStream() async* {
            yield 1;
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'countStream'
        assert 'Stream' in functions[0].return_type

    def test_operation_result_function_detected(self):
        """測試：OperationResult 函式正確識別"""
        code = """
        OperationResult<Book> addBook(Book book) {
            return OperationResult.success(book);
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'addBook'
        assert 'OperationResult' in functions[0].return_type

    def test_multiple_functions_detected(self):
        """測試：多個函式正確識別"""
        code = """
        void functionA() { }

        int functionB() { return 1; }

        Future<void> functionC() async { }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 3
        assert [f.name for f in functions] == ['functionA', 'functionB', 'functionC']

    def test_function_with_parameters(self):
        """測試：帶參數的函式正確識別"""
        code = """
        int calculateSum(int a, int b) {
            return a + b;
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'calculateSum'


class TestCommentDetection:
    """測試註解檢測功能"""

    def test_function_with_complete_comment(self):
        """測試：有完整註解的函式正確識別"""
        code = """
        /// 【需求來源】UC-01: 測試用例
        /// 【規格文件】docs/test.md
        void testFunction() { }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].has_comment == True

    def test_function_with_simple_comment(self):
        """測試：有簡單註解的函式（不完整）"""
        code = """
        /// 這是一個測試函式
        void testFunction() { }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        # 簡單註解不算完整註解
        assert functions[0].has_comment == False

    def test_function_without_comment(self):
        """測試：無註解的函式正確識別"""
        code = """
        void testFunction() { }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].has_comment == False

    def test_function_with_multiline_comment(self):
        """測試：多行註解正確檢測"""
        code = """
        /// 【需求來源】UC-01
        /// 【規格文件】docs/test.md
        /// 【工作日誌】v0.12.1.md
        void testFunction() { }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].has_comment == True


class TestEdgeCases:
    """測試邊緣案例"""

    def test_empty_code(self):
        """測試：空程式碼不報錯"""
        parser = DartParser()
        functions = parser.extract_functions("")
        assert len(functions) == 0

    def test_code_without_functions(self):
        """測試：沒有函式的程式碼"""
        code = """
        // 只有註解
        int x = 10;
        String name = 'test';
        """
        parser = DartParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0

    def test_multiline_function_signature(self):
        """測試：多行函式簽名正確處理"""
        code = """
        Future<OperationResult<Book>> addBook(
            Book book,
            {bool validate = true}
        ) async {
            return OperationResult.success(book);
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'addBook'

    def test_private_function_detected(self):
        """測試：私有函式（_開頭）正確識別"""
        code = """
        void _privateFunction() { }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == '_privateFunction'

    def test_function_with_underscore_in_name(self):
        """測試：名稱中包含底線的函式"""
        code = """
        void test_function_name() { }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'test_function_name'

    def test_getter_method_not_detected(self):
        """測試：getter 方法不應被識別為函式"""
        code = """
        String get name => _name;
        """
        parser = DartParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0

    def test_setter_method_not_detected(self):
        """測試：setter 方法不應被識別為函式"""
        code = """
        set name(String value) => _name = value;
        """
        parser = DartParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0


class TestAccuracyBenchmark:
    """測試準確率基準"""

    def test_complex_dart_file(self):
        """
        測試：複雜 Dart 檔案的準確率

        包含各種情況的混合測試
        """
        code = """
        /// 【需求來源】UC-01
        /// 【規格文件】docs/test.md
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
            // 私有輔助函式
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
            return 'data';
        }
        """
        parser = DartParser()
        functions = parser.extract_functions(code)

        # 應該識別: handleBookAdded, _validateBook, build, fetchData
        expected_functions = ['handleBookAdded', '_validateBook', 'build', 'fetchData']
        actual_functions = [f.name for f in functions]

        assert len(functions) == 4, f"應識別 4 個函式，實際識別 {len(functions)} 個"
        assert actual_functions == expected_functions, f"函式識別不正確: {actual_functions}"

        # 檢查註解檢測
        assert functions[0].has_comment == True, "handleBookAdded 應有完整註解"
        assert functions[1].has_comment == False, "_validateBook 無註解"


class TestPerformance:
    """測試效能"""

    def test_performance_large_file(self):
        """
        測試：大型檔案執行效能

        目標：1000 行程式碼 <100ms
        """
        parser = DartParser()

        # 生成 1000 個函式
        code = "\n\n".join([
            f"void function{i}() {{ }}" for i in range(1000)
        ])

        import time
        start = time.time()
        functions = parser.extract_functions(code)
        elapsed = (time.time() - start) * 1000  # 轉換為 ms

        assert elapsed < 100, f"效能不達標: {elapsed:.2f}ms > 100ms"
        assert len(functions) == 1000, "應識別 1000 個函式"

    def test_performance_complex_patterns(self):
        """測試：複雜模式的效能"""
        parser = DartParser()

        # 生成包含多種模式的程式碼
        code = "\n".join([
            f"Future<String> asyncFunc{i}() async {{ return 'data'; }}"
            for i in range(100)
        ])

        import time
        start = time.time()
        functions = parser.extract_functions(code)
        elapsed = (time.time() - start) * 1000

        assert elapsed < 50, f"複雜模式效能不達標: {elapsed:.2f}ms > 50ms"
        assert len(functions) == 100


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v", "--tb=short"])
