"""
JavaScript Parser 手動測試腳本

不需要 pytest，直接執行測試案例並顯示結果

執行方式:
    cd .claude/hooks && python3 tests/manual_test_javascript_parser.py
"""

import sys
from pathlib import Path

# 添加 parsers 模組到路徑
hooks_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_dir))

from parsers.javascript_parser import JavaScriptParser, Function, JS_KEYWORDS


def test_case(name: str, passed: bool, error_msg: str = ""):
    """顯示測試結果"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} {name}")
    if not passed and error_msg:
        print(f"    錯誤: {error_msg}")


def run_tests():
    """執行所有測試案例"""
    parser = JavaScriptParser()
    total_tests = 0
    passed_tests = 0

    print("=" * 60)
    print("JavaScript Parser 測試套件")
    print("=" * 60)

    # === 測試 1: 傳統函式宣告 ===
    total_tests += 1
    code = """
    function testFunction() {
        console.log('test');
    }
    """
    functions = parser.extract_functions(code)
    passed = len(functions) == 1 and functions[0].name == 'testFunction'
    if passed:
        passed_tests += 1
    test_case(
        "測試 1: 傳統函式宣告識別",
        passed,
        f"預期 1 個函式 'testFunction'，實際: {len(functions)}"
    )

    # === 測試 2: const 箭頭函式 ===
    total_tests += 1
    code = """
    const testFunction = () => {
        console.log('test');
    }
    """
    functions = parser.extract_functions(code)
    passed = (len(functions) == 1 and
              functions[0].name == 'testFunction' and
              functions[0].function_type == 'arrow')
    if passed:
        passed_tests += 1
    test_case(
        "測試 2: const 箭頭函式識別",
        passed,
        f"預期 arrow 函式，實際: {functions[0].function_type if functions else 'None'}"
    )

    # === 測試 3: let 箭頭函式 ===
    total_tests += 1
    code = """
    let testFunction = () => {
        console.log('test');
    }
    """
    functions = parser.extract_functions(code)
    passed = len(functions) == 1 and functions[0].name == 'testFunction'
    if passed:
        passed_tests += 1
    test_case("測試 3: let 箭頭函式識別", passed)

    # === 測試 4: 函式表達式 ===
    total_tests += 1
    code = """
    const testFunction = function() {
        console.log('test');
    }
    """
    functions = parser.extract_functions(code)
    passed = len(functions) == 1 and functions[0].name == 'testFunction'
    if passed:
        passed_tests += 1
    test_case("測試 4: 函式表達式識別", passed)

    # === 測試 5: 非同步函式 ===
    total_tests += 1
    code = """
    async function fetchData() {
        return await fetch('/api');
    }
    """
    functions = parser.extract_functions(code)
    passed = (len(functions) == 1 and
              functions[0].name == 'fetchData' and
              functions[0].is_async == True)
    if passed:
        passed_tests += 1
    test_case(
        "測試 5: 非同步函式識別",
        passed,
        f"is_async 應為 True，實際: {functions[0].is_async if functions else 'None'}"
    )

    # === 測試 6: 非同步箭頭函式 ===
    total_tests += 1
    code = """
    const fetchData = async () => {
        return await fetch('/api');
    }
    """
    functions = parser.extract_functions(code)
    passed = (len(functions) == 1 and
              functions[0].is_async == True)
    if passed:
        passed_tests += 1
    test_case("測試 6: 非同步箭頭函式", passed)

    # === 測試 7: export 函式 ===
    total_tests += 1
    code = """
    export function testFunction() {
        console.log('test');
    }

    export const arrowFunction = () => {
        console.log('test');
    }
    """
    functions = parser.extract_functions(code)
    passed = len(functions) == 2
    if passed:
        passed_tests += 1
    test_case(
        "測試 7: export 函式識別",
        passed,
        f"預期 2 個函式，實際: {len(functions)}"
    )

    # === 測試 8: 類別方法 ===
    total_tests += 1
    code = """
    class BookService {
        getBook(id) {
            return books[id];
        }

        async fetchBook(id) {
            return await fetch(`/api/books/${id}`);
        }
    }
    """
    functions = parser.extract_functions(code)
    passed = (len(functions) == 2 and
              functions[0].name == 'getBook' and
              functions[1].name == 'fetchBook' and
              functions[1].is_async == True)
    if passed:
        passed_tests += 1
    test_case(
        "測試 8: 類別方法識別",
        passed,
        f"預期 2 個方法，實際: {len(functions)}"
    )

    # === 測試 9: constructor 不識別 ===
    total_tests += 1
    code = """
    class BookService {
        constructor() {
            this.books = [];
        }
    }
    """
    functions = parser.extract_functions(code)
    passed = len(functions) == 0
    if passed:
        passed_tests += 1
    test_case(
        "測試 9: constructor 不應識別為函式",
        passed,
        f"預期 0 個函式，實際: {len(functions)}"
    )

    # === 測試 10: if 語句不識別 ===
    total_tests += 1
    code = """
    if (condition) {
        console.log('test');
    }
    """
    functions = parser.extract_functions(code)
    passed = len(functions) == 0
    if passed:
        passed_tests += 1
    test_case(
        "測試 10: if 語句不應識別為函式",
        passed,
        f"預期 0 個函式，實際: {len(functions)}"
    )

    # === 測試 11: for 迴圈不識別 ===
    total_tests += 1
    code = """
    for (let i = 0; i < 10; i++) {
        console.log(i);
    }
    """
    functions = parser.extract_functions(code)
    passed = len(functions) == 0
    if passed:
        passed_tests += 1
    test_case("測試 11: for 迴圈不應識別為函式", passed)

    # === 測試 12: while 迴圈不識別 ===
    total_tests += 1
    code = """
    while (condition) {
        doSomething();
    }
    """
    functions = parser.extract_functions(code)
    passed = len(functions) == 0
    if passed:
        passed_tests += 1
    test_case("測試 12: while 迴圈不應識別為函式", passed)

    # === 測試 13: JSDoc 檢測 ===
    total_tests += 1
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
    functions = parser.extract_functions(code)
    passed = (len(functions) == 1 and
              functions[0].has_comment == True)
    if passed:
        passed_tests += 1
    test_case(
        "測試 13: JSDoc 註解檢測",
        passed,
        f"has_comment 應為 True，實際: {functions[0].has_comment if functions else 'None'}"
    )

    # === 測試 14: TypeScript 類型註解支援 ===
    total_tests += 1
    code = """
    function getBook(id: string): Promise<Book> {
        return fetch(`/api/books/${id}`);
    }
    """
    functions = parser.extract_functions(code)
    passed = (len(functions) == 1 and
              functions[0].name == 'getBook')
    if passed:
        passed_tests += 1
    test_case("測試 14: TypeScript 類型註解支援", passed)

    # === 測試 15: TypeScript 泛型支援 ===
    total_tests += 1
    code = """
    function identity<T>(arg: T): T {
        return arg;
    }
    """
    functions = parser.extract_functions(code)
    passed = (len(functions) == 1 and
              functions[0].name == 'identity')
    if passed:
        passed_tests += 1
    test_case("測試 15: TypeScript 泛型支援", passed)

    # === 測試 16: 複雜檔案準確率 ===
    total_tests += 1
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
    functions = parser.extract_functions(code)
    expected_names = [
        'handleBookAdded', '_validateBook', 'fetchBooks',
        'getBook', 'saveBook', 'publicAPI'
    ]
    actual_names = [f.name for f in functions]
    passed = (len(functions) == 6 and
              sorted(actual_names) == sorted(expected_names))
    if passed:
        passed_tests += 1
    test_case(
        "測試 16: 複雜檔案準確率",
        passed,
        f"預期: {expected_names}\n實際: {actual_names}"
    )

    # === 測試 17: 效能測試（1000 個函式）===
    total_tests += 1
    import time
    code = "\n\n".join([f"function func{i}() {{ }}" for i in range(1000)])
    start = time.time()
    functions = parser.extract_functions(code)
    elapsed = (time.time() - start) * 1000  # ms
    passed = elapsed < 100 and len(functions) == 1000
    if passed:
        passed_tests += 1
    test_case(
        f"測試 17: 效能測試（1000 函式）- {elapsed:.2f}ms",
        passed,
        f"執行時間 {elapsed:.2f}ms 超過 100ms 目標" if elapsed >= 100 else ""
    )

    # === 測試 18: 空程式碼不報錯 ===
    total_tests += 1
    functions = parser.extract_functions("")
    passed = len(functions) == 0
    if passed:
        passed_tests += 1
    test_case("測試 18: 空程式碼不報錯", passed)

    # === 測試 19: 多種模式混合 ===
    total_tests += 1
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
    functions = parser.extract_functions(code)
    expected_names = [
        'traditionalFunc', 'arrowFunc', 'letArrow',
        'funcExpr', 'asyncFunc', 'method', 'asyncMethod'
    ]
    actual_names = [f.name for f in functions]
    passed = (len(functions) == 7 and
              sorted(actual_names) == sorted(expected_names))
    if passed:
        passed_tests += 1
    test_case(
        "測試 19: 多種模式混合",
        passed,
        f"預期 7 個函式，實際: {len(functions)}"
    )

    # === 測試 20: getter/setter 不識別 ===
    total_tests += 1
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
    functions = parser.extract_functions(code)
    passed = len(functions) == 0
    if passed:
        passed_tests += 1
    test_case(
        "測試 20: getter/setter 不應識別為函式",
        passed,
        f"預期 0 個函式，實際: {len(functions)}"
    )

    # === 總結 ===
    print("=" * 60)
    print(f"測試完成: {passed_tests}/{total_tests} 通過")
    print(f"通過率: {passed_tests / total_tests * 100:.1f}%")
    print("=" * 60)

    # 如果不是 100% 通過，返回非零退出碼
    if passed_tests != total_tests:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
