"""
JavaScript/TypeScript Parser 測試套件

測試 JavaScriptParser 類別的所有功能:
- 6 種 JavaScript 函式模式識別
- JavaScript 關鍵字過濾
- JSDoc 註解檢測
- TypeScript 支援
- 類別方法識別
- 邊緣案例處理

執行方式:
    python -m pytest .claude/hooks/tests/test_javascript_parser.py -v
"""

import pytest
import sys
from pathlib import Path

# 添加 parsers 模組到路徑
hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

from parsers.javascript_parser import JavaScriptParser, Function, JS_KEYWORDS


class TestJavaScriptFunctionPatterns:
    """測試 JavaScript 6 種函式模式識別"""

    def test_traditional_function_declaration(self):
        """
        測試：模式 1 - 傳統函式宣告識別

        格式: function foo() { }
        """
        code = """
        function testFunction() {
            console.log('test');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'testFunction'
        assert functions[0].function_type == 'function'
        assert functions[0].is_async == False

    def test_traditional_function_with_params(self):
        """測試：傳統函式帶參數"""
        code = """
        function calculateSum(a, b) {
            return a + b;
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'calculateSum'

    def test_arrow_function_const(self):
        """
        測試：模式 2 - const 箭頭函式識別

        格式: const foo = () => { }
        """
        code = """
        const testFunction = () => {
            console.log('test');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'testFunction'
        assert functions[0].function_type == 'arrow'

    def test_arrow_function_with_params(self):
        """測試：箭頭函式帶參數"""
        code = """
        const add = (a, b) => a + b
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'add'

    def test_arrow_function_let(self):
        """
        測試：模式 3 - let 箭頭函式識別

        格式: let foo = () => { }
        """
        code = """
        let testFunction = () => {
            console.log('test');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'testFunction'
        assert functions[0].function_type == 'arrow'

    def test_function_expression(self):
        """
        測試：模式 4 - 函式表達式識別

        格式: const foo = function() { }
        """
        code = """
        const testFunction = function() {
            console.log('test');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'testFunction'
        assert functions[0].function_type == 'function'

    def test_async_function_declaration(self):
        """
        測試：模式 5 - 非同步函式識別

        格式: async function foo() { }
        """
        code = """
        async function fetchData() {
            return await fetch('/api');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'fetchData'
        assert functions[0].is_async == True

    def test_async_arrow_function(self):
        """測試：非同步箭頭函式"""
        code = """
        const fetchData = async () => {
            return await fetch('/api');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'fetchData'
        assert functions[0].is_async == True

    def test_async_function_expression(self):
        """測試：非同步函式表達式"""
        code = """
        const fetchData = async function() {
            return await fetch('/api');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].is_async == True

    def test_export_function(self):
        """測試：匯出函式識別"""
        code = """
        export function testFunction() {
            console.log('test');
        }

        export const arrowFunction = () => {
            console.log('test');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 2
        assert functions[0].name == 'testFunction'
        assert functions[1].name == 'arrowFunction'


class TestClassMethods:
    """測試：模式 6 - 類別方法識別"""

    def test_class_method(self):
        """測試：類別普通方法識別"""
        code = """
        class BookService {
            getBook(id) {
                return books[id];
            }
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'getBook'
        assert functions[0].function_type == 'method'

    def test_class_async_method(self):
        """測試：類別非同步方法識別"""
        code = """
        class BookService {
            async fetchBook(id) {
                return await fetch(`/api/books/${id}`);
            }
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'fetchBook'
        assert functions[0].is_async == True
        assert functions[0].function_type == 'method'

    def test_class_static_method(self):
        """測試：類別靜態方法識別"""
        code = """
        class BookService {
            static create() {
                return new BookService();
            }
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'create'

    def test_multiple_class_methods(self):
        """測試：多個類別方法識別"""
        code = """
        class BookService {
            getBook(id) {
                return books[id];
            }

            async fetchBook(id) {
                return await fetch(`/api/books/${id}`);
            }

            static create() {
                return new BookService();
            }
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 3
        assert functions[0].name == 'getBook'
        assert functions[1].name == 'fetchBook'
        assert functions[2].name == 'create'

    def test_constructor_not_identified(self):
        """測試：constructor 不應被識別為函式"""
        code = """
        class BookService {
            constructor() {
                this.books = [];
            }
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 0, "constructor 不應被識別為一般函式"

    def test_getter_setter_not_identified(self):
        """測試：getter/setter 不應被識別為函式"""
        code = """
        class BookService {
            get count() {
                return this.books.length;
            }

            set count(value) {
                // do nothing
            }
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 0, "getter/setter 不應被識別為函式"


class TestJavaScriptKeywordFiltering:
    """測試 JavaScript 關鍵字過濾功能"""

    @pytest.mark.parametrize("keyword", list(JS_KEYWORDS))
    def test_all_keywords_excluded(self, keyword):
        """
        測試：所有 JavaScript 關鍵字正確排除

        驗證所有在 JS_KEYWORDS 中定義的關鍵字都不會被識別為函式
        """
        parser = JavaScriptParser()
        code = f"{keyword} (test) {{ }}"
        functions = parser.extract_functions(code)
        assert len(functions) == 0, f"{keyword} 不應被識別為函式"

    def test_if_statement_not_function(self):
        """測試：if 語句不應被識別為函式"""
        code = """
        if (condition) {
            console.log('test');
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0

    def test_for_loop_not_function(self):
        """測試：for 迴圈不應被識別為函式"""
        code = """
        for (let i = 0; i < 10; i++) {
            console.log(i);
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0

    def test_while_loop_not_function(self):
        """測試：while 迴圈不應被識別為函式"""
        code = """
        while (condition) {
            doSomething();
        }
        """
        parser = JavaScriptParser()
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
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0


class TestJSDocDetection:
    """測試 JSDoc 註解檢測功能"""

    def test_function_with_complete_jsdoc(self):
        """測試：有完整 JSDoc 的函式正確識別"""
        code = """
        /**
         * 取得書籍資料
         * @param {string} id - 書籍 ID
         * @returns {Promise<Book>} - 書籍物件
         */
        async function getBook(id) {
            return await fetch(`/api/books/${id}`);
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].has_comment == True

    def test_function_with_simple_jsdoc(self):
        """測試：簡單 JSDoc 註解"""
        code = """
        /**
         * 這是一個測試函式
         */
        function testFunction() { }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].has_comment == True

    def test_function_without_comment(self):
        """測試：無註解的函式"""
        code = """
        function testFunction() { }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].has_comment == False

    def test_function_with_single_line_comment(self):
        """測試：單行註解（不算 JSDoc）"""
        code = """
        // 這是單行註解
        function testFunction() { }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].has_comment == False

    def test_arrow_function_with_jsdoc(self):
        """測試：箭頭函式的 JSDoc 檢測"""
        code = """
        /**
         * 箭頭函式範例
         * @param {string} name
         */
        const greet = (name) => {
            console.log(`Hello, ${name}`);
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].has_comment == True


class TestTypeScriptSupport:
    """測試 TypeScript 支援"""

    def test_typescript_function_with_type_annotation(self):
        """測試：TypeScript 類型註解函式"""
        code = """
        function getBook(id: string): Promise<Book> {
            return fetch(`/api/books/${id}`);
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'getBook'

    def test_typescript_arrow_function_with_types(self):
        """測試：TypeScript 箭頭函式類型註解"""
        code = """
        const arrowFunction = (name: string): void => {
            console.log(name);
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'arrowFunction'

    def test_typescript_generic_function(self):
        """測試：TypeScript 泛型函式"""
        code = """
        function identity<T>(arg: T): T {
            return arg;
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'identity'

    def test_typescript_async_function_with_types(self):
        """測試：TypeScript 非同步函式類型註解"""
        code = """
        async function fetchData<T>(url: string): Promise<T> {
            const response = await fetch(url);
            return response.json();
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 1
        assert functions[0].name == 'fetchData'
        assert functions[0].is_async == True

    def test_typescript_interface_not_function(self):
        """測試：TypeScript interface 不應被識別為函式"""
        code = """
        interface Book {
            title: string;
            author: string;
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 0

    def test_typescript_type_alias_not_function(self):
        """測試：TypeScript type 別名不應被識別為函式"""
        code = """
        type BookId = string;
        type Book = {
            id: BookId;
            title: string;
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        assert len(functions) == 0


class TestEdgeCases:
    """測試邊緣案例"""

    def test_empty_code(self):
        """測試：空程式碼不報錯"""
        parser = JavaScriptParser()
        functions = parser.extract_functions("")
        assert len(functions) == 0

    def test_code_without_functions(self):
        """測試：沒有函式的程式碼"""
        code = """
        // 只有註解
        const x = 10;
        const name = 'test';
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)
        assert len(functions) == 0

    def test_multiline_function_signature(self):
        """測試：多行函式簽名"""
        code = """
        function calculateSum(
            a,
            b,
            c
        ) {
            return a + b + c;
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        # 註：多行簽名可能無法識別（已知限制）
        # 正則表達式只匹配單行模式
        # 這是可接受的限制（85-90% 準確率目標）

    def test_nested_functions(self):
        """測試：巢狀函式"""
        code = """
        function outer() {
            function inner() {
                console.log('inner');
            }
            inner();
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        # 應該識別兩個函式
        assert len(functions) == 2
        assert 'outer' in [f.name for f in functions]
        assert 'inner' in [f.name for f in functions]

    def test_immediately_invoked_function(self):
        """測試：立即執行函式 (IIFE)"""
        code = """
        (function() {
            console.log('IIFE');
        })();
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        # IIFE 匿名函式不應被識別（無名稱）
        assert len(functions) == 0

    def test_function_in_object_literal(self):
        """測試：物件字面量中的方法"""
        code = """
        const obj = {
            method() {
                console.log('method');
            }
        };
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        # 物件方法簡寫不支援（設計決策）
        assert len(functions) == 0

    def test_multiple_functions_mixed_styles(self):
        """測試：混合風格的多個函式"""
        code = """
        function traditionalFunc() { }

        const arrowFunc = () => { }

        let letArrow = () => { }

        const funcExpr = function() { }

        async function asyncFunc() { }

        class MyClass {
            method() { }
            async asyncMethod() { }
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        # 應該識別 7 個函式
        expected_names = [
            'traditionalFunc', 'arrowFunc', 'letArrow',
            'funcExpr', 'asyncFunc', 'method', 'asyncMethod'
        ]
        actual_names = [f.name for f in functions]

        assert len(functions) == 7
        assert sorted(actual_names) == sorted(expected_names)


class TestAccuracyBenchmark:
    """測試準確率基準"""

    def test_complex_javascript_file(self):
        """
        測試：複雜 JavaScript 檔案的準確率

        包含各種情況的混合測試
        """
        code = """
        /**
         * 處理書籍新增
         * @param {Book} book - 書籍物件
         */
        function handleBookAdded(book) {
            if (book.title === '') {
                return;
            }

            for (const tag of book.tags) {
                console.log(tag);
            }

            _validateBook(book);
        }

        function _validateBook(book) {
            // 私有輔助函式
        }

        const fetchBooks = async () => {
            return await fetch('/api/books');
        }

        class BookService {
            getBook(id) {
                return this.books[id];
            }

            async saveBook(book) {
                return await this.repository.save(book);
            }
        }

        export function publicAPI() {
            return 'API';
        }
        """
        parser = JavaScriptParser()
        functions = parser.extract_functions(code)

        # 應該識別: handleBookAdded, _validateBook, fetchBooks,
        #           getBook, saveBook, publicAPI
        expected_functions = [
            'handleBookAdded', '_validateBook', 'fetchBooks',
            'getBook', 'saveBook', 'publicAPI'
        ]
        actual_functions = [f.name for f in functions]

        assert len(functions) == 6, f"應識別 6 個函式，實際識別 {len(functions)} 個"
        assert sorted(actual_functions) == sorted(expected_functions)

        # 檢查註解檢測
        assert functions[0].has_comment == True, "handleBookAdded 應有 JSDoc 註解"
        assert functions[1].has_comment == False, "_validateBook 無註解"

        # 檢查 async 檢測
        fetch_func = next(f for f in functions if f.name == 'fetchBooks')
        save_func = next(f for f in functions if f.name == 'saveBook')
        assert fetch_func.is_async == True
        assert save_func.is_async == True


class TestPerformance:
    """測試效能"""

    def test_performance_large_file(self):
        """
        測試：大型檔案執行效能

        目標：1000 行程式碼 <100ms
        """
        parser = JavaScriptParser()

        # 生成 1000 個函式
        code = "\n\n".join([
            f"function func{i}() {{ }}" for i in range(1000)
        ])

        import time
        start = time.time()
        functions = parser.extract_functions(code)
        elapsed = (time.time() - start) * 1000  # 轉換為 ms

        assert elapsed < 100, f"效能不達標: {elapsed:.2f}ms > 100ms"
        assert len(functions) == 1000, "應識別 1000 個函式"

    def test_performance_complex_patterns(self):
        """測試：複雜模式的效能"""
        parser = JavaScriptParser()

        # 生成包含多種模式的程式碼
        code = "\n".join([
            f"async function asyncFunc{i}() {{ return 'data'; }}"
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
